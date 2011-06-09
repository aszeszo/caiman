#!/usr/bin/python
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
''' Code specific for the implementation of the InstallLogger'''
import logging
import logging.handlers
import os
import shutil
import socket
import struct
import time

# Global variables
_PID = str(os.getpid())
DEFAULTLOG = '/var/tmp/install/default_log' + '.' + _PID
DEFAULTPROGRESSFORMAT = '%(progress)s %(msg)s'
DEFAULTLOGLEVEL = logging.DEBUG
DEFAULTDESTINATION = '/var/tmp/install/dest'
MAX_INT = 100

INSTALL_LOGGER_NAME = "InstallationLogger"


class LogInitError(Exception):
    '''Raised if error occurs during initialization of logging'''
    pass


class LoggerError(Exception):
    '''Raised if a fatal error occurs in the logger'''
    pass


class ProgressFilter(logging.Filter):
    '''Filters records to determine if a progress message should
       be logged to a handler.
    '''

    def __init__(self, log_progress=True):
        self._log_progress = log_progress
        logging.Filter.__init__(self, name='')

    def filter(self, record):
        '''Checks to see if a record has a progress attribute or levelno'''
        if self._log_progress:
            return hasattr(record, 'progress') or hasattr(record, 'levelno')
        else:
            return not hasattr(record, 'progress')


class HTTPHandler(logging.handlers.HTTPHandler):
    '''The HTTPHandler super class doesn't have a preamble,
       which is required by the installer interface.
    '''

    def __init__(self, host, url, preamble, method="GET"):
        self._preamble = preamble
        logging.handlers.HTTPHandler.__init__(self, host, url, method="GET")


class FileHandler(logging.FileHandler):
    '''The FileHandler super class doesn't check to make sure a
       directory exists, so the check is done here.
    '''

    def __init__(self, filename, mode='a', encoding=None, delay=0):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename), mode=0777)

        # The mode may be set differently by the consumer, so
        # it should be passed through to the constructor.
        logging.FileHandler.__init__(self, filename, mode=mode,
            encoding=encoding, delay=delay)

    def transfer_log(self, destination, isdir=False):
        ''' transfer_log() - method to move the log from its original location
            to the location specified in the destination variable

            isdir - boolean argument to specify the destination is a directory.
            The log file will be moved from it's current location to the
            destination directory
        '''
        # clear out any records in the stream
        if self.stream:
            self.stream.flush()
            self.stream.close()

        # make sure the directory (or parent directory) exists
        if isdir:
            if not os.path.exists(destination):
                os.makedirs(destination)
        else:
            if not os.path.exists(os.path.split(destination)[0]):
                os.makedirs(os.path.split(destination)[0])

        # if the destination is a directory, copy the log file over.  If not,
        # copy the logfile to the renamed file specified
        if isdir:
            newfile = os.path.join(destination,
                                   os.path.basename(self.baseFilename))
            shutil.copy(self.baseFilename, newfile)
            self.baseFilename = newfile
        else:
            shutil.copy(self.baseFilename, destination)
            self.baseFilename = os.path.abspath(destination)

        # reopen the file with a mode of "a"
        self.mode = "a"
        self.stream = self._open()


class InstallFormatter(logging.Formatter):
    '''Sub-class the Formatter class to handle
       the progress records.
    '''

    def format(self, rec):
        if rec.levelno == MAX_INT:
            if self._fmt != DEFAULTPROGRESSFORMAT:
                self._fmt = 'PROGRESS REPORT: progress percent:' + \
                    '%(progress)s %(msg)s'
            rec.message = rec.getMessage()
            message_string = self._fmt % rec.__dict__
            return message_string
        else:
            try:
                return logging.Formatter(
                    fmt=InstallLogger.INSTALL_FORMAT).format(rec)
            except:
                return "Improper logging format. Log message dropped."


class ProgressLogRecord(logging.LogRecord):
    '''Used to construct the log record for the progress reporting'''

    def __init__(self, msg=None, progress=None, name='Progress', level=MAX_INT,
            pathname=None, lineno=None, args=None, exc_info=None, func=None):
        self.msg = msg
        self.progress = None
        self.levelno = level
        logging.LogRecord.__init__(self, name, level, pathname, lineno,
                 msg, args, exc_info, func=func)

        if InstallLogger.ENGINE is None:
            raise LoggerError("No engine is defined for logging")

        if progress >= 0:
            self.progress =  \
                InstallLogger.ENGINE.normalize_progress(progress)


class ProgressHandler(logging.handlers.SocketHandler):
    '''The ProgressHandler manages records that are sent via the
       report_progress method of the InstallLogger. It sends progress records
       to a progress receiver. This can be a remote socket of an on disk file.
       The ProgressHandler provides its own formatting, which formats the data
       for the progress receiver. The ProgressHandler is instantiated as a
       singleton.
    '''

    def __init__(self, host, port):
        logging.handlers.SocketHandler.__init__(self, host, port)

        self.host = host
        self.port = port
        self.createSocket()

    def send(self, data):
        '''Send a string to the socket. This is modified slightly from the
           logging SocketHandler's send method in order to manage the
           progress records.
        '''
        if not self.sock:
            self.createSocket()

        if self.sock:
            try:
                if hasattr(self.sock, "sendall"):
                    self.sock.sendall(struct.pack('@i', len(data)) + data)
                    # A small timeout in case the socket buffer is full
                    time.sleep(.05)
                else:
                    sentsofar = 0
                    left = len(data)
                    while left > 0:
                        sent = self.sock.send(data[sentsofar:])
                        sentsofar = sentsofar + sent
                        left = left - sent
            except socket.error:
                self.sock.close()
                self.sock = None  # so we can call createSocket next time

    def emit(self, record):
        # Format a record and emit the record to the socket.
        try:
            msg = self.format(record)
            self.send(msg)
        except:
            self.handleError(record)


class InstallLogger(logging.Logger):
    '''Sub-Class for logging in the install environment'''

    # Class variables used with the InstallLogger
    ENGINE = None
    DEFAULTFILEHANDLER = None
    INSTALL_FORMAT = '%(asctime)-25s %(name)-10s ' \
        '%(levelname)-10s %(message)-50s'

    def __init__(self, name, level=None):
        # If logging level was not provided, choose the desired default one.
        # Use DEFAULTLOGLEVEL for top level logger, while default to
        # logging.NOTSET for sub-loggers. That instructs Python logging to
        # inherit logging level from parent.
        if level is None:
            if "." in name:
                level = logging.NOTSET
            else:
                level = DEFAULTLOGLEVEL

        logging.Logger.__init__(self, name, level=level)
        self._prog_filter = ProgressFilter(log_progress=True)
        self._no_prog_filter = ProgressFilter(log_progress=False)

        # MAX_INT is the level that is associated with progress
        # reporting. The following commands add MAX_INT to the
        # logger's dictionary of log levels.
        logging.addLevelName(MAX_INT, 'MAX_INT')
        logging.addLevelName('MAX_INT', MAX_INT)

        # Make sure DEFAULTLOG is usable by everyone, even if created by root.
        logdir = os.path.dirname(DEFAULTLOG)
        if not os.path.exists(logdir):
            os.mkdir(logdir)
        statbuf = os.stat(logdir)
        if (statbuf.st_mode & 01777) != 01777:
            os.chmod(logdir, 01777)

        # Create the default log
        if not InstallLogger.DEFAULTFILEHANDLER:
            InstallLogger.DEFAULTFILEHANDLER = FileHandler(filename=DEFAULTLOG,
                                                            mode='a')
            InstallLogger.DEFAULTFILEHANDLER.setLevel(DEFAULTLOGLEVEL)
            InstallLogger.DEFAULTFILEHANDLER.setFormatter(InstallFormatter())
            logging.Logger.addHandler(self, InstallLogger.DEFAULTFILEHANDLER)
            InstallLogger.DEFAULTFILEHANDLER.addFilter(self._prog_filter)

    @property
    def default_log(self):
        '''Returns the name of the default log '''
        return DEFAULTLOG

    @property
    def name(self):
        '''returns the name of the logger'''
        return self.name

    def addHandler(self, handler):
        '''Adds the requested handler to the InstallLogger
           Performs special handling if it is a progress handler
        '''
        logging.Logger.addHandler(self, handler)

        if isinstance(handler, ProgressHandler):
            handler.addFilter(self._prog_filter)
            handler.setLevel(MAX_INT)
            handler.setFormatter(InstallFormatter(fmt='%(progress)s %(msg)s'))
        else:
            handler.addFilter(self._no_prog_filter)
            if handler.formatter is None:
                handler.setFormatter(InstallFormatter())

    def report_progress(self, msg=None, progress=None):
        '''Logs progress reports to the progress receiver'''
        assert(0 <= progress <= 100)
        prog_record = ProgressLogRecord(msg, progress)
        self.handle(prog_record)

    def transfer_log(self, destination=DEFAULTDESTINATION):
        '''
        Requests a transfer of the default log to a requested location,
        currently just another location on disk. It also adds the log
        location to a log file list that is available once logging completes.
        '''
        isDir = os.path.isdir(destination)
        InstallLogger.DEFAULTFILEHANDLER.transfer_log(destination, \
                                                      isDir)

    def close(self):
        '''Terminates logging and provides a list of log files'''

        close_log_list = []
        # Collect the location of log files
        for val in logging.Logger.manager.loggerDict.values():
            for handler in val.handlers:
                if isinstance(handler, FileHandler) and \
                    handler.baseFilename not in close_log_list:
                    close_log_list.append(handler.baseFilename)

        logging.shutdown()
        return close_log_list

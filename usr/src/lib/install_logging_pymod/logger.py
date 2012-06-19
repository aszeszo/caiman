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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#
''' Code specific for the implementation of the InstallLogger'''
import errno
import logging
import logging.handlers
import os
import shutil
import socket
import struct
import time

# Global variables
DEFAULTPROGRESSFORMAT = '%(progress)s %(msg)s'
DEFAULTLOGLEVEL = logging.DEBUG
DEFAULTDESTINATION = '/var/tmp/install/dest'
MAX_INT = 100

INSTALL_LOGGER_NAME = "InstallationLogger"


class InstallManager(logging.Manager):
    '''A sub-class of the logging.Manager that exists for the purpose
       of allowing applications to pass in a default log rather than
       using the default log provided by the installLogger class.
    '''
    def getLogger(self, name, log=None, level=None, exclusive_rw=False):
        """
        This getLogger method allows the application to pass in the following
        input:

        - name: Required. The name of the logger

        - log: Optional. If a default log is included, it will be set
          up as the default log location for the logging process.

        - level: Optional. This value may be set for a default log
          file. If it is not set, the logger sets to DEBUG as the default
          value. The format of the level should follow the format of
          the logging module. For example, logging.DEBUG, logging.INFO.

        - exclusive_rw - Optional. Opens the file in a more secure mode. It
          ensures safe log file creation and gives the file restrictive
          permissions. If it is not set, it defaults to False.

        These values are passed to the InstallLogger to set up a custom default
        log file.

        The placeholder code is an adjunct to the python logging module.
        It is used to manage the logging hierarchy. Because this getLogger
        method interfaces with the logging hierarchy, it is necessary to
        comply with that structure.
        """
        logger_name = None
        logging._acquireLock()
        try:
            if name in logging.Logger.manager.loggerDict:
                logger_name = logging.Logger.manager.loggerDict[name]
                if isinstance(logger_name, logging.PlaceHolder):
                    placeholder_for_fixup = logger_name
                    logger_name = \
                        logging._loggerClass(name, default_log=log,
                            level=level, exclusive_rw=exclusive_rw)
                    logger_name.manager = self
                    logging.Logger.manager.loggerDict[name] = logger_name
                    self._fixupChildren(placeholder_for_fixup, logger_name)
                    self._fixupParents(logger_name)
            else:
                logger_name = logging._loggerClass(name, default_log=log,
                    level=level, exclusive_rw=exclusive_rw)
                logger_name.manager = self
                logging.Logger.manager.loggerDict[name] = logger_name
                self._fixupParents(logger_name)
        finally:
            logging._releaseLock()
        return logger_name


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

    def __init__(self, filename, mode='a', encoding=None, delay=0,
        exclusive_rw=False):
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename), mode=0777)

        if exclusive_rw:
            delay = True

        # The mode may be set differently by the consumer, so
        # it should be passed through to the constructor.
        logging.FileHandler.__init__(self, filename, mode=mode,
            encoding=encoding, delay=delay)

        if exclusive_rw:
            fd = os.open(self.baseFilename,
                os.O_CREAT | os.O_EXCL | os.O_RDWR, 0644)
            self.stream = os.fdopen(fd, mode)

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

    def __init__(self, name, default_log=None, level=None, exclusive_rw=False):
        # If logging level was not provided, choose the desired default one.
        # Use DEFAULTLOGLEVEL for top level logger, while default to
        # logging.NOTSET for sub-loggers. That instructs Python logging to
        # inherit logging level from parent.

        self.default_log_file = None
        self._prog_filter = ProgressFilter(log_progress=True)
        self._no_prog_filter = ProgressFilter(log_progress=False)

        if InstallLogger.DEFAULTFILEHANDLER is not None:
            logging.Logger.__init__(self, name)
            return

        if not InstallLogger.DEFAULTFILEHANDLER and default_log:
            self.default_log_file = default_log

        self.exclusive_rw = exclusive_rw

        if level is None:
            if "." in name:
                level = logging.NOTSET
            else:
                level = DEFAULTLOGLEVEL

        logging.Logger.__init__(self, name, level=level)

        # MAX_INT is the level that is associated with progress
        # reporting. The following commands add MAX_INT to the
        # logger's dictionary of log levels.
        logging.addLevelName(MAX_INT, 'MAX_INT')
        logging.addLevelName('MAX_INT', MAX_INT)

        # Initialize the default log.
        if not InstallLogger.DEFAULTFILEHANDLER and self.default_log_file:
            logdir = os.path.dirname(self.default_log_file)

            if not os.path.exists(logdir):
                try:
                    os.makedirs(logdir)
                except OSError as err:
                    if err.errno != errno.EEXIST:
                        raise

                # Make sure default log file is usable by everyone,
                # even if created by root.
                statbuf = os.stat(logdir)
                if (statbuf.st_mode & 01777) != 01777:
                    os.chmod(logdir, 01777)

            InstallLogger.DEFAULTFILEHANDLER = \
                FileHandler(filename=self.default_log_file, mode='a',
                    exclusive_rw=self.exclusive_rw)
            InstallLogger.DEFAULTFILEHANDLER.setLevel(level)
            InstallLogger.DEFAULTFILEHANDLER.setFormatter(InstallFormatter())
            logging.Logger.addHandler(self, InstallLogger.DEFAULTFILEHANDLER)
            InstallLogger.DEFAULTFILEHANDLER.addFilter(self._prog_filter)

    @property
    def default_log(self):
        '''Returns the name of the default log '''
        return InstallLogger.DEFAULTFILEHANDLER.baseFilename

    @property
    def name(self):
        '''returns the name of the logger'''
        return self.name

    @property
    def default_fh(self):
        '''returns the default FileHandler for the logging process'''
        return InstallLogger.DEFAULTFILEHANDLER

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
            if hasattr(val, 'handlers'):
                for handler in val.handlers:
                    if isinstance(handler, FileHandler) and \
                        handler.baseFilename not in close_log_list:
                        close_log_list.append(handler.baseFilename)

        logging.shutdown()
        return close_log_list


# Create an instance of the InstallManager. This is a sub-class of
# the logging module manager. We want to use the same hierarchy
# for this manager, so instantiate it with the root logger from
# the logging module.
InstallLogger.manager = InstallManager(logging.Logger.root)

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

import cStringIO
import filecmp
import solaris_install.logger
import logging
import os
import random
import thread
import time
import unittest
from solaris_install.logger import InstallLogger, LogInitError
import socket
import struct
import sys

LOGGER = None
INSTALL_LOGGER_NAME = 'InsLggr'
TEST_RESULTS_FILE = '/var/tmp/install/tests/'


#A Simple Socket Receiver for Testing

def parse_msg(the_socket, cb_function):
    '''Parse the messages sent by the client.'''
    total_len = 0
    total_data = []
    size = sys.maxint
    size_data = sock_data = ''
    recv_size = 8192
    percent = None
    msg = None

    while total_len < size:
        sock_data = the_socket.recv(recv_size)
        if not total_data:
            if len(sock_data) > 4:
                size_data += sock_data
                size = struct.unpack('@i', size_data[:4])[0]
                recv_size = size
                if recv_size > 524288:
                    recv_size = 524288
                total_data.append(size_data[4:])
            else:
                size_data += sock_data
        else:
            total_data.append(sock_data)
        total_len = sum([len(i) for i in total_data])
        message = ''.join(total_data)
        if message:
            # This is a callback function that sends the
            # back to test to be verified
            cb_function(message)
            percent, msg = message.split(' ', 1)
        break
    return percent, msg


def start_server(host, port, cb_function):
    """Starts the server socket stream to receive messages"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(5)
    engine_sock, address = sock.accept()
    while True:
        percentage, mssg = parse_msg(engine_sock, cb_function)
        if percentage and float(percentage) <= 100:
            if "complete" in mssg:
                break
        else:
            break
    engine_sock.close()


class SingletonError():
    '''Occurs when one attempts to instantiate a second singleton'''
    pass


class TestInstallEngine(object):
    '''Simple Engine for testing with the installLogger'''

    _instance = None

    def __new__(cls):

        if TestInstallEngine._instance is None:
            TestInstallEngine._instance = object.__new__(cls)
            return TestInstallEngine._instance
        else:
            raise SingletonError("TestInstallEngine instance already exists",
                                 TestInstallEngine._instance)

    def __init__(self):
        self._init_logging()

    def _init_logging(self):
        '''Initializes the logger'''
        logging.setLoggerClass(InstallLogger)
        global LOGGER
        InstallLogger.ENGINE = self
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)
        LOGGER.setLevel(logging.DEBUG)

        if not isinstance(LOGGER, InstallLogger):
            raise LogInitError("install logger not of correct type!")
        LOGGER.debug('Beginning the Engine')

    def normalize_progress(self, cp_progress):
        '''Calculates a number and returns the result'''
        overall_progress = (1 * (float(cp_progress) / 100))
        return overall_progress


class TestInstallLogger(unittest.TestCase):
    '''Tests the Functionality of the InstallLogger subclass'''

    def setUp(self):
        self.pid = str(os.getpid())
        self.eng = TestInstallEngine()
        self.test_logger = logging.getLogger('InsLggr.TestLogger')
        self.logfile = None
        self.list = []

    def tearDown(self):
        self.eng = None
        TestInstallEngine._instance = None
        InstallLogger.DEFAULTFILEHANDLER = None
        logging.Logger.manager.loggerDict = {}
        logging.setLoggerClass(logging.Logger)
        self.test_logger.name = None
        logging._defaultFormatter = logging.Formatter()

        try:
            os.remove(solaris_install.logger.DEFAULTLOG)
        except:
            # File doesn't exist
            pass

        try:
            os.remove("/var/tmp/install")
        except OSError:
            # File doesn't exist
            pass

        try:
            os.remove("simplelog")
        except OSError:
            # File doesn't exist
            pass

        try:
            os.rmdir('/var/tmp/installLog')
        except OSError:
            # File doesn't exist
            pass

        try:
            os.remove('/var/tmp/sourcefile')
        except OSError:
            # File doesn't exist
            pass

        try:
            os.remove('stream.log')
        except OSError:
            # File doesn't exist
            pass

        try:
            os.remove('/var/tmp/install/fhtest')
        except OSError:
            # File doesn't exist
            pass

    def test_get_logger(self):
        '''Ensure that logger instance is from InstallLogger'''
        thelogger = logging.getLogger('theLogger')
        self.failIf(not isinstance(thelogger, InstallLogger))

    def test_get_default_log(self):
        '''Ensure that default log is returned with default_log method'''
        dlog = self.test_logger.default_log
        self.failIf(dlog != solaris_install.logger.DEFAULTLOG)

    def test_get_log_name(self):
        '''Ensure that logger name is returned correctly'''
        logName = self.test_logger.name
        self.failIf(logName != "InsLggr.TestLogger")

    def test_create_second_logger_instance(self):
        '''Ensure that only one InstallLogger is created for Install Logger'''
        self.second_logger = logging.getLogger('SecLogger')
        self.assertEqual(self.second_logger.name, 'SecLogger')
        fh = logging.FileHandler('simplelog')
        self.second_logger.addHandler(fh)
        self.second_logger.info('This is from the second logger')

        logfile = solaris_install.logger.DEFAULTLOG
        logtext = open(logfile).read()
        logsearch = "This is from the second logger"
        index = logtext.find(logsearch)
        self.assertEqual(index, -1, 'message is in default log and \
            should not be')

    def test_add_FileHandler(self):
        '''Ensure that FileHandlers can be added to a logger'''
        fh = solaris_install.logger.FileHandler('/var/tmp/install/fhtest')
        fh.setLevel(logging.CRITICAL)
        self.test_logger.addHandler(fh)
        self.failIf(not os.path.exists('/var/tmp/install/fhtest'))

    def test_exclude_log_message(self):
        '''Ensure that a log message below the designated level does not log'''
        fh = solaris_install.logger.FileHandler('/var/tmp/install/fhtest')
        fh.setLevel(logging.CRITICAL)
        self.test_logger.addHandler(fh)
        self.failIf(not os.path.exists('/var/tmp/install/fhtest'))
        self.test_logger.critical('critical message')
        self.test_logger.debug('debug message')
        logtext = open('/var/tmp/install/fhtest').read()
        logsearch = "critical message"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find the critical in log")
        logsearch = "debug message"
        index = logtext.find(logsearch)
        self.assertEqual(-1, index, "debug message erroneously logged")

    def test_add_StreamHandler(self):
        '''Ensure that StreamHandlers can be added to a logger'''
        self.list = []
        saveerr = sys.stderr
        outfil = open('stream.log', 'a')
        sys.stderr = outfil
        self.test_logger.addHandler(logging.StreamHandler())
        self.test_logger.info('This is a stream message')
        sys.stderr = saveerr
        logtext = open('stream.log').read()
        logsearch = "This is a stream message"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find the stream message in log")

    def test_create_defaultlog(self):
        '''Ensure default_log is created and uses the default format.'''
        self.failIf(not os.path.exists(solaris_install.logger.DEFAULTLOG))

    def test_log_debug_message(self):
        '''Ensure that debug log messages are logged to the log file'''
        self.test_logger.debug('This is a debug message')
        logfile = solaris_install.logger.DEFAULTLOG
        logtext = open(logfile).read()
        logsearch = "This is a debug message"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find debug message in default log")

    def test_log_warning_message(self):
        '''Ensure that warning log messages are logged to the log file'''
        self.test_logger.warning('This is a warning message')
        logfile = solaris_install.logger.DEFAULTLOG
        logtext = open(logfile).read()
        logsearch = "This is a warning message"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find warning message in default log")

    def test_log_info_message(self):
        '''Ensure that info log messages are logged to the log file'''
        self.test_logger.info('This is an info message')
        logfile = solaris_install.logger.DEFAULTLOG
        logtext = open(logfile).read()
        logsearch = "This is an info message"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find info message in default log")

    def test_default_format(self):
        '''Ensure that default format is set for the InstallLogger'''
        self.assertEqual(InstallLogger.INSTALL_FORMAT, \
            '%(asctime)-25s %(name)-10s %(levelname)-10s %(message)-50s')

    def test_transfer_log_destonly(self):
        '''Ensure that default log transfers to destination'''
        dest_dir = "/var/tmp/installLog/"
        base_name = os.path.basename(solaris_install.logger.DEFAULTLOG)
        test_filename = "/var/tmp/installLog/" + base_name
        self.test_logger.transfer_log(destination=dest_dir)
        self.failIf(not os.path.exists(test_filename))

    def test_transfer_log_src(self):
        '''Ensure that source file transfers to desired destination'''
        dest_file = "/var/tmp/installLog/"
        src_filename = "/var/tmp/sourcefile"

        #Create a source file and add a log message to it
        test_source_file = open(src_filename, 'w')
        test_source_file.write("This is a log message")
        test_source_file.close()

        self.test_logger.transfer_log( \
            source=src_filename, destination=dest_file)
        base_name = os.path.basename(src_filename)
        test_filename = "/var/tmp/installLog/" + base_name
        self.failIf(not os.path.exists(test_filename))
        self.failIf(not filecmp.cmp(src_filename, test_filename))

    def test_close(self):
        '''Ensure that InstallLogger close works'''
        test_list = ['/var/tmp/install/default_log.' + self.pid]
        test_close_list = self.test_logger.close()
        self.assertEquals(test_list, test_close_list)


class TestProgressHandler(unittest.TestCase):
    '''Tests the Functionality of the ProgressHandler'''

    def setUp(self):
        self.pid = str(os.getpid())
        self.eng = TestInstallEngine()
        self.test_logger = logging.getLogger('InsLggr.TestLogger')

        # Create parameters for the progress receiver
        random.seed()
        self.portno = random.randint(10000, 30000)
        self.hostname = 'localhost'

        # Create a default ProgressHandler
        proghdlr = solaris_install.logger.ProgressHandler( \
            host=self.hostname, port=self.portno)
        self.test_logger.addHandler(proghdlr)

        # This test uses a callback function to check the
        # functionality of sending progress messages to a
        # progress receiver.
        # Parameters that are used with callback functionality
        self.callfunction = None
        self.list = []

    def tearDown(self):
        self.eng = None
        TestInstallEngine._instance = None
        InstallLogger.DEFAULTFILEHANDLER = None
        logging.Logger.manager.loggerDict = {}
        logging.setLoggerClass(logging.Logger)
        self.test_logger.name = None
        self.test_logger.destination = None
        self.test_logger.level = None
        self.test_logger.parent = None
        self.test_logger.propagate = 1
        self.test_logger.handlers = []
        self.test_logger.disabled = 0
        self.callfunction = None
        self.list = []
        logging._defaultFormatter = logging.Formatter()

        try:
            os.remove(solaris_install.logger.DEFAULTLOG)
        except OSError:
            # File doesn't exist
            pass

        try:
            os.remove("simplelog")
        except OSError:
            # File doesn't exist
            pass

    def test_add_second_progresshandler(self):
        '''Test that a second progress handler can be added'''

        def setCallback(cb_func):
            '''Sets the parameter to the given callback function'''
            self.callfunction = cb_func

        def OnData(data):
            '''Calls the callback function with the given data'''
            self.callfunction(data)

        def DataCallback(msg):
            '''Callback function appends message to a list'''
            self.list.append(msg)

        setCallback(DataCallback)

        thread.start_new_thread(start_server, \
            ('localhost', 2555, OnData))

        time.sleep(1)

        proghdlr2 = solaris_install.logger.ProgressHandler( \
            'localhost', 2555)
        self.test_logger.addHandler(proghdlr2)
        self.test_logger.report_progress( \
            'this is a progress message with percentage 10', progress=10)
        testmsg = ["0.1 this is a progress message with percentage 10"]
        self.assertEqual(testmsg, self.list)

    def test_ProgressLogMessage(self):
        '''Test the message returned by ProgressLogRecord get_message'''
        msg = 'progress message'
        progress = 50
        prog_record = solaris_install.logger.ProgressLogRecord(msg, progress)
        prog_msg = prog_record.getMessage()
        self.assertEqual(msg, prog_msg)

    def test_progress_reported_to_default_log(self):
        ''''Tests that progress is reported to the default log'''

        self.test_logger.report_progress( \
            'this is a progress message with percentage 10', progress=10)

        logfile = solaris_install.logger.DEFAULTLOG
        logtext = open(logfile).read()
        logsearch = "PROGRESS REPORT: progress percent:0.1" + \
            " this is a progress message with percentage 10"
        index = logtext.find(logsearch)
        self.assertNotEqual(-1, index, \
            "Failed to find progress message in default log")

    def test_report_progress_fail(self):
        '''Tests that report_progress fails if value is invalid'''
        self.failUnlessRaises(AssertionError, self.test_logger.report_progress, \
            'this is a progress message with percentage -1', progress=-1)

    def test_progress_reported_to_receiver(self):
        '''Test that progress is reported to the progress receiver'''

        # These functions are used to register a callback which
        # tests the messages sent to the progress receiver.

        def setCallback(cb_func):
            '''Callback function variable'''
            self.callfunction = cb_func

        def OnData(data):
            '''Calls the callback function with the given data'''
            self.callfunction(data)

        def DataCallback(msg):
            '''Callback function appends message to a list'''
            self.list.append(msg)

        setCallback(DataCallback)

        # Start the progress receiver
        thread.start_new_thread(start_server, \
            (self.hostname, self.portno, OnData))

        time.sleep(1)

        self.test_logger.report_progress( \
            'this is a progress message with percentage 10', progress=10)
        testmsg = ["0.1 this is a progress message with percentage 10"]
        self.assertEqual(testmsg, self.list)

if __name__ == '__main__':
    unittest.main()

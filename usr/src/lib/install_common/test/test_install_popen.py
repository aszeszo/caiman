#!/usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#


import subprocess
import sys
import test.test_subprocess
import time
import unittest

from solaris_install import Popen, CalledProcessError


class MockLogger(object):
    
    def __init__(self, enabled_for):
        self.enabled_for = enabled_for
        self.msgs = {}
    
    def isEnabledFor(self, value):
        return value >= self.enabled_for
    
    def log(self, level, msg, *args):
        self.msgs.setdefault(level, []).append(msg % tuple(args))


class TestInstallPopen(unittest.TestCase):
    
    def cmd(self, exitcode):
        return [sys.executable, "-c",
                "import sys;"
                "print '--stdout--';"
                "print >> sys.stderr, '--stderr--';"
                "sys.exit(%s)" % exitcode]
    
    def test_capture_stdout(self):
        '''Popen.check_call(..., stdout=Popen.STORE) captures stdout'''
        popen = Popen.check_call(self.cmd(0), stdout=Popen.STORE)
        self.assertEqual(popen.stdout, "--stdout--\n")
    
    def test_capture_stderr(self):
        '''Popen.check_call(..., stderr=Popen.STORE) captures stderr'''
        popen = Popen.check_call(self.cmd(0), stderr=Popen.STORE,
                                 check_result=(0,))
        self.assertEqual(popen.stderr, "--stderr--\n")
    
    def test_stderr_exception(self):
        '''Popen.check_call(..., check_result=(Popen.STDERR_EMPTY, 0) raises exception on stderr'''
        try:
            popen = Popen.check_call(self.cmd(0), stderr=Popen.STORE,
                                     check_result=(Popen.STDERR_EMPTY, 0))
        except CalledProcessError as err:
            self.assertEquals("--stderr--\n", err.popen.stderr)
            self.assertEquals(0, err.popen.returncode)
        else:
            self.fail("Expected CalledProcessError when stderr non-empty")
    
    def test_log_out(self):
        '''Popen.check_call(..., logger=some_logger) logs stdout'''
        logger = MockLogger(100)
        popen = Popen.check_call(self.cmd(0), stdout=Popen.STORE,
                                 logger=logger, stdout_loglevel=100)
        self.assertTrue(sys.executable in logger.msgs[100][0])
        self.assertEqual("--stdout--", logger.msgs[100][1])
    
    def test_log_err(self):
        '''Popen.check_call(..., logger=some_logger) logs stderr'''
        logger = MockLogger(100)
        popen = Popen.check_call(self.cmd(0), stderr=Popen.STORE,
                                 logger=logger, stderr_loglevel=100,
                                 check_result=(0,))
        self.assertTrue("--stderr--" in logger.msgs[100][0],
                        logger.msgs[100][0])
    
    def test_log_long_output(self):
        '''Popen.check_call() correctly logs commands with lots of output'''
        output_length = Popen.LOG_BUFSIZE * 2
        logger = MockLogger(100)
        cmd = [sys.executable, "-c",
               "for x in xrange(%s): print x" % output_length]
        popen = Popen.check_call(cmd, stdout=subprocess.PIPE, logger=logger,
                                 stdout_loglevel=100)
        expected = "\n".join([str(x) for x in xrange(output_length)])
        actual = "\n".join(logger.msgs[100][1:])
        for idx, chr in enumerate(actual):
            # Each character is checked, rather than the string as a whole,
            # so that 10 characters of context can be added to the failure
            # message to assist with diagnosing the problem
            if chr != expected[idx]:
                actual_context = actual[(idx - 10):(idx + 10)]
                expected_context = expected[(idx - 10):(idx + 10)]
                self.fail("%r != %r" % (actual_context, expected_context))
        self.assertEqual(len(expected), len(actual),
                         "%r not found at end of actual output" %
                         expected[len(actual):])
    
    def test_log_blank_lines_ignored(self):
        '''Popen.check_call() skips logging of blank lines of output'''
        logger = MockLogger(100)
        lines = '\\n' * 6
        expected_log = ['\n' * 6]
        cmd = [sys.executable, "-c",
               "import sys;"
               "sys.stderr.write('%s')" % lines]
        popen = Popen.check_call(cmd, stderr=subprocess.PIPE, logger=logger,
                                 stdout_loglevel=0, stderr_loglevel=100,
                                 check_result=Popen.ANY)
        
        # No output should have been logged to the MockLogger
        self.assertFalse(100 in logger.msgs, logger.msgs.get(100, ''))
    
    def test_devnull(self):
        '''Test using Popen.DEVNULL for stdin'''
        popen = Popen(["/usr/bin/cat"], stdin=Popen.DEVNULL, stdout=Popen.PIPE)
        # Use PIPE for stdout as, for a failure case, the subprocess call
        # could hang indefinitely, so we can't block on it
        
        for wait_count in xrange(10):
            # If it's not done nearly instantly, something is wrong.
            # However, give the benefit of the doubt by waiting up to
            # 5 seconds for completion
            if popen.poll() is not None:
                break
            else:
                time.sleep(0.5)
        else:
            popen.kill()
            self.fail("stdin=Popen.DEVNULL did not work")
        
        stdout = popen.communicate()[0]
        self.assertEqual("", stdout)
    
    def test_check_result(self):
        '''Popen.check_call() check_result keyword arg raises errors appropriately'''
        try:
            popen = Popen.check_call(self.cmd(0), check_result=(0, 4))
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
        try:
            popen = Popen.check_call(self.cmd(4), check_result=(0, 4))
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
        self.assertRaises(CalledProcessError, Popen.check_call, self.cmd(5),
                          check_result=(0, 4))
    
    def test_check_result_ignore(self):
        '''Popen.check_call(..., check_result=Popen.ANY) ignores return codes'''
        try:
            popen = Popen.check_call(self.cmd(0), check_result=Popen.ANY)
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
        
        cmd2 = [sys.executable, "-c",
                "import sys;"
                "print '--stdout--';"
                "sys.exit(0)"]
        try:
            popen = Popen.check_call(cmd2, check_result=Popen.ANY)
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
        
        try:
            popen = Popen.check_call(self.cmd(4), check_result=Popen.ANY)
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
    
    def test_logging_no_hang(self):
        '''Try to ensure Popen.check_call doesn't hang when trying to do logging'''
        
        # To ensure the logger keyword arg is implemented in a way that
        # doesn't cause hangs, and since the use of logger causes blocking
        # behavior, spawn a non-blocking subprocess that spawns a blocking
        # subprocess. If the non-blocking subprocess doesn't complete
        # in a reasonable amount of time, kill both and fail
        cmd = [sys.executable, "-c",
               "from solaris_install import Popen; import logging; "
               "Popen.check_call(['/usr/bin/pkg', 'foo'], "
               "logger=logging.getLogger())"]
        
        popen = Popen(cmd, stdout=Popen.DEVNULL, stderr=Popen.DEVNULL)
        for wait_count in xrange(15):
            # If it's not done nearly instantly, something is wrong.
            # However, give the benefit of the doubt by waiting up to
            # 5 seconds for completion
            if popen.poll() is not None:
                break
            else:
                time.sleep(0.5)
        else:
            popen.kill()
            self.fail("subprocess hung while attempting logging")
    
    def test_logger_no_stdout_stderr(self):
        '''Popen.check_call() fails to run if logger is set but no output would be received'''
        self.assertRaises(ValueError, Popen.check_call, self.cmd(0),
                          logger="MyLogger")


class TestInstallPopenCompatible(test.test_subprocess.ProcessTestCase):
    '''Ensure compatibility with subprocess.Popen by running the
    subprocess.Popen's test suite against solaris_install.Popen
    
    '''
    def setUp(self):
        self.__Popen = subprocess.Popen
        subprocess.Popen = Popen
        super(TestInstallPopenCompatible, self).setUp()
    
    def tearDown(self):
        subprocess.Popen = self.__Popen
        super(TestInstallPopenCompatible, self).tearDown()

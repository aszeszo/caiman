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
        popen = Popen(self.cmd(0), stdout=Popen.STORE)
        self.assertEqual(popen.stdout, "--stdout--\n")
    
    def test_capture_stderr(self):
        popen = Popen(self.cmd(0), stderr=Popen.STORE, check_result=(0,))
        self.assertEqual(popen.stderr, "--stderr--\n")
    
    def test_stderr_exception(self):
        try:
            popen = Popen(self.cmd(0), stderr=Popen.STORE,
                          check_result=(Popen.STDERR_EMPTY,))
        except CalledProcessError as err:
            self.assertEquals("--stderr--\n", err.popen.stderr)
            self.assertEquals(0, err.popen.returncode)
        else:
            self.fail("Expected CalledProcessError when stderr non-empty")
    
    def test_log_out(self):
        logger = MockLogger(100)
        popen = Popen(self.cmd(0), stdout=Popen.STORE, logger=logger,
                      stdout_loglevel=100)
        self.assertTrue(sys.executable in logger.msgs[100][0])
        self.assertEqual("--stdout--", logger.msgs[100][1])
    
    def test_log_err(self):
        logger = MockLogger(100)
        popen = Popen(self.cmd(0), stderr=Popen.STORE, logger=logger,
                      stderr_loglevel=100, check_result=(0,))
        self.assertTrue("--stderr--" in logger.msgs[100][0],
                        logger.msgs[100][0])
    
    def test_log_long_output(self):
        output_length = Popen.LOG_BUFSIZE * 2
        logger = MockLogger(100)
        cmd = [sys.executable, "-c",
               "for x in xrange(%s): print x" % output_length]
        popen = Popen(cmd, stdout=subprocess.PIPE, logger=logger,
                      stdout_loglevel=100)
        expected = "\n".join([str(x) for x in xrange(output_length)]) + "\n"
        actual = "\n".join(logger.msgs[100][1:])
        for idx, chr in enumerate(actual):
            if chr != expected[idx]:
                actual_context = actual[idx-10:idx+10]
                expected_context = expected[idx-10:idx+10]
                self.fail("%r != %r" % (actual_context, expected_context))
        self.assertEqual(len(expected), len(actual))
    
    def test_check_result(self):
        try:
            popen = Popen(self.cmd(0), check_result=(0, 4))
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)
        try:
            popen = Popen(self.cmd(4), check_result=(0, 4))
        except CalledProcessError as err:
            self.fail("Unexpected CalledProcessError: %s" % err)


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


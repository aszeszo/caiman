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

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''


import logging
import unittest

import solaris_install.sysconfig as sysconfig


class TestSysconfig(unittest.TestCase):
    def test_parse_options_subcommand(self):
        '''parse_options() returns proper subcommmand'''
        (options, sub_cmd) = sysconfig._parse_options(["create-profile"])
        self.assertEqual(sub_cmd[0], "create-profile")
    
    def test_parse_options_no_flags(self):
        '''parse_options() returns proper default options'''
        (options, sub_cmd) = sysconfig._parse_options(["create-profile"])
        self.assertEqual(options.logname, sysconfig.DEFAULT_LOG_LOCATION)
        self.assertEqual(options.log_level,
                         getattr(logging, sysconfig.DEFAULT_LOG_LEVEL.upper()))
        self.assertFalse(options.force_bw)
        self.assertFalse(options.debug)
    
    def test_parse_options_accepts_flags(self):
        '''parse_options() accepts "create-profile -l <log> -b -o <profile>"'''
        (options, sub_cmd) = sysconfig._parse_options(["create-profile", "-l",
                                                       "/foo/log.txt", "-b",
                                                       "-o", "/foo/sc.xml"])
        self.assertEqual(options.logname, "/foo/log.txt")
        self.assertEqual(options.profile, "/foo/sc.xml")
        self.assertTrue(options.force_bw)
    
    def test_parse_options_log_level_valid(self):
        '''parse_options() properly reformats error, warn, info,
           debug and input'''
        levels = ["error", "warn", "info", "debug"]
        
        for level in levels:
            (options, sub_cmd) = sysconfig._parse_options(["create-profile",
                                                           "-v", level])
            self.assertEqual(options.log_level,
                             getattr(logging, level.upper()))
            if level == "debug":
                self.assertTrue(options.debug)
            else:
                self.assertFalse(options.debug)
        
        (options, sub_cmd) = sysconfig._parse_options(["create-profile", "-v",
                                                       "input"])
        self.assertEqual(options.log_level, sysconfig.LOG_LEVEL_INPUT)
        self.assertTrue(options.debug)
    
    def test_parse_options_invalid_log_level(self):
        '''parse_options() rejects unsupported log levels'''
        self.assertRaises(SystemExit, sysconfig._parse_options,
                          ["create-profile", "-v", "foo"])

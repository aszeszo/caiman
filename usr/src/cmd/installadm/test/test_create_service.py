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

import unittest
import osol_install.auto_install.create_service as create_service


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.''' 

    def test_parse_one_arg(self):
        '''Ensure one args caught'''
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_invalid_servicename(self):
        '''Ensure invalid servicename caught'''

        myargs = ["-n", "new=svc"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_alias_bad_options(self):
        '''Ensure invalid options combinations caught'''

        myargs = ["-t", "aliasof_name", "-s", "/tmp/myiso.iso"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-d", "/tmp/myimage"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-c", "5"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-i", "10.100.100.100"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_no_src_or_alias(self):
        '''Ensure missing source and missing alias caught'''

        myargs = ["-c", "5", "-i", "10.100.100.100"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_no_errors(self):
        '''Ensure successful command parsing'''

        myargs = ["-n", "myservice", "-s", "/tmp/myiso.iso"]
        options = create_service.parse_options(myargs)
        self.assertEquals(options.svcname, "myservice")
        self.assertEquals(options.srcimage, "/tmp/myiso.iso")



if __name__ == '__main__':
    unittest.main()

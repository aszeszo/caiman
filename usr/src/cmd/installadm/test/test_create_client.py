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
import osol_install.auto_install.create_client as create_client


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.''' 

    def test_parse_no_options(self):
        '''Ensure no options caught'''
        self.assertRaises(SystemExit, create_client.parse_options, [])

    def test_parse_invalid_options_args(self):
        '''Ensure invalid option flagged'''

        myargs = ["-m", "mysvc", "-e", "aa:bb:cc:dd:ee:ff", "-u"]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

        myargs = ["-n", "mysvc",  "-f", "aa:bb:cc:dd:ee:ff" ]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

        myargs = ["-n", "mysvc",  "-e", "aa:bb:cc:dd:ee:ff", "invalidarg"]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n",  "-e", "aa:bb:cc:dd:ee:ff" ]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

        myargs = ["-n", "mysvc",  "-e" ]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

        myargs = ["-n", "-e" ]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

    def test_parse_invalid_mac(self):
        '''Ensure invalid mac address flagged'''

        myargs = ["aabbccddee"]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)

        myargs = ["aa:bb:cc:dd:ee"]
        self.assertRaises(SystemExit, create_client.parse_options, myargs)


if __name__ == '__main__':
    unittest.main()

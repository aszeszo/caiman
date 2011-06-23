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
import osol_install.auto_install.rename_service as rename_service


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.''' 

    def test_parse_no_args(self):
        '''Ensure no args caught'''
        myargs = []
        self.assertRaises(SystemExit, rename_service.parse_options, myargs)

    def test_parse_one_arg(self):
        '''Ensure one args caught'''
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, rename_service.parse_options, myargs)

    def test_parse_three_args(self):
        '''Ensure three args caught'''
        myargs = ["mysvc", "newsvc", "threesacrowd"]
        self.assertRaises(SystemExit, rename_service.parse_options, myargs)

    def test_parse_invalid_servicename(self):
        '''Ensure invalid servicename caught'''

        myargs = ["mysvc", "new=svc"]
        self.assertRaises(SystemExit, rename_service.parse_options, myargs)


    def test_parse_options_novalue(self):
        '''Ensure option caught'''
        myargs = ["-n", "mysvc", "new=svc"]
        self.assertRaises(SystemExit, rename_service.parse_options, myargs)



if __name__ == '__main__':
    unittest.main()

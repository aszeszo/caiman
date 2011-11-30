#!/usr/bin/python3.6
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

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import unittest

import osol_install.auto_install.set_service as set_service


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.'''

    def test_parse_invalid_options_args(self):
        '''Ensure invalid option and args flagged'''
        myargs = ["-z", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

        myargs = ["badarg", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

        myargs = ["gobbledegook=nonsense", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

        myargs = ["-o", "badoption=value", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

        myargs = ["-o", "gob=ble=deg=ook", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-o", "servicename"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

    def test_parse_missing_svcname(self):
        '''Ensure missing service name is caught'''
        myargs = ["-o", "default-manifest=/tmp/dummy.xml"]
        self.assertRaises(SystemExit, set_service.parse_options, myargs)

    def test_parse_proper_processing(self):
        '''Test proper processing.'''
        myargs = ["-o", "default-manifest=/tmp/dummy.xml", "servicename"]
        options = set_service.parse_options(myargs)
        self.assertEqual(options.prop, "default-manifest")
        self.assertEqual(options.value, "/tmp/dummy.xml")
        self.assertEqual(options.svcname, "servicename")

        myargs = ["-o", "aliasof=myservice", "myalias"]
        options = set_service.parse_options(myargs)
        self.assertEqual(options.prop, "aliasof")
        self.assertEqual(options.value, "myservice")
        self.assertEqual(options.svcname, "myalias")

        myargs = ["-o", "imagepath=/newpath/images/mypath", "servicename"]
        options = set_service.parse_options(myargs)
        self.assertEqual(options.prop, "imagepath")
        self.assertEqual(options.value, "/newpath/images/mypath")
        self.assertEqual(options.svcname, "servicename")

    def test_parse_options_missing(self):
        '''Ensure options which are missing, are caught'''
        self.assertRaises(SystemExit, set_service.parse_options,
                          ["servicename"])


if __name__ == '__main__':
    unittest.main()

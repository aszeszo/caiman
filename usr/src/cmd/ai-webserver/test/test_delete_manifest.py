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

import gettext
import os
import tempfile
import unittest
import osol_install.auto_install.delete_manifest as delete_manifest

from nose.plugins.skip import SkipTest

gettext.install("ai-test")

class ParseOptions(unittest.TestCase):
    '''Tests for parse_options. Some tests correctly output usage msg'''

    def test_parse_no_options(self):
        '''Ensure no options caught'''
        self.assertRaises(SystemExit, delete_manifest.parse_options, []) 

    def test_parse_invalid_options(self):
        '''Ensure invalid option flagged'''
        myargs = ["-n", "mysvc", "-m", "manifest", "-u"] 
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs) 

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''

        myargs = ["-n", "-m", "manifest"]
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs)

        myargs = ["-n", "mysvc", "-m"]
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs)

    def test_parse_invalid_arg(self):
        '''Ensure unexpected arg caught '''
        myargs = ["-n", "mysvc", "-m", "manifest", "foobar"] 
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs) 

    def test_parse_missing_options(self):
        '''Ensure unexpected arg caught '''
        myargs = ["-n", "mysvc"] 
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs) 

        myargs = ["-m", "manifest"] 
        self.assertRaises(SystemExit, delete_manifest.parse_options, myargs) 


class DoDeleteManifest(unittest.TestCase):
    '''Tests for do_delete_manifest. '''

    def test_missing_service(self):
        '''catch bad AI service dir'''

        tempdirname = tempfile.NamedTemporaryFile(dir="/tmp").name

        args = [tempdirname]

        if os.geteuid() == 0:
            self.assertRaises(SystemExit, delete_manifest.do_delete_manifest, 
                              args) 
        else:
            raise SkipTest("Not root")


if __name__ == '__main__':
    unittest.main()

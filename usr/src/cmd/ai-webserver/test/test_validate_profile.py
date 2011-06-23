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
import tempfile
import unittest
import os
import lxml.etree
import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc
import osol_install.auto_install.data_files as df
import osol_install.auto_install.validate_profile as validate_profile


gettext.install("ai-test")

class MockDataBase(object):
    '''Class for mock database '''
    def __init__(self):
        self.queue  = MockQueue()

    def getQueue(self):
        return self.queue

class MockQueue(object):
    '''Class for mock database '''
    def __init__(self):
        self.criteria = None

    def put(self, query):
        return

class MockLog(object):
    '''Class for mock log '''
    def info(self, msg):
        return
    def debug(self, msg):
        return

class MockQuery(object):
    '''Class for mock query '''
    def __init__(self):
        self.query = None

    def __call__(self, query, commit=False):
        self.query = query
        return self

    def waitAns(self):
        return

    def getResponse(self):
        return [(1, 'myprofile', None, None,
            None, None, None, None,
            None, None, None,
            None, None, "testservice",
            None, 'myfile.xml')]

class ValidateProfile(unittest.TestCase):
    '''Tests for validate_profile'''

    def setUp(self):
        '''unit test set up

        '''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest

    def test_validate_file(self):
        prof = [
                '<?xml version="1.0"?>',
                '<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">',
                '<service_bundle type="profile" name="SUNWtime-slider">',
                '<service name="system/filesystem/zfs/auto-snapshot"',
                '	type="service"',
                '	version="0.2.96">',
                '        <property_group name="general" type="framework">',
                '            <propval name="action_authorization" type="astring"',
                '                value="solaris.smf.manage.zfs-auto-snapshot" />',
                '            <propval name="value_authorization" type="astring"',
                '                value="solaris.smf.manage.zfs-auto-snapshot" />',
                '        </property_group>',
                '</service>',
                '</service_bundle>']
        prof_str = ''
        for i in prof:
            prof_str += i + '\n'
        (tfp, fname) = tempfile.mkstemp()
        os.write(tfp, prof_str)
        os.close(tfp)
        #these tests should succeed for both string and file
        self.assertTrue(sc.validate_profile_string(prof_str))
        self.assertTrue(df.validate_file(fname, fname))
        os.unlink(fname)
        prof_str += 'should cause failure'
        (tfp, fname) = tempfile.mkstemp()
        os.write(tfp, prof_str)
        os.close(tfp)
        #these tests should fail for both string and file
        self.assertRaises(lxml.etree.XMLSyntaxError,
                          sc.validate_profile_string, prof_str)
        self.assertFalse(df.validate_file(fname, fname))
        os.unlink(fname)

class ParseOptions(unittest.TestCase):
    '''Tests for parse_options. Some tests correctly output usage msg'''

    def test_parse_no_options(self):
        '''Ensure no options caught'''
        self.assertRaises(SystemExit, validate_profile.parse_options, []) 
        myargs = ["mysvc"] 
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs) 

    def test_parse_invalid_options(self):
        '''Ensure invalid option flagged'''
        myargs = ["-n", "mysvc", "-p", "profile", "-u"] 
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs) 

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n", "-p", "profile"]
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs)
        myargs = ["-n", "mysvc", "-P"]
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs)
        myargs = ["-n", "mysvc", "-p"]
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs)

    def test_parse_mutex_options(self):
        '''Ensure no mutually exclusive options'''
        myargs = ["-n", "mysvc", "-P", "profile.xml", "-p", "profile"] 
        self.assertRaises(SystemExit, validate_profile.parse_options, myargs) 

    def test_parse_multi_options(self):
        '''Ensure multiple profiles processed'''
        myargs = ["-n", "mysvc", "-p", "profile", "-p", "profile2"] 
        options = validate_profile.parse_options(myargs)
        self.assertEquals(options.profile_name, ["profile", "profile2"])

if __name__ == '__main__':
    unittest.main()

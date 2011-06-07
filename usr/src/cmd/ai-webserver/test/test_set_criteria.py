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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import gettext
import tempfile
import unittest
import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.set_criteria as set_criteria


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
        return

class MockGetCriteria(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.crit_stripped = ["arch", "mem", "ipv4", "mac"]
        self.crit_unstripped = ["MINmem", "MINipv4", "MINmac",
                                "MAXmem", "MAXipv4", "MAXmac", "arch"]

    def __call__(self, queue, table=AIdb.MANIFESTS_TABLE, onlyUsed=False,
            strip=False):
        if strip:
            return self.crit_stripped
        else:
            return self.crit_unstripped

class MockisRangeCriteria(object):
    '''Class for mock isRangeCriteria '''
    def __init__(self):
        self.range = ["mem", "ipv4", "mac"]

    def __call__(self, queue, crit, table=AIdb.MANIFESTS_TABLE):
        if crit in self.range:
            return True
        return False

class MockgetManNames(object):
    '''Class for mock getManNames '''
    def __init__(self):
        self.man_names = ["fakeman"]

    def __call__(self, queue):
        return self.man_names

class MockDataFiles(object):
    '''Class for mock DataFiles'''
    def __init__(self):
        self.criteria = None
        self.database = MockDataBase()

class SetCriteria(unittest.TestCase):
    '''Tests for set_criteria'''

    def setUp(self):
        '''unit test set up

        '''
        self.aidb_DBrequest = AIdb.DBrequest
        self.aidb_isRangeCriteria = AIdb.isRangeCriteria
        self.aidb_getCriteria = AIdb.getCriteria
        self.mockquery = MockQuery()
        self.mockgetCriteria = MockGetCriteria()
        self.mockisRangeCriteria = MockisRangeCriteria()
        AIdb.DBrequest = self.mockquery
        AIdb.getCriteria = self.mockgetCriteria
        AIdb.isRangeCriteria = self.mockisRangeCriteria
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        AIdb.getCriteria = self.aidb_getCriteria
        AIdb.isRangeCriteria = self.aidb_isRangeCriteria

    def test_unbounded_min(self):
        '''Ensure set_criteria min query constructed properly '''
        criteria = {"arch": ["i86pc"], "mem": ["unbounded", 4096]}
        criteria.setdefault("ipv4")
        criteria.setdefault("mac")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  'manifests')
        expect_query = "UPDATE manifests SET arch='i86pc',MINmem=NULL," + \
                       "MAXmem='4096',MINipv4=NULL,MAXipv4=NULL,MINmac=NULL," +\
                       "MAXmac=NULL WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_unbounded_max(self):
        '''Ensure set_criteria max query constructed properly '''
        criteria = {"arch": ["i86pc"], "mem": [1024, "unbounded"]}
        criteria.setdefault("ipv4")
        criteria.setdefault("mac")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  'manifests')
        expect_query = "UPDATE manifests SET arch='i86pc',MINmem='1024'," + \
                       "MAXmem=NULL,MINipv4=NULL,MAXipv4=NULL,MINmac=NULL," + \
                       "MAXmac=NULL WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_range(self):
        '''Ensure set_criteria max query constructed properly '''
        criteria = {"arch": ["i86pc"], "ipv4": ["10.0.30.100", "10.0.50.400"]}
        criteria.setdefault("mac")
        criteria.setdefault("mem")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  'manifests')
        expect_query = "UPDATE manifests SET arch='i86pc',MINmem=NULL," + \
                       "MAXmem=NULL,MINipv4='10.0.30.100'," + \
                       "MAXipv4='10.0.50.400',MINmac=NULL,MAXmac=NULL " + \
                       "WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_append_unbounded_min(self):
        '''Ensure set_criteria append min query constructed properly '''
        criteria = {"arch": ["i86pc"], "mem": ["unbounded", 4096]}
        criteria.setdefault("ipv4")
        criteria.setdefault("mac")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  AIdb.PROFILES_TABLE, append=True)
        expect_query = "UPDATE " + AIdb.PROFILES_TABLE + " SET arch='i86pc',"\
                "MINmem=NULL,MAXmem='4096' WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_append_unbounded_max(self):
        '''Ensure set_criteria append max query constructed properly '''
        criteria = {"arch": ["i86pc"], "mem": [2048, "unbounded"]}
        criteria.setdefault("ipv4")
        criteria.setdefault("mac")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  'manifests', append=True)
        expect_query = "UPDATE manifests SET arch='i86pc',MINmem='2048'," \
                       "MAXmem=NULL WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_append_range(self):
        '''Ensure set_criteria append range query constructed properly '''
        criteria = {"arch": ["i86pc"], "ipv4": ["10.0.10.10", "10.0.10.300"]}
        criteria.setdefault("mem")
        criteria.setdefault("mac")
        set_criteria.set_criteria(criteria, "myxml", self.files.database,
                                  'manifests', append=True)
        expect_query = "UPDATE manifests SET arch='i86pc',MINipv4=" + \
                       "'10.0.10.10',MAXipv4='10.0.10.300' WHERE name='myxml'"
        self.assertEquals(expect_query, self.mockquery.query)

class CheckPublishedManifest(unittest.TestCase):
    '''Tests for check_published_manifest'''

    def setUp(self):
        '''unit test set up

        '''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery
        self.aidb_getManNames = AIdb.getManNames
        self.mockgetManNames = MockgetManNames()
        AIdb.getManNames = self.mockgetManNames
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        AIdb.getManNames = self.aidb_getManNames

    def test_no_such_name(self):
        '''Check no such manifest name caught '''
        self.assertFalse(set_criteria.check_published_manifest("/tmp",
                         self.files.database, "no_such_manifest"))

    def test_manifest_not_published(self):
        '''Check manifest not in published area caught'''
        self.assertFalse(set_criteria.check_published_manifest("/tmp",
                         self.files.database,
                         self.mockgetManNames.man_names[0])) 

class ParseOptions(unittest.TestCase):
    '''Tests for parse_options. Some tests correctly output usage msg'''

    def test_parse_no_options(self):
        '''Ensure no options caught'''
        self.assertRaises(SystemExit, set_criteria.parse_options, []) 
        myargs = ["mysvc"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 
        myargs = ["manifest"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 
        myargs = ["mysvc", "manifest"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 

    def test_parse_invalid_options(self):
        '''Ensure invalid option flagged'''
        myargs = ["-n", "mysvc", "-m", "manifest", "-u"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n", "mysvc", "-m", "manifest", "-c"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 
        myargs = ["-n", "mysvc", "-m", "manifest", "-C"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 
        myargs = ["-n", "mysvc", "-m", "manifest", "-a"] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 
        myargs = ["-n", "-m", "manifest"]
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs)
        myargs = ["-n", "mysvc", "-m"]
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs)
        myargs = ["-n", "mysvc", "-p"]
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs)

    def test_parse_mutually_exclusive(self):
        '''Ensure mutually exclusive options caught'''
        # Ensure -C and -a caught
        myargs = ["-n", "mysvc", "-m", "manifest", "-a", "arch=i86pc",
                  "-C", tempfile.mktemp()] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 

        # Ensure -C and -c caught
        myargs = ["-n", "mysvc", "-m", "manifest", "-c", "arch=i86pc", "-C",
                  tempfile.mktemp()] 
        self.assertRaises(SystemExit, set_criteria.parse_options, myargs) 

    def test_parse_valid_options(self):
        '''Ensure valid options parse successfully'''
        myargs = ["-n", "mysvc", "-m", "manifest", "-a", "arch=i86pc"]
        exp_options = {'criteria_a': ['arch=i86pc'], 'service_name': 'mysvc',
                       'manifest_name': 'manifest',
                       'criteria_file': None, 'criteria_c': []}
        options = set_criteria.parse_options(myargs)
        self.assertEquals(exp_options['criteria_a'], options.criteria_a) 
        self.assertEquals(exp_options['criteria_c'], options.criteria_c) 
        self.assertEquals(exp_options['service_name'], options.service_name)
        self.assertEquals(exp_options['manifest_name'], options.manifest_name) 
        self.assertEquals(exp_options['criteria_file'], options.criteria_file)

        myargs = ["-n", "mysvc", "-m", "manifest", "-c", "arch=i86pc"]
        exp_options = {'criteria_a': [],
                       'service_name': 'mysvc', 'manifest_name': 'manifest',
                       'criteria_file': None, 'criteria_c': ['arch=i86pc']}
        options = set_criteria.parse_options(myargs)
        self.assertEquals(exp_options['criteria_a'], options.criteria_a) 
        self.assertEquals(exp_options['criteria_c'], options.criteria_c) 
        self.assertEquals(exp_options['service_name'], options.service_name)
        self.assertEquals(exp_options['manifest_name'], options.manifest_name) 
        self.assertEquals(exp_options['criteria_file'], options.criteria_file)

        tempname = tempfile.mktemp()
        myargs = ["-n", "mysvc", "-m", "manifest", "-C", tempname]
        exp_options = {'criteria_a': [], 'service_name': 'mysvc',
                       'manifest_name': 'manifest', 'criteria_file': tempname,
                       'criteria_c': []}
        options = set_criteria.parse_options(myargs)
        self.assertEquals(exp_options['criteria_a'], options.criteria_a) 
        self.assertEquals(exp_options['criteria_c'], options.criteria_c) 
        self.assertEquals(exp_options['service_name'], options.service_name)
        self.assertEquals(exp_options['manifest_name'], options.manifest_name) 
        self.assertEquals(exp_options['criteria_file'], options.criteria_file)

if __name__ == '__main__':
    unittest.main()

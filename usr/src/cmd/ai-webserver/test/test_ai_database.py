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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import gettext
import unittest
import osol_install.auto_install.AI_database as AIdb

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

    def __call__(self, queue, onlyUsed=False, strip=False):
        if strip:
            return self.crit_stripped
        else:
            return self.crit_unstripped

class MockDataFiles(object):
    '''Class for mock DataFiles'''
    def __init__(self):
        self.criteria = None
        self.database = MockDataBase()

class getSpecificCriteria(unittest.TestCase):
    '''Tests for getSpecificCriteria'''

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest

    def test_arch_no_exclude(self):
        '''Verify arch query string with no exclude option'''
        criteria = "arch"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria)
        expect_query = "SELECT arch FROM manifests WHERE arch IS NOT NULL"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_arch_exclude(self):
        '''Verify arch query string with exclude option'''
        criteria = "arch"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria, excludeManifests=["suexml"])
        expect_query = "SELECT arch FROM manifests WHERE arch IS NOT NULL " + \
                       "AND name IS NOT 'suexml'"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_MINipv4(self):
        '''Verify single MIN query string '''
        criteria = "MINipv4"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria)
        expect_query = "SELECT MINipv4 FROM manifests WHERE MINipv4 IS " + \
                       "NOT NULL"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_MAXipv4(self):
        '''Verify single MAX query string '''
        criteria = "MAXipv4"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria)
        expect_query = "SELECT MAXipv4 FROM manifests WHERE MAXipv4 IS " + \
                       "NOT NULL"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_MIN_MAXmem(self):
        '''Verify mem range query string '''
        criteria = "MINmem"
        criteria2 = "MAXmem"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria, criteria2=criteria2)
        expect_query = "SELECT MINmem, MAXmem FROM manifests WHERE " + \
                       "(MINmem IS NOT NULL OR MAXmem IS NOT NULL)"
        self.assertEquals(expect_query, self.mockquery.query)

    def test_MIN_MAXmac(self):
        '''Verify mac range query string '''
        criteria = "MINmac"
        criteria2 = "MAXmac"
        queue = self.files.database.getQueue()
        AIdb.getSpecificCriteria(queue, criteria, criteria2=criteria2)
        expect_query = "SELECT HEX(MINmac), HEX(MAXmac) FROM manifests " + \
                       "WHERE (MINmac IS NOT NULL OR MAXmac IS NOT NULL)"
        self.assertEquals(expect_query, self.mockquery.query)


class isRangeCriteria(unittest.TestCase):
    '''Tests for isRangeCriteria'''

    def setUp(self):
        '''unit test set up'''
        self.aidb_getCriteria = AIdb.getCriteria
        self.mockgetCriteria = MockGetCriteria()
        AIdb.getCriteria = self.mockgetCriteria
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.getCriteria = self.aidb_getCriteria

    def test_arch_not_range(self):
        '''Verify arch returns false for range'''
        is_range_criteria = AIdb.isRangeCriteria(self.files.database, "arch")
        self.assertFalse(is_range_criteria)

    def test_ipv4_is_range(self):
        '''Verify ipv4 returns true for range'''
        is_range_criteria = AIdb.isRangeCriteria(self.files.database, "ipv4")
        self.assertTrue(is_range_criteria)

    def test_mac_is_range(self):
        '''Verify mac returns true for range'''
        is_range_criteria = AIdb.isRangeCriteria(self.files.database, "mac")
        self.assertTrue(is_range_criteria)

    def test_mem_is_range(self):
        '''Verify mem returns true for range'''
        is_range_criteria = AIdb.isRangeCriteria(self.files.database, "mem")
        self.assertTrue(is_range_criteria)

class formatValue(unittest.TestCase):
    '''Tests for formatValue'''
    
    def setUp(self):
        '''unit test set up'''
        self.ipv4     = '10000002015'
        self.mac      = '080027510CC7'
        self.network  = '172021239000'
        self.arch     = 'i86pc'
        self.platform = 'i386'
        self.cpu      = 'sun4u'
        self.mem      = '1024'

    def tearDown(self):
        '''unit test tear down'''
        self.ipv4     = None
        self.mac      = None
        self.network  = None
        self.arch     = None
        self.platform = None
        self.cpu      = None
        self.mem      = None

    def test_arch_formatValue(self):
        '''Ensure that ipv4 criteria is formatted appropriately'''
        fmt = AIdb.formatValue('MINipv4', self.ipv4)
        for octet in fmt.split('.'):
            self.assertEqual(octet, str(int(octet)))

    def test_mac_formatValue(self):
        '''Ensure that mac criteria is formatted appropriately'''
        fmt = AIdb.formatValue('MINmac', self.mac)
        for k, bits in enumerate(fmt.split(':')):
            self.assertEqual(bits, self.mac[k*2:(k*2)+2])

    def test_mem_formatValue(self):
        '''Ensure that memory criteria is formatted appropriately'''
        fmt = AIdb.formatValue('MINmem', self.mem)
        self.assertEqual(fmt.split(' ')[0], self.mem)
        self.assertEqual(fmt.split(' ')[1], 'MB')

    def test_other_formatValue(self):
        '''Ensure that formatValue does nothing with all other criteria'''
        fmt = AIdb.formatValue('network', self.network)
        self.assertEqual(fmt, self.network)
        fmt = AIdb.formatValue('arch', self.arch)
        self.assertEqual(fmt, self.arch)
        fmt = AIdb.formatValue('platform', self.platform)
        self.assertEqual(fmt, self.platform)
        fmt = AIdb.formatValue('cpu', self.cpu)
        self.assertEqual(fmt, self.cpu)


if __name__ == '__main__':
    unittest.main()

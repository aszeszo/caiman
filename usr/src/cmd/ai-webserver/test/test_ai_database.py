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
import os
import tempfile
import unittest

from sqlite3 import dbapi2 as sqlite3

import osol_install.auto_install.AI_database as AIdb

# Eventually bring names into convention.
# pylint: disable-msg=C0103

gettext.install("ai-test")


class MockDataBase(object):
    '''Class for mock database '''
    def __init__(self):
        self.queue = MockQueue()

    def getQueue(self):
        ''' Return request queue '''
        return self.queue


class MockQueue(object):
    '''Class for mock database '''

    def __init__(self):
        self.criteria = None

    # Disable unused-args message here as this is a dummy function.
    # Disable "method could be a function" errors as inappropriate here.
    # pylint: disable-msg=W0613,R0201
    def put(self, query):
        '''Dummy put method'''
        return


class MockQuery(object):
    '''Class for mock query '''
    def __init__(self):
        self.query = None

    # Disable "method could be a function" errors as inappropriate here.
    # Disable unused-args message here as this is a dummy function.
    # pylint: disable-msg=W0613, R0201
    def __call__(self, query, commit=False):
        self.query = query
        return self

    def waitAns(self):
        '''Dummy waitAns method'''
        return

    def getResponse(self):
        '''Dummy getResponse method'''
        return


class MockGetCriteria(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.crit_stripped = ["arch", "mem", "ipv4", "mac"]
        self.crit_unstripped = ["MINmem", "MINipv4", "MINmac",
                                "MAXmem", "MAXipv4", "MAXmac", "arch"]

    # Disable unused-args message here as this is a dummy function.
    # pylint: disable-msg=W0613
    def __call__(self, queue, table=AIdb.MANIFESTS_TABLE, onlyUsed=False,
                 strip=False):
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
        AIdb.getCriteria = MockGetCriteria()
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
        self.ipv4 = '10000002015'
        self.mac = '080027510CC7'
        self.network = '172021239000'
        self.arch = 'i86pc'
        self.platform = 'i386'
        self.cpu = 'sun4u'
        self.mem = '1024'

    def tearDown(self):
        '''unit test tear down'''
        self.ipv4 = None
        self.mac = None
        self.network = None
        self.arch = None
        self.platform = None
        self.cpu = None
        self.mem = None

    def test_arch_formatValue(self):
        '''Ensure that ipv4 criteria is formatted appropriately'''
        fmt = AIdb.formatValue('MINipv4', self.ipv4)
        for octet in fmt.split('.'):
            self.assertEqual(octet, str(int(octet)))

    def test_mac_formatValue(self):
        '''Ensure that mac criteria is formatted appropriately'''
        fmt = AIdb.formatValue('MINmac', self.mac)
        for k, bits in enumerate(fmt.split(':')):
            self.assertEqual(bits, self.mac[k * 2:(k * 2) + 2])

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


class build_query_str(unittest.TestCase):
    '''Tests for build_query_str'''

    def test_building_query_str(self):
        ''' test that we get reasonable query str '''
        cri_list = ['MINipv4', 'MAXipv4', 'arch', 'cpu', 'platform',
                  'MINmac', 'MAXmac', 'MINmem', 'MAXmem',
                  'MINnetwork', 'MAXnetwork']
        # Artificially small list to test filter functionality.
        all_cri_list = ['arch']
        my_crit_dict = {
                        'ipv4': '020025224125',
                        'arch': 'i86pc',
                        'platform': 'myplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeeff'
                       }
        query_str = AIdb.build_query_str(my_crit_dict, cri_list, all_cri_list)
        self.assertTrue(query_str.startswith("SELECT name"))
        self.assertTrue("FROM manifests WHERE " in query_str)
        self.assertTrue("MAXmem >= 2048 OR MAXmem IS NULL" in query_str)
        self.assertTrue("MINmem <= 2048 OR MINmem IS NULL" in query_str)
        self.assertTrue("MAXipv4 >= 020025224125" in query_str)
        self.assertTrue("MINipv4 <= 020025224125" in query_str)
        self.assertTrue("MAXnetwork >= 010000002000" in query_str)
        self.assertTrue("MINnetwork <= 010000002000" in query_str)
        self.assertTrue("HEX(MINmac) <= HEX(x'aabbccddeeff'" in query_str)
        self.assertTrue("HEX(MAXmac) >= HEX(x'aabbccddeeff'" in query_str)
        self.assertTrue("arch = LOWER('i86pc')" in query_str)
        self.assertTrue("platform = LOWER('myplatform')" in query_str)
        self.assertTrue("NOT ((arch IS NULL)" in query_str)
        self.assertFalse("(cpu IS NULL)" in query_str)
        self.assertTrue(query_str.endswith("LIMIT 1"))


class findManifest(unittest.TestCase):
    '''Tests for findManifest'''

    @classmethod
    def setUpClass(cls):
        '''unit test set up'''
        dbname = tempfile.NamedTemporaryFile(dir="/tmp", delete=False)
        cls.dbname = dbname.name
        cls.db = sqlite3.connect(dbname.name, isolation_level=None)

        # create db
        cls.db.execute("CREATE TABLE manifests("
                    "name TEXT, instance INTEGER, arch TEXT,"
                    "MINmac INTEGER, MAXmac INTEGER, MINipv4 INTEGER,"
                    "MAXipv4 INTEGER, cpu TEXT, platform TEXT, "
                    "MINnetwork INTEGER, MAXnetwork INTEGER,"
                    "MINmem INTEGER, MAXmem INTEGER)")

        #  add manifests to db
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('mac_ipv4_man',0,NULL,x'AABBCCDDEEFF',x'AABBCCDDEEFF',"
                   "020000000025,020000000025,NULL,NULL,NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('mac_min_unbound',0,NULL,x'AABBCCDDEEFF',x'AABBCCDDEEFF',"
                   "NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('ipv4_max_unbound',0,NULL,NULL,NULL,"
                   "020000000025,NULL,NULL,NULL,NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('platform_man',0,NULL,NULL,NULL,"
                   "NULL,NULL,NULL,'myplatform',NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('arch_man',0,'i86pc',NULL,NULL,"
                   "NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('cpu_man',0,NULL,NULL,NULL,"
                   "NULL,NULL,'i386',NULL,NULL,NULL,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('network_man',0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,"
                   "010000002000,010000002000,NULL,NULL)")
        cls.db.execute("INSERT INTO manifests VALUES"
                   "('mem_min_unbound',0,NULL,NULL,NULL,"
                   "NULL,NULL,NULL,NULL,NULL,NULL,NULL,2048)")
        cls.aidb = AIdb.DB(cls.dbname, commit=True)

    @classmethod
    def tearDownClass(cls):
        '''Class-level variable teardown'''
        cls.db.close()
        os.remove(cls.dbname)

    def test_unique_criteria_match(self):
        ''' test manifest match on mac and ipv4 value '''
        my_crit_dict = {
                        'ipv4': '020000000025',
                        'arch': 'i86pc',
                        'platform': 'myplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeeff'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "mac_ipv4_man")

    def test_mac_match(self):
        ''' test manifest match on mac '''
        my_crit_dict = {
                        'ipv4': '022000000225',
                        'arch': 'i86pc',
                        'platform': 'myplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeeff'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "mac_min_unbound")

    def test_ipv4_match(self):
        ''' test manifest match on ipv4 '''
        my_crit_dict = {
                        'ipv4': '020000000025',
                        'arch': 'i86pc',
                        'platform': 'myplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "ipv4_max_unbound")

    def test_platform_match(self):
        ''' test manifest match on platform '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'i86pc',
                        'platform': 'myplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "platform_man")

    def test_arch_match(self):
        ''' test manifest match on arch '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'i86pc',
                        'platform': 'otherplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "arch_man")

    def test_cpu_match(self):
        ''' test manifest match on cpu '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'sparc',
                        'platform': 'otherplatform',
                        'cpu': 'i386',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "cpu_man")

    def test_network_match(self):
        ''' test manifest match on network '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'sparc',
                        'platform': 'otherplatform',
                        'cpu': 'sun4v',
                        'network': '010000002000',
                        'mem': '2048',
                        'mac': 'aabbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "network_man")

    def test_mem_match(self):
        ''' test manifest match on mem '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'sparc',
                        'platform': 'otherplatform',
                        'cpu': 'sun4v',
                        'network': '010000002100',
                        'mem': '2048',
                        'mac': 'bbbbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEqual(manifest, "mem_min_unbound")

    def test_manifest_nomatch(self):
        ''' test that findManifest returns 0 for no matching manifest '''
        my_crit_dict = {
                        'ipv4': '010000000225',
                        'arch': 'sparc',
                        'platform': 'otherplatform',
                        'cpu': 'sun4v',
                        'network': '010000002100',
                        'mem': '3000',
                        'mac': 'bbbbccddeef0'
                       }
        manifest = AIdb.findManifest(my_crit_dict, self.aidb)
        self.assertEquals(manifest, 0)


if __name__ == '__main__':
    unittest.main()

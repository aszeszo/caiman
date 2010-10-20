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

#
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
'''Tests for DOC utility functionality'''

import unittest

from solaris_install.data_object.cache import DataObjectCache
from simple_data_object import SimpleDataObject


class  TestDataObjectCacheUtility(unittest.TestCase):
    '''Tests for DOC utility functionality'''

    def setUp(self):
        '''Create small set of objects and references to them'''
        self.doc = DataObjectCache()
        self.persistent_child_1 = SimpleDataObject("persistent_child_1")
        self.persistent_child_2 = SimpleDataObject("persistent_child_2")
        self.persistent_child_3 = SimpleDataObject("persistent_child_3")
        self.doc.persistent.insert_children([self.persistent_child_1,
            self.persistent_child_2, self.persistent_child_3])

        self.volatile_child_1 = SimpleDataObject("volatile_child_1")
        self.volatile_child_2 = SimpleDataObject("volatile_child_2")
        self.volatile_child_3 = SimpleDataObject("volatile_child_3")
        self.doc.volatile.insert_children([self.volatile_child_1,
            self.volatile_child_2, self.volatile_child_3])

    def tearDown(self):
        '''Clean up contents of DOC and reference'''
        self.doc.clear()
        self.doc = None

        self.persistent_child_1 = None
        self.persistent_child_2 = None
        self.persistent_child_3 = None

        self.volatile_child_1 = None
        self.volatile_child_2 = None
        self.volatile_child_3 = None


    def test_data_object_cache_utility_clear(self):
        '''Validate the doc.clear() clears children of sub-trees only'''
        self.assertTrue(self.doc.has_children,
            "DataObjectCache should always have children\n%s" %\
            (str(self.doc)))
        self.assertTrue(self.doc.persistent.has_children,
            "Persistent sub-tree should have children\n%s" %\
            (str(self.doc)))
        self.assertTrue(self.doc.volatile.has_children,
            "Volatile sub-tree should have children\n%s" %\
            (str(self.doc)))

        self.doc.clear()

        self.assertFalse(self.doc.persistent.has_children,
            "Persistent sub-tree should have no children:\n%s" %\
            (str(self.doc)))
        self.assertFalse(self.doc.volatile.has_children,
            "Volatile sub-tree should have no children\n%s" %\
            (str(self.doc)))
        self.assertTrue(self.doc.has_children,
            "DataObjectCache should always have children\n%s" %\
            (str(self.doc)))

    def test_data_object_cache_utility_is_empty(self):
        '''Validate that doc.is_empty property is valid'''
        self.assertFalse(self.doc.is_empty,
            "DOC doesn't contain children, when it should: \n%s" %
            (str(self.doc)))
        self.doc.clear()
        self.assertTrue(self.doc.is_empty,
            "DOC contains children when it should be empty: \n%s" %
            (str(self.doc)))

if __name__ == '__main__':
    unittest.main()

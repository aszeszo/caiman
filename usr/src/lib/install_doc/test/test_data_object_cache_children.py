#!/usr/bin/python
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
'''Tests to validata the DOC children operate as expected'''

import unittest

from solaris_install.data_object.cache import \
    DataObjectCache
from simple_data_object import SimpleDataObject


class  TestDataObjectCacheChildren(unittest.TestCase):
    '''Tests to validata the DOC children operate as expected'''

    def setUp(self):
        '''Create a reference to a DOC'''
        self.doc = DataObjectCache()

    def tearDown(self):
        '''Cleanup reference to DOC and it's children'''
        self.doc.clear()
        self.doc = None

    def test_data_object_cache_children_exist(self):
        '''Validate that the DOC children always exist'''
        persistent = self.doc.get_children(name="persistent")
        volatile = self.doc.get_children(name="volatile")

        self.assertTrue(len(persistent) > 0 and persistent[0] != None)
        self.assertTrue(len(volatile) > 0 and volatile[0] != None)

        self.assertEqual(persistent[0], self.doc.persistent)
        self.assertEqual(volatile[0], self.doc.volatile)

    def test_data_object_cache_children_insertion(self):
        '''Validate that DOC doesn't allow insertion of direct children'''
        simple = SimpleDataObject("Test Child")
        try:
            self.doc.insert_children(simple)
            self.fail("Managed to insert child when expected exception")
        except AttributeError:
            pass

    def test_data_object_cache_children_deletion_directly(self):
        '''Validate the DOC children cannot be deleted by reference'''
        try:
            self.doc.delete_children(self.doc.persistent)
            self.fail("Managed to delete 'persistent' when expected exception")
        except AttributeError:
            pass

        try:
            self.doc.delete_children(self.doc.volatile)
            self.fail("Managed to delete 'volatile' when expected exception")
        except AttributeError:
            pass

    def test_data_object_cache_children_deletion_all(self):
        '''Validate the DOC children cannot be deleted by delete all.'''
        try:
            self.doc.delete_children()
            self.fail("Managed to delete children when expected exception")
        except AttributeError:
            pass

    def test_data_object_cache_children_delete(self):
        '''Validate DOC and children cannot be deleted by delete() method'''
        try:
            self.doc.delete()
            self.fail("Managed to delete self when expected exception")
        except AttributeError:
            pass

        # Ensure that delete() call doesn't delete persistent and volatile.
        self.doc.persistent.delete()
        self.assertNotEqual(self.doc.persistent, None)

        self.doc.volatile.delete()
        self.assertNotEqual(self.doc.volatile, None)

if __name__ == '__main__':
    unittest.main()

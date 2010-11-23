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
'''Tests to validate DOC snapshots support'''

import unittest
from StringIO import StringIO
from tempfile import mkdtemp, mktemp
from os import unlink, rmdir, stat, path

from solaris_install.data_object.cache import DataObjectCache
from simple_data_object import SimpleDataObject, \
    SimpleDataObject2, SimpleDataObject3, SimpleDataObject4


class TestDataObjectCacheSnapshots(unittest.TestCase):
    '''Tests to validate DOC snapshots support'''

    def setUp(self):
        '''Set up correct environment for tests.

        Creates reference to a temp dir and file and StringIO buffer.

        Creates a tree of elements in the DOC to validate before/after.
        '''

        # Create temporary work directory
        self.temp_dir = mkdtemp(prefix="doc_test-")
        self.temp_file = mktemp(prefix="snapshot-", dir=self.temp_dir)

        # Create StringIO memory buffer for I/O test
        self.buffer = StringIO()

        # Create a tree that looks like:
        #  DOC
        #    volatile
        #      volatile_root
        #    persistent
        #      persistent_root
        #        child_1
        #            child_1_1
        #            child_1_2
        #        child_2
        #            child_2_1
        #                child_2_1_1
        #                    child_2_1_1_1
        #                    child_2_1_1_2
        #        child_3
        #            child_3_1
        #                child_3_1_2
        #                child_3_1_2
        #                child_3_1_2_same_name
        #        child_4
        #        child_5
        #            child_5_1
        #            child_5_2
        #                child_5_2_1
        #                child_5_2_2
        #                child_5_2_3
        #                    child_5_2_3_1
        #                    child_5_2_3_2
        #                    child_5_2_3_3
        #                    child_5_2_3_3_same_name
        #        child_5_same_name

        # Create DOC node
        self.doc = DataObjectCache()

        # Create some persistent content
        self.persistent_root = SimpleDataObject("persistent_root")
        # Add some children, used by most tests.
        self.child_1 = SimpleDataObject2("child_1")
        self.child_2 = SimpleDataObject("child_2")
        self.child_3 = SimpleDataObject("child_3")
        self.child_4 = SimpleDataObject2("child_4")
        self.child_5 = SimpleDataObject3("child_5")
        self.child_5_same_name = SimpleDataObject("child_5")

        self.do_list = list()
        self.do_list.append(self.child_1)
        self.do_list.append(self.child_2)
        self.do_list.append(self.child_3)
        self.do_list.append(self.child_4)
        self.do_list.append(self.child_5)
        self.do_list.append(self.child_5_same_name)

        self.persistent_root.insert_children(self.do_list)

        self.doc.persistent.insert_children(self.persistent_root)

        # Now let's add the children of children, etc. for use by
        # get_descendants() tests.
        # child_1 children
        self.child_1_1 = SimpleDataObject("child_1_1")
        self.child_1_2 = SimpleDataObject("child_1_2")
        self.child_1.insert_children([self.child_1_1, self.child_1_2])

        # child_2 tree
        self.child_2_1 = SimpleDataObject2("child_2_1")
        self.child_2.insert_children(self.child_2_1)
        self.child_2_1_1 = SimpleDataObject2("child_2_1_1")
        self.child_2_1.insert_children(self.child_2_1_1)
        self.child_2_1_1_1 = SimpleDataObject2("child_2_1_1_1")
        self.child_2_1_1_2 = SimpleDataObject2("child_2_1_1_2")
        self.child_2_1_1.insert_children(
            [self.child_2_1_1_1, self.child_2_1_1_2])

        # child_3 tree
        self.child_3_1 = SimpleDataObject("child_3_1")
        self.child_3.insert_children(self.child_3_1)
        self.child_3_1_1 = SimpleDataObject("child_3_1_1")
        self.child_3_1_2 = SimpleDataObject("child_3_1_2")
        self.child_3_1_2_same_name = SimpleDataObject("child_3_1_2")
        self.child_3_1.insert_children([self.child_3_1_1, self.child_3_1_2,
        self.child_3_1_2_same_name])

        # child_5 tree
        self.child_5_1 = SimpleDataObject("child_5_1")
        self.child_5_2 = SimpleDataObject("child_5_2")
        self.child_5.insert_children([self.child_5_1, self.child_5_2])
        self.child_5_2_1 = SimpleDataObject("child_5_2_1")
        self.child_5_2_2 = SimpleDataObject("child_5_2_2")
        self.child_5_2_3 = SimpleDataObject4("child_5_2_3")
        self.child_5_2.insert_children(
            [self.child_5_2_1, self.child_5_2_2, self.child_5_2_3])

        self.child_5_2_3_1 = SimpleDataObject("child_5_2_3_1")
        self.child_5_2_3_2 = SimpleDataObject("child_5_2_3_2")
        self.child_5_2_3_3 = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3_3_same_name = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3.insert_children(
            [self.child_5_2_3_1, self.child_5_2_3_2,
        self.child_5_2_3_3, self.child_5_2_3_3_same_name])

        # Create some volatile content, not much, just enough to test that it's
        # not overwritten on loading of snapshot.
        self.volatile_root = SimpleDataObject2("volatile_root")
        self.doc.volatile.insert_children(self.volatile_root)

    def tearDown(self):
        '''Cleanup test environment and references.'''
        # Remove temp dir, may not always be there.
        if path.exists(self.temp_file):
            unlink(self.temp_file)

        if path.exists(self.temp_dir):
            rmdir(self.temp_dir)

        # Remove buffer
        self.buffer.close()  # Free's memory
        self.buffer = None

        # Unset variables.
        self.doc.clear()
        self.doc = None
        self.volatile_root = None
        self.persistent_root = None
        self.child_1 = None
        self.child_2 = None
        self.child_3 = None
        self.child_4 = None
        self.child_5 = None
        self.child_5_same_name = None
        self.do_list = None

        self.child_1_1 = None
        self.child_1_2 = None

        self.child_2_1 = None
        self.child_2_1_1 = None
        self.child_2_1_1_1 = None
        self.child_2_1_1_2 = None

        self.child_3_1 = None
        self.child_3_1_1 = None
        self.child_3_1_2 = None
        self.child_3_1_2_same_name = None

        self.child_5_1 = None
        self.child_5_2 = None
        self.child_5_2_1 = None
        self.child_5_2_2 = None
        self.child_5_2_3 = None

        self.child_5_2_3_1 = None
        self.child_5_2_3_2 = None
        self.child_5_2_3_3 = None
        self.child_5_2_3_3_same_name = None

    def test_data_object_cache_snapshots_write_file_string(self):
        '''Validate writing of a snapshot to a file'''
        try:
            self.doc.take_snapshot(self.temp_file)
        except Exception, e:
            self.fail("Got unexpected error writing snapshot: " + str(e))

        try:
            stat_info = stat(self.temp_file)
            self.assertFalse(stat_info.st_size < 2048,
                "Snapshot file size is too small: %d" % (stat_info.st_size))
        except Exception, e:
            self.fail("Got unexpected error stat-ing snapshot file: " + str(e))

    def test_data_object_cache_snapshots_write_file_object(self):
        '''Validate writing of a snapshot to a file-like object'''
        try:
            self.doc.take_snapshot(self.buffer)
        except Exception, e:
            self.fail("Got unexpected error writing snapshot: " + str(e))

        try:
            self.assertFalse(self.buffer.len < 2048,
                "Snapshot buffer size is too small: %d" % (self.buffer.len))
        except Exception, e:
            self.fail("Got unexpected error stat-ing snapshot file: " + str(e))

    def test_data_object_cache_snapshots_write_file_invalid_path(self):
        '''Validate failure to invalid path'''
        self.assertRaises(IOError, self.doc.take_snapshot,
            self.temp_dir + "/tmpnon-existant_dir/file")

    def test_data_object_cache_snapshots_write_file_null_object(self):
        '''Validate failure if passed None'''
        self.assertRaises(ValueError, self.doc.take_snapshot, None)

    def test_data_object_cache_snapshots_read_file_string(self):
        '''Validate snapshotted and restored data are the same'''
        before_snap = str(self.doc.persistent)
        try:
            self.doc.take_snapshot(self.temp_file)
        except Exception, e:
            self.fail("Got unexpected error writing snapshot: " + str(e))

        # Remove some persistent children to be sure it's empty so won't
        # compare unless load of snapshot works correctly
        for child in self.doc.persistent.children:
            for child_child in child.children:
                child_child.delete_children()

        after_delete = str(self.doc.persistent)

        self.assertNotEquals(before_snap, after_delete,
            "Before and After delete strings are same:\
            \nBEFORE\n%s\n\nAFTER:\n%s\n" % (before_snap, after_delete))

        try:
            self.doc.load_from_snapshot(self.temp_file)
        except Exception, e:
            self.fail("Got unexpected error reading snapshot: " + str(e))

        after_snap = str(self.doc.persistent)

        self.assertEquals(before_snap, after_snap,
            "Before and After strings differ:\nBEFORE\n%s\n\nAFTER:\n%s\n" %
            (before_snap, after_snap))

    def test_data_object_cache_snapshots_read_file_object(self):
        '''Validate snapshot and restore work after modifications in memory'''
        before_snap = str(self.doc.persistent)

        try:
            self.doc.take_snapshot(self.buffer)
            # Rewind to start so that read will be in right place.
            self.buffer.seek(0)
        except Exception, e:
            self.fail("Got unexpected error writing snapshot: " + str(e))

        self.assertTrue(self.buffer.len > 2048,
            "Buffer size is wrong: %d" % (self.buffer.len))

        # Remove some persistent children to be sure it's empty so won't
        # compare unless load of snapshot works correctly
        for child in self.doc.persistent.children:
            for child_child in child.children:
                child_child.delete_children()

        after_delete = str(self.doc.persistent)

        self.assertNotEquals(before_snap, after_delete,
            "Before and After delete strings are same:\
            \nBEFORE\n%s\n\nAFTER:\n%s\n" % (before_snap, after_delete))

        try:
            self.doc.load_from_snapshot(self.buffer)
        except Exception, e:
            self.fail("Got unexpected error reading snapshot: " + str(e))

        after_snap = str(self.doc.persistent)

        self.assertEquals(before_snap, after_snap,
            "Before and After strings differ:\nBEFORE\n%s\n\nAFTER:\n%s\n" %
            (before_snap, after_snap))

    def test_data_object_cache_snapshots_read_file_invalid_path(self):
        '''Validate failure if non-existant file path passed'''
        self.assertRaises(IOError, self.doc.load_from_snapshot,
            self.temp_dir + "/tmpnon-existant_dir/file")

    def test_data_object_cache_snapshots_read_file_null_object(self):
        '''Validate failure if None valud passed to load_from_snapshot()'''
        self.assertRaises(ValueError, self.doc.load_from_snapshot, None)

    def test_data_object_cache_snapshots_ensure_volatile_skipped(self):
        '''Validate that 'volatile' doesn't change on restore'''
        try:
            self.doc.take_snapshot(self.buffer)
            # Rewind to start so that read will be in right place.
            self.buffer.seek(0)
        except Exception, e:
            self.fail("Got unexpected error writing snapshot: " + str(e))

        # Add a child to the volatile tree
        new_child = SimpleDataObject3("new_volatile_child")
        self.doc.volatile.insert_children(new_child)
        before_restore = str(self.doc.volatile)

        try:
            self.doc.load_from_snapshot(self.buffer)
        except Exception, e:
            self.fail("Got unexpected error reading snapshot: " + str(e))

        after_restore = str(self.doc.volatile)

        self.assertEquals(before_restore, after_restore,
            "Before and After strings differ:\nBEFORE\n%s\n\nAFTER:\n%s\n" %
            (before_restore, after_restore))

        self.assertEquals(self.doc.volatile.get_children(name=new_child.name),
            [new_child], "Failed to locate 'new_child' in DOC!")

if __name__ == '__main__':
    unittest.main()

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
'''Test for DataObject utility methods'''

import unittest
import copy

from simple_data_object import SimpleDataObject, \
    SimpleDataObject2, SimpleDataObject3, SimpleDataObject4, \
    create_simple_data_obj_tree


class  TestDataObjectUtility(unittest.TestCase):
    '''Test for DataObject utility methods'''

    def setUp(self):
        '''Create tree structure and local reference'''
        self.data_obj = create_simple_data_obj_tree()

    def tearDown(self):
        '''Clean up refrences'''
        self.data_obj = None

    def test_data_object_utility_get_name(self):
        '''Validate name property is read-only and returns correct info'''
        self.assertEqual(self.data_obj["child_1_2"]._name,
            self.data_obj["child_1_2"].name)

        try:
            self.data_obj["child_1"].name = "NewName"
            self.fail("Succeeded in setting name, when expected failure.")
        except AttributeError:
            pass

    def test_data_object_utility_get_parent(self):
        '''Validate parent property is read-only and returns correct info'''
        self.assertEqual(self.data_obj["child_1_2"]._parent,
            self.data_obj["child_1_2"].parent)

        try:
            self.data_obj["child_1_1"].parent = self.data_obj["child_2"]
            self.fail("Succeeded in setting parent, when expected failure.")
        except AttributeError:
            pass

    def test_data_object_utility_get_xml_str(self):
        '''Validate get_xml_str() method'''
        s = self.data_obj["data_obj"].get_xml_tree_str()
        # Ensure not None
        self.assertTrue(s != None, "get_xml_str() returned None!")
        # Ensure it contains a string we expect
        self.assertTrue(s.find(self.data_obj["child_5_2_3_3"].name) != -1)
        # Ensure it's the length we expect - could fail easily, may
        # need re-baseline?
        self.assertTrue(len(s) == 1262,
            "get_xml_str() returned invalid string len: len = %d\n%s" %
            (len(s), s))

    def test_data_object_utility_has_children(self):
        '''Validate has_children property'''
        # Test multiple children
        self.assertTrue(self.data_obj["data_obj"].has_children,
            "'%s' should have children\n%s" %\
            (self.data_obj["data_obj"].name, str(self.data_obj)))
        # Test no children
        self.assertFalse(self.data_obj["child_4"].has_children,
            "'%s' should not have children\n%s" %\
            (self.data_obj["child_4"].name, str(self.data_obj["child_4"])))
        # Test one child.
        self.assertTrue(self.data_obj["child_2_1"].has_children,
            "'%s' should have children\n%s" %\
            (self.data_obj["child_2_1"].name, str(self.data_obj["child_2_1"])))

    def test_data_object_utility_copy(self):
        '''Validate copy mechanism'''
        orig_name = self.data_obj["child_5_2"].name
        orig_parent = self.data_obj["child_5_2"].parent
        orig_children = self.data_obj["child_5_2"].children

        my_copy = copy.copy(self.data_obj["child_5_2"])

        # Ensure original is unchanged.
        self.assertEqual(self.data_obj["child_5_2"].name, orig_name)
        self.assertEqual(self.data_obj["child_5_2"].parent, orig_parent)
        self.assertEqual(self.data_obj["child_5_2"].children, orig_children)

        # Ensure that copy has expected differences.
        self.assertNotEqual(my_copy, self.data_obj["child_5_2"])

        self.assertEqual(my_copy.name, self.data_obj["child_5_2"].name)

        self.assertTrue(my_copy.parent == None,
            "Copy shouldn't have a parent")

        self.assertFalse(my_copy.has_children,
            "Copy shouldn't have any children")

        self.assertNotEqual(my_copy.children,
            self.data_obj["child_5_2"].children)

    def test_data_object_utility_deepcopy(self):
        '''Validate deepcopy mechanism'''
        orig_name = self.data_obj["child_5_2"].name
        orig_parent = self.data_obj["child_5_2"].parent
        orig_children = self.data_obj["child_5_2"].children

        my_copy = copy.deepcopy(self.data_obj["child_5_2"])

        # Ensure original is unchanged.
        self.assertEqual(self.data_obj["child_5_2"].name, orig_name)
        self.assertEqual(self.data_obj["child_5_2"].parent, orig_parent)
        self.assertEqual(self.data_obj["child_5_2"].children, orig_children)

        # Ensure that copy has expected differences
        self.assertNotEqual(my_copy, self.data_obj["child_5_2"])

        self.assertEqual(my_copy.name, self.data_obj["child_5_2"].name)

        self.assertTrue(my_copy.parent == None,
            "Copy shouldn't have a parent")

        self.assertTrue(my_copy.has_children,
            "Copy should have children")

        # Children aren't exactly same objects.
        self.assertNotEqual(my_copy.children,
            self.data_obj["child_5_2"].children)

        # Children should be same contents though...
        orig_children = self.data_obj["child_5_2"].children
        copy_children = my_copy.children

        self.assertEqual(len(orig_children), len(copy_children),
            "Copy should have the same number of children! %d != %d" %\
            (len(orig_children), len(copy_children)))

        for i in range(len(orig_children)):
            # Check that original child has correct parent
            self.assertEqual(orig_children[i].parent,
                self.data_obj["child_5_2"])
            # Check that new copy has the correct parent
            self.assertEqual(copy_children[i].parent, my_copy)
            # Check that the names are still the same
            self.assertEqual(orig_children[i].name, copy_children[i].name)

if __name__ == '__main__':
    unittest.main()

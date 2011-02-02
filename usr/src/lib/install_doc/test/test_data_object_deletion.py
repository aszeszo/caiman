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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
'''Tests for various DataObject deletion methods'''

import unittest

from solaris_install.data_object import ObjectNotFoundError
from simple_data_object import SimpleDataObject, \
    SimpleDataObject2, SimpleDataObject3


class TestDataObjectDeletion(unittest.TestCase):
    '''Tests for various DataObject deletion methods'''

    def setUp(self):
        '''Create simple tree and references to children'''
        # Create root node
        self.data_obj = SimpleDataObject("root")
        # Add some children
        self.child_1 = SimpleDataObject2("child_1")
        self.child_2 = SimpleDataObject("child_2")
        self.child_3 = SimpleDataObject("child_3")
        self.child_4 = SimpleDataObject2("child_4")
        self.child_5 = SimpleDataObject("child_5")

        # Add a child to child_2
        self.child_2_1 = SimpleDataObject("child_2_1")
        self.child_2.insert_children(self.child_2_1)

        self.do_list = list()
        self.do_list.append(self.child_1)
        self.do_list.append(self.child_2)
        self.do_list.append(self.child_3)
        self.do_list.append(self.child_4)
        self.do_list.append(self.child_5)

        self.data_obj.insert_children(self.do_list)

    def tearDown(self):
        '''Clean up stored references'''
        self.data_obj = None
        self.child_1 = None
        self.child_2 = None
        self.child_3 = None
        self.child_4 = None
        self.child_5 = None

        self.child_2_1 = None

        self.do_list = None

    def test_data_object_delete_self(self):
        '''Validate that self.delete() deletes self from parent'''

        obj = self.data_obj.get_children(self.child_4.name)

        self.assertEqual(obj, [self.child_4],
            "Failed to locate child_4 as child of data_obj.")

        self.child_4.delete()  # Delete self from parent.

        self.assertRaises(ObjectNotFoundError, self.data_obj.get_children,
            self.child_4.name, not_found_is_err=True)

    def test_data_object_delete_self_and_children(self):
        '''Validate self.delete() deletes self plus children'''

        obj = self.data_obj.get_children(self.child_2.name)

        self.assertEqual(obj, [self.child_2],
            "Failed to locate child_2 as child of data_obj.")

        self.child_2.delete()  # Delete self from parent.

        self.assertRaises(ObjectNotFoundError, self.data_obj.get_children,
            self.child_2.name, not_found_is_err=True)

        # Ensure that child_2 now has no children
        self.assertFalse(self.child_2.has_children,
            "child_2 shouldn't have children anymore.")

        # Ensure that child_2 now has no children
        self.assertFalse(self.child_2.has_children,
            "child_2 shouldn't have children anymore.")

    def test_data_object_delete_all(self):
        '''Validate delete_children() deletes all children nodes'''

        self.data_obj.delete_children()

        self.assertFalse(self.data_obj.has_children, str(self.data_obj))

    def test_data_object_delete_specific_single(self):
        '''Validate deletion of a specific child by reference'''

        self.data_obj.delete_children(self.child_3)

        for child in self.data_obj.children:
            self.assertNotEqual(child.name, self.child_3.name,
                "Found deleted object 'child_3': %s" + str(self.data_obj))

    def test_data_object_delete_specific_list(self):
        '''Validate deletion of a list of references to specific children'''

        self.data_obj.delete_children([self.child_3, self.child_5])

        for child in self.data_obj.children:
            self.assertNotEqual(child, self.child_3,
                "Found deleted object 'child_3': %s" + str(self.data_obj))
            self.assertNotEqual(child, self.child_5,
                "Found deleted object 'child_5': %s" + str(self.data_obj))

    def test_data_object_delete_by_name_no_children(self):
        '''Validate failure if asked to delete children if there are none'''
        self.assertRaises(ObjectNotFoundError, self.child_2_1.delete_children,
            name="ignored", not_found_is_err=True)

    def test_data_object_delete_by_class_type_no_children(self):
        '''Validate failure if asked to delete non-existant class type'''
        self.assertRaises(ObjectNotFoundError, self.child_2_1.delete_children,
            class_type=SimpleDataObject, not_found_is_err=True)

    def test_data_object_delete_by_name(self):
        '''Validate failure if asked to delete non-exitant child by name'''
        self.data_obj.delete_children(name=self.child_4.name)

        for child in self.data_obj.children:
            self.assertNotEqual(child, self.child_4,
                "Found deleted object 'child_4': %s" + str(self.data_obj))

    def test_data_object_delete_by_type(self):
        '''Validate correct deletion of specific class types'''
        # Should remove child_1 and child_4 which are of type SimpleDataObject2
        self.data_obj.delete_children(class_type=SimpleDataObject2)

        for child in self.data_obj.children:
            self.assertNotEqual(child, self.child_1,
                "Found deleted object 'child_1': %s" + str(self.data_obj))
            self.assertNotEqual(child, self.child_4,
                "Found deleted object 'child_4': %s" + str(self.data_obj))

    def test_data_object_delete_by_name_and_type(self):
        '''Validate correct deletion of an obj by name and type'''
        # Should remove child_4 which has name and type SimpleDataObject2
        self.data_obj.delete_children(name=self.child_4.name,
                                      class_type=SimpleDataObject2)

        found_child_1 = False
        for child in self.data_obj.children:
            if child == self.child_1:
                found_child_1 = True
            self.assertNotEqual(child, self.child_4,
                "Found deleted object 'child_4': %s" + str(self.data_obj))

        self.assertTrue(found_child_1,
            "child_1 should still be present: %s" % (str(self.data_obj)))

    def test_data_object_delete_by_children_not_exist_single(self):
        '''Validate failure if asked to delete non-existant child reference'''
        not_a_child = SimpleDataObject("Not A Child 1")

        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            not_a_child, not_found_is_err=True)

    def test_data_object_delete_by_children_not_exist_list(self):
        '''Validate failure when deleting a list of non-existant children'''
        not_a_child_list = [self.child_5, SimpleDataObject("Not A Child 1")]

        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            not_a_child_list, not_found_is_err=True)

    def test_data_object_delete_by_children_not_exist_tuple(self):
        '''Validate deletion of a tuple containing non-existant ref'''
        not_a_child_list = (self.child_5, SimpleDataObject("Not A Child 1"))

        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            not_a_child_list, not_found_is_err=True)

    def test_data_object_delete_by_name_not_exist(self):
        '''Validate failure when deleting non-existant child by name'''
        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            name="non_existant_name", not_found_is_err=True)

    def test_data_object_delete_by_type_not_exist(self):
        '''Validate failure when deleting non-existant child by type'''
        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            class_type=SimpleDataObject3, not_found_is_err=True)

    def test_data_object_delete_by_name_exist_and_type_not_exist(self):
        '''Validate failure when deleting child name and non-existant type'''
        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            name=self.child_4.name, class_type=SimpleDataObject3,
            not_found_is_err=True)

    def test_data_object_delete_by_name_exist_and_type_not_exist_not_err(self):
        '''Validate no err when deleting child name and non-existant type'''
        self.data_obj.delete_children(name=self.child_4.name,
            class_type=SimpleDataObject3, not_found_is_err=False)

    def test_data_object_delete_by_name_not_exist_and_type_exist(self):
        '''Validate failure when deleting child non-existant name and type'''
        self.assertRaises(ObjectNotFoundError, self.data_obj.delete_children,
            name="non existant name", class_type=SimpleDataObject2,
            not_found_is_err=True)

    def test_data_object_delete_by_name_not_exist_and_type_exist_not_err(self):
        '''Validate not err when deleting child non-existant name and type'''
        self.data_obj.delete_children(name="non existant name",
            class_type=SimpleDataObject2, not_found_is_err=False)

    def test_data_object_delete_by_object_with_name_and_type_ignored(self):
        '''Validate name and type ignored if specific child ref provided'''
        # Should remove child_3 only, and ignore name and type
        self.data_obj.delete_children(children=self.child_3,
                                      name=self.child_4.name,
                                      class_type=SimpleDataObject2)

        found_child_1 = False
        found_child_2 = False
        found_child_4 = False
        found_child_5 = False
        for child in self.data_obj.children:
            if child == self.child_1:
                found_child_1 = True
            if child == self.child_2:
                found_child_2 = True
            if child == self.child_4:
                found_child_4 = True
            if child == self.child_5:
                found_child_5 = True
            self.assertNotEqual(child, self.child_3,
                "Found deleted object 'child_3': %s" + str(self.data_obj))

        self.assertTrue(found_child_1,
            "child_1 should still be present: %s" % (str(self.data_obj)))
        self.assertTrue(found_child_2,
            "child_2 should still be present: %s" % (str(self.data_obj)))
        self.assertTrue(found_child_4,
            "child_4 should still be present: %s" % (str(self.data_obj)))
        self.assertTrue(found_child_5,
            "child_5 should still be present: %s" % (str(self.data_obj)))


if __name__ == '__main__':
    unittest.main()

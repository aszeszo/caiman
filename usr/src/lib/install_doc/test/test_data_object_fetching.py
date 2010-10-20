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
'''Tests for DataObject fetching methods'''

import unittest

from solaris_install.data_object import ObjectNotFoundError
from simple_data_object import create_simple_data_obj_tree, SimpleDataObject, \
    SimpleDataObject2, SimpleDataObject3, SimpleDataObject4, SimpleDataObject5


class  TestDataObjectFetching(unittest.TestCase):
    '''Tests for DataObject fetching methods'''

    def setUp(self):
        '''Create tree of data objects to test on'''
        self.data_objs = create_simple_data_obj_tree()

    def tearDown(self):
        '''Clean up references to objects'''
        self.data_objs = None
        del self.data_objs

    #
    # Test 'get_children()' and property 'children'
    #
    def test_dobj_get_all_children_using_method(self):
        '''Validate get_children() returns all children'''
        children = self.data_objs["data_obj"].get_children()
        internal_children = self.data_objs["data_obj"]._children

        # Ensure both are the same length.
        self.assertEquals(len(children), len(internal_children))

        # Ensure that while the lists themselves are different, the children
        # contained in the lists are the same - comparison of lists will
        # return true if they both contain the same items.
        self.assertEquals(children, internal_children)

        # Ensure that the list returned from get_children() is a copy
        children.remove(self.data_objs["child_3"])
        self.assertNotEquals(children, internal_children)

    def test_dobj_get_all_children_using_property(self):
        '''Validate .children property returns all children'''

        children = self.data_objs["data_obj"].children
        internal_children = self.data_objs["data_obj"]._children

        # Ensure both are the same length.
        self.assertEquals(len(children), len(internal_children))

        # Ensure that while the lists themselves are different, the children
        # contained in the lists are the same - comparison of lists will
        # return true if they both contain the same items.
        self.assertEquals(children, internal_children)

        # Ensure that the list returned from get_children() is a copy
        children.remove(self.data_objs["child_3"])
        self.assertNotEquals(children, internal_children)

    def test_dobj_get_all_children_using_method_max_count_2(self):
        '''Validate get_children(max_count=2) returns only 2 children'''
        children = self.data_objs["data_obj"].get_children(max_count=2)
        internal_children = self.data_objs["data_obj"]._children

        # Ensure both are the same length.
        self.assertEquals(len(children), 2)

        # Ensure that while the lists themselves are different, the children
        # contained in the lists are the same - comparison of lists will
        # return true if they both contain the same items.
        self.assertEquals(children, internal_children[:2])

    def test_dobj_get_children_by_name_unique(self):
        '''Validate get_children with unique name returns correct child'''
        found_obj_list = self.data_objs["data_obj"].get_children(
            name=self.data_objs["child_4"].name)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_4"])

    def test_dobj_get_children_by_name_multiple(self):
        '''Validate get_children with multiple name matches returns list'''
        found_obj_list = self.data_objs["data_obj"].get_children(
            name=self.data_objs["child_5"].name)

        self.assertTrue(len(found_obj_list) == 2)
        self.assertEqual(found_obj_list,
            [self.data_objs["child_5"], self.data_objs["child_5_same_name"]])

    def test_dobj_get_children_by_type_unique(self):
        '''Validate get_children with unique type match returns 1 child'''
        # Should return child_5 which is of type SimpleDataObject3
        found_obj_list = self.data_objs["data_obj"].get_children(
            class_type=SimpleDataObject3)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5"])

    def test_dobj_get_children_by_type_multiple(self):
        '''Validate get_children with multiple type matches returns list'''
        # Should return child_1 and child_4 which are of type SimpleDataObject2
        found_obj_list = self.data_objs["data_obj"].get_children(
            class_type=SimpleDataObject2)

        self.assertTrue(len(found_obj_list) == 2)
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_4"]])

    def test_dobj_get_children_by_name_and_type(self):
        '''Validate get_children matches with name and type'''
        # Should return child_4 which has name and type SimpleDataObject2
        found_obj_list = self.data_objs["data_obj"].get_children(
            name=self.data_objs["child_4"].name, class_type=SimpleDataObject2)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_4"])

    def test_dobj_get_children_by_name_not_exist(self):
        '''Validate get_children failure with non-exitant name'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_children, name="non_existant_name")

    def test_dobj_get_children_by_type_not_exist(self):
        '''Validate get_children failure with non-existant type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_children,
            class_type=SimpleDataObject4)

    def test_dobj_get_children_by_name_exist_and_type_not_exist(self):
        '''Validate get_children failure with valid name & non-existant type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_children,
            name=self.data_objs["child_4"].name, class_type=SimpleDataObject4)

    def test_dobj_get_children_by_name_not_exist_and_type_exist(self):
        '''Validate get_children failure with non-existant name & valid type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_children,
            name="non existant name", class_type=SimpleDataObject2)

    #
    # Test get_file_child()
    #
    def test_dobj_get_first_child(self):
        '''Validate get_first_child() returns first child'''

        child = self.data_objs["data_obj"].get_first_child()
        internal_children = self.data_objs["data_obj"]._children

        # Ensure that it's really the first child in internal list.
        self.assertEquals(child, internal_children[0])

    def test_dobj_get_first_child_no_children(self):
        '''Validate get_first_child() fails with no children'''

        child = self.data_objs["child_4"].get_first_child()

        # Ensure object has no children
        self.assertFalse(self.data_objs["child_4"].has_children)

        self.assertEquals(child, None,
            "Got child returned when parent had no children!")

    def test_dobj_get_first_child_by_name_unique(self):
        '''Validate get_first_child find first match of unique name'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            name=self.data_objs["child_4"].name)

        self.assertEqual(found_obj, self.data_objs["child_4"])

    def test_dobj_get_first_child_by_name_not_unique(self):
        '''Validate get_first_child find first match of non-unique name'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            name=self.data_objs["child_5"].name)

        self.assertEqual(found_obj, self.data_objs["child_5"])

    def test_dobj_get_first_child_by_type_unique(self):
        '''Validate get_first_child find first match of unique type'''
        # Should return child_5 which is of type SimpleDataObject3
        found_obj = self.data_objs["data_obj"].get_first_child(
            class_type=SimpleDataObject3)

        self.assertEqual(found_obj, self.data_objs["child_5"])

    def test_dobj_get_first_child_by_type_not_unique(self):
        '''Validate get_first_child find first match of non-unique type'''
        # Should return child_1 with type SimpleDataObject2, as is child_4
        found_obj = self.data_objs["data_obj"].get_first_child(
            class_type=SimpleDataObject2)

        self.assertEqual(found_obj, self.data_objs["child_1"])

    def test_dobj_get_first_child_by_name_and_type(self):
        '''Validate get_first_child find first match of name & type'''
        # Should return child_4 which has name and type SimpleDataObject2
        found_obj = self.data_objs["data_obj"].get_first_child(
            name=self.data_objs["child_4"].name, class_type=SimpleDataObject2)

        self.assertEqual(found_obj, self.data_objs["child_4"])

    def test_dobj_get_first_child_by_name_not_exist(self):
        '''Validate get_first_child fails for non-existant name'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            name="non_existant_name")
        self.assertEquals(found_obj, None)

    def test_dobj_get_first_child_by_type_not_exist(self):
        '''Validate get_first_child fails for non-existant type'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            class_type=SimpleDataObject4)
        self.assertEquals(found_obj, None)

    def test_dobj_get_first_child_by_name_exist_and_type_not_exist(self):
        '''Validate get_first_child fails for valid name & non-existant type'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            name=self.data_objs["child_4"].name, class_type=SimpleDataObject4)
        self.assertEquals(found_obj, None)

    def test_dobj_get_first_child_by_name_not_exist_and_type_exist(self):
        '''Validate get_first_child fails for non-existant name & valid type'''
        found_obj = self.data_objs["data_obj"].get_first_child(
            name="non existant name", class_type=SimpleDataObject2)
        self.assertEquals(found_obj, None)

    #
    # Test 'get_descendants()'
    #
    def test_dobj_get_descendants_by_name_unique(self):
        '''Validate get_descendants finds unique name'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
                                    name=self.data_objs["child_5_2_3_1"].name)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5_2_3_1"])

    def test_dobj_get_descendants_by_name_multiple(self):
        '''Validate get_descendants finds all objs with non-unique name'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            name=self.data_objs["child_3_1_2"].name)

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d" % (len(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_3_1_2"],
             self.data_objs["child_3_1_2_same_name"]])

    def test_dobj_get_descendants_by_type_unique(self):
        '''Validate get_descendants finds unique type'''
        # Should return child_5_2_3 which is of type SimpleDataObject4
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject4)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5_2_3"])

    def test_dobj_get_descendants_by_type_multiple(self):
        '''Validate get_descendants finds all objs with non-unique type'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject2)

        self.assertTrue(len(found_obj_list) == 6,
                "Expected len 6, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_2_1_1"],
                 self.data_objs["child_2_1_1_1"],
                 self.data_objs["child_2_1_1_2"], self.data_objs["child_4"]])

    def test_dobj_get_descendants_using_no_params(self):
        '''Validate get_descendants fails with no params'''
        self.assertRaises(ValueError,
            self.data_objs["data_obj"].get_descendants)

    def test_dobj_get_descendants_by_name_and_type(self):
        '''Validate get_descendants finds all objs with name & type'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
                                name=self.data_objs["child_2_1_1_2"].name,
                                class_type=SimpleDataObject2)

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_2_1_1_2"])

    def test_dobj_get_descendants_by_name_not_exist(self):
        '''Validate get_descendants fails with non-existant name'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_descendants,
            name="non_existant_name")

    def test_dobj_get_descendants_by_type_not_exist(self):
        '''Validate get_descendants fails with non-existant type'''
        self.assertRaises(ObjectNotFoundError,
        self.data_objs["data_obj"].get_descendants,
            class_type=SimpleDataObject5)

    def test_dobj_get_descendants_by_name_exist_and_type_not_exist(self):
        '''Validate get_descendants fails with valid name & non-existant type
        '''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_descendants,
            name=self.data_objs["child_5_2_2"].name,
            class_type=SimpleDataObject4)

    def test_dobj_get_descendants_by_name_not_exist_and_type_exist(self):
        '''Validate get_descendants fails with non-existant name & valid type
        '''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].get_descendants,
            name="non existant name", class_type=SimpleDataObject2)

    def test_dobj_get_descendants_by_type_and_max_depth_minus_1(self):
        '''Validate get_descendants fails with max_depth=-1'''
        self.assertRaises(ValueError,
            self.data_objs["data_obj"].get_descendants,
            class_type=SimpleDataObject2, max_depth=-1)

    def test_dobj_get_descendants_by_type_and_max_depth_1(self):
        '''Validate get_descendants limits by type to max_depth = 1'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject2, max_depth=1)

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_1"], self.data_objs["child_4"]])

    def test_dobj_get_descendants_by_type_and_max_depth_2(self):
        '''Validate get_descendants limits by type to max_depth = 2'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject2, max_depth=2)

        self.assertTrue(len(found_obj_list) == 3,
                "Expected len 3, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_4"]])

    def test_dobj_get_descendants_by_type_and_max_depth_3(self):
        '''Validate get_descendants limits by type to max_depth = 3'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject2, max_depth=3)

        self.assertTrue(len(found_obj_list) == 4,
                "Expected len 4, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_2_1_1"], self.data_objs["child_4"]])

    def test_dobj_get_descendants_by_type_and_max_depth_4(self):
        '''Validate get_descendants limits by type to max_depth = 4'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject2, max_depth=4)

        self.assertTrue(len(found_obj_list) == 6,
                "Expected len 6, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_2_1_1"],
                 self.data_objs["child_2_1_1_1"],
                 self.data_objs["child_2_1_1_2"], self.data_objs["child_4"]])

    def test_dobj_get_descendants_using_method_max_count_invalid(self):
        '''Validate get_descendants fails with max_count = 0'''
        self.assertRaises(ValueError,
            self.data_objs["data_obj"].get_descendants,
            class_type=SimpleDataObject, max_count=0)

    def test_dobj_get_descendants_by_type_and_max_count_1(self):
        '''Validate get_descendants limits by type to max_count = 1'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject, max_count=1)

        self.assertTrue(len(found_obj_list) == 1,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list, [self.data_objs["child_1"]])

    def test_dobj_get_descendants_by_type_and_max_count_2(self):
        '''Validate get_descendants limits by type to max_count = 2'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject, max_count=2)

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_1"], self.data_objs["child_1_1"]])

    def test_dobj_get_descendants_by_type_and_max_count_4(self):
        '''Validate get_descendants limits by type to max_count = 4'''
        found_obj_list = self.data_objs["data_obj"].get_descendants(
            class_type=SimpleDataObject, max_count=4)

        self.assertTrue(len(found_obj_list) == 4,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_1"], self.data_objs["child_1_1"],
             self.data_objs["child_1_2"], self.data_objs["child_2"]])

if __name__ == '__main__':
    unittest.main()

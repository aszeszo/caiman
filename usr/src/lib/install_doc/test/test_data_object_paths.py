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
'''Tests to validate DataObject paths functionality'''

import unittest

from solaris_install.data_object import ObjectNotFoundError, PathError, \
    DataObjectBase
import simple_data_object


class  TestDataObjectPaths(unittest.TestCase):
    '''Tests to validate DataObject paths functionality'''

    def setUp(self):
        '''Create ref to simple tree of data objects'''
        self.data_objs = simple_data_object.create_simple_data_obj_tree()

    def tearDown(self):
        '''Clean up references'''
        self.data_objs = None
        del self.data_objs

    def test_dobj_path_find_path_by_name(self):
        '''Validate simple paths, using name only, finds correct child'''

        # Find direct child.
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/%s" % (self.data_objs["child_3"].name))

        self.assertEqual(found_obj_list, [self.data_objs["child_3"]])

        # Search for deep child, at top - should fail.
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "/%s" % (self.data_objs["child_2_1_1_1"].name))

        # Search for same child again, but using '//' syntax, to search down.
        found_obj_list = self.data_objs["data_obj"].find_path("//%s" %
            (self.data_objs["child_2_1_1_1"].name))

        self.assertEqual(found_obj_list, [self.data_objs["child_2_1_1_1"]])

    def test_dobj_path_get_all_children_using_type(self):
        '''Validate path to object by type'''
        children = self.data_objs["data_obj"].find_path(
            "/[@solaris_install.data_object.DataObject]")
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

    def test_dobj_path_get_all_children_using_method_max_count_2(self):
        '''Validate path to objects with max_count == 2'''
        children = self.data_objs["data_obj"].find_path(
            "/[@solaris_install.data_object.DataObject#2]")
        internal_children = self.data_objs["data_obj"]._children

        # Ensure both are the same length.
        self.assertEquals(len(children), 2)

        # Ensure that while the lists themselves are different, the children
        # contained in the lists are the same - comparison of lists will
        # return true if they both contain the same items.
        self.assertEquals(children, internal_children[:2])

    def test_dobj_path_get_children_by_name_unique(self):
        '''Validate path to uniquely named object returns 1 obj'''
        found_obj_list = self.data_objs["data_obj"].find_path("/%s" %
            (self.data_objs["child_4"].name))

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_4"])

    def test_dobj_path_get_children_by_name_multiple(self):
        '''Validate path to non-unique named objects returns all matches'''
        found_obj_list = self.data_objs["data_obj"].find_path("/%s" %
            (self.data_objs["child_5"].name))

        self.assertTrue(len(found_obj_list) == 2)
        self.assertEqual(found_obj_list,
                [self.data_objs["child_5"],
                self.data_objs["child_5_same_name"]])

    def test_dobj_path_get_children_by_type_unique(self):
        '''Validate path with unique type returns 1 object'''
        # Should return child_5 which is of type SimpleDataObject3
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/[@simple_data_object.SimpleDataObject3]")

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5"])

    def test_dobj_path_get_children_by_type_multiple(self):
        '''Validate path with non-unique type returns correct children'''
        # Should return child_1 and child_4 which are of type SimpleDataObject2
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/[@simple_data_object.SimpleDataObject2]")

        self.assertTrue(len(found_obj_list) == 2)
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_4"]])

    def test_dobj_path_get_children_by_name_and_type(self):
        '''Validate path with name and type returns single match'''
        # Should return child_4 which has name and type SimpleDataObject2
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/%s[@simple_data_object.SimpleDataObject2]" %
            (self.data_objs["child_4"].name))

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_4"])

    def test_dobj_path_get_children_by_name_not_exist(self):
        '''Validate failure on path with non-existant name'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "/non_existant_name")

    def test_dobj_path_get_children_by_type_not_exist(self):
        '''Validate failure on path with non-existant type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "/[@simple_data_object.SimpleDataObject4]")

    def test_dobj_path_get_children_by_name_exist_and_type_not_exist(self):
        '''Validate failure on path with valid name and non-existant type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "/%s[@simple_data_object.SimpleDataObject4]" %
            (self.data_objs["child_4"].name))

    def test_dobj_path_get_children_by_name_not_exist_and_type_exist(self):
        '''Validate failure on path with non-existant name and valid type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "/non existant name[@simple_data_object.SimpleDataObject2]")

    #
    # Test get_file_child()
    #
    def test_dobj_path_get_first_child(self):
        '''Validate path limit to first match'''
        child_list = self.data_objs["data_obj"].find_path(
            "/[@solaris_install.data_object.DataObject#1]")
        internal_children = [self.data_objs["data_obj"]._children[0]]

        # Ensure that it's really the first child in internal list.
        self.assertEquals(child_list, internal_children)

    def test_dobj_path_get_first_child_no_children(self):
        '''Validate failure on path with no children & limit to first match'''

        self.assertRaises(ObjectNotFoundError,
            self.data_objs["child_4"].find_path,
            "/[@solaris_install.data_object.DataObject#1]")

    def test_dobj_path_get_first_child_by_name_unique(self):
        '''Validate path with name and limit to first match'''
        found_obj = self.data_objs["data_obj"].find_path("/%s[#1]" %
            (self.data_objs["child_4"].name))

        self.assertEqual(found_obj, [self.data_objs["child_4"]])

    def test_dobj_path_get_first_child_by_name_not_unique(self):
        '''Validate path with non-unique name and limit to first match'''
        found_obj = self.data_objs["data_obj"].find_path("/%s[#1]" %
            (self.data_objs["child_5"].name))

        self.assertEqual(found_obj, [self.data_objs["child_5"]])

    def test_dobj_path_get_first_child_by_type_unique(self):
        '''Validate path with unique type and limit to first match'''
        # Should return child_5 which is of type SimpleDataObject3
        found_obj = self.data_objs["data_obj"].find_path(
            "/[@simple_data_object.SimpleDataObject3#1]")

        self.assertEqual(found_obj, [self.data_objs["child_5"]])

    def test_dobj_path_get_first_child_by_type_not_unique(self):
        '''Validate path with non-unique name and limit to first match'''
        # Should return child_1 with type SimpleDataObject2, as is child_4
        found_obj = self.data_objs["data_obj"].find_path(
            "/[@simple_data_object.SimpleDataObject2#1]")

        self.assertEqual(found_obj, [self.data_objs["child_1"]])

    def test_dobj_path_get_first_child_by_name_and_type(self):
        '''Validate path with name and type and limit to first match'''
        # Should return child_4 which has name and type SimpleDataObject2
        found_obj = self.data_objs["data_obj"].find_path(
            "/%s[@simple_data_object.SimpleDataObject2#1]" %
            (self.data_objs["child_4"].name))

        self.assertEqual(found_obj, [self.data_objs["child_4"]])

    #
    # Test 'get_descendants()'
    #
    def test_dobj_path_get_descendants_by_name_unique(self):
        '''Validate path with deep search by unique name'''
        found_obj_list = self.data_objs["data_obj"].find_path("//%s" %
                                    (self.data_objs["child_5_2_3_1"].name))

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5_2_3_1"])

    def test_dobj_path_get_descendants_by_name_multiple(self):
        '''Validate path with deep search by non-unique name'''
        found_obj_list = self.data_objs["data_obj"].find_path("//%s" %
                                    (self.data_objs["child_3_1_2"].name))

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d" % (len(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_3_1_2"],
                self.data_objs["child_3_1_2_same_name"]])

    def test_dobj_path_get_descendants_by_type_unique(self):
        '''Validate path with deep search by unique type'''
        # Should return child_5_2_3 which is of type SimpleDataObject4
        found_obj_list = self.data_objs["data_obj"].find_path(
        "//[@simple_data_object.SimpleDataObject4]")

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_5_2_3"])

    def test_dobj_path_get_descendants_by_type_multiple(self):
        '''Validate path with deep search by non-unique type'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2]")

        self.assertTrue(len(found_obj_list) == 6,
                "Expected len 6, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                self.data_objs["child_2_1_1"], self.data_objs["child_2_1_1_1"],
                self.data_objs["child_2_1_1_2"], self.data_objs["child_4"]])

    def test_dobj_path_get_descendants_name_by_type_multiple(self):
        '''Validate path with deep search by non-unique type and name attr'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2].name")

        self.assertTrue(len(found_obj_list) == 6,
                "Expected len 6, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                ["child_1", "child_2_1", "child_2_1_1", "child_2_1_1_1",
                 "child_2_1_1_2", "child_4"])

    def test_dobj_path_get_descendants_by_name_and_type(self):
        '''Validate path with deep search by name and type'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//%s[@simple_data_object.SimpleDataObject2]" %
            (self.data_objs["child_2_1_1_2"].name))

        self.assertTrue(len(found_obj_list) == 1)
        self.assertEqual(found_obj_list[0], self.data_objs["child_2_1_1_2"])

    def test_dobj_path_get_descendants_by_name_not_exist(self):
        '''Validate failure on path with deep search by non-existant name'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "//non_existant_name")

    def test_dobj_path_get_descendants_by_type_not_exist(self):
        '''Validate fail on path with deep search by non-existant type'''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "//[@simple_data_object.SimpleDataObject5]")

    def test_dobj_path_get_descendants_by_name_exist_and_type_not_exist(self):
        '''Validate fail on path with deep search by valid name & invalid type
        '''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "//%s[@simple_data_object.SimpleDataObject4]" %
            (self.data_objs["child_5_2_2"].name))

    def test_dobj_path_get_descendants_by_name_not_exist_and_type_exist(self):
        '''Validate failure on path deep search non-existant name & valid type
        '''
        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path,
            "//nonexistantname[@simple_data_object.SimpleDataObject2]")

    def test_dobj_path_get_descendants_by_type_and_max_depth_minus_1(self):
        '''Validate failure on path deep search with invalid (-1) max_depth'''
        self.assertRaises(ValueError, self.data_objs["data_obj"].find_path,
            "//[@simple_data_object.SimpleDataObject2?-1]")

    def test_dobj_path_get_descendants_by_type_and_max_depth_1(self):
        '''Validate path with deep search by type and max_depth == 1'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2?1]")

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_1"], self.data_objs["child_4"]])

    def test_dobj_path_get_descendants_by_type_and_max_depth_2(self):
        '''Validate path with deep search by type and max_depth == 2'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2?2]")

        self.assertTrue(len(found_obj_list) == 3,
                "Expected len 3, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_4"]])

    def test_dobj_path_get_descendants_by_type_and_max_depth_3(self):
        '''Validate path with deep search by type and max_depth == 3'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2?3]")

        self.assertTrue(len(found_obj_list) == 4,
                "Expected len 4, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_2_1_1"], self.data_objs["child_4"]])

    def test_dobj_path_get_descendants_by_type_and_max_depth_4(self):
        '''Validate path with deep search by type and max_depth == 4'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject2?4]")

        self.assertTrue(len(found_obj_list) == 6,
                "Expected len 6, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
                [self.data_objs["child_1"], self.data_objs["child_2_1"],
                 self.data_objs["child_2_1_1"],
                 self.data_objs["child_2_1_1_1"],
                 self.data_objs["child_2_1_1_2"], self.data_objs["child_4"]])

    def test_dobj_path_get_descendants_using_method_max_count_invalid(self):
        '''Validate fail on path with deep search with invalid max_count (-1)
        '''
        self.assertRaises(ValueError, self.data_objs["data_obj"].find_path,
            "//[@simple_data_object.SimpleDataObject#0]")

    def test_dobj_path_get_descendants_by_type_and_max_count_1(self):
        '''Validate path with deep search by type and max_count == 1'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject#1]")

        self.assertTrue(len(found_obj_list) == 1,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list, [self.data_objs["child_1"]])

    def test_dobj_path_get_descendants_by_type_and_max_count_2(self):
        '''Validate path with deep search by type and max_count == 2'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject#2]")

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list, [self.data_objs["child_1"],
            self.data_objs["child_1_1"]])

    def test_dobj_path_get_descendants_by_type_and_max_count_4(self):
        '''Validate path with deep search by type and max_count == 4'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "//[@simple_data_object.SimpleDataObject#4]")

        self.assertTrue(len(found_obj_list) == 4,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list, [self.data_objs["child_1"],
            self.data_objs["child_1_1"], self.data_objs["child_1_2"],
            self.data_objs["child_2"]])

    def test_dobj_path_get_deep_path_objs(self):
        '''Validate path with long path and max_count'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/child_2/child_2_1/child_2_1_1/"
            "[@simple_data_object.SimpleDataObject#4]")

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            [self.data_objs["child_2_1_1_1"], self.data_objs["child_2_1_1_2"]])

    def test_dobj_path_get_deep_path_name(self):
        '''Validate path with long path and max_count getting name attr'''
        found_obj_list = self.data_objs["data_obj"].find_path(
            "/child_2/child_2_1/child_2_1_1/"
            "[@simple_data_object.SimpleDataObject#4].name")

        self.assertTrue(len(found_obj_list) == 2,
                "Expected len 2, got %d : %s" %
                    (len(found_obj_list), str(found_obj_list)))
        self.assertEqual(found_obj_list,
            ["child_2_1_1_1", "child_2_1_1_2"])

    def test_dobj_path_find_path_prop(self):
        '''Validate object_path property can retrieve same object'''
        test_obj = self.data_objs["child_2_1_1_1"]
        self.assertEquals("/child_2/child_2_1/child_2_1_1/child_2_1_1_1",
            test_obj.object_path)

        # Ensure that fetching something by it's own path returns itself.
        self.assertEquals([test_obj],
            self.data_objs["data_obj"].find_path(test_obj.object_path))

    def test_dobj_path_find_path_special_chars(self):
        '''Validate correct handling of path with special chars'''
        # Construct a special tree for this test
        root = simple_data_object.SimpleDataObject("root")
        child_1 = simple_data_object.SimpleDataObject("using/some/slashes")
        child_2 = simple_data_object.SimpleDataObject("using /%$ ?'@#&")
        child_1_1 = simple_data_object.SimpleDataObject(
            "using / some / slashes&others!? $%^!*^&")
        child_2_1 = simple_data_object.SimpleDataObject("using just spaces")

        root.insert_children([child_1, child_2])
        child_1.insert_children(child_1_1)
        child_2.insert_children(child_2_1)

        # Ensure that fetching something by it's own path returns itself.
        self.assertEquals([child_1_1],
            root.find_path(child_1_1.object_path))

        self.assertEquals([child_2_1],
            root.find_path(child_2_1.object_path))

    def test_dobj_path_find_path_end_slash_ignored(self):
        '''Validate path with trailing slash'''
        end_slash = "/child_1/"

        self.assertEquals([self.data_objs["child_1"]],
            self.data_objs["data_obj"].find_path(end_slash))

    def test_dobj_path_find_path_fail_bad_paths(self):
        '''Validate fail on path without '/' at start'''
        rel_path = "child_1/child_1_1"

        self.assertRaises(PathError,
            self.data_objs["data_obj"].find_path, rel_path)

    def test_dobj_path_find_path_1_valid_attribute(self):
        '''Validate path with unique name getting attribute'''
        attr = "/child_1/child_1_1.name"

        attr_val_list = self.data_objs["data_obj"].find_path(attr)

        self.assertEquals(attr_val_list,
            [self.data_objs["child_1_1"].name])

    def test_dobj_path_find_path_many_valid_attribute(self):
        '''Validate path with non-unique name getting attribute'''
        attr = "//child_5_2_3/[@DataObject].name"

        attr_val_list = self.data_objs["data_obj"].find_path(attr)

        self.assertEquals(attr_val_list,
            [self.data_objs["child_5_2_3_1"].name,
             self.data_objs["child_5_2_3_2"].name,
             self.data_objs["child_5_2_3_3"].name,
             self.data_objs["child_5_2_3_3"].name])

    def test_dobj_path_find_path_no_name_or_class_type(self):
        '''Validate access to path with no name to access attribute'''
        attr = "/child_1/.name"

        self.assertEquals(self.data_objs["data_obj"].find_path(attr),
            [self.data_objs["child_1_1"].name,
             self.data_objs["child_1_2"].name])

    def test_dobj_path_find_path_fail_bad_attribute(self):
        '''Validate fail on path attempting to access protected attributes'''
        attr = "/child_1/child_1_1._name"

        self.assertRaises(AttributeError,
            self.data_objs["data_obj"].find_path, attr)

    def test_dobj_path_find_path_ignore_bad_expr(self):
        '''Validate path with bad expr ignores the bad elements'''
        attr = "//child_5_2_3/[a bad expr, here].name"

        attr_val_list = self.data_objs["data_obj"].find_path(attr)

        self.assertEquals(attr_val_list,
            [self.data_objs["child_5_2_3_1"].name,
             self.data_objs["child_5_2_3_2"].name,
             self.data_objs["child_5_2_3_3"].name,
             self.data_objs["child_5_2_3_3"].name])

    def test_dobj_path_find_path_fail_no_matches(self):
        '''Validate path with non-existant name fails'''
        attr = "/child_1/no_such_child"

        self.assertRaises(ObjectNotFoundError,
            self.data_objs["data_obj"].find_path, attr)

    def test_dobj_path_find_path_fail_invalid_mod_name(self):
        '''Validate path with non-existant object module name fails'''
        attr = "/child_1/[@no_such_mod.MyObject]"

        self.assertRaises(PathError,
            self.data_objs["data_obj"].find_path, attr)

    def test_dobj_path_find_path_fail_invalid_class_name(self):
        '''Validate path with non-existant Class and no module name fails'''
        attr = "/child_1/[@MyObject]"

        self.assertRaises(PathError,
            self.data_objs["data_obj"].find_path, attr)

    def test_dobj_path_find_path_fail_valid_mod_not_class(self):
        '''Validate path with non-existant Class and in a valid module fails'''
        attr = "/child_1/[@solaris_install.data_object.NoSuchClass]"

        self.assertRaises(PathError,
            self.data_objs["data_obj"].find_path, attr)

    def test_dobj_path_find_path_just_slashes(self):
        '''Validate path with just '/' or '//' '''
        self.assertEqual(self.data_objs["data_obj"].find_path("/"),
            self.data_objs["data_obj"].children)

        self.assertEqual(self.data_objs["data_obj"].find_path("//"),
            self.data_objs["data_obj"].get_descendants(
                class_type=DataObjectBase))

    def test_dobj_path_simple_str_subst(self):
        """Validate string replace with some simple substitutions
        """
        self.assertEquals(self.data_objs["data_obj"].str_replace_paths_refs(
            "value=%{//child_5_2_3_1.name}"),
            "value='child_5_2_3_1'")

        self.assertEquals(self.data_objs["data_obj"].str_replace_paths_refs(
            "allvalues=%{//[@simple_data_object.SimpleDataObject2].name}"),
            "allvalues='child_1','child_2_1','child_2_1_1','child_2_1_1_1',"
            "'child_2_1_1_2','child_4'")

        self.assertEquals(self.data_objs["data_obj"].str_replace_paths_refs(
            "allvalues=%{/child_2//.name}"),
            "allvalues="
            "'child_2_1','child_2_1_1','child_2_1_1_1','child_2_1_1_2'")

        self.assertEquals(self.data_objs["data_obj"].str_replace_paths_refs(
            "allvalues=%{/child_2//.name}", value_separator=" "),
            "allvalues="
            "'child_2_1' 'child_2_1_1' 'child_2_1_1_1' 'child_2_1_1_2'")

    def test_dobj_path_multiple_str_subst(self):
        """Validate string replace with some multiple substitutions
        """
        self.assertEquals(self.data_objs["data_obj"].str_replace_paths_refs(
            "value1=%{//child_3_1_1.name}"
            " value2=%{//child_5_2_1.name}"),
            "value1='child_3_1_1' value2='child_5_2_1'")


if __name__ == '__main__':
    unittest.main()

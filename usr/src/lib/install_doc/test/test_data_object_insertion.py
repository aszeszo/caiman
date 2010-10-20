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
'''Tests for DataObject insertion methods'''

import unittest

from solaris_install.data_object import ObjectNotFoundError
from simple_data_object import SimpleDataObject


class TestDataObjectInsertion(unittest.TestCase):
    '''Tests for DataObject insertion methods'''

    def setUp(self):
        '''Create simple data object reference'''
        self.data_obj = SimpleDataObject("root")

    def tearDown(self):
        '''Clean up data_obj reference'''
        self.data_obj = None

    def test_insert_children_default_single(self):
        '''Validate insertion of single child'''
        new_do = SimpleDataObject("child_1")

        self.data_obj.insert_children(new_do)
        self.assertEqual(self.data_obj.children[0], new_do)

    def test_insert_children_default_fail_both_before_and_after(self):
        '''Validate failure on insert with invalid before and after'''
        new_do = SimpleDataObject("child_1")

        self.assertRaises(ValueError, self.data_obj.insert_children,
            new_do, new_do, new_do)

    def test_insert_children_default_fail_single(self):
        '''Validate failure on insert with non-DataObjectBase sub-class'''
        new_obj = object()

        self.assertRaises(TypeError, self.data_obj.insert_children, new_obj)

    def test_insert_children_default_fail_single_null_param(self):
        '''Validate failure on insert of None value'''
        self.assertRaises(TypeError, self.data_obj.insert_children, None)

    def test_insert_children_default_list(self):
        '''Validate insert of list of children'''
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)
        i = 0
        for child in self.data_obj.children:
            self.assertEqual(child, new_do_list[i])
            i += 1
        self.assertEqual(i, len(new_do_list))

    def test_insert_children_default_fail_list(self):
        '''Validate failure of insert of list of children with bad element'''
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(object())

        self.assertRaises(TypeError, self.data_obj.insert_children,
            new_do_list)

    def test_insert_children_default_fail_tuple(self):
        '''Validate failure of insert of tuple of children with bad element'''
        # Create tuple
        new_do_list = (
            SimpleDataObject("child_1"),
            SimpleDataObject("child_2"),
            SimpleDataObject("child_3"),
            SimpleDataObject("child_4"), object())

        self.assertRaises(TypeError, self.data_obj.insert_children,
            new_do_list)

    def test_insert_children_default_fail_invalid_type(self):
        '''Validate failure of insert of child with non-DataObjectBase'''
        self.assertRaises(TypeError, self.data_obj.insert_children,
            object())

    def test_insert_children_before_single(self):
        '''Validate insertion of children list with before value'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        child_3 = SimpleDataObject("child_3")
        new_do_list.append(child_3)
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something before child_3
        new_do = SimpleDataObject("before_child_3")
        self.data_obj.insert_children(new_do, before=child_3)

        i = 0
        for child in self.data_obj.children:
            if i == 2:
                self.assertEqual(child, new_do, str(self.data_obj))
                break
            i += 1

    def test_insert_children_before_doesnt_exist(self):
        '''Validate failure on insertion with non-existant 'before' obj'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        not_in_list = SimpleDataObject("child_not_in_list")

        new_do = SimpleDataObject("before_child_3")
        #Now for the real test, to insert something before non-existant child
        self.assertRaises(ObjectNotFoundError, self.data_obj.insert_children,
            new_do, before=not_in_list)

    def test_insert_children_after_doesnt_exist(self):
        '''Validate failure on insertion with non-existant 'after' obj'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        not_in_list = SimpleDataObject("child_not_in_list")

        new_do = SimpleDataObject("after_child_3")
        #Now for the real test, to insert something after non-existant child
        self.assertRaises(ObjectNotFoundError, self.data_obj.insert_children,
            new_do, after=not_in_list)

    def test_insert_children_before_first_single(self):
        '''Validate insertion of child with before == first child'''
        # Populate existing children first.
        new_do_list = list()
        child_1 = SimpleDataObject("child_1")
        new_do_list.append(child_1)
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something before child_1
        new_do = SimpleDataObject("before_child_1")
        self.data_obj.insert_children(new_do, before=child_1)

        self.assertEqual(self.data_obj.children[0],
                         new_do, str(self.data_obj))

    def test_insert_children_after_single(self):
        '''Validate insertion of children with after value'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        child_3 = SimpleDataObject("child_3")
        new_do_list.append(child_3)
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something before child_3
        new_do = SimpleDataObject("after_child_5")
        self.data_obj.insert_children(new_do, after=child_3)

        i = 0
        for child in self.data_obj.children:
            if i == 3:
                self.assertEqual(child, new_do, str(self.data_obj))
                break
            i += 1

    def test_insert_children_after_last_single(self):
        '''Validate insertion of children with after == last child'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))
        child_5 = SimpleDataObject("child_5")
        new_do_list.append(child_5)

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something after child_5
        new_do = SimpleDataObject("after_child_5")
        self.data_obj.insert_children(new_do, after=child_5)

        children = self.data_obj.children
        self.assertEqual(children[len(children) - 1],
                         new_do, str(self.data_obj))

    def test_insert_children_before_list(self):
        '''Validate insertion of children with before value'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        child_3 = SimpleDataObject("child_3")
        new_do_list.append(child_3)
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something before child_3
        to_insert = list()
        to_insert.append(SimpleDataObject("before_child_3 - A"))
        to_insert.append(SimpleDataObject("before_child_3 - B"))
        to_insert.append(SimpleDataObject("before_child_3 - C"))

        self.data_obj.insert_children(to_insert, before=child_3)

        i = 0
        j = 0
        for child in self.data_obj.children:
            if i >= 2:
                self.assertEqual(child, to_insert[j],
                    "child = %s ; compared_to = %s" % (child, to_insert[j]))
                j += 1
                if j >= len(to_insert):
                    break
            i += 1

    def test_insert_children_before_first_list(self):
        '''Validate insertion of children with before == first child'''
        # Populate existing children first.
        new_do_list = list()
        child_1 = SimpleDataObject("child_1")
        new_do_list.append(child_1)
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something before child_1
        to_insert = list()
        to_insert.append(SimpleDataObject("before_child_1 - A"))
        to_insert.append(SimpleDataObject("before_child_1 - B"))
        to_insert.append(SimpleDataObject("before_child_1 - C"))

        self.data_obj.insert_children(to_insert, before=child_1)

        i = 0
        for child in self.data_obj.children:
            self.assertEqual(child, to_insert[i],
                "child = %s ; compared_to = %s" % (child, to_insert[i]))
            i += 1
            if not (i < len(to_insert)):
                break

    def test_insert_children_after_list(self):
        '''Validate insertion of children list with after value'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_1"))
        new_do_list.append(SimpleDataObject("child_2"))
        child_3 = SimpleDataObject("child_3")
        new_do_list.append(child_3)
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something after child_3
        to_insert = list()
        to_insert.append(SimpleDataObject("after_child_3 - A"))
        to_insert.append(SimpleDataObject("after_child_3 - B"))
        to_insert.append(SimpleDataObject("after_child_3 - C"))

        self.data_obj.insert_children(to_insert, after=child_3)

        i = 0
        j = 0
        for child in self.data_obj.children:
            if i >= 3:
                self.assertEqual(child, to_insert[j],
                    "child = %s ; compared_to = %s" % (child, to_insert[j]))
                j += 1
                if j >= len(to_insert):
                    break
            i += 1

    def test_insert_children_after_last_list(self):
        '''Validate insertion of children list with after == last child'''
        # Populate existing children first.
        new_do_list = list()
        new_do_list.append(SimpleDataObject("child_2"))
        new_do_list.append(SimpleDataObject("child_3"))
        new_do_list.append(SimpleDataObject("child_4"))
        new_do_list.append(SimpleDataObject("child_5"))
        child_5 = SimpleDataObject("child_5")
        new_do_list.append(child_5)

        self.data_obj.insert_children(new_do_list)

        #Now for the real test, to insert something after child_5
        to_insert = list()
        to_insert.append(SimpleDataObject("after_child_3 - A"))
        to_insert.append(SimpleDataObject("after_child_3 - B"))
        to_insert.append(SimpleDataObject("after_child_3 - C"))

        self.data_obj.insert_children(to_insert, after=child_5)

        children = self.data_obj.children
        num_children = len(children)
        offset = num_children - len(to_insert)
        for i in range(len(to_insert)):
            self.assertEqual(children[offset + i], to_insert[i],
                "child = %s ; compared_to = %s" %
                (children[offset + i], to_insert[i]))

if __name__ == '__main__':
    unittest.main()

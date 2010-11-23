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
'''Tests to ensure that DataObject XML support is working as expected'''

import unittest

from solaris_install.data_object import DataObject
from simple_data_object import SimpleDataObject, SimpleDataObject2, \
    SimpleDataObject3, SimpleDataObjectHandlesChildren


class TestDataObjectXmlSupport(unittest.TestCase):
    '''Tests to ensure that DataObject XML support is working as expected'''

    def setUp(self):
        '''Create an XML tree for testing and references to them.

        The tree will look like the following:

            root
                child_1
                    child_1_1
                    child_1_2
                child_2
                    child_2_1
                        child_2_1_1
                            child_2_1_1_1
                            child_2_1_1_2
                child_3
                    child_3_1
                        child_3_1_2
                        child_3_1_2
                        child_3_1_2_same_name
                child_4
                child_5
                    child_5_1
                    child_5_2
                        child_5_2_1
                        child_5_2_2
                        child_5_2_3
                            child_5_2_3_1
                            child_5_2_3_2
                            child_5_2_3_3
                            child_5_2_3_3_same_name
                child_5_same_name
        '''

        # Create root node
        self.data_obj = SimpleDataObject("root")
        # Add some children, used by most tests.
        self.child_1 = SimpleDataObject2("child_1")
        self.child_2 = SimpleDataObject("child_2")
        self.child_3 = SimpleDataObject("child_3")
        self.child_4 = SimpleDataObject2("child_4")
        self.child_5 = SimpleDataObject3("child_5")

        self.do_list = list()
        self.do_list.append(self.child_1)
        self.do_list.append(self.child_2)
        self.do_list.append(self.child_3)
        self.do_list.append(self.child_4)
        self.do_list.append(self.child_5)

        self.data_obj.insert_children(self.do_list)

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
        self.child_5_2_3 = SimpleDataObjectHandlesChildren("child_5_2_3")
        self.child_5_2.insert_children(
            [self.child_5_2_1, self.child_5_2_2, self.child_5_2_3])

        self.child_5_2_3_1 = SimpleDataObject("child_5_2_3_1")
        self.child_5_2_3_2 = SimpleDataObject("child_5_2_3_2")
        self.child_5_2_3_3 = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3_3_same_name = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3.insert_children(
            [self.child_5_2_3_1, self.child_5_2_3_2,
            self.child_5_2_3_3, self.child_5_2_3_3_same_name])

    def tearDown(self):
        '''Clean up all references to objects'''
        self.data_obj = None
        self.child_1 = None
        self.child_2 = None
        self.child_3 = None
        self.child_4 = None
        self.child_5 = None
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

    def test_data_object_xml_support_skips_levels(self):
        '''Validate XML generation will skip levels if child doesn't gen XML'''
        # SimpleDataObject3 objects don't generate XML, so should be skipped
        # and all of child_5's children should be direct sub-elements of the
        # node called 'root'

        xml_tree = self.data_obj.get_xml_tree()

        child_names = []
        for xml_child in xml_tree:
            child_names.append(xml_child.get("name"))

        self.assertEqual(child_names,
            [self.child_1.name, self.child_2.name, self.child_3.name,
             self.child_4.name, self.child_5_1.name, self.child_5_2.name])

    def test_data_object_xml_support_parent_generates_xml(self):
        '''Validate ability to generate XML for children'''
        # child_5_2_3 generates the xml for it's children in the form:
        #   <child name="<NAME>"/>

        xml_tree = self.child_5_2_3.get_xml_tree()
        names = []
        for xml_child in xml_tree:
            self.assertEqual(xml_child.tag,
                SimpleDataObjectHandlesChildren.TAG_NAME,
                "sib-element had unexpected tag : %s" % (xml_child.tag))
            names.append(xml_child.get("name"))

        self.assertEqual(names, \
            [self.child_5_2_3_1.name, self.child_5_2_3_2.name,
             self.child_5_2_3_3.name, self.child_5_2_3_3_same_name.name])

    def test_data_object_xml_support_get_tree_string(self):
        '''Validate ability to generate XML using get_xml_tree_str()'''
        # Define expected string, compensate for indent. Using '.' in expected
        # string to remove conflict with indent replacement.
        indentation = '''\
        '''
        expected_xml = '''\
        <SimpleDataObject name="root">
        ..<SimpleDataObject2 name="child_1">
        ....<SimpleDataObject name="child_1_1"/>
        ....<SimpleDataObject name="child_1_2"/>
        ..</SimpleDataObject2>
        ..<SimpleDataObject name="child_2">
        ....<SimpleDataObject2 name="child_2_1">
        ......<SimpleDataObject2 name="child_2_1_1">
        ........<SimpleDataObject2 name="child_2_1_1_1"/>
        ........<SimpleDataObject2 name="child_2_1_1_2"/>
        ......</SimpleDataObject2>
        ....</SimpleDataObject2>
        ..</SimpleDataObject>
        ..<SimpleDataObject name="child_3">
        ....<SimpleDataObject name="child_3_1">
        ......<SimpleDataObject name="child_3_1_1"/>
        ......<SimpleDataObject name="child_3_1_2"/>
        ......<SimpleDataObject name="child_3_1_2"/>
        ....</SimpleDataObject>
        ..</SimpleDataObject>
        ..<SimpleDataObject2 name="child_4"/>
        ..<SimpleDataObject name="child_5_1"/>
        ..<SimpleDataObject name="child_5_2">
        ....<SimpleDataObject name="child_5_2_1"/>
        ....<SimpleDataObject name="child_5_2_2"/>
        ....<SimpleDataObjectHandlesChildren name="child_5_2_3">
        ......<so_child name="child_5_2_3_1"/>
        ......<so_child name="child_5_2_3_2"/>
        ......<so_child name="child_5_2_3_3"/>
        ......<so_child name="child_5_2_3_3"/>
        ....</SimpleDataObjectHandlesChildren>
        ..</SimpleDataObject>
        </SimpleDataObject>
        '''.replace(indentation, "").replace(".", " ")
        xml_str = self.data_obj.get_xml_tree_str()

        self.assertEqual(xml_str, expected_xml,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n'%s'\nEXPECTED:\n'%s'\n" %
            (len(xml_str), len(expected_xml), xml_str, expected_xml))

    def test_data_object_xml_methods(self):
        '''Validate XML methods react correctly to None parameter'''
        self.assertFalse(DataObject.can_handle(None))

        self.assertFalse(DataObject.from_xml(None))

if __name__ == '__main__':
    unittest.main()

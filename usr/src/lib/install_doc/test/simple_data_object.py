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
'''Create some simple DataObject implmentations to allow for testing.'''

from lxml import etree

from solaris_install.data_object import DataObject


class SimpleDataObject(DataObject):
    '''Base simple data object, that enables import/export of XML'''

    @classmethod
    def can_handle(cls, xml_node):
        '''Handle any tag with the same name as the class'''
        if xml_node.tag == cls.__name__:
            return True

    @classmethod
    def from_xml(cls, xml_node):
        '''Import XML tags with the same name as the class'''
        if xml_node.tag == cls.__name__:
            # Create a new object, appropriate for the classname, works for
            # sub-classes too...
            return globals()[cls.__name__](xml_node.attrib.get("name").strip())

        return None

    def to_xml(self):
        '''Generate XML tags with the same name as the class'''
        element = etree.Element(self.__class__.__name__, name=self.name)
        return element

    def __repr__(self):
        '''Describe the class for debug output'''
        return "%s: name = %s" % (self.__class__.__name__, self.name)


class SimpleDataObjectNoXml(SimpleDataObject):
    '''Simple DataObject that doesn't generate XML'''

    @classmethod
    def can_handle(cls, xml_node):
        '''Doesn't import any XML'''
        return False

    @classmethod
    def from_xml(cls, xml_node):
        '''Doesn't import any XML'''
        return None

    def to_xml(self):
        '''Doesn't generate any XML'''
        return None


# Define an alternative SimpleDataObjects for testing by by type
class SimpleDataObject2(SimpleDataObject):
    '''Alternative class definition for searching by class type tests'''
    pass


class SimpleDataObject3(SimpleDataObjectNoXml):
    '''Alternative class definition for searching by class type without XML'''
    pass


class SimpleDataObject4(SimpleDataObject):
    '''Alternative class definition for searching by class type tests'''
    pass


class SimpleDataObject5(SimpleDataObject):
    '''Alternative class definition for searching by class type tests'''
    pass


# Simple DataObject that imports and generates children's XML
class SimpleDataObjectHandlesChildren(SimpleDataObject):
    '''A simple DataObject that generates and imports XML for it's children'''

    TAG_NAME = "so_child"

    def __init__(self, name):
        super(SimpleDataObjectHandlesChildren, self).__init__(name)
        self.generates_xml_for_children = True

    def to_xml(self):
        '''Generate XML for itself and it's children'''
        element = etree.Element(self.__class__.__name__, name=self.name)

        for child in self.children:
            sub_element = etree.SubElement(element, self.TAG_NAME)
            sub_element.set("name", child.name)

        return element

    @classmethod
    def can_handle(cls, xml_node):
        '''Can import XML for itself and it's children'''
        if xml_node.tag == cls.__name__:
            return True

    @classmethod
    def from_xml(cls, xml_node):
        '''Import XML for itself and it's children'''
        if xml_node.tag != cls.__name__:
            return None

        new_obj = SimpleDataObjectHandlesChildren(
            xml_node.attrib.get("name").strip())

        # Now, we need to handle children we generated
        for node in xml_node:
            if node.tag == cls.TAG_NAME:
                new_child = SimpleDataObject(node.get("name").strip())
                new_obj.insert_children(new_child)

        return new_obj


def create_simple_data_obj_tree():
    '''Create test object tree and return dict to access specific elements'''

    # Create a tree that looks like:
    #
    #    root
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

    object_dict = dict()

    # Create root node
    object_dict["data_obj"] = SimpleDataObject("root")
    # Add some children, used by most tests.
    object_dict["child_1"] = SimpleDataObject2("child_1")
    object_dict["child_2"] = SimpleDataObject("child_2")
    object_dict["child_3"] = SimpleDataObject("child_3")
    object_dict["child_4"] = SimpleDataObject2("child_4")
    object_dict["child_5"] = SimpleDataObject3("child_5")
    object_dict["child_5_same_name"] = SimpleDataObject("child_5")

    do_list = list()
    do_list.append(object_dict["child_1"])
    do_list.append(object_dict["child_2"])
    do_list.append(object_dict["child_3"])
    do_list.append(object_dict["child_4"])
    do_list.append(object_dict["child_5"])
    do_list.append(object_dict["child_5_same_name"])

    object_dict["data_obj"].insert_children(do_list)

    # Now let's add the children of children, etc. for use by
    # get_descendants() tests.
    # child_1 children
    object_dict["child_1_1"] = SimpleDataObject("child_1_1")
    object_dict["child_1_2"] = SimpleDataObject("child_1_2")
    object_dict["child_1"].insert_children(
        [object_dict["child_1_1"], object_dict["child_1_2"]])

    # child_2 tree
    object_dict["child_2_1"] = SimpleDataObject2("child_2_1")
    object_dict["child_2"].insert_children(object_dict["child_2_1"])
    object_dict["child_2_1_1"] = SimpleDataObject2("child_2_1_1")
    object_dict["child_2_1"].insert_children(object_dict["child_2_1_1"])
    object_dict["child_2_1_1_1"] = SimpleDataObject2("child_2_1_1_1")
    object_dict["child_2_1_1_2"] = SimpleDataObject2("child_2_1_1_2")
    object_dict["child_2_1_1"].insert_children(
        [object_dict["child_2_1_1_1"], object_dict["child_2_1_1_2"]])

    # child_3 tree
    object_dict["child_3_1"] = SimpleDataObject("child_3_1")
    object_dict["child_3"].insert_children(object_dict["child_3_1"])
    object_dict["child_3_1_1"] = SimpleDataObject("child_3_1_1")
    object_dict["child_3_1_2"] = SimpleDataObject("child_3_1_2")
    object_dict["child_3_1_2_same_name"] = SimpleDataObject("child_3_1_2")
    object_dict["child_3_1"].insert_children(
        [object_dict["child_3_1_1"], object_dict["child_3_1_2"],
    object_dict["child_3_1_2_same_name"]])

    # child_5 tree
    object_dict["child_5_1"] = SimpleDataObject("child_5_1")
    object_dict["child_5_2"] = SimpleDataObject("child_5_2")
    object_dict["child_5"].insert_children(
        [object_dict["child_5_1"], object_dict["child_5_2"]])
    object_dict["child_5_2_1"] = SimpleDataObject("child_5_2_1")
    object_dict["child_5_2_2"] = SimpleDataObject("child_5_2_2")
    object_dict["child_5_2_3"] = SimpleDataObject4("child_5_2_3")
    object_dict["child_5_2"].insert_children(
        [object_dict["child_5_2_1"], object_dict["child_5_2_2"],
         object_dict["child_5_2_3"]])

    object_dict["child_5_2_3_1"] = SimpleDataObject("child_5_2_3_1")
    object_dict["child_5_2_3_2"] = SimpleDataObject("child_5_2_3_2")
    object_dict["child_5_2_3_3"] = SimpleDataObject("child_5_2_3_3")
    object_dict["child_5_2_3_3_same_name"] = SimpleDataObject("child_5_2_3_3")
    object_dict["child_5_2_3"].insert_children(
        [object_dict["child_5_2_3_1"], object_dict["child_5_2_3_2"],
        object_dict["child_5_2_3_3"], object_dict["child_5_2_3_3_same_name"]])

    return object_dict

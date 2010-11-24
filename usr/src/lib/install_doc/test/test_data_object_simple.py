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
'''Tests to validate SimpleXmlHandlerBase functionality'''

import unittest

from lxml import etree

from solaris_install.data_object import \
    ParsingError
from solaris_install.data_object.simple import \
    SimpleXmlHandlerBase

from simple_data_object import SimpleDataObject


class SimpleXmlHandlerTag(SimpleXmlHandlerBase):
    '''Define class where we override TAG_NAME'''
    TAG_NAME = "simple_tag"


class SimpleXmlHandlerBadTag(SimpleXmlHandlerBase):
    '''Define class where we override TAG_NAME with a bad tag value'''
    TAG_NAME = "bad tag"


class  TestSimpleXmlHandlerBase(unittest.TestCase):
    '''Tests to validate SimpleXmlHandlerBase functionality'''

    def setUp(self):
        self.simple_tag_no_name = SimpleXmlHandlerTag()
        self.simple_tag_with_name = SimpleXmlHandlerTag('My Name')

    def tearDown(self):
        self.simple_tag_no_name = None
        self.simple_tag_with_name = None

    def test_data_object_simple_fail_not_subclass(self):
        '''Validate that direct instantaion of SimpleXmlHandlerBase will fail.
        '''
        self.assertRaises(ValueError, SimpleXmlHandlerBase)

    def test_data_object_simple_xml_valid_tag_no_name(self):
        '''Validate that XML is generated using a valid TAG_NAME and no name'''
        # Set expected xml, and compensate for indent
        expected_xml = '<simple_tag/>\n'

        xml_str = self.simple_tag_no_name.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_simple_xml_valid_tag_with_name(self):
        '''Validate that XML is generated using a valid TAG_NAME and name'''
        # Set expected xml, and compensate for indent
        expected_xml = '<simple_tag name="My Name"/>\n'

        xml_str = self.simple_tag_with_name.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_simple_fail_invalid_tag(self):
        '''Validate that XML generation fails using an invalid TAG_NAME'''
        try:
            data_obj = SimpleXmlHandlerBadTag()
            data_obj.to_xml()
            self.fail("Unexpected success creating obj with a bad tag name")
        except ValueError:
            pass

    def test_data_object_simple_fail_can_handle_invalid_tag(self):
        '''Validate that can_handle fails using an invalid tag name'''
        TEST_XML = '<bad_tag/>'

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        self.assertFalse(SimpleXmlHandlerBase.can_handle(xml_tree),
            "can_handle returned True when given a bad tag: %s" % (TEST_XML))

    def test_data_object_simple_fail_from_xml_invalid_tag(self):
        '''Validate that from_xml() fails using an invalid XML tag'''
        TEST_XML = '<bad_tag/>'

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        # can_handle tested seperately, just ensure from_xml will fail too.
        self.assertRaises(ParsingError,
            SimpleXmlHandlerTag.from_xml, xml_tree)

    def test_data_object_simple_import_xml_default(self):
        '''Validate that from_xml() correctly imports XML'''
        TEST_XML = '<simple_tag/>'

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if SimpleXmlHandlerTag.can_handle(xml_tree):
            new_obj = SimpleXmlHandlerTag.from_xml(xml_tree)
            self.assertTrue(new_obj is not None,
                "Failed to create SimpleXmlHandlerTag from XML")
            self.assertEquals(new_obj.name, SimpleXmlHandlerTag.TAG_NAME,
                "Created SimpleXmlHandlerTag has wrong name.")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_simple_import_xml_with_name(self):
        '''Validate that from_xml() correctly imports XML'''
        TEST_XML = '<simple_tag name="My Name"/>'

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if SimpleXmlHandlerTag.can_handle(xml_tree):
            new_obj = SimpleXmlHandlerTag.from_xml(xml_tree)
            self.assertTrue(new_obj is not None,
                "Failed to create SimpleXmlHandlerTag from XML")
            self.assertEquals(new_obj.name, "My Name",
                "Created SimpleXmlHandlerTag has wrong name.")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_simple_can_insert_to_doc(self):
        '''Validate SimpleXmlHandlerBase can be inserted as child of DataObject
        '''
        data_obj = SimpleDataObject("test_obj")
        data_obj.insert_children(SimpleXmlHandlerTag("test"))

if __name__ == '__main__':
    unittest.main()

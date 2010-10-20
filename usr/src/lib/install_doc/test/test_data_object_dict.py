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
'''Tests to validate DataObjectDict functionality'''

import unittest

from lxml import etree

from solaris_install.data_object.data_dict import \
    DataObjectDict, ParsingError

from simple_data_object import SimpleDataObject


class DataObjectDictDiffTag(DataObjectDict):
    '''Define class where we override TAG_NAME'''
    TAG_NAME = "different_tag"


class DataObjectDictDiffSubTag(DataObjectDict):
    '''Define class where we override SUB_TAG_NAME'''
    SUB_TAG_NAME = "different_sub_tag"


class DataObjectDictDiffBothTag(DataObjectDict):
    '''Define class where we override both TAG_NAME and SUB_TAG_NAME'''
    TAG_NAME = "different_both_tag"
    SUB_TAG_NAME = "different_both_sub_tag"


class DataObjectDictBadTag(DataObjectDict):
    '''Define class where we override TAG_NAME with a bad tag value'''
    TAG_NAME = "bad tag"


class DataObjectDictBadSubTag(DataObjectDict):
    '''Define class where we override SUB_TAG_NAME with a bad tag value'''
    SUB_TAG_NAME = "bad sub tag"


class  TestDataObjectDict(unittest.TestCase):
    '''Tests to validate DataObjectDict functionality'''

    def setUp(self):
        '''Create simple dictionary, and several objects using it'''
        tmp_dict = dict()
        tmp_dict["name1"] = "value1"
        tmp_dict["name2"] = "value2"
        tmp_dict["name3"] = "value3"
        tmp_dict["name4"] = "value4"
        tmp_dict["name5"] = "value5"

        self.data_dict_xml = DataObjectDict("test_dictionary_xml", tmp_dict,
            generate_xml=True)

        self.data_dict_no_xml = DataObjectDict("test_dictionary_no_xml",
            tmp_dict)

        self.data_dict_diff_tag = DataObjectDictDiffTag(
            "test_dictionary_diff_tag", tmp_dict, generate_xml=True)

        self.data_dict_diff_sub_tag = DataObjectDictDiffSubTag(
            "test_dictionary_diff_sub_tag", tmp_dict, generate_xml=True)

        self.data_dict_diff_both_tags = DataObjectDictDiffBothTag(
            "test_dictionary_diff_both_tags", tmp_dict,
            generate_xml=True)

        # Slightly different dictionary, add a key of 'name'.
        tmp_dict = dict()
        tmp_dict["name"] = "value"
        tmp_dict["name1"] = "value1"
        tmp_dict["name2"] = "value2"
        tmp_dict["name3"] = "value3"
        tmp_dict["name4"] = "value4"
        tmp_dict["name5"] = "value5"

        self.data_dict_attr = DataObjectDict("test_dictionary_attr", tmp_dict)

    def tearDown(self):
        '''Free up references to objects'''
        self.data_dict_xml = None
        self.data_dict_no_xml = None
        self.data_dict_diff_tag = None
        self.data_dict_diff_sub_tag = None
        self.data_dict_diff_both_tags = None

    def test_data_object_dict_no_xml(self):
        '''Validate that XML isn't generated if generate_xml=False'''
        self.assertTrue(self.data_dict_no_xml.get_xml_tree() == None,
            self.data_dict_no_xml.get_xml_tree_str())

    def test_data_object_dict_xml_default(self):
        '''Validate that XML is generated with default settings'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        expected_xml = '''\
        <data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </data_dictionary>
        '''.replace(indentation, "")

        xml_str = self.data_dict_xml.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_dict_value_using_attr(self):
        '''Validate that its possible to refer to a value as an attribute'''
        self.assertEqual(self.data_dict_attr.name1,
            self.data_dict_attr.data_dict["name1"])

        # Ensure that name returns _name, not value in dictionary.
        self.assertEqual(self.data_dict_attr.name,
            self.data_dict_attr._name)

    def test_data_object_dict_value_fail_using_attr(self):
        '''Validate that its not possible to refer to an invalid attribute'''
        try:
            self.data_dict_attr.name10
            self.fail("Didn't raise exception referring to invalid attribute")
        except AttributeError:
            pass

    def test_data_object_dict_xml_diff_tag(self):
        '''Validate that XML is generated using a different TAG_NAME'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        expected_xml = '''\
        <different_tag name="test_dictionary_diff_tag">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </different_tag>
        '''.replace(indentation, "")

        xml_str = self.data_dict_diff_tag.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_dict_xml_diff_sub_tag(self):
        '''Validate that XML is generated using a different SUB_TAG_NAME'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        expected_xml = '''\
        <data_dictionary name="test_dictionary_diff_sub_tag">
          <different_sub_tag name="name1">value1</different_sub_tag>
          <different_sub_tag name="name2">value2</different_sub_tag>
          <different_sub_tag name="name3">value3</different_sub_tag>
          <different_sub_tag name="name4">value4</different_sub_tag>
          <different_sub_tag name="name5">value5</different_sub_tag>
        </data_dictionary>
        '''.replace(indentation, "")

        xml_str = self.data_dict_diff_sub_tag.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_dict_xml_diff_both_tag(self):
        '''Validate that XML uses different TAG_NAME and SUB_TAG_NAME'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        expected_xml = '''\
        <different_both_tag name="test_dictionary_diff_both_tags">
          <different_both_sub_tag name="name1">value1</different_both_sub_tag>
          <different_both_sub_tag name="name2">value2</different_both_sub_tag>
          <different_both_sub_tag name="name3">value3</different_both_sub_tag>
          <different_both_sub_tag name="name4">value4</different_both_sub_tag>
          <different_both_sub_tag name="name5">value5</different_both_sub_tag>
        </different_both_tag>
        '''.replace(indentation, "")

        xml_str = self.data_dict_diff_both_tags.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml, "EXPECTED:\n%s\nGOT:\n%s" %\
            (expected_xml, xml_str))

    def test_data_object_dict_fail_not_dict(self):
        '''Validate failure if non-dict type passed for dictionary'''
        try:
            DataObjectDict("not_dict", data_dict=["elem1"])
            self.fail("Unexpected success creating obj with a list")
        except ValueError:
            pass

    def test_data_object_dict_set_dict_prop(self):
        '''Validate correct setting of data_dict property on creation'''
        obj = DataObjectDict("not_dict", data_dict=dict())
        obj.data_dict = {'key1': 'value1', 'key2': 'value2'}
        self.assertEqual(obj.data_dict['key1'], 'value1')
        self.assertEqual(obj.data_dict['key2'], 'value2')

    def test_data_object_dict_fail_not_dict_prop(self):
        '''Validate failure if non-dict passed as data_dict on creation'''
        try:
            obj = DataObjectDict("not_dict", data_dict=dict())
            obj.data_dict = list()
            self.fail("Unexpected success setting data_dict to a list")
        except ValueError:
            pass

    def test_data_object_dict_fail_invalid_tag(self):
        '''Validate that XML generation fails using an invalid TAG_NAME'''
        try:
            data_dict = {'key1': 'value1', 'key2': 'value2'}
            data_obj = DataObjectDictBadTag("invalid_tag", data_dict,
                generate_xml=True)
            data_obj.to_xml()
            self.fail("Unexpected success creating obj with a bad tag name")
        except ValueError:
            pass

    def test_data_object_dict_fail_invalid_sub_tag(self):
        '''Validate that XML generation fails using an invalid SUB_TAG_NAME'''
        try:
            data_dict = {'key1': 'value1', 'key2': 'value2'}
            data_obj = DataObjectDictBadSubTag("invalid_tag", data_dict,
                generate_xml=True)
            data_obj.to_xml()
            self.fail(
                "Unexpected success creating obj with a bad sub-tag name")
        except ValueError:
            pass

    def test_data_object_dict_fail_can_handle_invalid_tag(self):
        '''Validate that can_handle fails using an invalid tag name'''
        indentation = '''\
        '''
        TEST_XML = '''\
        <bad_data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </bad_data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        self.assertFalse(DataObjectDict.can_handle(xml_tree),
            "can_handle returned True when given a bad tag: %s" % (TEST_XML))

    def test_data_object_dict_fail_can_handle_invalid_sub_tag(self):
        '''Validate that can_handle fails using an invalid sub tag'''
        indentation = '''\
        '''
        TEST_XML = '''\
        <data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <baddata name="name4">value4</baddata>
          <data name="name5">value5</data>
        </data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        self.assertFalse(DataObjectDict.can_handle(xml_tree),
            "can_handle returned True when given a bad sub_tag: %s" %
            (TEST_XML))

    def test_data_object_dict_fail_from_xml_invalid_tag(self):
        '''Validate that from_xml() fails using an invalid XML tag'''
        indentation = '''\
        '''
        TEST_XML = '''\
        <bad_data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </bad_data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        # can_handle tested seperately, just ensure from_xml will fail too.
        self.assertRaises(ParsingError, DataObjectDict.from_xml, xml_tree)

    def test_data_object_dict_fail_from_xml_invalid_sub_tag(self):
        '''Validate that from_xml() fails using an invalid XML sub tag'''
        indentation = '''\
        '''
        TEST_XML = '''\
        <data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <baddata name="name4">value4</baddata>
          <data name="name5">value5</data>
        </data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        # can_handle tested seperately, just ensure from_xml will fail too.
        self.assertRaises(ParsingError, DataObjectDict.from_xml, xml_tree)

    def test_data_object_dict_set_generate_xml_prop(self):
        '''Validate that set/get of generate_xml flag works'''
        self.assertFalse(self.data_dict_no_xml.generate_xml)
        self.assertTrue(self.data_dict_no_xml.to_xml() == None)

        self.data_dict_no_xml.generate_xml = True
        self.assertTrue(self.data_dict_no_xml.generate_xml)
        self.assertTrue(self.data_dict_no_xml.to_xml() != None)

        self.data_dict_no_xml.generate_xml = False
        self.assertFalse(self.data_dict_no_xml.generate_xml)
        self.assertTrue(self.data_dict_no_xml.to_xml() == None)

    def test_data_object_dict_import_xml_default(self):
        '''Validate that from_xml() correctly imports XML'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        TEST_XML = '''\
        <data_dictionary name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if DataObjectDict.can_handle(xml_tree):
            new_obj = DataObjectDict.from_xml(xml_tree)
            self.assertTrue(new_obj != None,
                "Failed to create DataObjectDict from XML")
            self.assertEquals(type(new_obj.data_dict), dict,
                "new object's data_dict is not a data_dict.")
            self.assertEquals(new_obj.data_dict["name1"], "value1",
                "new object's name1 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name2"], "value2",
                "new object's name2 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name3"], "value3",
                "new object's name3 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name4"], "value4",
                "new object's name4 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name5"], "value5",
                "new object's name5 doesn't have correct value")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_dict_import_xml_diff_tag(self):
        '''Validate from_xml() imports correctly with diff tag'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        TEST_XML = '''\
        <different_tag name="test_dictionary_xml">
          <data name="name1">value1</data>
          <data name="name2">value2</data>
          <data name="name3">value3</data>
          <data name="name4">value4</data>
          <data name="name5">value5</data>
        </different_tag>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if DataObjectDictDiffTag.can_handle(xml_tree):
            new_obj = DataObjectDictDiffTag.from_xml(xml_tree)
            self.assertTrue(new_obj != None,
                "Failed to create DataObjectDict from XML")
            self.assertEquals(type(new_obj.data_dict), dict,
                "new object's data_dict is not a data_dict.")
            self.assertEquals(new_obj.data_dict["name1"], "value1",
                "new object's name1 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name2"], "value2",
                "new object's name2 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name3"], "value3",
                "new object's name3 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name4"], "value4",
                "new object's name4 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name5"], "value5",
                "new object's name5 doesn't have correct value")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_dict_import_xml_diff_sub_tag(self):
        '''Validate from_xml() imports correctly with diff sub tag'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        TEST_XML = '''\
        <data_dictionary name="test_dictionary_xml">
          <different_sub_tag name="name1">value1</different_sub_tag>
          <different_sub_tag name="name2">value2</different_sub_tag>
          <different_sub_tag name="name3">value3</different_sub_tag>
          <different_sub_tag name="name4">value4</different_sub_tag>
          <different_sub_tag name="name5">value5</different_sub_tag>
        </data_dictionary>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if DataObjectDictDiffSubTag.can_handle(xml_tree):
            new_obj = DataObjectDictDiffSubTag.from_xml(xml_tree)
            self.assertTrue(new_obj != None,
                "Failed to create DataObjectDict from XML")
            self.assertEquals(type(new_obj.data_dict), dict,
                "new object's data_dict is not a data_dict.")
            self.assertEquals(new_obj.data_dict["name1"], "value1",
                "new object's name1 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name2"], "value2",
                "new object's name2 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name3"], "value3",
                "new object's name3 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name4"], "value4",
                "new object's name4 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name5"], "value5",
                "new object's name5 doesn't have correct value")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_dict_import_xml_diff_both_tag(self):
        '''Validate from_xml() imports correctly with diff tag and sub-tag'''
        # Set expected xml, and compensate for indent
        indentation = '''\
        '''
        TEST_XML = '''\
        <different_both_tag name="test_dictionary_diff_both_tags">
          <different_both_sub_tag name="name1">value1</different_both_sub_tag>
          <different_both_sub_tag name="name2">value2</different_both_sub_tag>
          <different_both_sub_tag name="name3">value3</different_both_sub_tag>
          <different_both_sub_tag name="name4">value4</different_both_sub_tag>
          <different_both_sub_tag name="name5">value5</different_both_sub_tag>
        </different_both_tag>
        '''.replace(indentation, "")

        # Parse the XML into an XML tree.
        xml_tree = etree.fromstring(TEST_XML)

        if DataObjectDictDiffBothTag.can_handle(xml_tree):
            new_obj = DataObjectDictDiffBothTag.from_xml(xml_tree)
            self.assertTrue(new_obj != None,
                "Failed to create DataObjectDict from XML")
            self.assertEquals(type(new_obj.data_dict), dict,
                "new object's data_dict is not a data_dict.")
            self.assertEquals(new_obj.data_dict["name1"], "value1",
                "new object's name1 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name2"], "value2",
                "new object's name2 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name3"], "value3",
                "new object's name3 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name4"], "value4",
                "new object's name4 doesn't have correct value")
            self.assertEquals(new_obj.data_dict["name5"], "value5",
                "new object's name5 doesn't have correct value")
        else:
            self.fail("can_handle returned False, expected True!")

    def test_data_object_dict_can_insert_to_doc(self):
        '''Validate DataObjectDict can be inserted as child of DataObject'''
        data_obj = SimpleDataObject("test_obj")
        data_dict = {'key1': 'value1', 'key2': 'value2'}
        data_dict_obj = DataObjectDict("TestChild", data_dict)
        data_obj.insert_children(data_dict_obj)


if __name__ == '__main__':
    unittest.main()

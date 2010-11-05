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
'''Tests to validate DataObjectCache registration mechanism'''

import unittest

from lxml import etree

from solaris_install.data_object import DataObject
from solaris_install.data_object.cache import DataObjectCache
import solaris_install.data_object.cache as DOC
from simple_data_object import SimpleDataObject, SimpleDataObject2, \
    SimpleDataObject3, SimpleDataObject4
import simple_data_object

# Define two classes that both handle the same tag, but have
# different priorities.
COMMON_TAG = "common_tag"


class SimpleDataObjectSameTagNormPrio(DataObject):
    '''Define a simple data object that uses COMMON_TAG to use default prio'''

    @classmethod
    def can_handle(cls, xml_node):
        '''Can we handle XML node?'''
        if xml_node.tag == COMMON_TAG:
            return True

    @classmethod
    def from_xml(cls, xml_node):
        '''Return an instance of self if XML has correct tag'''
        if xml_node.tag == COMMON_TAG:
            SimpleDataObjectSameTagNormPrio(name=xml_node.attrib.get("name"))

        return None

    def to_xml(self):
        '''Generate XML using COMMON_TAG value'''
        element = etree.Element(COMMON_TAG, name=self.name)
        return element

    def __repr__(self):
        return "%s: name = %s" % (self.__class__.__name__, self.name)


class SimpleDataObjectSameTagHighPrio(SimpleDataObjectSameTagNormPrio):
    '''Define a similar class, but will be given a higher priority'''
    pass


class TestDataObjectCacheRegistration(unittest.TestCase):
    '''Tests to validate DataObjectCache registration mechanism'''

    def setUp(self):
        '''Create DOC reference, and ensure an empty class registry'''
        self.doc = DataObjectCache()

        # Hack to ensure that registry is empty before we use it,
        self.orig_registry = DOC._CACHE_CLASS_REGISTRY
        DOC._CACHE_CLASS_REGISTRY = dict()

    def tearDown(self):
        '''Cleanup DOC reference, but restore DOC's class registry when done'''
        self.doc.clear()
        self.doc = None

        # Hack to ensure that registry is restored after we use it.
        DOC._CACHE_CLASS_REGISTRY = self.orig_registry

    def test_doc_registration_simple_data_object(self):
        '''Validate registration and selection of a single class'''
        try:
            DataObjectCache.register_class(SimpleDataObject)
        except (TypeError, ValueError):
            self.fail("Failed to register SimpleDataObject!")

        # Test that it's actually registered and will correclty return class.
        simple = SimpleDataObject("TestSimple")
        xml_elem = simple.to_xml()
        class_obj = DataObjectCache.find_class_to_handle(xml_elem)
        self.assertEqual(class_obj, SimpleDataObject, str(class_obj))

    def test_doc_registration_simple_data_object_prio_30(self):
        '''Validate insertion of a class with prio 30'''
        try:
            DataObjectCache.register_class(SimpleDataObject, priority=30)
        except (TypeError, ValueError):
            self.fail("Failed to register SimpleDataObject with prio 30!")

    def test_doc_registration_simple_data_object_prio_0(self):
        '''Validate insertion of a class with prio 0'''
        try:
            DataObjectCache.register_class(SimpleDataObject, priority=0)
        except (TypeError, ValueError):
            self.fail("Failed to register SimpleDataObject with prio 0!")

    def test_doc_registration_simple_data_object_prio_100(self):
        '''Validate insertion of a class with prio 100'''
        try:
            DataObjectCache.register_class(SimpleDataObject, priority=100)
        except (TypeError, ValueError):
            self.fail("Failed to register SimpleDataObject with prio 100!")

    def test_doc_registration_simple_data_object_prio_minus_1(self):
        '''Validate insertion fails with a class with prio -1'''
        self.assertRaises(ValueError, DataObjectCache.register_class,
            SimpleDataObject, priority=-1)

    def test_doc_registration_simple_data_object_prio_101(self):
        '''Validate insertion fails with a class with prio 101'''
        self.assertRaises(ValueError, DataObjectCache.register_class,
            SimpleDataObject, priority=101)

    def test_doc_registration_non_data_object(self):
        '''Validate insertion fails with a non-DataObject sub-class'''
        self.assertRaises(TypeError, DataObjectCache.register_class,
            object)

    def test_doc_registration_get_registered_classes_str(self):
        '''Validate correct output from get_registered_classes_str()'''
        # Used as expected return string in method
        # Compensate for indent
        indentation = '''\
        '''
        expected_registered_classes_str = '''\
        ============================
        Registered Classes:
        [Priority = 30]
            <class 'simple_data_object.SimpleDataObject'>
        [Priority = 50]
            <class 'simple_data_object.SimpleDataObject2'>
            <class 'simple_data_object.SimpleDataObject3'>
        [Priority = 100]
            <class 'simple_data_object.SimpleDataObject4'>
        ============================
        '''.replace(indentation, "")

        DataObjectCache.register_class(SimpleDataObject, priority=30)
        DataObjectCache.register_class(SimpleDataObject2)
        DataObjectCache.register_class(SimpleDataObject3, priority=50)
        DataObjectCache.register_class(SimpleDataObject4, priority=100)

        txt = self.doc.get_registered_classes_str()

        self.assertEquals(expected_registered_classes_str, txt,
            "EXPECTED:\n%s\nGOT:\n%s\n" %
            (expected_registered_classes_str, txt))

    def test_doc_registration_classes_from_module_same_prio(self):
        '''Validate registration of classes in a module at same priority'''
        # Compensate for indent
        indentation = '''\
        '''
        expected_registered_classes_str = '''\
        ============================
        Registered Classes:
        [Priority = 30]
            <class 'simple_data_object.SimpleDataObject'>
            <class 'simple_data_object.SimpleDataObject2'>
            <class 'simple_data_object.SimpleDataObject3'>
            <class 'simple_data_object.SimpleDataObject4'>
            <class 'simple_data_object.SimpleDataObject5'>
            <class 'simple_data_object.SimpleDataObjectHandlesChildren'>
            <class 'simple_data_object.SimpleDataObjectNoXml'>
        ============================
        '''.replace(indentation, "")
        DataObjectCache.register_class(simple_data_object, priority=30)

        txt = self.doc.get_registered_classes_str()

        self.assertEquals(expected_registered_classes_str, txt,
            "EXPECTED:\n%s\nGOT:\n%s\n" %
            (expected_registered_classes_str, txt))

    def test_doc_registration_classes_from_module_in_list_same_prio(self):
        '''Validate registration of classes in a module list at same priority
        '''
        # Compensate for indent
        indentation = '''\
        '''
        expected_registered_classes_str = '''\
        ============================
        Registered Classes:
        [Priority = 30]
            <class 'simple_data_object.SimpleDataObject'>
            <class 'simple_data_object.SimpleDataObject2'>
            <class 'simple_data_object.SimpleDataObject3'>
            <class 'simple_data_object.SimpleDataObject4'>
            <class 'simple_data_object.SimpleDataObject5'>
            <class 'simple_data_object.SimpleDataObjectHandlesChildren'>
            <class 'simple_data_object.SimpleDataObjectNoXml'>
        ============================
        '''.replace(indentation, "")
        DataObjectCache.register_class([simple_data_object], priority=30)

        txt = self.doc.get_registered_classes_str()

        self.assertEquals(expected_registered_classes_str, txt,
            "EXPECTED:\n%s\nGOT:\n%s\n" %
            (expected_registered_classes_str, txt))

    def test_doc_registration_multiple_classes_same_prio(self):
        '''Validate registration of multiple classes at same priority'''
        # Compensate for indent
        indentation = '''\
        '''
        expected_registered_classes_str = '''\
        ============================
        Registered Classes:
        [Priority = 30]
            <class 'simple_data_object.SimpleDataObject'>
            <class 'simple_data_object.SimpleDataObject2'>
            <class 'simple_data_object.SimpleDataObject3'>
            <class 'simple_data_object.SimpleDataObject4'>
        ============================
        '''.replace(indentation, "")
        DataObjectCache.register_class(SimpleDataObject, priority=30)
        DataObjectCache.register_class(SimpleDataObject2, priority=30)
        DataObjectCache.register_class(SimpleDataObject3, priority=30)
        DataObjectCache.register_class(SimpleDataObject4, priority=30)

        txt = self.doc.get_registered_classes_str()

        self.assertEquals(expected_registered_classes_str, txt,
            "EXPECTED:\n%s\nGOT:\n%s\n" %
            (expected_registered_classes_str, txt))

    def test_doc_registration_multiple_handlers_highest_prio_selected(self):
        '''Validate highest priority class is selected when several handlers'''
        DataObjectCache.register_class(SimpleDataObjectSameTagHighPrio,
            priority=30)
        DataObjectCache.register_class(SimpleDataObjectSameTagNormPrio,
            priority=50)

        xml_elem = etree.Element(COMMON_TAG, name="some name")

        class_obj = DataObjectCache.find_class_to_handle(xml_elem)

        self.assertEqual(class_obj, SimpleDataObjectSameTagHighPrio)

    def test_doc_registration_no_handler_found(self):
        '''Validate failure of no handler is found'''
        DataObjectCache.register_class(SimpleDataObject)
        DataObjectCache.register_class(SimpleDataObject2)
        DataObjectCache.register_class(SimpleDataObject3)
        DataObjectCache.register_class(SimpleDataObject4)

        # First ensure it works as expected.
        xml_elem = etree.Element("SimpleDataObject", name="handled")

        class_obj = DataObjectCache.find_class_to_handle(xml_elem)

        self.assertEqual(class_obj, SimpleDataObject)

        # Now ensure that it fails when expected.
        xml_elem_fail = etree.Element("not_handled", name="not_handled_name")

        class_obj = DataObjectCache.find_class_to_handle(xml_elem_fail)

        self.assertEqual(class_obj, None)


if __name__ == '__main__':
    unittest.main()

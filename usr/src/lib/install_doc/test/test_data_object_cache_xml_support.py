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
'''Tests to test DOC XML specific methods'''

import unittest

from solaris_install.data_object.cache import DataObjectCache
import solaris_install.data_object.cache as DOC
from simple_data_object import SimpleDataObject, \
    SimpleDataObject2, SimpleDataObject3, SimpleDataObjectHandlesChildren


class  TestDataObjectCacheXmlSupport(unittest.TestCase):
    '''Tests to test DOC XML specific methods'''

    def setUp(self):
        '''Create DOC, and empty registry of classes, some children and refs'''

        # Hack to ensure that registry is empty before we use it,
        self.orig_registry = DOC._CACHE_CLASS_REGISTRY
        DOC._CACHE_CLASS_REGISTRY = dict()

        DataObjectCache.register_class([SimpleDataObject, SimpleDataObject2,
                SimpleDataObject3, SimpleDataObjectHandlesChildren])

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
        #        child_5_same_name

        # Create root node
        self.doc = DataObjectCache()

        # Create some persistent content
        self.persistent_root = SimpleDataObject("persistent_root")

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

        self.persistent_root.insert_children(self.do_list)

        self.doc.persistent.insert_children(self.persistent_root)

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
        self.child_2_1_1.insert_children([self.child_2_1_1_1,
            self.child_2_1_1_2])

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
        self.child_5_2.insert_children([self.child_5_2_1, self.child_5_2_2,
            self.child_5_2_3])

        self.child_5_2_3_1 = SimpleDataObject("child_5_2_3_1")
        self.child_5_2_3_2 = SimpleDataObject("child_5_2_3_2")
        self.child_5_2_3_3 = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3_3_same_name = SimpleDataObject("child_5_2_3_3")
        self.child_5_2_3.insert_children([self.child_5_2_3_1,
            self.child_5_2_3_2, self.child_5_2_3_3,
            self.child_5_2_3_3_same_name])

        # Create some volatile content, not much, just enough to test that it's
        # not overwritten on loading of snapshot.
        self.volatile_root = SimpleDataObject2("volatile_root")
        self.doc.volatile.insert_children(self.volatile_root)

    def tearDown(self):
        '''Restore class registry and clear DOC and other references'''

        # Hack to ensure that registry is restored after we use it.
        DOC._CACHE_CLASS_REGISTRY = self.orig_registry

        self.doc.clear()
        self.doc = None
        self.persistent_root = None
        self.volatile_root = None
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

    def test_data_object_cache_xml_support_skip_sub_tree_elements(self):
        '''Validate no XML generated by volatile and persistent'''

        # doc.volatile and doc.persistent shouldn't generate their own
        # XML, so ensure tha this is the case.
        xml_tree = self.doc.generate_xml_manifest()

        child_names = []
        for xml_child in xml_tree:
            child_names.append(xml_child.get("name"))

        self.assertEqual(child_names, \
            [self.persistent_root.name, self.volatile_root.name])

    def test_data_object_cache_xml_support_generates_expected_xml(self):
        '''Validate that expected XML is generated by generate_xml_manifest'''
        indentation = '''\
        '''
        expected_xml = '''\
        <root>
        ..<SimpleDataObject name="persistent_root">
        ....<SimpleDataObject2 name="child_1">
        ......<SimpleDataObject name="child_1_1"/>
        ......<SimpleDataObject name="child_1_2"/>
        ....</SimpleDataObject2>
        ....<SimpleDataObject name="child_2">
        ......<SimpleDataObject2 name="child_2_1">
        ........<SimpleDataObject2 name="child_2_1_1">
        ..........<SimpleDataObject2 name="child_2_1_1_1"/>
        ..........<SimpleDataObject2 name="child_2_1_1_2"/>
        ........</SimpleDataObject2>
        ......</SimpleDataObject2>
        ....</SimpleDataObject>
        ....<SimpleDataObject name="child_3">
        ......<SimpleDataObject name="child_3_1">
        ........<SimpleDataObject name="child_3_1_1"/>
        ........<SimpleDataObject name="child_3_1_2"/>
        ........<SimpleDataObject name="child_3_1_2"/>
        ......</SimpleDataObject>
        ....</SimpleDataObject>
        ....<SimpleDataObject2 name="child_4"/>
        ....<SimpleDataObject name="child_5_1"/>
        ....<SimpleDataObject name="child_5_2">
        ......<SimpleDataObject name="child_5_2_1"/>
        ......<SimpleDataObject name="child_5_2_2"/>
        ......<SimpleDataObjectHandlesChildren name="child_5_2_3">
        ........<so_child name="child_5_2_3_1"/>
        ........<so_child name="child_5_2_3_2"/>
        ........<so_child name="child_5_2_3_3"/>
        ........<so_child name="child_5_2_3_3"/>
        ......</SimpleDataObjectHandlesChildren>
        ....</SimpleDataObject>
        ..</SimpleDataObject>
        ..<SimpleDataObject2 name="volatile_root"/>
        </root>
        '''.replace(indentation, "").replace(".", " ")

        xml_str = self.doc.get_xml_tree_str()

        self.assertEqual(xml_str, expected_xml,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n%s\nEXPECTED:\n%s\n" %
            (len(xml_str), len(expected_xml), xml_str, expected_xml))

    def test_data_object_cache_xml_support_children_from_xml_volatile(self):
        '''Validate import_from_manifest_xml volatile flag'''
        # Get original XML tree
        orig_xml_tree = self.doc.generate_xml_manifest()
        orig_xml_str = self.doc.get_xml_tree_str()

        # Empty the DOC
        self.doc.clear()

        self.assertTrue(self.doc.is_empty)

        # Now, try to re-create DOC from oricinal XML
        self.doc.import_from_manifest_xml(orig_xml_tree, volatile=True)

        self.assertTrue(self.doc.volatile.has_children)
        self.assertFalse(self.doc.persistent.has_children)

        imported_xml_str = self.doc.get_xml_tree_str()

        self.assertEqual(imported_xml_str, orig_xml_str,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n%s\nEXPECTED:\n%s\n" %
            (len(imported_xml_str), len(orig_xml_str),
             imported_xml_str, orig_xml_str))

    def test_data_object_cache_xml_support_children_from_xml_persistent(self):
        '''Validate default XML import into persistent tree'''
        # Get original XML tree
        orig_xml_tree = self.doc.generate_xml_manifest()
        orig_xml_str = self.doc.get_xml_tree_str()

        # Empty the DOC
        self.doc.clear()

        self.assertTrue(self.doc.is_empty)

        # Now, try to re-create DOC from oricinal XML
        self.doc.import_from_manifest_xml(orig_xml_tree)

        # Ensure it's in the correct tree
        self.assertFalse(self.doc.volatile.has_children)
        self.assertTrue(self.doc.persistent.has_children)

        imported_xml_str = self.doc.get_xml_tree_str()

        self.assertEqual(imported_xml_str, orig_xml_str,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n%s\nEXPECTED:\n%s\n" %
            (len(imported_xml_str), len(orig_xml_str),
             imported_xml_str, orig_xml_str))

    def test_data_object_cache_xml_methods(self):
        '''Validate correct values returned from XML methods'''
        self.assertNotEqual(self.doc.to_xml(), None)
        self.assertEqual(self.doc.persistent.to_xml(), None)
        self.assertEqual(self.doc.volatile.to_xml(), None)

        self.assertFalse(self.doc.can_handle(None))
        self.assertFalse(self.doc.from_xml(None))

        self.assertFalse(self.doc.persistent.can_handle(None))
        self.assertFalse(self.doc.persistent.from_xml(None))

        self.assertFalse(self.doc.volatile.can_handle(None))
        self.assertFalse(self.doc.volatile.from_xml(None))


if __name__ == '__main__':
    unittest.main()

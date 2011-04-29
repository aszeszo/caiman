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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
Tests for mim set(), add() and get() methods.

Note: XML files created during the tests must conform to the DTD in the gate.
If the DTD changes, the XML files created need to change accordingly.
'''

import unittest
import os
import solaris_install.manifest_input.mim as mim
import solaris_install.manifest_input as milib

# Eventually bring names into convention.
# Ignore warnings of missing docstrings.
# pylint: disable-msg=C0111, C0103


class TestMIMSetAddGetCommon(unittest.TestCase):
    '''
    Tests for XML xpath-like path processing.
    '''

    # Must run gate init file (i.e. usr/src/tools/env/developer.sh)
    # to define ROOT first.  ROOT is the root of the gate's proto area.
    ROOT = os.environ.get("ROOT")

    MIM_TEST_XML_FILENAME = "/tmp/mim_test.xml"
    AIMANIFEST = ROOT + "/usr/bin/aimanifest"
    SCHEMA = ROOT + "/usr/share/install/ai.dtd"

    UNIQUE = True
    INCREMENTAL = True

    def setUp(self):
        os.environ["AIM_MANIFEST"] = self.MIM_TEST_XML_FILENAME

    def addset_and_check_node(self, mim_obj, command, path, value, is_unique):
        '''
        Add or set an element value or attribute, then verify it.

        Check pathname returned by add or set, and get.

        Args:
          mim_obj: ManifestInput module object

          command: "add" or "set"

          path: path to a unique place in the tree to add an element or attr

          value: value of element or attribute being added.

          is_unique:
          - Set to True if path passed in matches only one node.  If True,
            mim.get() will be called with the path passed in, and values
            compared.  If False, mim.get() is called with the path returned
            from add() or set().
        '''
        if command == "add":
            func = mim_obj.add
        elif command == "set":
            func = mim_obj.set
        ret_addset_path = func(path, value)

        # if is_unique, then can compare pathname returned by add() and get()
        # as well as the values returned.
        if is_unique:
            ret_value, ret_get_path = mim_obj.get(path)
            self.assertEquals(ret_value, value,
                "get() of value add()ed or set does not match")
            self.assertEquals(ret_get_path, ret_addset_path,
                "add/set and get of the same element " +
                "returned different pathnames")
        else:
            # retrieve only value via returned (unique) pathname and compare.
            ret_value, ret_get_path = mim_obj.get(ret_addset_path)
            self.assertEquals(ret_value, value,
                "get() of value add()ed or set does not match")

    def add_and_check_node(self, mim_obj, path, value, is_unique):
        self.addset_and_check_node(mim_obj, "add", path, value, is_unique)

    def set_and_check_node(self, mim_obj, path, value, is_unique):
        self.addset_and_check_node(mim_obj, "set", path, value, is_unique)


class TestSagA(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_sag_1(self):
        '''
        Add first set of nodes.  Specify attribute value for leaf node
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.add_and_check_node(mim_obj, "/auto_install/ai_instance/target/" +
                           "disk/disk_name@name",
                           "disk1", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagB(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software>\n')
            test_xml.write('    </software>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_2(self):
        '''
        Attempt to add a second tree root node (error)
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        # Generates "Cannot add a second tree root node"
        self.assertRaises(milib.MimInvalidError, mim_obj.add,
            "/auto_install@rootattr", "rootattrval")
        mim_obj.commit(validate=False)


class TestSagC(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software name="sw1"/>\n')
            test_xml.write('    <software name="sw2"/>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_3(self):
        '''
        Attempt to set an attribute when path is not deterministic (error)
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        # Generates "Ambiguity error:  Path matches more than one element"
        self.assertRaises(milib.MimMatchError, mim_obj.set,
                          "/auto_install/ai_instance/software@type/", "IPS")
        mim_obj.commit(validate=False)


class TestSagD(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software name="sw1"/>\n')
            test_xml.write('    <software name="sw2"/>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_4(self):
        '''
        Set attribute to a node that is unambiguously determined
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/"
                                "software[@name=\"sw1\"]@type",
                                "IPS", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagE(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software name="sw1"/>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_5(self):
        '''
        Set same attribute again, but to a different value.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/"
                                "software@name", "newname1", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagF(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software/>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_6(self):
        '''
        Set a value to a node that doesn't exist. (error)
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        # Generates "Error:  Path matches no elements"
        self.assertRaises(milib.MimMatchError, mim_obj.set,
                          "/auto_install/ai_instance/software/software_data",
                          "ghostly")
        mim_obj.commit(validate=False)


class TestSagG(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <software/>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_7(self):
        '''
        Set an attribute value in a node that doesn't exist yet. (error)
        '''
        # Generates "Error:  Path matches no elements"

        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.assertRaises(milib.MimMatchError, mim_obj.set,
                          "/auto_install/ai_instance/software/"
                          "software_data@action", "install")
        mim_obj.commit(validate=False)


class TestSagH(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('          <disk_name name="disk1"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('          <disk_name name="disk2"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_8(self):
        '''
        Add an element using a subpath.

        This is to distinguish it from other existing possible parent nodes.
        '''

        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.add_and_check_node(mim_obj, "/auto_install/ai_instance/target/" +
                                "disk[disk_name@name=\"disk2\"]/slice",
                                "theslice", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagI(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('          <disk_name name="disk1"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('          <disk_name name="disk2"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_9(self):
        '''
        Set a new attribute in an element specified with a subpath.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/target/" +
                                "disk[disk_name@name=\"disk2\"]/" +
                                "disk_name@newattr",
                                "hard", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagJ(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('          <disk_name name="disk2"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_10(self):
        '''
        Change existing attribute's value.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/target/" +
                                "disk@name", "disk3",
                                self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagK(TestMIMSetAddGetCommon):
    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>ai_instance_val</ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_11(self):
        '''
        Change value of an existing element.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.set_and_check_node(mim_obj, "/auto_install/ai_instance",
                                "newval", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagL(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_sag_12(self):
        '''
        Add an element but don't specify an attribute's value.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimInvalidError, mim_obj.add,
                          "/auto_install/ai_instance/target/" +
                          "disk/disk_name@name",
                          value=None)
        self.assertRaises(milib.MimEmptyTreeError, mim_obj.commit)


class TestSagM(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_sag_13(self):
        '''
        Add an element but don't specify a value for it.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimInvalidError, mim_obj.add,
                          "/auto_install/ai_instance/target/" +
                          "disk/disk_name",
                          value=None)
        self.assertRaises(milib.MimEmptyTreeError, mim_obj.commit)


class TestSagN(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_sag_14(self):
        '''
        Add two sibling elements with the same tag, where it is allowed.
        '''
        # <software> is the first node in the path which can have same-tagged
        # elements per the DTD.
        # Note: values in <software> are not normally given, but doing so
        # doesn't alter functionality, and they are needed for this test.

        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.add_and_check_node(mim_obj, "/auto_install/ai_instance/software/",
                                "software1", self.UNIQUE)
        self.add_and_check_node(mim_obj, "/auto_install/ai_instance/software/",
                                "software2", not self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagO(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('        <disk>disk1</disk>\n')
            test_xml.write('        <disk>disk2</disk>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('            <disk_name name="c0t0d0s0"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('        <disk>\n')
            test_xml.write('            <disk_name name="c0t1d0s0"/>\n')
            test_xml.write('        </disk>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_15(self):
        '''
        Specify ambiguous element path to get().
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimMatchError, mim_obj.get,
                          "/auto_install/ai_instance/target/disk/")
        mim_obj.commit(validate=False)

    def test_sag_16(self):
        '''
        Try to set an element value but specify an ambiguity in mid path
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimMatchError, mim_obj.set,
                          "/auto_install/ai_instance/"
                          "target/disk", "disk3")
        mim_obj.commit(validate=False)

    def test_sag_17(self):
        '''
        Set same attr in sibling elements with same tag, using different values
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/"
                                "target/disk[.=\"disk1\"]@in_zpool",
                                "pool1", self.UNIQUE)
        self.set_and_check_node(mim_obj, "/auto_install/ai_instance/"
                                "target/disk[.=\"disk2\"]@in_zpool",
                                "pool2", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagP(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('      <disk in_zpool="pool1"/>\n')
            test_xml.write('      <disk in_zpool="pool2"/>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_18(self):
        '''
        Specify ambiguous attribute path to get().
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.assertRaises(milib.MimMatchError, mim_obj.get,
                          "/auto_install/ai_instance/target/disk@in_zpool")
        mim_obj.commit(validate=False)


class TestSagQ(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_sag_19(self):
        '''
        Set new values, using identifier paths returned from previous adds.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        path1 = mim_obj.add("/auto_install/ai_instance/software@name",
                             "swname1")
        path2 = mim_obj.add("/auto_install/ai_instance/software@name",
                             "swname2")
        self.set_and_check_node(mim_obj, path1, "newsw1name", self.UNIQUE)
        self.set_and_check_node(mim_obj, path2, "newsw2name", self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagR(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <add_drivers>\n')
            test_xml.write('      <search_all/>\n')
            test_xml.write('    </add_drivers>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_20(self):
        '''
        Try to add a like-tagged element where such elements are not allowed.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)

        self.assertRaises(milib.MimInvalidError, mim_obj.add,
                          "/auto_install/ai_instance/add_drivers/search_all",
                          "true")
        mim_obj.commit(validate=False)


class TestSagS(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance>\n')
            test_xml.write('    <target>\n')
            test_xml.write('    <disk>disk1</disk>\n')
            test_xml.write('    <disk>disk2</disk>\n')
            test_xml.write('    </target>\n')
            test_xml.write('  </ai_instance>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_21(self):
        '''
        Add element where the parent would have to be created.
        (non-simple path)  Value not in quotes.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.add_and_check_node(mim_obj,
                                "/auto_install/ai_instance/target/"
                                "disk=disk1/disk_name@name", "c0t0d0s0",
                                self.UNIQUE)
        mim_obj.commit(validate=False)

    def test_sag_22(self):
        '''
        Add element where the parent would have to be created.
        (non-simple path)  Value in quotes.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.add_and_check_node(mim_obj,
                                "/auto_install/ai_instance/target/"
                                "disk=\"disk1\"/disk_name@name", "c0t0d0s0",
                                self.UNIQUE)
        mim_obj.commit(validate=False)


class TestSagT(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:
            test_xml.write('<auto_install>\n')
            test_xml.write('  <ai_instance/>\n')
            test_xml.write('</auto_install>\n')

    def test_sag_23(self):
        '''
        Try to get an element that doesn't exist.
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimMatchError, mim_obj.get,
                          "/auto_install/ai_instance/target")
        mim_obj.commit(validate=False)

    def test_sag_24(self):
        '''
        Try to get a missing attribute from an element that exists
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimMatchError, mim_obj.get,
                          "/auto_install/ai_instance@name")
        mim_obj.commit(validate=False)

    def test_sag_25(self):
        '''
        Try to get an attribute from a missing element
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimMatchError, mim_obj.get,
                          "/auto_install/ai_instance/software@name")
        mim_obj.commit(validate=False)

    def test_sag_26(self):
        '''
        Try to create a like-tagged leaf element where not allowed
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimInvalidError, mim_obj.add,
                          "/auto_install/ai_instance", "second")
        mim_obj.commit(validate=False)


class TestSagU(TestMIMSetAddGetCommon):

    def setUp(self):
        TestMIMSetAddGetCommon.setUp(self)
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)
        test_xml = open(self.MIM_TEST_XML_FILENAME, "w")
        test_xml.close()

    def test_sag_26(self):
        '''
        Create an empty tree, so that commit can raise an exception.
        (The commit is done in tearDown)
        '''
        mim_obj = mim.ManifestInput(self.MIM_TEST_XML_FILENAME, self.SCHEMA)
        self.assertRaises(milib.MimEmptyTreeError, mim_obj.commit)

if __name__ == "__main__":
    unittest.main()

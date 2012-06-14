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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''
Tests of Manifest Input Module overlay() functionality.
'''

import os
import tempfile
import unittest

import solaris_install.manifest_input as milib

from lxml import etree
from solaris_install import Popen, SYS_AI_MANIFEST_DTD
from solaris_install.manifest_input.mim import ManifestInput

# Note: Some python strings split across lines have a "+" at the end of their
# non-final lines. To the python interpreter these are superfluous, but the
# unit test framework looks at them to know the length of the full message
# string to print.  Please do not delete them.


class TestMIMOverlayCommon(unittest.TestCase):
    '''
    Common setup for Overlay testing.
    '''

    # Provided files.
    ROOT = os.environ["ROOT"]
    BASE_MANIFEST = ROOT + "/usr/share/auto_install/manifest/ai_manifest.xml"
    SCHEMA = ROOT + SYS_AI_MANIFEST_DTD

    # Created files.
    AIM_MANIFEST_FILE = "/tmp/mim_test.xml"
    MAIN_XML_FILE = "/tmp/test_main.xml"
    OVERLAY_XML_FILE = "/tmp/test_overlay.xml"

    # More descriptive arg name to pass to boolean "incremental" argument.
    OVERLAY = True

    def setUp(self):
        '''
        Specify where the manifest will be built.  Start with no data.
        '''
        os.environ["AIM_MANIFEST"] = self.AIM_MANIFEST_FILE

    def tearDown(self):
        '''
        Remove files created during testing.
        '''
        if os.path.exists(self.AIM_MANIFEST_FILE):
            os.unlink(self.AIM_MANIFEST_FILE)

    # More descriptive arg name to pass to method below "with_software" arg.
    WITH_SOFTWARE = True

    def create_starting_file(self, with_software=False):
        '''
        Create an XML file most tests start with.
        '''
        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            if with_software:
                main_xml.write('    <software/>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

    def destroy_starting_file(self):
        '''
        Destroy file created by create_starting_file().
        '''
        if os.path.exists(self.MAIN_XML_FILE):
            os.unlink(self.MAIN_XML_FILE)


class TestOverlayA(TestMIMOverlayCommon):
    '''
    Break a manifest apart and piece it together using overlay functionality.

    This class orchestrates a test whereby a proper manifest (BASE_MANIFEST)
    which (is assumed to) contain <target>, <software> and <configuration>
    is split into three sections, each containing one section, and
    overlay is used to put the sections back together into a viable manifest
    again.
    '''

    # BASE_MANIFEST as written out by the XML parser.
    FULL_XML = "/tmp/test_full.xml"

    # Names of the XML files which hold one section apiece.
    TARGET_XML = "/tmp/test_target.xml"
    SOFTWARE_XML = "/tmp/test_software.xml"
    CONFIG_XML = "/tmp/test_config.xml"

    # Paths to roots of each of the three sections.
    TARGET_SUBTREE = "/auto_install/ai_instance/target"
    SOFTWARE_SUBTREE = "/auto_install/ai_instance/software"
    CONFIG_SUBTREE = "/auto_install/ai_instance/configuration"

    # Diff command.
    DIFF = "/usr/bin/diff"

    def prune(self, subtree):
        '''
        Prune the part of the main tree given by the subtree argument.
        '''
        for tag in self.tree.xpath(subtree):
            tag.getparent().remove(tag)

    @staticmethod
    def strip_blank_lines(filename):
        '''
        Get rid of all lines in a file, which have only white space in them.
        '''
        outfile_fd, temp_file_name = tempfile.mkstemp(text=True)
        outfile = os.fdopen(outfile_fd, 'w')
        with open(filename, 'r') as infile:
            for line in infile:
                if not line.strip():
                    continue
                outfile.write(line)
        outfile.close()
        os.rename(temp_file_name, filename)

    def setUp(self):
        TestMIMOverlayCommon.setUp(self)

        # Assume the manifest used has separate sibling sections for
        # configuration, software and sc_embedded_manifest, and no others.
        # Create three files, each with one of the sections.

        # Read in base manifest, and write it out, stripping whitespace lines.
        parser = etree.XMLParser(remove_comments=True)
        self.tree = etree.parse(self.BASE_MANIFEST, parser)
        self.tree.write(self.FULL_XML, pretty_print=True)
        TestOverlayA.strip_blank_lines(self.FULL_XML)

        # Generate the three files with subsections.
        self.prune(self.SOFTWARE_SUBTREE)
        self.tree.write(self.TARGET_XML, pretty_print=True)

        self.tree = etree.parse(self.BASE_MANIFEST, parser)
        self.prune(self.TARGET_SUBTREE)
        self.tree.write(self.SOFTWARE_XML, pretty_print=True)

    def tearDown(self):
        '''
        Remove files created during testing.
        '''
        TestMIMOverlayCommon.tearDown(self)
        if os.path.exists(self.FULL_XML):
            os.unlink(self.FULL_XML)
        if os.path.exists(self.TARGET_XML):
            os.unlink(self.TARGET_XML)
        if os.path.exists(self.SOFTWARE_XML):
            os.unlink(self.SOFTWARE_XML)

    def test_overlay_1(self):
        '''
        Put original manifest together from pieces, and verify it.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE)
        mim.load(self.SOFTWARE_XML, not self.OVERLAY)
        mim.load(self.TARGET_XML, self.OVERLAY)
        mim.commit()
        TestOverlayA.strip_blank_lines(self.AIM_MANIFEST_FILE)

        # Raises an exception if diff command finds differences from original.
        Popen.check_call([self.DIFF, self.FULL_XML, self.AIM_MANIFEST_FILE])


class TestOverlayBCommon(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create an overlay file.
        '''
        TestMIMOverlayCommon.setUp(self)

        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance name="secondname">\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):

        TestMIMOverlayCommon.tearDown(self)

        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def do_test(self):
        '''
        Load main, then overlay and test.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)
        (value, path) = mim.get("/auto_install/ai_instance@name")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]",
                          "Error: incorrect pathname returned when getting " +
                          "\"name\" attribute")
        self.assertEquals(value, "secondname",
                          "Error changing existing attribute " +
                          "of non-leaf node.")


class TestOverlay2(TestOverlayBCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestOverlayBCommon.setUp(self)
        self.create_starting_file(self.WITH_SOFTWARE)

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestOverlayBCommon.tearDown(self)
        self.destroy_starting_file()

    def test_overlay_2(self):
        '''
        Change an attribute of an existing non-leaf element.
        '''
        self.do_test()


class TestOverlay3(TestOverlayBCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestOverlayBCommon.setUp(self)
        self.create_starting_file()

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestOverlayBCommon.tearDown(self)
        self.destroy_starting_file()

    def test_overlay_3(self):
        '''
        Change an attribute of an existing non-leaf element.
        '''
        self.do_test()


class TestOverlay4(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestMIMOverlayCommon.setUp(self)
        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance auto_reboot="true"/>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_4(self):
        '''
        Leaf overlayed where same-tagged elements not allowed

        ... replaces existing element and any subtree from it.
        '''

        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        # Verify the old element with name attribute is gone.
        self.assertRaises(milib.MimMatchError, mim.get,
            "/auto_install/ai_instance@name")

        # Verify the new element with auto_reboot attribute is present.
        (value, path) = mim.get("/auto_install/ai_instance@auto_reboot")
        self.assertEquals(value, "true",
            "Error adding new element with new attribute")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]",
                          "Error: incorrect pathname returned when getting " +
                          "\"auto_reboot\" attribute")


class TestOverlay5(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance auto_reboot="true">\n')
            ovrl_xml.write('    <software>\n')
            ovrl_xml.write('    </software>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_5(self):
        '''
        Overlay same-tagged non-leaf element with new attr where not allowed.

        Same-tagged non-leaf elements are not allowed.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        # Verify auto_reboot attribute was added to existing element.
        (value, path) = mim.get("/auto_install/ai_instance@name")
        self.assertEquals(value, "firstname",
                          "Error finding original attribute of existing node")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]",
                          "Error: incorrect pathname returned when getting" +
                          "\"name\" attr")

        (value, path) = mim.get("/auto_install/ai_instance@auto_reboot")
        self.assertEquals(value, "true",
                          "Error adding new attribute to existing node")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]",
                          "Error: incorrect pathname returned when getting " +
                          "\"auto_reboot\" attr")


class TestOverlay6(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestMIMOverlayCommon.setUp(self)

        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <bogus/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_6(self):
        '''
        Try to overlay a leaf element (id by value) where it does not belong.

        Give element a value to identify it.
        '''
        # Note: giving a bogus attribute is not checked, only a bogus element.

        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        self.assertRaises(milib.MimInvalidError, mim.load,
            self.OVERLAY_XML_FILE, self.OVERLAY)


class TestOverlay7(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestMIMOverlayCommon.setUp(self)

        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <bogus bogusattr="junk"/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_7(self):
        '''
        Try to overlay a leaf element (id by attr) where it does not belong.

        Give element an attribute to identify it.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        self.assertRaises(milib.MimInvalidError, mim.load,
            self.OVERLAY_XML_FILE, self.OVERLAY)


class TestOverlay8(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestMIMOverlayCommon.setUp(self)

        self.create_starting_file(self.WITH_SOFTWARE)

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <software>\n')
            ovrl_xml.write('      <software_data action="install"/>\n')
            ovrl_xml.write('    </software>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_8(self):
        '''
        Add a new non-leaf element where same-tagged elements are allowed.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        (value, path) = mim.get("/auto_install/ai_instance/"
                                "software/software_data@action")
        self.assertEquals(value, "install",
                          "Error adding new same-tagged element")

        # Target[2] means a second element was (properly) added.
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]/software[2]" +
                          "/software_data[1]",
                          "Error: incorrect pathname returned when getting " +
                          "\"action\" attr.")


class TestOverlay9(TestMIMOverlayCommon):

    def setUp(self):
        '''
        Create needed files.
        '''
        TestMIMOverlayCommon.setUp(self)

        self.create_starting_file()

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <software/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_9(self):
        '''
        Add new leaf elem where same-tagged elements are allowed and none exist
        '''
        self.mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        self.mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        self.mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        # Software[1] means a first software element was (properly) added.
        (value, path) = self.mim.get("/auto_install/ai_instance/software")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]/software[1]",
                          "Error adding leaf element where like-tagged " +
                          "elements are allowed.")


class TestOverlay10(TestOverlay9):

    def test_overlay_10(self):
        '''
        Check path to second same-tagged element.
        '''
        self.test_overlay_9()
        self.mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        # software[2] means a second software element was (properly) added.
        (value, path) = self.mim.get("/auto_install/ai_instance/software[2]")
        self.assertEquals(path, "/auto_install[1]/ai_instance[1]/software[2]",
                          "Error adding second like-tagged leaf element.")


class TestOverlayInsertionOrderCommon(TestMIMOverlayCommon):
    '''
    Common code for checking order of sibling elements.
    '''
    def check_insertion_order(self):
        '''
        Verify that target, sofware, configuration nodes exist and in order
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)
        ai_instance_node = mim._xpath_search("/auto_install[1]/ai_instance[1]")
        found_target = found_software = found_config = False
        for child in ai_instance_node[0]:
            if child.tag == "target":
                self.assertTrue(not found_software and not found_config,
                                "Target element not added before software " +
                                "or configuration elements")
                found_target = True
                continue
            if child.tag == "software":
                self.assertTrue(found_target and not found_config,
                                "Software element not added between target " +
                                "and configuration elements")
                found_software = True
                continue
            if child.tag == "configuration":
                self.assertTrue(found_target and found_software,
                                "Configuration element not added after "
                                "target and software elements")
                return
        self.assertTrue(found_target, "Target element not added")
        self.assertTrue(found_software, "Software element not added")
        self.assertTrue(found_config, "Configuration element not added")


class TestOverlay11(TestOverlayInsertionOrderCommon):
    ''' add element where element belongs between two existing elements.'''

    def setUp(self):
        TestOverlayInsertionOrderCommon.setUp(self)

        # Set up initial file with <target> and <configuration> sections.  DTD
        # specifies that <software> goes between <target> and <configuration>.
        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            main_xml.write('    <target/>\n')
            main_xml.write('    <configuration source="abc" name="def"/>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <software/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestOverlayInsertionOrderCommon.tearDown(self)

        if os.path.exists(self.MAIN_XML_FILE):
            os.unlink(self.MAIN_XML_FILE)
        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_11(self):
        '''
        Verify that software section went between target and configuration.
        '''
        self.check_insertion_order()


class TestOverlay12(TestOverlayInsertionOrderCommon):
    '''
    Add element where element belongs before existing elements.
    '''

    def setUp(self):
        TestOverlayInsertionOrderCommon.setUp(self)

        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            main_xml.write('    <software/>\n')
            main_xml.write('    <configuration source="abc" name="def"/>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

        # Set up overlay file with <target> that goes before <software> and
        # <configuration>
        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <target/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestOverlayInsertionOrderCommon.tearDown(self)

        if os.path.exists(self.MAIN_XML_FILE):
            os.unlink(self.MAIN_XML_FILE)
        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_12(self):
        '''
        Verify that target section went before software and configuration.
        '''
        self.check_insertion_order()


class TestOverlay13(TestOverlayInsertionOrderCommon):
    '''
    Add element where element belongs after all existing elements.
    '''

    def setUp(self):
        TestOverlayInsertionOrderCommon.setUp(self)

        # Set up initial file with <target> and <configuration> sections.  DTD
        # specifies that <configuration> goes after <target> and <software>.
        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            main_xml.write('    <target/>\n')
            main_xml.write('    <software/>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <configuration source="abc" name="def"/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestOverlayInsertionOrderCommon.tearDown(self)

        if os.path.exists(self.MAIN_XML_FILE):
            os.unlink(self.MAIN_XML_FILE)
        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_13(self):
        '''
        Verify that configuration section went after target and software.
        '''
        self.check_insertion_order()


class TestOverlay14(TestMIMOverlayCommon):
    '''
    Place element which normally goes after an element that is not present.

    Like above, but <software> node is missing.  Tests that <configuration>
    gets added after <target>.
    '''

    def setUp(self):
        TestMIMOverlayCommon.setUp(self)

        # Set up initial file with <target> and <configuration> sections.  DTD
        # specifies that <software> goes between <target> and <configuration>.
        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            main_xml.write('    <target/>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <configuration source="abc" name="def"/>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)

        if os.path.exists(self.MAIN_XML_FILE):
            os.unlink(self.MAIN_XML_FILE)
        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_14(self):
        '''
        Verify that configuration goes after target.

        Normally it would go after software, but software is missing and
        software comes after target.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)
        ai_instance_node = mim._xpath_search("/auto_install[1]/ai_instance[1]")
        found_target = found_config = False
        for child in ai_instance_node[0]:
            if child.tag == "target":
                self.assertTrue(not found_config,
                                "Target element not added before software " +
                                "or configuration elements")
                found_target = True
                continue
            if child.tag == "configuration":
                self.assertTrue(found_target,
                                "Configuration element not added after "
                                "target and software elements")
                return
        self.assertTrue(found_target, "Target element not added")
        self.assertTrue(found_config, "Configure element not added")


class TestOverlay15(TestMIMOverlayCommon):
    '''
    Add element where another element with same tag already exists.

    Start with a tree with target, software and source.  Add another tree also
    with target, software and source.  Are all target nodes, software nodes and
    source nodes together?
    '''

    def setUp(self):
        TestMIMOverlayCommon.setUp(self)

        # Set up initial file with <target> and <configuration> sections.  DTD
        # specifies that <software> goes between <target> and <configuration>.
        with open(self.MAIN_XML_FILE, "w") as main_xml:
            main_xml.write('<auto_install>\n')
            main_xml.write('  <ai_instance name="firstname">\n')
            main_xml.write('    <target>target1</target>\n')
            main_xml.write('    <software>software1</software>\n')
            main_xml.write('    <source>source1</source>\n')
            main_xml.write('  </ai_instance>\n')
            main_xml.write('</auto_install>\n')

        with open(self.OVERLAY_XML_FILE, "w") as ovrl_xml:
            ovrl_xml.write('<auto_install>\n')
            ovrl_xml.write('  <ai_instance>\n')
            ovrl_xml.write('    <target>target2</target>\n')
            ovrl_xml.write('    <software>software2</software>\n')
            ovrl_xml.write('    <source>source2</source>\n')
            ovrl_xml.write('  </ai_instance>\n')
            ovrl_xml.write('</auto_install>\n')

    def tearDown(self):
        '''
        Destroy files created for these tests.
        '''
        TestMIMOverlayCommon.tearDown(self)
        self.destroy_starting_file()

        if os.path.exists(self.OVERLAY_XML_FILE):
            os.unlink(self.OVERLAY_XML_FILE)

    def test_overlay_15(self):
        '''
        Interleaves two files with same nodes.  Verifies order.
        '''
        values_order = ["target2", "software1", "software2",
                         "source1", "source2"]

        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.MAIN_XML_FILE, not self.OVERLAY)
        mim.load(self.OVERLAY_XML_FILE, self.OVERLAY)

        ai_instance_node = mim._xpath_search("/auto_install[1]/ai_instance[1]")
        values_order_index = 0
        for child in ai_instance_node[0]:
            self.assertEquals(child.text, values_order[values_order_index],
                ("Child \"%s\" is out of order.  " +
                "Found \"%s\" in its place at index %d.\n") %
                (child.tag, values_order[values_order_index],
                values_order_index))
            values_order_index += 1
        self.assertEquals(values_order_index, len(values_order),
            "Only %d of %d were found.\n" % (values_order_index,
            len(values_order)))

if __name__ == "__main__":
    unittest.main()

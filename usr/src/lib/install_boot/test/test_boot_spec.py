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

"""boot_spec Unit Tests"""

import unittest

from lxml import etree

from solaris_install.boot.boot_spec import BootMods, BootEntry
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine


indentation = '''\
    '''


class TestBootMods(unittest.TestCase):
    """ Test case to test the from_xml() method of
        BootMods
    """

    BOOT_MODS_XML = '''
    <root>
    <boot_mods timeout="20" title="Boot Testing"/>
    </root>'''

    BOOT_MODS_NOTITLE_XML = '''
    <root>
    <boot_mods timeout="20"/>
    </root>'''

    BOOT_MODS_NOTIMEOUT_XML = '''
    <root>
    <boot_mods title="Boot Testing"/>
    </root>'''

    def setUp(self):
        """ Initialises a runtime environment for execution of
            BootMods and BootMods unit tests.
        """
        self.engine = get_new_engine_instance()

    def tearDown(self):
        """ Cleans up after the previous unit test execution.
        """
        if self.engine is not None:
            reset_engine(self.engine)
        self.doc = None
        self.boot_mods = None

    def _run_manifest_parser(self, test_xml, expected_xml):
        """ Support method to import manifest XML into the DOC and extract it
            back out. Compares the two and raises and assertEqual exception if
            they do not match.
            Inputs:
            - text_xml: The xml string representation imported into the DOC
            - expected_xml: The xml representation out from the DOC
        """
        self.doc = InstallEngine.get_instance().data_object_cache
        boot_mods_dom = etree.fromstring(test_xml)
        self.doc.import_from_manifest_xml(boot_mods_dom, volatile=True)

        boot_mods = self.doc.volatile.get_first_child(class_type=BootMods)
        xml_str = boot_mods.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n'%s'\nEXPECTED:\n'%s'\n" %
            (len(xml_str), len(expected_xml), xml_str, expected_xml))

    def test_manifest_xml(self):
        """ Tests the from_xml() and to_xml() methods of BootMods with
            both timeout and title specfied.
        """
        expected_xml = '''\
        <boot_mods title="Boot Testing" timeout="20"/>
        '''.replace(indentation, "")

        self._run_manifest_parser(self.BOOT_MODS_XML, expected_xml)

    def test_manifest_notitle_xml(self):
        """ Tests the from_xml() and to_xml() methods of BootMods with
            no title specfied.
        """
        expected_xml = '''\
        <boot_mods timeout="20"/>
        '''.replace(indentation, "")
        self._run_manifest_parser(self.BOOT_MODS_NOTITLE_XML, expected_xml)

    def test_manifest_notimeout_xml(self):
        """ Tests the from_xml() and to_xml() methods of BootMods with
            no timeout specfied.
        """
        expected_xml = '''\
        <boot_mods title="Boot Testing"/>
        '''.replace(indentation, "")
        self._run_manifest_parser(self.BOOT_MODS_NOTIMEOUT_XML, expected_xml)


class TestBootEntry(unittest.TestCase):
    """ Test case to test the from_xml() method of
        BootMods
    """
    BOOT_ENTRY_XML = '''
    <root>
        <boot_entry>
            <title_suffix>Basic Boot Entry</title_suffix>
        </boot_entry>
    </root>'''

    BOOT_ENTRY_DEFAULT_XML = '''
    <root>
        <boot_entry default_entry="true">
            <title_suffix>Default Boot Entry</title_suffix>
        </boot_entry>
    </root>'''

    BOOT_ENTRY_NOTDEFAULT_XML = '''
    <root>
        <boot_entry default_entry="false">
            <title_suffix>Non-Default Boot Entry</title_suffix>
        </boot_entry>
    </root>'''

    BOOT_ENTRY_START_XML = '''
    <root>
        <boot_entry insert_at="start">
            <title_suffix>First Boot Entry</title_suffix>
        </boot_entry>
    </root>'''

    BOOT_ENTRY_END_XML = '''
    <root>
        <boot_entry insert_at="end">
            <title_suffix>Last Boot Entry</title_suffix>
        </boot_entry>
    </root>'''

    BOOT_ENTRY_KARGS_XML = '''
    <root>
        <boot_entry>
            <title_suffix>Kernel Args Boot Entry</title_suffix>
            <kernel_args>test_kernel_args=rhubarb</kernel_args>
        </boot_entry>
    </root>'''

    def setUp(self):
        """ Initialises a runtime environment for execution of
            BootMods and BootMods unit tests.
        """
        self.engine = get_new_engine_instance()

    def tearDown(self):
        """ Cleans up after the previous unit test execution.
        """
        if self.engine is not None:
            reset_engine(self.engine)
        self.doc = None

    def _run_manifest_parser(self, test_xml, expected_xml):
        """ Support method to import manifest XML into the DOC and extract it
            back out. Compares the two and raises and assertEqual exception if
            they do not match.
            Inputs:
            - text_xml: The xml string representation imported into the DOC
            - expected_xml: The xml representation out from the DOC
        """
        self.doc = InstallEngine.get_instance().data_object_cache
        boot_entry_dom = etree.fromstring(test_xml)
        self.doc.import_from_manifest_xml(boot_entry_dom, volatile=True)

        boot_entry = self.doc.volatile.get_first_child(class_type=BootEntry)
        xml_str = boot_entry.get_xml_tree_str()
        self.assertEqual(xml_str, expected_xml,
            "Resulting XML doesn't match expected (len=%d != %d):\
             \nGOT:\n'%s'\nEXPECTED:\n'%s'\n" %
            (len(xml_str), len(expected_xml), xml_str, expected_xml))

    def test_manifest_basic_entry_xml(self):
        """Tests the from_xml() and to_xml() with a basic barebones entry.
        """
        expected_xml = '''\
        <boot_entry>
        ..<title_suffix>Basic Boot Entry</title_suffix>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_XML, expected_xml)

    def test_manifest_default_entry_xml(self):
        """Tests the from_xml() and to_xml() methods of BootEntry with
           default_entry = "true"
        """

        expected_xml = '''\
        <boot_entry default_entry="true">
        ..<title_suffix>Default Boot Entry</title_suffix>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_DEFAULT_XML, expected_xml)

    def test_manifest_notdefault_entry_xml(self):
        """Tests the from_xml() and to_xml() methods of BootEntry with
           default_entry = "false"
        """

        expected_xml = '''\
        <boot_entry default_entry="false">
        ..<title_suffix>Non-Default Boot Entry</title_suffix>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_NOTDEFAULT_XML, expected_xml)

    def test_manifest_start_entry_xml(self):
        """Tests the from_xml() and to_xml() methods of BootEntry with
           insert_at = "start"
        """

        expected_xml = '''\
        <boot_entry insert_at="start">
        ..<title_suffix>First Boot Entry</title_suffix>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_START_XML, expected_xml)

    def test_manifest_end_entry_xml(self):
        """Tests the from_xml() and to_xml() methods of BootEntry with
           insert_at = "end"
        """

        expected_xml = '''\
        <boot_entry insert_at="end">
        ..<title_suffix>Last Boot Entry</title_suffix>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_END_XML, expected_xml)

    def test_manifest_kargs_entry_xml(self):
        """Tests the from_xml() and to_xml() methods of BootEntry with
           kernel_args specified
        """

        expected_xml = '''\
        <boot_entry>
        ..<title_suffix>Kernel Args Boot Entry</title_suffix>
        ..<kernel_args>test_kernel_args=rhubarb</kernel_args>
        </boot_entry>
        '''.replace(indentation, "").replace(".", " ")
        self._run_manifest_parser(self.BOOT_ENTRY_KARGS_XML, expected_xml)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

from lxml import etree
import unittest

from solaris_install.sysconfig.profile.system_info import SystemInfo


class TestSystemInfo(unittest.TestCase):
    
    def test_determine_kbd_layout(self):
        '''Test that determine_kbd_layout returns under normal conditions'''
        # Due to its nature, and under the hope that an RFE comes along that
        # simplifies SystemInfo.determine_keyboard_layout(), only the
        # common case is checked for now.
        
        kbd = SystemInfo.determine_keyboard_layout('/dev/kbd',
                                 '/usr/share/lib/keytables/type_6/kbd_layouts')
        self.assertTrue(kbd)


SAMPLE_SYSINFO_XML = '''<root>
  <service version="1" type="service" name="system/config">
    <instance enabled="true" name="default">
      <property_group type="application" name="other_sc_params">
        <propval type="astring" name="timezone" value="Europe/Prague"/>
      </property_group>
    </instance>
  </service>
  <service version="1" type="service" name="system/identity">
    <instance enabled="true" name="node">
      <property_group type="application" name="config">
        <propval type="astring" name="nodename" value="solaris"/>
      </property_group>
    </instance>
  </service>
  <service version="1" type="service" name="system/keymap">
    <instance enabled="true" name="default">
      <property_group type="system" name="keymap">
        <propval type="astring" name="layout" value="US-English"/>
      </property_group>
    </instance>
  </service>
  <service version="1" type="service" name="system/console-login">
    <property_group type="application" name="ttymon">
      <propval type="astring" name="terminal_type" value="vt100"/>
    </property_group>
  </service>
</root>
'''


class TestSysInfoToXML(unittest.TestCase):
    
    def test_to_xml(self):
        '''Compare the SystemInfo.to_xml() output with a baseline (see above).
        Only concerned with structure, so propvals are ignored.
        
        '''
        sys = SystemInfo(tz_timezone='Europe/Prague')
        xml = sys.to_xml()
        xml_root = etree.fromstring("<root/>")
        xml_root.extend(xml)
        xml_str = etree.tostring(xml_root, pretty_print=True)
        xml_lines = xml_str.splitlines()
        compare_with = SAMPLE_SYSINFO_XML.splitlines()
        for xml_line, compare_with_line in zip(xml_lines, compare_with):
            if "<propval" in compare_with_line:
                continue
            self.assertEqual(xml_line, compare_with_line)

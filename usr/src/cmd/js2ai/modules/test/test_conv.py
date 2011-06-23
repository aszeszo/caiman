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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

import os
import shutil
import tempfile
import unittest

import solaris_install.js2ai as js2ai

from solaris_install.js2ai.common import ARCH_GENERIC, ARCH_SPARC, ARCH_X86
from solaris_install.js2ai.common import ConversionReport
from solaris_install.js2ai.common import KeyValues
from solaris_install.js2ai.common import DEFAULT_AI_FILENAME
from solaris_install.js2ai.common import fetch_xpath_node
from solaris_install.js2ai.common import pretty_print
from solaris_install.js2ai.common import write_xml_data
from solaris_install.js2ai.conv import XMLProfileData
from solaris_install.js2ai.conv import XMLRuleData
from solaris_install.js2ai.default_xml import XMLDefaultData
from test_js2ai import failure_report


class Test_Profile(unittest.TestCase):
    """Test Profile code"""
    default_xml = None

    def setUp(self):
        """Setup test run"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        # Test to see if the default xml file is present
        # on the system.  It isn't guaranteed to be present unless
        # the package pkg:/system/install/auto-install/auto-install-common
        # is installed.   If it is present use it.  If not we'll create
        # a barebones xml file
        if os.path.isfile(DEFAULT_AI_FILENAME):
            default_xml_filename = DEFAULT_AI_FILENAME
        else:
            default_xml_filename = None

        self.default_xml = XMLDefaultData(default_xml_filename)
        js2ai.logger_setup(self.working_dir)

    def tearDown(self):
        """Clean up test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def profile_failure_report(self, xml_profile_data, report):
        """Generate profile failure report"""
        rbuffer = "\nResulting XML Tree: "
        if xml_profile_data.tree is None:
            rbuffer += "No data available"
        else:
            rbuffer += "\n\n" + pretty_print(xml_profile_data.tree)
        rbuffer += "\n\n\n" + failure_report(report, self.log_file)
        return rbuffer

    def test_arch_conflict(self):
        """Test for conversion error when x86 and sparc ops mixed"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s1"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c3t0d0", "solaris", "all"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        # We get 2 conflict errors here instead of 1.
        # 1 is for architecture conflict while the other is for the
        # fdisk.  We use fdisk and boot_device to set the value to use
        # for rootdisk.
        self.assertEquals(report.conversion_errors, 2,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_arch_sparc(self):
        """Make sure arch type for profile is SPARC when sparc op used"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s1"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(ARCH_SPARC, xml_data.architecture)

    def test_arch_x86(self):
        """Make sure arch type for profile is X86 when x86 op used"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(ARCH_X86, xml_data.architecture)

    def test_arch_generic(self):
        """Ensure arch type for prof is generic when no sparc/x86 is op used"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool",
                              ["newpool", "auto", "auto", "auto", "any"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(ARCH_GENERIC, xml_data.architecture)

    def test_arch_none(self):
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "40", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(None, xml_data.architecture)

        # Fetch x86 and sparc versions of the manifest xml tree
        x86_tree = xml_data.fetch_tree(ARCH_X86)
        sparc_tree = xml_data.fetch_tree(ARCH_SPARC)

        # Test to make sure that the <partition> node exists in the x86
        # tree but not in the sparc tree
        xpath = "/auto_install/ai_instance/target/disk/partition"
        partition = fetch_xpath_node(x86_tree, xpath)
        self.assertNotEquals(None, partition,
                             "<partition> not found in x86 tree")

        partition = fetch_xpath_node(sparc_tree, xpath)
        self.assertEquals(None, partition,
                          "<partition> found in sparc tree")

    def test_boot_device_entry1(self):
        """Tests boot_device <device> where device is a disk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry2(self):
        """Tests boot_device <device> where device is a slice"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry3(self):
        """Tests boot_device <device> where device = any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["any"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry4(self):
        """Tests boot_device <device> where device = existing"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["existing"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry5(self):
        """Tests boot_device <device> <eprom> where eprom = preserve"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "preserve"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry6(self):
        """Tests boot_device <device> <eprom> where eeprom = update"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "update"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry7(self):
        """Tests boot_device <device> where device is a /dev/dsk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry8(self):
        """Tests boot_device <device> where too many args specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0", "1", "2"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry9(self):
        """Tests boot_device <device> <eprom> where eeprom = bogus"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "bogus"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True, str(report))
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry10(self):
        """Tests boot_device with previous set root_device """
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c2t0d0"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c0t0d0s0"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True, str(report))
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_boot_device_entry11(self):
        """Tests boot_device with bad device name """
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c0txx0s0"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True, str(report))
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry1(self):
        """Tests fdisk <diskname> where diskname is rootdisk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["rootdisk.s0", "solaris", "all"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry2(self):
        """Tests fdisk <diskname> where diskname is all"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["all", "solaris", "all"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry3(self):
        """Tests fdisk <diskname> where diskname is a valid disk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c2t0d0", "solaris", "all"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry4(self):
        """Tests fdisk <type> where type is dosprimary"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "dosprimary", "all"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry5(self):
        """Tests fdisk <type> where type is x86boot"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "x86boot", "all"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    # size == all was tested via tests above

    def test_fdisk_entry6(self):
        """Tests fdisk <size> where size is maxfree"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "maxfree"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry7(self):
        """Tests fdisk <size> where size is delete"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "delete"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry8(self):
        """Tests fdisk <size> where size is 0 (delete)"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "0"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry9(self):
        """Tests fdisk <size> where size is ##"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "40000"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry10(self):
        """Tests fdisk entry with to little args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_fdisk_entry11(self):
        """Tests fdisk entry with invalid size"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "xyz"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry1(self):
        """Tests filesys <device> where device is a disk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        # Fails because not a slice
        key_value = KeyValues("filesys", ["c2t0d0", "20", "/"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry2(self):
        """Tests filesys <device> where device is a slice with mount /"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "20", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry3(self):
        """Tests filesys <device> where device is a slice with mount swap"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2d0s0", "20", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry4(self):
        """Tests filesys <device> where device = any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "1024", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_filesys_entry5(self):
        """Tests filesys <device> where device is a slice with mount /opt"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2d0s0", "20", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry6(self):
        """Tests filesys <remote> <ip_addr>|"-" [<mount>] [<mntopts>]"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["s_ref:/usr/share/man", "-",
            "/usr/share/man", "ro"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry7(self):
        """Tests filesys mirror where the mirror is unamed and mount is swap"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        # This is invalid since no root / mount was specified
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s1", "c0t1d0s1"
            "2048", "swap"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry8(self):
        """Tests filesys mirror where the mirror is unamed"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry9(self):
        """Tests filesys mirror where the mirror is missing :"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirrorbogus", "c0t0d0s3", \
            "c0t1d0s3", "4096", "/"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry10(self):
        """Tests filesys <device> with no size specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry11(self):
        """Tests filesys with too many args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "/", "ro,quota", "extra arg"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry12(self):
        """Tests filesys mirror where the mirror device is not unique"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t0d0s3",
            "4096", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry13(self):
        """Tests filesys mirror where the mirror device is not unique"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "rootdisk.s3",
                             "rootdisk.s3", "4096", "/home"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry14(self):
        """Tests filesys with rootdisk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["rootdisk.s1", "2000", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry15(self):
        """Tests filesys mirror with no mount point specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry16(self):
        """Tests filesys <device> <size> with no mount point specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "5120"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry17(self):
        """Tests filesys mirror with invalid mount point specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "bad_mp"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry18(self):
        """Tests filesys <device> with invalid mount point specified"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "5120", "bad_mp"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry19(self):
        """Tests filesys mirror where the mount point is not /"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3",
                             "c0t0d0s4", "4096", "/home"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()

        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry20(self):
        """Tests root_device mirrored filesys conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 3)
        kv_dict[key_value.line_num] = key_value

        # filesys mirror c1t0d0s0 c1t0d0s2 all /
        key_value = KeyValues("filesys", ["mirror", "c1t0d0s0", "c1t0d0s2"
                              "all", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry21(self):
        """Tests root_device filesys device conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 3)
        kv_dict[key_value.line_num] = key_value

        # filesys c2t0d0s0 20 /
        key_value = KeyValues("filesys", ["c2t0d0s0", "20", "/"], 4)
        kv_dict[key_value.line_num] = key_value

        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry22(self):
        """Tests filesys <device> where device is a slice with mount /"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "2000000", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s4", "200", "swap"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry23(self):
        """Tests filesys mirror where the mirror is unamed for / and swap"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s0", "c0t1d0s0",
            "12048", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s1", "c0t1d0s1",
            "2048", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry24(self):
        """Tests filesys for / and swap, where swap has size of all"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "12048", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s1", "all", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry25(self):
        """Tests filesys for / and swap, where / has size of all"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "all", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s1", "2000", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry26(self):
        """Tests filesys for / and swap, where same slice specified for both"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "all", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "2000", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry27(self):
        """Tests filesys for / any and swap with specified slice"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "200000", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c0t0d0s0", "2000", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry28(self):
        """Tests filesys for / any and swap any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "200000", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "2000", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry29(self):
        """Tests filesys for invalid size"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "xyz", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry30(self):
        """Tests filesys with partitioning default"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "4000", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_filesys_entry31(self):
        """Tests filesys for / any and swap any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["any"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["explicit"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "200000", "/"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "2000", "swap"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_partitioning_entry1(self):
        """Tests partitioning default"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_partitioning_entry2(self):
        """Tests partitioning existing"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["existing"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, None,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_partitioning_entry3(self):
        """Tests partitioning duplicate"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["existing"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_package_entry1(self):
        """Tests package with incorrect # of args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["mirrorbogus", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_package_entry2(self):
        """Tests package with add option"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWzoner", "add"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report, None, False, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_package_entry3(self):
        """Tests package with delete option"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWzoner", "delete"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_package_entry4(self):
        """Tests package with understood add option"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWftp"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_package_entry5(self):
        """Tests package with remote add option"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        # package SPROcc add nfs 172.16.64.194:/export/packages
        key_value = KeyValues("package", ["SUNWftp", "add", "nfs",
                              "172.16.64.194:/export/packages"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry1(self):
        """Tests pool with incorrect # of args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["mirrorbogus", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry2(self):
        """Tests pool with pool name too long"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["aVeryLongPoolName01234567890123",
            "auto", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry3(self):
        """Tests pool with unsupported pool size of auto"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "auto", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry4(self):
        """Tests pool with unsupported pool size of all"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "all", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry5(self):
        """Tests pool with pool size/swap size/dump size/ of 4g"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry6(self):
        """Tests pool with invalid pool size"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4TB", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry7(self):
        """Tests pool with invalid swap size"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4TB", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry8(self):
        """Tests pool with invalid dump size"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4g", "4KB", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry9(self):
        """Tests pool where vdevlist is any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool", "4g", "4g", "4g", "any"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry10(self):
        """Tests pool with all any values"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "all", "auto", "auto", "any"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_pool_entry11(self):
        """Tests boot_device mirrored pool conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #boot_device c0t0d0
        key_value = KeyValues("boot_device", ["c0t0d0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto mirror c0t0d0s0 c0t0d0s1
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "mirror", "c0t0d0s0", "c1t0d0s1"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry12(self):
        """Tests root_device mirrored pool conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s1
        key_value = KeyValues("root_device", ["c0t0d0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto mirror c0t0d0s0 c0t0d0s1
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "mirror", "c0t0d0s0", "c0t0d1s0"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry13(self):
        """Tests boot_device pool device conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #boot_device c0t0d0
        key_value = KeyValues("boot_device", ["c0t0d0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto c1t0d0s7
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "c1t0d0s7"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry14(self):
        """Tests root_device pool device conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto c0t0d0s7
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "c1t0d0s7"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry15(self):
        """Tests root_device pool with no device conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto c0t0d0s0
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "c0t0d0s0"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry17(self):
        """Tests root_device pool with any device"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto any
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "any"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry18(self):
        """Tests mirrored pool with a device of any"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #root_device c0t0d0s0
        key_value = KeyValues("root_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto mirror any c0t0d0s7
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "mirror", "any", "c1t0d0s7"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry19(self):
        """Tests pool/fdisk conflict"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto c0t0d0s0
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        # fdisk c1t0d0 solaris all
        key_value = KeyValues("fdisk", ["c0t0d0", "solaris", "all"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry20(self):
        """Tests boot_device mirrored pool where devices agree"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #boot_device c0t0d0
        key_value = KeyValues("boot_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto mirror c0t0d0s0 c0t0d0s1
        key_value = KeyValues("pool", ["newpool", "auto", "auto", "auto",
                              "mirror", "c0t0d0s0", "c0t0d0s1"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_pool_entry21(self):
        """Tests boot_device, pool where device is any size is auto"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value

        #boot_device c0t0d0
        key_value = KeyValues("boot_device", ["c0t0d0s0"], 2)
        kv_dict[key_value.line_num] = key_value

        #pool newpool auto auto auto mirror c0t0d0s0 c0t0d0s1
        key_value = KeyValues("pool", ["newpool", "1000", "auto", "auto",
                              "any"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_root_device_entry1(self):
        """Tests root_device with incorrect # of args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["mirrorbogus", "/"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_root_device_entry2(self):
        """Tests root_device with invalid device"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["cKt0d0s3"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_root_device_entry3(self):
        """Tests root_device with valid device"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))

    def test_root_device_entry4(self):
        """Tests root_device with previous set boot_device"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c1t0d0s1"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 4)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_system_type_entry1(self):
        """Tests system_type with valid value"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("system_type", ["standalone"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 3)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_system_type_entry2(self):
        """Tests system_type with invalid value"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("system_type", ["somevalue"], 2)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 3)
        kv_dict[key_value.line_num] = key_value
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_usedisk_entry1(self):
        """Tests usedisk with incorrect # of args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["mirrorbogus", "c0d0s3", \
            "c0t1d0s3", "4096", "/"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_usedisk_entry2(self):
        """Tests usedisk with correct # of args"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 3)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["c0t0d0"], 5)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_usedisk_entry3(self):
        """Tests usedisk with correct # of args but bad disk"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["bogus"], 5)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 7)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_install_type_entry1(self):
        """Tests failure of install_type upgrade"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["upgrade"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, None,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_install_type_entry2(self):
        """Tests failure of install_type"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["None"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, None,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, None,
                          self.profile_failure_report(xml_data, report))

    def test_install_type_entry3(self):
        """Tests failure of install_type flash_install"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["flash_install"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, None,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_install_type_entry4(self):
        """Tests failure of install_type flash_upgrade"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["flash_upgrade"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.conversion_errors, None,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.unsupported_items, 1,
                          self.profile_failure_report(xml_data, report))
        self.assertEquals(report.validation_errors, 0,
                          self.profile_failure_report(xml_data, report))

    def test_install_type_entry5(self):
        """Tests install_type of initial_install"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        kv_dict[key_value.line_num] = key_value
        key_value = KeyValues("partitioning", ["default"], 2)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  self.default_xml, True, None)
        self.assertEquals(report.has_errors(), False,
                          self.profile_failure_report(xml_data, report))


class Test_Profile_corner_cases(unittest.TestCase):
    """Test profile corner cases"""

    def setUp(self):
        """Setup for tests run"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Cleanup test"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_corner_case1(self):
        """Tests corner cases to satisfy code coverage"""
        kv_dict = {}
        key_value = KeyValues("install_type", ["upgrade"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report,
                                  None, None, None)
        self.assertEquals(report.has_errors(), True)

    def test_corner_case2(self):
        """Tests corner cases to satisfy code coverage"""
        kv_dict = {}
        kv_dict[0] = None
        report = ConversionReport()
        self.assertRaises(KeyError, XMLProfileData,
                         "test", kv_dict, report, None, True, None)

    def test_non_exist_dir1(self):
        """Write xml data (None) to non existing directory

        """
        tdir = os.path.join(self.working_dir, "abc")
        # The directory that this file will be written to doesn't exist
        # so this test passes by not getting any exceptions during the
        # run
        write_xml_data(None, tdir, "filename")

    def test_non_exist_dir2(self):
        """Write xml data to non existing directory

        """
        kv_dict = {}
        key_value = KeyValues("install_type", ["invalid_value"], 1)
        kv_dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", kv_dict, report, None, True, None)
        tdir = os.path.join(self.working_dir, "abc")
        # The directory that this file will be written to doesn't exist
        # so this test passes by not getting any exceptions during the
        # run
        write_xml_data(xml_data.tree, tdir, "filename")


class Test_Profile_unsupported_keywords(unittest.TestCase):
    """Test profile unsupported keywords"""

    unsupported_keywords = [
        "bootenv",
        "client_arch",
        "client_swap",
        "cluster",
        "dontuse",
        "geo",
        "locale",
        "num_clients",
        "partitioning",
        "system_type",
    ]

    def test_unsupported_keywords(self):
        """Tests failure of unsupported keywords"""
        for keyword in self.unsupported_keywords:
            kv_dict = {}
            key_value = KeyValues(keyword, ["bogus_arg"], 1)
            kv_dict[key_value.line_num] = key_value
            report = ConversionReport()
            XMLProfileData("test", kv_dict, report, None, True, None)
            self.assertEquals(report.has_errors(), True)
            self.assertEquals(report.process_errors, 1)
            self.assertEquals(report.conversion_errors, None)
            self.assertEquals(report.unsupported_items, None)


class Test_Rules(unittest.TestCase):
    """Test Rules"""

    def setUp(self):
        """Setup tests"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)
        js2ai.logger_setup(self.working_dir)

    def tearDown(self):
        """Cleanup after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def rule_failure_report(self, report):
        """Generate failure report"""
        return failure_report(report, self.log_file)

    def test_arch_entry1(self):
        """ Tests the "arch" keyword to make sure it returns successfully"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("arch", ["sparc"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_arch_entry2(self):
        """ Tests the "arch" keyword to make sure it returns failure.
        """
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("arch", None, 1)
        report = ConversionReport()
        try:
            XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass
        else:
            self.fail("Expected ValueError")

    def test_hostaddress_entry1(self):
        """ Tests the "hostaddress" keyword to make sure it returns success"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("hostaddress", ["192.168.168.123"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_hostaddress_entry2(self):
        """ Tests the "hostaddress" keyword to make sure it fails if None"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("hostaddress", None, 1)
        report = ConversionReport()
        try:
            XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass
        else:
            self.fail("Expected ValueError")

    def test_no_def_rule(self):
        """ Test the error path in the case where is no defined rule"""
        report = ConversionReport()
        XMLRuleData("test", None, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_network_range1(self):
        """ Test that given an address we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("network", ["192.168.168.0"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_network_range2(self):
        """ Test that given an invalid address we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("network", ["192.168.168"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), True,
                          self.rule_failure_report(report))
        self.assertEquals(report.process_errors, 1,
                          self.rule_failure_report(report))
        self.assertEquals(report.conversion_errors, 0,
                          self.rule_failure_report(report))
        self.assertEquals(report.unsupported_items, 0,
                          self.rule_failure_report(report))

    def test_karch_entry1(self):
        """ Test that given an karch we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("karch", ["sun4v"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_karch_entry2(self):
        """ Test that given an invalid karch we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("karch", None, 1)
        report = ConversionReport()
        try:
            XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass

    def test_memsize_entry1(self):
        """ Test that given a memsize we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", ["2048"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_memsize_entry2(self):
        """ Test that given a invalid memsize we error correctly """
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", None, 1)
        report = ConversionReport()
        try:
            XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass
        else:
            self.fail("Expected ValueError")

    def test_memsize_entry3(self):
        """ Test that given a memsize we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", ["1024-2048"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_model_entry1(self):
        """ Test that given an model we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("model", ["SUNW,Sun-Fire-880"], 1)
        report = ConversionReport()
        XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False,
                          self.rule_failure_report(report))

    def test_model(self):
        """ Test that given an blank model we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("model", None, 1)
        report = ConversionReport()
        try:
            XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass
        else:
            self.fail("Expected ValueError")


class Test_Rule_unsupported_keywords(unittest.TestCase):
    """Test Rules unsupported keywords"""

    unsupported_rule_keywords = [
        "any",
        "disksize",
        "domainname",
        "hostname",
        "installed",
        "osname",
        "probe",
        "totaldisk",
        "bogus",
    ]

    def test_unsupported_rule_keywords(self):
        """Tests failure of unsupported keywords"""
        for keyword in self.unsupported_rule_keywords:
            def_rule = js2ai.DefinedRule(None, None, None)
            report = ConversionReport()
            def_rule.add_key_values(keyword, ["bogus_arg"], 1)
            XMLRuleData("test", def_rule, report, None)
            self.assertEquals(report.has_errors(), True)
            self.assertEquals(report.process_errors, 0)
            self.assertEquals(report.conversion_errors, 0)
            self.assertEquals(report.unsupported_items, 1, keyword + "failed")


if __name__ == '__main__':
    unittest.main()

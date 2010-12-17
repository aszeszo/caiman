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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

import sys
import os
import unittest
import tempfile
import shutil

import solaris_install.js2ai as js2ai

from solaris_install.js2ai.common import ProfileData
from solaris_install.js2ai.common import KeyValues
from solaris_install.js2ai.common import ConversionReport
from solaris_install.js2ai.conv import XMLProfileData
from solaris_install.js2ai.conv import XMLRuleData


class  Test_Profile_boot_device(unittest.TestCase):

    def test_boot_device_entry1(self):
        """Tests boot_device <device> where device is a disk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False)

    def test_boot_device_entry2(self):
        """Tests boot_device <device> where device is a slice"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), False)

    def test_boot_device_entry3(self):
        """Tests boot_device <device> where device = any"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["any"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_boot_device_entry4(self):
        """Tests boot_device <device> where device = existing"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["existing"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_boot_device_entry5(self):
        """Tests boot_device <device> <eprom> where eprom = preserve"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "preserve"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_boot_device_entry6(self):
        """Tests boot_device <device> <eprom> where eeprom = update"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "update"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_boot_device_entry7(self):
        """Tests boot_device <device> where device is a /dev/dsk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), False)

    def test_boot_device_entry8(self):
        """Tests boot_device <device> where too many args specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2d0s0", "1", "2"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        report = xml_data.conversion_report
        self.assertEquals(report.has_errors(), True)

    def test_boot_device_entry9(self):
        """Tests boot_device <device> <eprom> where eeprom = bogus"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("boot_device", ["c2t0d0s0", "bogus"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True, str(report))
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)


class  Test_Profile_fdisk(unittest.TestCase):

    def test_fdisk_entry1(self):
        """Tests fdisk <diskname> where diskname is rootdisk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["rootdisk.s0", "solaris", "all"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_fdisk_entry2(self):
        """Tests fdisk <diskname> where diskname is all"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["all", "solaris", "all"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_fdisk_entry3(self):
        """Tests fdisk <diskname> where diskname is a valid disk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c2t0d0", "solaris", "all"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_fdisk_entry4(self):
        """Tests fdisk <type> where type is dosprimary"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "dosprimary", "all"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_fdisk_entry5(self):
        """Tests fdisk <type> where type is x86boot"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "x86boot", "all"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    # size == all was tested via tests above

    def test_fdisk_entry6(self):
        """Tests fdisk <size> where size is maxfree"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "maxfree"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_fdisk_entry7(self):
        """Tests fdisk <size> where size is delete"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "delete"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_fdisk_entry8(self):
        """Tests fdisk <size> where size is 0 (delete)"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "0"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_fdisk_entry9(self):
        """Tests fdisk <size> where size is ##"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0", "solaris", "40000"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_fdisk_entry10(self):
        """Tests fdisk entry with to little args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("fdisk", ["c1t0d0"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        logger = None
        xml_data = XMLProfileData("test", dict, report, True, logger)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)


class  Test_Profile_filesys(unittest.TestCase):

    def test_filesys_entry1(self):
        """Tests filesys <device> where device is a disk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        # Fails because not a slice
        key_value = KeyValues("filesys", ["c2t0d0", "20", "/"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_filesys_entry2(self):
        """Tests filesys <device> where device is a slice with mount /"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "20", "/"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_filesys_entry3(self):
        """Tests filesys <device> where device is a slice with mount swap"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2d0s0", "20", "swap"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry4(self):
        """Tests filesys <device> where device = any"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["any", "1024", "/", "logging"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry5(self):
        """Tests filesys <device> where device is a slice with mount /opt"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2d0s0", "20", "/"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_filesys_entry6(self):
        """Tests filesys <remote> <ip_addr>|"-" [<mount>] [<mntopts>]"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["s_ref:/usr/share/man", "-",
            "/usr/share/man", "ro"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry7(self):
        """Tests filesys mirror where the mirror is unamed and mount is swap"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s1",
            "2048", "swap"], 3)
        # The swap file system is created and mirrored on the slice c0t0d0s1,
        # and is sized at 2048 Mbytes. The custom JumpStart program assigns a
        # name to the mirror.
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_filesys_entry8(self):
        """Tests filesys mirror where the mirror is unamed"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "/"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_filesys_entry9(self):
        """Tests filesys mirror where the mirror is missing :"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirrorbogus", "c0t0d0s3",\
            "c0t1d0s3", "4096", "/"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_filesys_entry10(self):
        """Tests filesys <device> with no size specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_filesys_entry11(self):
        """Tests filesys with too many args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "/", "ro,quota", "extra arg"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_filesys_entry12(self):
        """Tests filesys mirror where the mirror device is not unique"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t0d0s3",
            "4096", "/"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 1, report)

    def test_filesys_entry12(self):
        """Tests filesys mirror where the mirror device is not unique"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 2)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "rootdisk.s3",
                             "rootdisk.s3", "4096", "/home"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 1, report)

    def test_filesys_entry13(self):
        """Tests filesys with multiple rootdisks"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 2)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["rootdisk.s0", "2000", "/"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_filesys_entry14(self):
        """Tests filesys mirror with no mount point specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry15(self):
        """Tests filesys <device> <size> with no mount point specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "5120"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry16(self):
        """Tests filesys mirror with invalid mount point specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3", "c0t1d0s3",
            "4096", "bad_mp"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry17(self):
        """Tests filesys <device> with invalid mount point specified"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["c2t0d0s0", "5120", "bad_mp"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_filesys_entry18(self):
        """Tests filesys mirror where the mount point is not /"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("filesys", ["mirror", "c0t0d0s3",
                             "c0t0d0s4", "4096", "/home"], 3)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 1, report)


class  Test_Profile_package(unittest.TestCase):

    def test_package_entry1(self):
        """Tests package with incorrect # of args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["mirrorbogus", "/"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_package_entry2(self):
        """Tests package with add option"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWzoner", "add"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, False, None)
        self.assertEquals(report.has_errors(), False)

    def test_package_entry3(self):
        """Tests package with delete option"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWzoner", "delete"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_package_entry4(self):
        """Tests package with understood add option"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("package", ["SUNWftp"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)


class  Test_Profile_pool(unittest.TestCase):

    def test_pool_entry1(self):
        """Tests pool with incorrect # of args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["mirrorbogus", "/"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_pool_entry2(self):
        """Tests pool with pool name too long"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["aVeryLongPoolName01234567890123",
            "auto", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_pool_entry3(self):
        """Tests pool with unsupported pool size of auto"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "auto", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_pool_entry4(self):
        """Tests pool with unsupported pool size of all"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "all", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_pool_entry5(self):
        """Tests pool with pool size/swap size/dump size/ of 4g"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)

    def test_pool_entry6(self):
        """Tests pool with invalid pool size"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4TB", "4g", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_pool_entry7(self):
        """Tests pool with invalid swap size"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4TB", "4g", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_pool_entry8(self):
        """Tests pool with invalid dump size"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "4g", "4g", "4KB", "mirror", "c0t0d0s0", "c0t1d0s0"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_pool_entry9(self):
        """Tests failure: pool where vdevlist is any"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool", "4g", "4g", "4g", "any"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_pool_entry10(self):
        """Tests pool with all any values"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("pool", ["rpool",
            "all", "auto", "auto", "any"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)


class  Test_Profile_root_device(unittest.TestCase):

    def test_root_device_entry1(self):
        """Tests root_device with incorrect # of args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["mirrorbogus", "/"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_root_device_entry2(self):
        """Tests root_device with invalid device"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["cKt0d0s3"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)

    def test_root_device_entry3(self):
        """Tests root_device with valid device"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("root_device", ["c0t0d0s1"], 4)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)


class  Test_Profile_usedisk(unittest.TestCase):

    def test_usedisk_entry1(self):
        """Tests usedisk with incorrect # of args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["mirrorbogus", "c0d0s3",\
            "c0t1d0s3", "4096", "/"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_usedisk_entry2(self):
        """Tests usedisk with correct # of args"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["c0t0d0"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 1)

    def test_usedisk_entry3(self):
        """Tests usedisk with correct # of args but bad disk"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        key_value = KeyValues("usedisk", ["bogus"], 5)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 1)
        self.assertEquals(report.unsupported_items, 0)


class  Test_Profile_corner_cases(unittest.TestCase):

    def test_corner_case1(self):
        """Tests corner cases to satisfy code coverage"""
        dict = {}
        key_value = KeyValues("install_type", ["upgrade"], None)
        dict[key_value.line_num] = key_value
        self.assertRaises(ValueError,
            XMLProfileData, "test", dict, None, True, None)

    def test_corner_case2(self):
        """Tests corner cases to satisfy code coverage"""
        dict = {}
        dict[0] = None
        self.assertRaises(ValueError, XMLProfileData,
                         "test", dict, None, True, None)


class  Test_Profile_install_type(unittest.TestCase):

    def test_install_type_entry1(self):
        """Tests failure of install_type upgrade"""
        dict = {}
        key_value = KeyValues("install_type", ["upgrade"], 1)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, str(report))
        self.assertEquals(report.conversion_errors, None)
        self.assertEquals(report.unsupported_items, 1)

    def test_install_type_entry2(self):
        """Tests failure of install_type"""
        dict = {}
        key_value = KeyValues("install_type", ["None"], 1)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, None)
        self.assertEquals(report.unsupported_items, None)

    def test_install_type_entry3(self):
        """Tests failure of install_type flash_install"""
        dict = {}
        key_value = KeyValues("install_type", ["flash_install"], 1)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, str(report))
        self.assertEquals(report.conversion_errors, None)
        self.assertEquals(report.unsupported_items, 1)

    def test_install_type_entry4(self):
        """Tests failure of install_type flash_upgrade"""
        dict = {}
        key_value = KeyValues("install_type", ["flash_upgrade"], 1)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 0, str(report))
        self.assertEquals(report.conversion_errors, None)
        self.assertEquals(report.unsupported_items, 1)

    def test_install_type_entry5(self):
        """Tests install_type of initial_install"""
        dict = {}
        key_value = KeyValues("install_type", ["initial_install"], 1)
        dict[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLProfileData("test", dict, report, True, None)
        self.assertEquals(report.has_errors(), False)


class  Test_Profile_unsupported_keywords(unittest.TestCase):

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
            dict = {}
            key_value = KeyValues(keyword, ["bogus_arg"], 1)
            dict[key_value.line_num] = key_value
            report = ConversionReport()
            xml_data = XMLProfileData("test", dict, report, True, None)
            self.assertEquals(report.has_errors(), True)
            self.assertEquals(report.process_errors, 1)
            self.assertEquals(report.conversion_errors, None)
            self.assertEquals(report.unsupported_items, None)


class  Test_Rules(unittest.TestCase):

    def test_arch_entry1(self):
        """ Tests the "arch" keyword to make sure it returns successfully"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("arch", ["sparc"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_arch_entry2(self):
        """ Tests the "arch" keyword to make sure it returns failure.
        """
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("arch", None, 1)
        report = ConversionReport()
        try:
            xml_data = XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass

    def test_hostaddress_entry1(self):
        """ Tests the "hostaddress" keyword to make sure it returns success"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("hostaddress", ["192.168.168.123"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_hostaddress_entry2(self):
        """ Tests the "hostaddress" keyword to make sure it fails if None"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("hostaddress", None, 1)
        report = ConversionReport()
        try:
            xml_data = XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass

    def test_no_def_rule(self):
        """ Test the error path in the case where is no defined rule"""
        report = ConversionReport()
        xml_data = XMLRuleData("test", None, report, None)
        self.assertEquals(report.has_errors(), False)
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_network_range1(self):
        """ Test that given an address we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("network", ["192.168.168.0"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_network_range2(self):
        """ Test that given an invalid address we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("network", ["192.168.168"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

    def test_karch_entry1(self):
        """ Test that given an karch we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("karch", ["sun4v"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_karch_entry2(self):
        """ Test that given an invalid karch we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("karch", None, 1)
        report = ConversionReport()
        try:
            xml_data = XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass

    def test_memsize_entry1(self):
        """ Test that given a memsize we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", ["2048"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_memsize_entry2(self):
        """ Test that given a invalid memsize we error correctly """
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", None, 1)
        report = ConversionReport()
        try:
            xml_data = XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass

    def test_memsize_entry3(self):
        """ Test that given a memsize we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("memsize", ["1024-2048"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_model_entry1(self):
        """ Test that given an model we process it correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("model", ["SUNW,Sun-Fire-880"], 1)
        report = ConversionReport()
        xml_data = XMLRuleData("test", def_rule, report, None)
        self.assertEquals(report.has_errors(), False)

    def test_model(self):
        """ Test that given an blank model we error correctly"""
        def_rule = js2ai.DefinedRule(None, None, None)
        def_rule.add_key_values("model", None, 1)
        report = ConversionReport()
        try:
            xml_data = XMLRuleData("test", def_rule, report, None)
        except ValueError:
            pass


class  Test_Rule_unsupported_keywords(unittest.TestCase):

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
            xml_data = XMLRuleData("test", def_rule, report, None)
            self.assertEquals(report.has_errors(), True)
            self.assertEquals(report.process_errors, 0)
            self.assertEquals(report.conversion_errors, 0)
            self.assertEquals(report.unsupported_items, 1)


if __name__ == '__main__':
    unittest.main()

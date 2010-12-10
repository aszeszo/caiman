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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

""" test_grub_setup

 Test program for grub_setup
"""

import os
import os.path
import shutil
import unittest

import testlib

from solaris_install.distro_const.checkpoints.grub_setup import AIGrubSetup, \
    LiveCDGrubSetup, TextGrubSetup
from solaris_install.distro_const.distro_spec import GrubEntry, GrubMods
from solaris_install.engine import InstallEngine


class TestBuildPositionSpecific(unittest.TestCase):
    """ test case to test the build_position_specific() method of
        GrubSetup
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/menu.lst", "/.image_info"]
        self.grubsetup = LiveCDGrubSetup("Test GrubSetup")
        self.grubsetup.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.grubsetup.img_info_path = \
            os.path.join(self.grubsetup.pkg_img_path, ".image_info")
        self.grubsetup.menu_list = \
            os.path.join(self.grubsetup.pkg_img_path, "menu.lst")

        grub_mods = GrubMods("GrubMods")
        grub_mods.min_mem = "1000"
        grub_mods.timeout = "30"
        grub_mods.default_entry = "0"
        grub_mods.title = "myentry"
        self.grubsetup.grub_mods = grub_mods

    def tearDown(self):
        shutil.rmtree(self.grubsetup.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_position_begin(self):
        begin_entry = GrubEntry("Begin Entry")
        begin_entry.position = "0"
        begin_entry.title_suffix = "Sonia"
        begin_entry.lines = ["kernel$ SonKern", "module$ SonMod"]

        entries = self.grubsetup.build_entries()
        self.grubsetup.grub_entry_list = [begin_entry]
        self.grubsetup.build_position_specific(entries)
        self.grubsetup.write_entries(entries)

        try:
            with open(self.grubsetup.menu_list, "r") as fh:
                menu_lst_data = [line.strip() for line in fh.readlines()]
                fh.close()
        except IOError, msg:
            self.fail("unable to open the menu.list file: " + str(msg))

        # walk the menu.lst file and look for the first title
        for line in menu_lst_data:
            if line.startswith("title"):
                self.assert_("Sonia" in line, line)
                break

    def test_position_second(self):
        second_entry = GrubEntry("Second Entry")
        second_entry.position = "1"
        second_entry.title_suffix = "derp"
        second_entry.lines = ["kernel$ derpKern", "module$ derpKern"]

        entries = self.grubsetup.build_entries()
        self.grubsetup.grub_entry_list = [second_entry]
        self.grubsetup.build_position_specific(entries)
        self.grubsetup.write_entries(entries)

        try:
            with open(self.grubsetup.menu_list, "r") as fh:
                menu_lst_data = [line.strip() for line in fh.readlines()]
                fh.close()
        except IOError, msg:
            self.fail("unable to open the menu.list file: " + str(msg))

        # walk the menu.lst file and look for the first title
        title = 0
        for line in menu_lst_data:
            if line.startswith("title"):
                if title == 1:
                    self.assert_("derp" in line, line)
                    break
                else:
                    title += 1

        # verify the default, timeout and min_mem64 values
        for line in menu_lst_data:
            if line.startswith("default"):
                self.assertEqual(line.split()[1], "0")
            if line.startswith("timeout"):
                self.assertEqual(line.split()[1], "30")
            if line.startswith("min_mem"):
                self.assertEqual(line.split()[1], "1000")


class TestUpdateImgInfo(unittest.TestCase):
    """ test case to test the update_img_info_path() method of
        GrubSetup
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/menu.lst", "/.image_info", "/etc/release"]
        self.grubsetup = AIGrubSetup("Test GrubSetup")
        self.grubsetup.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.grubsetup.img_info_path = \
            os.path.join(self.grubsetup.pkg_img_path, ".image_info")
        self.grubsetup.menu_list = \
            os.path.join(self.grubsetup.pkg_img_path, "menu.lst")

        grub_mods = GrubMods("GrubMods")
        grub_mods.min_mem = "1000"
        grub_mods.timeout = "30"
        grub_mods.default_entry = "0"
        grub_mods.title = "Sonia's entry"
        self.grubsetup.grub_mods = grub_mods

    def tearDown(self):
        shutil.rmtree(self.grubsetup.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_ai_entries(self):
        self.grubsetup.update_img_info_path()
        iip = os.path.join(self.grubsetup.pkg_img_path, ".image_info")
        with open(iip, "r") as fh:
            image_info = fh.read().splitlines()

        # verify the AI specific entries
        line = "GRUB_MIN_MEM64=%s" % self.grubsetup.grub_mods.min_mem
        self.assert_(line in image_info)
        self.assert_("GRUB_DO_SAFE_DEFAULT=true" in image_info)


class TestAIBuildEntries(unittest.TestCase):
    """ test case to test the build_entries() method of
        AIGrubSetup
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/menu.lst"]
        self.grubsetup = AIGrubSetup("Test AIGrubSetup")
        self.grubsetup.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.grubsetup.menu_list = \
            os.path.join(self.grubsetup.pkg_img_path, "menu.lst")

        grub_mods = GrubMods("GrubMods")
        grub_mods.min_mem = "1000"
        grub_mods.timeout = "30"
        grub_mods.default_entry = "0"
        grub_mods.title = "Sonia's entry"
        self.grubsetup.grub_mods = grub_mods

    def tearDown(self):
        shutil.rmtree(self.grubsetup.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_write_entries(self):
        second_entry = GrubEntry("Second Entry")
        second_entry.position = "1"
        second_entry.title_suffix = "derp"
        second_entry.lines = ["kernel$ derpKern", "module$ derpKern"]

        entries = self.grubsetup.build_entries()
        self.grubsetup.grub_entry_list = [second_entry]
        self.grubsetup.build_position_specific(entries)
        self.grubsetup.write_entries(entries)

        try:
            with open(self.grubsetup.menu_list, "r") as fh:
                menu_lst_data = [line.strip() for line in fh.readlines()]
                fh.close()
        except IOError, msg:
            self.fail("unable to open the menu.list file: " + str(msg))

        # verify the 'custom' and regular entry
        for line in menu_lst_data:
            if line.startswith("title") and \
                line.strip().endswith("Automated Install custom"):
                for innerline in menu_lst_data:
                    if line.startswith("kernel"):
                        self.assert_(
                            innerline.strip().endswith("aimanifest=prompt"))
                        break

            if line.startswith("title") and \
                line.strip().endswith("Automated Install"):
                for innerline in menu_lst_data:
                    if line.startswith("kernel"):
                        self.assert_("=" in innerline)
                        break


class TestLiveCDBuildEntries(unittest.TestCase):
    """ test case to test the build_entries() method of
        LiveCDGrubSetup
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/menu.lst"]
        self.grubsetup = LiveCDGrubSetup("Test LiveCDGrubSetup")
        self.grubsetup.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.grubsetup.menu_list = \
            os.path.join(self.grubsetup.pkg_img_path, "menu.lst")

        grub_mods = GrubMods("GrubMods")
        grub_mods.min_mem = "1000"
        grub_mods.timeout = "30"
        grub_mods.default_entry = "0"
        grub_mods.title = "Sonia's entry"
        self.grubsetup.grub_mods = grub_mods

    def tearDown(self):
        shutil.rmtree(self.grubsetup.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_write_entries(self):
        second_entry = GrubEntry("Second Entry")
        second_entry.position = "1"
        second_entry.title_suffix = "derp"
        second_entry.lines = ["kernel$ derpKern", "module$ derpKern"]

        entries = self.grubsetup.build_entries()
        self.grubsetup.grub_entry_list = [second_entry]
        self.grubsetup.build_position_specific(entries)
        self.grubsetup.write_entries(entries)

        try:
            with open(self.grubsetup.menu_list, "r") as fh:
                menu_lst_data = [line.strip() for line in fh.readlines()]
                fh.close()
        except IOError, msg:
            self.fail("unable to open the menu.list file: " + str(msg))

        # verify the 'vesa' and 'text console' entry
        for line in menu_lst_data:
            if line.startswith("title") and \
                line.strip().endswith("VESA driver"):
                for innerline in menu_lst_data:
                    if line.startswith("kernel"):
                        self.assert_(
                            innerline.strip().endswith("-B livemode=vesa"))
                        break

            if line.startswith("title") and \
                line.strip().endswith("text console"):
                for innerline in menu_lst_data:
                    if line.startswith("kernel"):
                        self.assert_(
                            innerline.strip().endswith("-B livemode=text"))
                        break


class TestTextBuildEntries(unittest.TestCase):
    """ test case to test the build_entries() method of
        TextGrubSetup
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/menu.lst"]
        self.grubsetup = TextGrubSetup("Test TextGrubSetup")
        self.grubsetup.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.grubsetup.menu_list = \
            os.path.join(self.grubsetup.pkg_img_path, "menu.lst")

        grub_mods = GrubMods("GrubMods")
        grub_mods.min_mem = "1000"
        grub_mods.timeout = "30"
        grub_mods.default_entry = "0"
        grub_mods.title = "Sonia's entry"
        self.grubsetup.grub_mods = grub_mods

    def tearDown(self):
        shutil.rmtree(self.grubsetup.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_write_entries(self):
        second_entry = GrubEntry("Second Entry")
        second_entry.position = "1"
        second_entry.title_suffix = "derp"
        second_entry.lines = ["kernel$ derpKern", "module$ derpKern"]

        entries = self.grubsetup.build_entries()
        self.grubsetup.grub_entry_list = [second_entry]
        self.grubsetup.build_position_specific(entries)
        self.grubsetup.write_entries(entries)

        try:
            with open(self.grubsetup.menu_list, "r") as fh:
                menu_lst_data = [line.strip() for line in fh.readlines()]
                fh.close()
        except IOError, msg:
            self.fail("unable to open the menu.list file: " + str(msg))

        # verify that there's a 'hiddenmenu' line
        hiddenmenu = 0
        for line in menu_lst_data:
            if line.startswith("hiddenmenu"):
                hiddenmenu = 1
                break

        self.assert_(hiddenmenu == 1)

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

""" test_pkg_img_mod

 Test program for the pkg_img_mod checkpoint

"""

import shutil
import os
import unittest

import testlib

from solaris_install.distro_const.checkpoints.pkg_img_mod import PkgImgMod, \
    LiveCDPkgImgMod, AIPkgImgMod
from solaris_install.engine import InstallEngine


class TestStripRoot(unittest.TestCase):
    """ test case to test the strip_root() method of PkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/etc/.pwd.lock",
                         "/sbin/bar/baz",
                         "/kernel/foo",
                         "/lib/"]
        self.ba_filelist = ["/.volsetid"]
        self.pim = PkgImgMod("Test PkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.pim.ba_build = testlib.create_filesystem(*self.ba_filelist)

    def tearDown(self):
        for entry in [self.pim.pkg_img_path, self.pim.ba_build]:
            shutil.rmtree(entry, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.strip_root()

        # verify sbin, kernel, lib and .pwd.lock are removed
        self.assert_(not os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "sbin")))
        self.assert_(not os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "kernel")))
        self.assert_(not os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "lib")))
        self.assert_(not os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "etc/.pwd.lock")))

        # verify .volsetid got copied
        self.assert_(os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                 ".volsetid")))


class TestCreateUsrArchive(unittest.TestCase):
    """ test case to test the create_usr_archive() method of PkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/usr/lib",
                         "/usr/sbin/lofiadm",
                         "/usr/file1/file2",
                         "/usr/file2/file3/file4",
                         "/usr/file3/file3/file4/file5",
                         "/usr/file4/file5/file6/file7/file8"]
        self.pim = PkgImgMod("Test PkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.create_usr_archive()

        # verify that that zlib was created
        self.assert_(os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "solaris.zlib")))


class TestCreateMiscArchive(unittest.TestCase):
    """ test case to test the create_misc_archive() method of PkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.filelist = ["/opt/",
                         "/opt/lib",
                         "/etc/",
                         "/etc/sbin/lofiadm",
                         "/etc/file1/file2",
                         "/var/",
                         "/var/file2/file3/file4",
                         "/var/file3/file3/file4/file5",
                         "/var/file4/file5/file6/file7/file8"]
        self.pim = PkgImgMod("Test PkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.create_misc_archive()

        # verify that that zlib was created
        self.assert_(os.path.exists(os.path.join(self.pim.pkg_img_path,
                                                     "solarismisc.zlib")))


class TestCleanupIcons(unittest.TestCase):
    """ test case to test the cleanup_icons method of LiveCDPkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the
        # proper location
        InstallEngine()
        self.filelist = ["/usr/",
                         "/usr/file1/file2/icon-theme.cache"]
        self.pim = LiveCDPkgImgMod("Test LiveCDPkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.cleanup_icons()
        os.chdir(os.path.join(self.pim.pkg_img_path, "usr"))

        for _none, _none, files in os.walk("."):
            self.assert_("icon-theme.cache" not in files)


class TestStripPlatform(unittest.TestCase):
    """ test case to test the strip_platform method of LiveCDPkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the
        # proper location
        InstallEngine()
        self.filelist = ["/platform/",
                         "/platform/dir1/dir2/unix",
                         "/platform/dir1/dir2/file",
                         "/platform/dir2/dir3/boot_archive",
                         "/platform/dir2/dir3/file2"]

        self.pim = LiveCDPkgImgMod("Test LiveCDPkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.strip_platform()
        os.chdir(os.path.join(self.pim.pkg_img_path, "platform"))

        # ensure that boot_archive and unix were not removed
        # but 'file' and 'file2' were
        for _none, _none, files in os.walk("."):
            for f in files:
                self.assert_(f not in ["file", "file2"], f)
                self.assert_(f in ["boot_archive", "unix"], f)


class TestStripX86Platform(unittest.TestCase):
    """ test case to test the strip_x86_platform method of AIPkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the
        # proper location
        InstallEngine()
        self.filelist = ["/platform/",
                         "/platform/i86pc/amd64/boot_archive",
                         "/platform/i86pc/amd64/archive_cache",
                         "/platform/i86pc/boot_archive",
                         "/platform/i86pc/kernel/unix",
                         "/platform/i86pc/kernel/drv/xsvc",
                         "/boot/"]

        self.pim = AIPkgImgMod("Test AIPkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.strip_x86_platform()
        os.chdir(os.path.join(self.pim.pkg_img_path, "platform"))

        for (_none, _none, files) in os.walk("."):
            for f in files:
                self.assert_(f in ["boot_archive", "unix"], f)

        # verify the directory created in boot is a full directory
        self.assert_(os.path.isdir(os.path.join(self.pim.pkg_img_path,
                                                "boot/platform")))


class TestStripSPARCPlatform(unittest.TestCase):
    """ test case to test the strip_sparc_platform method of AIPkgImgMod
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the
        # proper location
        InstallEngine()
        self.filelist = ["/platform/",
                         "/platform/sun4u/boot_archive",
                         "/platform/sun4v/archive_cache",
                         "/platform/file/wanboot",
                         "/platform/kernel/unix",
                         "/platform/kernel/genunix",
                         "/boot/"]

        self.pim = AIPkgImgMod("Test AIPkgImgMod")
        self.pim.pkg_img_path = testlib.create_filesystem(*self.filelist)

    def tearDown(self):
        shutil.rmtree(self.pim.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_run(self):
        self.pim.strip_sparc_platform()
        os.chdir(os.path.join(self.pim.pkg_img_path, "platform"))

        for (_none, _none, files) in os.walk("."):
            for f in files:
                self.assert_(f in ["boot_archive", "wanboot"], f)

        # verify the directory created in boot is a symlink
        self.assert_(os.path.islink(os.path.join(self.pim.pkg_img_path,
                                                "boot/platform")))

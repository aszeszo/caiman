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

""" test_boot_archive_archive

 Test program for boot_archive_archive

"""

import os
import os.path
import shutil
import subprocess
import tempfile
import unittest

import testlib

from osol_install.install_utils import dir_size
from solaris_install.distro_const.checkpoints.boot_archive_archive \
    import BootArchiveArchive
from solaris_install.engine import InstallEngine

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()

_NULL = open("/dev/null", "r+")


class TestStripArchive(unittest.TestCase):
    """ test case to test the strip_archive() method of boot_archive_archive
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        filelist = ["/kernel/crypto/aes", "/kernel/crypto/amd64/aes",
                    "/kernel/genunix", "/kernel/amd64/genunix",
                    "/kernel/drv/cpuid.conf", "/lib/libfoo.so.1",
                    "/lib/amd64/libfoo.so.1",
                    "/platform/i86pc/kernel/cpu/cpu.generic",
                    "/platform/i86pc/kernel/cpu/amd64/cpu.generic"]
        self.tdir = testlib.create_filesystem(*filelist)
        self.tempdir = tempfile.mkdtemp(dir="/var/tmp", prefix="baa_strip_")
        os.chmod(self.tempdir, 0777)
        self.baa = BootArchiveArchive("Test BAA")
        self.baa.ba_build = self.tdir

        # strip archvie only functions on x86
        self.baa.kernel_arch = "x86"

    def tearDown(self):
        # remove both the transfer tempdir and temporary filesystem
        shutil.rmtree(self.tempdir, ignore_errors=True)
        shutil.rmtree(self.tdir, ignore_errors=True)
        InstallEngine._instance = None

    def test_bad_kernel_arch(self):
        """ test case for incorrect architecture specification
        """
        self.baa.kernel_arch = "sparc"
        self.assertRaises(RuntimeError, self.baa.strip_archive, self.tempdir,
                          32)

    def test_bad_bits(self):
        """ test case for invalid isa specification
        """
        self.assertRaises(RuntimeError, self.baa.strip_archive, self.tempdir,
                          16)

    def test_strip_32bit(self):
        """ test case for stripping the 32-bit x86 archive
        """
        self.baa.strip_archive(self.tempdir, 32)

        # change to the tempdir
        cwd = os.getcwd()
        os.chdir(self.tempdir)

        # walk the filesystem and ensure there are no directories ending in
        # amd64
        for sys_dir in ["kernel", "platform", "lib"]:
            for root, dirs, _none in os.walk(sys_dir):
                self.assert_("amd64" not in root)
                self.assert_("amd64" not in dirs)
        os.chdir(cwd)

    def test_strip_64bit(self):
        """ test case for stripping the 64-bit x86 archive
        """
        self.baa.strip_archive(self.tempdir, 64)

        # change to the tempdir
        cwd = os.getcwd()
        os.chdir(self.tempdir)

        # walk the filesystem and ensure there are no 32-bit files aside from
        # .conf files
        for sys_dir in ["kernel", "platform"]:
            for root, _none, files in os.walk(sys_dir):
                if not root.endswith("amd64"):
                    # 32 bit directory
                    for f in files:
                        # the only files should end in .conf
                        self.assert_(f.endswith(".conf"))
        os.chdir(cwd)


class TestCalculateBASize(unittest.TestCase):
    """ test case to test the calculate_ba_size() method of
    boot_archive_archive
    """

    def setUp(self):
        InstallEngine()
        # create a dummy filesystem with some files
        filelist = ["/fake/directory/"]
        self.tdir = testlib.create_filesystem(*filelist)

        self.baa = BootArchiveArchive("Test BAA")

    def tearDown(self):
        shutil.rmtree(self.tdir, ignore_errors=True)
        InstallEngine._instance = None

    def test_small_x86_archive(self):
        """ test case for an x86 archive less than 150M
        """
        self.baa.ba_build = self.tdir
        self.baa.kernel_arch = "x86"

        # create a small archive (< 150000) bytes
        f = os.path.join(self.tdir, "fake/directory", "small_file")
        cmd = ["/usr/sbin/mkfile", "100k", f]
        subprocess.check_call(cmd)

        size, _none = self.baa.calculate_ba_size(self.tdir)

        # verify the size
        by_hand = int(round(dir_size(self.tdir) / 1024 * 1.2))
        self.assert_(size == by_hand, "%d %d" % (size, by_hand))

    def test_large_sparc_archive(self):
        """ test case for a sparc archive greater than 150M
        """
        self.baa.ba_build = self.tdir
        self.baa.kernel_arch = "sparc"

        # create a large archive (> 150000) bytes
        f = os.path.join(self.tdir, "fake/directory", "small_file")
        cmd = ["/usr/sbin/mkfile", "160m", f]
        subprocess.check_call(cmd)

        size, _none = self.baa.calculate_ba_size(self.tdir)

        # verify the size
        by_hand = int(round(dir_size(self.tdir) / 1024 * 1.1))
        self.assert_(size == by_hand, "%d %d" % (size, by_hand))


class TestCreateRamdisksAndArchives(unittest.TestCase):
    """ test case to test the creation of ramdisks and archive files for
    boot_archive_archive
    """

    def setUp(self):
        InstallEngine()
        # create a dummy filesystem with some files
        self.pi_filelist = ["/platform/i86pc/", "/platform/sun4u/lib/fs/ufs/",
                            "/usr/platform/sun4u/lib/fs/ufs/",
                            "/etc/system", "/platform/i86pc/amd64/",
                            "/boot/solaris/filelist.ramdisk",
                            "/platform/sun4v/"]
        self.baa = BootArchiveArchive("Test BAA")
        self.baa.pkg_img_path = testlib.create_filesystem(*self.pi_filelist)
        self.baa.ba_build = self.baa.pkg_img_path
        self.baa.tmp_dir = tempfile.mkdtemp(dir="/var/tmp", prefix="baa_tmp_")
        self.baa.x86_dir = os.path.join(self.baa.tmp_dir, "x86")
        self.baa.amd64_dir = os.path.join(self.baa.tmp_dir, "amd64")
        os.mkdir(self.baa.x86_dir)
        os.mkdir(self.baa.amd64_dir)

    def tearDown(self):
        shutil.rmtree(self.baa.pkg_img_path, ignore_errors=True)
        shutil.rmtree(self.baa.tmp_dir, ignore_errors=True)
        if self.baa.lofi_list:
            for entry in self.baa.lofi_list:
                entry.destroy()

        InstallEngine._instance = None

    def test_create_x86_ramdisks(self):
        """ test case for x86 ramdisk creation
        """
        self.baa.kernel_arch = "x86"
        # set the nbpi to 1024
        self.baa.nbpi = 1024

        # create a 1MB file in both self.baa.x86_dir and amd64_dir
        cmd = ["/usr/sbin/mkfile", "1m", os.path.join(self.baa.x86_dir, "a")]
        subprocess.check_call(cmd)
        cmd = ["/usr/sbin/mkfile", "1m", os.path.join(self.baa.amd64_dir, "a")]
        subprocess.check_call(cmd)

        self.baa.create_ramdisks()
        self.assert_(len(self.baa.lofi_list) > 0)

        self.baa.create_archives()

    def test_create_sparc_ramdisks(self):
        """ test case for sparc ramdisk creation
        """
        self.baa.kernel_arch = "sparc"
        # set the nbpi to 1024
        self.baa.nbpi = 1024

        # create a 1MB file in both self.baa.x86_dir and amd64_dir
        cmd = ["/usr/sbin/mkfile", "1m", os.path.join(self.baa.ba_build, "a")]
        subprocess.check_call(cmd)

        self.baa.create_ramdisks()

        for entry in ["set root_is_ramdisk=1", "set ramdisk_size="]:
            cmd = ["/usr/bin/grep", entry, os.path.join(self.baa.ba_build,
                                                        "etc/system")]
            self.assert_(subprocess.call(cmd, stdout=_NULL, stderr=_NULL) == 0)

        self.assert_(len(self.baa.lofi_list) > 0)

        # create /platform/sun4u/lib/fs/ufs/bootblk from /etc/system
        bb = os.path.join(self.baa.pkg_img_path,
                          "platform/sun4u/lib/fs/ufs/bootblk")
        shutil.copy2("/etc/system", bb)
        os.chmod(bb, 0444)

        # create a symlink in /usr to the bootblock
        os.symlink(bb, os.path.join(self.baa.pkg_img_path,
                                    "usr/platform/sun4u/lib/fs/ufs/bootblk"))

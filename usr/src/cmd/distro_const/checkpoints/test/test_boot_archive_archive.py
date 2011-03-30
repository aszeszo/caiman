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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
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

        size = self.baa.calculate_ba_size(self.tdir)

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

        size = self.baa.calculate_ba_size(self.tdir)

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

    def tearDown(self):
        shutil.rmtree(self.baa.pkg_img_path, ignore_errors=True)
        shutil.rmtree(self.baa.tmp_dir, ignore_errors=True)
        if self.baa.lofi:
            self.baa.lofi.destroy()

        InstallEngine._instance = None

    def test_create_x86_ramdisks(self):
        """ test case for x86 ramdisk creation
        """
        self.baa.kernel_arch = "x86"
        # set the nbpi to 1024
        self.baa.nbpi = 1024

        # create a 1MB file 
        cmd = ["/usr/sbin/mkfile", "1m", os.path.join(self.baa.ba_build, "a")]
        subprocess.check_call(cmd)

        self.baa.create_ramdisks()
        self.assert_(self.baa.lofi is not None)

        self.baa.create_archives()

    def test_create_sparc_ramdisks(self):
        """ test case for sparc ramdisk creation
        """
        self.baa.kernel_arch = "sparc"
        # set the nbpi to 1024
        self.baa.nbpi = 1024

        # create a 1MB file in both self.baa.ba_build directory
        cmd = ["/usr/sbin/mkfile", "1m", os.path.join(self.baa.ba_build, "a")]
        subprocess.check_call(cmd)

        self.baa.create_ramdisks()

        for entry in ["set root_is_ramdisk=1", "set ramdisk_size="]:
            cmd = ["/usr/bin/grep", entry, os.path.join(self.baa.ba_build,
                                                        "etc/system")]
            self.assert_(subprocess.call(cmd, stdout=_NULL, stderr=_NULL) == 0)

        self.assert_(self.baa.lofi is not None)

        # create /platform/sun4u/lib/fs/ufs/bootblk from /etc/system
        bb = os.path.join(self.baa.pkg_img_path,
                          "platform/sun4u/lib/fs/ufs/bootblk")
        shutil.copy2("/etc/system", bb)
        os.chmod(bb, 0444)

        # create a symlink in /usr to the bootblock
        os.symlink(bb, os.path.join(self.baa.pkg_img_path,
                                    "usr/platform/sun4u/lib/fs/ufs/bootblk"))

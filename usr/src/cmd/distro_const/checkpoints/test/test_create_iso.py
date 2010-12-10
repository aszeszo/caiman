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

""" test_create_iso

 Test program for create_iso
"""

import os
import os.path
import shutil
import unittest

import testlib

from subprocess import CalledProcessError

from solaris_install.distro_const.checkpoints.create_iso import CreateISO
from solaris_install.engine import InstallEngine


class TestISOSetup(unittest.TestCase):
    """ test case for testing the setup() method of CreateISO
    """

    def setUp(self):
        InstallEngine()
        self.ba_filelist = [".volsetid"]
        self.pi_filelist = ["a", "b"]
        self.c_iso = CreateISO("Test Create ISO")
        self.c_iso.distro_name = "distro name"
        self.c_iso.partial_distro_name = self.c_iso.distro_name
        self.c_iso.dist_iso = "/var/tmp/dist.iso"
        self.c_iso.ba_build = testlib.create_filesystem(*self.ba_filelist)
        self.c_iso.pkg_img_path = testlib.create_filesystem(*self.pi_filelist)
        self.c_iso.arch = "i386"
        self.c_iso.media_dir = "/var/tmp/missing"

    def tearDown(self):
        if os.path.isdir(self.c_iso.media_dir):
            os.rmdir(self.c_iso.media_dir)
        for entry in [self.c_iso.pkg_img_path, self.c_iso.ba_build]:
            shutil.rmtree(entry, ignore_errors=True)
        InstallEngine._instance = None

    def test_missing_media_dir(self):
        if os.path.isdir(self.c_iso.media_dir):
            os.rmdir(self.c_iso.media_dir)
        self.c_iso.setup()
        self.assert_(os.path.isdir(self.c_iso.media_dir))

    def test_x86_mkisofs_cmd(self):
        self.c_iso.setup()
        self.assert_("boot/grub/stage2_eltorito" in self.c_iso.mkisofs_cmd)
        self.assert_("-no-emul-boot" in self.c_iso.mkisofs_cmd)
        self.assert_("-no-iso-translate" in self.c_iso.mkisofs_cmd)

    def test_sparc_mkisofs_cmd(self):
        self.c_iso.arch = "sparc"
        self.c_iso.setup()
        self.assert_("-ldots" in self.c_iso.mkisofs_cmd)
        self.assert_("-B" in self.c_iso.mkisofs_cmd)


class TestPrepareBootblock(unittest.TestCase):
    """ test method for testing the prepare_bootblock method of CreateISO
    """

    def setUp(self):
        InstallEngine()
        self.outblock = "/var/tmp/bootblock"
        self.c_iso = CreateISO("Test Create ISO")

    def tearDown(self):
        if os.path.isfile(self.outblock):
            os.remove(self.outblock)
        InstallEngine._instance = None

    def test_prepare_bootblock(self):
        self.c_iso.prepare_bootblock("/dev/null", self.outblock)
        self.assert_(os.path.isfile(self.outblock))
        self.assert_(os.path.getsize(self.outblock) > 0)


class TestExecuteMkisofs(unittest.TestCase):
    """ test method for testing the run_mkisofs method of CreateISO
    """

    def setUp(self):
        InstallEngine()
        self.c_iso = CreateISO("Test Create ISO")

    def tearDown(self):
        InstallEngine._instance = None

    def test_execute(self):
        self.c_iso.mkisofs_cmd = ["/usr/bin/cat", "/etc/motd"]
        self.c_iso.run_mkisofs()

    def test_bad_execute(self):
        self.c_iso.mkisofs_cmd = ["/usr/bin/grep", "nothere", "/etc/system"]
        self.assertRaises(CalledProcessError, self.c_iso.run_mkisofs)


class TestTimeStampMedia(unittest.TestCase):
    """ test method for testing the create_additional_timestamp method of
    CreateISO
    """

    def setUp(self):
        InstallEngine()
        self.media_filelist = ["a.iso"]
        self.c_iso = CreateISO("Test Create ISO")
        self.c_iso.media_dir = testlib.create_filesystem(*self.media_filelist)
        self.c_iso.dist_iso = os.path.join(self.c_iso.media_dir, "a.iso")
        self.c_iso.partial_distro_name = "foo"
        self.incr_iso = os.path.join(self.c_iso.media_dir,
                                     self.c_iso.partial_distro_name) + ".iso"

    def tearDown(self):
        if os.path.isdir(self.c_iso.media_dir):
            shutil.rmtree(self.c_iso.media_dir, ignore_errors=True)
        InstallEngine._instance = None

    def test_existing_iso(self):
        with open(self.incr_iso, "w"):
            pass
        self.c_iso.create_additional_timestamp()
        self.assert_(os.path.islink(self.incr_iso))
        dist_iso_statinfo = os.stat(os.path.join(self.c_iso.media_dir, 
                                    self.c_iso.dist_iso))
        incr_iso_statinfo = os.stat(self.incr_iso)
        self.assert_(dist_iso_statinfo.st_ino == incr_iso_statinfo.st_ino)

    def test_nonexisting_iso(self):
        self.c_iso.create_additional_timestamp()
        self.assert_(os.path.islink(self.incr_iso))
        dist_iso_statinfo = os.stat(os.path.join(self.c_iso.media_dir, 
                                    self.c_iso.dist_iso))
        incr_iso_statinfo = os.stat(self.incr_iso)
        self.assert_(dist_iso_statinfo.st_ino == incr_iso_statinfo.st_ino)

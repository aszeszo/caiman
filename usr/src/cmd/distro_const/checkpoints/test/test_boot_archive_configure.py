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

""" test_boot_archive_configure

 Test program for boot_archive_configure

"""

import os
import os.path
import tempfile
import shutil
import stat
import subprocess
import unittest

import testlib

import solaris_install.distro_const.checkpoints.boot_archive_configure as bac
from solaris_install.distro_const.checkpoints.boot_archive_configure \
    import BootArchiveConfigure, AIBootArchiveConfigure, \
           LiveCDBootArchiveConfigure
from solaris_install.engine import InstallEngine

_NULL = open("/dev/null", "r+")


class TestConfigureSymlinks(unittest.TestCase):
    """ test case to test the correct configuration of symlinks
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.pi_filelist = ["/etc/zones/index", "/etc/mime.types",
                            "/var/adm/wtmpx", "/var/adm/spellhist",
                            "/var/lib/gdm/", "/var/log/gdm/",
                            "/var/fake1/fake2/fake3/fake4/fake5/fakefile"]
        self.ba_filelist = ["/etc/zones/index", "/var/adm/wtmpx",
                            "/var/adm/spellhist"]
        args = {"image_type": "test"}
        self.bac = BootArchiveConfigure(name="Test BAC", arg=args)
        self.bac.pkg_img_path = testlib.create_filesystem(*self.pi_filelist)
        self.bac.ba_build = testlib.create_filesystem(*self.ba_filelist)

    def tearDown(self):
        for entry in [self.bac.pkg_img_path, self.bac.ba_build]:
            shutil.rmtree(entry, ignore_errors=True)
        InstallEngine._instance = None

    def test_basic_symlinks(self):
        # create a simple symlink for testing
        os.symlink("/dev/null", os.path.join(self.bac.pkg_img_path,
                                             "etc/symlink"))

        # simply test that the files in pi_filelist that are not in ba_filelist
        # are symlinks
        self.bac.configure_symlinks()

        # walk each entry in the pi_filelist
        for entry in self.pi_filelist:
            # skip the entries in the ba_filelist
            if entry in self.ba_filelist:
                continue

            path = os.path.join(self.bac.ba_build, entry.lstrip("/"))

            if entry.endswith("/"):
                # if it's a directory, verify it exists
                self.assert_(os.path.isdir(path))
            else:
                # otherwise verify it's a symlink
                self.assert_(os.path.islink(path))

    def test_permissions(self):
        # test non-standard permissions of directories like /var/lib/gdm being
        # 1770 gdm:gdm

        # change var/lib/gdm to 1770
        testdir = "var/lib/gdm"
        os.chmod(os.path.join(self.bac.pkg_img_path, testdir), 01770)

        # configure the symlinks
        self.bac.configure_symlinks()

        # verify the stat of the two directories is the same
        pi_statinfo = os.stat(os.path.join(self.bac.pkg_img_path, testdir))
        ba_statinfo = os.stat(os.path.join(self.bac.ba_build, testdir))

        self.assert_(pi_statinfo.st_mode == ba_statinfo.st_mode)

    def test_uidgid(self):
        # test changing the uid/gid of a directory to something other than
        # root:root

        # change var/lib/gdm to gdm:gdm (uid: 50, gid: 50)
        testdir = "var/lib/gdm"
        os.chown(os.path.join(self.bac.pkg_img_path, testdir), 50, 50)

        # configure the symlinks
        self.bac.configure_symlinks()

        # verify the stat of the two directories is the same
        pi_statinfo = os.stat(os.path.join(self.bac.pkg_img_path, testdir))
        ba_statinfo = os.stat(os.path.join(self.bac.ba_build, testdir))

        self.assert_(pi_statinfo.st_uid == ba_statinfo.st_uid)
        self.assert_(pi_statinfo.st_gid == ba_statinfo.st_gid)


class TestConfigureSystem(unittest.TestCase):
    """ test case to test the correct configuration of the boot archive
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.ba_filelist = ["/etc/default/init", "/etc/inet/hosts",
                            "/etc/nodename", "/etc/svc/", "/usr/bin/"]
        args = {"image_type": "test"}
        self.bac = BootArchiveConfigure(name="Test BAC", arg=args)
        self.bac.ba_build = testlib.create_filesystem(*self.ba_filelist)
        self.bac.pkg_img_path = tempfile.mkdtemp(dir="/var/tmp",
                                                 prefix="bac_conf_system_")
        self.bac.file_defaults = os.path.join(os.path.dirname(
            os.path.abspath(bac.__file__)), "defaultfiles")

        # write some info to etc/default/init
        self.init_file = os.path.join(self.bac.ba_build, "etc/default/init")
        with open(self.init_file, "w+") as fh:
            fh.write("TZ=foobar\n")

        # write some info to etc/inet/hosts
        self.hosts_file = os.path.join(self.bac.ba_build, "etc/inet/hosts")
        with open(self.hosts_file, "w+") as fh:
            fh.write("127.0.0.1\thostname\n")

        # touch the smf repo
        os.makedirs(os.path.join(self.bac.pkg_img_path, "etc/svc"))
        self.smf_repo = os.path.join(self.bac.pkg_img_path,
                                     "etc/svc/repository.db")
        with open(self.smf_repo, "w+") as fh:
            pass

    def tearDown(self):
        for entry in [self.bac.pkg_img_path, self.bac.ba_build]:
            shutil.rmtree(entry, ignore_errors=True)
        InstallEngine._instance = None

    def test_basic_configure(self):
        # execute the method
        self.bac.configure_system()

        # verify /dev exists
        self.assert_(os.path.isdir(os.path.join(self.bac.ba_build, "dev")))

        # verify files were created
        for entry in ["reconfigure", "etc/coreadm.conf", "etc/rtc_config",
                      "etc/svc/repository.db", "test"]:
            self.assert_(os.path.isfile(os.path.join(self.bac.ba_build,
                                                     entry)))

        # verify the TZ is set correctly in etc/default/init
        self.assert_(os.path.isfile(os.path.join(self.bac.ba_build,
                                                 "etc/default/init")))
        found = False
        with open(os.path.join(self.bac.ba_build, "etc/default/init")) as fh:
            if "TZ=GMT" in fh.readline():
                found = True
        self.assert_(found)

        # verify the directories were created
        for d in ["tmp", "proc", "mnt", "mnt/misc", "mnt/pkg", ".cdrom"]:
            self.assert_(os.path.isdir(os.path.join(self.bac.ba_build, d)))

        # verify /bin and /opt are symlinks
        for entry in ["bin", "opt"]:
            self.assert_(os.path.islink(os.path.join(self.bac.ba_build,
                                                     entry)))

        # verify .volsetid
        volsetid = os.path.join(self.bac.ba_build, ".volsetid")
        self.assert_(os.path.isfile(volsetid))
        self.assert_(os.path.getsize(volsetid) > 0)
        volsetid_statinfo = os.stat(volsetid)
        m = volsetid_statinfo.st_mode
        self.assert_(volsetid_statinfo.st_uid == 0)
        self.assert_(volsetid_statinfo.st_gid == 0)
        # verify the file is 0440
        self.assert_((m & stat.S_IRUSR & stat.S_IRGRP) == 0)


class TestConfigureGDM(unittest.TestCase):
    """ test case to test the configuration of GDM for a LiveCD distribution
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        self.pi_filelist = ["/etc/gdm/", "/save/", "/jack/",
                            "/etc/gdm/custom.conf"]
        self.ba_filelist = ["/etc/gdm/custom.conf"]
        args = {"image_type": "test"}
        self.bac = LiveCDBootArchiveConfigure(name="Test BAC", arg=args)
        self.bac.ba_build = testlib.create_filesystem(*self.ba_filelist)
        self.bac.pkg_img_path = testlib.create_filesystem(*self.pi_filelist)

        self.gdm_conf = os.path.join(self.bac.pkg_img_path,
                                     "etc/gdm/custom.conf")
        with open(self.gdm_conf, "w+") as fh:
            fh.write("# GDM configuration storage\n\n")
            fh.write("[daemon]\n\n")
            fh.write("[security]\n\n")

    def tearDown(self):
        for entry in [self.bac.pkg_img_path, self.bac.ba_build]:
            shutil.rmtree(entry, ignore_errors=True)
        InstallEngine._instance = None

    def test_configure_gdm(self):
        # configure gdm
        self.bac.configure_gdm()

        # verify save/etc/gdm/custom.conf exists in pkg_image
        self.assert_(os.path.isfile(os.path.join(self.bac.pkg_img_path,
                                                 "save/etc/gdm/custom.conf")))

        # verify the entries in custom.conf
        for entry in ["AutomaticLoginEnable\=true", "AutomaticLogin=jack",
                      "GdmXserverTimeout=30"]:
            cmd = ["/usr/bin/grep", entry, self.gdm_conf]
            self.assert_(subprocess.call(cmd, stdout=_NULL, stderr=_NULL) == 0,
                         " ".join(cmd))


class TestConfigureUserAttr(unittest.TestCase):
    """ test case to test the configuration of /etc/user_attr
    """

    def setUp(self):
        # create a dummy filesystem with some files created in the proper
        # location
        InstallEngine()
        args = {"image_type": "test"}
        self.bac = LiveCDBootArchiveConfigure(name="Test BAC", arg=args)
        self.ba_filelist = ["/etc/user_attr", "/etc/sudoers"]
        self.pi_filelist = ["/save/"]
        self.bac.ba_build = testlib.create_filesystem(*self.ba_filelist)
        self.bac.pkg_img_path = testlib.create_filesystem(*self.pi_filelist)

        self.user_attr = os.path.join(self.bac.ba_build, "etc/user_attr")
        with open(self.user_attr, "a+") as fh:
            fh.write("dladm::::auths=solaris.smf.manage.wpa,solaris.smf.modify")
            fh.write("\nroot::::auths=solaris.*,solaris.grant;profiles=All\n")

    def tearDown(self):
        shutil.rmtree(self.bac.ba_build, ignore_errors=True)
        shutil.rmtree(self.bac.pkg_img_path, ignore_errors=True)
        InstallEngine._instance = None

    def test_configure_user_attr(self):
        # configure /etc/user_attr
        self.bac.configure_user_attr_and_sudoers()

        # walk the file and verify root and Jack's entry
        with open(self.user_attr) as fh:
            line = fh.readline()
            if line.startswith("root"):
                self.assert_("type=role" in line)
            if line.startswith("jack"):
                self.assert_("profiles=Software Installation;roles=root" in \
                             line)

        # verify Jack is in /etc/sudoers
        with open(os.path.join(self.bac.ba_build, "etc/sudoers")) as fh:
            data = fh.read().splitlines()

        for line in data:
            if line.startswith("jack"):
                self.assert_("jack ALL=(ALL) ALL" in line)
                break

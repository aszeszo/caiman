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

""" test_zpool_vdevs.py - test suite to exercise creation of zpools via
instantiation.py
"""
import os
import unittest

import solaris_install.target.vdevs as vdevs

from solaris_install import Popen
from solaris_install.engine.test import engine_test_utils
from solaris_install.target import instantiation, Target
from solaris_install.target.logical import *
from solaris_install.target.physical import *
from solaris_install.target.size import Size


MKFILE = "/usr/sbin/mkfile"


class TestZpoolVdevs(unittest.TestCase):
    """ Test case for exercising creation of Zpool objects and validating
    against real zpools
    """
    def create_file(self, path, size="64m"):
        # look for the file first.  if it exists, remove if
        if os.path.isfile(path):
            os.unlink(path)

        # create the file with mkfile
        cmd = [MKFILE, size, path]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)

        # add the file to the list to destroy later
        self.file_list.append(path)

    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # list of created files for zpool vdev usage
        self.file_list = []

        # list of created zpools
        self.zpool_list = []

        # create the basic DOC structure
        self.target = Target(Target.DESIRED)
        self.logical = Logical("logical")
        self.target.insert_children(self.logical)

        self.doc.insert_children(self.target)

    def tearDown(self):
        engine_test_utils.reset_engine()

        # walk the zpool_list and call destroy
        for zpool in self.zpool_list:
            zpool.destroy(dry_run=False, force=True)

        # walk the file_list call unlink() on them
        for f in self.file_list:
            if os.path.isfile(f):
                os.unlink(f)

    def test_simple_vdev(self):
        """ 1 single vdev
        """
        # create a single 64M file
        f1 = "/var/tmp/ti_file_1"
        self.create_file(f1)

        # create a new Disk object
        d = Disk("disk")
        d.ctd = f1
        d.in_zpool = "ti_zpool_test"
        d.whole_disk = True
        self.target.insert_children(d)

        # create a new Zpool object
        zpool = self.logical.add_zpool("ti_zpool_test")

        # create the zpool and store it for later teardown
        try:
            t = instantiation.TargetInstantiation("test_ti")
            t.execute(dry_run=False)
            self.zpool_list.append(zpool)
        except Exception as err:
            import traceback
            print traceback.print_exc()
            self.fail(str(err))

        # pull the vdevs and verify
        vdev_map = vdevs._get_vdev_mapping(zpool.name)

        # verify the map is correct
        self.assertTrue("root" in vdev_map)
        self.assertEquals(1, len(vdev_map["root"]))
        self.assertEquals([f1], vdev_map["root"])

    def test_mirror_vdevs(self):
        """ 2 mirrored root disks
        """
        # create two 64M files
        f1 = "/var/tmp/ti_file_1"
        self.create_file(f1)

        f2 = "/var/tmp/ti_file_2"
        self.create_file(f2)

        # create two disk objects
        d1 = Disk("disk1")
        d1.ctd = f1
        d1.in_zpool = "ti_zpool_test"
        d1.in_vdev = "mirror-0"
        d1.whole_disk = True

        d2 = Disk("disk2")
        d2.ctd = f2
        d2.in_zpool = "ti_zpool_test"
        d2.in_vdev = "mirror-0"
        d2.whole_disk = True

        self.target.insert_children([d1, d2])

        # create a new Zpool object
        zpool = self.logical.add_zpool("ti_zpool_test")
        zpool.add_vdev("mirror-0", "mirror")

        # create the zpool and store it for later teardown
        try:
            t = instantiation.TargetInstantiation("test_ti")
            t.execute(dry_run=False)
            self.zpool_list.append(zpool)
        except Exception as err:
            import traceback
            print traceback.print_exc()
            self.fail(str(err))

        # pull the vdevs and verify
        vdev_map = vdevs._get_vdev_mapping(zpool.name)

        # verify the map is correct
        self.assertTrue("mirror-0" in vdev_map)
        self.assertEquals(2, len(vdev_map["mirror-0"]))
        self.assertEquals([f1, f2], vdev_map["mirror-0"])

    def test_complex_vdevs1(self):
        """ 10 disks: Mirrored root + raidz datapool with log and spare
        """
        # create 10 files
        for i in range(1, 11):
            f = "/var/tmp/ti_file_%d" % i
            self.create_file(f)

        # create 10 disk objects
        for i in range(1, 11):
            d = Disk("disk%d" % i)
            d.ctd = self.file_list[i - 1]
            if i in [1, 2]:
                d.in_zpool = "ti_zpool_test_root"
                d.in_vdev = "root-mirror"
            elif i in [3, 4, 5, 6]:
                d.in_zpool = "ti_zpool_test_datapool"
                d.in_vdev = "datapool-raidz"
            elif i in [7, 8]:
                d.in_zpool = "ti_zpool_test_datapool"
                d.in_vdev = "datapool-log"
            elif i in [9, 10]:
                d.in_zpool = "ti_zpool_test_datapool"
                d.in_vdev = "datapool-spare"
            self.target.insert_children(d)

        # create two new zpool objects
        zpool1 = self.logical.add_zpool("ti_zpool_test_root")
        zpool1.add_vdev("root-mirror", "mirror")

        zpool2 = self.logical.add_zpool("ti_zpool_test_datapool")
        zpool2.add_vdev("datapool-raidz", "raidz")
        zpool2.add_vdev("datapool-log", "log")
        zpool2.add_vdev("datapool-spare", "spare")

        # create the zpools and store it for later teardown
        try:
            t = instantiation.TargetInstantiation("test_ti")
            t.execute(dry_run=False)
            self.zpool_list.append(zpool1)
            self.zpool_list.append(zpool2)
        except Exception as err:
            import traceback
            print traceback.print_exc()
            self.fail(str(err))

        # pull the vdevs and verify
        vdev_map1 = vdevs._get_vdev_mapping(zpool1.name)

        # verify the map is correct
        self.assertTrue("mirror-0" in vdev_map1)
        self.assertTrue(len(vdev_map1["mirror-0"]) == 2)
        self.assertTrue(vdev_map1["mirror-0"] == self.file_list[:2])

        vdev_map2 = vdevs._get_vdev_mapping(zpool2.name)
        self.assertTrue("spare" in vdev_map2)
        self.assertTrue("logs" in vdev_map2)
        self.assertTrue("raidz-0" in vdev_map2)
        self.assertTrue(2, len(vdev_map2["spare"]))
        self.assertTrue(2, len(vdev_map2["logs"]))
        self.assertTrue(4, len(vdev_map2["raidz-0"]))
        self.assertEquals(self.file_list[-2:], vdev_map2["spare"])
        self.assertEquals(self.file_list[6:8], vdev_map2["logs"])
        self.assertEquals(self.file_list[2:6], vdev_map2["raidz-0"])

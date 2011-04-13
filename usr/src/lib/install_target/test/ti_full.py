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

"""
ti_full.py - tests Target Instantiation with dry_run set to False.

*** THIS *WILL* REPARTITION THE GIVEN DISK AND DESTROY ALL DATA CONTAINED ON
IT.  DO NOT RUN THIS TEST AS PART OF A NIGHTLY TEST SUITE RUN UNLESS YOU KNOW
WHAT YOU ARE DOING.  ***
"""
import ctypes as C
import fcntl
import os
import platform
import unittest

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc

from nose.plugins.skip import SkipTest

from solaris_install import Popen
from solaris_install.engine.test import engine_test_utils
from solaris_install.engine import InstallEngine
from solaris_install.target import Target
from solaris_install.target.libdiskmgt.const import ALIAS
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.physical import Disk, DiskGeometry, DiskProp
from solaris_install.target.size import Size


GBSECTOR = long(1024 * 1024 * 1024 / 512)  # 1 GB of sectors

# CTD of the disk to repartition.  *** THE DATA ON THE DISK WILL BE DESTROYED
MASTER_CTD = "c8t3d0"   # leeroy.us.oracle.com - x86
#MASTER_CTD = "c4t2d0"   # t2k-brm-09.us.oracle.com - sparc


class TestTI(unittest.TestCase):
    # set the arch
    if platform.processor() == "i386":
        ARCH = "x86"
    else:
        ARCH = "sparc"

    def __init__(self, methodName="runTest"):
        unittest.TestCase.__init__(self, methodName)

        # extract drive informtion to construct a bare-bones DOC object
        dmd = diskmgt.descriptor_from_key(ALIAS, MASTER_CTD)
        alias = diskmgt.DMAlias(dmd.value)
        drive = alias.drive
        dma = drive.media.attributes

        if dma.ncylinders is None:
            raise RuntimeError("Unable to process disk label.  Please " +
                               "place a VTOC label on the disk.")

        # get the maximum size of the disk
        fd = os.open("/dev/rdsk/" + MASTER_CTD + "s2", os.O_RDONLY|os.O_NDELAY)
        try:
            media_info = drive.DKMinfo()
            fcntl.ioctl(fd, diskmgt.DKIOCGMEDIAINFO, C.addressof(media_info))
        except IOError as error:
            print 'ioctl failed: ', str(error)
            raise
        finally:
            os.close(fd)

        # set the basic geometry
        self.disk = Disk(MASTER_CTD)
        self.disk.ctd = MASTER_CTD
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(str(media_info.dki_capacity) +
                                            Size.sector_units)
        self.disk_size = self.disk.disk_prop.dev_size.sectors

        self.disk.geometry = DiskGeometry(dma.blocksize,
                                          dma.nheads * dma.nsectors)
        self.disk.geometry.ncyl = dma.ncylinders
        self.disk.geometry.nhead = dma.nheads
        self.disk.geometry.nsectors = dma.nsectors

        self.target = Target(Target.DESIRED)
        self.target.insert_children(self.disk)

    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile
        self.doc.insert_children(self.target)

    def tearDown(self):
        engine_test_utils.reset_engine()

    def get_fdisk(self):
        cmd = ["/usr/sbin/fdisk", "-W", "-", "/dev/rdsk/" + MASTER_CTD + "p0"]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        if p.returncode != 0:
            raise RuntimeError(" ".join(cmd) + " failed")
        return p.stdout, p.stderr

    def get_prtvtoc(self):
        cmd = ["/usr/sbin/prtvtoc", "/dev/rdsk/" + MASTER_CTD + "s0"]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        if p.returncode != 0:
            raise RuntimeError(" ".join(cmd) + " failed")
        return p.stdout, p.stderr

    def test_x86_single_partition(self):
        if self.ARCH != "x86":
            raise SkipTest("test not supported on sparc")

        # set the partition size to 50% of the disk size
        partition_size = int(float(self.disk_size) / 2.0)
        p = self.disk.add_partition(1, self.disk.geometry.cylsize,
                                    partition_size, Size.sector_units)

        # register a TI checkpoint and execute it
        self.engine.register_checkpoint("ti",
            "solaris_install/target/instantiation", "TargetInstantiation")
        status, failed_cp = self.engine.execute_checkpoints()

        if status != InstallEngine.EXEC_SUCCESS:
            err = errsvc.get_errors_by_mod_id(failed_cp[0])[0]
            self.fail(err.error_data[liberrsvc.ES_DATA_EXCEPTION])

        # verify the data
        outs, errs = self.get_fdisk()
        lines = [line.strip().split() for line in outs.splitlines() \
                 if line and not line.startswith("*")]

        # by default, fdisk will show a minimum of 4 lines, 1 for each primary
        # partition.  Since we're only testing line 1, ignore the rest
        self.assertEqual(lines[0][0], str(p.part_type))
        self.assertEqual(lines[0][8], str(self.disk.geometry.cylsize))
        self.assertEqual(lines[0][9], str(p.size.sectors))

    def test_x86_five_partitions(self):
        if self.ARCH != "x86":
            raise SkipTest("test not supported on sparc")

        # set the partition size of each of the partitions to 10% of the disk
        p_size = int(float(self.disk_size) * 0.10)
        norm_size = p_size / self.disk.geometry.cylsize * \
            self.disk.geometry.cylsize

        # add 5 partitions.  Partition 1 will be the extended partition and
        # partition 5 will be the solaris2 partition
        self.disk.add_partition(1, self.disk.geometry.cylsize, p_size,
            Size.sector_units, 15)

        # linux native partition
        self.disk.add_partition(2, self.disk.geometry.cylsize + p_size + 1,
            p_size, Size.sector_units, 131)

        # linux native partition
        self.disk.add_partition(3,
            self.disk.geometry.cylsize + (2 * p_size) + 2, p_size,
            Size.sector_units, 131)

        # linux native partition
        self.disk.add_partition(4,
            self.disk.geometry.cylsize + (3 * p_size) + 3, p_size,
            Size.sector_units, 131)

        # logical partition inside partition 1 with a partition type of
        # solaris2.  Allow for an offset on either side of 63 sectors
        self.disk.add_partition(5, self.disk.geometry.cylsize + 63,
            p_size - 63, Size.sector_units)

        # register a TI checkpoint and execute it
        self.engine.register_checkpoint("ti",
            "solaris_install/target/instantiation", "TargetInstantiation")
        status, failed_cp = self.engine.execute_checkpoints()

        if status != InstallEngine.EXEC_SUCCESS:
            err = errsvc.get_errors_by_mod_id(failed_cp[0])[0]
            self.fail(err.error_data[liberrsvc.ES_DATA_EXCEPTION])

        # verify the data
        outs, errs = self.get_fdisk()
        lines = [line.strip().split() for line in outs.splitlines() \
                 if line and not line.startswith("*")]

        # verify the partition types (first column)
        self.assertEqual(lines[0][0], "15")
        self.assertEqual(lines[1][0], "131")
        self.assertEqual(lines[2][0], "131")
        self.assertEqual(lines[3][0], "131")
        self.assertEqual(lines[4][0], "191")

        # verify the size (10th column)
        self.assertEqual(lines[0][9], str(norm_size))
        self.assertEqual(lines[1][9], str(norm_size))
        self.assertEqual(lines[2][9], str(norm_size))
        self.assertEqual(lines[3][9], str(norm_size))
        self.assertEqual(lines[4][9], str(norm_size - 63))

    def test_x86_single_slice(self):
        if self.ARCH != "x86":
            raise SkipTest("test not supported on sparc")

        # set the partition size to 50% of the disk size
        p_size = int(float(self.disk_size) / 2.0)

        # add a partition at start_sector CYLSIZE
        part = self.disk.add_partition(1, self.disk.geometry.cylsize, p_size,
                                       Size.sector_units)

        # add a 1 GB slice to the partition
        part.add_slice(0, self.disk.geometry.cylsize, 1, Size.gb_units)

        # register a TI checkpoint and execute it
        self.engine.register_checkpoint("ti",
            "solaris_install/target/instantiation", "TargetInstantiation")
        status, failed_cp = self.engine.execute_checkpoints()

        # verify the data
        outs, errs = self.get_prtvtoc()
        lines = [line.strip().split() for line in outs.splitlines() \
                 if line and not line.startswith("*")]

        self.assertEqual(lines[0][3], str(self.disk.geometry.cylsize))
        self.assertEqual(lines[0][4], str(GBSECTOR))

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

import ctypes as C
import os
import os.path
import unittest
from solaris_install.engine.test import engine_test_utils
from solaris_install.target import instantiation, Target
from solaris_install.target.libadm import const, cstruct, extvtoc
from solaris_install.target.logical import *
from solaris_install.target.physical import *
from solaris_install.target.size import Size

BLOCKSIZE = 512
CYLSIZE = 1024
GBSECTOR = long(1024 * 1024 * 1024 / 512)  # 1 GB of sectors


class TestDiskPartition(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # create some DOC objects
        self.target = Target(Target.DESIRED)
        self.doc.insert_children(self.target)

        self.disk = Disk("disk")
        self.disk.ctd = "c8t1d0"
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(str(200) + Size.gb_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE
        self.disk.disk_prop.cylsize = CYLSIZE
        self.disk.disk_geometry = DiskGeometry()
        self.target.insert_children(self.disk)

    def tearDown(self):
        engine_test_utils.reset_engine()

    def test_create_single_partition(self):
        part = Partition(2)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.sector_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        self.disk.insert_children(part)

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_create_multiple_partitions(self):
        part = Partition(2)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.sector_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        part2 = Partition(4)
        part2.action = "create"
        part2.start_sector = 50 * GBSECTOR + 50
        part2.size = Size("50" + Size.sector_units)
        part2.part_type = "extended"
        part2.bootid = 0

        self.disk.insert_children([part, part2])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_create_destroy_multiple_partitions(self):
        part = Partition(1)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.sector_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        part2 = Partition(2)
        part2.action = "destroy"
        part2.start_sector = 50 * GBSECTOR + 51
        part2.size = Size("50" + Size.sector_units)
        part2.part_type = "primary"
        part2.bootid = 0

        self.disk.insert_children([part, part2])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_noname_partition(self):
        part = Partition(None)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.sector_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        self.disk.insert_children(part)

        t = instantiation.TargetInstantiation("test_ti")
        self.assertRaises(RuntimeError, t.execute, dry_run=True)


class TestDiskSlice(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # create some DOC objects
        self.target = Target(Target.DESIRED)
        self.doc.insert_children(self.target)

        self.disk = Disk("disk")
        self.disk.ctd = "c8t1d0"
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(str(200) + Size.gb_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE
        self.disk.disk_prop.cylsize = CYLSIZE
        self.disk.disk_geometry = DiskGeometry()
        self.target.insert_children(self.disk)

    def tearDown(self):
        engine_test_utils.reset_engine()

    def test_update_vtoc(self):
        slice1 = Slice(1)
        slice1.action = "create"
        slice1.size = Size("4" + Size.sector_units)
        slice1.start_sector = 1
        slice1.tag = const.V_BOOT
        slice1.flag = const.V_RONLY

        slice2 = Slice(2)
        slice2.action = "create"
        slice2.size = Size("8" + Size.sector_units)
        slice2.start_sector = 10
        slice2.tag = const.V_BACKUP
        slice2.flag = const.V_RONLY

        slice3 = Slice(3)
        slice3.action = "preserve"
        slice3.size = Size("20" + Size.sector_units)
        slice3.start_sector = 20
        slice3.tag = const.V_USR
        slice3.flag = const.V_UNMNT

        slices_list = [slice1, slice2, slice3]
        extvtocp = C.pointer(cstruct.extvtoc())
        c = extvtocp.contents
        self.disk.geometry.ncly = 5
        self.disk._update_vtoc_struct(extvtocp, slices_list, 10)
        self.failIf(\
            c.v_part[int(slice1.name)].p_size != slice1.size.sectors or \
            c.v_part[int(slice1.name)].p_start != slice1.start_sector or \
            c.v_part[int(slice1.name)].p_tag != slice1.tag or \
            c.v_part[int(slice1.name)].p_flag != slice1.flag)

        self.failIf(\
            c.v_part[int(slice2.name)].p_size != slice2.size.sectors or \
            c.v_part[int(slice2.name)].p_start != slice2.start_sector or \
            c.v_part[int(slice2.name)].p_tag != slice2.tag or \
            c.v_part[int(slice2.name)].p_flag != slice2.flag)

        self.failIf(\
            c.v_part[int(slice3.name)].p_size != slice3.size.sectors or \
            c.v_part[int(slice3.name)].p_start != slice3.start_sector or \
            c.v_part[int(slice3.name)].p_tag != slice3.tag or \
            c.v_part[int(slice3.name)].p_flag != slice3.flag)

    def test_slice_on_part(self):
        self.disk.geometry.nheads = 24
        self.disk.geometry.nsectors = 848
        self.disk.geometry.blocksize = 512
        self.disk.geometry.ncyl = 14089

        part = Partition(2)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.gb_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        self.disk.insert_children(part)

        slice1 = Slice(1)
        slice1.action = "create"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE
        slice1.tag = const.V_USR
        slice1.flag = 0

        part.insert_children(slice1)

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_swap_slices(self):
        self.disk.geometry.nheads = 24
        self.disk.geometry.nsectors = 848
        self.disk.geometry.blocksize = 512
        self.disk.geometry.ncyl = 14089

        part = Partition(2)
        part.action = "create"
        part.start_sector = 0
        part.size = Size("50" + Size.gb_units)
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE

        self.disk.insert_children(part)

        slice1 = Slice(1)
        slice1.action = "create"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE
        slice1.tag = const.V_SWAP
        slice1.is_swap = True

        slice2 = Slice(2)
        slice2.action = "create"
        slice2.size = Size(str(GBSECTOR) + Size.sector_units)
        slice2.start_sector = slice1.start_sector + slice1.size.sectors
        slice2.tag = const.V_SWAP
        slice2.is_swap = True

        part.insert_children([slice1, slice2])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))


class TestDiskLabeling(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # create some DOC objects
        self.target = Target(Target.DESIRED)
        self.doc.insert_children(self.target)

        self.disk = Disk("disk")
        self.disk.ctd = "c8t1d0"
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.blocksize = BLOCKSIZE
        self.disk.disk_prop.cylsize = CYLSIZE
        self.disk.disk_geometry = DiskGeometry()
        self.disk.disk_prop.dev_size = Size("500gb")
        self.target.insert_children(self.disk)

    def tearDown(self):
        engine_test_utils.reset_engine()

    def test_part_preserve(self):
        part = Partition(1)
        part.action = "preserve"
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE
        part.size = Size("0b")
        part.start_sector = 0

        part2 = Partition(2)
        part2.action = "preserve"
        part2.part_type = "primary"
        part2.bootid = 0
        part2.size = Size("0b")
        part2.start_sector = 0

        self.disk.insert_children([part, part2])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_slice_on_part_preserve(self):
        part = Partition(1)
        part.action = "preserve"
        part.type = "primary"
        part.bootid = Partition.ACTIVE
        part.start_sector = 0
        part.size = Size("50" + Size.gb_units)

        part2 = Partition(2)
        part2.action = "preserve"
        part2.type = "primary"
        part2.bootid = 0
        part2.size = Size("50" + Size.gb_units)
        part2.start_sector = 50 * GBSECTOR + 50

        self.disk.insert_children([part, part2])

        slice1 = Slice(1)
        slice1.action = "preserve"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE

        slice2 = Slice(2)
        slice2.action = "preserve"
        slice2.size = Size(str(GBSECTOR) + Size.sector_units)
        slice2.start_sector = CYLSIZE + GBSECTOR + 1

        slice3 = Slice(3)
        slice3.action = "preserve"
        slice3.size = Size(str(GBSECTOR) + Size.sector_units)
        slice3.start_sector = CYLSIZE + (2 * GBSECTOR + 2)

        part.insert_children([slice1, slice2, slice3])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_slice_preserve(self):
        slice1 = Slice(1)
        slice1.action = "preserve"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE

        slice2 = Slice(2)
        slice2.action = "preserve"
        slice2.size = Size(str(GBSECTOR) + Size.sector_units)
        slice2.start_sector = CYLSIZE + GBSECTOR + 1

        slice3 = Slice(3)
        slice3.action = "preserve"
        slice3.size = Size(str(GBSECTOR) + Size.sector_units)
        slice3.start_sector = CYLSIZE + (2 * GBSECTOR + 2)

        self.disk.insert_children([slice1, slice2, slice3])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_part_not_preserve(self):
        part = Partition(1)
        part.action = "create"
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE
        part.size = Size("2b")

        part2 = Partition(2)
        part2.action = "destroy"
        part2.part_type = "primary"
        part2.bootid = 0
        part2.size = Size("2b")

        self.disk.insert_children([part, part2])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_slice_on_part_not_preserve(self):
        part = Partition(1)
        part.action = "preserve"
        part.part_type = "primary"
        part.bootid = Partition.ACTIVE
        part.size = Size("50" + Size.gb_units)
        part.start_sector = 0

        part2 = Partition(2)
        part2.action = "preserve"
        part2.part_type = "primary"
        part2.bootid = 0
        part2.size = Size("50" + Size.gb_units)
        part2.start_sector = 50 * GBSECTOR + 50

        self.disk.insert_children([part, part2])

        slice1 = Slice(1)
        slice1.action = "create"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE

        slice2 = Slice(2)
        slice2.action = "create"
        slice2.size = Size(str(GBSECTOR) + Size.sector_units)
        slice2.start_sector = CYLSIZE + GBSECTOR + 1

        slice3 = Slice(3)
        slice3.action = "destroy"
        slice3.size = Size(str(GBSECTOR) + Size.sector_units)
        slice3.start_sector = CYLSIZE + (2 * GBSECTOR + 2)

        part.insert_children([slice1, slice2, slice3])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_slice_not_preserve(self):
        slice1 = Slice(1)
        slice1.action = "create"
        slice1.size = Size(str(GBSECTOR) + Size.sector_units)
        slice1.start_sector = CYLSIZE

        slice2 = Slice(2)
        slice2.action = "create"
        slice2.size = Size(str(GBSECTOR) + Size.sector_units)
        slice2.start_sector = CYLSIZE + GBSECTOR + 1

        slice3 = Slice(3)
        slice3.action = "destroy"
        slice3.size = Size(str(GBSECTOR) + Size.sector_units)
        slice3.start_sector = CYLSIZE + (2 * GBSECTOR + 2)

        self.disk.insert_children([slice1, slice2, slice3])

        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))


class TestZpool(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # create DOC objects
        self.target = Target(Target.DESIRED)
        self.doc.insert_children(self.target)

        self.logical = Logical("logical")

        self.disk1 = Disk("disk")
        self.disk1.ctd = "c8t1d0"
        self.disk1.disk_prop = DiskProp()
        self.disk1.disk_prop.blocksize = 512

        self.disk2 = Disk("disk2")
        self.disk2.ctd = "c8t2d0"
        self.disk2.disk_prop = DiskProp()
        self.disk2.disk_prop.blocksize = 512

    def tearDown(self):
        self.target.delete_children()
        self.target.delete()
        engine_test_utils.reset_engine()

    def test_one_disk_zpool_create(self):
        self.disk1.in_zpool = "test_zpool"
        zpool = Zpool("test_zpool")
        zpool.action = "create"
        self.logical.insert_children(zpool)
        self.target.insert_children([self.disk1, self.logical])
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_two_disk_zpool_create(self):
        self.disk1.in_zpool = "test_zpool"
        self.disk2.in_zpool = "test_zpool"
        zpool = Zpool("test_zpool")
        zpool.action = "create"
        self.logical.insert_children(zpool)
        self.target.insert_children([self.disk1, self.disk2, self.logical])
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_whole_disk_zpool_create(self):
        self.disk1.in_zpool = "test_zpool"
        self.disk1.whole_disk = True
        self.disk2.in_zpool = "test_zpool"
        self.disk2.whole_disk = True
        zpool = Zpool("test_zpool")
        zpool.action = "create"
        self.logical.insert_children(zpool)
        self.target.insert_children([self.disk1, self.disk2, self.logical])
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_empty_zpool_delete(self):
        zpool = Zpool("test_zpool")
        zpool.action = "delete"
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_full_zpool_delete(self):
        zpool = Zpool("test_zpool")
        zpool.action = "delete"
        fs1 = Filesystem("test_zpool/fs1")
        fs2 = Filesystem("test_zpool/fs2")
        fs3 = Filesystem("test_zpool/fs3")
        zpool.insert_children([fs1, fs2, fs3])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_empty_zpool_preserve(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_full_zpool_preserve(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/fs1")
        fs2 = Filesystem("test_zpool/fs2")
        fs3 = Filesystem("test_zpool/fs3")
        zpool.insert_children([fs1, fs2, fs3])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_filesystem_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/fs1")
        fs1.action = "create"
        fs2 = Filesystem("test_zpool/fs2")
        fs2.action = "create"
        fs3 = Filesystem("test_zpool/fs3")
        fs3.action = "create"
        zpool.insert_children([fs1, fs2, fs3])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_filesystem_create_and_delete(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/fs1")
        fs1.action = "create"
        fs2 = Filesystem("test_zpool/fs2")
        fs2.action = "delete"
        fs3 = Filesystem("test_zpool/fs3")
        fs3.action = "create"
        zpool.insert_children([fs1, fs2, fs3])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_zvol_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/swap")
        fs1.action = "create"
        fs2 = Filesystem("test_zpool/dump")
        fs2.action = "create"
        zpool.insert_children([fs1, fs2])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_zvol_create_and_delete(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/swap")
        fs1.action = "delete"
        fs2 = Filesystem("test_zpool/dump")
        fs2.action = "create"
        zpool.insert_children([fs1, fs2])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_full_zpool_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "create"
        fs1 = Filesystem("test_zpool/swap")
        fs1.action = "create"
        fs2 = Filesystem("test_zpool/dump")
        fs2.action = "create"
        zpool.insert_children([fs1, fs2])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_pool_and_dataset_options(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        fs1 = Filesystem("test_zpool/fs1")
        fs1.action = "create"
        fs2 = Filesystem("test_zpool/fs2")
        fs2.action = "create"
        fs3 = Filesystem("test_zpool/fs3")
        fs3.action = "create"
        pool_options = PoolOptions("pool options")
        fs_options = DatasetOptions("fs options")
        pool_options1 = Options("pool option1")
        pool_options1.options_str = "-o autoexpand=off"
        fs_options1 = Options("fs options1")
        fs_options1.options_str = "-O atime=on"
        pool_options.insert_children(pool_options1)
        fs_options.insert_children(fs_options1)
        zpool.insert_children([fs1, fs2, fs3, pool_options, fs_options])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        self.doc.insert_children(self.target)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_two_disk_vdev_create(self):
        self.disk1.in_zpool = "test_zpool"
        self.disk1.in_vdev = "test_mirror"
        self.disk2.in_zpool = "test_zpool"
        self.disk2.in_vdev = "test_mirror"
        zpool = Zpool("test_zpool")
        zpool.action = "create"
        vdev = Vdev("test_mirror")
        vdev.redundancy = "mirror"
        zpool.insert_children(vdev)
        self.logical.insert_children(zpool)
        self.target.insert_children([self.disk1, self.disk2, self.logical])
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_multi_disk_multi_vdev_create(self):
        self.disk1.in_zpool = "test_zpool"
        self.disk1.in_vdev = "test_mirror"
        self.disk2.in_zpool = "test_zpool"
        self.disk2.in_vdev = "test_mirror"
        self.disk3 = Disk("disk3")
        self.disk3.ctd = "c8t3d0"
        self.disk3.in_zpool = "test_zpool"
        self.disk3.in_vdev = "test_raidz"
        self.disk4 = Disk("disk4")
        self.disk4.ctd = "c8t4d0"
        self.disk4.in_zpool = "test_zpool"
        self.disk4.in_vdev = "test_raidz"
        self.disk5 = Disk("disk5")
        self.disk5.ctd = "c8t5d0"
        self.disk5.in_zpool = "test_zpool"
        self.disk5.in_vdev = "test_raidz"
        self.disk6 = Disk("disk6")
        self.disk6.ctd = "c8t6d0"
        self.disk6.in_zpool = "test_zpool"
        self.disk6.in_vdev = "test_spare"
        self.disk7 = Disk("disk7")
        self.disk7.ctd = "c8t7d0"
        self.disk7.in_zpool = "test_zpool"
        self.disk7.in_vdev = "test_log"
        zpool1 = Zpool("test_zpool")
        zpool1.action = "create"
        vdev1 = Vdev("test_mirror")
        vdev1.redundancy = "mirror"
        vdev2 = Vdev("test_raidz")
        vdev2.redundancy = "raidz"
        vdev3 = Vdev("test_log")
        vdev3.redundancy = "log"
        vdev4 = Vdev("test_spare")
        vdev4.redundancy = "spare"
        zpool1.insert_children([vdev1, vdev2, vdev3, vdev4])
        self.logical.insert_children(zpool1)
        self.target.insert_children([self.disk1, self.disk2, self.disk3, \
            self.disk4, self.disk5, self.disk6, self.disk7, self.logical])
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))


class TestBE(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache.volatile

        # create DOC objects
        self.target = Target(Target.DESIRED)
        self.doc.insert_children(self.target)

        self.logical = Logical("logical")

    def tearDown(self):
        self.target.delete_children()
        self.target.delete()
        engine_test_utils.reset_engine()

    def test_one_be_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        be1 = BE("be1")
        zpool.insert_children(be1)
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_two_be_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        be1 = BE("be1")
        be2 = BE("be2")
        zpool.insert_children([be1, be2])
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_default_be_create(self):
        zpool = Zpool("test_zpool")
        zpool.action = "preserve"
        be1 = BE()
        zpool.insert_children(be1)
        self.logical.insert_children(zpool)
        self.target.insert_children(self.logical)
        t = instantiation.TargetInstantiation("test_ti")
        try:
            t.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

if __name__ == '__main__':
    unittest.main()

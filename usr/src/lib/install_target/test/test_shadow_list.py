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

""" test_shadow_list.py - collection of unittests for testing target validation
through shadow list manipulation
"""
import copy
import platform
import unittest

from nose.plugins.skip import SkipTest

import osol_install.errsvc as errsvc

from osol_install.liberrsvc import ES_DATA_EXCEPTION

from solaris_install import Popen
from solaris_install.target import Target
from solaris_install.target.physical import Disk, DiskGeometry, DiskProp, \
    InsufficientSpaceError, Partition, Slice
from solaris_install.target.libadm.const import MAX_EXT_PARTS, V_NUMPAR
from solaris_install.target.logical import BE, Logical, Vdev, Zpool
from solaris_install.target.shadow.physical import LOGICAL_ADJUSTMENT, \
    ShadowPhysical
from solaris_install.target.shadow.logical import ShadowLogical
from solaris_install.target.shadow.zpool import ShadowZpool
from solaris_install.target.size import Size
from solaris_install.target.vdevs import _get_vdev_mapping


GBSECTOR = long(1024 * 1024 * 1024 / 512)  # 1 GB of sectors
BLOCKSIZE = 512
CYLSIZE = 16065


class TestZpool(unittest.TestCase):
    """ test case to test manipulation of Zpool objects via the API and shadow
    list interfaces
    """
    def setUp(self):
        # create DOC objects
        self.target = Target("target")
        self.logical = Logical("logical")
        self.target.insert_children(self.logical)

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.target.delete_children()
        self.target.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_simple_zpool(self):
        # create a DOC tree
        self.logical.add_zpool("test_zpool")
        self.assertFalse(errsvc._ERRORS)

    def test_add_duplicate_zpool_names(self):
        self.logical.add_zpool("test_zpool")
        self.logical.add_zpool("test_zpool")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowZpool.DuplicateZpoolNameError))

    def test_add_two_root_pools(self):
        self.logical.add_zpool("test_zpool", is_root=True)
        self.logical.add_zpool("test_zpool2", is_root=True)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowZpool.TooManyRootPoolsError))

    def test_add_overlapping_mountpoints(self):
        self.logical.add_zpool("test_zpool", mountpoint="/foo")
        self.logical.add_zpool("test_zpool2", mountpoint="/foo/bar")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowZpool.DuplicateMountpointError))

    def test_delete_zpool(self):
        zpool1 = self.logical.add_zpool("test_zpool")
        zpool2 = self.logical.add_zpool("test_zpool2")

        # verify there are 2 entries in the _children list
        self.assertEqual(len(self.logical._children), 2)

        # delete zpool2
        zpool2.delete()

        # verify there is only one entry in the _children list and the proper
        # zpool was removed
        self.assertEqual(len(self.logical._children), 1)
        self.assertEqual(self.logical._children[0].name, "test_zpool")

        # delete zpool1
        zpool1.delete()

        # verify there are no entries in the _children list
        self.assertFalse(self.logical._children)

    def test_delete_zpool_twice(self):
        zpool = self.logical.add_zpool("test_zpool")
        self.logical.delete_zpool(zpool)
        self.assertFalse(self.logical._children)

        # try to delete the zpool again.
        self.logical.delete_zpool(zpool)
        self.assertFalse(self.logical._children)

    def test_delete_zpool_from_logical(self):
        zpool1 = self.logical.add_zpool("test_zpool")
        zpool2 = self.logical.add_zpool("test_zpool2")

        # verify there are 2 entries in the _children list
        self.assertEqual(len(self.logical._children), 2)

        # delete zpool2
        self.logical.delete_zpool(zpool2)

        # verify there is only one entry in the _children list and the proper
        # zpool was removed
        self.assertEqual(len(self.logical._children), 1)
        self.assertEqual(self.logical._children[0].name, "test_zpool")

    def test_add_vdev(self):
        # create a zpool and a vdev
        zpool = self.logical.add_zpool("test_zpool")
        zpool.add_vdev(label="test_vdev", redundancy="mirror")
        self.assertTrue(zpool.get_descendants(class_type=Vdev))

    def test_delete_vdev(self):
        # create a zpool and two vdevs
        zpool = self.logical.add_zpool("test_zpool")
        vdev1 = zpool.add_vdev(label="test_vdev1", redundancy="mirror")
        vdev2 = zpool.add_vdev(label="test_vdev2", redundancy="raidz")

        # verify there are two vdevs
        self.assertEqual(len(zpool.get_descendants(class_type=Vdev)), 2)

        # delete vdev2
        zpool.delete_vdev(vdev2)

        # verify there is only one vdev
        self.assertEqual(len(zpool.get_descendants(class_type=Vdev)), 1)

        # delete vdev1
        zpool.delete_vdev(vdev1)

        # verify there are no vdevs
        self.assertFalse(zpool.get_descendants(class_type=Vdev))


class TestZFSFilesystem(unittest.TestCase):
    """ test case to test the manipulation of ZFS filesystems via the API and
    shadow list interface.
    """
    def setUp(self):
        self.zpool = Zpool("zpool")

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.zpool.delete_children()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_simple_filesystem(self):
        self.zpool.add_filesystem("test_filesystem")
        self.assertFalse(errsvc._ERRORS)

    def test_add_simple_filesystem_with_mountpoint(self):
        self.zpool.add_filesystem("test_filesystem", "/mountpoint")
        self.assertFalse(errsvc._ERRORS)

    def test_add_duplicate_filesystem_names(self):
        self.zpool.add_filesystem("test_filesystem")
        self.assertFalse(errsvc._ERRORS)

        self.zpool.add_filesystem("test_filesystem")
        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowLogical.DuplicateDatasetNameError))

    def test_add_duplicate_mountpoints(self):
        self.zpool.add_filesystem("test_filesystem", "/a")
        self.assertFalse(errsvc._ERRORS)

        self.zpool.add_filesystem("test_filesystem_2", "/a")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowLogical.DuplicateMountpointError))

    def test_delete_filesystem(self):
        fs1 = self.zpool.add_filesystem("test_filesystem1")
        fs2 = self.zpool.add_filesystem("test_filesystem2")

        # verify there are 2 entries in _children
        self.assertEqual(len(self.zpool._children), 2)

        # delete fs2
        fs2.delete()

        # verify there is only one entry in the _children list and the proper
        # fs was removed
        self.assertEqual(len(self.zpool._children), 1)
        self.assertEqual(self.zpool._children[0].name, "test_filesystem1")

        # delete fs1
        fs1.delete()

        # verify there are no entries in _children
        self.assertFalse(self.zpool._children)

    def test_delete_filesystem_from_zpool(self):
        fs1 = self.zpool.add_filesystem("test_filesystem1")
        fs2 = self.zpool.add_filesystem("test_filesystem2")

        # verify there are 2 entries in the _children list
        self.assertEqual(len(self.zpool._children), 2)

        # delete zpool2
        self.zpool.delete_filesystem(fs2)

        # verify there is only one entry in the _children list and the proper
        # zpool was removed
        self.assertEqual(len(self.zpool._children), 1)
        self.assertEqual(self.zpool._children[0].name, "test_filesystem1")

        # delete zpool2 again
        self.zpool.delete_filesystem(fs2)

        # verify there is only one entry in the _children list and the proper
        # zpool was removed
        self.assertEqual(len(self.zpool._children), 1)
        self.assertEqual(self.zpool._children[0].name, "test_filesystem1")


class TestZvol(unittest.TestCase):
    """ test case to test the manipulation of Zvols via the API and
    shadow list interface.
    """
    def setUp(self):
        self.target = Target("target")

        # create a disk object
        self.disk = Disk("test disk")
        self.disk.in_zpool = "zpool"
        self.disk.ctd = "c12345t0d0"
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)

        # 250GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 250) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

        self.logical = Logical("logical")
        self.zpool = Zpool("zpool")
        self.logical.insert_children(self.zpool)

        self.target.insert_children([self.disk, self.logical])

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.logical.delete_children()
        self.logical.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_simple_zvol(self):
        self.zpool.add_zvol("test_zvol", "10")
        self.assertFalse(errsvc._ERRORS)

    def test_add_duplicate_zvol_names(self):
        self.zpool.add_zvol("test_zvol", "10")
        self.assertFalse(errsvc._ERRORS)

        self.zpool.add_zvol("test_zvol", "10")
        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowLogical.DuplicateDatasetNameError))

    def test_delete_zvol(self):
        zvol1 = self.zpool.add_zvol("zvol1", "10")
        zvol2 = self.zpool.add_zvol("zvol2", "10")

        # verify there are 2 entries in the _children list
        self.assertEqual(len(self.zpool._children), 2)

        # delete zvol2
        zvol2.delete()

        # verify there is only one entry in the _children list and the proper
        # zvol was removed
        self.assertEqual(len(self.zpool._children), 1)
        self.assertEqual(self.zpool._children[0].name, "zvol1")

    def test_delete_zvol_from_zpool(self):
        zvol1 = self.zpool.add_zvol("zvol1", "10")
        zvol2 = self.zpool.add_zvol("zvol2", "10")

        # verify there are 2 entries in the _children list
        self.assertEqual(len(self.zpool._children), 2)

        # delete zvol2
        self.zpool.delete_zvol(zvol2)

        # verify there is only one entry in the _children list and the proper
        # zvol was removed
        self.assertEqual(len(self.zpool._children), 1)
        self.assertEqual(self.zpool._children[0].name, "zvol1")

    def test_resize_zvol(self):
        zvol = self.zpool.add_zvol("zvol1", "10")

        # verify the size is 10gb
        self.assertEqual(self.zpool._children[0].size, "10g")

        # resize it to 20gb
        zvol.resize("20", Size.gb_units)

        # verify the size is 20gb
        self.assertEqual(self.zpool._children[0].size, "20g")

    def test_swap_zvol_with_noswap_set(self):
        self.logical.noswap = True
        zvol = self.zpool.add_zvol("swap_zvol", "10", Size.gb_units, "swap")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowLogical.NoswapMismatchError))

    def test_dump_zvol_with_nodump_set(self):
        self.logical.nodump = True
        zvol = self.zpool.add_zvol("dump_zvol", "10", Size.gb_units, "dump")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowLogical.NodumpMismatchError))


class TestPartition(unittest.TestCase):
    def setUp(self):
        self.disk = Disk("test disk")
        self.disk.ctd = "c12345t0d0"
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk.label = "VTOC"

        # 100GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.disk.delete_children()
        self.disk.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_single_partition(self):
        self.disk.add_partition(1, 0, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_duplicate_partition(self):
        # add 2 1GB partition with the same index but different starting sector
        self.disk.add_partition(1, 0, 1, Size.gb_units)

        # account for the first silce moving from a start_sector of 0 to
        # CYLSIZE
        self.disk.add_partition(1, CYLSIZE + GBSECTOR + 1, 1,
                                Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.DuplicatePartitionNameError))

    def test_overlapping_starting_sector(self):
        # add a 10 GB disk
        self.disk.add_partition(0, CYLSIZE, 10, Size.gb_units)
        # add an 11 GB disk
        self.disk.add_partition(1, CYLSIZE, 11, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingPartitionError))

    def test_overlapping_ending_sector(self):
        # add a 9 GB disk on the second cylinder boundary
        self.disk.add_partition(0, CYLSIZE * 2, 9, Size.gb_units)
        # add a 10 GB disk on the first cylinder boundary
        self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingPartitionError))

    def test_add_two_extended_partitions(self):
        # add 2 1GB partitions
        self.disk.add_partition(1, 0, 1, Size.gb_units,
            partition_type=Partition.name_to_num("WIN95 Extended(LBA)"))

        # account for the first silce moving from a start_sector of 0 to
        # CYLSIZE
        self.disk.add_partition(2, CYLSIZE + GBSECTOR + 1, 1, Size.gb_units,
            partition_type=Partition.name_to_num("WIN95 Extended(LBA)"))

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.TooManyExtPartitionsError))

    def test_delete_partition(self):
        p1 = self.disk.add_partition(1, 0, 1, Size.gb_units)
        p2 = self.disk.add_partition(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in the _children
        self.assertEqual(len(self.disk._children), 2)

        # delete partition 2
        p2.delete()

        # verify there is only one entry in the _children and the proper
        # partition was removed.
        self.assertEqual(len(self.disk._children), 1)
        self.assertEqual(self.disk._children[0].name, 1)

    def test_delete_partition_with_slice_children(self):
        # add a 10gb partition
        p1 = self.disk.add_partition(1, 0, 10, Size.gb_units)

        # add two slices
        p1.add_slice(0, CYLSIZE, 1, Size.gb_units)
        p1.add_slice(1, GBSECTOR + CYLSIZE + 1, 1, Size.gb_units)

        # delete the partition
        p1.delete()

        # verify there are no errors
        self.assertFalse(errsvc._ERRORS)

        # verify the _children is empty
        self.assertFalse(self.disk._children)

    def test_delete_partition_from_disk(self):
        p1 = self.disk.add_partition(1, 0, 1, Size.gb_units)
        p2 = self.disk.add_partition(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in the _children
        self.assertEqual(len(self.disk._children), 2)

        # delete partition 2
        self.disk.delete_partition(p2)

        # verify there is only one entry in the _children and the proper
        # partition was removed.
        self.assertEqual(len(self.disk._children), 1)
        self.assertEqual(self.disk._children[0].name, 1)

    def test_resize_partition(self):
        # create a 1 GB partition
        p1 = self.disk.add_partition(1, CYLSIZE, 1, Size.gb_units)
        self.disk.insert_children(p1)

        # verify the size of the slice is 1 GB of sectors, rounded for CYLSIZE
        self.assertEqual(p1.size.sectors, (GBSECTOR / CYLSIZE) * CYLSIZE)

        # resize it to 5 GB
        new_p1 = p1.resize(5, Size.gb_units)

        # verify the size of the partition is 5 GB of sectors
        self.assertEqual(new_p1.size.sectors,
            ((5 * GBSECTOR) / CYLSIZE * CYLSIZE))

    def test_in_zpool_conflict_with_parent(self):
        # set the in_zpool attribute in the disk
        self.disk.in_zpool = "tank"

        # create a 1 GB partition
        p1 = self.disk.add_partition(1, 0, 1, Size.gb_units, in_zpool="tank")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.OverlappingPartitionZpoolError))

    def test_in_vdev_conflict_with_parent(self):
        # set the in_vdev attribute in the disk
        self.disk.in_vdev = "a label"

        # create a 1 GB partition
        self.disk.add_partition(1, 0, 1, Size.gb_units, in_vdev="a label")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.OverlappingPartitionVdevError))

    def test_change_type(self):
        p = self.disk.add_partition(1, 0, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(p.part_type, Partition.name_to_num("Solaris2"))

        new_p = p.change_type(Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(new_p.part_type, \
            Partition.name_to_num("WIN95 Extended(LBA)"))

    def test_extended_partition_too_small(self):
        self.disk.add_partition(1, CYLSIZE, 10, Size.sector_units,
            partition_type=Partition.name_to_num("WIN95 Extended(LBA)"))

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.ExtPartitionTooSmallError))

    def test_fat16_partition_too_large(self):
        self.disk.add_partition(1, 0, 10, Size.gb_units,
                                partition_type=Partition.name_to_num(
                                "FAT16 (Upto 32M)"))

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.FAT16PartitionTooLargeError))

    def test_whole_disk_is_true(self):
        self.disk.whole_disk = True
        self.disk.add_partition(1, 0, 10, Size.gb_units,
            partition_type=Partition.name_to_num("Solaris2"))

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.WholeDiskIsTrueError))

    def test_whole_disk_is_false(self):
        self.disk.whole_disk = False
        self.disk.add_partition(1, 0, 10, Size.gb_units,
            partition_type=Partition.name_to_num("Solaris2"))

        # verify that there are no errors
        self.assertFalse(errsvc._ERRORS)

    def test_holey_object_no_children(self):
        holey_list = self.disk.get_gaps()
        self.assertEqual(holey_list[0].size, self.disk.disk_prop.dev_size)

        # verify the logical list is empty as well
        self.assertFalse(self.disk.get_logical_partition_gaps())

    def test_holey_object_one_child_start_at_nonzero(self):
        # add a single partition, starting at start sector CYLSIZE
        p = self.disk.add_partition(1, CYLSIZE, 25, Size.gb_units)

        disksize = self.disk.disk_prop.dev_size.sectors

        holey_list = self.disk.get_gaps()

        # verify the holey list is correct
        self.assertEqual(len(holey_list), 1)

        # round the expected value up to the next cylinder boundary
        rounded_value = (((CYLSIZE + p.size.sectors + 1) / CYLSIZE) * \
            CYLSIZE) + CYLSIZE
        difference = rounded_value - (p.start_sector + p.size.sectors)

        rounded_size = \
            ((disksize - CYLSIZE - p.size.sectors - difference) / CYLSIZE) * \
                CYLSIZE

        self.assertEqual(holey_list[0].start_sector, rounded_value)
        self.assertEqual(holey_list[0].size.sectors, rounded_size)

        # verify the logical list is empty as well
        self.assertFalse(self.disk.get_logical_partition_gaps())

    def test_holey_object_logical_partitions(self):
        # add a single extended partition
        extended_part = self.disk.add_partition(1, CYLSIZE, 25, Size.gb_units,
            partition_type=15)

        # add a single logical partition
        logical_part = self.disk.add_partition(5, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

        disksize = self.disk.disk_prop.dev_size.sectors

        logical_holey_list = self.disk.get_logical_partition_gaps()

        # verify the disk's holey lists are correct
        self.assertEqual(len(logical_holey_list), 1)

        self.assertEqual(logical_holey_list[0].start_sector, \
            extended_part.start_sector + LOGICAL_ADJUSTMENT + \
            logical_part.size.sectors + LOGICAL_ADJUSTMENT)
        self.assertEqual(logical_holey_list[0].size.sectors,
            extended_part.size.sectors - (2 * LOGICAL_ADJUSTMENT) - \
                logical_part.size.sectors - 1)

    def test_add_two_active_partitions(self):
        self.disk.add_partition(1, 0, 5, Size.gb_units,
                                bootid=Partition.ACTIVE)
        self.disk.add_partition(2, 10 * GBSECTOR, 1, Size.gb_units,
                                bootid=Partition.ACTIVE)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.MultipleActivePartitionsError))

    def test_change_bootid(self):
        p = self.disk.add_partition(1, 0, 5, Size.gb_units)
        p.change_bootid(Partition.ACTIVE)
        self.assertFalse(errsvc._ERRORS)

        # change the bootid to something not allowed
        self.assertRaises(RuntimeError, p.change_bootid, "bad value")

    def test_disk_remaining_space(self):
        p = self.disk.add_partition(1, 0, 5, Size.gb_units)
        self.assertEqual(self.disk.remaining_space.sectors, \
            self.disk.disk_prop.dev_size.sectors - p.size.sectors)

    def test_defect_17624(self):
        """ test case specifically designed to validate defect 17624
        """
        # reset the disk size to 500gb
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 500) + Size.sector_units)

        # primary partitions.  Extended partition is partition 3.  Set the
        # sizes explictly to sector units to ensure the math is exact
        self.disk.add_partition(1, 2048, 2054272, Size.sector_units,
            partition_type=Partition.name_to_num("IFS: NTFS"))
        self.disk.add_partition(2, 2056320, 65802240, Size.sector_units,
            partition_type=Partition.name_to_num("Solaris2"))
        self.disk.add_partition(3, 67858560, 908893440, Size.sector_units,
            partition_type=Partition.name_to_num("WIN95 Extended(LBA)"))
        self.disk.add_partition(4, 976752000, 16065, Size.sector_units,
            partition_type=Partition.name_to_num("OS/2 Boot/Coherent swap"),
            bootid=Partition.ACTIVE)

        # verify there are no errors with the primary/extended partitions
        self.assertFalse(errsvc._ERRORS)

        # logical partitions
        self.disk.add_partition(5, 67858623, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(6, 76083903, 2008, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(7, 80196543, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(8, 88421823, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(9, 96647103, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(10, 104872383, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(11, 113097663, 32129, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(12, 178899903, 1004, Size.mb_units,
            partition_type=Partition.name_to_num("WIN95 FAT16(LBA)"))
        self.disk.add_partition(13, 180956223, 1004, Size.mb_units,
            partition_type=Partition.name_to_num("WIN95 FAT16(LBA)"))
        self.disk.add_partition(14, 183012543, 2008, Size.mb_units,
            partition_type=Partition.name_to_num("WIN95 FAT16(LBA)"))
        self.disk.add_partition(15, 187125183, 8032, Size.mb_units,
            partition_type=Partition.name_to_num("Linux native"))
        self.disk.add_partition(16, 203575743, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(17, 211801023, 4016, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(18, 220026303, 2008, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(19, 224138943, 2008, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(20, 228251583, 48194, Size.mb_units,
            partition_type=Partition.name_to_num("IFS: NTFS"))
        self.disk.add_partition(21, 326954943, 16064, Size.mb_units,
            partition_type=Partition.name_to_num("IFS: NTFS"))
        self.disk.add_partition(22, 956188863, 2008, Size.mb_units,
            partition_type=Partition.name_to_num("Solaris/Linux swap"))
        self.disk.add_partition(23, 960301503, 8032, Size.mb_units,
            partition_type=Partition.name_to_num("IFS: NTFS"))

        # verify there are no errors with the logical partitions
        self.assertFalse(errsvc._ERRORS)

    def test_invalid_start_sector(self):
        self.disk.add_partition(1, -16065, 1, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.InvalidPartitionStartSectorError))

    def test_invalid_partition_id(self):
        # create a partition with an invalid partition id.  name_to_num() of an
        # invalid partition ID will return None
        self.disk.add_partition(1, 1, 1, Size.gb_units,
            partition_type=Partition.name_to_num("INVALID PARTITION ID"))

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.PartitionTypeMissingError))

    def test_is_primary(self):
        p = self.disk.add_partition(1, 0, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertTrue(p.is_primary)

    def test_is_extended(self):
        p = self.disk.add_partition(1, 0, 1, Size.gb_units, partition_type=5)
        self.assertFalse(errsvc._ERRORS)
        self.assertTrue(p.is_extended)

    def test_is_logical(self):
        # add a single extended partition
        extended_part = self.disk.add_partition(1, CYLSIZE, 25, Size.gb_units,
                                        partition_type=15)

        # add a single logical partition
        logical_part = self.disk.add_partition(5, CYLSIZE, 1, Size.gb_units)

        self.assertFalse(errsvc._ERRORS)
        self.assertTrue(logical_part.is_logical)

    def test_no_validate_children(self):
        self.disk.validate_children = False
        start_sector = 12345
        p = self.disk.add_partition(1, 12345, 5, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(start_sector, p.start_sector)
        self.assertEqual(Size("5gb"), p.size)

    def test_get_next_partition_name(self):
        self.assertEqual(self.disk.get_next_partition_name(primary=True), "1")
        self.assertEqual(self.disk.get_next_partition_name(primary=False), "5")

        # add an extended partition
        extended_part = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units,
           partition_type=15)

        self.assertFalse(errsvc._ERRORS)
        self.assertTrue(extended_part.is_primary)
        self.assertTrue(extended_part.is_extended)

        # add a logical partition
        logical_part = self.disk.add_partition(5, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertTrue(logical_part.is_logical)

        self.assertEqual(len(self.disk.primary_partitions), 1)
        self.assertEqual(len(self.disk.logical_partitions), 1)

        self.assertEqual(self.disk.get_next_partition_name(primary=True), "2")
        self.assertEqual(self.disk.get_next_partition_name(primary=False), "6")

        # ignore any insertion errors for testing get_next_partition_name
        self.disk.add_partition(2, CYLSIZE, 1, Size.gb_units)
        self.disk.add_partition(3, CYLSIZE, 1, Size.gb_units)
        self.disk.add_partition(4, CYLSIZE, 1, Size.gb_units)

        # verify get_next_partition_name returns None if there are no available
        # primary partitions
        self.assertEqual(self.disk.get_next_partition_name(primary=True), None)

    def test_cr_7055489(self):
        self.disk.add_partition("0", CYLSIZE, 10, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.InvalidPartitionNameError))

    def test_insertion_of_partition_over_deleted_partition_of_same_name(self):
        # add a 1GB partition at start_sector CYLSIZE and set the action to
        # delete
        p = self.disk.add_partition(1, CYLSIZE, 1, Size.gb_units)
        p.action = "delete"

        # insert another partition with the same name
        self.disk.add_partition(1, CYLSIZE, 2, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_resize_child_partition_at_start(self):
        # +-----------------+
        # |            |////|
        # |    p1      |/g1/|
        # +-----------------+
        original_p1 = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units)

        # increase the size of p1 into gap 1
        p1 = self.disk.resize_partition(original_p1, 25, Size.gb_units)
        self.assertEqual(original_p1.start_sector, p1.start_sector)
        self.assertEqual(p1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of p1 beyond the bounds of the disk
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p1, 100, Size.gb_units)

    def test_resize_child_partition_at_end(self):
        # +-----------------+
        # |////|            |
        # |/g1/|     p1     |
        # +-----------------+
        start_sector = self.disk.disk_prop.dev_size.sectors - 10 * GBSECTOR
        original_p1 = self.disk.add_partition(1, start_sector, 10,
                                              Size.gb_units)

        # increase the size of p1 into gap 1
        p1 = self.disk.resize_partition(original_p1, 25, Size.gb_units)
        self.assertEqual(p1.start_sector,
            original_p1.start_sector - (15 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(p1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of p1 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p1, 100, Size.gb_units)

    def test_resize_child_partition_only_right(self):
        # +-----------------------+
        # |            |     |////|
        # |    p1      | p2  |/g1/|
        # +-----------------------+
        p1 = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units)
        gaps = self.disk.get_gaps()
        original_p2 = self.disk.add_partition(2, gaps[0].start_sector, 10,
                                              Size.gb_units)

        # increase the size of p2 into gap 1
        p2 = self.disk.resize_partition(original_p2, 25, Size.gb_units)
        self.assertEqual(p2.start_sector, original_p2.start_sector)
        self.assertEqual(p2.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of p2 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p2, 100, Size.gb_units)

    def test_resize_child_partition_only_left(self):
        # +------------------------+
        # |////|            |      |
        # |/g1/|     p1     |  p2  |
        # +------------------------+
        start_sector = self.disk.disk_prop.dev_size.sectors - 10 * GBSECTOR
        p2 = self.disk.add_partition(2, start_sector, 10, Size.gb_units)
        original_p1 = self.disk.add_partition(1,
            start_sector - (10 * GBSECTOR), 10, Size.gb_units)

        # increase the size of p1 into gap 1
        p1 = self.disk.resize_partition(original_p1, 25, Size.gb_units)
        self.assertEqual(p1.start_sector,
            original_p1.start_sector - CYLSIZE - \
                (15 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(p1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of p1 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p1, 100, Size.gb_units)

    def test_resize_child_partition_no_room(self):
        # +------------------------+
        # |    |            |      |
        # | p1 |     p2     |  p3  |
        # +------------------------+
        p1 = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units)
        gaps = self.disk.get_gaps()
        original_p2 = self.disk.add_partition(2, gaps[0].start_sector, 10,
                                              Size.gb_units)
        gaps = self.disk.get_gaps()
        p3 = self.disk.add_partition(3, gaps[0].start_sector, 10,
                                     Size.gb_units)

        # verify p2 can not be increased in size beyond the original 10gb
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            original_p2, 10.1, Size.gb_units)

    def test_resize_child_partition_with_gaps_on_either_side(self):
        # +----------------------------+
        # |    |//////|    |//////|    |
        # | p1 |//g1//| p2 |//g2//| p3 |
        # +----------------------------+
        p1 = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units)
        original_p2 = self.disk.add_partition(2, 25 * GBSECTOR, 10,
                                              Size.gb_units)
        p3 = self.disk.add_partition(3, 40 * GBSECTOR, 10, Size.gb_units)

        # increase the size of p2 into g2, but not to exceed it
        p2 = self.disk.resize_partition(original_p2, 15, Size.gb_units)
        self.assertEqual(original_p2.start_sector, p2.start_sector)
        self.assertEqual(p2.size.sectors,
            Size("15gb").sectors / CYLSIZE * CYLSIZE)

        # destroy partition 2 and re-insert
        self.disk.delete_children(class_type=Partition, name=2)
        original_p2 = self.disk.add_partition(2, 25 * GBSECTOR, 10,
                                              Size.gb_units)

        # increase the size of p2 to consume all of g2 and part of g1
        p2 = self.disk.resize_partition(original_p2, 20, Size.gb_units)
        self.assertEqual(p2.start_sector,
            original_p2.start_sector - (5 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(p2.size.sectors,
            Size("20gb").sectors / CYLSIZE * CYLSIZE)

        # destroy partition 2 and re-insert
        self.disk.delete_children(class_type=Partition, name=2)
        original_p2 = self.disk.add_partition(2, 25 * GBSECTOR, 10,
                                              Size.gb_units)

        # increase the size of p2 beyond the bounds of the two gaps
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            original_p2, 30, Size.gb_units)


class TestSliceInDisk(unittest.TestCase):
    def setUp(self):
        self.disk = Disk("test disk")
        self.disk.ctd = "c12345t0d0"
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk.label = "VTOC"

        # 100GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.disk.delete_children()
        self.disk.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_single_slice(self):
        # add a 1GB slice at start_sector CYLSIZE
        self.disk.add_slice(0, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_cylinder_zero_boundary_adjustment(self):
        # add a 1GB slice at start_sector 0
        self.disk.add_slice(0, 0, 1, Size.gb_units)

        # test that it moved to the first cylinder boundary
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(self.disk._children[0].start_sector, CYLSIZE)

    def test_add_too_many_slices(self):
        for i in range(V_NUMPAR + 2):
            start_sector = i * GBSECTOR + i
            self.disk.add_slice(i, start_sector, 1)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.TooManySlicesError))

    def test_duplicate_slice(self):
        # add 2 1GB slices with the same index but different starting sector
        self.disk.add_slice(0, 0, 1, Size.gb_units)

        # account for the first silce moving from a start_sector of 0 to
        # CYLSIZE
        self.disk.add_slice(0, CYLSIZE + GBSECTOR + 1, 1, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.DuplicateSliceNameError))

    def test_overlapping_starting_sector(self):
        # add a 10 GB slice
        self.disk.add_slice(0, CYLSIZE, 10, Size.gb_units)
        # add an 11 GB slice
        self.disk.add_slice(1, CYLSIZE, 11, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceError))

    def test_overlapping_ending_sector(self):
        # add a 9 GB slice on the second cylinder boundary
        self.disk.add_slice(0, CYLSIZE * 2, 9, Size.gb_units)
        # add a 10 GB slice on the first cylinder boundary
        self.disk.add_slice(1, CYLSIZE, 10, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceError))

    def test_delete_slice(self):
        s1 = self.disk.add_slice(1, 0, 1, Size.gb_units)
        s2 = self.disk.add_slice(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in _children
        self.assertEqual(len(self.disk._children), 2)

        # delete slice 2
        s2.delete()

        # verify there is only one entry in the _children and the proper
        # slice was removed.
        self.assertEqual(len(self.disk._children), 1)
        self.assertEqual(self.disk._children[0].name, 1)

    def test_delete_slice_in_disk(self):
        s1 = self.disk.add_slice(1, 0, 1, Size.gb_units)
        s2 = self.disk.add_slice(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in the _children
        self.assertEqual(len(self.disk._children), 2)

        # delete slice 2
        self.disk.delete_slice(s2)

        # verify there is only one entry in the _children and the proper
        # slice was removed.
        self.assertEqual(len(self.disk._children), 1)
        self.assertEqual(self.disk._children[0].name, 1)

    def test_resize_slice(self):
        # create a 1 GB slice
        s1 = self.disk.add_slice(1, CYLSIZE, 1, Size.gb_units)

        # verify the size of the slice is 1 GB of sectors, rounded for CYLSIZE
        self.assertEqual(s1.size.sectors, (GBSECTOR / CYLSIZE) * CYLSIZE)

        # resize it to 5 GB
        new_s1 = s1.resize(5, Size.gb_units)

        # verify the size of the slice is 5 GB of sectors
        self.assertTrue(new_s1.size.sectors, 5 * GBSECTOR - 1)

    def test_in_zpool_confilict_with_parent(self):
        # set the in_zpool attribute in the disk
        self.disk.in_zpool = "tank"

        # create a 1 GB partition
        self.disk.add_slice(1, 0, 1, Size.gb_units, in_zpool="tank")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceZpoolError))

    def test_in_vdev_confilict_with_parent(self):
        # set the in_vdev attribute in the disk
        self.disk.in_vdev = "a label"

        # create a 1 GB partition
        self.disk.add_slice(1, 0, 1, Size.gb_units, in_vdev="a label")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceVdevError))

    def test_whole_disk_is_true(self):
        self.disk.whole_disk = True
        # add a 100 MB slice
        self.disk.add_slice(0, 0, 100, Size.mb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.WholeDiskIsTrueError))

    def test_whole_disk_is_false(self):
        self.disk.whole_disk = False
        # add a 100 MB slice
        self.disk.add_slice(0, 0, 100, Size.mb_units)

        # verify that there are no errors
        self.assertFalse(errsvc._ERRORS)

    def test_holey_object_no_children(self):
        holey_list = self.disk.get_gaps()
        self.assertTrue(holey_list[0].size, self.disk.disk_prop.dev_size)

    def test_holey_object_one_child_start_at_cylsize(self):
        # add a single slice, starting at start sector CLYSIZE
        s = self.disk.add_slice(1, CYLSIZE, 25, Size.gb_units)
        disksize = self.disk.disk_prop.dev_size.sectors

        holey_list = self.disk.get_gaps()

        # verify the holey list is correct
        self.assertEqual(len(holey_list), 1)

        # round the expected value up to the next cylinder boundary
        rounded_value = (((CYLSIZE + s.size.sectors + 1) / CYLSIZE) * \
            CYLSIZE) + CYLSIZE
        difference = rounded_value - (s.start_sector + s.size.sectors)

        rounded_size = \
            ((disksize - CYLSIZE - s.size.sectors - difference) / \
                CYLSIZE) * CYLSIZE

        self.assertEqual(holey_list[0].start_sector, rounded_value)
        self.assertEqual(holey_list[0].size.sectors, rounded_size)

    def test_holey_object_one_child_start_at_nonzero(self):
        # add a single slice, starting at start sector CYLSIZE * 10
        start = CYLSIZE * 10

        s = self.disk.add_slice(1, start, 25, Size.gb_units)
        disksize = self.disk.disk_prop.dev_size.sectors

        holey_list = self.disk.get_gaps()

        # verify the holey list is correct
        self.assertEqual(len(holey_list), 2)

        self.assertEqual(holey_list[0].start_sector, CYLSIZE)
        self.assertEqual(holey_list[0].size.sectors,
            (((start - CYLSIZE - 1) / CYLSIZE) * CYLSIZE))

        # round the expected value up to the next cylinder boundary
        rounded_value = (((CYLSIZE * 10 + s.size.sectors + 1) / CYLSIZE) * \
            CYLSIZE) + CYLSIZE
        difference = rounded_value - (s.start_sector + s.size.sectors)

        rounded_size = \
            ((disksize - (CYLSIZE * 10) - s.size.sectors - difference) / \
                CYLSIZE) * CYLSIZE

        self.assertEqual(holey_list[1].start_sector, rounded_value)
        self.assertEqual(holey_list[1].size.sectors, rounded_size)

    def test_invalid_start_sector(self):
        self.disk.add_slice(0, -16065, 1, Size.gb_units)
        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.InvalidSliceStartSectorError))

    def test_slice_entire_size_of_disk(self):
        disksize = self.disk.disk_prop.dev_size.sectors

        # add a non V_BACKUP slice the entire size of the disk
        s = self.disk.add_slice(0, CYLSIZE, disksize, Size.sector_units)

        # verify there are no errors
        self.assertFalse(errsvc._ERRORS)

        # verify the size of the slice, rounding for cylinder size and
        # maximum size limits
        if platform.processor() == "i386":
            self.assertEqual(((disksize / CYLSIZE) - 4) * CYLSIZE,
                             s.size.sectors)
        else:
            self.assertEqual(((disksize / CYLSIZE)) * CYLSIZE, s.size.sectors)

    def test_no_validate_children(self):
        self.disk.validate_children = False
        start_sector = 12345
        s = self.disk.add_slice(1, 12345, 5, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(start_sector, s.start_sector)
        self.assertEqual(Size("5gb"), s.size)

    def test_insertion_of_slice_over_deleted_slice_of_same_name(self):
        # add a 1GB slice at start_sector CYLSIZE and set the action to delete
        s = self.disk.add_slice(0, CYLSIZE, 1, Size.gb_units)
        s.action = "delete"

        # insert another slice with the same name
        self.disk.add_slice(0, CYLSIZE, 2, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)


class TestSliceInPartition(unittest.TestCase):
    def setUp(self):
        self.disk = Disk("test disk")
        self.disk.ctd = "c12345t0d0"
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk.label = "VTOC"

        # 100GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

        # create a single 50 GB partition inside the disk
        self.partition = self.disk.add_partition(1, CYLSIZE, 50, Size.gb_units)

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.disk.delete_children()
        self.disk.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_single_slice(self):
        # add a 1GB slice at start_sector CYLSIZE
        self.partition.add_slice(0, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_cylinder_zero_boundary_adjustment(self):
        # add a 1GB slice at start_sector 0
        self.partition.add_slice(0, 0, 1, Size.gb_units)

        # test that it moved to the first cylinder boundary
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(self.partition._children[0].start_sector, CYLSIZE)

    def test_add_too_many_slices(self):
        for i in range(V_NUMPAR + 2):
            start_sector = i * GBSECTOR + i
            self.partition.add_slice(i, start_sector, 1)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.TooManySlicesError))

    def test_duplicate_slice(self):
        # add 2 1GB slices with the same index but different starting sector
        self.partition.add_slice(0, 0, 1, Size.gb_units)

        # account for the first silce moving from a start_sector of 0 to
        # CYLSIZE
        self.partition.add_slice(0, CYLSIZE + GBSECTOR + 1, 1,
                                 Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.DuplicateSliceNameError))

    def test_overlapping_starting_sector(self):
        # add a 10 GB disk
        self.partition.add_slice(0, CYLSIZE, 10, Size.gb_units)
        # add an 11 GB disk
        self.partition.add_slice(1, CYLSIZE, 11, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceError))

    def test_overlapping_ending_sector(self):
        # add a 9 GB disk on the second cylinder boundary
        self.partition.add_slice(0, CYLSIZE * 2, 9, Size.gb_units)
        # add a 10 GB disk on the first cylinder boundary
        self.partition.add_slice(1, CYLSIZE, 10, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceError))

    def test_delete_slice(self):
        s1 = self.partition.add_slice(1, 0, 1, Size.gb_units)
        s2 = self.partition.add_slice(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in the _children
        self.assertEqual(len(self.partition._children), 2)

        # delete slice 2
        s2.delete()

        # verify there is only one entry in the _children and the proper
        # slice was removed.
        self.assertEqual(len(self.partition._children), 1)
        self.assertEqual(self.partition._children[0].name, 1)

    def test_delete_slice_in_partition(self):
        s1 = self.partition.add_slice(1, 0, 1, Size.gb_units)
        s2 = self.partition.add_slice(2, GBSECTOR + 1, 1, Size.gb_units)

        # verify there are 2 entries in the _children
        self.assertEqual(len(self.partition._children), 2)

        # delete slice 2
        self.partition.delete_slice(s2)

        # verify there is only one entry in the _children and the proper
        # slice was removed.
        self.assertEqual(len(self.partition._children), 1)
        self.assertEqual(self.partition._children[0].name, 1)

    def test_resize_slice(self):
        # create a 1 GB slice
        s1 = self.partition.add_slice(0, CYLSIZE, 1, Size.gb_units)

        # verify the size of the slice is 1 GB of sectors, rounded for CYLSIZE
        self.assertEqual(s1.size.sectors, (GBSECTOR / CYLSIZE) * CYLSIZE)

        # resize it to 5 GB
        new_s1 = s1.resize(5, Size.gb_units)

        # verify the size of the slice is 5 GB of sectors
        self.assertTrue(new_s1.size.sectors, 5 * GBSECTOR)

    def test_a_in_zpool_confilict_with_disk(self):
        # set the in_zpool attribute in the disk
        self.disk.in_zpool = "tank"

        # create a 1 GB partition
        self.partition.add_slice(1, 0, 1, Size.gb_units, in_zpool="tank")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceZpoolError))

    def test_in_vdev_confilict_with_disk(self):
        # set the in_vdev attribute in the disk
        self.disk.in_vdev = "a label"

        # create a 1 GB partition
        self.partition.add_slice(1, 0, 1, Size.gb_units, in_vdev="a label")

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.OverlappingSliceVdevError))

    def test_holey_object_no_children(self):
        holey_list = self.partition.get_gaps()
        self.assertEqual(holey_list[0].size, self.partition.size)

    def test_holey_object_one_child_start_at_nonzero(self):
        # add a single partition, starting at start sector CYLSIZE * 10
        start = CYLSIZE * 10
        s = self.partition.add_slice(1, start, 25, Size.gb_units)

        holey_list = self.partition.get_gaps()

        # verify the holey list is correct
        self.assertEqual(len(holey_list), 2)

        self.assertEqual(holey_list[0].start_sector, 0)
        self.assertEqual(holey_list[0].size.sectors, start - 1)
        self.assertEqual(holey_list[1].start_sector, \
            10 * CYLSIZE + s.size.sectors + 1)
        self.assertEqual(holey_list[1].size.sectors, \
            self.partition.size.sectors - s.size.sectors - 10 * CYLSIZE - 1)

    def test_partition_remaining_space(self):
        s = self.partition.add_slice(0, CYLSIZE, 5, Size.gb_units)
        self.assertEqual(self.partition.remaining_space.sectors,
                         self.partition.size.sectors - s.size.sectors)

    def test_invalid_start_sector(self):
        self.partition.add_slice(0, -16065, 1, Size.gb_units)
        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.InvalidSliceStartSectorError))

    def test_slice_entire_size_of_partition(self):
        # add a non V_BACKUP slice the entire size of the partition
        s = self.partition.add_slice(0, CYLSIZE, self.partition.size.sectors,
                                     Size.sector_units)

        # verify there are no errors
        self.assertFalse(errsvc._ERRORS)

        # verify the size of the slice
        self.assertEqual(self.partition.size.sectors, s.size.sectors)

    def test_no_validate_children(self):
        self.partition.validate_children = False
        start_sector = 12345
        s = self.partition.add_slice(1, 12345, 5, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(start_sector, s.start_sector)
        self.assertEqual(Size("5gb"), s.size)

    def test_insertion_of_slice_over_deleted_slice_of_same_name(self):
        # add a 1GB slice at start_sector CYLSIZE and set the action to delete
        s = self.partition.add_slice(0, CYLSIZE, 1, Size.gb_units)
        s.action = "delete"

        # insert another slice with the same name
        self.partition.add_slice(0, CYLSIZE, 2, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_resize_child_slice_at_start(self):
        # +-----------------+
        # |            |////|
        # |    s1      |/g1/|
        # +-----------------+
        original_s1 = self.partition.add_slice(1, CYLSIZE, 10, Size.gb_units)

        # increase the size of s1 into gap 1
        s1 = self.partition.resize_slice(original_s1, 25, Size.gb_units)
        self.assertEqual(original_s1.start_sector, s1.start_sector)
        self.assertEqual(s1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of s1 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            s1, 100, Size.gb_units)

    def test_resize_child_slice_at_end(self):
        # +-----------------+
        # |////|            |
        # |/g1/|     s1     |
        # +-----------------+
        start_sector = (self.partition.start_sector + \
                        self.partition.size.sectors) - 10 * GBSECTOR
        original_s1 = self.partition.add_slice(1, start_sector, 10,
                                               Size.gb_units)

        # increase the size of s1 into gap 1
        s1 = self.partition.resize_slice(original_s1, 25, Size.gb_units)
        self.assertEqual(s1.start_sector,
            original_s1.start_sector - (15 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(s1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of s1 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            s1, 100, Size.gb_units)

    def test_resize_child_slice_only_right(self):
        # +-----------------------+
        # |            |     |////|
        # |    s1      | s2  |/g1/|
        # +-----------------------+
        s1 = self.partition.add_slice(1, CYLSIZE, 10, Size.gb_units)
        gaps = self.partition.get_gaps()
        original_s2 = self.partition.add_slice(2, gaps[0].start_sector, 10,
                                               Size.gb_units)

        # increase the size of s2 into gap 1
        s2 = self.partition.resize_slice(original_s2, 25, Size.gb_units)
        self.assertEqual(s2.start_sector, original_s2.start_sector)
        self.assertEqual(s2.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of s2 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            s2, 100, Size.gb_units)

    def test_resize_child_slice_only_left(self):
        # +------------------------+
        # |////|            |      |
        # |/g1/|     s1     |  s2  |
        # +------------------------+
        start_sector = (self.partition.start_sector + \
                        self.partition.size.sectors) - 10 * GBSECTOR
        s2 = self.partition.add_slice(2, start_sector, 10, Size.gb_units)
        original_s1 = self.partition.add_slice(1,
            start_sector - (10 * GBSECTOR), 10, Size.gb_units)

        # increase the size of s1 into gap 1
        s1 = self.partition.resize_slice(original_s1, 25, Size.gb_units)
        self.assertEqual(s1.start_sector,
            original_s1.start_sector - CYLSIZE - \
                (15 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(s1.size.sectors,
            Size("25gb").sectors / CYLSIZE * CYLSIZE)

        # increase the size of s1 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            s1, 100, Size.gb_units)

    def test_resize_child_slice_no_room(self):
        # +------------------------+
        # |    |            |      |
        # | s1 |     s2     |  s3  |
        # +------------------------+
        s1 = self.partition.add_slice(1, CYLSIZE, 10, Size.gb_units)
        gaps = self.partition.get_gaps()
        original_s2 = self.partition.add_slice(2, gaps[0].start_sector, 10,
                                               Size.gb_units)
        gaps = self.partition.get_gaps()
        s3 = self.partition.add_slice(3, gaps[0].start_sector, 10,
                                      Size.gb_units)

        # verify s2 can not be increased in size beyond the original 10gb
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            original_s2, 10.1, Size.gb_units)

    def test_resize_child_slice_with_gaps_on_either_side(self):
        # +----------------------------+
        # |    |//////|    |//////|    |
        # | s1 |//g1//| s2 |//g2//| s3 |
        # +----------------------------+
        s1 = self.partition.add_slice(1, CYLSIZE, 10, Size.gb_units)
        original_s2 = self.partition.add_slice(2, 25 * GBSECTOR, 10,
                                               Size.gb_units)
        s3 = self.partition.add_slice(3, 40 * GBSECTOR, 10, Size.gb_units)

        # increase the size of s2 into g2, but not to exceed it
        s2 = self.partition.resize_slice(original_s2, 15, Size.gb_units)
        self.assertEqual(original_s2.start_sector, s2.start_sector)
        self.assertEqual(s2.size.sectors,
            Size("15gb").sectors / CYLSIZE * CYLSIZE)

        # destroy slice 2 and re-insert
        self.partition.delete_children(class_type=Slice, name=2)
        original_s2 = self.partition.add_slice(2, 25 * GBSECTOR, 10,
                                               Size.gb_units)

        # increase the size of s2 to consume all of g2 and part of g1
        s2 = self.partition.resize_slice(original_s2, 20, Size.gb_units)
        self.assertEqual(s2.start_sector,
            original_s2.start_sector - (5 * GBSECTOR) / CYLSIZE * CYLSIZE)
        self.assertEqual(s2.size.sectors,
            Size("20gb").sectors / CYLSIZE * CYLSIZE)

        # destroy slice 2 and re-insert
        self.partition.delete_children(class_type=Slice, name=2)
        original_s2 = self.partition.add_slice(2, 25 * GBSECTOR, 10,
                                               Size.gb_units)

        # increase the size of s2 beyond the bounds of the two gaps
        self.assertRaises(InsufficientSpaceError, self.partition.resize_slice,
            original_s2, 30, Size.gb_units)


class TestLogicalPartition(unittest.TestCase):

    def setUp(self):
        self.disk = Disk("test disk")
        self.disk.ctd = "c12345t0d0"
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk.label = "VTOC"

        # 100GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.disk.delete_children()
        self.disk.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_single_logical_partition(self):
        # add a 10 GB extended partition (type is 0xf or "15")
        self.disk.add_partition(1, 0, 10, Size.gb_units,
                                Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)

        # add a logical partition to the disk
        self.disk.add_partition(5, 0, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)

    def test_add_three_logical_partitions_in_order(self):
        # add a 10 GB extended partition (type is 0xf or "15")
        ep = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)

        # add a logical partition to the disk
        l1 = self.disk.add_partition(5, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l1.start_sector, ep.start_sector + LOGICAL_ADJUSTMENT)
        self.assertEqual(l1.size.sectors, GBSECTOR - LOGICAL_ADJUSTMENT)

        # add a second logical partition to the disk
        l2 = self.disk.add_partition(6, CYLSIZE + GBSECTOR + 64, 1,
                                     Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l2.start_sector, \
            l1.start_sector + l1.size.sectors + LOGICAL_ADJUSTMENT + 1)
        self.assertEqual(l2.size.sectors, GBSECTOR)

        # add a third logical partition to the disk
        l3 = self.disk.add_partition(8, CYLSIZE + (GBSECTOR * 2) + 128, 1,
                                     Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l3.start_sector, \
            l2.start_sector + l2.size.sectors + LOGICAL_ADJUSTMENT + 1)
        self.assertEqual(l3.size.sectors, GBSECTOR)

    def test_add_three_logical_partitions_out_of_order(self):
        # add a 10 GB extended partition (type is 0xf or "15")
        ep = self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)

        # add a logical partition to the disk (at the 'end')
        l1 = self.disk.add_partition(5, CYLSIZE + (GBSECTOR * 2) + 128, 1,
                                     Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l1.start_sector, CYLSIZE + (GBSECTOR * 2) + 128)
        self.assertEqual(l1.size.sectors, GBSECTOR)

        # add a second logical partition to the disk (at the 'beginning')
        l2 = self.disk.add_partition(6, CYLSIZE, 1, Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l2.start_sector, ep.start_sector + LOGICAL_ADJUSTMENT)
        self.assertEqual(l2.size.sectors, GBSECTOR - LOGICAL_ADJUSTMENT)

        # add a third logical partition to the disk (in the 'middle')
        l3 = self.disk.add_partition(8, CYLSIZE + GBSECTOR + 64, 1,
                                     Size.gb_units)
        self.assertFalse(errsvc._ERRORS)
        self.assertEqual(l3.start_sector, \
            l2.start_sector + l2.size.sectors + LOGICAL_ADJUSTMENT + 1)
        self.assertEqual(l3.size.sectors, GBSECTOR)

    def test_add_logical_without_extended(self):
        # add a logical partition to the disk
        self.disk.add_partition(5, 0, 1, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
                                   ShadowPhysical.NoExtPartitionsError))

    def test_add_too_many_logical_partitions(self):
        # add a 50 GB extended partition (type is 0xf or "15")
        self.disk.add_partition(1, 0, 50, Size.gb_units,
                                Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)

        # add MAX_EXT_PARTS
        for i in range(5, 5 + MAX_EXT_PARTS + 2):
            start_sector = i * GBSECTOR
            self.disk.add_partition(i, start_sector, 1, Size.gb_units)

        # verify there are two errors in the errsvc list.  One for an invalid
        # name and one for exceeding the number of logical partitions
        self.assertEqual(len(errsvc._ERRORS), 2)
        invalid_error = errsvc._ERRORS[0]
        toomany_error = errsvc._ERRORS[1]

        self.assertTrue(isinstance(invalid_error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.InvalidPartitionNameError))
        self.assertTrue(isinstance(toomany_error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.TooManyLogicalPartitionsError))

    def test_add_too_large_logical_partition(self):
        # add a 10 GB extended partition
        self.disk.add_partition(1, CYLSIZE, 10, Size.gb_units,
                                Partition.name_to_num("WIN95 Extended(LBA)"))
        self.assertFalse(errsvc._ERRORS)

        # add 20 GB logical partition starting at the same place
        self.disk.add_partition(5, CYLSIZE, 20, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.LogicalPartitionOverlapError))

    def test_resize_child_partition_at_start(self):
        # +-----------------+
        # |            |////|
        # |    p5      |/g1/|
        # +-----------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        self.disk.add_partition(1, 0, 75, Size.gb_units,
                                Partition.name_to_num("WIN95 Extended(LBA)"))
        original_p5 = self.disk.add_partition(5, CYLSIZE, 10, Size.gb_units)

        # increase the size of p5 into gap 1
        p5 = self.disk.resize_partition(original_p5, 25, Size.gb_units)
        self.assertEqual(original_p5.start_sector, p5.start_sector)
        self.assertEqual(p5.size.sectors, Size("25gb").sectors)

        # increase the size of p5 beyond the bounds of the disk
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p5, 100, Size.gb_units)

    def test_resize_child_partition_at_end(self):
        # +-----------------+
        # |////|            |
        # |/g1/|     p5     |
        # +-----------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        p1 = self.disk.add_partition(1, 0, 75, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))
        start_sector = p1.size.sectors - 10 * GBSECTOR
        original_p5 = self.disk.add_partition(5, start_sector, 10,
                                              Size.gb_units)

        # increase the size of p5 into gap 1
        p5 = self.disk.resize_partition(original_p5, 25, Size.gb_units)
        self.assertEqual(p5.start_sector,
            original_p5.start_sector - (15 * GBSECTOR) + CYLSIZE - 1)
        self.assertEqual(p5.size.sectors, Size("25gb").sectors)

        # increase the size of p5 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p5, 100, Size.gb_units)

    def test_resize_child_partition_only_right(self):
        # +-----------------------+
        # |            |     |////|
        # |    p5      | p6  |/g1/|
        # +-----------------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        p1 = self.disk.add_partition(1, 0, 75, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))

        p5 = self.disk.add_partition(5, CYLSIZE, 10, Size.gb_units)
        gaps = self.disk.get_logical_partition_gaps()
        original_p6 = self.disk.add_partition(6, gaps[0].start_sector, 10,
                                              Size.gb_units)

        # increase the size of p6 into gap 1
        p6 = self.disk.resize_partition(original_p6, 25, Size.gb_units)
        self.assertEqual(p6.start_sector, original_p6.start_sector)
        self.assertEqual(p6.size.sectors, Size("25gb").sectors)

        # increase the size of p6 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p6, 100, Size.gb_units)

    def test_resize_child_partition_only_left(self):
        # +------------------------+
        # |////|            |      |
        # |/g1/|     p5     |  p6  |
        # +------------------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        p1 = self.disk.add_partition(1, 0, 75, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))

        start_sector = p1.size.sectors - 10 * GBSECTOR
        original_p6 = self.disk.add_partition(6, start_sector, 10,
                                              Size.gb_units)

        original_p5 = self.disk.add_partition(5,
            start_sector - (10 * GBSECTOR), 10, Size.gb_units)

        # increase the size of p5 into gap 1
        p5 = self.disk.resize_partition(original_p5, 25, Size.gb_units)
        self.assertEqual(p5.start_sector,
            original_p5.start_sector - (15 * GBSECTOR))
        self.assertEqual(p5.size.sectors, Size("25gb").sectors)

        # increase the size of p5 beyond the bounds of the partition
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            p5, 100, Size.gb_units)

    def test_resize_child_partition_no_room(self):
        # +------------------------+
        # |    |            |      |
        # | p5 |     p6     |  p7  |
        # +------------------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        p1 = self.disk.add_partition(1, 0, 75, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))

        p5 = self.disk.add_partition(5, CYLSIZE, 10, Size.gb_units)
        gaps = self.disk.get_logical_partition_gaps()
        original_p6 = self.disk.add_partition(6, gaps[0].start_sector, 10,
                                              Size.gb_units)
        gaps = self.disk.get_logical_partition_gaps()
        p7 = self.disk.add_partition(7, gaps[0].start_sector, 10,
                                     Size.gb_units)

        # verify p6 can not be increased in size beyond the original 10gb
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            original_p6, 10.1, Size.gb_units)

    def test_resize_child_partition_with_gaps_on_either_side(self):
        # +----------------------------+
        # |    |//////|    |//////|    |
        # | p5 |//g1//| p6 |//g2//| p7 |
        # +----------------------------+
        # add a 75 GB extended partition (type is 0xf or "15")
        p1 = self.disk.add_partition(1, 0, 75, Size.gb_units,
            Partition.name_to_num("WIN95 Extended(LBA)"))

        p5 = self.disk.add_partition(5, CYLSIZE, 10, Size.gb_units)
        original_p6 = self.disk.add_partition(6, 25 * GBSECTOR, 10,
                                              Size.gb_units)
        p7 = self.disk.add_partition(7, 40 * GBSECTOR, 10, Size.gb_units)

        # increase the size of p6 into g2, but not to exceed it
        p6 = self.disk.resize_partition(original_p6, 11, Size.gb_units)
        self.assertEqual(original_p6.start_sector, p6.start_sector)
        self.assertEqual(p6.size.sectors, Size("11gb").sectors)

        # destroy partition 2 and re-insert
        self.disk.delete_children(class_type=Partition, name=6)
        original_p6 = self.disk.add_partition(6, 25 * GBSECTOR, 10,
                                              Size.gb_units)

        # increase the size of p6 to consume all of g2 and part of g1
        p6 = self.disk.resize_partition(original_p6, 20, Size.gb_units)
        self.assertEqual(p6.start_sector,
            original_p6.start_sector - (5 * GBSECTOR) - 1)
        self.assertEqual(p6.size.sectors, Size("20gb").sectors)

        # destroy partition 6 and re-insert
        self.disk.delete_children(class_type=Partition, name=6)
        original_p6 = self.disk.add_partition(6, 25 * GBSECTOR, 10,
                                              Size.gb_units)

        # increase the size of p6 beyond the bounds of the two gaps
        self.assertRaises(InsufficientSpaceError, self.disk.resize_partition,
            original_p6, 35, Size.gb_units)


class TestFinalValidation(unittest.TestCase):

    def setUp(self):
        self.target = Target(Target.DESIRED)
        self.logical = Logical("logical")

        self.disk1 = Disk("disk")
        self.disk1.ctd = "c12345t0d0"
        self.disk1.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk1.label = "VTOC"

        # 100GB disk
        self.disk1.disk_prop = DiskProp()
        self.disk1.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk1.disk_prop.blocksize = BLOCKSIZE

        # reset the errsvc
        errsvc.clear_error_list()

    def tearDown(self):
        self.target.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_simple(self):
        # insert the smallest required objects:   one disk, one active solaris2
        # partition and one slice with in_zpool set to the root pool name, one
        # BE under the root pool

        # 10 gb partition, 1 gb slice
        p = self.disk1.add_partition(1, 0, 10, Size.gb_units,
                                     bootid=Partition.ACTIVE)
        p.add_slice(0, 0, 1, in_zpool="rpool")

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=True)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertTrue(self.target.final_validation())

    def test_simple_with_solaris2_on_logical(self):
        # insert the smallest required objects:   one disk, one active solaris2
        # logical partition and one slice with in_zpool set to the root pool
        # name, one BE under the root pool

        # 30 gb primary partition, 10 gb logical solaris2 partition, and 1 gb
        # slice
        primary_part = self.disk1.add_partition(1, 0, 30, Size.gb_units,
            Partition.name_to_num("Win95 Extended(LBA)"))
        logical_part = self.disk1.add_partition(5, 0, 10, Size.gb_units)
        logical_part.add_slice(0, 0, 1, in_zpool="rpool")

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=True)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertTrue(self.target.final_validation())

    def test_missing_active_solaris2_partition_x86(self):
        if platform.processor() != "i386":
            raise SkipTest("test not supported on sparc")

        # 10 gb partition defaults to INACTIVE, 1 gb slice
        p = self.disk1.add_partition(1, 0, 10, Size.gb_units)
        p.add_slice(0, 0, 1, in_zpool="rpool")

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=True)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertFalse(self.target.final_validation())

    def test_no_root_zpool(self):
        # 10 gb partition, 1 gb slice
        p = self.disk1.add_partition(1, 0, 10, Size.gb_units,
                                     bootid=Partition.ACTIVE)
        p.add_slice(0, 0, 1, in_zpool="rpool")

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=False)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertFalse(self.target.final_validation())

    def test_whole_disk_set(self):
        self.disk1.whole_disk = True

        # 10 gb partition, 1 gb slice
        p = self.disk1.add_partition(1, 0, 10, Size.gb_units,
                                     bootid=Partition.ACTIVE)
        p.add_slice(0, 0, 1)

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=False)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertFalse(self.target.final_validation())

    def test_no_BE(self):
        # 10 gb partition, 1 gb slice
        p = self.disk1.add_partition(1, 0, 10, Size.gb_units,
                                     bootid=Partition.ACTIVE)
        p.add_slice(0, 0, 1)

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=False)

        self.target.insert_children([self.disk1, self.logical])

        self.assertFalse(self.target.final_validation())

    def test_simple_failure_two_slices_under_partition(self):
        # create a single 10gb partition
        partition = self.disk1.add_partition("1", 0, 10, Size.gb_units,
                                             bootid=Partition.ACTIVE)

        # create two slices that overlap
        partition.add_slice("0", CYLSIZE, 1, Size.gb_units)
        partition.add_slice("1", CYLSIZE, 1, Size.gb_units)

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=False)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])
        self.assertFalse(self.target.final_validation())

    def test_invalid_parent_with_valid_child(self):
        # 10 gb logical partition (with no extended partition), 1 gb slice
        p = self.disk1.add_partition(5, 0, 10, Size.gb_units,
                                     bootid=Partition.ACTIVE)
        p.add_slice(0, 0, 1, in_zpool="rpool")

        # "rpool" boot pool with one BE
        zpool = self.logical.add_zpool("rpool", is_root=True)
        zpool.insert_children(BE())

        self.target.insert_children([self.disk1, self.logical])

        self.assertFalse(self.target.final_validation())


class TestInUse(unittest.TestCase):

    def setUp(self):
        # find the list of vdevs for the root pool
        cmd = ["/usr/sbin/zpool", "list", "-H", "-o", "name,bootfs"]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        for line in p.stdout.splitlines():
            (name, bootfs) = line.split()
            if bootfs != "-":
                root_pool = name
                break
        else:
            raise SkipTest("unable to find root pool name")

        # find the list of vdevs that compose the 'rpool' zpool
        rpool_map = _get_vdev_mapping(root_pool)

        # take the first key in the rpool_map and use the first slice that
        # makes up that key's mapping
        self.in_use_slice = rpool_map[rpool_map.keys()[0]][0]
        (self.ctd, _none, self.index) = \
            self.in_use_slice.split("/")[-1].partition("s")

        # construct a disk DOC object from the in_use_slice
        self.disk = Disk("test disk")
        self.disk.ctd = self.ctd
        self.disk.geometry = DiskGeometry(BLOCKSIZE, CYLSIZE)
        self.disk.label = "VTOC"

        # 100GB disk
        self.disk.disk_prop = DiskProp()
        self.disk.disk_prop.dev_size = Size(
            str(GBSECTOR * 100) + Size.sector_units)
        self.disk.disk_prop.blocksize = BLOCKSIZE

    def tearDown(self):
        self.disk.delete_children()
        self.disk.delete()

        # reset the errsvc
        errsvc.clear_error_list()

    def test_add_slice_in_use(self):
        self.disk.add_slice(self.index, 0, 1, Size.gb_units)

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.SliceInUseError))

    def test_delete_slice_in_use(self):
        # the add slice will set an error, but we want to test delete.
        s = self.disk.add_slice(self.index, 0, 1, Size.gb_units)
        errsvc.clear_error_list()
        s.delete()

        # verify there is only one error in the errsvc list and that it is the
        # proper error
        self.assertEqual(len(errsvc._ERRORS), 1)
        error = errsvc._ERRORS[0]
        self.assertTrue(isinstance(error.error_data[ES_DATA_EXCEPTION],
            ShadowPhysical.SliceInUseError))

    def test_force_delete_slice_in_use(self):
        # the add slice will set an error, but we want to test delete.
        s = self.disk.add_slice(self.index, 0, 1, Size.gb_units)
        s.force = True
        errsvc.clear_error_list()
        s.delete()
        self.assertFalse(errsvc._ERRORS)


class TestSize(unittest.TestCase):

    def test_add_size(self):
        size1 = Size("1024mb")
        size2 = Size("1024mb")
        self.assertEqual(size1 + size2, Size("2gb"))
        size1 += Size("3gb")
        self.assertEqual(size1, Size("4gb"))

    def test_sub_size(self):
        size1 = Size("4096mb")
        size2 = Size("2048mb")
        self.assertEqual(size1 - size2, Size("2gb"))

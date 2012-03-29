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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
import osol_install.errsvc as errsvc

from solaris_install.target.libadm.const import FD_NUMPART, MAX_EXT_PARTS, \
    V_BACKUP, V_BOOT, V_NUMPAR
from solaris_install.target.libdiskmgt import const as ldm_const
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.libefi.const import EFI_NUMPAR, EFI_NUMUSERPAR
from solaris_install.target.libefi.cstruct import EFI_MAXPAR
from solaris_install.target.shadow import ShadowList, ShadowExceptionBase
from solaris_install.target.size import Size

LOGICAL_ADJUSTMENT = 63

# Lowest common multiple blocksize that ensures physical block alignment for
# all block size multiples from 512bytes up to the maximum 128KB volume block
# size for LUNs in the Sun Unified Storage appliance. For info see:
# blogs.oracle.com/dlutz/entry/partition_alignment_guidelines_for_unified
EFI_BLOCKSIZE_LCM = (128 * 1024)


class ShadowPhysical(ShadowList):
    """ ShadowPhysical - class to hold and validate Physical objects
    (GPTPartition, Partition and Slice)
    """
    class WholeDiskIsTrueError(ShadowExceptionBase):
        def __init__(self):
            self.value = "whole_disk attribute for this Disk is set to " + \
                         "'true'. GPTPartitions, partitions or slices " + \
                         "cannot be specified for this Disk"

    # GPTPartition exception classes
    class GPTPartitionInUseError(ShadowExceptionBase):
        def __init__(self, in_use):
            s = in_use["used_by"][0]
            if "used_name" in in_use:
                s += ": %s" % in_use["used_name"][0]
            self.value = "GPT partition currently in use by %s" % s

    class DuplicateGPTPartitionNameError(ShadowExceptionBase):
        def __init__(self, gpart_name):
            self.value = "GPT partition name %s already inserted" % gpart_name

    class InvalidGPTPartitionNameError(ShadowExceptionBase):
        def __init__(self, name, ctd):
            self.value = "Invalid name:  '%s' for GPT partition " % name + \
                         "on disk:  %s" % ctd

    class InvalidGPTPartitionStartSectorError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Invalid entry for GPT partition's start_sector"

    class OverlappingGPTPartitionError(ShadowExceptionBase):
        def __init__(self, partition_name, existing_partition):
            self.value = "GPT partition %s overlaps with" % partition_name + \
                         " existing GPT partition: %s" % existing_partition

    class OverlappingGPTPartitionVdevError(ShadowExceptionBase):
        def __init__(self):
            self.value = "GPT partition in_vdev attribute overlaps " + \
                         "with parent"

    class OverlappingGPTPartitionZpoolError(ShadowExceptionBase):
        def __init__(self):
            self.value = "GPT partition in_zpool attribute overlaps " + \
                         "with parent"

    class GPTPartitionTypeMissingError(ShadowExceptionBase):
        def __init__(self):
            self.value = "GPT partition has invalid partition type"

    class TooManyGPTPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Only %d GPT partitions may be inserted" % \
                         EFI_MAXPAR

    # Slice exception classes
    class OverlappingSliceError(ShadowExceptionBase):
        def __init__(self, slice_name, existing_slice):
            self.value = "Slice %s overlaps with existing slice: %s" % \
                         (slice_name, existing_slice)

    class OverlappingSliceZpoolError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Slice in_zpool attribute overlaps with parent"

    class OverlappingSliceVdevError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Slice in_vdev attribute overlaps with parent"

    class SliceTooLargeError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Slice too large"

    class DuplicateSliceNameError(ShadowExceptionBase):
        def __init__(self, slice_name):
            self.value = "Slice name %s already inserted" % slice_name

    class TooManySlicesError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Only %d slices may be inserted" % V_NUMPAR

    class InvalidSliceStartSectorError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Invalid entry for slice's start_sector"

    class SliceInUseError(ShadowExceptionBase):
        def __init__(self, in_use):
            s = in_use["used_by"][0]
            if "used_name" in in_use:
                s += ": %s" % in_use["used_name"][0]
            self.value = "Slice currently in use by %s" % s

    # Partition (MBR) exception classes
    class DuplicatePartitionNameError(ShadowExceptionBase):
        def __init__(self, partition_name):
            self.value = "Partition name %s already inserted" % partition_name

    class FAT16PartitionTooLargeError(ShadowExceptionBase):
        def __init__(self):
            self.value = "FAT16 Partition is too large.  It must not " + \
                         "exceed 4GB"

    class InvalidPartitionNameError(ShadowExceptionBase):
        def __init__(self, name, ctd):
            self.value = "Invalid name:  '%s' for partition " % name + \
                         "on disk:  %s" % ctd

    class InvalidPartitionStartSectorError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Invalid entry for partition's start_sector"

    class InvalidTypeError(ShadowExceptionBase):
        def __init__(self, valid_type):
            self.value = "Invalid partition type for operation.  Requires " + \
                         "type:  %s" % valid_type

    class MultipleActivePartitionsError(ShadowExceptionBase):
        def __init__(self, partition_name):
            self.value = "Partition %s already marked as active" % \
                         partition_name

    class OverlappingPartitionError(ShadowExceptionBase):
        def __init__(self, partition_name, existing_partition):
            self.value = "Partition %s overlaps with " % partition_name + \
                         "existing partition: %s" % existing_partition

    class OverlappingPartitionVdevError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition in_vdev attribute overlaps with parent"

    class OverlappingPartitionZpoolError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition in_zpool attribute overlaps with parent"

    class PartitionTypeMissingError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition has invalid partition type"

    # Logical partition exception classes
    class LogicalPartitionOverlapError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Logical partition exceeds the start or end " + \
                         "sector of the extended partition"

    class TooManyLogicalPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Only %d logical partitions may be inserted" % \
                         MAX_EXT_PARTS

    # Extented partition exception classes
    class ExtPartitionTooSmallError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Extended Partition is too small.  It must be 63 " + \
                         "sectors or larger."

    class NoExtPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "A logical partition exists without an extended " + \
                         "partition"

    class TooManyExtPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "There is already an extended partition set for " + \
                         "this Disk"

    def in_use_check(self, value):
        """ in_use_check() - method to query the "discovered" DOC tree
        for in_use conflicts.
        """
        in_use = dict()

        # If this is a Slice within a Partition object we need to
        # to go up 2 ancestors higher to get the Disk object.
        if self.container.__class__.__name__ == "Partition":
            desired_disk = self.container.parent
        else:
            desired_disk = self.container

        # Get the root DOC node and find the discovered sub-tree.
        # Not finding discovered here would be an error under normal
        # conditions but most unit tests don't create the discovered
        # tree. So we just return nothing if the discovered tree or
        # disk is not found.
        root = self.container.root_object
        discovered = root.get_descendants(name="discovered",
            max_count=1, not_found_is_err=False)
        if not discovered:
            return in_use

        disks = discovered[0].get_descendants(name="disk",
            not_found_is_err=False)

        # Look through the discovered disks and match it with ours
        for disk in disks:
            if disk.name_matches(desired_disk):
                # Find the matching slice/(gpt)partition object and make
                # sure we're comparing apples to apples.
                partyslices = disk.get_descendants(name=value.name)
                if not partyslices:
                    break

                for partyslice in partyslices:
                    if partyslice.__class__.__name__ == \
                        value.__class__.__name__:
                        in_use = partyslice.in_use
                        break

            if in_use:
                break

        return in_use

    def insert_slice(self, index, value):
        """ insert_slice() - override method for validation of Slice DOC
        objects.

        the following checks are done as part of validation:

        - the parent Disk object does not have whole_disk attribute set

        - the start_sector of the slice is an int or long and is between 0 and
          the container's maximum size

        - no overlapping boundaries of the slice with any other slices already
          inserted

        - no more than V_NUMPAR slices

        - no duplicate indexes (ie. no duplicate slice numbers)

        - none of the parent objects have an in_zpool or in_vdev attribute set
        """
        # set the proper cylinder boundary and parent_size based on
        # the container type
        if hasattr(self.container, "geometry"):
            # container is a Disk object
            parent_size = self.container.disk_prop.dev_size.sectors
            label = self.container.label

            # verify that the Disk does not have 'whole_disk' set to 'true'
            if self.container.whole_disk:
                self.set_error(self.WholeDiskIsTrueError())

        elif hasattr(self.container, "part_type"):
            # container is a Partition object
            parent_size = self.container.size.sectors
            label = self.container.parent.label

        # check the bounds of the slice to be added.
        if not (isinstance(value.start_sector, int) or \
           isinstance(value.start_sector, long)):
            self.set_error(self.InvalidSliceStartSectorError())
        if not (0 <= value.start_sector <= parent_size):
            self.set_error(self.InvalidSliceStartSectorError())

        # find the cylinder boundary of the disk and adjust the Slice's start
        # and size to fall on a cylinder boundary.  start and end will be on
        # the boundaries and in blocks.

        # only adjust the start sector for VTOC slices that are do not have the
        # V_BOOT or V_BACKUP tag.
        if label == "VTOC" and value.tag not in [V_BACKUP, V_BOOT]:
            # fix the start_sector and size to align to cylinder boundaries
            value = self.cylinder_boundary_adjustment(value)

        cb_start = value.start_sector
        cb_end = value.start_sector + value.size.sectors - 1

        # verify each slice does not overlap with any other slice
        for slc in self._shadow:
            # if slice 2 is being inserted into a VTOC labeled disk, do not
            # check for overlap
            if label == "VTOC" and int(value.name) == 2:
                break

            # skip VTOC overlap slice if it is already inserted into the
            # shadow list
            if label == "VTOC" and int(slc.name) == 2:
                continue

            # calculate the range of each slice already inserted
            start = slc.start_sector
            end = slc.start_sector + slc.size.sectors - 1

            # check that the start sector is not within another slice and
            # the existing slice isn't inside the new slice but only for slices
            # not marked for deletion
            if value.action != "delete" and slc.action != "delete":
                if (start <= cb_start <= end or start <= cb_end <= end) or \
                   (cb_start <= start <= cb_end or cb_start <= end <= cb_end):
                    self.set_error(
                        self.OverlappingSliceError(value.name, slc.name))

        if len(self._shadow) >= V_NUMPAR:
            self.set_error(self.TooManySlicesError())

        # check for duplicate slice.name values
        if value.name in [slc.name for slc in self._shadow \
                          if slc.action != "delete"]:
            self.set_error(self.DuplicateSliceNameError(value.name))

        # check for in_zpool overlap
        if value.in_zpool is not None:
            # check the container
            if getattr(self.container, "in_zpool") == value.in_zpool:
                self.set_error(self.OverlappingSliceZpoolError())
            # check the container's parent if it's a partition
            if hasattr(self.container, "part_type"):
                if getattr(self.container.parent, "in_zpool") == \
                   value.in_zpool:
                    self.set_error(self.OverlappingSliceZpoolError())

        # check for in_vdev overlap
        if value.in_vdev is not None:
            # check the container
            if getattr(self.container, "in_vdev") == value.in_vdev:
                self.set_error(self.OverlappingSliceVdevError())
            # check the container's parent if it's a partition
            if hasattr(self.container, "part_type"):
                if getattr(self.container.parent, "in_vdev") == \
                   value.in_vdev:
                    self.set_error(self.OverlappingSliceVdevError())

        # check for in_use conflicts.
        stats = self.in_use_check(value)
        if stats and value.action != "preserve" and not value.force:
            self.set_error(self.SliceInUseError(stats))

        # insert the corrected Slice object
        ShadowList.insert(self, index, value)

    def insert_gptpartition(self, index, value):
        """ insert_gptpartition() - override method for validation of
        GPTPartition DOC objects.

        the following checks are done as part of validation:

        - the parent Disk object does not have whole_disk attribute set

        - the start_sector of the slice is an int or long and is between 0 and
          the container's maximum size

        - no overlapping boundaries of the GPT partition with any other
          GPT partitions already inserted

        - no more than EFI_NUMUSERPAR for non-reserved or non-preserved
          partitions

        - no duplicate indexes (ie. no duplicate GPT partition numbers)

        - none of the parent objects have an in_zpool or in_vdev attribute set
        """
        # set the parent_size based on the parent Disk object
        parent_size = self.container.disk_prop.dev_size.sectors
        label = self.container.label

        # verify part_type is not None
        if value.part_type is None:
            self.set_error(self.GPTPartitionTypeMissingError())

        # verify the name of the partition is valid
        # User partitions must be between s0 - s6 unless preserving existing
        # ones
        # Reserved partitions can and should be s8+
        if not value.is_reserved and \
            not 0 <= int(value.name) < EFI_NUMUSERPAR:
            if value.action != "preserve":
                self.set_error(self.InvalidGPTPartitionNameError(
                    str(value.name), self.container.ctd))
        if int(value.name) == EFI_NUMUSERPAR:
            if value.action != "preserve":
                self.set_error(self.InvalidGPTPartitionNameError(
                    str(value.name), self.container.ctd))

        # check the bounds of the GPT partition to be added.
        if not (isinstance(value.start_sector, int) or \
            isinstance(value.start_sector, long)):
            self.set_error(self.InvalidGPTPartitionStartSectorError())

        if hasattr(self.container.disk_prop, "dev_size") and \
           getattr(self.container.disk_prop, "dev_size") is not None:
            if not (0 <= value.start_sector <= \
               self.container.disk_prop.dev_size.sectors):
                self.set_error(self.InvalidGPTPartitionStartSectorError())

        # fix the start_sector and size to align against a lowest common
        # multiple disk block size. Helps to prevent partition mis-alignment.
        value = self.sector_boundary_adjustment(value)

        # verify that the Disk does not have 'whole_disk' set to 'true'
        if self.container.whole_disk:
            self.set_error(self.WholeDiskIsTrueError())

        new_start = value.start_sector
        new_end = value.start_sector + value.size.sectors - 1

        # verify each GPT partition does not overlap with any other
        for gpart in self._shadow:

            # calculate the range of each GPT partition already inserted
            start = gpart.start_sector
            end = gpart.start_sector + gpart.size.sectors - 1

            # check that the start sector is not within another GPT partition
            # and the existing GPT partition isn't inside the new GPT
            # partition but only for GPT partitions not marked for deletion
            if value.action != "delete" and gpart.action != "delete":
                if (start <= new_start <= end or start <= new_end <= end) or \
                   (new_start <= start <= new_end or \
                    new_start <= end <= new_end):
                    self.set_error(
                        self.OverlappingGPTPartitionError(value.name,
                                                          gpart.name))
        if len(self._shadow) >= EFI_MAXPAR:
            self.set_error(self.TooManyGPTPartitionsError())

        # check for duplicate gptpartition.name values
        if value.name in [gpart.name for gpart in self._shadow \
                          if gpart.action != "delete"]:
            self.set_error(self.DuplicateGPTPartitionNameError(value.name))

        # check for in_zpool overlap
        if value.in_zpool is not None:
            # check the container
            if getattr(self.container, "in_zpool") == value.in_zpool:
                self.set_error(self.OverlappingGPTPartitionZpoolError())

        # check for in_vdev overlap
        if value.in_vdev is not None:
            # check the container
            if getattr(self.container, "in_vdev") == value.in_vdev:
                self.set_error(self.OverlappingGPTPartitionVdevError())

        # check for in_use conflicts.
        stats = self.in_use_check(value)
        if stats and value.action != "preserve" and not value.force:
            self.set_error(self.GPTPartitionInUseError(stats))

        # insert the corrected GPTPartition object
        ShadowList.insert(self, index, value)

    def insert_partition(self, index, value):
        """ insert_partition() - override method for validation of
        Partition DOC objects.

        the following checks are done as part of validation:

        - Partition objects *must* have a part_type.

        - the parent Disk object does not have whole_disk attribute set

        - the start_sector of the slice is an int or long and is between 0 and
          the container's maximum size

        - if a partition is a logical partition, ensure there is an extended
          partition somewhere in indexes 1-4

        - no more than MAX_EXT_PARTS logical partitions

        - logical partitions fall within the boundaries of the extended
          partition

        - Only one active primary partition

        - primary partitions are not larger than the Disk

        - no overlapping boundaries of the partition with any other partitions
          already inserted

        - no duplicate indexes

        - the extended partition is at least 63 sectors in size and there is
          only one extended partition specified

        - none of the parent objects have an in_zpool or in_vdev attribute set
        """
        # verify part_type is not None
        if value.part_type is None:
            self.set_error(self.PartitionTypeMissingError())

        # verify the name of the partition is valid
        if not (1 <= int(value.name) <= (FD_NUMPART + MAX_EXT_PARTS)):
            self.set_error(self.InvalidPartitionNameError(
                str(value.name), self.container.ctd))

        # fix the start_sector and size to align to cylinder boundaries for
        # primary partitions
        if value.is_primary:
            value = self.cylinder_boundary_adjustment(value)

        # check the bounds of the partition to be added.
        if not (isinstance(value.start_sector, int) or \
           isinstance(value.start_sector, long)):
            self.set_error(self.InvalidPartitionStartSectorError())

        if hasattr(self.container.disk_prop, "dev_size") and \
           getattr(self.container.disk_prop, "dev_size") is not None:
            if not (0 <= value.start_sector <= \
               self.container.disk_prop.dev_size.sectors):
                self.set_error(self.InvalidPartitionStartSectorError())

        # verify that the Disk does not have 'whole_disk' set to 'true'
        if self.container.whole_disk:
            self.set_error(self.WholeDiskIsTrueError())

        # if the partition is a logical partition, ensure there is a partition
        # with part_type in Partition.EXTENDED_ID_LIST has already been
        # inserted.
        if value.is_logical:
            extended_part = None
            for partition in self._shadow:
                if partition.is_extended:
                    if partition.part_type in partition.EXTENDED_ID_LIST:
                        extended_part = partition

            if extended_part is None:
                self.set_error(self.NoExtPartitionsError())
            else:
                # verify there are not more than MAX_EXT_PARTS
                logical_list = [p for p in self._shadow if p.is_logical and \
                                p.action != "delete"]
                if len(logical_list) >= MAX_EXT_PARTS:
                    self.set_error(self.TooManyLogicalPartitionsError())

                # ensure this logical partition does not start too close to any
                # previously inserted logical partitions.

                # sort the logical list by start sector
                slist = sorted(logical_list,
                    lambda x, y: cmp(x.start_sector, y.start_sector))

                # find the closest logical partition within the extended
                # partition
                closest_endpoint = 0
                for logical in slist:
                    end_point = logical.start_sector + logical.size.sectors
                    if end_point < value.start_sector and \
                       end_point > closest_endpoint:
                        closest_endpoint = end_point

                if closest_endpoint == 0:
                    # no logical partitions were found, so use the start of the
                    # extended partition, if the difference is smaller than the
                    # needed offset
                    diff = value.start_sector - extended_part.start_sector
                    if diff < LOGICAL_ADJUSTMENT and value.action == "create":
                        value.start_sector = extended_part.start_sector + \
                                             LOGICAL_ADJUSTMENT
                        new_size = value.size.sectors - LOGICAL_ADJUSTMENT
                        value.size = Size(str(new_size) + Size.sector_units)
                else:
                    diff = value.start_sector - closest_endpoint
                    # make sure there's at least 63 sectors between logical
                    # partitions
                    if diff < LOGICAL_ADJUSTMENT and value.action == "create":
                        value.start_sector += LOGICAL_ADJUSTMENT - diff

                        new_size = value.size.sectors - LOGICAL_ADJUSTMENT
                        value.size = Size(str(new_size) + Size.sector_units)

        # check the bootid attibute on primary partitions for multiple active
        # partitions
        if value.is_primary and value.bootid == value.ACTIVE:
            for partition in self._shadow:
                # skip logical partitions
                if partition.is_logical:
                    continue

                # check the bootid attribute
                if partition.bootid == value.ACTIVE:
                    self.set_error(self.MultipleActivePartitionsError(
                        partition.name))

        p_start = value.start_sector
        p_end = p_start + value.size.sectors - 1

        # walk each inserted partition already in the shadow list to ensure the
        # partition we're trying to insert doesn't cross boundaries.
        for partition in self._shadow:
            # start and end points of the partition to check
            if partition.is_primary:
                start = partition.start_sector
                end = start + partition.size.sectors - 1
            else:
                # for logical partitions, there needs to be a buffer of
                # LOGICAL_ADJUSTMENT on each end
                start = partition.start_sector - LOGICAL_ADJUSTMENT
                end = start + partition.size.sectors - 1 + LOGICAL_ADJUSTMENT

            if value.is_primary:
                # do not test logical partition boundaries for primary
                # partitions
                if partition.is_logical:
                    continue
            else:
                # verify the logical partition we're trying to insert fits
                # within the extended partition "parent"
                if partition.is_extended and partition.action != "delete":
                    if p_start < start or p_end > end:
                        self.set_error(self.LogicalPartitionOverlapError())

                # do not test primary partition boundaries for logical
                # partitions
                if partition.is_primary:
                    continue

            # check that the start sector of the partition we're trying to
            # insert is not within another partition and the existing partition
            # isn't inside the partition we're inserting.  Primary partitions
            # are only checked against other primary partitions and logical
            # partitions are only checked aginst other logical partitions.
            # Partitions marked for deletion should not be checked at all
            if value.action != "delete" and partition.action != "delete":
                if ((start <= p_start <= end) or (start <= p_end <= end)) or \
                   ((p_start <= start <= p_end) or (p_start <= end <= p_end)):
                    self.set_error(self.OverlappingPartitionError(
                        partition.name, value.name))

        # check that a primary partition doesn't exceed the size of the Disk,
        # if the dev_size is specified
        if hasattr(self.container.disk_prop, "dev_size") and \
           self.container.disk_prop.dev_size is not None and \
           value.is_primary:
            disk_size = self.container.disk_prop.dev_size.sectors
            p_size = value.start_sector + value.size.sectors

        # check that the name of the partition is not already in the list
        if value.name in [p.name for p in self._shadow \
                          if p.action != "delete"]:
            self.set_error(self.DuplicatePartitionNameError(value.name))

        # if this is an extended partition, verify there are no other
        # partitions of the same type.  Also verify it's at least
        # LOGICAL_ADJUSTMENT sectors in size
        if value.is_extended:
            for partition in self._shadow:
                if partition.is_extended and partition.action != "delete":
                    self.set_error(self.TooManyExtPartitionsError())
            if value.size.sectors < LOGICAL_ADJUSTMENT:
                self.set_error(self.ExtPartitionTooSmallError())

        # if the partition type is FAT16, make sure it's not larger than 4GB
        fat16_list = [
            value.name_to_num("FAT16 (Upto 32M)"),
            value.name_to_num("FAT16 (>32M, HUGEDOS)"),
            value.name_to_num("WIN95 FAT16(LBA)")
        ]
        if value.part_type in fat16_list and value.action == "create":
            if value.size.byte_value > Size.units["gb"] * 4:
                self.set_error(self.FAT16PartitionTooLargeError())

        # check to see if the container object has the same in_zpool attribute
        if value.in_zpool is not None:
            if getattr(self.container, "in_zpool") == value.in_zpool:
                self.set_error(self.OverlappingPartitionZpoolError())

        # check to see if the container object has the same in_vdev attribute
        if value.in_vdev is not None:
            if getattr(self.container, "in_vdev") == value.in_vdev:
                self.set_error(self.OverlappingPartitionVdevError())

        # insert the partition
        ShadowList.insert(self, index, value)

    def insert(self, index, value):
        # check the container object's adjust_boundaries attribute.  If False,
        # simply insert the object into the shadow list
        if hasattr(self.container, "validate_children") and \
           not self.container.validate_children:
            ShadowList.insert(self, index, value)
        else:
            # reset the errsvc for Physical errors
            errsvc.clear_error_list_by_mod_id(self.mod_id)

            # Check the value to see what kind of DOC object we're trying to
            # insert. We can't import the classes from target.physical because
            # it results in a circular import, so look at class name instead.
            insert_map = {"GPTPartition": self.insert_gptpartition,
                          "Slice": self.insert_slice,
                          "Partition": self.insert_partition}
            insert_map[value.__class__.__name__](index, value)

    def remove(self, value):
        # reset the errsvc for Physical errors
        errsvc.clear_error_list_by_mod_id(self.mod_id)

        # Check slices or GPT partitions for in use conclicts
        if hasattr(value, "force"):
            # check for in_use conflicts.
            stats = self.in_use_check(value)
            if stats and not value.force:
                self.set_error(self.SliceInUseError(stats))

        # remove the object
        ShadowList.remove(self, value)

    def cylinder_boundary_adjustment(self, value):
        """ NOTE: MBR/VTOC SPECIFIC - do not use for GPT disk partitioning.

        cylinder_boundary_adjustment() - method to adjust a Partition or
        Slice object's start_sector and size value to fall on cylinder
        boundaries

        value - DOC object to adjust
        """
        # only make adjustments when the action is 'create'
        if value.action != "create":
            return value

        # determine the cylsize based on the container object
        if hasattr(self.container, "geometry"):
            # container is a Disk object
            cyl_boundary = self.container.geometry.cylsize
            disk_size = self.container.disk_prop.dev_size.sectors
            arch = self.container.kernel_arch
        elif hasattr(self.container, "part_type"):
            # container is a Partition object
            cyl_boundary = self.container.parent.geometry.cylsize
            disk_size = self.container.parent.disk_prop.dev_size.sectors
            arch = self.container.parent.kernel_arch

        # adjust the start_sector up to the next cylinder boundary
        if value.start_sector % cyl_boundary != 0:
            new_start_sector = ((value.start_sector / cyl_boundary) * \
                               cyl_boundary) + cyl_boundary

            # adjust the size down by the same amount
            difference = new_start_sector - value.start_sector
            value.start_sector = new_start_sector
            value.size = Size(str(value.size.sectors - difference) + \
                              Size.sector_units)

        # check the start_sector of the object.  If it starts at zero, adjust
        # it to start at the first cylinder boundary instead so as not to
        # clobber the disk label
        if value.start_sector == 0:
            value.start_sector = cyl_boundary
            value.size = Size(str(value.size.sectors - cyl_boundary) + \
                              Size.sector_units)

        # adjust the size down to the nearest end cylinder
        if value.size.sectors % cyl_boundary != 0:
            new_size = (value.size.sectors / cyl_boundary) * cyl_boundary
            value.size = Size(str(new_size) + Size.sector_units)

        # x86 specific check for slices and partitions
        if arch == "x86":
            if hasattr(value, "force"):
                # The largest possible size for any slice (other than slice 2),
                # is disk size - 4 cylinders.  1 cylinder for the MBR, 2
                # cylinders for the VTOC label, and 1 cylinder for slice 8
                max_cyl = 4
            elif hasattr(value, "part_type"):
                # The largest possible size for any partition is disk_size - 1
                # cylinder (for the MBR)
                max_cyl = 1

            # adjust the value's size if it's larger than the cylinder maximum
            if (disk_size - value.size.sectors) / cyl_boundary < max_cyl:
                end_cylinder = ((disk_size / cyl_boundary) - max_cyl) * \
                               cyl_boundary
                value.size = Size(str(end_cylinder) + Size.sector_units)

        return value

    def sector_boundary_adjustment(self, value):
        """ NOTE: GPT SPECIFIC - do not use for MBR/VTOC disk partitioning.

        sector_boundary_adjustment() - method to adjust a GPTPartition
        objects start_sector and size value to align with 128KB physical
        block boundaries and avoid overlapping with either the primary
        or secondary EFI labels at the beginning or end of the disk.

        Some larger disks, iSCSI, zvols etc. implement larger physical block
        sizes, up to 128KB for Sun Storage Array Luns.
        Some of these can emulate a 512 byte block size for compatibility.

        If not aligned properly, the file system would appear to be logically
        aligned but physically end up misaligned across physical sectors, which
        causes performance problems. This method rounds GPT partitions on disks
        reporting < 128KB block size to multiples of 128KB.

        value - DOC object to adjust
        """
        # only make adjustments when the action is 'create'
        if value.action != "create":
            return value

        # determine the reported blocksize of the Disk container object
        # and its size in blocks/sectors.
        block_size = self.container.geometry.blocksize
        disk_size = self.container.disk_prop.dev_size.sectors

        # Check to make sure we get a clean block size multiple
        if EFI_BLOCKSIZE_LCM % block_size != 0:
            # Unexpected block size (ie. not a multiple of 512,
            # or > EFI_BLOCKSIZE_LCM)
            # Don't try to do anything fancy.
            block_multiplier = 1
        else:
            block_multiplier = EFI_BLOCKSIZE_LCM / block_size

        # check the start_sector of the object.
        # The start sector may need to be further rounded up to align with
        # our lowest common multiple disk block size value.
        min_start_sector = self.container.gpt_primary_table_size.sectors
        if value.start_sector < min_start_sector:
            difference = min_start_sector - value.start_sector
            value.start_sector = min_start_sector
            value.size = Size(str(value.size.sectors - difference) + \
                              Size.sector_units,
                              blocksize=block_size)

        # Round the start_sector up to the next block_multiplier boundary
        # This provides ample space for the EFI disk label and EFI partition
        # entries and facilitates proper partition alignment
        if value.start_sector % block_multiplier != 0:
            new_start_sector = ((value.start_sector / block_multiplier) * \
                               block_multiplier) + block_multiplier
            difference = new_start_sector - value.start_sector
            value.start_sector = new_start_sector
            value.size = Size(str(value.size.sectors - difference) + \
                              Size.sector_units,
                              blocksize=block_size)

        # Check to make sure the GPT partition doesn't extend into or beyond
        # where the secondary/backup GPT header is stored:
        end_sector = value.start_sector + value.size.sectors - 1
        bkup_start = disk_size - self.container.gpt_backup_table_size.sectors
        if bkup_start <= end_sector:
            # adjust the size down so it doesn't corrupt the backup EFI label
            value.size = Size(str(bkup_start - value.start_sector - 1) + \
                              Size.sector_units,
                              blocksize=block_size)

        # adjust the size down to the nearest whole multiple of
        # block_multiplier to make partition end on a physical block boundary
        if value.size.sectors % block_multiplier != 0:
            value.size = Size(str((value.size.sectors / block_multiplier) * \
                              block_multiplier) + Size.sector_units,
                              blocksize=block_size)

        return value

    def __init__(self, container, *args):
        ShadowList.__init__(self, *args)

        self.mod_id = "physical validation"
        self.container = container

        for entry in args:
            self.append(entry)  # will call self.insert

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
import osol_install.errsvc as errsvc

from solaris_install.target.libadm.const import FD_NUMPART, MAX_EXT_PARTS, \
    V_BACKUP, V_BOOT, V_NUMPAR
from solaris_install.target.libdiskmgt import const as ldm_const
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.shadow import ShadowList, ShadowExceptionBase
from solaris_install.target.size import Size

LOGICAL_ADJUSTMENT = 63


class ShadowPhysical(ShadowList):
    """ ShadowPhysical - class to hold and validate Physical objects (Partition
    and Slice)
    """
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

    class OverlappingPartitionError(ShadowExceptionBase):
        def __init__(self, partition_name, existing_partition):
            self.value = "Partition %s overlaps with " % partition_name + \
                         "existing partition: %s" % existing_partition

    class OverlappingPartitionZpoolError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition in_zpool attribute overlaps with parent"

    class OverlappingPartitionVdevError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition in_vdev attribute overlaps with parent"

    class LogicalPartitionOverlapError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Logical partition exceeds the start or end " + \
                         "sector of the extended partition"

    class DuplicatePartitionNameError(ShadowExceptionBase):
        def __init__(self, partition_name):
            self.value = "Partition name %s already inserted" % partition_name

    class TooManyLogicalPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Only %d logical partitions may be inserted" % \
                         MAX_EXT_PARTS

    class MultipleActivePartitionsError(ShadowExceptionBase):
        def __init__(self, partition_name):
            self.value = "Partition %s already marked as active" % \
                         partition_name

    class InvalidTypeError(ShadowExceptionBase):
        def __init__(self, valid_type):
            self.value = "Invalid partition type for operation.  Requires " + \
                         "type:  %s" % valid_type

    class NoExtPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "A logical partition exists without an extended " + \
                         "partition"

    class TooManyExtPartitionsError(ShadowExceptionBase):
        def __init__(self):
            self.value = "There is already an extended partition set for " + \
                         "this Disk"

    class ExtPartitionTooSmallError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Extended Partition is too small.  It must be 63 " + \
                         "sectors or larger."

    class FAT16PartitionTooLargeError(ShadowExceptionBase):
        def __init__(self):
            self.value = "FAT16 Partition is too large.  It must not " + \
                         "exceed 4GB"

    class WholeDiskIsTrueError(ShadowExceptionBase):
        def __init__(self):
            self.value = "whole_disk attribute for this Disk is set to " + \
                         "'true'. Partitions or slices cannot be " + \
                         "specified for this Disk"

    class InvalidSliceStartSectorError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Invalid entry for slice's start_sector"

    class InvalidPartitionStartSectorError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Invalid entry for partition's start_sector"

    class SliceInUseError(ShadowExceptionBase):
        def __init__(self, in_use):
            s = in_use["used_by"][0]
            if "used_name" in in_use:
                s += ": %s" % in_use["used_name"][0]
            self.value = "Slice currently in use by %s" % s

    class PartitionTypeMissingError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Partition has invalid partition type"

    def in_use_check(self, ctds):
        """ in_use_check() - method to query libdiskmgt to check for in_use
        confilcts.
        """
        try:
            dmd = diskmgt.descriptor_from_key(ldm_const.SLICE,
                                              "/dev/dsk/" + ctds)
        except KeyError:
            # the requested slice doesn't exist so simply skip the check
            return dict()
        else:
            dm_slice = diskmgt.DMSlice(dmd.value)
            return dm_slice.use_stats

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
        # set the proper cylinder boundry, parent_size and ctds string based on
        # the container type
        if hasattr(self.container, "geometry"):
            # container is a Disk object
            parent_size = self.container.disk_prop.dev_size.sectors
            ctds = self.container.ctd + "s%s" % value.name
            label = self.container.label

            # verify that the Disk does not have 'whole_disk' set to 'true'
            if self.container.whole_disk:
                self.set_error(self.WholeDiskIsTrueError())

        elif hasattr(self.container, "part_type"):
            # container is a Partition object
            parent_size = self.container.size.sectors
            ctds = self.container.parent.ctd + "s%s" % value.name
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
        if value.name in [slc.name for slc in self._shadow]:
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

        # check for in_use conflicts.  Re-query libdiskmgt due to circular
        # import issues with trying to navigate the DOC
        stats = self.in_use_check(ctds)
        if stats and value.action != "preserve" and not value.force:
            self.set_error(self.SliceInUseError(stats))

        # insert the corrected Slice object
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
                if partition.is_extended:
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
        if value.name in [p.name for p in self._shadow]:
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

            # check the value to see what kind of DOC object we're trying to
            # insert.
            if hasattr(value, "force"):
                # this is a Slice object, so call insert_slice
                self.insert_slice(index, value)
            elif hasattr(value, "part_type"):
                # this is a Partition object, so call insert_partition
                self.insert_partition(index, value)

    def remove(self, value):
        # reset the errsvc for Physical errors
        errsvc.clear_error_list_by_mod_id(self.mod_id)

        # look for slices only
        if hasattr(value, "force"):
            # set the ctds of the slice
            if hasattr(self.container, "geometry"):
                # container is a Disk object
                ctds = self.container.ctd + "s%s" % value.name
            elif hasattr(self.container, "part_type"):
                # container is a Partition object
                ctds = self.container.parent.ctd + "s%s" % value.name

            # check for in_use conflicts.  Re-query libdiskmgt due to circular
            # import issues with trying to navigate the DOC
            stats = self.in_use_check(ctds)
            if stats and not value.force:
                self.set_error(self.SliceInUseError(stats))

        # remove the object
        ShadowList.remove(self, value)

    def cylinder_boundary_adjustment(self, value):
        """ cylinder_boundary_adjustment() - method to adjust a Partition or
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

        # round the start sector up/down if it doesn't already start on
        # cylinder boundary
        if value.start_sector % cyl_boundary != 0:
            value.start_sector = ((value.start_sector + (cyl_boundary / 2)) / \
                                 cyl_boundary) * cyl_boundary

        # check the start_sector of the object.  If it starts at zero, adjust
        # it to start at the first cylinder boundary instead so as not to
        # clobber the disk label
        if value.start_sector == 0:
            value.start_sector = cyl_boundary

        # adjust the size down to the nearest end cylinder
        if value.size.sectors % cyl_boundary != 0:
            end_cylinder = (value.size.sectors / cyl_boundary) * cyl_boundary
            value.size = Size(str(end_cylinder) + Size.sector_units)

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

    def __init__(self, container, *args):
        ShadowList.__init__(self, *args)

        self.mod_id = "physical validation"
        self.container = container

        for entry in args:
            self.append(entry)  # will call self.insert

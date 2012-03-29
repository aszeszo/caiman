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

""" physical.py -- library containing class definitions for physical DOC
objects, including Partition, Slice and Disk.
"""
import copy
import gettext
import locale
import os
import platform
import tempfile

from multiprocessing import Manager
from uuid import UUID

from lxml import etree

from bootmgmt.bootinfo import SystemFirmware
from solaris_install import CalledProcessError, Popen, run
from solaris_install.data_object import DataObject, ParsingError
from solaris_install.target.cuuid import cUUID, UUID2cUUID
from solaris_install.target.libadm import const, cstruct, extvtoc
from solaris_install.target.libdiskmgt import const as ldm_const
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.libefi import const as efi_const
from solaris_install.target.libefi import efi
from solaris_install.target.libefi.cstruct import EFI_MAXPAR
from solaris_install.target.shadow.physical import LOGICAL_ADJUSTMENT, \
    ShadowPhysical, EFI_BLOCKSIZE_LCM
from solaris_install.target.size import Size

FDISK = "/usr/sbin/fdisk"
FORMAT = "/usr/sbin/format"
FSTYP = "/usr/sbin/fstyp"
PCFSMKFS = "/usr/lib/fs/pcfs/mkfs"
SWAP = "/usr/sbin/swap"
UMOUNT = "/usr/sbin/umount"

MNTTAB = "/etc/mnttab"

FIRST_CYL = 0
BOOT_SLICE_RES_CYL = 1
BACKUP_SLICE = 2
BOOT_SLICE = 8
ALT_SLICE = 9


def partition_sort(a, b):
    return cmp(int(a.name), int(b.name))


def fill_right(obj, desired_size, right_gap):
    """ fill_right() - function to calculate how much space in the next gap is
    needed to fulfil a change in size of an object (Slice or Partition)

    obj - Slice or Partition object
    desired_size - how much more space the object needs to grow by
    right_gap - the gap immediately adjacent to the object to grow
    """

    if obj.start_sector + obj.size.sectors + desired_size <= \
       right_gap.start_sector + right_gap.size.sectors:
        return 0
    else:
        # consume the gap and return what's left
        return desired_size - right_gap.size.sectors


def fill_left(obj, desired_size, left_gap):
    """ fill_left() - function to calculate how much space in the previous gap
    is needed to fulfil a change in size of an object (Slice or Partition)

    obj - Slice or Partition object
    desired_size - how much more space the object needs to grow by
    left_gap - the gap immediately preceeding the object to grow
    """

    if obj.start_sector - desired_size >= left_gap.start_sector:
        return 0
    else:
        return desired_size - left_gap.size.sectors


class DiskNotEmpty(Exception):
    """ User-defined Exception raised when attempting to relabel a disk that
    has children (GPTPartition, Partitions, or Slices)
    """


class DuplicatePartition(Exception):
    """ User-defined Exception raised when attempting to add an MBR EFI_SYSTEM
    partition when it already exists.

    """
    def __init__(self, duplicate, msg=None):
        super(DuplicatePartition, self).__init__(msg)
        self._dup = duplicate

    @property
    def duplicate(self):
        return self._dup


class DuplicateGPTPartition(Exception):
    """ User-defined Exception raised when attempting to add an EFI_RESERVED
    when it already exists or when adding either of EFI_BIOS_BOOT or
    EFI_SYSTEM when one of those already exist.
    """
    def __init__(self, duplicate, msg=None):
        super(DuplicateGPTPartition, self).__init__(msg)
        self._dup = duplicate

    @property
    def duplicate(self):
        return self._dup


class InsufficientSpaceError(Exception):
    """ User-defined Exception raised when attempting to change the size of a
    Slice or Partition object
    """

    def __init__(self, available_size, msg=None):
        super(InsufficientSpaceError, self).__init__(msg)
        self.available_size = available_size


class NoPartitionSlotsFree(Exception):
    """ User-defined Exception raised when attempting to add an EFI_SYSTEM
    partition when no slots are left available for
    the partition.
    """


class NoGPTPartitionSlotsFree(Exception):
    """ User-defined Exception raised when attempting to add an EFI_SYSTEM
    or EFI_BIOS_BOOT partition when no slots are left available for
    the partition.
    """


class GPTPartition(DataObject):
    def __init__(self, name):
        super(GPTPartition, self).__init__(name)
        # set the default partition type to Solaris
        self.action = "create"
        self.force = False

        self.size = Size("0b")
        self.start_sector = 0

        self._guid = efi_const.EFI_USR  # cUUID of partition type GUID
        self.uguid = None  # cUUID of unique partition GUID
        self.flag = 0

        # in_use value from libdiskmgt
        self.in_use = None

        # zpool and vdev references
        self.in_zpool = None
        self.in_vdev = None

        # True if the partition contains a PCFS/FAT filesystem
        self._is_pcfs_formatted = None

    def to_xml(self):
        gpart = etree.Element("gpt_partition")
        gpart.set("name", str(self.name))
        gpart.set("action", self.action)
        gpart.set("force", str(self.force).lower())

        # For legibility try and set part_type to an alias.
        for (alias, guid) in efi_const.PARTITION_GUID_ALIASES.iteritems():
            if guid == self.guid:
                part_type = alias
                break
        else:
            part_type = "{%s}" % (self.guid)
        gpart.set("part_type", part_type)

        if self.in_zpool is not None:
            gpart.set("in_zpool", self.in_zpool)
        if self.in_vdev is not None:
            gpart.set("in_vdev", self.in_vdev)

        size = etree.SubElement(gpart, "size")
        size.set("val", str(self.size.sectors) + Size.sector_units)
        size.set("start_sector", str(self.start_sector))

        return gpart

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'gpt_partition'
        - a 'name' attribute

        otherwise return False
        """
        if element.tag != "gpt_partition":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        part_type = element.get("part_type")
        action = element.get("action")
        force = element.get("force")
        in_zpool = element.get("in_zpool")
        in_vdev = element.get("in_vdev")

        gpart = GPTPartition(name)

        if force is not None:
            try:
                gpart.force = {"true": True, "false": False}[force.lower()]
            except KeyError:
                raise ParsingError("GPTPartition elements force attribute " +
                                   "must be either 'true' or 'false'")

        size = element.find("size")
        if size is not None:
            gpart.size = Size(size.get("val"))
            start_sector = size.get("start_sector")
            if start_sector is not None:
                # ensure we can cast a supplied value to an integer
                try:
                    start_sector = int(start_sector)
                except:
                    # catch any failure
                    raise ParsingError("GPTPartition size element has "
                                       "invalid 'start_sector' attribute")
            gpart.start_sector = start_sector

        gpart.action = action

        if part_type is None:
            raise ParsingError("Missing GPT Partition type")

        # Partition type can be specified as one of:
        # - A supported alias (eg. "esp")
        # - A supported long name (eg. "EFI System Partition")
        # - A supported GUID (eg. '{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}')
        try:
            gpart.guid = part_type
        except (ValueError, TypeError):
            raise ParsingError("'%s' is not a supported GPT partition " \
                               "type" % part_type)

        if in_zpool is not None:
            gpart.in_zpool = in_zpool
        if in_vdev is not None:
            gpart.in_vdev = in_vdev

        return gpart

    @classmethod
    def alias_to_guid(cls, alias_name):
        """ alias_to_guid - given a GPT partition alias, lookup
            the corresponding partition GUID.
        """
        return efi_const.PARTITION_GUID_ALIASES.get(alias_name)

    @classmethod
    def guid_to_name(cls, gpart_guid):
        """ guid_to_name - given a GPT partition GUID, lookup
            the corresponding partition name
        """
        data = efi_const.PARTITION_GUID_PTAG_MAP.get(gpart_guid)
        if data is not None:
            return data[0]

    @classmethod
    def guid_to_ptag(cls, gpart_guid):
        """ guid_to_ptag - given a GPT partition GUID, lookup
            the corresponding partition P_TAG
        """
        data = efi_const.PARTITION_GUID_PTAG_MAP.get(gpart_guid)
        if data is not None:
            return data[1]

    @classmethod
    def name_to_guid(cls, gpart_name):
        """ name_to_guid - given a GPT partition name, lookup
            the corresponding partition GUID
        """
        for (p_guid, (p_name, p_tag)) in \
            efi_const.PARTITION_GUID_PTAG_MAP.iteritems():
            if p_name.upper() == gpart_name.upper():
                return p_guid
        return None

    @classmethod
    def name_to_ptag(cls, gpart_name):
        """ name_to_ptag - given a GPT partition name, lookup
            the corresponding partition P_TAG
        """
        for (p_guid, (p_name, p_tag)) in \
            efi_const.PARTITION_GUID_PTAG_MAP.iteritems():
            if p_name.upper() == gpart_name.upper():
                return p_tag
        return None

    def format_pcfs(self):
        """ format_pcfs() - method to format a GPT partition with a FAT/pcfs
        filesystem. This should be used when creating a new EFI system
        partition on the disk
        """
        rdsk_dev = "/dev/rdsk/%ss%s" % (self.parent.ctd, self.name)
        cmd = [PCFSMKFS, rdsk_dev]
        run(cmd, stdin=open("/dev/zero", "r"))

    def resize(self, size, size_units=Size.gb_units, start_sector=None):
        """ resize() - method to resize a GPTPartition object.

        start_sector is optional.  If not provided, use the existing
        start_sector.
        """
        if start_sector is None:
            start_sector = self.start_sector

        # delete the existing GPTPartition from the parent's shadow list
        self.delete()

        # re-insert it with the new size
        resized_gpart = self.parent.add_gptpartition(self.name,
            start_sector, size, size_units=size_units,
            partition_type=self.guid, in_zpool=self.in_zpool,
            in_vdev=self.in_vdev)

        return resized_gpart

    def change_type(self, new_type):
        """ change_type() - method to change the partition type of a
        GPTPartition object
        """
        # delete the existing GPT partition from the parent's shadow list
        self.delete()

        # Insert the new one, preserving existing size parameters
        new_gptpartition = self.parent.add_gptpartition(self.name,
            self.start_sector, self.size.sectors, size_units=Size.sector_units,
            partition_type=new_type, in_zpool=self.in_zpool,
            in_vdev=self.in_vdev)

        return new_gptpartition

    @property
    def guid(self):
        """ guid returns the cUUID object that represents the identifier for
            this partition.
        """
        return self._guid

    @guid.setter
    def guid(self, val):
        """ attempt to set the guid for this GPT partition being as flexible
            as possible.
        """
        if val is None:
            raise ValueError("'None' is an invalid GUID value")

        # always store it as cUUID so its ready for libefi
        if isinstance(val, cUUID):
            guid = val

        elif isinstance(val, UUID):
            guid = UUID2cUUID(val)

        elif isinstance(val, int):
            # they gave us a ptag
            for (p_guid, (p_name, p_tag)) in \
                efi_const.PARTITION_GUID_PTAG_MAP.iteritems():
                if p_tag == val:
                    guid = p_guid
                    break
            else:
                raise ValueError("%d not a known tag" % (val))

        elif isinstance(val, basestring):
            guid = GPTPartition.alias_to_guid(val)
            if guid is None:
                guid = GPTPartition.name_to_guid(val)
            if guid is None:
                guid = cUUID(val)  # will raise ValueError if it can't convert
        else:
            raise TypeError("unable to convert '%s' object to cUUID" %
                (type(val)))

        self._guid = guid

    @property
    def part_type(self):
        """ Friendly string or None"""
        name, p_tag = efi_const.PARTITION_GUID_PTAG_MAP.get(self.guid,
                                                            (None, None))
        return name

    @part_type.setter
    def part_type(self, val):
        """ they really just meant to set guid (which accepts just about
        anything)
        """
        self.guid = val

    @property
    def tag(self):
        """ integer tag for libefi corresponding to self.guid or None"""
        name, p_tag = efi_const.PARTITION_GUID_PTAG_MAP.get(self.guid,
                                                            (None, None))
        return p_tag

    @tag.setter
    def tag(self, val):
        """ they really just meant to set guid (which accepts just about
        anything)
        """
        self.guid = val

    @property
    def is_bios_boot(self):
        """ is_bios_boot() - instance property to return a Boolean value of
        True if the GPT partition GUID is a BIOS boot partition
        """
        return self.guid == efi_const.EFI_BIOS_BOOT

    @property
    def is_efi_system(self):
        """ is_efi_system() - instance property to return a Boolean value of
        True if the GPT partition GUID is an EFI system partition
        """
        return self.guid == efi_const.EFI_SYSTEM

    @property
    def is_pcfs_formatted(self):
        """ is_pcfs_formatted() instance property
        Returns:
        - True if the GPT partition guid is formatted with a pcfs filesystem.
        - False if the GPT partition is not formatted with a pcfs filesystem.
        - None if unknown
        This test is useful in conjuction with the is_efi_system property to
        determine if an existing EFI system partition  can be reused to store
        the Solaris UEFI boot program. If False, a format using mkfs on the
        partition would be required.
        """
        return self._is_pcfs_formatted

    @property
    def is_solaris(self):
        """ is_solaris() - instance property to return a Boolean value of True
        if the GPT partition GUID is a Solaris partition
        """
        return self.guid == efi_const.EFI_USR

    @property
    def is_reserved(self):
        """ is_reserved() - instance property to return a Boolean value of True
        if the GPT partition GUID is a Solaris Reserved partition
        """
        return self.guid == efi_const.EFI_RESERVED

    @property
    def is_unused(self):
        """ is_reserved() - instance property to return a Boolean value of True
        if the GPT partition GUID is a Solaris Reserved partition
        """
        return self.guid == efi_const.EFI_UNUSED

    def get_gap_before(self):
        """ Returns the HoleyObject gap that occurs immediately before this
        GPTPartition, or None if there is no such gap.
        """
        if self.parent is not None:
            gaps = self.parent.get_gaps()
            # An 'adjacent' before gap is one that ends exactly one block
            # before the start block of this partition
            for gap in gaps:
                if gap.start_sector + gap.size.sectors - \
                    self.start_sector == 0:
                    return gap

        return None

    def get_gap_after(self):
        """ Returns the HoleyObject gap that occurs immediately after this
        GPTPartition, or None if there is no such gap
        """
        if self.parent is not None:
            gaps = self.parent.get_gaps()
            # An 'adjacent' after gap is one that starts exactly one block
            # after the end block of this partition
            for gap in gaps:
                if self.start_sector + \
                    self.size.sectors - gap.start_sector == 0:
                    return gap

        return None

    def __repr__(self):
        p = "GPTPartition: name=%s; action=%s, force=%s" \
            % (self.name, self.action, self.force)
        if self.part_type is not None:
            p += "; part_type=%s" % self.part_type
        if self.tag is not None:
            p += ", tag=%d" % self.tag
        if self.flag is not None:
            p += ", flag=%d" % self.flag
        if self.in_use is not None:
            p += ", in_use=%s" % self.in_use
        if self.in_zpool is not None:
            p += "; in_zpool=%s" % self.in_zpool
        if self.in_vdev is not None:
            p += "; in_vdev=%s" % self.in_vdev

        p += "; size=%s; start_sector=%s" % \
            (str(self.size), str(self.start_sector))

        return p


class Partition(DataObject):
    """ class definition for Partition objects
    """

    ACTIVE = 0x80
    INACTIVE = 0

    # store a list of partition IDs allowed for a partition to be considered an
    # extended partition.
    EXTENDED_ID_LIST = [5, 12, 15]

    def __init__(self, name, validate_children=True):
        super(Partition, self).__init__(name)
        self.action = "create"
        self.validate_children = validate_children

        # set the default partition type to Solaris2
        self.part_type = self.name_to_num("Solaris2")
        self.bootid = Partition.INACTIVE
        self.is_linux_swap = False

        self.size = Size("0b")
        self.start_sector = 0

        # zpool and vdev references
        self.in_zpool = None
        self.in_vdev = None

        # True if the partition contains a PCFS/FAT filesystem
        self._is_pcfs_formatted = None

        # turn self._children into a shadow list
        self._children = ShadowPhysical(self)

    def to_xml(self):
        partition = etree.Element("partition")
        partition.set("action", self.action)
        if self.name is not None:
            partition.set("name", str(self.name))
        if self.part_type is not None:
            partition.set("part_type", str(self.part_type))
        if self.in_zpool is not None:
            partition.set("in_zpool", self.in_zpool)
        if self.in_vdev is not None:
            partition.set("in_vdev", self.in_vdev)

        size = etree.SubElement(partition, "size")
        size.set("val", str(self.size.sectors) + Size.sector_units)
        size.set("start_sector", str(self.start_sector))

        return partition

    @classmethod
    def can_handle(cls, element):
        if element.tag == "partition":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        part_type = element.get("part_type")
        action = element.get("action")
        in_zpool = element.get("in_zpool")
        in_vdev = element.get("in_vdev")

        # If the user specifies a name of "", turn it into a None
        if name is not None and len(name) == 0:
            name = None

        if name is None and action != "use_existing_solaris2":
            # Partition name must be provided in all cases other than
            # use_existing_solaris2
            raise ParsingError("Partition name must be provided if action "
                               "is not 'use_existing_solaris2'")

        partition = Partition(name, validate_children=False)

        size = element.find("size")
        if size is not None:
            partition.size = Size(size.get("val"))
            start_sector = size.get("start_sector")
            if start_sector is not None:
                # ensure we can cast a supplied value to an integer
                try:
                    start_sector = int(start_sector)
                except:
                    # catch any failure
                    raise ParsingError("Partition size element has invalid "
                                       "'start_sector' attribute")
            partition.start_sector = start_sector

        partition.action = action
        if part_type is not None:
            partition.part_type = int(part_type)
        if in_zpool is not None:
            partition.in_zpool = in_zpool
        if in_vdev is not None:
            partition.in_vdev = in_vdev
        return partition

    def add_slice(self, index, start_sector, size, size_units=Size.gb_units,
                  in_zpool=None, in_vdev=None, force=False):
        """ add_slice() - method to create a Slice object and add it as a child
        of the Partition object
        """
        # create a new Slice object
        new_slice = Slice(index)

        new_slice.size = Size(str(size) + str(size_units))
        new_slice.start_sector = start_sector
        new_slice.in_zpool = in_zpool
        new_slice.in_vdev = in_vdev
        new_slice.force = force

        # add the new Slice object as a child
        self.insert_children(new_slice)

        return new_slice

    def delete_slice(self, slc):
        """ delete_slice() - method to delete a specific Slice object
        """
        self.delete_children(name=slc.name, class_type=Slice)

    def format_pcfs(self):
        """ format_pcfs() - method to format a partition with a FAT/pcfs
        filesystem. This should be used when creating a new EFI system
        partition on the disk
        """
        rdsk_dev = "/dev/rdsk/%sp%s" % (self.parent.ctd, self.name)
        cmd = [PCFSMKFS, rdsk_dev]
        run(cmd, stdin=open("/dev/zero", "r"))

    def resize_slice(self, slc, size, size_units=Size.gb_units):
        """ resize_slice() - method to resize a Slice child.
        """

        # create a new_size object
        new_size = Size(str(size) + str(size_units))

        # check to see if the resized Slice is simply decreasing in size
        if new_size <= slc.size:
            # simply call Slice.resize
            return slc.resize(size, size_units)

        # find the previous and next gap
        previous_gap = None
        next_gap = None
        available_size = copy.copy(slc.size)
        end_sector = slc.start_sector + slc.size.sectors
        for gap in self.get_gaps():
            if abs(gap.start_sector + gap.size.sectors - slc.start_sector) <= \
               self.parent.geometry.cylsize:
                previous_gap = gap
                available_size += previous_gap.size
            if abs(slc.start_sector + slc.size.sectors - gap.start_sector) <= \
               self.parent.geometry.cylsize:
                next_gap = gap
                available_size += next_gap.size
                end_sector = next_gap.start_sector + next_gap.size.sectors

        # try to fill in both sides of the Slice
        remaining_space = new_size.sectors - slc.size.sectors

        if next_gap is not None:
            # try to consume space from the right first
            remaining_space = fill_right(slc, remaining_space, next_gap)
            if not remaining_space:
                # the size of the Slice is increasing but not impacting the
                # next object so call resize
                return slc.resize(size, size_units)

        # consume additional space from the left, if needed
        if remaining_space and previous_gap is not None:
            # continue to consume from the left
            remaining_space = fill_left(slc, remaining_space, previous_gap)

        if remaining_space:
            # there's no room to increase this Slice
            raise InsufficientSpaceError(available_size)

        new_start_sector = end_sector - new_size.sectors
        return slc.resize(size, size_units, start_sector=new_start_sector)

    def resize(self, size, size_units=Size.gb_units, start_sector=None):
        """ resize() - method to resize a Partition object.

        start_sector is optional.  If not provided, use the existing
        start_sector.

        NOTE: the resulting new size is not checked to ensure the resized
        Partition 'fits' within the current available space.  To ensure proper
        'fit', use Disk.resize_partition()
        """
        if start_sector is None:
            start_sector = self.start_sector

        # delete the existing partition from the parent's shadow list
        self.delete()

        # re-insert it with the new size
        resized_partition = self.parent.add_partition(self.name, start_sector,
            size, size_units=size_units, partition_type=self.part_type,
            bootid=self.bootid, in_zpool=self.in_zpool, in_vdev=self.in_vdev)

        return resized_partition

    def change_type(self, new_type):
        """ change_type() - method to change the partition type of a Partition
        object
        """
        # delete the existing partition from the parent's shadow list
        self.delete()

        # the size of the partition is already in sectors, so use that as the
        # units.
        new_partition = self.parent.add_partition(self.name, self.start_sector,
            self.size.sectors, size_units=Size.sector_units,
            partition_type=new_type, bootid=self.bootid,
            in_zpool=self.in_zpool, in_vdev=self.in_vdev)

        return new_partition

    def change_bootid(self, new_bootid):
        """ change_bootid() - method to change the partition's bootid
        """
        # verify the new_bootid is valid
        if new_bootid not in [Partition.ACTIVE, Partition.INACTIVE]:
            raise RuntimeError("Partition.bootid must be Partition.ACTIVE " \
                               "or Partition.INACTIVE")

        # delete the existing partition from the parent's shadow list
        self.delete()

        # the size of the partition is already in sectors, so use that as the
        # units.
        new_partition = self.parent.add_partition(self.name, self.start_sector,
            self.size.sectors, size_units=Size.sector_units,
            partition_type=self.part_type, bootid=new_bootid,
            in_zpool=self.in_zpool, in_vdev=self.in_vdev)

        return new_partition

    def get_gaps(self):
        """ get_gaps() - method to return a list of Holey Objects
        available on this Partition
        """
        if not self._children:
            # return a list of the size of the partition
            return[HoleyObject(0, self.size)]

        # create a list of sector usage by this partition.
        usage = list()
        for child in self._children:
            # skip slices marked for deletion
            if child.action == "delete":
                continue
            # skip the child if it has a tag of V_BACKUP (5)
            if getattr(child, "tag") == const.V_BACKUP:
                continue
            usage.append(child.start_sector)
            usage.append(child.start_sector + child.size.sectors)

        # sort the usage list and add bookends
        usage.sort()
        usage.insert(0, 0L)
        usage.append(self.size.sectors)

        holes = list()
        i = 0
        while i < len(usage) - 1:
            # subtract i+1 to get the size of this hole.
            size = usage[i + 1] - usage[i]

            # if the size is 0 (for a starting sector of 0) or 1 (for adjacent
            # children), there's no gap, so skip it
            if size not in [0, 1] and size > self.parent.geometry.cylsize:
                # do not correct for holes that start at 0
                if usage[i] == 0:
                    holes.append(HoleyObject(
                        usage[i], Size(str(size - 1) + Size.sector_units)))
                else:
                    holes.append(HoleyObject(
                        usage[i] + 1, Size(str(size - 1) + Size.sector_units)))

            # step across the size of the child
            i += 2

        return holes

    def get_gap_before(self):
        """ Returns the HoleyObject gap that occurs immediately before this
        partition, or None if there no such gap.

        If the partition is logical, only logical gaps (gaps within an
        EXTENDED partition) are considered; otherwise, only Disk gaps (gaps
        between primary partitions are considered.
        """

        if self.parent is not None:
            if self.is_logical:
                gaps = self.parent.get_logical_partition_gaps()
                # An 'adjacent' logical gap is one that is within
                # the "logical adjustment" + 1 sectors of this partition
                adjacent_size = LOGICAL_ADJUSTMENT + 1
            else:
                gaps = self.parent.get_gaps()
                # An 'adjacent' primary gap is one that is within
                # one cylinder of this partition
                adjacent_size = self.parent.geometry.cylsize

            for gap in gaps:
                if abs(gap.start_sector + gap.size.sectors - \
                       self.start_sector) <= adjacent_size:
                    return gap

        return None

    def get_gap_after(self):
        """ Returns the HoleyObject gap that occurs immediately after this
        partition, or None if there is no such gap.

        If the partition is logical, only logical gaps (gaps within an
        EXTENDED partition) are considered; otherwise, only Disk gaps (gaps
        between primary partitions) are considered.
        """

        if self.parent is not None:
            if self.is_logical:
                gaps = self.parent.get_logical_partition_gaps()
                # An 'adjacent' logical gap is one that is within
                # the "logical adjustment" + 1 sectors of this partition
                adjacent_size = LOGICAL_ADJUSTMENT + 1
            else:
                gaps = self.parent.get_gaps()
                # An 'adjacent' primary gap is one that is within
                # one cylinder of this partition
                adjacent_size = self.parent.geometry.cylsize

            for gap in gaps:
                if abs(self.start_sector + \
                    self.size.sectors - gap.start_sector) <= \
                    adjacent_size:
                    return gap

        return None

    def create_entire_partition_slice(self, name="0", in_zpool=None,
                                      in_vdev=None, tag=None, force=False):
        """ create_entire_partition_slice - method to clear out all existing
        slices and create a single slice equal to the size of the partition.

        name, in_zpool, in_vdev, tag - optional arguments to pass directly to
        add_slice() or apply to the created Slice object
        """

        # delete all existing children
        self.delete_children(class_type=Slice)
        gaps = self.get_gaps()

        # set the args and kwargs for add_slice()
        args = [name, gaps[0].start_sector, gaps[0].size.sectors]
        kwargs = {"size_units": Size.sector_units, "force": force}

        # set optional attributes
        if in_zpool is not None:
            kwargs["in_zpool"] = in_zpool

        if in_vdev is not None:
            kwargs["in_vdev"] = in_vdev

        new_slice = self.add_slice(*args, **kwargs)

        if tag is not None:
            new_slice.tag = tag

        return new_slice

    @classmethod
    def name_to_num(cls, part_name):
        """ name_to_num - given a partition name, lookup
            the corresponding partition number
        """
        for (p_num, p_name) in ldm_const.PARTITION_ID_MAP.iteritems():
            if p_name.upper() == part_name.upper():
                return p_num
        return None

    @property
    def remaining_space(self):
        """ remaining_space() - instance property to return a Size object of
        the remaining overall space available on the Partition
        """
        return Size(str(self.size.sectors - \
            sum([c.size.sectors for c in self._children])) + Size.sector_units)

    @property
    def is_pcfs_formatted(self):
        """ is_pcfs_formatted() instance property
        Returns:
        - True if the partition is formatted with a pcfs filesystem.
        - False if the partition is not formatted with a pcfs filesystem.
        - None if unknown
        This test is useful in conjuction with the is_efi_system property to
        determine if an existing EFI system partition  can be reused to store
        the Solaris UEFI boot program. If False, a format using mkfs on the
        partition would be required.
        """
        return self._is_pcfs_formatted

    @property
    def is_primary(self):
        """ is_primary() - instance property to return a Boolean value of True
        if the partition is a primary partition
        """
        if self.name is not None and int(self.name) <= const.FD_NUMPART:
            return True
        return False

    @property
    def is_logical(self):
        """ is_logical() - instance property to return a Boolean value of True
        if the partition is a logical partition
        """
        if self.name is None or self.is_primary:
            return False
        return True

    @property
    def is_extended(self):
        """ is_extended() - instance property to return a Boolean value of True
        if the partition is a extended partition
        """
        if self.is_primary and self.part_type in Partition.EXTENDED_ID_LIST:
            return True
        return False

    @property
    def is_efi_system(self):
        """ is_solaris() - instance property to return a Boolean value of True
        if the partition is an EFI system partition
        """
        if self.part_type == 239:
            return True
        return False

    @property
    def is_solaris(self):
        """ is_solaris() - instance property to return a Boolean value of True
        if the partition is a Solaris partition
        """
        if (self.part_type == 130 and not self.is_linux_swap) or \
           self.part_type == 191:
            return True
        return False

    def __setstate__(self, state):
        """ method to override the parent's version of __setstate__.  We do
        this so deepcopy() sets validate_children to True
        """
        super(Partition, self).__setstate__(state)
        self.validate_children = True

    def __copy__(self):
        """ method to override the parent's version of __copy__.
        We want the _children list to be a shadow list instead of a flat list.
        We also need to reset validate_children to True.
        """
        new_copy = super(Partition, self).__copy__()
        new_copy._children = ShadowPhysical(new_copy)
        new_copy.validate_children = True
        return new_copy

    def __repr__(self):
        s = "Partition: name=%s; action=%s" % (self.name, self.action)

        if self.part_type is not None:
            s += "; part_type=%s" % self.part_type
        s += "; size=%s; start_sector=%s" % \
            (str(self.size), str(self.start_sector))

        if self.in_zpool is not None:
            s += "; in_zpool=%s" % self.in_zpool
        if self.in_vdev is not None:
            s += "; in_vdev=%s" % self.in_vdev
        if self.bootid is not None:
            s += "; bootid=%d" % self.bootid
        s += "; is_linux_swap=%s" % self.is_linux_swap

        return s


class HoleyObject(DataObject):
    """ class definition for HoleyObject
    """

    def __init__(self, start_sector, size):
        super(HoleyObject, self).__init__("hole")
        self.start_sector = start_sector
        self.size = size

    def to_xml(self):
        pass

    @classmethod
    def can_handle(cls, element):
        return False

    @classmethod
    def from_xml(cls, element):
        pass

    def __repr__(self):
        s = "HoleyObj:  start_sector: %d; size: %s" % \
            (self.start_sector, self.size)
        return s


class Slice(DataObject):
    """ class definition for Slice objects
    """

    def __init__(self, name):
        super(Slice, self).__init__(name)

        self.action = "create"
        self.force = False
        self.is_swap = False

        self.size = Size("0b")
        self.start_sector = 0

        self.tag = 0
        self.flag = 0

        # in_use value from libdiskmgt
        self.in_use = None

        # zpool and vdev references
        self.in_zpool = None
        self.in_vdev = None

    def to_xml(self):
        slc = etree.Element("slice")
        slc.set("name", str(self.name))
        slc.set("action", self.action)
        slc.set("force", str(self.force).lower())
        slc.set("is_swap", str(self.is_swap).lower())

        if self.in_zpool is not None:
            slc.set("in_zpool", self.in_zpool)
        if self.in_vdev is not None:
            slc.set("in_vdev", self.in_vdev)

        size = etree.SubElement(slc, "size")
        size.set("val", str(self.size.sectors) + Size.sector_units)
        size.set("start_sector", str(self.start_sector))

        return slc

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'slice'
        - a 'name' attribute

        otherwise return False
        """
        if element.tag != "slice":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        action = element.get("action")
        force = element.get("force")
        is_swap = element.get("is_swap")
        in_zpool = element.get("in_zpool")
        in_vdev = element.get("in_vdev")

        # slice is a python built-in class so use slc
        slc = Slice(name)

        if force is not None:
            try:
                slc.force = {"true": True, "false": False}[force.lower()]
            except KeyError:
                raise ParsingError("Slice element's force attribute must " +
                                   "be either 'true' or 'false'")

        if is_swap is not None:
            try:
                slc.is_swap = {"true": True, "false": False}[is_swap.lower()]
            except KeyError:
                raise ParsingError("Slice element's is_swap attribute must " +
                                   "be either 'true' or 'false'")

        size = element.find("size")
        if size is not None:
            slc.size = Size(size.get("val"))
            start_sector = size.get("start_sector")
            if start_sector is not None:
                # ensure we can cast a supplied value to an integer
                try:
                    start_sector = int(start_sector)
                except:
                    # catch any failure
                    raise ParsingError("Slice size element has invalid "
                                       "'start_sector' attribute")
            slc.start_sector = start_sector

        slc.action = action

        if in_zpool is not None:
            slc.in_zpool = in_zpool
        if in_vdev is not None:
            slc.in_vdev = in_vdev

        return slc

    def resize(self, size, size_units=Size.gb_units, start_sector=None):
        """ resize() - method to resize a Slice object.

        start_sector is optional.  If not provided, use the existing
        start_sector.

        NOTE: the resulting new size is not checked to ensure the resized
        Slice 'fits' within the current available space.  To ensure proper
        'fit', use Disk.resize_slice() or Partition.resize_slice()
        """
        if start_sector is None:
            start_sector = self.start_sector

        # delete the existing slice from the parent's shadow list
        self.delete()

        # re-insert it with the new size
        resized_slice = self.parent.add_slice(self.name, start_sector, size,
            size_units, self.in_zpool, self.in_vdev)

        return resized_slice

    def __repr__(self):
        s = "Slice: name=%s; action=%s, force=%s, is_swap=%s" \
            % (self.name, self.action, self.force, self.is_swap)
        if self.tag is not None:
            s += ", tag=%d" % self.tag
        if self.flag is not None:
            s += ", flag=%d" % self.flag
        if self.in_use is not None:
            s += ", in_use=%s" % self.in_use
        if self.in_zpool is not None:
            s += "; in_zpool=%s" % self.in_zpool
        if self.in_vdev is not None:
            s += "; in_vdev=%s" % self.in_vdev

        s += "; size=%s; start_sector=%s" % \
            (str(self.size), str(self.start_sector))

        return s


class Disk(DataObject):
    """class for modifying disk layout
    """

    reserved_guids = (efi_const.EFI_RESERVED,)

    def __init__(self, name, validate_children=True):
        """ constructor for the class
        """
        super(Disk, self).__init__(name)
        self.validate_children = validate_children
        self.disk_prop = None
        self.disk_keyword = None

        # store valid representations of the disk
        self.ctd = None
        self.volid = None
        self.devpath = None
        self.devid = None
        self.receptacle = None
        self.opath = None
        self.wwn = None

        # is the Disk a cdrom drive?
        self.iscdrom = False

        # does the Disk require an EFI system MBR partition. Ignore for GPT
        self.requires_mbr_efi_partition = False

        # Geometry object for this disk
        self.geometry = DiskGeometry()

        if platform.processor() == "i386":
            self.kernel_arch = "x86"
        else:
            self.kernel_arch = "sparc"

        # zpool and vdev references
        self.in_zpool = None
        self.in_vdev = None

        # whole disk attribute
        self._whole_disk = False

        # disk label
        self._label = None

        # write cache
        self.write_cache = False

        # Firmware specific required guids for GPT boot disks
        firmware = SystemFirmware.get()
        sysboot_guid = None
        required_guids = list(Disk.reserved_guids)
        if firmware.fw_name == 'uefi64':
            sysboot_guid = efi_const.EFI_SYSTEM
            required_guids.append(efi_const.EFI_SYSTEM)
            self.requires_mbr_efi_partition = True
        elif firmware.fw_name == 'bios':
            sysboot_guid = efi_const.EFI_BIOS_BOOT
            required_guids.append(efi_const.EFI_BIOS_BOOT)
        self._sysboot_guid = sysboot_guid
        self._required_guids = tuple(required_guids)

        # active and passive aliases
        self.active_ctds = list()
        self.passive_ctds = list()

        # shadow lists
        self._children = ShadowPhysical(self)

    def to_xml(self):
        disk = etree.Element("disk")
        if self.in_zpool is not None:
            disk.set("in_zpool", self.in_zpool)
        if self.in_vdev is not None:
            disk.set("in_vdev", self.in_vdev)
        disk.set("whole_disk", str(self.whole_disk).lower())

        if self.ctd is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.ctd)
            disk_name.set("name_type", "ctd")
        elif self.volid is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.volid)
            disk_name.set("name_type", "volid")
        elif self.devpath is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.devpath)
            disk_name.set("name_type", "devpath")
        elif self.devid is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.devid)
            disk_name.set("name_type", "devid")
        elif self.receptacle is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.receptacle)
            disk_name.set("name_type", "receptacle")
        elif self.wwn is not None:
            disk_name = etree.SubElement(disk, "disk_name")
            disk_name.set("name", self.wwn)
            disk_name.set("name_type", "wwn")

        if self.disk_prop is not None:
            disk_prop = etree.SubElement(disk, "disk_prop")
            if self.disk_prop.dev_type is not None:
                disk_prop.set("dev_type", self.disk_prop.dev_type)
            if self.disk_prop.dev_vendor is not None:
                disk_prop.set("dev_vendor", self.disk_prop.dev_vendor)
            if self.disk_prop.dev_chassis is not None:
                disk_prop.set("dev_chassis", self.disk_prop.dev_chassis)
            if self.disk_prop.dev_size is not None:
                disk_prop.set("dev_size",
                    str(self.disk_prop.dev_size.sectors) + Size.sector_units)
        if self.disk_keyword is not None:
            disk_keyword = etree.SubElement(disk, "disk_keyword")
            disk_keyword.set("key", self.disk_keyword.key)

        return disk

    @classmethod
    def can_handle(cls, element):
        if element.tag == "disk":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        in_zpool = element.get("in_zpool")
        in_vdev = element.get("in_vdev")
        whole_disk = element.get("whole_disk")

        disk = Disk("disk", validate_children=False)

        if in_zpool is not None:
            disk.in_zpool = in_zpool
        if in_vdev is not None:
            disk.in_vdev = in_vdev
        if whole_disk is not None:
            try:
                disk.whole_disk = {"true": True,
                                   "false": False}[whole_disk.lower()]
            except KeyError:
                raise ParsingError("Disk element's whole_disk attribute " +
                                   "must be either 'true' or 'false'")

        # check for disk subelements
        disk_name = element.find("disk_name")
        if disk_name is not None:
            name_type = disk_name.get("name_type")
            if name_type == "ctd":
                disk.ctd = disk_name.get("name")
            elif name_type == "volid":
                disk.volid = disk_name.get("name")
            elif name_type == "devpath":
                disk.devpath = disk_name.get("name")
            elif name_type == "devid":
                disk.devid = disk_name.get("name")
            elif name_type == "receptacle":
                disk.receptacle = disk_name.get("name")
            elif name_type == "wwn":
                disk.wwn = disk_name.get("name")
            else:
                raise ParsingError("No Disk identification provided")

        disk_prop = element.find("disk_prop")
        if disk_prop is not None:
            dp = DiskProp()
            dp.dev_type = disk_prop.get("dev_type")
            dp.dev_vendor = disk_prop.get("dev_vendor")
            dp.dev_chassis = disk_prop.get("dev_chassis")
            dev_size = disk_prop.get("dev_size")
            if dev_size is not None:
                dp.dev_size = Size(disk_prop.get("dev_size"))
            disk.disk_prop = dp

        disk_keyword = element.find("disk_keyword")
        if disk_keyword is not None:
            disk.disk_keyword = DiskKeyword()

        # Check for iSCSI information, will be handled in DOC as a child Iscsi
        # object. Left this way to it's easy to locate the Iscsi information in
        # the DOC for pre-discovery setup.
        iscsi = element.find("iscsi")

        # at least one of the disk criteria must be specified
        if disk_name is None and disk_prop is None and \
            disk_keyword is None and iscsi is None:
            raise ParsingError("No Disk identification provided")

        return disk

    @property
    def label(self):
        """ Returns the disk label. Currently "GPT" and "VTOC" are recognized.
        """
        return self._label

    @label.setter
    def label(self, val):
        """ Attempt to set the disk label.

        The disk must be empty of child (DOS) Partitions or Slices if val is
        "GPT" or empty of GPTPartitions if val is "VTOC" or a a DiskNotEmpty
        exception is raised.

        val must be either one of "GPT" or  "VTOC" otherwise ValueError is
        raised.
        """
        if val not in ["GPT", "VTOC"]:
            raise ValueError("%s is not a recognized disk label" % (val))

        if val == "GPT":
            for obj in [Partition, Slice]:
                children = self.get_children(class_type=obj)
                if children:
                    raise DiskNotEmpty
        else:
            children = self.get_children(class_type=GPTPartition)
            if children:
                raise DiskNotEmpty

        self._label = val

    @property
    def whole_disk(self):
        """ Returns the whole_disk mode value (True or False)
        """
        return self._whole_disk

    @whole_disk.setter
    def whole_disk(self, use_whole_disk):
        """ Attempt to set the whole_disk mode on the disk

        If use_whole_disk is true, the disk must be empty of child
        GPTPartitions, Partitions or Slice objects or a DiskNotEmpty exception
        is raised.

        use_whole_disk must be either True or False
        """

        if use_whole_disk:
            for obj in [GPTPartition, Partition, Slice]:
                children = self.get_children(class_type=obj)
                if children:
                    raise DiskNotEmpty
            self._whole_disk = True
        else:
            self._whole_disk = False

    @property
    def gpt_primary_table_size(self):
        """ Returns the Size value that a GPT header including protective MBR
        and GPE partition entries would occupy on this disk
        """
        # Value, per UEFI spec is the sum of:
        # + 1 block for the MBR
        # + 1 block for the GPT header
        # + (128 x 128 bytes) for partition entries
        blocks = 1 + 1 + \
            (efi_const.EFI_MIN_ARRAY_SIZE / self.geometry.blocksize)

        return Size(str(blocks) + \
                    Size.sector_units,
                    blocksize=self.geometry.blocksize)

    @property
    def gpt_backup_table_size(self):
        """ Returns the Size value that a GPT header including GPE partition
        entries would occupy on this disk
        """
        # Value, per UEFI spec is the sum of:
        # + 1 block for the GPT header
        # + (128 x 128 bytes) for partition entries
        blocks = 1 + \
            (efi_const.EFI_MIN_ARRAY_SIZE / self.geometry.blocksize)

        return Size(str(blocks) + \
                    Size.sector_units,
                    blocksize=self.geometry.blocksize)

    @property
    def gpt_partitions(self):
        return self.get_children(class_type=GPTPartition)

    @property
    def primary_partitions(self):
        """ primary_partitions() - instance property to return all primary
        partitions on this Disk
        """

        partitions = self.get_children(class_type=Partition)
        return [part for part in partitions if part.is_primary]

    @property
    def logical_partitions(self):
        """ logical_partitions() - instance property to return all logical
        partitions on this Disk
        """

        partitions = self.get_children(class_type=Partition)
        return [part for part in partitions if part.is_logical]

    @property
    def required_guids(self):
        ''' Instance proprerty to return the tuple of additional required
            partition type GUIDS besides the obvious Solaris partition.
        '''
        return self._required_guids

    @property
    def sysboot_guid(self):
        ''' Instance proprerty to return the GUID of the required system
            boot partition (EFI system or BIOS boot partition) or None for
            SPARC
        '''
        return self._sysboot_guid

    def get_next_partition_name(self, primary=True):
        """ get_next_partition_name() - method to return the next available
        partition name as a string

        Supports both GPT and legacy MBR Partition types

        primary - boolean argument representing which kind of MBR partition to
        check.
            If True AND Disk has an MBR label, only check primary partitions.
            If False, check logical partitions.
            Ignored on GPT labeled Disks
        """
        if self.label == "VTOC":
            # MBR-VTOC Disk label
            primary_set = set(range(1, const.FD_NUMPART + 1))
            logical_set = set(range(5, const.FD_NUMPART + \
                              const.MAX_EXT_PARTS + 1))

            if primary:
                available_set = primary_set - \
                    set([int(p.name) for p in self.primary_partitions])
            else:
                available_set = logical_set - \
                    set([int(p.name) for p in self.logical_partitions])
        else:
            # Solaris userland limits EFI label to 7 free partitions plus the
            # "reserved" Solaris partion: number '8'
            gpt_set = set(range(0, efi_const.EFI_NUMUSERPAR))
            available_set = gpt_set - \
                set([int(p.name) for p in self.gpt_partitions])

        if not available_set:
            return None
        else:
            return str(min(available_set))

    def get_details(self):
        """ Returns a tuple of (name, summary) containing details about this
        disk.  Currently, this method is only in use by the gui-installer.

        Returns: (name, summary)
        - name, a string indicating the size and controller type of disk.  This
          is suitable for use as the label for the disk icon.
        - summary, a 5 (or 7) line text string summary of the Disk's details.
          This is suitable for use as a Gtk+ Tooltip for the disk icon.
        """
        _ = gettext.gettext

        size_label = _("Size")
        ctrl_type_label = _("Type")
        vendor_label = _("Vendor")
        device_label = _("Device")
        bootdev_label = _("Boot device")
        chassis_label = _("Chassis")
        receptacle_label = _("Receptacle")
        unknown_label = _("Unknown")
        unknown_size_label = _("???GB")
        yes_label = _("Yes")
        no_label = _("No")

        # First, fetch all the values that we will need
        size = None
        vendor = None
        device = None
        ctrl_type = None
        bootdev = None
        chassis = None
        receptacle = None

        if self.disk_prop is not None:
            if self.disk_prop.dev_size is not None:
                # Display sizes in GB or TB, as appropriate
                if self.disk_prop.dev_size > Size("1" + Size.tb_units):
                    units = Size.tb_units
                    units_str = _("TB")
                else:
                    units = Size.gb_units
                    units_str = _("GB")
                size = self.disk_prop.dev_size.get(units=units)
                size_str = locale.format("%.1f", size) + units_str

            vendor = self.disk_prop.dev_vendor
            chassis = self.disk_prop.dev_chassis

        if self.ctd is not None:
            device = self.ctd

            # Get Disk Controller type via libdiskmgt
            dm_drive = None
            try:
                dm_desc = diskmgt.descriptor_from_key(ldm_const.ALIAS, device)
                dm_alias = diskmgt.DMAlias(dm_desc.value)
                dm_drive = dm_alias.drive
            except OSError:
                pass

            if dm_drive is not None:
                dm_controllers = dm_drive.controllers
                if dm_controllers is not None and len(dm_controllers):
                    dm_attribs = dm_controllers[0].attributes

                    if dm_attribs is not None:
                        ctrl_type = dm_attribs.type
                        # A couple of quick cosmetic changes to the value:
                        # - just take the first word, eg fibre channel -> fibre
                        # - use uppercase (prefer ATA, SCSI to ata, scsi, etc)
                        ctrl_type = ctrl_type.split()[0].upper()

        elif self.volid is not None:
            device = self.volid
        elif self.devpath is not None:
            device = self.devpath
        elif self.devid is not None:
            device = self.devid
        elif self.wwn is not None:
            device = self.wwn

        if self.is_boot_disk():
            bootdev = yes_label
        else:
            bootdev = no_label
        receptacle = self.receptacle

        if size_str is None:
            size_str = unknown_size_label
        if ctrl_type is None:
            ctrl_type = unknown_label
        if vendor is None:
            vendor = unknown_label
        if device is None:
            device = unknown_label

        name = "%s %s" % (size_str, ctrl_type)

        summary = "%s: %s\n%s: %s\n%s: %s\n%s: %s\n%s: %s" % \
            (size_label, size_str, ctrl_type_label, ctrl_type, vendor_label,
             vendor, device_label, device, bootdev_label, bootdev)
        # Only append the CRO info if it is present
        if chassis is not None:
            summary = "%s\n%s: %s" % (summary, chassis_label, chassis)
        if receptacle is not None:
            summary = "%s\n%s: %s" % (summary, receptacle_label, receptacle)

        return name, summary

    def add_gptpartition(self, index, start_sector, size,
                         size_units=Size.gb_units,
                         partition_type=efi_const.EFI_USR,
                         in_zpool=None, in_vdev=None, force=False):
        """ add_gptpartition() - method to create a GPTPartition object
        and add it as a child of the Disk object
        """
        # create a new GPTPartition object
        new_gpart = GPTPartition(index)

        new_gpart.guid = partition_type

        new_gpart.size = Size(str(size) + str(size_units),
                              blocksize=self.geometry.blocksize)
        new_gpart.start_sector = start_sector
        new_gpart.in_zpool = in_zpool
        new_gpart.in_vdev = in_vdev
        new_gpart.force = force

        # add the new GPTPartition object as a child
        self.insert_children(new_gpart)

        return new_gpart

    def delete_gptpartition(self, gpart):
        """ delete_gptpartition() - method to delete a specific
        GPTPartition object
        """
        self.delete_children(name=gpart.name, class_type=GPTPartition)

    def resize_gptpartition(self, gpt_partition, size,
                            size_units=Size.gb_units):
        """ resize_gptpartition() - method to resize a GPTPartition child.
        """
        # create a new_size object
        new_size = Size(str(size) + str(size_units),
                        blocksize=self.geometry.blocksize)

        # check to see if the resized Partition is simply decreasing in size
        if new_size <= gpt_partition.size:
            # simply call GPTPartition.resize
            return gpt_partition.resize(size, size_units)

        # find the previous and next gap
        previous_gap = None
        next_gap = None
        available_size = copy.copy(gpt_partition.size)
        end_sector = gpt_partition.start_sector + gpt_partition.size.sectors

        # Since we are using LBA, immediately adjacent gaps should align
        # exactly with the start and end of gpt_partition respectively.
        for gap in self.get_gaps():
            if gap.start_sector + gap.size.sectors - \
                   gpt_partition.start_sector == 0:
                previous_gap = gap
                available_size += previous_gap.size
            elif gpt_partition.start_sector + gpt_partition.size.sectors - \
               gap.start_sector == 0:
                next_gap = gap
                available_size += next_gap.size
                end_sector = next_gap.start_sector + next_gap.size.sectors

        # try to fill in both sides of the Partition
        remaining_space = new_size.sectors - gpt_partition.size.sectors

        if next_gap is not None:
            # try to consume space from the right first
            remaining_space = fill_right(gpt_partition, remaining_space,
                                         next_gap)
            if not remaining_space:
                # the size of the Partition is increasing but not impacting the
                # next object so call resize
                return gpt_partition.resize(size, size_units)

        # consume additional space from the left, if needed
        if remaining_space and previous_gap is not None:
            # continue to consume from the left
            remaining_space = fill_left(gpt_partition, remaining_space,
                                        previous_gap)

        if remaining_space:
            # there's no room to increase this Partition
            raise InsufficientSpaceError(available_size)

        new_start_sector = end_sector - new_size.sectors
        return gpt_partition.resize(size, size_units,
                                    start_sector=new_start_sector)

    def add_partition(self, index, start_sector, size,
                      size_units=Size.gb_units,
                      partition_type=Partition.name_to_num("Solaris2"),
                      bootid=Partition.INACTIVE, in_zpool=None, in_vdev=None):
        """ add_partition() - method to create a Partition object and add it as
        a child of the Disk object
        """
        # check the index value.  If the partition to be created is a logical
        # partition, set the bootid to Partition.INACTIVE per fdisk rules
        if int(index) > const.FD_NUMPART:
            bootid = Partition.INACTIVE

        # create a new Partition object based on the partition type
        new_partition = Partition(index)
        new_partition.part_type = partition_type
        new_partition.bootid = bootid
        new_partition.size = Size(str(size) + str(size_units),
                                  blocksize=self.geometry.blocksize)
        new_partition.start_sector = start_sector
        new_partition.in_zpool = in_zpool
        new_partition.in_vdev = in_vdev

        # add the new Partition object as a child
        self.insert_children(new_partition)

        return new_partition

    def delete_partition(self, partition):
        """ delete_partition() - method to delete a specific Partition object
        """
        self.delete_children(name=partition.name, class_type=Partition)

    def resize_partition(self, partition, size, size_units=Size.gb_units):
        """ resize_partition() - method to resize a Partition child.
        """

        # create a new_size object
        new_size = Size(str(size) + str(size_units))

        # check to see if the resized Partition is simply decreasing in size
        if new_size <= partition.size:
            # simply call Partition.resize
            return partition.resize(size, size_units)

        # find the previous and next gap
        previous_gap = None
        next_gap = None
        available_size = copy.copy(partition.size)
        end_sector = partition.start_sector + partition.size.sectors

        if partition.is_primary:
            gap_list = self.get_gaps()
            adjacent_size = self.geometry.cylsize
        else:
            gap_list = self.get_logical_partition_gaps()
            adjacent_size = LOGICAL_ADJUSTMENT + 1

        for gap in gap_list:
            if abs(gap.start_sector + gap.size.sectors - \
                   partition.start_sector) <= adjacent_size:
                previous_gap = gap
                available_size += previous_gap.size
            if abs(partition.start_sector + partition.size.sectors - \
               gap.start_sector) <= adjacent_size:
                next_gap = gap
                available_size += next_gap.size
                end_sector = next_gap.start_sector + next_gap.size.sectors

        # try to fill in both sides of the Partition
        remaining_space = new_size.sectors - partition.size.sectors

        if next_gap is not None:
            # try to consume space from the right first
            remaining_space = fill_right(partition, remaining_space, next_gap)
            if not remaining_space:
                # the size of the Partition is increasing but not impacting the
                # next object so call resize
                return partition.resize(size, size_units)

        # consume additional space from the left, if needed
        if remaining_space and previous_gap is not None:
            # continue to consume from the left
            remaining_space = fill_left(partition, remaining_space,
                                        previous_gap)

        if remaining_space:
            # there's no room to increase this Partition
            raise InsufficientSpaceError(available_size)

        new_start_sector = end_sector - new_size.sectors
        return partition.resize(size, size_units,
                                start_sector=new_start_sector)

    def add_slice(self, index, start_sector, size, size_units=Size.gb_units,
                  in_zpool=None, in_vdev=None, force=False):
        """ add_slice() - method to create a Slice object and add it as a child
        of the Disk object
        """
        # create a new Slice object
        new_slice = Slice(index)
        new_slice.size = Size(str(size) + str(size_units),
                              blocksize=self.geometry.blocksize)
        new_slice.start_sector = start_sector
        new_slice.in_zpool = in_zpool
        new_slice.in_vdev = in_vdev
        new_slice.force = force

        # add the new Slice object as a child
        self.insert_children(new_slice)

        return new_slice

    def delete_slice(self, slc):
        """ delete_slice() - method to delete a specific Slice object
        """
        self.delete_children(name=slc.name, class_type=Slice)

    def resize_slice(self, slc, size, size_units=Size.gb_units):
        """ resize_slice() - method to resize a Slice child.
        """

        # create a new_size object
        new_size = Size(str(size) + str(size_units))

        # check to see if the resized Slice is simply decreasing in size
        if new_size <= slc.size:
            # simply call Slice.resize
            return slc.resize(size, size_units)

        # find the previous and next gap
        previous_gap = None
        next_gap = None
        available_size = copy.copy(slc.size)
        end_sector = slc.start_sector + slc.size.sectors
        for gap in self.get_gaps():
            if abs(gap.start_sector + gap.size.sectors - slc.start_sector) <= \
               self.geometry.cylsize:
                previous_gap = gap
                available_size += previous_gap.size
            if abs(slc.start_sector + slc.size.sectors - gap.start_sector) <= \
               self.geometry.cylsize:
                next_gap = gap
                available_size += next_gap.size
                end_sector = next_gap.start_sector + next_gap.size.sectors

        # try to fill in both sides of the Slice
        remaining_space = new_size.sectors - slc.size.sectors

        if next_gap is not None:
            # try to consume space from the right first
            remaining_space = fill_right(slc, remaining_space, next_gap)
            if not remaining_space:
                # the size of the Slice is increasing but not impacting the
                # next object so call resize
                return slc.resize(size, size_units)

        # consume additional space from the left, if needed
        if remaining_space and previous_gap is not None:
            # continue to consume from the left
            remaining_space = fill_left(slc, remaining_space, previous_gap)

        if remaining_space:
            # there's no room to increase this Slice
            raise InsufficientSpaceError(available_size)

        new_start_sector = end_sector - new_size.sectors
        return slc.resize(size, size_units, start_sector=new_start_sector)

    def add_gpt_system(self, donor=None):
        """ Add default system/bios boot for x86 if this is a GPT disk

            Params
            - donor
              a GPTPartition object on the same disk that can be resized as
              a last resort if the disk doesn't have enough contiguous free
              space to contain the system partition.

            Returns tuple: (sys_part, donor)
            - sys_part
              The appropriate EFI system or BIOS system that was created.
            - donor
              The donor partition which may have been partially or fully used
              to create space for the system partition. Callers should check
              the returned copy of donor.
        """
        if self.kernel_arch == "sparc":
            return None, None

        if self.label == "VTOC":
            raise ValueError("Can't add EFI_SYSTEM/EFI_BIOS_BOOT" \
                             "to a VTOC labeled disk")

        gparts = self.get_children(class_type=GPTPartition)

        # Make sure we don't already have one.
        # Note that it must occupy a slot between s0 - s6 otherwise it
        # will not be mountable and therefore be unusable.
        sys = filter(lambda gpe: (gpe.action != "delete") and
                                 (gpe.guid == self.sysboot_guid) and
                                 (int(gpe.name) < efi_const.EFI_NUMUSERPAR),
                     gparts)

        if sys:
            raise DuplicateGPTPartition(sys[0], "attempt to add "
                "EFI_SYSTEM/EFI_BIOS_BOOT when disk already has one")

        # Get the lowest available slot
        index = self.get_next_partition_name()
        if index is None:
            raise NoGPTPartitionSlotsFree("attempt to add EFI_SYSTEM/ "
                "EFI_BIOS_BOOT to disk with no empty partition slots")

        sys_size = Size(str(efi_const.EFI_DEFAULT_SYSTEM_SIZE) + \
                        Size.byte_units,
                        self.geometry.blocksize)

        gaps = self.get_gaps()

        # next is like filter but we only explore the list up to
        # the first match (or if there are none the whole list).
        gap = next((hole for hole in gaps if hole.size >= sys_size), None)
        if gap is not None:
            # we found a suitable gap for the system partition
            gptsys_start = gap.start_sector
        else:
            if donor is None:
                raise InsufficientSpaceError(0, "Insufficient space for "
                    "EFI_SYSTEM/EFI_BIOS_BOOT partition")
            else:
                # We need to use some space belonging to the donor partition.
                # donor must belong to the same disk object
                if not self.name_matches(donor.parent):
                    raise ValueError("Donor partition does not belong " \
                        "to this disk: %s" % str(self))

                # donor must be a solaris partition as it is the only one
                # that we support resizing of.
                if not donor.is_solaris:
                    raise ValueError("Donor partition must be a solaris " \
                        "partition. Invalid partition type: %s" \
                        % str(donor.part_type))

                # donor must not have the preserve action set
                if donor.action == "preserve":
                    raise ValueError("Donor partition is a preserved and " \
                                       "cannot not be resized")

                # XXX - the size of donor should be checked, however it will
                # get validated for minimum size requirements as the Solaris
                # installation partition in all current usage.

                # Find an adjacent gap before the donor partition. Use as much
                # free space from it as possible before consuming space from
                # the donor.
                for hole in gaps:
                    if hole.start_sector + hole.size.sectors \
                        - donor.start_sector == 0:
                        gap = hole
                        shortage = sys_size.sectors - gap.size.sectors
                        gptsys_start = gap.start_sector
                        break
                else:
                    shortage = sys_size.sectors
                    gptsys_start = donor.start_sector

                # Take what we need from donor to make up the shortage
                newsize = donor.size.sectors - shortage
                newstart_sector = donor.start_sector + shortage
                donor = donor.resize(newsize,
                    size_units=Size.sector_units,
                    start_sector=newstart_sector)

        sys_part = self.add_gptpartition(str(index), gptsys_start,
            sys_size.sectors, size_units=Size.sector_units,
            partition_type=self.sysboot_guid, force=True)

        return sys_part, donor

    def add_gpt_reserve(self, donor=None):
        """ Add default EFI_RESERVED to disk if this is a GPT disk

            Returns tuple: (resv_part, donor)
            - sys_part
              The Solaris reserved partition that was created.
            - donor
              The donor partition which may have been partially or fully used
              to create space for the reserved partition. Callers should check
              the returned copy of donor.
        """
        if self.label == "VTOC":
            raise ValueError("Can't add Solaris reserved partition " \
                               "to a VTOC labeled disk")

        gparts = self.get_children(class_type=GPTPartition)

        # Make sure we don't already have one
        resv = filter(lambda gpe: gpe.is_reserved and gpe.action != "delete",
                      gparts)
        if resv:
            raise DuplicateGPTPartition(resv[0], "attempt to add "
                "EFI_RESERVED when disk already has one")

        # This should ideally be partition 8. Otherwise we have to use the
        # highest available index under 7, which is the "whole disk" partition.
        used = [int(gpe.name) for gpe in gparts]
        for index in [efi_const.EFI_PREFERRED_RSVPAR] + \
                     range(efi_const.EFI_NUMUSERPAR - 1, -1, -1):
            if index not in used:
                break
        else:
            raise NoGPTPartitionSlotsFree("attempt to add EFI_SYSTEM/"
                "EFI_BIOS_BOOT to disk with no empty partition slots")

        # Check to make sure we get a clean block size multiple
        if EFI_BLOCKSIZE_LCM % self.geometry.blocksize != 0:
            # Unexpected block size (ie. not a multiple of 512,
            # or > EFI_BLOCKSIZE_LCM)
            # Don't try to do anything fancy.
            block_multiplier = 1
        else:
            block_multiplier = EFI_BLOCKSIZE_LCM / self.geometry.blocksize

        # The reserved part HAS to be >=16384 sectors, so increment it up
        # to account for any rounding down that might happen to it.
        resv_sectors = efi_const.EFI_MIN_RESV_SIZE + block_multiplier

        # We want to place the reserved partition as close to the end of the
        # disk as possible so sort the gaps in reverse order by start sector
        unsortedgaps = self.get_gaps()
        gaps = sorted(unsortedgaps,
                      key=lambda gap: gap.start_sector, reverse=True)

        # next is like filter but we only explore the list up to
        # the first match (or if there are none the whole list).
        gap = next((hole for hole in gaps if \
                    hole.size.sectors >= resv_sectors),
                    None)

        if gap is not None:
            # Fill the gap up from the end rather than the beginning
            resv_start = gap.start_sector + gap.size.sectors - resv_sectors
        else:
            if donor is None:
                raise InsufficientSpaceError("Insufficient space for "
                    "Solaris reserved partition")
            else:
                # We need to use some space belonging to the donor partition.
                # donor must belong to the same disk object
                if not self.name_matches(donor.parent):
                    raise ValueError("Donor partition does not belong " \
                        "to this disk: %s" % str(self))

                # donor must be a solaris partition as it is the only one
                # that we support resizing of.
                if not donor.is_solaris:
                    raise ValueError("Donor partition must be a solaris " \
                        "partition. Invalid partition type: %s" \
                        % str(donor.part_type))

                # donor must not have the preserve action set
                if donor.action == "preserve":
                    raise ValueError("Donor partition is a preserved and " \
                                       "cannot not be resized")

                # XXX - the size of donor should be checked, however it will
                # get validated for minimum size requirements as the Solaris
                # installation partition in all current usage.

                # Find an adjacent gap after the donor partition. Use as much
                # free space from it as possible before consuming space from
                # the donor.
                for hole in gaps:
                    if donor.start_sector + donor.size.sectors \
                        - hole.start_sector == 0:
                        gap = hole
                        shortage = resv_sectors - gap.size.sectors
                        resv_start = gap.start_sector - shortage
                        break
                else:
                    shortage = resv_sectors
                    resv_start = donor.start_sector + donor.size.sectors \
                        - resv_sectors

                # Take what we need from donor to make up the shortage
                newsize = donor.size.sectors - shortage
                donor = donor.resize(newsize, size_units=Size.sector_units)

        resv_part = self.add_gptpartition(str(index), resv_start,
            resv_sectors, Size.sector_units,
            partition_type=efi_const.EFI_RESERVED, force=True)

        return resv_part, donor

    def add_mbr_system(self, solaris2_part=None):
        """ Add, if required, an EFI system partition x86 to an MBR/DOS
            partitioned disk

            An MBR/DOS EFI system partition is required if and only if the
            system is UEFI and attempting to install onto an MBR/DOS
            partitioned disk.

            Preference is given to using a logical partition slot rather
            than a primary slot because the small amount of space required by
            the EFI system partition and the very limited number of primary
            partition slots available makes for poor use of primary slots and
            helps avoid large, unusable primary partition gaps.

            Params
            - solaris2_part
              a Solaris2 Partition object on the same disk that can be resized
              or converted if the disk doesn't have enough contiguous free
              space or partition slots to contain the EFI system partition.

            Returns tuple: (sys_part, donor)
            - efi_part
              The EFI system partition that was created. The EFI system
              partition returned will be a logical partition to conserve
              available primary partition slots.
            - solaris2_part
              The Solaris2 partition which may have been modified to create
              space for the system partition. Callers should check the
              returned copy of donor as it may have been resized and/or
              converted from primary to logical type to make room for the EFI
              system partition
        """

        # Not applicable to SPARC or BIOS systems
        if not self.requires_mbr_efi_partition:
            return None, solaris2_part

        if self.label == "GPT":
            raise ValueError("Can't add MBR EFI System partition to a " \
                             "GPT labeled disk")

        if solaris2_part:
            # Chuck out the solaris2_part if it does not belong to this disk
            if not self.name_matches(solaris2_part.parent):
                raise ValueError("solaris2_part argument does not belong " \
                                 "to this disk: %s" % str(self))

            # Chuck out the solaris2_part if it is not actually Solaris2.
            if solaris2_part.action != 'create' and \
                not solaris2_part.is_solaris:
                raise ValueError("solaris2_part argument must be a valid "
                                 "Solaris2 partition: %s" \
                                 % str(solaris2_part))

        parts = self.get_children(class_type=Partition)

        # Make sure we don't already have one.
        efisys = filter(lambda part: part.action != "delete" and
                                     part.is_efi_system,
                        parts)

        if efisys:
            raise DuplicatePartition(efisys[0], "attempt to add an MBR EFI " \
                "System partition to disk that already has one")

        # See if the disk has an extended partition. We will try to squeeze
        # the EFI System partition in there.
        extended_part = None
        for part in parts:
            if part.is_extended and part.action != "delete":
                extended_part = part
                break

        efisys_size = Size(str(efi_const.EFI_DEFAULT_SYSTEM_SIZE) + \
                           Size.byte_units,
                           self.geometry.blocksize)
        efisys_type = Partition.name_to_num("EFI System")

        if extended_part:
            # Already have an extended partition.
            # We need a logical gap and a slot to create a logical EFI system
            # partition.
            index = self.get_next_partition_name(primary=False)
            bestfit = None
            efisys_start = None
            if index:
                for gap in self.get_logical_partition_gaps():
                    # Look for the smallest gap that's big enough
                    if gap.size >= efisys_size:
                        if not bestfit or gap.size < bestfit.size:
                            bestfit = gap
                if bestfit:
                    efisys_start = gap.start_sector

            if not efisys_start:
                # No existing logical gap or slot. Before attempting to consume
                # part of solaris2_part, see if there is a primary partition
                # slot free, and a gap.
                if not index:
                    # There is no free logical slot, so look for a primary one
                    # instead.
                    index = self.get_next_partition_name()
                    if not index:
                        # No logical or primary slots - Well and truly hosed.
                        raise NoPartitionSlotsFree

                    # We have a primary slot, just need to find a gap
                    gaps = self.get_gaps()
                    for gap in gaps:
                        if gap.size >= efisys_size:
                            if not bestfit or gap.size < bestfit.size:
                                bestfit = gap

                    if bestfit:
                        # Found a suitable primary gap
                        efisys_start = bestfit.start_sector

                # At this point we have a logical slot but no usable logical
                # gap. See if the Solaris2 partition is logical.
                # If so we can carve a gap out of that.
                if not efisys_start:
                    if not solaris2_part or not solaris2_part.is_logical:
                        # No gaps and no solaris2_part that we can consume
                        # so give up
                        raise InsufficientSpaceError(0, "Insufficient space " \
                            "for EFI system partition")

                    # Resize our logical Solaris2 partition
                    # Look for a gap immediately before the Solaris2 partition
                    # and use as much free space from it as possible before
                    # consuming space from the Solaris2 partition
                    s2_pre_gap = solaris2_part.get_gap_before()
                    if s2_pre_gap:
                        shortage = efisys_size.sectors - \
                            s2_pre_gap.size.sectors
                        efisys_start = s2_pre_gap.start_sector
                    else:
                        shortage = efisys_size.sectors
                        efisys_start = solaris2_part.start_sector

                    # Take what we need from solaris2_part to make up the
                    # shortage
                    new_s2_size = solaris2_part.size.sectors - shortage
                    new_s2_start = solaris2_part.start_sector + shortage
                    solaris2_part = solaris2_part.resize(new_s2_size,
                        size_units=Size.sector_units,
                        start_sector=new_s2_start)

            efisys_part = self.add_partition(index,
                efisys_start,
                efisys_size.sectors,
                size_units=Size.sector_units,
                partition_type=efisys_type)

        else:
            # No extended partition. Convert the Solaris2 partition. The
            # Solaris2 partition MUST be a primary partition at this point
            # since we failed to find an extended partition above.
            new_extended_part = solaris2_part.change_type(
                Partition.name_to_num("DOS Extended"))

            # Add the EFI system partition first. Don't need to check the
            # partition index returned as there are guaranteed to be no
            # logicals at this point. Index will be 5
            gaps = self.get_logical_partition_gaps()
            index = self.get_next_partition_name(primary=False)
            efisys_part = self.add_partition(index,
                gaps[0].start_sector,
                efisys_size.sectors,
                size_units=Size.sector_units,
                partition_type=efisys_type)

            # Re-calculate gaps to get the starting point of the new
            # Solaris2 partition.
            # <paranoia>
            # There should be only one but just in case some rounding
            # adjumstment created an unexpected tiny gap, process the list and
            # use the biggest gap.
            # </paranoia>
            index = self.get_next_partition_name(primary=False)
            biggest_gap = None
            for gap in self.get_logical_partition_gaps():
                if biggest_gap is None or \
                    gap.size.sectors > biggest_gap.size.sectors:
                    biggest_gap = gap

            solaris2_part = self.add_partition(index,
                biggest_gap.start_sector,
                biggest_gap.size.sectors,
                size_units=Size.sector_units,
                partition_type=Partition.name_to_num("Solaris2"),
                in_zpool=solaris2_part.in_zpool,
                in_vdev=solaris2_part.in_vdev)

        return efisys_part, solaris2_part

    def add_required_partitions(self, donor):
        """ Add, if required, an EFI system partition (fdisk or GPT),
            and a reserved partition.

            Returns tuple: (efi_sys, resv, donor)
            - efi_sys
              either a Partitioin or GPTPartition or None to be used
              as the EFI system partition. None is returned if the
              system does not require an EFI System partition.
            - resv
              a GPTPartition to be used by ZFS or None if the system
              does not require a reserved GPTPartition
            - donor
              The donor you passed in or None.
        """

        def check_efi_sys(part):
            # If an EFI system partition check that it's PCFS formatted and
            # change its action to "create" so Instantiation will format.
            if part.is_efi_system:
                # If an EFI system partition check that it's PCFS formatted
                # and change its action to "create" so Instantiation will
                # format.
                if not part.is_pcfs_formatted:
                    part.action = "create"

        if self.label == "VTOC":
            try:
                efi_sys, donor = self.add_mbr_system(donor)
            except DuplicatePartition as err:
                # Great - there is at least one that can be used.
                efi_sys = err.duplicate
                check_efi_sys(efi_sys)

            resv = None
        else:
            try:
                efi_sys, donor = self.add_gpt_system(donor)
            except DuplicateGPTPartition as err:
                # Great - there is at least one that can be used.
                efi_sys = err.duplicate
                check_efi_sys(efi_sys)

            try:
                resv, donor = self.add_gpt_reserve(donor)
            except DuplicateGPTPartition as err:
                resv = err.duplicate

        return (efi_sys, resv, donor)

    def _get_gpt_gaps(self):
        """ _get_gpt_gaps() - method to return a list of Holey Objects on a
        GPT labeled disk.
        """
        # create a list of sector usage by this disk.
        usage = list()
        for child in self._children:
            # skip partitions or slices marked for deletion
            if child.action == "delete":
                continue
            usage.append(child.start_sector)
            usage.append(child.start_sector + child.size.sectors - 1)

        # sort the usage list and add bookends
        usage.sort()

        # insert bookend and usage value pair to corden off the area reserved
        # for the primary GPT table.
        usage[0:0] = [0L, 0L, self.gpt_primary_table_size.sectors - 1]

        # The disk's end bookend is effectively the start of the backup GPT
        # table
        usage.append(self.disk_prop.dev_size.sectors - \
            self.gpt_backup_table_size.sectors)

        holes = list()
        i = 0

        # Any potential gap must be at least as big as the standard block
        # alignment unit
        if EFI_BLOCKSIZE_LCM % self.geometry.blocksize != 0:
            # Unexpected block size (ie. not a multiple of 512,
            # or > EFI_BLOCKSIZE_LCM)
            # Don't try to do anything fancy.
            min_block_count = 1
        else:
            min_block_count = EFI_BLOCKSIZE_LCM / self.geometry.blocksize

        while i < len(usage) - 1:
            start_sector = usage[i]

            # subtract i+1 to get the size of this hole.
            size = usage[i + 1] - usage[i] - 1

            # Ignore any hole which is smaller than the standard block
            # alignment unit
            if size >= min_block_count:
                holes.append(HoleyObject(start_sector + 1,
                    Size(str(size) + Size.sector_units)))

            # step across the size of the child
            i += 2

        return holes

    def _get_vtoc_gaps(self):
        """ _get_vtoc_gaps() - method to return a list of Holey Objects
        (depending on architecture) available on the Disk.

        Backup slices (V_BACKUP) and logical partitions (if x86) are skipped.
        """
        # create a list of sector usage by this disk.
        usage = list()
        for child in self._children:
            # skip partitions or slices marked for deletion
            if child.action == "delete":
                continue
            # skip the child if it's a slice and has a tag of V_BACKUP (5)
            if isinstance(child, Slice):
                if getattr(child, "tag") == const.V_BACKUP:
                    continue
            # skip the child if it's a logical partition
            if isinstance(child, Partition):
                if child.is_logical:
                    continue

            usage.append(child.start_sector)
            usage.append(child.start_sector + child.size.sectors)

        # sort the usage list and add bookends
        usage.sort()
        usage.insert(0, 0L)
        usage.append(self.disk_prop.dev_size.sectors)

        holes = list()
        i = 0
        while i < len(usage) - 1:
            start_sector = usage[i]

            # subtract i+1 to get the size of this hole.
            size = usage[i + 1] - usage[i]

            # if the size is 0 (for a starting sector of 0) or 1 (for adjacent
            # children), there's no gap, so skip it.
            # Also skip any hole which is smaller than the cylinder boundary
            if size not in [0, 1] and size > self.geometry.cylsize:
                # do not correct for holes that start at 0
                if start_sector == 0:
                    holes.append(HoleyObject(start_sector,
                        Size(str(size - 1) + Size.sector_units)))
                else:
                    holes.append(HoleyObject(start_sector + 1,
                        Size(str(size - 1) + Size.sector_units)))

            # step across the size of the child
            i += 2

        # now that the holes are calculated, adjust any holes whose start
        # sector does not fall on a cylinder or block multiple boundary.
        final_list = list()
        for hole in holes:
            if hole.start_sector % self.geometry.cylsize != 0:
                # celing the start_sector to the next min_size_unit boundary
                new_start_sector = \
                    ((hole.start_sector / self.geometry.cylsize) * \
                    self.geometry.cylsize) + self.geometry.cylsize

                # calculate the difference so the size can be adjusted
                difference = new_start_sector - hole.start_sector

                # reset the attributes of the hole
                hole.start_sector = new_start_sector
                hole.size = Size(str(hole.size.sectors - difference) + \
                                 Size.sector_units)

            # check the start_sector of the gap.  If it starts at zero, adjust
            # it to start at the first cylinder boundary
            if hole.start_sector == 0:
                hole.start_sector = self.geometry.cylsize
                hole.size = \
                    Size(str(hole.size.sectors - self.geometry.cylsize) + \
                         Size.sector_units)

            # adjust the size down to the nearest end cylinder
            if hole.size.sectors % self.geometry.cylsize != 0:
                new_size = (hole.size.sectors / self.geometry.cylsize) * \
                           self.geometry.cylsize
                hole.size = Size(str(new_size) + Size.sector_units)

            # finally, re-check the size of the hole.  If it's smaller than a
            # cylinder, do not add it to the list
            if hole.size.sectors > self.geometry.cylsize:
                final_list.append(hole)

        return final_list

    def get_gaps(self):
        """ get_gaps() - method to return a list of Holey Objects, depending
        depending (primarily) on disk label, available on the Disk.
        If disk.label is unset, an attempt will be made to identify the disk
        label based on contents of the disk.
        """
        # the Disk must have a disk_prop.dev_size attribute
        if not hasattr(self.disk_prop, "dev_size"):
            return list()

        if self.label == "GPT":
            # Let gap code determine initial hole as there are headers
            # on both ends of the disk.
            return self._get_gpt_gaps()

        elif self.label == "VTOC":
            if not self._children:  # Short circuit for childless VTOC disk
                return[HoleyObject(0, self.disk_prop.dev_size)]

            else:
                return self._get_vtoc_gaps()

        elif self.label is None:
            # No label so examine children. Try VTOC first.
            for obj in [Partition, Slice]:
                children = self.get_children(class_type=obj)
                if children:
                    return self._get_vtoc_gaps()

            # Now try GPT
            children = self.get_children(class_type=GPTPartition)
            if self.children:
                return self._get_gpt_gaps()

            # Still nothing. Just return a list of the size of the disk
            return[HoleyObject(0, self.disk_prop.dev_size)]

    def get_logical_partition_gaps(self):
        """ get_logical_partition_gaps() - method to return a list of Holey
        Objects available within the extended partition of the disk
        """
        # check for an extended partition
        part_list = self.get_children(class_type=Partition)

        for part in part_list:
            if part.is_extended and part.action != "delete":
                extended_part = part
                break
        else:
            return list()

        # extract all logicial partitions
        logical_list = [p for p in part_list if p.is_logical]
        if not logical_list:
            # return a single Holey Object the size of the extended partition
            return [HoleyObject(extended_part.start_sector,
                                extended_part.size)]

        # create a list of sector usage by the logical partitions
        usage = list()
        for logical_part in logical_list:
            usage.append(logical_part.start_sector)
            usage.append(logical_part.start_sector + logical_part.size.sectors)

        # sort the usage list and add bookends
        usage.sort()
        usage.insert(0, extended_part.start_sector)
        usage.append(extended_part.start_sector + extended_part.size.sectors)

        holes = list()
        i = 0
        while i < len(usage) - 1:
            # subtract i+1 to get the size of this hole.
            size = usage[i + 1] - usage[i]

            # if the size is equal to the logical partition offset, or the gap
            # is smaller than the offset there's no gap, so skip it.
            if size > LOGICAL_ADJUSTMENT:
                # set the start_sector of the hole to include the offset.
                start_sector = usage[i] + LOGICAL_ADJUSTMENT
                size_obj = Size(str(size - 1 - LOGICAL_ADJUSTMENT) + \
                                Size.sector_units)
                holes.append(HoleyObject(start_sector, size_obj))

            # step across the size of the child
            i += 2

        return holes

    def __setstate__(self, state):
        """ method to override the parent's version of __setstate__.  We do
        this so deepcopy() sets validate_children to True
        """
        super(Disk, self).__setstate__(state)
        self.validate_children = True

    def __copy__(self):
        """ method to override the parent's version of __copy__.
        We want the _children list to be a shadow list instead of a flat list
        We also need to reset validate_children to True.
        """
        new_copy = super(Disk, self).__copy__()
        new_copy._children = ShadowPhysical(new_copy)
        new_copy.validate_children = True
        return new_copy

    def __repr__(self):
        s = "Disk: "
        s += "ctd=%s; volid=%s; devpath=%s; devid=%s; wwn=%s" \
            % (self.ctd, self.volid, self.devpath, self.devid, self.wwn)

        if self.disk_prop is not None:
            if self.disk_prop.dev_type is not None:
                s += "; prop:dev_type=%s" % self.disk_prop.dev_type
            if self.disk_prop.dev_vendor is not None:
                s += "; prop:dev_vendor=%s" % self.disk_prop.dev_vendor
            if self.disk_prop.dev_size is not None:
                s += "; prop:dev_size=%s" % self.disk_prop.dev_size
        if self.disk_keyword is not None:
            s += "; keyword: key=%s" % self.disk_keyword.key

        s += "; is_cdrom=%s; label=%s" % (self.iscdrom, self.label)
        if self.in_zpool is not None:
            s += "; in_zpool=%s" % self.in_zpool
        if self.in_vdev is not None:
            s += "; in_vdev=%s" % self.in_vdev
        s += "; whole_disk=%s" % self.whole_disk
        s += "; write_cache=%s" % self.write_cache
        if self.active_ctds:
            s += "; active ctd aliases=%s" % ", ".join(self.active_ctds)
        if self.passive_ctds:
            s += "; passive ctd aliases=%s" % ", ".join(self.passive_ctds)

        return s

    def _unmount_ufs_filesystems(self):
        """ method to unmount all mounted filesystems on this disk
        """
        disk_dev = "/dev/dsk/%s" % self.ctd
        self.logger.debug("Unmounting filesystems on disk: %s" % self.ctd)
        with open(MNTTAB, 'r') as fh:
            for line in fh.readlines():
                if line.startswith(disk_dev):
                    cmd = [UMOUNT, "-f", disk_dev]
                    run(cmd)

    def _release_swap(self):
        """ method to release all swap devices associated
            with a given disk
        """
        disk_dev = "/dev/dsk/%s" % self.ctd
        # get a list of all swap devices on the system
        cmd = [SWAP, "-l"]
        p = run(cmd, check_result=Popen.ANY)

        # remove the header and trailing newline
        swap_list = p.stdout.split("\n")[1:-1]
        for swap in swap_list:
            swap_dev = swap.split()[0]
            if swap_dev.startswith(disk_dev):
                cmd = [SWAP, "-d", disk_dev + "swap"]
                run(cmd)

    def _create_ufs_swap(self, swap_slice_list, dry_run):
        """ _create_ufs_swap() - method to create a new swap entry from a list
        of slices
        """

        disk_dev = "/dev/dsk/%s" % self.ctd
        self.logger.debug("Creating ufs swap slice(s)")
        for swap_slice in swap_slice_list:
            swap_dev = disk_dev + "s" + str(swap_slice.name)

            # look to see if this slice is already being used as swap
            cmd = [SWAP, "-l"]
            p = run(cmd, check_result=Popen.ANY)
            for line in p.stdout.splitlines():
                if line.startswith(swap_dev):
                    cmd = [SWAP, "-d", swap_dev]
                    if not dry_run:
                        run(cmd)

            cmd = [SWAP, "-a", swap_dev]
            if not dry_run:
                run(cmd)

    def _update_partition_table(self, part_list, dry_run):
        """ _update_partition_table() - method to lay out the fdisk partitions
        of the Disk
        """

        # Need to destroy all zpools on the disk, unmount filesystems, and
        # release ufs swap.
        if not dry_run:
            # release ufs swap
            self._release_swap()
            # unmount ufs filesystems
            self._unmount_ufs_filesystems()

        # generate and write the desired partition table to the disk.
        # partition.name == partition number
        # partition.part_type = id. Indicates if solaris, linux, extended etc.
        # partition.bootid = 0x80 means active
        # partition.size = size in bytes
        # partition.start_sector = start sector in bytes

        tmp_part_file = tempfile.mkstemp(prefix="fdisk-")[1]
        with open(tmp_part_file, 'w') as fh:
            # Sort by partition number
            part_list.sort(partition_sort)
            number_parts = 1
            for part in part_list:
                # Pad the partition table for partitions that aren't there.
                # This is needed because of extended partitions
                while number_parts != int(part.name):
                    fh.write("0\t 0\t 0\t 0\t 0\t 0\t 0\t 0\t 0\t 0\n")
                    number_parts += 1
                fh.write("%s\t %d\t %lu\t %lu\t %lu\t %lu\t %lu\t %lu\t " \
                         "%lu\t %lu\n" % (part.part_type, part.bootid,
                         0, 0, 0, 0, 0, 0, part.start_sector,
                         part.size.sectors))
                number_parts += 1

        rdisk_dev = "/dev/rdsk/%sp0" % self.ctd
        cmd = [FDISK, "-n", "-F", tmp_part_file, rdisk_dev]
        if not dry_run:
            run(cmd)
        os.unlink(tmp_part_file)

        # Format the EFI system partition if necessary
        sys_part = next((part for part in part_list if part.is_efi_system),
            None)
        if sys_part is not None and sys_part.action == "create":
            sys_part.format_pcfs()

    def _update_gpt_struct(self, gpt_struct, gpart_list):
        """ gpt_struct must be already pre allocated an intialised with the
        correct number of partitions matching gpart_list by calling
        efi_init() prior to invocation of this method
        """

        # Populate GPT Partitions according to input from DOC
        for gpart in gpart_list:
            if gpart.is_unused:
                # Skip "Unused" partitions. efi_write() chokes on it. This
                # suggests the client didn't clean up target DOC cleanly.
                self.logger.warning('Ignoring invalid "Unused" type GPT ' \
                                    'partition: %s' % str(gpart))
                continue
            efi_part = gpt_struct.contents.efi_parts[int(gpart.name)]
            efi_part.p_start = gpart.start_sector
            efi_part.p_size = gpart.size.sectors
            efi_part.p_flag = gpart.flag
            efi_part.p_guid = gpart.guid
            if gpart.uguid is not None:
                efi_part.p_uguid = gpart.uguid
            # XXX
            # libefi will only create a GPT partition using the supplied GUID
            # if p_tag is set to the special value: 0xFF. Bugster CR: 7117104
            efi_part.p_tag = 0xFF

    def _update_gptpartition_table(self, gpart_list, dry_run):
        """ _update_gptpartition_table()
        method to initialise and write a DK_GPT structure with the desired
        partition information.
        """
        # check for a GPT label
        if self.label == "VTOC":
            self.logger.debug("Unable to change a VTOC labeled disk (%s)"
                              % self.ctd)
            return

        rdsk_dev = "/dev/rdsk/%ss0" % self.ctd
        max_gpart_num = -1
        # Find the highest numbered GPT partition. We have to account for
        # undefined partitions numbers for efi_init() and initialize
        # the DK_GPT structure with the highest numbered partition in order
        # to map partition name to partition number correctly
        for gpart in gpart_list:
            max_gpart_num = max(int(gpart.name), max_gpart_num)

        # gpart.name is zero based so increment by + 1 to get correct size
        num_gparts = max_gpart_num + 1
        if num_gparts <= 0:
            return

        # Scan gpart_list to check that all preserved partitions have the
        # unique GUID set. If they aren't we have to find them from libefi.
        # This will typically occur if the preserved partition is specified
        # in an AI manifest rather than copied over from target discovery by
        # the interactive installers.
        # Not preserving the uguid breaks UEFI boot of other operating
        # systems.
        no_uguid = next((p for p in gpart_list if \
                        p.action == "preserve" and p.uguid is None),
                        None)

        if not dry_run:
            fh = os.open(rdsk_dev, os.O_RDWR | os.O_NDELAY)
            try:
                if no_uguid:
                    try:
                        orig_gptp = efi.efi_read(fh)
                        orig_gpt = orig_gptp.contents
                        for gpart in gpart_list:
                            # Client is responsible for ensuring that a
                            # partition with action "preserve" represents an
                            # actual existing partition on the disk.
                            if gpart.action == "preserve":
                                index = int(gpart.name)
                                if index >= orig_gpt.efi_nparts:
                                    raise RuntimeError("GPT partition with " \
                                        "preserve action does not exist on " \
                                        "disk: %s\nPartition: %s" \
                                        % (gpart.parent.ctd, str(gpart)))

                                efi_part = orig_gpt.efi_parts[index]
                                gpart.uguid = copy.copy(efi_part.p_uguid)
                    finally:
                        efi.efi_free(orig_gptp)

                gptp = efi.efi_init(fh, num_gparts)
                try:
                    # Update the DK_GPT with the desired GPT Partition layout.
                    self._update_gpt_struct(gptp, gpart_list)
                    self.logger.debug("GPT layout for efi_write():")
                    self.logger.debug(_pretty_print_dk_gptp(gptp))
                    # Write the new DK_GPT struct out
                    efi.efi_write(fh, gptp)
                finally:
                    efi.efi_free(gptp)
            finally:
                os.close(fh)

            # Format the EFI system partition if necessary
            sys_part = next((gpe for gpe in gpart_list if gpe.is_efi_system),
                None)
            if sys_part is not None and sys_part.action == "create":
                sys_part.format_pcfs()

    def _update_vtoc_struct(self, vtoc_struct, slice_list, nsecs):
        """ _update_vtoc_struct() - method to update a vtoc_struct object with
        values from Slice objects from the DOC
        """

        # initialize a list of extpartition objects.  All slice attributes are
        # initialized to zero.
        base_structure = cstruct.extpartition()
        base_structure.p_tag = 0
        base_structure.p_flag = 0
        base_structure.p_start = 0
        base_structure.p_size = 0
        slices = [base_structure] * const.V_NUMPAR

        # Create slice 2 (BACKUP) - contains all available space.
        backup = cstruct.extpartition()
        backup.p_tag = const.V_BACKUP
        backup.p_flag = const.V_UNMNT
        backup.p_start = FIRST_CYL

        # On x86, slice 2 needs to be the size of the solaris2 partition.  For
        # SPARC, simply use the entire size of the disk.
        if self.kernel_arch == "x86":
            # find the solaris2 partition for this disk to set the size of the
            # backup slice
            for part in self.get_children(class_type=Partition):
                if part.is_solaris:
                    backup.p_size = part.size.sectors
        else:
            backup.p_size = self.geometry.ncyl * nsecs

        slices[2] = backup

        if self.kernel_arch == "x86":
            # Create slice 8 (BOOT) - allocates 1st cylinder
            boot = cstruct.extpartition()
            boot.p_tag = const.V_BOOT
            boot.p_flag = const.V_UNMNT
            boot.p_start = FIRST_CYL
            boot.p_size = BOOT_SLICE_RES_CYL * nsecs
            slices[8] = boot

        # Slices according to input from DOC
        for slc in slice_list:
            slc_data = cstruct.extpartition()
            slc_data.p_tag = slc.tag
            slc_data.p_flag = slc.flag
            slc_data.p_start = slc.start_sector
            slc_data.p_size = slc.size.sectors
            slices[int(slc.name)] = slc_data

        # update the v_part array of the extvtoc structure with the correctly
        # populated slice values
        vtoc_struct.contents.v_part = \
            (cstruct.extpartition * const.V_NUMPAR)(*slices)

    def _update_slices(self, slice_list, dry_run):
        """ _update_slices() _ method to read and (re)write an extvtoc
        structure with the desired slice information.
        """
        # check for a GPT label
        if self.label == "GPT":
            self.logger.debug("Unable to change the VTOC of a GPT labeled "
                              "disk (%s)" % self.ctd)
            return

        rdsk_dev = "/dev/rdsk/%ss2" % self.ctd
        num_slices = len(slice_list)
        if num_slices == 0:
            return

        nsects = self.geometry.nheads * self.geometry.nsectors

        # Read the original VTOC from the target.
        # Slices are recreated according to the attributes provided,
        # rest of the information is preserved.
        if not dry_run:
            fh = os.open(rdsk_dev, os.O_RDWR | os.O_NDELAY)
            extvtocp = extvtoc.read_extvtoc(fh)

            # Update the vtoc structure read from the disk with
            # the new slice layout that is desired.
            self._update_vtoc_struct(extvtocp, slice_list, nsects)

            # Write new vtoc out
            extvtoc.write_extvtoc(fh, extvtocp)

            os.close(fh)

    def force_vtoc(self):
        """ force_vtoc() - method to force a VTOC label onto a disk
        """
        cmd = [FORMAT, "-L", "vtoc", "-d", self.ctd]
        run(cmd)

    def force_efi(self):
        """ force_efi() - method to force an EFI/GPT label onto a disk
        """
        cmd = [FORMAT, "-L", "efi", "-d", self.ctd]
        run(cmd)

    def _set_vtoc_label_and_geometry(self, dry_run):
        """ _set_vtoc_label_and_geometry() - method to force a VTOC label and
        to set all of the disk geometery including dev_size
        """
        if not dry_run:
            # Create a new Manager object as a shared memory tool for the child
            # process to use
            manager = Manager()
            new_dma = manager.list()
            pid = os.fork()
            if pid == 0:
                # child process
                self.force_vtoc()
                dmd = diskmgt.descriptor_from_key(ldm_const.DRIVE, self.devid)
                drive = diskmgt.DMDrive(dmd.value)
                dma = drive.media.attributes
                new_dma.extend([dma.ncylinders, dma.nheads, dma.nsectors,
                                dma.blocksize])
                os._exit(0)
            else:
                # parent process.  Wait for the child to exit
                _none, status = os.wait()

            # pull the data from the child process out of the Manager and set
            # attributes.
            ncyl, nhead, nsect, blocksize = new_dma
            new_geometry = DiskGeometry(blocksize, nhead * nsect)
            new_geometry.ncyl = ncyl
            new_geometry.nheads = nhead
            new_geometry.nsectors = nsect
            self.geometry = new_geometry
            self.disk_prop.dev_size = Size(str(ncyl * nhead * nsect) +
                                           Size.sector_units)

            # update the label
            self.label = "VTOC"

    def _label_disk(self, dry_run):
        """ _label_disk() - method to label the disk with a VTOC label
        """
        cmd = [FORMAT, "-d", self.ctd]
        if not dry_run:
            self.logger.debug("Executing: %s" % " ".join(cmd))
            p = Popen(cmd, stdin=Popen.PIPE, stdout=Popen.PIPE,
                      stderr=Popen.PIPE)
            outs, errs = p.communicate("label\ny\nq\n")
            self.logger.debug("stdout: %s" % outs)
            self.logger.debug("stderr: %s" % errs)

    def name_matches(self, other):
        '''Returns True if 'other' Disk's name matches this Disk.'''
        if self.ctd is not None and other.ctd is not None:
            if self.ctd == other.ctd:
                return True
        if self.volid is not None and other.volid is not None:
            if self.volid == other.volid:
                return True
        if self.devpath is not None and other.devpath is not None:
            if self.devpath == other.devpath:
                return True
        if self.devid is not None and other.devid is not None:
            if self.devid == other.devid:
                return True
        if self.opath is not None and other.opath is not None:
            if self.opath == other.opath:
                return True
        if self.wwn is not None and other.wwn is not None:
            if self.wwn == other.wwn:
                return True
        if other.ctd in self.active_ctds:
            return True
        if self.receptacle is not None and other.receptacle is not None:
            if self.receptacle == other.receptacle:
                return True

        return False

    def is_boot_disk(self):
        '''Returns True if this Disk has the "boot_disk" keyword.'''
        if self.disk_keyword is not None and \
            self.disk_keyword.key == "boot_disk":
            return True

        return False

    @property
    def remaining_space(self):
        """ remaining_space() - instance property to return a Size object of
        the remaining overall space available on the Disk
        """
        return Size(str(self.disk_prop.dev_size.sectors - \
            sum([c.size.sectors for c in self._children])) + Size.sector_units)


class DiskGeometry(object):
    """ class definition for DiskGeometry objects
    """

    def __init__(self, blocksize=512, cylsize=512):
        self.blocksize = blocksize
        self.cylsize = cylsize
        self.efi = False
        self.ncyl = 0
        self.nheads = 0
        self.nsectors = 0


class DiskProp(object):
    """ class definition for DiskProp objects
    """

    def __init__(self):
        self.dev_type = None
        self.dev_vendor = None
        self.dev_chassis = None
        self.dev_size = None

    def prop_matches(self, other):
        """ Attempt to match disk_prop. Any of the properties
        dev_type/dev_vendor/dev_chassis/dev_size must been specified

        For comparrisons of dev_size, a match is found if the size of other's
        dev_size is smaller than this dev_size
        """
        for k in self.__dict__:
            # if both Disk objects have the attribute, compare them
            if getattr(self, k) is not None and getattr(other, k) is not None:
                # special case for dev_size.  other.dev_size must be smaller
                # than self.dev_size
                if k == "dev_size":
                    if self.dev_size < other.dev_size:
                        return False
                else:
                    if getattr(self, k).lower() != getattr(other, k).lower():
                        # the strings are not equal
                        return False

            # handle the case where self does not have the attribute set
            elif getattr(self, k) is None and getattr(other, k) is not None:
                return False

        return True


class DiskKeyword(object):
    """ class definition for DiskKeyword objects
    """

    def __init__(self):
        # this is the only key word so far. If others need to be added, this
        # class can be augmented
        self.key = "boot_disk"


class Iscsi(DataObject):
    """ class definition for Iscsi objects
    """

    def __init__(self, name):
        super(Iscsi, self).__init__(name)

        self.source = None
        self.target_name = None
        self.target_lun = None
        self.target_port = None
        self.target_ip = None

    def to_xml(self):
        element = etree.Element("iscsi")
        if self.source is not None:
            element.set("source", self.source)
        if self.target_name is not None:
            element.set("target_name", self.target_name)
        if self.target_lun is not None:
            element.set("target_lun", self.target_lun)
        if self.target_port is not None:
            element.set("target_port", self.target_port)
        if self.target_ip is not None:
            element.set("target_ip", self.target_ip)
        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'iscsi'

        otherwise return False
        """
        if element.tag != "iscsi":
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        source = element.get("source")
        target_name = element.get("target_name")
        target_lun = element.get("target_lun")
        target_port = element.get("target_port")
        target_ip = element.get("target_ip")

        iscsi = Iscsi("iscsi")
        if source == "dhcp":
            iscsi.source = source
        else:
            # ensure target_lun is not None
            if target_lun is None:
                raise ParsingError("Iscsi element must specify 'target_lun' "
                                   "attribute")
            else:
                iscsi.target_lun = target_lun

            # ensure target_ip is not None
            if target_ip is None:
                raise ParsingError("Iscsi element must specify 'target_ip' "
                                   "attribute")
            else:
                iscsi.target_ip = target_ip

            if target_name is not None:
                iscsi.target_name = target_name
            if target_port is not None:
                iscsi.target_port = target_port
        return iscsi

    def __repr__(self):
        s = ""
        if self.source is not None:
            s += "; source=%s" % self.source
        if self.target_name is not None:
            s += "; target_name=%s" % self.target_name
        if self.target_lun is not None:
            s += "; target_lun=%s" % self.target_lun
        if self.target_port is not None:
            s += "; target_port=%s" % self.target_port
        return s


def _pretty_print_dk_gptp(dk_gptp):
    dk_gpt = dk_gptp.contents
    s = "dk_gpt struct:\n"
    s += "--------------\n"
    s += "efi_version:   \t" + str(dk_gpt.efi_version) + '\n'
    s += "efi_nparts:    \t" + str(dk_gpt.efi_nparts) + '\n'
    s += "efi_part_size: \t" + str(dk_gpt.efi_part_size) + '\n'
    s += "efi_lbasize:   \t" + str(dk_gpt.efi_lbasize) + '\n'
    s += "efi_last_lba:  \t" + str(dk_gpt.efi_last_lba) + '\n'
    s += "efi_last_u_lba:\t" + str(dk_gpt.efi_last_u_lba) + '\n'
    s += "efi_disk_uguid:\t" + str(dk_gpt.efi_disk_uguid) + '\n'
    s += "efi_flags:     \t" + str(dk_gpt.efi_flags) + '\n'
    s += "efi_altern_lba:\t" + str(dk_gpt.efi_altern_lba) + '\n'
    s += '\n'

    for i in range(dk_gpt.efi_nparts):
        s += "efi_part #" + str(i) + ":\n"
        s += "\tp_start:\t" + str(dk_gpt.efi_parts[i].p_start) + '\n'
        s += "\tp_size: \t" + str(dk_gpt.efi_parts[i].p_size) + '\n'
        s += "\tp_guid: \t" + str(dk_gpt.efi_parts[i].p_guid) + '\n'
        s += "\tp_tag:  \t" + str(dk_gpt.efi_parts[i].p_tag) + '\n'
        s += "\tp_flag: \t" + str(dk_gpt.efi_parts[i].p_flag) + '\n'
        s += "\tp_name: \t" + str(dk_gpt.efi_parts[i].p_name) + '\n'
        s += "\tp_uguid:\t" + str(dk_gpt.efi_parts[i].p_uguid) + '\n'
    return s

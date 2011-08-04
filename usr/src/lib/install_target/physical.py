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

""" physical.py -- library containing class definitions for physical DOC
objects, including Partition, Slice and Disk.
"""
import gettext
import locale
import logging
import os
import platform
import tempfile

from multiprocessing import Manager

from lxml import etree

from solaris_install import Popen, run
from solaris_install.data_object import DataObject, ParsingError
from solaris_install.logger import INSTALL_LOGGER_NAME as ILN
from solaris_install.target.libadm import const, cstruct, extvtoc
from solaris_install.target.libdiskmgt import const as ldm_const
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.shadow.physical import LOGICAL_ADJUSTMENT, \
    ShadowPhysical
from solaris_install.target.size import Size

FDISK = "/usr/sbin/fdisk"
FORMAT = "/usr/sbin/format"
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


class Partition(DataObject):
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

    def resize(self, size, size_units=Size.gb_units, start_sector=None):
        """ resize() - method to resize a Partition object.

        start_sector is optional.  If not provided, use the existing
        start_sector.
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
            if size not in [0, 1]:
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
            if force.lower() == "true":
                slc.force = True
            elif force.lower() == "false":
                slc.force = False
            else:
                raise ParsingError("Slice element's force attribute must " +
                                   "be either 'true' or 'false'")

        if is_swap is not None:
            if is_swap.lower() == "true":
                slc.is_swap = True
            elif is_swap.lower() == "false":
                slc.is_swap = False
            else:
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

        # is the Disk a cdrom drive?
        self.iscdrom = False

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
        self.whole_disk = False

        # disk label
        self.label = None

        # write cache
        self.write_cache = False

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
            if whole_disk.lower() == "true":
                disk.whole_disk = True
            elif whole_disk.lower() == "false":
                disk.whole_disk = False
            else:
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
    def primary_partitions(self):
        partitions = self.get_children(class_type=Partition)
        return [part for part in partitions if part.is_primary]

    @property
    def logical_partitions(self):
        partitions = self.get_children(class_type=Partition)
        return [part for part in partitions if part.is_logical]

    def get_next_partition_name(self, primary=True):
        """ get_next_partition_name() - method to return the next available
        partition name as a string

        primary - boolean argument representing which kind of partition to
        check.  If True, only check primary partitions.  If False, check
        logical partitions
        """
        primary_set = set(range(1, const.FD_NUMPART + 1))
        logical_set = set(range(5, const.FD_NUMPART + const.MAX_EXT_PARTS + 1))

        if primary:
            available_set = primary_set - \
                set([int(p.name) for p in self.primary_partitions])
        else:
            available_set = logical_set - \
                set([int(p.name) for p in self.logical_partitions])

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
            except OSError as err:
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
        new_partition.size = Size(str(size) + str(size_units))
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

    def add_slice(self, index, start_sector, size, size_units=Size.gb_units,
                  in_zpool=None, in_vdev=None, force=False):
        """ add_slice() - method to create a Slice object and add it as a child
        of the Disk object
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

    def get_gaps(self):
        """ get_gaps() - method to return a list of Holey Objects
        (depending on architecture) available on the Disk.

        Backup slices (V_BACKUP) and logical partitions (if x86) are skipped.
        """
        # the Disk must have a disk_prop.dev_size attribute
        if not hasattr(self.disk_prop, "dev_size"):
            return list()

        if not self._children:
            # return a list of the size of the disk
            return[HoleyObject(0, self.disk_prop.dev_size)]

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
            # children), there's no gap, so skip it.  Also skip any hole which
            # is smaller than the cylinder boundary
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
        # sector does not fall on a cylinder boundary.
        final_list = list()
        for hole in holes:
            if hole.start_sector % self.geometry.cylsize != 0:
                # celing the start_sector to the next cylinder boundary
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
            # it to start at the first cylinder boundary instead
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

    def get_logical_partition_gaps(self):
        """ get_logical_parittion_gaps() - method to return a list of Holey
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
        s += "ctd=%s; volid=%s; devpath=%s; devid=%s" \
            % (self.ctd, self.volid, self.devpath, self.devid)

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

    def _update_vtoc_struct(self, vtoc_struct, slice_list, nsecs):

        # initialize a list of extpartition objects.  All slice attributes are
        # initialized to zero.
        base_structure = cstruct.extpartition()
        base_structure.p_tag = 0
        base_structure.p_flag = 0
        base_structure.p_start = 0
        base_structure.p_size = 0
        slices = [base_structure] * const.V_NUMPAR

        # Create slice 2 (BACKUP) - contains all available space.
        # XXX This is only valid for VTOC label and needs to be
        # addressed when adding support for GPT label.
        backup = cstruct.extpartition()
        backup.p_tag = const.V_BACKUP
        backup.p_flag = const.V_UNMNT
        backup.p_start = FIRST_CYL

        # On x86, slice 2 needs to be 3 cylinders smaller than the size of the
        # entire disk.  1 cylinder is used by the MBR and 2 cylinders are used
        # by the VTOC label itself.  There is no need to adjust SPARC sizes.
        if self.kernel_arch == "x86":
            backup.p_size = (self.geometry.ncyl - 3) * nsecs
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
        """ _label_disk() - method to label the disk.

        XXX:  GPT labels are not completely handled.  Need to revisit for later
        GPT work.
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
    def __init__(self, blocksize=512, cylsize=512):
        self.blocksize = blocksize
        self.cylsize = cylsize
        self.efi = False
        self.ncyl = 0
        self.nheads = 0
        self.nsectors = 0


class DiskProp(object):
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
    def __init__(self):
        # this is the only key word so far. If others need to be added, this
        # class can be augmented
        self.key = "boot_disk"


class Iscsi(DataObject):
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

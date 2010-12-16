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

import os

from lxml import etree

from solaris_install.data_object import DataObject, ParsingError
from solaris_install.target import zfs as zfs_lib

class Target(DataObject):
    def __init__(self, name):
        super(Target, self).__init__(name)

    def to_xml(self):
        return etree.Element("target")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "target":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return Target("target")


class TargetDevice(DataObject):
    def __init__(self, name):
        super(TargetDevice, self).__init__(name)

    def to_xml(self):
        return etree.Element("target_device")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "target_device":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return TargetDevice("target_device")
        

class Disk(DataObject):
    def __init__(self, name):
        super(Disk, self).__init__(name)
        self.disk_prop = None
        self.disk_keyword = None

        # store valid representations of the disk
        self.ctd = None
        self.volid = None
        self.devpath = None
        self.devid = None

    def to_xml(self):
        disk = etree.Element("disk")
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
        elif self.disk_prop is not None:
            disk_prop = etree.SubElement(disk, "disk_prop")
            if self.disk_prop.dev_type is not None:
                disk_prop.set("dev_type", self.disk_prop.dev_type)
            if self.disk_prop.dev_vendor is not None:
                disk_prop.set("dev_vendor", self.disk_prop.dev_vendor)
            if self.disk_prop.dev_size is not None:
                disk_prop.set("dev_size", self.disk_prop.dev_size)
        elif self.disk_keyword is not None:
            disk_keyword = etree.SubElement(disk, "disk_keyword")
            disk_keyword.set("key", self.disk_keyword.key)
        else:
            raise ParsingError("Disk identification missing")

        return disk

    @classmethod
    def can_handle(cls, element):
        if element.tag == "disk":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        disk = Disk("disk")

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
            else:
                raise ParsingError("No Disk identification provided")

        disk_prop = element.find("disk_prop")
        if disk_prop is not None:
            dp = DiskProp()
            dp.dev_type = disk_prop.get("dev_type")
            dp.dev_vendor = disk_prop.get("dev_vendor")
            dp.dev_size = disk_prop.get("dev_size")
            disk.disk_prop = dp

        disk_keyword = element.find("disk_keyword")
        if disk_keyword is not None:
            disk.disk_keyword = DiskKeyword()

        return disk


class DiskProp(object):
    def __init__(self):
        self.dev_type = None
        self.dev_vendor = None
        self.dev_size = None


class DiskKeyword(object):
    def __init__(self):
        # this is the only key word so far.  If others need to be added, this
        # class can be augmented
        self.key = "boot_disk"


class Vdev(DataObject):
    def __init__(self, name):
        super(Vdev, self).__init__(name)

        self.redundancy = "mirror"

    def to_xml(self):
        element = etree.Element("vdev")
        element.set("redundancy", self.redundancy)
        return element

    @classmethod
    def can_handle(cls, element):
        if element.tag == "vdev":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        redundancy = element.get("redundancy")
        vdev = Vdev("vdev")
        if redundancy is not None:
            vdev.redundancy = redundancy
        return vdev
        
        
class Dataset(DataObject):
    def __init__(self, name):
        super(Dataset, self).__init__(name)

    def to_xml(self):
        return etree.Element("dataset")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "dataset":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return Dataset("dataset")


class Slice(DataObject):
    def __init__(self, name):
        super(Slice, self).__init__(name)

        self.action = "create"
        self.is_root = None
        self.force = "false"

        self.index = None

        self.size = 0
        self.start_sector = 0

    def to_xml(self):
        slc = etree.Element("slice")
        slc.set("name", self.name)
        slc.set("action", self.action)
        if self.is_root is not None:
            slc.set("is_root", self.is_root)
        slc.set("force", self.force)

        size = etree.SubElement(slc, "size")
        size.set("size", str(self.size))
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
        slc = Slice(name)

        name = element.get("name")
        action = element.get("action")
        is_root = element.get("is_root")
        force = element.get("force")

        size = element.find("size")
        if size is not None:
            slc.size = int(size.get("val"))
            slc.start_sector = int(size.get("start_sector"))

        # slice is a python built-in class so use slice_obj
        slc.action = action
        if is_root is not None:
            slc.is_root = is_root
        slc.force = force
        return slc


class Partition(DataObject):
    def __init__(self, name):
        super(Partition, self).__init__(name)

        self.action = "create"
        self.part_type = "191"

        self.size = 0
        self.start_sector = 0

    def to_xml(self):
        partition = etree.Element("partition")
        partition.set("action", self.action)
        partition.set("name", self.name)
        if self.part_type is not None:
            partition.set("part_type", self.part_type)

        size = etree.SubElement(partition, "size")
        size.set("size", str(self.size))
        size.set("start_sector", str(self.start_sector))

        return partition

    @classmethod
    def can_handle(cls, element):
        if element.tag == "partition":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        partition = Partition(name)

        name = element.get("name")
        part_type = element.get("part_type")
        action = element.get("action")

        size = element.find("size")
        if size is not None:
            try:
                partition.size = int(size.get("val"))
            except:
                # catch any failure
                raise ParsingError("Size element has invalid 'val' attribute")

            try:
                partition.start_sector = int(size.get("start_sector"))
            except:
                # catch any failure
                raise ParsingError("Size element has invalid " + \
                                   "'start_sector' attribute")

        partition.action = action
        if part_type is not None:
            partition.part_type = part_type
        return partition


class Options(DataObject):
    def __init__(self, name):
        super(Options, self).__init__(name)

    def to_xml(self):
        return etree.Element("options")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "options":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return Options("options")


class Filesystem(DataObject):
    def __init__(self, name):
        super(Filesystem, self).__init__(name)

        self.dataset_path = None
        self.action = "create"
        self.mountpoint = None

    def to_xml(self):
        element = etree.Element("filesystem")
        element.set("name", self.dataset_path)
        element.set("action", self.action)
        if self.mountpoint is not None:
            element.set("mountpoint", self.mountpoint)
        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'filesystem'
        - a name attribute
        - an action attribute

        otherwise return False
        """
        if element.tag != "filesystem":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        dataset_path = element.get("name")
        action = element.get("action")
        mountpoint = element.get("mountpoint")

        filesystem = Filesystem("filesystem")
        filesystem.dataset_path = dataset_path
        filesystem.action = action
        if mountpoint is not None:
            filesystem.mountpoint = mountpoint
        else:
            # Recursively strip the dataset_path until the mountpoint is
            # found.
            stripped_entries = []
            dataset_list = dataset_path.split("/")
            while dataset_list:
                try:
                    test_dataset = zfs_lib.Dataset("/".join(dataset_list))
                    test_dataset_mp = getattr(test_dataset, "mountpoint")
                except AttributeError:
                    # strip off the last element and save it for later
                    stripped_entries.append(dataset_list[-1])
                    dataset_list = dataset_list[:-1]
                    continue
                else:
                    # the mountpoint was found so add the stripped entries
                    # (in reverse) to generate the proper path.
                    filesystem.mountpoint = os.path.join(test_dataset_mp,
                        "/".join(reversed(stripped_entries)))
                    break
            else:
                # set the mountpoint to None
                filesystem.mountpoint = None

        return filesystem


class Zpool(DataObject):
    def __init__(self, name):
        super(Zpool, self).__init__(name)

        self.action = "create"
        self.is_root = "false"
        self.mountpoint = None

    def to_xml(self):
        element = etree.Element("zpool")
        element.set("name", self.name)
        element.set("action", self.action)
        element.set("is_root", self.is_root)
        if self.mountpoint is not None:
            element.set("mountpoint", self.mountpoint)
        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'zpool'
        - a name attribute

        otherwise return False
        """
        if element.tag != "zpool":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        action = element.get("action")
        is_root = element.get("is_root")
        mountpoint = element.get("mountpoint")

        zpool = Zpool(name)
        if action is not None:
            zpool.action = action
        if is_root is not None:
            zpool.is_root = is_root
        if mountpoint is not None:
            zpool.mountpoint = mountpoint
        return zpool


class PoolOptions(DataObject):
    def __init__(self, name):
        super(PoolOptions, self).__init__(name)

    def to_xml(self):
        return etree.Element("pool_options")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "pool_options":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return PoolOptions("pool_options")

class DatasetOptions(DataObject):
    def __init__(self, name):
        super(DatasetOptions, self).__init__(name)

    def to_xml(self):
        return etree.Element("dataset_options")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "dataset_options":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return DatasetOptions("dataset_options")


class Zvol(DataObject):
    def __init__(self, name):
        super(Zvol, self).__init__(name)

        self.action = "create"

    def to_xml(self):
        element = etree.Element("zvol")
        element.set("name", self.name)
        element.set("action", self.action)
        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'zvol'
        - a name attribute
        - an action attribute

        otherwise return False
        """
        if element.tag != "zvol":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        action = element.get("action")

        zvol = Zvol(name)
        zvol.action = action
        return zvol


class Iscsi(DataObject):
    def __init__(self, name):
        super(Iscsi, self).__init__(name)

        self.source = None
        self.target_lun = None
        self.target_port = None

    def to_xml(self):
        element = etree.Element("iscsi")
        element.set("name", self.name)
        if self.source is not None:
            element.set("source", self.source)
        if self.target_lun is not None:
            element.set("target_lun", self.target_lun)
        if self.target_port is not None:
            element.set("target_port", self.target_port)
        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'iscsi'
        - a name attribute

        otherwise return False
        """
        if element.tag != "iscsi":
            return False
        if element.get("name") is None:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get("name")
        source = element.get("source")
        target_lun = element.get("target_lun")
        target_port = element.get("target_port")

        iscsi = Iscsi(name)
        if source is not None:
            iscsi.source = source
        if target_lun is not None:
            iscsi.target_lun = target_lun
        if target_port is not None:
            iscsi.target_port = target_port
        return iscsi


class IP(DataObject):
    def __init__(self, name):
        super(IP, self).__init__(name)

    def to_xml(self):
        return etree.Element("ip")

    @classmethod
    def can_handle(cls, element):
        if element.tag == "ip":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        # this element does not have any attributes or text
        return IP("ip")


class Swap(DataObject):
    def __init__(self, name):
        super(Swap, self).__init__(name)

        self.no_swap = "false"

    def to_xml(self):
        element = etree.Element("swap")
        element.set("no_swap", self.no_swap)

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'swap'

        otherwise return False
        """
        if element.tag != "swap":
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        no_swap = element.get("no_swap")

        swap = Swap("swap")
        if no_swap is not None:
            swap.no_swap = no_swap
        return swap


class Dump(DataObject):
    def __init__(self, name):
        super(Dump, self).__init__(name)

        self.no_dump = "false"

    def to_xml(self):
        element = etree.Element("dump")
        element.set("no_dump", self.no_dump)

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has:
        - the tag 'dump'

        otherwise return False
        """
        if element.tag != "dump":
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        no_dump = element.get("no_dump")

        dump = Dump("dump")
        if no_dump is not None:
            dump.no_dump = no_dump
        return dump

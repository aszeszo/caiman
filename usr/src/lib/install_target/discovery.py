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

""" discovery.py - target discovery checkpoint.  Attempts to find all target
devices on the given system.  The Data Object Cache is populated with the
information.
"""

import logging
import os.path
import platform
import re

import solaris_install.target.vdevs as vdevs

from bootmgmt.pysol import di_find_prop

from solaris_install import CalledProcessError, Popen, run
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.logger import INSTALL_LOGGER_NAME as ILN
from solaris_install.target import CRO_LABEL, Target
from solaris_install.target.libbe import be
from solaris_install.target.libdevinfo import devinfo
from solaris_install.target.libdiskmgt import const, diskmgt
from solaris_install.target.libdiskmgt.attributes import DMMediaAttr
from solaris_install.target.logical import BE, Filesystem, Logical, Zpool, Zvol
from solaris_install.target.physical import Disk, DiskProp, DiskGeometry, \
    DiskKeyword, Iscsi, Partition, Slice
from solaris_install.target.size import Size


CROINFO = "/usr/sbin/croinfo"
DEVFSADM = "/usr/sbin/devfsadm"
DHCPINFO = "/sbin/dhcpinfo"
EEPROM = "/usr/sbin/eeprom"
FSTYP = "/usr/sbin/fstyp"
ISCSIADM = "/usr/sbin/iscsiadm"
PRTVTOC = "/usr/sbin/prtvtoc"
SVCS = "/usr/bin/svcs"
SVCADM = "/usr/bin/svcadm"
ZFS = "/usr/sbin/zfs"
ZPOOL = "/usr/sbin/zpool"
ZVOL_PATH = "/dev/zvol/dsk"

DISK_SEARCH_NAME = "disk"
ZPOOL_SEARCH_NAME = "zpool"

# regex for matching c#t#d# OR c#d# strings
DISK_RE = "c\d+(?:t\d+)?d\d+"


class DiskLabelMissingError(Exception):
    """ Disk is unusable for install due to missing label
    """
    pass


class TargetDiscovery(Checkpoint):
    """ Discover all logical and physical devices on the system.
    """

    def __init__(self, name, search_name=None, search_type=None):
        super(TargetDiscovery, self).__init__(name)

        self.eng = InstallEngine.get_instance()
        self.doc = self.eng.data_object_cache

        # create a root node to insert all discovered objects into
        self.root = Target(Target.DISCOVERED)

        # user specified search criteria
        self.search_name = search_name
        self.search_type = search_type

        # list of discovered swap and dump zvols
        self.swap_list = list()
        self.dump_list = list()

        # eeprom diag mode and bootdisk value
        self.sparc_diag_mode = False
        self.bootdisk = None

        # kernel architecture
        self.arch = platform.processor()

        # croinfo dictionary
        self.cro_dict = dict()

    def is_bootdisk(self, name):
        """ is_bootdisk() -- simple method to compare the name of the disk in
        question with what libdevinfo reports as the bootdisk

        name - ctd name of the disk to check
        """
        # cache the answer so we don't do multiple lookups to libdevinfo
        if self.bootdisk is None:
            self.bootdisk = devinfo.get_curr_bootdisk()
        return self.bootdisk == name

    def get_progress_estimate(self):
        # XXX
        return 1

    def discover_disk(self, drive):
        """ discover_disk - method to discover a physical disk's attributes,
        partitions and slices

        drive - which physical drive to parse
        """
        # create a DOC object for this drive.  Set validate_children to False
        # so the shadow code doesn't adjust the start sector or size for any
        # children discovered
        new_disk = Disk("disk", validate_children=False)

        # extract drive attributes and media information
        drive_attributes = drive.attributes
        drive_media = drive.media

        # set attributes for the disk
        new_disk.ctd = drive.aliases[0].name
        new_disk.devid = drive.name
        new_disk.iscdrom = drive.cdrom
        new_disk.opath = drive_attributes.opath

        # if a drive is offline or down return None
        if drive_attributes.status == "DOWN":
            self.logger.debug("disk '%s' is offline" % new_disk.ctd)
            return None

        # set the devpath
        if os.path.islink(drive_attributes.opath):
            link = os.readlink(drive_attributes.opath)

            # clean up the link to get rid of the leading '../../devices/' and
            # trailing minor name
            if link.startswith("../../devices") and ":" in link:
                link = link.partition("../../devices")[2].rpartition(":")[0]
                new_disk.devpath = link

        # check for SPARC eeprom settings which would interfere with finding
        # the boot disk
        if self.arch == "sparc":
            if not self.sparc_diag_mode:
                # check eeprom settings
                cmd = [EEPROM, "diag-switch?"]
                p = run(cmd)
                diag_switch_value = p.stdout.partition("=")[2]
                if diag_switch_value.strip().lower() == "true":
                    # set a variable so we don't check every single disk and
                    # log a message
                    self.sparc_diag_mode = True
                    self.logger.info("Unable to determine bootdisk with " + \
                                     "diag-switch? eeprom setting set to " + \
                                     "'true'.  Please set diag-switch? " + \
                                     "to false and reboot the system")

        # check for the bootdisk
        if not self.sparc_diag_mode:
            if self.is_bootdisk(new_disk.ctd):
                new_disk.disk_keyword = DiskKeyword()

        # set vendor information for the drive
        new_disk.disk_prop = DiskProp()
        if drive.controllers:
            new_disk.disk_prop.dev_type = drive.controllers[0].attributes.type
        new_disk.disk_prop.dev_vendor = drive_attributes.vendor_id

        # set the alias and receptacle for disks, if possible
        if not new_disk.iscdrom and new_disk.ctd in self.cro_dict:
            new_disk.disk_prop.dev_chassis = self.cro_dict[new_disk.ctd][1]
            new_disk.receptacle = self.cro_dict[new_disk.ctd][2]

        # walk the media node to extract partitions and slices
        if drive_media is None:
            # since the drive has no media, we can't determine any attributes
            # about it (geometry, slices, partitions, etc.) so simply return
            # None
            return None
        else:
            # store the attributes locally so libdiskmgt doesn't have to keep
            # looking them up
            drive_media_attributes = drive_media.attributes

            # retrieve the drive's geometry
            new_disk = self.set_geometry(drive_media_attributes, new_disk)

            # keep a list of slices already visited so they're not discovered
            # again later
            visited_slices = []

            # if this system is x86 and the drive has slices but no fdisk
            # partitions, don't report any of the slices
            if self.arch == "i386" and drive_media.slices and not \
               drive_media.partitions:
                return new_disk

            for partition in drive_media.partitions:
                new_partition = self.discover_partition(partition,
                    drive_media_attributes.blocksize)

                # add the partition to the disk object
                new_disk.insert_children(new_partition)

                # check for slices associated with this partition.  If found,
                # add them as children
                for slc in partition.media.slices:
                    # discover the slice
                    new_slice = self.discover_slice(slc,
                        drive_media_attributes.blocksize)

                    # constrain when a slice is added to the DOC.  We only want
                    # to add a slice when:
                    # - the partition id is a Solaris partition (non EFI)
                    # - the fstyp is 'zfs' (for EFI labeled disks)
                    # - the fstyp is 'unknown_fstyp' AND it's slice 8 (for EFI
                    #   labeled disks)
                    if new_partition.is_solaris:
                        new_partition.insert_children(new_slice)
                    elif new_partition.part_type == 238:
                        # call fstyp to try to figure out the slice type
                        cmd = [FSTYP, slc.name]
                        p = run(cmd, check_result=Popen.ANY)
                        if p.returncode == 0:
                            if p.stdout.strip() == "zfs":
                                # add the slice since it's used by zfs
                                new_partition.insert_children(new_slice)
                        else:
                            if p.stderr.startswith("unknown_fstyp") and \
                                new_slice.name == "8":
                                # add the slice since it's an EFI boot slice
                                new_partition.insert_children(new_slice)

                    # keep a record this slice so it's not discovered again
                    visited_slices.append(slc.name)

            for slc in drive_media.slices:
                # discover the slice if it's not already been found
                if slc.name not in visited_slices:
                    new_slice = self.discover_slice(slc,
                        drive_media_attributes.blocksize)
                    new_disk.insert_children(new_slice)

            return new_disk

    def set_geometry(self, dma, new_disk):
        """ set_geometry() - method to set the geometry of the Disk DOC object
        from the libdiskmgt drive object.

        dma - the drive's media attributes as returned by libdiskmgt
        new_disk - Disk DOC object
        """
        new_geometry = None

        # If a disk is missing some basic attributes then it most likely has
        # no disk label.  This requires manual resolution to fix so raise
        # an error.
        if not DMMediaAttr.NACCESSIBLE in dma or \
           not DMMediaAttr.BLOCKSIZE in dma:
            raise DiskLabelMissingError("Disk %s appears to be missing a "
                "label and needs to be labelled manually." % new_disk.ctd)

        # If the disk has a GPT label (or no label), ncylinders will be
        # None
        if dma.ncylinders is None:
            new_disk.disk_prop.dev_size = Size(str(dma.naccessible) +
                                               Size.sector_units)

            # set only the blocksize (not the cylinder size)
            new_geometry = DiskGeometry(dma.blocksize, None)

            # set the label of the disk, if possible
            if dma.efi:
                new_disk.label = "GPT"
                new_geometry.efi = True
        else:
            new_disk.label = "VTOC"

            # set the disk's volid
            new_disk.volid = dma.label

            ncyl = dma.ncylinders
            nhead = dma.nheads
            nsect = dma.nsectors

            new_disk.disk_prop.dev_size = Size(str(ncyl * nhead * nsect) +
                                               Size.sector_units)
            new_geometry = DiskGeometry(dma.blocksize, nhead * nsect)
            new_geometry.ncyl = ncyl
            new_geometry.nheads = nhead
            new_geometry.nsectors = nsect
            new_disk.geometry = new_geometry

        return new_disk

    def discover_pseudo(self, controller):
        """ discover_psuedo - method to discover pseudo controller information,
        usually zvol swap and dump
        """
        for drive in controller.drives:
            for slc in drive.media.slices:
                stats = slc.use_stats
                if "used_by" in stats:
                    if stats["used_name"][0] == "dump":
                        if slc.name.startswith(ZVOL_PATH):
                            # remove the /dev/zvol/dsk from the path
                            self.dump_list.append(slc.name[14:])
                    if stats["used_name"][0] == "swap":
                        if slc.name.startswith(ZVOL_PATH):
                            # remove the /dev/zvol/dsk from the path
                            self.swap_list.append(slc.name[14:])

    def discover_partition(self, partition, blocksize):
        """ discover_partition - method to discover a physical disk's
        partition layout

        partition - partition object as discovered by ldm
        blocksize - blocksize of the disk
        """
        # store the attributes locally so libdiskmgt doesn't have to keep
        # looking them up
        partition_attributes = partition.attributes

        # partition name is ctdp path.  Split the string on "p"
        root_path, _none, index = partition.name.partition("p")

        # create a DOC object for this partition.  Set validate_children to
        # False so the shadow code doesn't adjust the start sector or size for
        # any children discovered
        new_partition = Partition(index, validate_children=False)
        new_partition.action = "preserve"
        new_partition.part_type = partition_attributes.id

        # check the partition's ID to set the partition type correctly
        if partition_attributes.id == \
            Partition.name_to_num("Solaris/Linux swap"):
            try:
                # try to call prtvtoc on slice 2.  If it succeeds, this is a
                # solaris1 partition.
                slice2 = root_path + "s2"
                cmd = [PRTVTOC, slice2]
                run(cmd, stdout=Popen.DEVNULL)
            except CalledProcessError:
                # the call to prtvtoc failed which means this partition is
                # Linux swap. To be sure, prtvtoc failure might also mean an
                # unlabeled Solaris1 partition but we aren't going to worry
                # about that for now. Displaying an unlabeled (and therefore
                # unused) Solaris1 partition should not have any unforeseen
                # consequences in terms of data loss.
                new_partition.is_linux_swap = True

        new_partition.size = Size(str(partition_attributes.nsectors) + \
                             Size.sector_units, blocksize=blocksize)
        new_partition.start_sector = long(partition_attributes.relsect)
        new_partition.size_in_sectors = partition_attributes.nsectors

        return new_partition

    def discover_slice(self, slc, blocksize):
        """ discover_slices - method to discover a physical disk's slice
        layout.

        slc - slice object as discovered by ldm
        blocksize - blocksize of the disk
        """
        # store the attributes locally so libdiskmgt doesn't have to keep
        # looking them up
        slc_attributes = slc.attributes

        new_slice = Slice(str(slc_attributes.index))
        new_slice.action = "preserve"
        new_slice.tag = slc_attributes.tag
        new_slice.flag = slc_attributes.flag
        new_slice.size = Size(str(slc_attributes.size) + Size.sector_units,
                              blocksize=blocksize)
        new_slice.start_sector = long(slc_attributes.start)
        new_slice.size_in_sectors = slc_attributes.size

        stats = slc.use_stats
        if "used_by" in stats:
            new_slice.in_use = stats

        return new_slice

    def discover_zpools(self, search_name=""):
        """ discover_zpools - method to walk zpool list output to create Zpool
        objects.  Returns a logical DOC object with all zpools populated.
        """
        # create a logical element
        logical = Logical("logical")

        # set noswap and nodump to True until a zvol is found otherwise
        logical.noswap = True
        logical.nodump = True

        # retreive the list of zpools
        cmd = [ZPOOL, "list", "-H", "-o", "name"]
        p = run(cmd)

        # Get the list of zpools
        zpool_list = p.stdout.splitlines()

        # walk the list and populate the DOC
        for zpool_name in zpool_list:
            # if the user has specified a specific search name, only run
            # discovery on that particular pool name
            if search_name and zpool_name != search_name:
                continue

            self.logger.debug("Populating DOC for zpool:  %s", zpool_name)

            # create a new Zpool DOC object and insert it
            zpool = Zpool(zpool_name)
            zpool.action = "preserve"
            logical.insert_children(zpool)

            # check to see if the zpool is the boot pool
            cmd = [ZPOOL, "list", "-H", "-o", "bootfs", zpool_name]
            p = run(cmd)
            if p.stdout.rstrip() != "-":
                zpool.is_root = True

            # get the mountpoint of the zpool
            cmd = [ZFS, "get", "-H", "-o", "value", "mountpoint", zpool_name]
            p = run(cmd)
            zpool.mountpoint = p.stdout.strip()

            # set the vdev_mapping on each physical object in the DOC tree for
            # this zpool
            self.set_vdev_map(zpool)

            # for each zpool, get all of its datasets
            cmd = [ZFS, "list", "-r", "-H", "-o",
                   "name,type,used,mountpoint", zpool_name]
            p = run(cmd)

            # walk each dataset and create the appropriate DOC objects for
            # each.  Skip the first line of list output, as the top level
            # dataset (also the dataset with the same name as that of the
            # zpool) may have a different mountpoint than the zpool.
            for dataset in p.stdout.rstrip().split("\n")[1:]:
                try:
                    name, ds_type, ds_size, mountpoint = dataset.split(None, 3)
                except ValueError as err:
                    # trap on ValueError so any inconsistencies are captured
                    self.logger.debug("Unable to process dataset: %r" %
                                      dataset)
                    self.logger.debug(str(err))
                    continue

                # fix the name field to remove the name of the pool
                name = name.partition(zpool_name + "/")[2]

                if ds_type == "filesystem":
                    obj = Filesystem(name)
                    obj.mountpoint = mountpoint
                elif ds_type == "volume":
                    obj = Zvol(name)
                    # the output from zfs list returns values like "37G" and
                    # "3.2M".  The Size() class expects "37GB" and "3.2MB".
                    obj.size = Size(ds_size + "B")

                    # check for swap/dump.  If there's a match, set the zvol
                    # 'use' attribute and the noswap/nodump attribute of
                    # logical.  The zpool name needs to be re-attached to the
                    # zvol name to match what was already parsed
                    if os.path.join(zpool_name, name) in self.swap_list:
                        obj.use = "swap"
                        logical.noswap = False
                    if os.path.join(zpool_name, name) in self.dump_list:
                        obj.use = "dump"
                        logical.nodump = False

                obj.action = "preserve"
                zpool.insert_children(obj)

        return logical

    def set_vdev_map(self, zpool):
        """ set_vdev_map() - walk the vdev_map to set the zpool's vdev entries
        and update existing physical DOC entries with the proper in_zpool and
        in_vdev attributes.

        zpool - zpool DOC object
        """
        # get the list of Disk DOC objects already inserted
        disklist = self.root.get_children(class_type=Disk)

        # get the vdev mappings for this pool
        vdev_map = vdevs._get_vdev_mapping(zpool.name)

        for vdev_type, vdev_entries in vdev_map.iteritems():
            in_vdev_label = "%s-%s" % (zpool.name, vdev_type)
            if vdev_type != "none":
                redundancy = vdev_type.partition("-")[0]
            else:
                redundancy = vdev_type

            # create a Vdev DOC entry for the vdev_type
            zpool.add_vdev(in_vdev_label, redundancy)

            for full_entry in vdev_entries:
                # remove the device path from the entry
                entry = full_entry.rpartition("/dev/dsk/")[2]

                # try to partition the entry for slices
                (vdev_ctd, vdev_letter, vdev_index) = entry.rpartition("s")

                # if the entry is not a slice, vdev_letter and index will
                # be empty strings
                if not vdev_letter:
                    # try to partition the entry for partitions
                    (vdev_ctd, vdev_letter, vdev_index) = \
                        entry.rpartition("p")

                    # if the entry is also not a partition skip this entry
                    if not vdev_letter:
                        continue

                # walk the disk list looking for a matching ctd
                for disk in disklist:
                    if hasattr(disk, "ctd"):
                        if disk.ctd == vdev_ctd:
                            # this disk is a match
                            if vdev_letter == "s":
                                child_list = disk.get_descendants(
                                    class_type=Slice)
                            elif vdev_letter == "p":
                                child_list = disk.get_descendants(
                                    class_type=Partition)

                            # walk the child list and look for a matching name
                            for child in child_list:
                                if child.name == vdev_index:
                                    # set the in_zpool and in_vdev attributes
                                    child.in_zpool = zpool.name
                                    child.in_vdev = in_vdev_label

                            # break out of the disklist walk
                            break

    def discover_BEs(self, zpool_name="", name=None):
        """ discover_BEs - method to discover all Boot Environments (BEs) on
        the system.
        """
        be_list = be.be_list(name)

        # walk each zpool already discovered and add BEs as necessary
        for zpool in self.root.get_descendants(class_type=Zpool):
            # check to see if we only want a subset of zpools.
            if zpool_name and zpool_name != zpool.name:
                continue

            for be_name, be_pool, root_ds, is_active in be_list:
                if be_pool == zpool.name:
                    zpool.insert_children(BE(be_name))

    def discover_entire_system(self, add_physical=True):
        """ discover_entire_system - populates the root node of the DOC tree
        with the entire physical layout of the system.

        add_physical - boolean value to signal if physical targets should be
        added to the DOC.
        """
        # to find all the drives on the system, first start with the
        # controllers
        for controller in diskmgt.descriptors_by_type(const.CONTROLLER):
            # trap on the "/pseudo" controller (zvol swap and dump)
            if controller.name == "/pseudo" and add_physical:
                self.discover_pseudo(controller)
            else:
                # extract every drive on the given controller
                for drive in controller.drives:
                    # skip USB floppy drives
                    if controller.attributes is not None and \
                       controller.attributes.type == const.CTYPE_USB:
                        try:
                            di_props = di_find_prop("compatible",
                                                    controller.name)
                        except Exception:
                            di_props = list()

                        if const.DI_FLOPPY in di_props:
                            self.logger.debug("skipping USB drive at: "
                                "%s" % new_disk.devpath)
                            continue

                    # query libdiskmgt for the drive's information
                    new_disk = self.discover_disk(drive)

                    # skip invalid drives and CDROM drives
                    if new_disk is None or new_disk.iscdrom:
                        continue

                    if add_physical:
                        self.root.insert_children(new_disk)

        # extract all of the devpaths from all of the drives already inserted
        devpath_list = [disk.devpath for disk in
                        self.root.get_descendants(class_type=Disk)]

        # now walk all the drives in the system to make sure we pick up any
        # disks which have no controller (OVM Xen disks)
        for drive in diskmgt.descriptors_by_type(const.DRIVE):
            new_disk = self.discover_disk(drive)

            # skip invalid drives and CDROM drives
            if new_disk is None or new_disk.iscdrom:
                continue

            # skip any disk we've already discovered
            if new_disk.devpath in devpath_list:
                continue

            if add_physical:
                self.root.insert_children(new_disk)

    def setup_iscsi(self):
        """ set up the iSCSI initiator appropriately (if specified)
        such that any physical/logical iSCSI devices can be discovered.
        """
        SVC = "svc:/network/iscsi/initiator:default"

        # verify iscsiadm is available
        if not os.path.exists(ISCSIADM):
            raise RuntimeError("iSCSI discovery enabled but %s does " \
                "not exist" % ISCSIADM)

        # ensure the iscsi/initiator service is online
        state_cmd = [SVCS, "-H", "-o", "STATE", SVC]
        p = run(state_cmd, check_result=Popen.ANY)
        if p.returncode != 0:
            # iscsi/initiator is not installed
            raise RuntimeError("%s not found - is it installed?" % SVC)

        # if the service is offline, enable it
        state = p.stdout.strip()
        if state == "offline":
            cmd = [SVCADM, "enable", "-s", SVC]
            run(cmd)

            # verify the service is now online
            p = run(state_cmd, check_result=Popen.ANY)
            state = p.stdout.strip()

            if state != "online":
                raise RuntimeError("Unable to start %s" % SVC)

        elif state != "online":
            # the service is in some other kind of state, so raise an error
            raise RuntimeError("%s requires manual servicing" % SVC)

        for iscsi in self.doc.get_descendants(class_type=Iscsi):
            # check iscsi.source for dhcp.  If set, query dhcpinfo for the
            # iSCSI boot parameters and set the rest of the Iscsi object
            # attributes
            if iscsi.source == "dhcp":
                p = run([DHCPINFO, "Rootpath"])

                # RFC 4173 defines the format of iSCSI boot parameters in DHCP
                # Rootpath as follows:
                # Rootpath=iscsi:<IP>:<protocol>:<port>:<LUN>:<target>
                iscsi_str = p.stdout.partition('=')[2]
                params = iscsi_str.split(':')
                iscsi.target_ip = params[1]
                iscsi.target_port = params[3]
                iscsi.target_lun = params[4]
                iscsi.target_name = params[5]

            if iscsi.target_name is not None:
                # set up static discovery of targets
                discovery_str = iscsi.target_name + "," + iscsi.target_ip
                if iscsi.target_port is not None:
                    discovery_str += ":" + iscsi.target_port
                cmd = [ISCSIADM, "add", "static-config", discovery_str]
                run(cmd)

                cmd = [ISCSIADM, "modify", "discovery", "--static", "enable"]
                run(cmd)

                iscsi_list_cmd = [ISCSIADM, "list", "target", "-S",
                                  discovery_str]
            else:
                # set up discovery of sendtargets targets
                discovery_str = iscsi.target_ip
                if iscsi.target_port is not None:
                    discovery_str += ":" + iscsi.target_port
                cmd = [ISCSIADM, "add", "discovery-address", discovery_str]
                run(cmd)

                cmd = [ISCSIADM, "modify", "discovery", "--sendtargets",
                       "enable"]
                run(cmd)

                iscsi_list_cmd = [ISCSIADM, "list", "target", "-S"]

            # run devfsadm and wait for the iscsi devices to configure
            run([DEVFSADM, "-i", "iscsi"])

            # list all the targets found
            iscsi_list = run(iscsi_list_cmd)

            # the output will look like:
            #
            # Target: <iqn string>
            #        Alias: -
            #        TPGT: 1
            #        ISID: 4000002a0000
            #        Connections: 1
            #        LUN: 1
            #             Vendor:  SUN     
            #             Product: COMSTAR         
            #             OS Device Name: <ctd>
            #        LUN: 0
            #             Vendor:  SUN     
            #             Product: COMSTAR         
            #             OS Device Name: <ctd>
            #
            # The LUN number and ctd strings are the only values we're
            # interested in.
            iscsi_dict = dict()

            # walk the output from iscsiadm list target to create a mapping
            # between ctd and LUN number.
            for line in iscsi_list.stdout.splitlines():
                line = line.lstrip()
                if line.startswith("LUN:"):
                    lun_num = line.split(": ")[1]
                if line.startswith("OS Device Name:") and lun_num is not None:
                    iscsi_ctd = line.rpartition("/")[2]
                    iscsi_dict[iscsi_ctd] = lun_num

                    # reset the lun_num for the next lun
                    lun_num = None

            # try to map iscsi_lun back to iscsi.target_lun
            for iscsi_ctd, iscsi_lun in iscsi_dict.items():
                if iscsi.target_lun is not None:
                    if iscsi.target_lun == iscsi_lun:
                        iscsi.parent.ctd = iscsi_ctd.partition("s2")[0]
                        break
                else:
                    iscsi.parent.ctd = iscsi_ctd.partition("s2")[0]
                    break
            else:
                raise RuntimeError("target_lun: %s not found on target"
                                   % iscsi.target_lun)

    def setup_croinfo(self):
        """ set up a DataObjectDict representing the output from
        /usr/sbin/croinfo
        """
        cmd = [CROINFO, "-h", "-O", "cAR"]
        p = run(cmd)

        # for systems that do not support CRO, nothing will be returned in
        # stdout so simply return.
        if not p.stdout:
            return

        # keep a positional counter since we can't use OrderedDicts until 2.7
        i = 1
        for line in p.stdout.splitlines():
            (ctd, alias, receptacle) = line.split(":")
            # skip any entries where the ctd is missing.
            if not ctd:
                continue

            self.cro_dict[ctd] = (i, alias or None, receptacle)
            i += 1

        if self.cro_dict:
            # Only insert if there is something in it
            self.doc.persistent.insert_children(
                DataObjectDict(CRO_LABEL, self.cro_dict,
                               generate_xml=True))

    def execute(self, dry_run=False):
        """ primary execution checkpoint for Target Discovery
        """
        # setup croinfo mappings
        self.setup_croinfo()

        # setup iSCSI so that all iSCSI physical and logical devices can be
        # discovered
        self.setup_iscsi()

        # check to see if the user specified a search_type
        if self.search_type == DISK_SEARCH_NAME:
            try:
                # check to see if the search name is either c#t#d# or c#d#
                if re.match(DISK_RE, self.search_name, re.I):
                    dmd = diskmgt.descriptor_from_key(const.ALIAS,
                                                      self.search_name)
                    alias = diskmgt.DMAlias(dmd.value)
                    drive = alias.drive
                else:
                    dmd = diskmgt.descriptor_from_key(const.DRIVE,
                                                      self.search_name)
                    drive = diskmgt.DMDrive(dmd.value)
            except OSError as err:
                raise RuntimeError("Unable to look up %s - %s" % \
                    (self.search_name, err))

            # insert the drive information into the tree
            new_disk = self.discover_disk(drive)
            if new_disk is not None:
                self.root.insert_children(new_disk)

        elif self.search_type == ZPOOL_SEARCH_NAME:
            self.discover_entire_system(add_physical=False)
            self.root.insert_children(self.discover_zpools(
                self.search_name))

            # Add all Boot Environments that are contained in this zpool
            self.discover_BEs(self.search_name)

        else:
            self.discover_entire_system()

            # Add the discovered zpool objects
            self.root.insert_children(self.discover_zpools())

            # Add all Boot Environments
            self.discover_BEs()

        # Add the root node to the DOC
        self.doc.persistent.insert_children(self.root)

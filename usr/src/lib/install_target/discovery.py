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

""" discovery.py - target discovery checkpoint.  Attempts to find all target
devices on the given system.  The Data Object Cache is populated with the
information.
"""

import copy
import optparse
import os
import platform
import re
import sys
import tempfile

import solaris_install.target.vdevs as vdevs

from bootmgmt.pysol import getmntany, mnttab_open, mnttab_close

from solaris_install import CalledProcessError, Popen, run
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.target import CRO_LABEL, Target
from solaris_install.target.libbe import be
from solaris_install.target.libdevinfo import devinfo
from solaris_install.target.libdiskmgt import const, diskmgt
from solaris_install.target.libefi.efi import efi_free, efi_read
from solaris_install.target.logical import BE, Filesystem, Logical, Zpool, Zvol
from solaris_install.target.physical import Disk, DiskProp, DiskGeometry, \
    DiskKeyword, Iscsi, GPTPartition, Partition, Slice
from solaris_install.target.size import Size


CROINFO = "/usr/sbin/croinfo"
DEVFSADM = "/usr/sbin/devfsadm"
DHCPINFO = "/sbin/dhcpinfo"
DLADM = "/usr/sbin/dladm"
EEPROM = "/usr/sbin/eeprom"
FSTYP = "/usr/sbin/fstyp"
ISCSIADM = "/usr/sbin/iscsiadm"
PCFSMOUNT = "/usr/lib/fs/pcfs/mount"
PRTVTOC = "/usr/sbin/prtvtoc"
SVCS = "/usr/bin/svcs"
SVCADM = "/usr/sbin/svcadm"
UMOUNT = "/usr/sbin/umount"
ZFS = "/usr/sbin/zfs"
ZPOOL = "/usr/sbin/zpool"
ZVOL_PATH = "/dev/zvol/dsk"
ZVOL_RPATH = "/dev/zvol/rdsk"

DISK_SEARCH_NAME = "disk"
ZPOOL_SEARCH_NAME = "zpool"

# regex for matching c#t#d# OR c#d# strings.  Use \w rather than \d for the
# "t" to allow matching of WWNs
DISK_RE = "c\d+(?:t\w+)?d\d+"


def retrieve_drive(name):
    """ function to return a drive object based on a specific name
    """

    try:
        # check to see if the search name is either c#t#d# or c#d#
        if re.match(DISK_RE, name, re.I):
            dmd = diskmgt.descriptor_from_key(const.ALIAS, name)
            alias = diskmgt.DMAlias(dmd.value)
            drive = alias.drive
        else:
            dmd = diskmgt.descriptor_from_key(const.DRIVE, name)
            drive = diskmgt.DMDrive(dmd.value)
    except (KeyError, OSError) as err:
        raise RuntimeError("Unable to look up %s - %s" % (name, err))

    return drive


class TargetDiscovery(Checkpoint):
    """ Discover all logical and physical devices on the system.
    """

    def __init__(self, name, search_name=None, search_type=None):
        super(TargetDiscovery, self).__init__(name)

        self.dry_run = False

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

        # if a drive is offline or down return None
        if drive_attributes.status == "DOWN":
            self.logger.debug("disk '%s' is offline" % new_disk.name)
            return None

        # set the wwn string, including lun if available
        wwn = getattr(drive.aliases[0].attributes, "wwn", None)
        if wwn is not None:
            lun = getattr(drive.aliases[0].attributes, "lun", None)
            if lun is not None:
                new_disk.wwn = "%s,%d" % (wwn, lun)
            else:
                new_disk.wwn = wwn

        for alias in drive.aliases:
            if drive_media is not None:
                if self.verify_disk_read(alias.name,
                                         drive_media.attributes.blocksize):
                    new_disk.active_ctds.append(alias.name)
                else:
                    new_disk.passive_ctds.append(alias.name)

        # set the new_disk ctd string
        if new_disk.wwn is None:
            # use the only alias name
            new_disk.ctd = drive.aliases[0].name
        else:
            # use the first active ctd
            new_disk.ctd = new_disk.active_ctds[0]

        new_disk.devid = drive.name
        new_disk.iscdrom = drive.cdrom
        new_disk.opath = drive_attributes.opath

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

            # check for any Iscsi object in the DOC.  If found, change the
            # dev_type from 'scsi' to 'iSCSI' to allow the installers finer
            # granularity when choosing these types of LUNs
            iscsi_check = self.doc.get_descendants(class_type=Iscsi)
            if iscsi_check:
                cmd = [ISCSIADM, "list", "target", "-S"]
                p = run(cmd)
                if new_disk.ctd in p.stdout:
                    new_disk.disk_prop.dev_type = "iSCSI"

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

            # if this system is x86 and the drive reports *VTOC* slices but no
            # fdisk partitions, don't report any of the slices. This probably
            # means there is no label at all on the disk:
            # On x86 libdiskmgmt will report slices, but no partitions
            # when the disk has no partition table/label at all.
            if self.arch == "i386" \
                and drive_media.slices \
                and not drive_media.partitions \
                and new_disk.label != "GPT":
                # Unset the erroneous disk label
                new_disk._label = None
                return new_disk

            if new_disk.label == "VTOC":
                for partition in drive_media.partitions:
                    new_partition = self.discover_partition(partition,
                        drive_media_attributes.blocksize)

                    # add the partition to the disk object
                    new_disk.insert_children(new_partition)

                    # check for slices associated with this partition
                    # if found, add them as children
                    for slc in partition.media.slices:
                        # discover the slice
                        new_slice = self.discover_slice(slc,
                            drive_media_attributes.blocksize)

                        # constrain when a slice is added to the DOC.
                        # We only want to add a slice when the partition id
                        # is a Solaris partition (non EFI)
                        if new_partition.is_solaris:
                            new_partition.insert_children(new_slice)

                        # keep a record this slice so it's not discovered again
                        visited_slices.append(slc.name)

                for slc in drive_media.slices:
                    # discover the slice if it's not already been found
                    if slc.name not in visited_slices:
                        new_slice = self.discover_slice(slc,
                            drive_media_attributes.blocksize)
                        new_disk.insert_children(new_slice)

            # If the disk has a GPT label then the protective MBR
            # reported by libdiskmgt should be ignored. The GPT partitions
            # are reported by libdiskmgt as "slices", similar to VTOC slices
            elif new_disk.label == "GPT":
                # EFI/GPT label on disc. Discover GPT partitions.
                # libdiskmgt's information about GPT partitions is incomplete
                # so use libefi to fill in what is missing.
                fh = os.open(new_disk.opath, os.O_RDONLY | os.O_NDELAY)
                try:
                    gptp = efi_read(fh)
                    try:
                        for slc in drive_media.slices:
                            efi_part = gptp.contents.efi_parts[
                                slc.attributes.index]
                            new_gpart = self.discover_gptpartition(slc,
                                drive_media_attributes.blocksize,
                                efi_part)
                            new_disk.insert_children(new_gpart)
                    finally:
                        efi_free(gptp)
                finally:
                    os.close(fh)

            return new_disk

    def verify_disk_read(self, ctd, blocksize):
        """
        verify_disk_read() - method to verify a low-level read from the raw ctd
        path.
        """

        raw = "/dev/rdsk/%s" % ctd
        raw2 = raw + "s2"
        # Depending on the label used, we need to check both the raw device and
        # slice 2 to see if the disk can be read.
        for raw_disk in [raw, raw2]:
            fd = None
            try:
                try:
                    fd = os.open(raw_disk, os.O_RDONLY | os.O_NDELAY)
                    try:
                        _none = os.read(fd, blocksize)
                    except OSError:
                        # the read() call failed
                        continue
                    else:
                        return True
                except OSError:
                    # the open() call failed
                    continue
            finally:
                if fd is not None:
                    os.close(fd)
        return False

    def set_geometry(self, dma, new_disk):
        """ set_geometry() - method to set the geometry of the Disk DOC object
        from the libdiskmgt drive object.

        dma - the drive's media attributes as returned by libdiskmgt
        new_disk - Disk DOC object
        """
        new_geometry = None

        # If the disk has a GPT label (or no label), ncylinders will be
        # None
        if dma.ncylinders is None:
            # XXX - libdiskmgt calculation of DM_NACCESSIBLE for GPT disks
            # is broken, so we use DM_SIZE since we can access all blocks on
            # the disk anyway because we don't need to worry about VTOC
            # imposed cylinder alignment on disk size.
            # Bugster CR: 7099417
            new_disk.disk_prop.dev_size = Size(str(dma.size) +
                                               Size.sector_units,
                                               dma.blocksize)

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
            new_disk.disk_prop.dev_size = Size(str(dma.naccessible) +
                                               Size.sector_units,
                                               dma.blocksize)
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

        # If the partition is an EFI system partition check to see if it
        # is PCFS formatted. We only do this on EFI system partitions to save
        # time since mounting can be slow.
        if new_partition.is_efi_system:
            ctdp = partition.name.rsplit('/', 1)[-1]
            new_partition._is_pcfs_formatted = self.is_pcfs_formatted(ctdp)

        return new_partition

    def discover_gptpartition(self, partition, blocksize, efipart):
        """ discover_gptpartition - method to discover a physical disk's GPT
        partition layout.

        # Note that libdiskmgmt terminology treats GPT partitions as slices
        # as does the Solaris cXtYdZsN notation
        # We shall refer to them as GPT partitions though, like the rest of
        # the world does.
        partition - object as discovered by ldm
        blocksize - blocksize of the disk
        efipart - DK_PART EFI cstruct
        """
        # store the attributes locally so libdiskmgt doesn't have to keep
        # looking them up
        gpart_attributes = partition.attributes

        new_gpart = GPTPartition(str(gpart_attributes.index))
        new_gpart.action = "preserve"
        new_gpart.size = Size(str(gpart_attributes.size) + Size.sector_units,
                              blocksize=blocksize)
        new_gpart.start_sector = long(gpart_attributes.start)
        new_gpart.size_in_sectors = gpart_attributes.size

        stats = partition.use_stats
        if "used_by" in stats:
            new_gpart.in_use = stats

        # EFI partition type GUID and p_flag not provided by libdiskmgt.  Fall
        # back on libefi provided DK_PART data.
        new_gpart.part_type = '{%s}' % str(efipart.p_guid)
        new_gpart.guid = copy.copy(efipart.p_guid)
        new_gpart.uguid = copy.copy(efipart.p_uguid)
        new_gpart.flag = efipart.p_flag

        # If the partition is an EFI system partition check to see if it
        # is PCFS formatted. We only do this on EFI system partition to save
        # time since mounting can be slow.
        if new_gpart.is_efi_system:
            ctds = partition.name.rsplit('/', 1)[-1]
            new_gpart._is_pcfs_formatted = self.is_pcfs_formatted(ctds)

        return new_gpart

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

            # for each zpool, get all of its datasets.  Switch to the C locale
            # so we don't have issues with LC_NUMERIC settings
            cmd = [ZFS, "list", "-r", "-H", "-o",
                   "name,type,used,mountpoint", zpool_name]
            p = run(cmd, env={"LC_ALL": "C"})

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
                    obj.size = Size(ds_size)

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

                # try to partition the entry for GPT partitions and
                # VTOC slices.
                # Both are identified by the letter "s" preceding the index.
                (vdev_ctd, vdev_letter, vdev_index) = entry.rpartition("s")

                # if the entry is not a GPT partition or VTOC slice,
                # vdev_letter and index will be empty strings
                if not vdev_letter:
                    # try to partition the entry for MBR partitions
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
                                if disk.label == "VTOC":
                                    child_list = disk.get_descendants(
                                        class_type=Slice)
                                elif disk.label == "GPT":
                                    child_list = disk.get_descendants(
                                        class_type=GPTPartition)
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
            # skip USB floppy controllers
            if controller.floppy_controller:
                continue

            # trap on the "/pseudo" controller (zvol swap and dump)
            if controller.name == "/pseudo" and add_physical:
                self.discover_pseudo(controller)
            else:
                # extract every drive on the given controller
                for drive in controller.drives:
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
        self.logger.debug("Adding drives without controllers to the DOC")
        for drive in diskmgt.descriptors_by_type(const.DRIVE):
            # skip drives that have controllers.  They would have already been
            # discovered above.
            if drive.controllers:
                continue

            # skip any drive whose opath starts with "/dev/zvol/rdsk"
            if drive.attributes.opath.startswith(ZVOL_RPATH):
                continue

            new_disk = self.discover_disk(drive)

            # skip invalid drives and CDROM drives
            if new_disk is None or new_disk.iscdrom or new_disk.ctd == "dump":
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

        # pull out all of the iscsi entries from the DOC
        iscsi_list = self.doc.get_descendants(class_type=Iscsi)

        # if there's nothing to do, simply return
        if not iscsi_list:
            return

        # check each entry in the iscsi_list.  If any of them do not have a ctd
        # value already, set up the mapping to the LUN.
        for iscsi in iscsi_list:
            if not iscsi.ctd_list:
                # attempt to connect to the target
                try:
                    iscsi.setup_iscsi()
                except (CalledProcessError, RuntimeError):
                    # remove the iSCSI configuration since it's invalid
                    iscsi.teardown()
                    raise

            # map the iSCSI object back to its parent Disk object for AI.
            if isinstance(iscsi.parent, Disk):
                iscsi.parent.ctd = iscsi.ctd_list[0]

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
        self.dry_run = dry_run

        # look to see if the persistent tree already has a DISCOVERED Target
        # node.
        discovered = \
            self.doc.persistent.get_descendants(name=Target.DISCOVERED)

        if discovered:
            # target discovery has already run once.  Before continuing to run
            # it again, force libdiskmgt to rebuild its cache.
            self.logger.debug("Found existing Target.DISCOVERED object.  "
                              "Forcing libdiskmgt to refresh its cache.")
            diskmgt.cache_update()

        # setup croinfo mappings
        self.setup_croinfo()

        # setup iSCSI so that all iSCSI physical and logical devices can be
        # discovered
        self.setup_iscsi()

        # check to see if the user specified a search_type
        if self.search_type == DISK_SEARCH_NAME:
            if isinstance(self.search_name, list):
                for name in self.search_name:
                    drive = retrieve_drive(name)
                    new_disk = self.discover_disk(drive)
                    if new_disk is not None:
                        self.root.insert_children(new_disk)
            else:
                drive = retrieve_drive(self.search_name)
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

        # If this is the first run of discovery, simply insert the entire root
        if not discovered:
            self.doc.persistent.insert_children(self.root)
        else:
            # take the first (and only) entry in the list and add each new
            # child object to the existing discovered tree
            discovered = discovered[0]
            for child in self.root.children:
                discovered.insert_children(child)

    def is_pcfs_formatted(self, ctdn):
        """ is_pcfs_formatted() Return a Boolean value of True if the GPT
        partition guid is already formatted with a pcfs filesystem.

        This test is useful in conjuction with the is_efi_system property to
        determine if an existing EFI system partition  can be reused to store
        the Solaris UEFI boot program. If False, a format using mkfs on the
        partition would be required.
        """

        dev_dsk = "/dev/dsk/%s" % ctdn
        if os.path.exists(dev_dsk) is False:
            raise RuntimeError("No such block device exists: %s" % dev_dsk)

        # Check to see if it's mounted first. If it is we can look at the
        # fstype it is mounted with.
        mntmatch = None
        try:
            mnttab_open()
            mntmatch = getmntany(mnt_special=dev_dsk)
        finally:
            mnttab_close()

        # Mounted
        if mntmatch is not None:
            if mntmatch.get('mnt_fstype') == 'pcfs':
                return True
            else:
                return False
        # Not mounted
        else:
            # Try to mount with pcfs. This is a much more robust and reliable
            # check that the ESP is usable than simply checking with
            # fstyp(1M)
            mount_point = tempfile.mkdtemp(dir="/system/volatile",
                                           prefix="esp_%s_" % (ctdn))
            try:
                mount_cmd = [PCFSMOUNT, dev_dsk, mount_point]
                run(mount_cmd)
                umount_cmd = [UMOUNT, dev_dsk]
                run(umount_cmd)
                return True
            except CalledProcessError:
                return False
            finally:
                os.rmdir(mount_point)
            return False

if __name__ == "__main__":
    # if discovery.py is run from the command line, rather than imported as a
    # checkpoint, run discovery and print the output.
    def parse_args():
        """ parse_args() - function to parse the command line arguments
        """
        parser = optparse.OptionParser()
        parser.add_option("-d", "--disk", dest="disk", action="store_true",
                          help="print disk information")
        parser.add_option("-g", "--gptpartition", dest="gptpartition",
                          action="store_true",
                          help="print GPT partition information")
        parser.add_option("-p", "--partition", dest="partition",
                          action="store_true",
                          help="print partition information")
        parser.add_option("-s", "--slice", dest="slc", action="store_true",
                          help="print slice information")
        parser.add_option("-z", "--zpool", dest="zpool", action="store_true",
                          help="print zpool information")
        parser.add_option("--libdiskmgt", dest="libdiskmgt",
                          action="store_true",
                          help="print all output from libdiskmgt")
        parser.add_option("--xml", dest="xml", action="store_true",
                          help="print DOC xml")
        options, args = parser.parse_args()

        # only run target discovery if the user requests something out of the
        # DOC.  If only libdiskmgt output is requested, do not run target
        # discovery.
        if options.disk or options.partition or options.slc or \
           options.zpool or options.xml:
            options.require_td = True
        else:
            options.require_td = False

        return options, args

    def print_disk(doc):
        """ prints the output from the -d argument
        """
        print "Disk discovery"
        # walk the DOC and print only what the user requested
        target = doc.persistent.get_children(class_type=Target)[0]
        disk_list = target.get_children(class_type=Disk)
        header_format = "%15s | %15s | %15s |"
        entry_format = "%15s | %15s | %15.3f |"
        print "Total number of disks:  %d" % len(disk_list)
        print '-' * 53
        print header_format % ("name", "boot disk?", "size [GB]")
        print '-' * 53
        for disk in disk_list:
            if disk.disk_keyword is not None and \
               disk.disk_keyword.key == "boot_disk":
                boot = "yes"
            else:
                boot = "no"
            print entry_format % (disk.ctd, boot, \
                                  disk.disk_prop.dev_size.get(Size.gb_units))
        print '-' * 53

    def print_gptpartition(doc):
        """ prints the output from the -g argument
        """
        print "GPT partition discovery"
        # walk the DOC and print only what the user requested
        target = doc.persistent.get_children(class_type=Target)[0]
        disk_list = target.get_children(class_type=Disk)

        header_format = "{0:>15} | {1:>5} | {2:>40} |"
        disk_format = "{0:>15} |" + 7 * " " + "|" + 42 * " " + "|"
        entry_format = " " * 16 + "| {0:>5} | {1:>40} |"

        disk_line = '-' * 67
        entry_line = disk_line + "|"

        print disk_line
        print header_format.format(*["disk name", "index", "in use?"])
        print entry_line
        for disk in disk_list:
            print disk_format.format(disk.ctd)
            gpart_list = disk.get_descendants(class_type=GPTPartition)
            for gpart in gpart_list:
                if gpart.in_use is None:
                    in_use = "no"
                else:
                    if "used_by" in gpart.in_use:
                        in_use = "used by:  %s" % gpart.in_use["used_by"][0]
                        if "used_name" in gpart.in_use:
                            in_use += " (%s)" % gpart.in_use["used_name"][0]
                print entry_format.format(*[gpart.name, in_use])
            print entry_line

    def print_partition(doc):
        """ prints the output from the -p argument
        """
        print "Partition discovery"
        # walk the DOC and print only what the user requested
        target = doc.persistent.get_children(class_type=Target)[0]
        disk_list = target.get_children(class_type=Disk)
        header_format = "{0:>15} | {1:>5} | {2:>7} | {3:>5} | {4:>11} |"
        disk_format = "{0:>15} |" + 39 * " " + "|"
        line_format = " " * 16 + "| {0:>5} | {1:>7} | {2:>5} | {3:>11} |"

        entry_line = '-' * 57

        print entry_line
        print header_format.format(*["disk_name", "index", "active?", "ID",
                                   "Linux Swap?"])
        print entry_line
        for disk in disk_list:
            print disk_format.format(disk.ctd)
            partition_list = disk.get_children(class_type=Partition)
            for partition in partition_list:
                if partition.bootid == Partition.ACTIVE:
                    active = "yes"
                else:
                    active = "no"

                if partition.is_linux_swap:
                    linux_swap = "yes"
                else:
                    linux_swap = "no"
                print line_format.format(*[partition.name.split("/")[-1],
                                         active, partition.part_type,
                                         linux_swap])
            print entry_line

    def print_slice(doc):
        """ prints the output from the -s argument
        """
        print "Slice discovery"
        # walk the DOC and print only what the user requested
        target = doc.persistent.get_children(class_type=Target)[0]
        disk_list = target.get_children(class_type=Disk)

        header_format = "{0:>15} | {1:>5} | {2:>40} |"
        disk_format = "{0:>15} |" + 7 * " " + "|" + 42 * " " + "|"
        entry_format = " " * 16 + "| {0:>5} | {1:>40} |"

        disk_line = '-' * 67
        entry_line = disk_line + "|"

        print disk_line
        print header_format.format(*["disk name", "index", "in use?"])
        print entry_line
        for disk in disk_list:
            print disk_format.format(disk.ctd)
            slice_list = disk.get_descendants(class_type=Slice)
            for slc in slice_list:
                if slc.in_use is None:
                    in_use = "no"
                else:
                    if "used_by" in slc.in_use:
                        in_use = "used by:  %s" % slc.in_use["used_by"][0]
                        if "used_name" in slc.in_use:
                            in_use += " (%s)" % slc.in_use["used_name"][0]
                print entry_format.format(*[slc.name, in_use])
            print entry_line

    def print_zpool(doc):
        """ prints the output from the -z argument
        """
        print "Zpool discovery"
        target = doc.persistent.get_children(class_type=Target)[0]
        logical = target.get_children(class_type=Logical)[0]
        zpool_list = logical.get_children(class_type=Zpool)

        print_format = "{0:>10} | {1:>20} | {2:>20} | {3:>7} | {4:>8} |"

        zpool_line = '-' * 79

        print zpool_line
        print print_format.format(*["name", "bootfs", "guid", "size",
                                    "capacity"])
        print zpool_line
        for zpool in zpool_list:
            # extract zpool information
            cmd = ["/usr/sbin/zpool", "get", "bootfs,guid,size,capacity",
                   zpool.name]
            p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
            # strip out just the third column.  Exclude the header row and
            # trailing newline
            (bootfs, guid, size, capacity) = \
                [line.split()[2] for line in p.stdout.split("\n")[1:-1]]
            print print_format.format(*[zpool.name, bootfs, guid, size,
                                        capacity])
        print zpool_line

    def print_libdiskmgt():
        """ prints drive information from the --libdiskmgt argument
        """

        def indent_str(level, string):
            """ function to print an indented string
            """
            return "\n".join(
                ["    " * level + line for line in string.splitlines()]
            )

        # start at the bus level
        indent = 0
        for bus in diskmgt.descriptors_by_type(const.BUS):
            print indent_str(indent, str(bus))
            indent += 1
            for controller in bus.controllers:
                print indent_str(indent, str(controller))
                indent += 1
                for path in controller.paths:
                    print indent_str(indent, str(path))
                for drive in controller.drives:
                    print indent_str(indent, str(drive))
                    indent += 1
                    for path in drive.paths:
                        print indent_str(indent, str(path))
                    for alias in drive.aliases:
                        print indent_str(indent, str(alias))

                    media = drive.media
                    if media is not None:
                        print indent_str(indent, str(media))
                        dma = media.attributes
                        indent += 1
                        if dma.efi or dma.fdisk:
                            for part in media.partitions:
                                print indent_str(indent, str(part))
                        for slc in media.slices:
                            print indent_str(indent, str(slc))
                        indent -= 1
                    indent -= 1
                indent -= 1
            indent -= 1

    # parse command line arguments
    options, args = parse_args()

    if options.libdiskmgt:
        print_libdiskmgt()
        if not options.require_td:
            sys.exit()

    # set up Target Discovery and execute it, finding the entire system
    InstallEngine()
    TD = TargetDiscovery("Test TD")

    # set dry_run to True so we don't label any drives on SPARC
    TD.execute(dry_run=True)

    if options.disk:
        print_disk(TD.doc)
    if options.gptpartition:
        print_gptpartition(TD.doc)
    if options.partition:
        print_partition(TD.doc)
    if options.slc:
        print_slice(TD.doc)
    if options.zpool:
        print_zpool(TD.doc)
    if options.xml:
        print TD.doc.get_xml_tree_str()

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

""" instantiation.py - target instantiation checkpoint.  Parses the Data Object
Cache for physical and logical targets.
"""
from copy import copy

from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.target import Target
from solaris_install.target.logical import BE, DatasetOptions, Filesystem, \
    Options, PoolOptions, Vdev, Zvol, Zpool
from solaris_install.target.physical import Disk, Partition, Slice


class TargetInstantiation(Checkpoint):
    """ class to instantiate targets
    """

    def __init__(self, name):
        super(TargetInstantiation, self).__init__(name)

        # lists for specific elements in the DOC
        self.logical_list = list()
        self.physical_list = list()
        self.swap_list = list()
        self.dump_list = list()

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 1

    def parse_doc(self):
        """ method for parsing data object cache (DOC) objects for use by the
        checkpoint
        """
        # doc and target nodes
        self.doc = InstallEngine.get_instance().data_object_cache
        self.target = self.doc.get_descendants(name=Target.DESIRED,
                                               class_type=Target,
                                               not_found_is_err=True)[0]

        self.logical_list = self.target.get_descendants(class_type=Zpool)
        self.physical_list = self.target.get_descendants(class_type=Disk)

        self.swap_list = []
        self.dump_list = []

        zvol_list = self.target.get_descendants(class_type=Zvol)

        if zvol_list:
            for zvol in zvol_list:
                if zvol.use == "swap":
                    self.swap_list.append(zvol)
                if zvol.use == "dump":
                    self.dump_list.append(zvol)

    def setup_physical(self):
        """ method used to parse the list of disks and create the desired
        physical configuration.
        """
        # walk the list
        for disk in self.physical_list:
            # if the 'whole_disk' attribute is set to True
            # don't even bother initializing the Disk. it will
            # be processed appropriately at zpool instantiation
            # time.
            if disk.whole_disk:
                continue

            # get the list of fdisk partitions and slices on the disk
            partition_list = disk.get_descendants(class_type=Partition)
            slice_list = disk.get_descendants(class_type=Slice)

            update_partition_table = False
            label_disk = True

            if partition_list:
                dup_partition_list = copy(partition_list)
                for partition in dup_partition_list:
                    # look for a partition name of None.  If it exists, raise
                    # an exception
                    if partition.name is None:
                        raise RuntimeError("Invalid name for Partition: " +
                                           str(partition))

                    # update the partition table and label the disk
                    # only if a partition is being created or destroyed.
                    #
                    # don't update the partition table or label the disk
                    # if 'preserve' or 'use_existing' is set on the partition
                    if partition.action == "create":
                        update_partition_table = True
                    elif partition.action == "delete":
                        partition_list.pop(partition_list.index(partition))
                        update_partition_table = True
                    elif partition.action in \
                        ["preserve", "use_existing_solaris2"]:
                        label_disk = False

            update_vtoc = False
            swap_slice_list = []
            if slice_list:
                dup_slice_list = copy(slice_list)
                for slc in dup_slice_list:
                    # write out the vtoc if a slice is being created or
                    # destroyed.
                    #
                    # don't write out the vtoc or label the disk if all
                    # the slices are being 'preserved'
                    if slc.action == "create":
                        update_vtoc = True
                    elif slc.action == "delete":
                        slice_list.pop(slice_list.index(slc))
                        update_vtoc = True
                    elif slc.action == "preserve":
                        label_disk = False

                    # if 'is_swap' is set to True, add this
                    # slice to the swap_slice_list
                    if slc.is_swap:
                        swap_slice_list.append(slc)

            if update_partition_table:
                disk._update_partition_table(partition_list, self.dry_run)
            if label_disk:
                # if no slices or partitions are marked 'preserve'
                # label the disk
                disk._label_disk(self.dry_run)
            if update_vtoc:
                disk._update_slices(slice_list, self.dry_run)
            if swap_slice_list:
                # one or more slices need to be added as ufs swap
                disk._create_ufs_swap(swap_slice_list, self.dry_run)

    def create_dump(self):
        """ method used to parse the dump (zvol) targets and create the
        objects marked 'create'
        """
        if self.dump_list:
            for dump in self.dump_list:
                if dump.action == "create":
                    dump.create(self.dry_run)

    def destroy_dump(self):
        """ method used to parse the dump (zvol) targets and destroy the
        objects marked 'delete'
        """
        if self.dump_list:
            for dump in self.dump_list:
                if dump.action in ["delete", "create"]:
                    if dump.exists:
                        dump.destroy(self.dry_run)

    def create_swap(self):
        """ method used to parse the swap (zvol) targets and create the
        objects marked 'create'
        """
        if self.swap_list:
            for swap in self.swap_list:
                if swap.action == "create":
                    swap.create(self.dry_run)

    def destroy_swap(self):
        """ method used to parse the swap (zvol) targets and destroy the
        objects marked 'delete' or 'create' (since 'create' has an
        implicit destroy associated with it)
        """
        if self.swap_list:
            for swap in self.swap_list:
                if swap.action in ["delete", "create"]:
                    if swap.exists:
                        swap.destroy(self.dry_run)

    def get_vdev_names(self, zpool_name, vdev_name=None, in_type="in_zpool"):
        """ method to extract all of the physical device names for a given
        zpool or vdev name from the DOC
        """
        vdev_list = []
        for class_type in [Disk, Partition, Slice]:
            dev_list = self.target.get_descendants(class_type=class_type)
            for dev in [d for d in dev_list if d.in_zpool == zpool_name]:
                # in_zpool will already match the zpool name.  For in_vdev,
                # also verify the vdev_name matches
                if in_type == "in_zpool" or \
                   (in_type == "in_vdev" and dev.in_vdev == vdev_name):
                    if isinstance(dev, Disk):
                        vdev_list.append(dev.ctd)
                    elif isinstance(dev, Partition):
                        vdev_list.append(dev.parent.ctd + "p%s" % dev.name)
                    elif isinstance(dev, Slice):
                        if isinstance(dev.parent, Partition):
                            vdev_list.append(dev.parent.parent.ctd + "s%s" % \
                                             dev.name)
                        else:
                            vdev_list.append(dev.parent.ctd + "s%s" % dev.name)

        # check to make sure something was populated in the vdev_list for
        # zpools with in_vdev set
        if in_type == "in_vdev" and not vdev_list:
            # the device (or devices) marked as "in_vdev" have no corresponding
            # zpool.  Raise a RuntimeError to notify the user something is very
            # wrong
            raise RuntimeError("in_vdev attribute requires in_zpool attribute")

        return vdev_list

    def destroy_logicals(self):
        """ method used to parse the logical targets and destroy the
        objects with action of 'delete' or 'create' (since 'create' has
        an implicit destroy associated with it)
        """
        for zpool in self.logical_list:
            if zpool.action in ["delete", "create"]:
                zpool.destroy(self.dry_run)
            else:
                # a pool was marked 'preserve' in which
                # case it might have filesystem/zvol children
                # objects that might be marked 'delete' or 'create'
                fs_list = zpool.get_children(class_type=Filesystem)
                if fs_list:
                    for fs in fs_list:
                        # create a new filesystem object
                        if fs.action in ["delete", "create"]:
                            fs.destroy(self.dry_run)

                zvol_list = zpool.get_children(class_type=Zvol)
                if zvol_list:
                    for zvol in zvol_list:
                        # create a new filesystem object
                        if zvol.action in ["delete", "create"]:
                            zvol.destroy(self.dry_run)

    def create_logicals(self):
        """ method used to parse the logical targets and create the objects
        with action of "create"
        """
        for zpool in self.logical_list:
            # get the pool and/or dataset options
            pool_options_list = zpool.get_children(class_type=PoolOptions)
            dataset_options_list = zpool.get_children(
                class_type=DatasetOptions)

            options = []
            if pool_options_list:
                for entry in pool_options_list:
                    options_entry = entry.get_children(class_type=Options)
                    for option in options_entry:
                        options.extend(option.options_str.split())
            if dataset_options_list:
                for entry in dataset_options_list:
                    options_entry = entry.get_children(class_type=Options)
                    for option in options_entry:
                        options.extend(option.options_str.split())

            vdevs = zpool.get_children(class_type=Vdev)
            vdev_list = []
            if vdevs:
                # if the pool has vdevs listed underneath it, get
                # those as well as the associated physical devices. i.e.
                # create a list of the form:
                # ["mirror", "c8t1d0", "c8t2d0", "mirror", "c8t3d0"]
                #
                # if no vdevs are listed just get the physical devices. i.e.
                # create a list of the form:
                # ["c8t1d0", "c8t2d0"]
                for vdev in vdevs:
                    if vdev.redundancy.capitalize() != "None":
                        # handle the special case for log mirror vdevs
                        if vdev.redundancy.capitalize() == "Logmirror":
                            vdev_list.extend(["log", "mirror"])
                        else:
                            vdev_list.append(vdev.redundancy)
                    vdev_list.extend(self.get_vdev_names(zpool.name, vdev.name,
                        in_type="in_vdev"))
            else:
                vdev_list = self.get_vdev_names(zpool.name)

            # set up the pool
            zpool.vdev_list = vdev_list
            if zpool.action == "create":
                zpool.create(self.dry_run, options)
            elif zpool.action == "preserve":
                if not zpool.exists:
                    # a pool marked 'preserve' that does not exist
                    # needs to be created
                    zpool.create(self.dry_run, options)

            # set up the filesystems in that pool, but only if the in_be
            # attribute is False
            fs_list = zpool.get_children(class_type=Filesystem)
            for fs in [fs for fs in fs_list if not fs.in_be]:
                if fs.action == "create":
                    fs.create(self.dry_run)
                    if fs.mountpoint is not None:
                        fs.set("mountpoint", fs.mountpoint, self.dry_run)
                elif fs.action == "preserve":
                    # if the filesystem doesn't exist, create it
                    if not fs.exists:
                        fs.create(self.dry_run)
                        if fs.mountpoint is not None:
                            fs.set("mountpoint", fs.mountpoint, self.dry_run)

            # set up the zvols in that pool but only on zvols whose use
            # attribute is "none".  "swap" and "dump" are handled later
            zvol_list = zpool.get_children(class_type=Zvol)
            for zvol in [z for z in zvol_list if z.use.lower() == "none"]:
                if zvol.action == "create":
                    zvol.create(self.dry_run)
                elif zvol.action == "preserve":
                    # if the zvol doesn't exist, create it
                    if not zvol.exists:
                        zvol.create(self.dry_run)

            # Set up the Boot Environment
            be_list = zpool.get_children(class_type=BE)
            be_fs_list = [fs.name for fs in fs_list if fs.in_be]
            for be in be_list:
                # Initialize the new BE.  If filesystems were specified with
                # "in_be" set to True, add those filesystems to the init call
                if be_fs_list:
                    be.init(self.dry_run, pool_name=zpool.name,
                            fs_list=be_fs_list)
                else:
                    be.init(self.dry_run, pool_name=zpool.name)

    def execute(self, dry_run=False):
        """ Primary execution method use by the Checkpoint parent class
        """
        self.logger.debug("Executing Target Instantiation")
        self.dry_run = dry_run

        self.parse_doc()

        # destroy swap and dump devices first
        self.destroy_swap()

        self.destroy_dump()

        # destroy other logical devices
        self.destroy_logicals()

        # destroy and then create physical devices
        self.setup_physical()

        # set up logical devices (zpool, zvol, zfs, BE)
        if self.logical_list:
            self.create_logicals()

        # lastly set up swap and dump devices
        self.create_swap()

        self.create_dump()

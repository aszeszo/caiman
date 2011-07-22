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

''' target_selection.py - Select Install Target(s)
'''
import copy
import os
import platform
import re
import traceback

from operator import attrgetter
import osol_install.errsvc as errsvc
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.target import Target, vdevs
from solaris_install.target.controller import TargetController, \
    DEFAULT_VDEV_NAME, SwapDumpGeneralError, SwapDumpSpaceError
from solaris_install.target.logical import Logical, Zpool, Vdev, BE, Zvol, \
    Filesystem, DatasetOptions, PoolOptions
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size

DISK_RE = "c\d+(?:t\d+)?d\d+"


class SelectionError(Exception):
    '''Error generated when any selection problems occur'''

    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg


class TargetSelection(Checkpoint):
    '''TargetSelection - Checkpoint to select install target.

       This checkpoint attempts to select the install target(s) based on
       the information provided in the discovered targets and the target
       information provided in the AI Manifest.

       If it's not possible to determine a selection, then a SelectionError
       exception will be raised, causing the installation to fail.
    '''
    RAIDZ_REDUNDANCY = ['raidz', 'raidz1', 'raidz2', 'raidz3']
    TOPLEVEL_REDUNDANCY = ['none', 'mirror']
    TOPLEVEL_REDUNDANCY.extend(RAIDZ_REDUNDANCY)
    INVALID_ROOT_VDEV = ['log', 'logmirror']
    PRESERVED = ['preserve', 'use_existing']

    def __init__(self, name, be_mountpoint="/a"):
        super(TargetSelection, self).__init__(name)

        # instance attributes
        self.be_mountpoint = be_mountpoint
        self.doc = InstallEngine.get_instance().data_object_cache
        self.dry_run = False

        # Initialize TargetController
        self.controller = TargetController(self.doc)

        # Cache of Discovered Tree, Disks  in the DOC, will be filled in later
        self._discovered = None
        self._wipe_disk = False
        self._discovered_disks = list()
        self._discovered_zpools = list()
        self._discovered_zpool_map = dict()
        self._remaining_zpool_map = dict()

        self.__reset_maps()

    def __reset_maps(self):
        '''Reset all local map information to default values
        '''
        # Whether swap/dump is to be created, noswap = Don't create swap
        self._nozpools = False
        self._noswap = False
        self._nodump = False

        # Cache of various information useful during parsing of manifest info
        self._root_pool = None     # Should be only one root pool
        self._be = None            # Should be only one BE

        self._is_generated_root_pool = False
        self._root_vdev = None     # Will only be set if we create a new rpool
                                   # due to none existing in manifest

        self._swap_zvol_map = dict()  # Map of zpool:swap to Zvol object
        self._dump_zvol = None   # Can only have one dump device

        self._no_logical_disks = list()  # List of disks with no zpool or vdev

        # Assuming only one target object per manifest.
        # If supporting more than one target, these will become lists
        # of dictionaries accessed via a target index.
        self._zpool_map = dict()   # Map of zpool names to Zpool object
        self._vdev_map = dict()    # Map of zpool:vdev names to Vdev objects
        self._vdev_added_map = dict()  # Map of zpool:vdev names we added
        self._zvol_map = dict()    # Map of zpool:zvols names to Zvol objects
        self._fs_map = dict()      # Map of zpool:datasets to Dataset objects
        self._pool_options = dict()  # Map of zpool names to PoolOption objects
        self._dataset_options = dict()  # Map of zpool names to DatasetOptions
        self._disk_map = dict()      # Map of disks to Disk objects

    def __find_disk(self, disk):
        '''Find a disk matching some criteria

           Disk can be identified in the following order of preference :
               1. disk.ctd (device name)
               2. disk.volid (volume name)
               3. disk.devid (device id)
               4. disk.devpath (device path)
               5. disk.receptacle (disk silk screen name)
               6. disk.is_boot_disk() (contains keyword "boot_disk")

               7. If None of the above are specified, a disk can be
                  identified via any/all of the three disk properties:
                    - dev_type
                    - dev_vendor
                    - dev_size
                  In this scenario, first matching disk will be returned.
        '''

        for discovered_disk in self._discovered_disks:
            # Attempt to match ctd/volid/devpath/devid first
            if discovered_disk.name_matches(disk):
                return discovered_disk

            # Attempt to match disk_prop.  Only match disk properties if all
            # ctd/volid/devpath/devid/receptacle are None, then attempt to
            # match on boot disk or one of the disk properties if specified
            if disk.ctd is None and disk.volid is None and \
               disk.devpath is None and disk.devid is None and \
               disk.receptacle is None:

                # Attempt to match disk_prop. Any of the properties
                # dev_type/dev_vendor/dev_size must been specified
                if discovered_disk.disk_prop is not None and \
                    disk.disk_prop is not None:
                    if discovered_disk.disk_prop.prop_matches(disk.disk_prop):
                        return discovered_disk

                # Attempt to match on boot_disk
                if disk.is_boot_disk() and discovered_disk.is_boot_disk():
                    return discovered_disk

        return None

    @staticmethod
    def __is_iterable(obj):
        '''Test if an object is iterable'''
        try:
            i = iter(obj)
            return True
        except TypeError:
            return False

    def __pretty_print_disk(self, disk):
        '''Print disk identifier rather than whole disk's str()'''
        if self.__is_iterable(disk):
            ret_str = ""
            for _disk in disk:
                if len(ret_str) != 0:
                    ret_str += ", "
                ret_str += self.__pretty_print_disk(_disk)
                return ret_str
        else:
            if isinstance(disk, Disk):
                if disk.ctd is not None:
                    return "%s" % disk.ctd
                if disk.volid is not None:
                    return "[volid='%s']" % disk.volid
                if disk.devpath is not None:
                    return "[devpath='%s']" % disk.devpath
                if disk.devid is not None:
                    return "[devid='%s']" % disk.devid
                if disk.receptacle is not None:
                    return "[receptacle='%s']" % disk.receptacle

                if disk.disk_prop is not None:
                    disk_props = list()
                    if disk.disk_prop.dev_type is not None:
                        disk_props.append(
                            "dev_type='%s'" % (disk.disk_prop.dev_type))
                    if disk.disk_prop.dev_vendor is not None:
                        disk_props.append(
                            "dev_vendor='%s'" % (disk.disk_prop.dev_vendor))
                    if disk.disk_prop.dev_chassis is not None:
                        disk_props.append(
                            "dev_chassis='%s'" %
                            (disk.disk_prop.dev_chassis))
                    if disk.disk_prop.dev_size is not None:
                        disk_props.append(
                            "dev_size='%s'" %
                            (str(disk.disk_prop.dev_size.sectors) +
                             Size.sector_units))
                    if disk_props:
                        disk_props_str = "[" + ",".join(disk_props) + "]"
                        return disk_props_str

                # All else fails, maybe looking for boot-disk?
                if disk.is_boot_disk():
                    return "[boot-disk]"

        return str(disk)

    def __handle_vdev(self, vdev):
        '''Create Vdev object
        '''
        self.logger.debug("Processing Vdev '%s', redundancy='%s'" %
            (vdev.name, vdev.redundancy))

        new_vdev = copy.copy(vdev)
        return new_vdev

    def __handle_filesystem(self, fs):
        '''Create Filesystem Object
        '''
        self.logger.debug("Processing Filesystem '%s', action='%s', "
            "mountpoint='%s'" % (fs.name, fs.action, fs.mountpoint))

        new_fs = copy.copy(fs)

        # Handle options children
        for options in fs.children:
            new_options = self.__handle_options(options)
            if new_options is not None:
                new_fs.insert_children(new_options)

        return new_fs

    def __handle_zvol(self, zvol):
        '''Create Zvol object
        '''
        self.logger.debug("Processing Zvol '%s', action='%s', use='%s'" %
            (zvol.name, zvol.action, zvol.use))

        new_zvol = copy.copy(zvol)
        # Handle options children

        for options in zvol.children:
            new_options = self.__handle_options(options)
            if new_options is not None:
                new_zvol.insert_children(new_options)

        return new_zvol

    def __handle_options(self, options):
        '''Create Zpool or Dataset Options object
        '''
        self.logger.debug("Processing Options '%s'" %
            str(options))

        new_options = copy.copy(options)
        return new_options

    def __handle_pool_options(self, pool_options):
        '''Create PoolOptions object
        '''
        self.logger.debug("Processing Pool Options '%s'" %
            str(pool_options))

        new_pool_options = copy.copy(pool_options)

        # Handle options children
        for options in pool_options.children:
            new_options = self.__handle_options(options)
            if new_options is not None:
                new_pool_options.insert_children(new_options)

        return new_pool_options

    def __handle_dataset_options(self, dataset_options):
        '''Create DatasetOption object
        '''
        self.logger.debug("Processing Dataset Options '%s'" %
            str(dataset_options))

        new_dataset_options = copy.copy(dataset_options)

        # Handle options children
        for options in dataset_options.children:
            new_options = self.__handle_options(options)
            if new_options is not None:
                new_dataset_options.insert_children(new_options)

        return new_dataset_options

    def __handle_be(self, be):
        '''Create BE object, set mountpoint to that passed in
           to target_selection init.
        '''
        self.logger.debug("Processing BE '%s'" % (be.name))

        new_be = copy.copy(be)
        new_be.mountpoint = self.be_mountpoint

        # Handle options children
        for options in be.children:
            new_options = self.__handle_options(options)
            if new_options is not None:
                new_be.insert_children(new_options)

        return new_be

    def __handle_zpool(self, zpool, logical):
        '''Process all zpool children, handling each child object type
           and returning Zpool object
        '''

        self.logger.debug("Processing Zpool '%s', action='%s', is_root='%s',"
            " mountpoint='%s'" % \
            (zpool.name, zpool.action, zpool.is_root, zpool.mountpoint))

        this_be = None

        if zpool.name in self._zpool_map:
            raise SelectionError("Zpool '%s' specified twice" % (zpool.name))

        vdev_count = 0
        new_zpool = copy.copy(zpool)
        logical.insert_children(new_zpool)
        for child in zpool.children:
            if isinstance(child, Vdev):
                new_vdev = self.__handle_vdev(child)
                if new_vdev is not None:
                    vdev_key = new_zpool.name + ":" + new_vdev.name
                    if vdev_key not in self._vdev_map:
                        self._vdev_map[vdev_key] = new_vdev
                        self.logger.debug("Adding Vdev '%s' to zpool" %
                            (new_vdev.name))
                        new_zpool.insert_children(new_vdev)
                        vdev_count += 1
                    else:
                        raise SelectionError(
                            "Vdev '%s' specified twice in zpool '%s'" % \
                            (new_vdev.name, new_zpool.name))
                else:
                    raise SelectionError("Failed to copy Vdev.")

            elif isinstance(child, Filesystem):
                new_fs = self.__handle_filesystem(child)
                if new_fs is not None:
                    if new_fs.action == "preserve" and \
                        new_zpool.action not in self.PRESERVED:
                        raise SelectionError("Filesystem '%s' cannot be "
                            "preserved in non-preserved zpool '%s'." % \
                            (new_fs.name, new_zpool.name))

                    fs_key = new_zpool.name + ":" + new_fs.name
                    # Filesystem name must be unique within each pool
                    if fs_key not in self._fs_map and \
                        fs_key not in self._zvol_map:
                        self._fs_map[fs_key] = new_fs
                        self.logger.debug("Adding Filesystem '%s' to zpool" %
                            (new_fs.name))
                        new_zpool.insert_children(new_fs)
                    else:
                        raise SelectionError(
                            "Filesystem '%s' specified twice in zpool '%s'" % \
                            (new_fs.name, new_zpool.name))
                else:
                    raise SelectionError("Failed to copy Filesystem.")

            elif isinstance(child, Zvol):
                new_zvol = self.__handle_zvol(child)
                if new_zvol is not None:
                    if new_zvol.action in self.PRESERVED and \
                        new_zpool.action not in self.PRESERVED:
                        raise SelectionError("Zvol '%s' cannot be "
                            "preserved in non-preserved zpool '%s'." % \
                            (new_zvol.name, zpool.name))
                    zvol_key = new_zpool.name + ":" + new_zvol.name
                    # Zvol name must be unique within each pool
                    if zvol_key not in self._zvol_map and \
                        zvol_key not in self._fs_map:
                        if new_zvol.use == "swap":
                            # Cannot specify Swap Zvol and noswap == true
                            if self._noswap:
                                if zpool.action in self.PRESERVED:
                                    raise SelectionError(
                                        "Swap zvol already exists and "
                                        "noswap specified in manifest.")
                                else:
                                    raise SelectionError(
                                        "Both swap zvol and noswap specified "
                                        "in manifest.")
                            self._swap_zvol_map[zvol_key] = new_zvol
                        elif new_zvol.use == "dump":
                            # Can only specify one Dump Zvol
                            if self._dump_zvol is not None:
                                raise SelectionError(
                                    "Dump zvol specified twice.")

                            # Cannot specify Dump Zvol and nodump == true
                            if self._nodump:
                                if zpool.action in self.PRESERVED:
                                    raise SelectionError(
                                        "Dump zvol already exists and "
                                        "nodump specified in manifest.")
                                else:
                                    raise SelectionError(
                                        "Both dump zvol and nodump specified "
                                        "in manifest.")

                            # Cannot delete a dump zvol
                            if new_zvol.action == "delete":
                                self.__raise_dump_zvol_deletion_exception()
                            self._dump_zvol = new_zvol

                        self._zvol_map[zvol_key] = new_zvol
                        self.logger.debug("Adding Zvol '%s' to zpool" %
                            (new_zvol.name))
                        new_zpool.insert_children(new_zvol)
                    else:
                        raise SelectionError(
                            "Zvol '%s' specified twice in zpool '%s'" % \
                            (new_zvol.name, new_zpool.name))
                else:
                    raise SelectionError("Failed to copy Zvol.")

            elif isinstance(child, PoolOptions):
                new_pool_options = self.__handle_pool_options(child)
                if new_pool_options is not None:
                    # Can only specify one pool_options per zpool
                    if new_zpool.name not in self._pool_options:
                        self._pool_options[new_zpool.name] = new_pool_options
                        self.logger.debug("Adding Pool Options '%s' to"
                            "zpool '%s'" % (new_pool_options, new_zpool.name))
                        new_zpool.insert_children(new_pool_options)
                    else:
                        raise SelectionError(
                            "More than one pool_options specified "
                            "zpool '%s'" % (new_zpool.name))
                else:
                    raise SelectionError("Failed to copy PoolOptions.")

            elif isinstance(child, DatasetOptions):
                # Validate only one dataset options
                new_dataset_options = self.__handle_dataset_options(child)
                if new_dataset_options is not None:
                    # Can only specify one dataset_options per zpool
                    if new_zpool.name not in self._dataset_options:
                        self._dataset_options[new_zpool.name] = \
                            new_dataset_options
                        self.logger.debug("Adding Dataset Options to zpool")
                        new_zpool.insert_children(new_dataset_options)
                    else:
                        raise SelectionError(
                            "More than one dataset_options specified "
                            "in zpool '%s'" % (new_zpool.name))
                else:
                    raise SelectionError("Failed to copy DatasetOptions.")

            elif isinstance(child, BE):
                if not zpool.is_root:
                    raise SelectionError("BE cannot be part of non root "
                        "pool '%s'" % (zpool.name))
                new_be = self.__handle_be(child)
                if new_be is not None:
                    # BE can only be specified once in entire manifest
                    if self._be is None:
                        self._be = new_be
                        this_be = new_be

                        self.logger.debug("Adding BE '%s' to zpool" %
                            (new_be.name))
                        new_zpool.insert_children(new_be)
                    else:
                        if this_be is not None:
                            raise SelectionError(
                                "More than one BE specified in zpool '%s'" % \
                                (new_zpool.name))
                        else:
                            raise SelectionError(
                                "Only one BE element allowed per logical.")
                else:
                    raise SelectionError("Failed to copy BE.")

            else:
                raise SelectionError("Invalid zpool sub element")

        if vdev_count == 0:
            # Zpool specified in manifest but no vdevs were specified
            # Add a default vdev of type mirror to add any disks to later
            self.logger.debug("No Vdevs found in zpool '%s', adding mirror."
                % (new_zpool.name))
            new_vdev = new_zpool.add_vdev(DEFAULT_VDEV_NAME, "mirror")
            vdev_key = new_zpool.name + ":" + new_vdev.name
            self._vdev_map[vdev_key] = new_vdev
            self._vdev_added_map[vdev_key] = new_vdev

        return new_zpool

    def __handle_preserved_zpool(self, discovered_zpool, zpool):
        '''
            Process all zpool children, handling each child object type
            and returning Zpool object.
            Preserving a Zpool effectively means maintaining the physical
            device structure of a zpool, so you cannot add new physical
            devices via AI, you can however change what's contained on the
            zpool, e.g. create/delete filesystems/Zvols.

            Filesystems:
                - Create, must not already exist
                - Delete, must exist already
                - Preserve, nothing to do, but must exist already.

            Zvols:
                - Create, must not already exist
                - Delete, must exist already
                - Preserve, nothing to do, but must exist already.
                - use_existing, must exist, and usage must be changing

            BE's:
                - Can only be one BE, BE's are not copied from discovered
                  as there could be laods.
                - Ensure this BE does not exist already, if not specified
                  Ensure default created BE does not already exist.

            Dataset Options:
                - Not allowed in AI, user can do this manually, requires
                  parsing of string options and zfs knowledge of what options
                  can be applied post pool creation.

            Pool Options:
                - Not allowed in AI, user can do this manually, requires
                  parsing of string options and zfs knowledge of what options
                  can be applied post pool creation.
        '''
        self.logger.debug("Processing %s Zpool '%s', action='%s',"
            " is_root='%s', mountpoint='%s'" % (zpool.action, zpool.name,
            zpool.action, zpool.is_root, zpool.mountpoint))

        discovered_bes = self.__get_discovered_be(zpool)
        this_be = None

        discovered_zpool.action = zpool.action

        for child in zpool.children:
            if isinstance(child, Vdev):
                raise SelectionError("Cannot specify vdev's for preserved "
                    "zpool '%s'." % (zpool.name))

            elif isinstance(child, Filesystem):
                new_fs = self.__handle_filesystem(child)
                if new_fs is not None:
                    fs_key = zpool.name + ":" + new_fs.name
                    # Check if this filesystem already exists as zvol
                    if fs_key in self._zvol_map:
                        raise SelectionError("Filesystem '%s' specified on "
                            "preserved zpool '%s' exists as Zvol." % \
                            (new_fs.name, zpool.name))
                    elif fs_key in self._fs_map:
                        # Only preserve and delete are allowed for existing
                        if new_fs.action not in ["preserve", "delete"]:
                            raise SelectionError("Filesystem '%s' specified on"
                                " preserved zpool '%s' contains invalid action"
                                " of '%s'." % \
                                (new_fs.name, zpool.name, new_fs.action))
                        # Remove discovered item in order to add user specified
                        discovered_zpool.delete_children(new_fs)
                    else:
                        # Only create allowed for new filesystems
                        if new_fs.action != "create":
                            raise SelectionError("Filesystem '%s' specified on"
                                " preserved zpool '%s' contains invalid action"
                                " of '%s'." % \
                                (new_fs.name, zpool.name, new_fs.action))
                        self._fs_map[fs_key] = new_fs

                    self.logger.debug("Adding Filesystem '%s' to zpool" %
                         (new_fs.name))
                    discovered_zpool.insert_children(new_fs)
                else:
                    raise SelectionError("Failed to process Filesystem.")

            elif isinstance(child, Zvol):
                new_zvol = self.__handle_zvol(child)
                if new_zvol is not None:
                    zvol_key = zpool.name + ":" + new_zvol.name

                    # Check if This Zvol already exists as filesystem
                    if zvol_key in self._fs_map:
                        raise SelectionError("Zvol '%s' specified on "
                            "preserved zpool '%s' exists as Filesystem." % \
                            (new_zvol.name, zpool.name))
                    elif zvol_key in self._zvol_map:
                        # Only preserve, delete, use_existing are allowed
                        if new_zvol.action not in \
                            ["preserve", "delete", "use_existing"]:
                            raise SelectionError("Zvol '%s' specified on "
                                "preserved zpool '%s' contains invalid action "
                                "of '%s'." % \
                                (new_zvol.name, zpool.name, new_zvol.action))

                        discovered_zvol = discovered_zpool.get_first_child(
                            new_zvol.name, Zvol)

                        if discovered_zvol is None:
                            raise SelectionError("Zvol '%s' not found in "
                                "discovered." % (new_zvol.name))

                        if new_zvol.action == "use_existing":
                            if discovered_zvol.use == new_zvol.use:
                                raise SelectionError("Zvol '%s' marked as "
                                    "use_existing but usage has not changed." %
                                    (new_zvol.name))
                            elif discovered_zvol.use == "dump":
                                # Cannot delete a dump zvol
                                self.__raise_dump_zvol_deletion_exception()

                            elif new_zvol.use == "dump":
                                # Can only specify one Dump Zvol
                                if self._dump_zvol is not None:
                                    raise SelectionError(
                                        "Dump zvol specified twice.")

                                # Cannot specify Dump Zvol and nodump == true
                                if self._nodump:
                                    raise SelectionError(
                                        "Both dump zvol and nodump "
                                        "specified in manifest.")
                                # Make a copy of discovered zvol to ensure we
                                # get same size specification
                                new_zvol = copy.deepcopy(discovered_zvol)
                                new_zvol.action = "create"
                                new_zvol.use = "dump"
                                self._dump_zvol = new_zvol

                            elif new_zvol.use == "swap":
                                # Cannot have Swap Zvol and noswap == true
                                if self._noswap:
                                    raise SelectionError(
                                        "Both swap zvol and noswap "
                                        "specified in manifest.")
                                if new_zvol in self._swap_zvol_map:
                                    raise SelectionError("Zvol '%s' specified "
                                        "as swap twice in preserved zpool "
                                        "'%s'" % (new_zvol.name, zpool.name))
                                new_zvol = copy.deepcopy(discovered_zvol)
                                new_zvol.action = "create"
                                new_zvol.use = "swap"
                                self._swap_zvol_map[zvol_key] = new_zvol
                            else:
                                new_zvol = copy.deepcopy(discovered_zvol)
                                new_zvol.action = "create"
                                new_zvol.use = "none"

                            if discovered_zvol.use == "swap":
                                # Remove this device from swap map
                                if new_zvol in self._swap_zvol_map:
                                    del self._swap_zvol_map[zvol_key]

                        # Remove discovered item in order to add user specified
                        discovered_zpool.delete_children(new_zvol)
                    else:
                        # Only create allowed for new zvol
                        if new_zvol.action != "create":
                            raise SelectionError("Zvol '%s' specified on "
                                "preserved zpool '%s' contains invalid action "
                                "of '%s'." % \
                                (new_zvol.name, zpool.name, new_zvol.action))
                        self._zvol_map[zvol_key] = new_zvol

                    self._zvol_map[zvol_key] = new_zvol
                    self.logger.debug("Adding Zvol '%s' to zpool" %
                        (new_zvol.name))
                    discovered_zpool.insert_children(new_zvol)
                else:
                    raise SelectionError("Failed to copy Zvol.")

            elif isinstance(child, PoolOptions):
                raise SelectionError("Cannot specify Pool Option's for "
                    "preserved zpool '%s'." % (zpool.name))

            elif isinstance(child, DatasetOptions):
                raise SelectionError("Cannot specify Dataset Option's for "
                    "preserved zpool '%s'." % (zpool.name))

            elif isinstance(child, BE):
                if not zpool.is_root:
                    raise SelectionError("BE cannot be part of non root "
                        "pool '%s'" % (zpool.name))
                new_be = self.__handle_be(child)
                if new_be is not None:
                    # Ensure this boot environment does not exist on
                    # this preserved/use_existing zpool
                    if new_be.exists:
                        raise SelectionError(
                                "BE '%s' specified in preserved "
                                "zpool '%s' already exists. To install to "
                                "existing zpool you must specify a unique "
                                "BE in the manifest." % \
                                (new_be.name, zpool.name))

                    # BE can only be specified once in entire manifest
                    if self._be is None:
                        self._be = new_be
                        this_be = new_be

                        self.logger.debug("Adding BE '%s' to zpool" %
                            (new_be.name))
                        discovered_zpool.insert_children(new_be)
                    else:
                        if this_be is not None:
                            raise SelectionError(
                                "More than one BE specified in zpool '%s'" % \
                                (zpool.name))
                        else:
                            raise SelectionError(
                                "Only one BE element allowed per logical.")
                else:
                    raise SelectionError("Failed to copy BE.")

            else:
                raise SelectionError("Invalid zpool sub element")

    def __handle_logical(self, logical):
        '''Create Logical structure from manifest, validating
           zpools and contents in the process
        '''
        # Clear the Error service
        errsvc.clear_error_list()

        self.logger.debug("Processing Logical noswap : %s, nodump : %s" %
            (logical.noswap, logical.nodump))

        # Set whether to specifically not create swap/dump
        self._noswap = logical.noswap
        self._nodump = logical.nodump

        new_logical = copy.copy(logical)

        preserving_zpools = False
        for zpool in logical.children:
            # This will always be true as Logical can only contain zpools
            if isinstance(zpool, Zpool):
                if zpool.action in self.PRESERVED:
                    preserving_zpools = True
                    disc_zpool = self.__get_discovered_zpool(zpool)
                    if disc_zpool is None:
                        raise SelectionError("Failed to find zpool '%s' in "
                            "discovered logical tree." % (zpool.name))

                    if zpool.action == "use_existing" and \
                        not disc_zpool.is_root:
                        raise SelectionError("Specified action of "
                            "'use_existing' on pool '%s' is invalid. '%s' "
                            "is not a root pool." % (zpool.name, zpool.name))

                    new_zpool = self.__handle_zpool(disc_zpool, new_logical)

                    # Copy physical devices to desired
                    self.__copy_zpool_discovered_devices(new_zpool)
                else:
                    new_zpool = self.__handle_zpool(zpool, new_logical)

                if new_zpool is not None:
                    if new_zpool.name not in self._zpool_map:
                        if new_zpool.is_root:
                            # Only one root pool can be specified
                            if self._root_pool is not None:
                                raise SelectionError(
                                    "Root pool specified twice")
                            self.logger.debug("Root zpool found '%s'" %
                                (new_zpool.name))
                            self._root_pool = new_zpool
                        self.logger.debug("Adding zpool '%s' to logical" %
                            (new_zpool.name))
                        self._zpool_map[new_zpool.name] = new_zpool
                    else:
                        raise SelectionError("Zpool '%s' specified twice" %
                            (new_zpool.name))

                if zpool.action in self.PRESERVED:
                    self.__handle_preserved_zpool(new_zpool, zpool)
            else:
                raise SelectionError("Invalid logical child.")

        if preserving_zpools:
            # Need to update all devices, and remove any references to
            # Zpools that do not exist.
            self.__remove_invalid_zpool_references(new_logical)

        if self._zpool_map is None or len(self._zpool_map) == 0:
            self._nozpools = True
            new_logical = None

        # Check error service for errors
        errors = errsvc.get_all_errors()
        if errors:
            existing_desired = \
                self.doc.persistent.get_first_child(Target.DESIRED)
            if existing_desired:
                self.logger.debug("Desired =\n%s\n" % (str(existing_desired)))
            errstr = "Following errors occurred processing logical :\n%s" % \
                (str(errors[0]))
            raise SelectionError(errstr)

        return new_logical

    def __raise_dump_zvol_deletion_exception(self):
        '''
            Dump zvol's cannot be unassigned from being a dump device.
            Bug 6910925 is addressing this issue, however until resolved
            we have to trap and tell the user that this is not possible.
        '''
        self.logger.debug("Workaround for releaseing Zvol as dump device.")
        self.logger.debug("Create a new Zvol on another pool, and assign ")
        self.logger.debug("this Zvol as the dump device. The original dump")
        self.logger.debug("assigned Zvol and it's pool can now be destroyed.")

        raise SelectionError("Dump device cannot be unassigned. Due to "
            "RFE 6910925. See install_log for workaround.")

    def __remove_invalid_zpool_references(self, logical):
        '''
            Process all physical devices, remove any references to in_zpool
            in_vdev referencing pools not in this logical tree.

            Whilst processing the disks add them to the internal maps.

            At this stage self._zpool_map will have been populated.
        '''
        # Cycle through all desired physical disks checking what pool if
        # any these disks/devices are assigned to.
        # If the pool does not exist in this logical, then reset their
        # in_zpool and in_vdev attributes to None
        new_desired_target = self.__get_new_desired_target()
        desired_disks = new_desired_target.get_descendants(class_type=Disk)

        for disk in desired_disks:
            if disk.in_zpool is not None and \
                disk.in_zpool not in self._zpool_map:
                disk.in_zpool = None
                disk.in_vdev = None

            # Process any children and ensure they are unset aswell
            for disk_kid in disk.children:
                if (isinstance(disk_kid, Partition) or \
                    isinstance(disk_kid, Slice)) and \
                    disk_kid.in_zpool is not None and \
                    disk_kid.in_zpool not in self._zpool_map:
                    disk_kid.in_zpool = None
                    disk_kid.in_vdev = None

                if isinstance(disk_kid, Partition):
                    for slc in disk_kid.children:
                        if isinstance(slc, Slice) and \
                            slc.in_zpool is not None and \
                            slc.in_zpool not in self._zpool_map:
                            slc.in_zpool = None
                            slc.in_vdev = None

        # Add all these disks to map
        self.__add_disks_to_map(desired_disks)

    def __add_disks_to_map(self, disks):
        '''
            Given a list of disks, add them to the intermal disk map.
            Throwing exception if disk has already been added.
        '''
        for disk in disks:
            if disk.ctd in self._disk_map:
                # Seems that the disk is specified more than once in
                # the manifest!
                raise SelectionError(
                    "Disk '%s' matches already used disk '%s'." %
                    (self.__pretty_print_disk(disk), disk.ctd))
            self._disk_map[disk.ctd] = disk

    def __get_discovered_be(self, zpool):
        '''
            Retrieve the list of boot environments for a specific discovered
            zpool.
        '''
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        discovered_zpools = discovered.get_descendants(name=zpool.name,
            class_type=Zpool)

        if not discovered_zpools:
            return None

        found_be = discovered_zpools[0].get_descendants(class_type=BE)
        return found_be

    def __get_discovered_zpool(self, zpool):
        '''
            Process list of discovered zpools for matching zpool.
            Return None if not found or zpool object if found.
        '''
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        discovered_zpools = discovered.get_descendants(name=zpool.name,
            class_type=Zpool)

        if not discovered_zpools:
            return None

        found_zpool = copy.deepcopy(discovered_zpools[0])

        # Remove BE's as they cannot be preserved/recreated via AI
        found_zpool.delete_children(class_type=BE)

        return found_zpool

    def __copy_zpool_discovered_devices(self, zpool):
        '''
            For zpools being preserved, copy all devices associated with
            this zpool into desired tree.
            When copying devices, entire disk tree needs to be copied if
            any part of the disk resides on this zpool, by default all elements
            are set to "preserved", so nothing will get destroyed, TI needs
            to have all elements of the disk tree structure or it will wipe
            them.
            Throw exception if after processing all physical devices, and
            none were found for this zpool.
        '''
        new_desired_target = self.__get_new_desired_target()
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        discovered_disks = discovered.get_descendants(class_type=Disk)

        device_found = False
        for disk in discovered_disks:
            disk_copy = None
            disk_found = False
            if disk.in_zpool is not None and disk.in_zpool == zpool.name:
                # Copy entire disk
                disk_copy = copy.deepcopy(disk)
                disk_found = True
            else:
                for disk_kid in disk.children:
                    if isinstance(disk_kid, Partition):
                        if disk_kid.in_zpool is not None and \
                            disk_kid.in_zpool == zpool.name:
                            disk_found = True
                            break
                        else:
                            for slc in disk_kid.children:
                                if isinstance(slc, Slice):
                                    # Only copy if in this zpool
                                    if slc.in_zpool is not None and \
                                        slc.in_zpool == zpool.name:
                                        disk_found = True
                                        break

                    elif isinstance(disk_kid, Slice):
                        if disk_kid.in_zpool is not None and \
                            disk_kid.in_zpool == zpool.name:
                            disk_found = True
                            break

                if disk_found:
                    disk_copy = copy.deepcopy(disk)

            if disk_copy is not None and disk_found:
                # If this is the root pool, make sure solaris partition
                # is marked as Active, Final Validation fails otherwise
                if zpool.is_root and platform.processor() == 'i386':
                    solaris2_part_type = Partition.name_to_num("Solaris2")
                    for disk_kid in disk_copy.children:
                        if isinstance(disk_kid, Partition) and \
                            disk_kid.part_type == solaris2_part_type:
                            disk_kid.bootid = Partition.ACTIVE
                            break
                new_desired_target.insert_children(disk_copy)
                device_found = True

        if not device_found:
            raise SelectionError("Failed to find any discovered devices for "
                "zpool '%s'." % (zpool.name))

    def __validate_zpool_actions(self, zpool):
        '''Perform some validation on zpool actions against
           root pool and existing zpool's.
           Ensure pool name does not exist as a current directory, it pool does
           not exist already and is being created.
        '''

        if zpool.exists:
            # Get zpool discovered object
            discovered_zpool = self.__get_discovered_zpool(zpool)

            if discovered_zpool is None:
                if self.dry_run:
                    # Throw warning only if in dry run mode
                    self.logger.warning("zpool.exists() reports zpool '%s' "
                        "exists, but zpool object not in Discovered tree." % \
                        (zpool.name))
                else:
                    raise SelectionError("zpool.exists() reports zpool '%s' "
                        "exists, but zpool object not in Discovered tree." % \
                        (zpool.name))

            if zpool.action == "create":
                # Log warning stating zpool will be destroyed
                self.logger.warning("Existing zpool '%s' will be destroyed."
                                    % (zpool.name))

            elif zpool.action == "preserve" and \
                (zpool.is_root or discovered_zpool.is_root):
                # Manifest specifies to preserve pool, and either manifest
                # or discovered specify this as root pool
                raise SelectionError("Invalid preservation specified for "
                    "root zpool '%s'. Use 'use_existing' action." % \
                    (zpool.name))

            elif zpool.action == "use_existing":
                # Pool must be a an existing root pool
                if not discovered_zpool.is_root:
                    raise SelectionError("Cannot specify 'use_existing' "
                        "action for already existing non root zpool '%s'."
                        % (zpool.name))

                if not zpool.is_root:
                    raise SelectionError("Cannot specify 'use_existing' "
                        "action on non root zpool '%s'." % (zpool.name))

                # Preserving a root pool, let's make sure there is
                # sufficient space left in this pool for a solaris install
                zpool_available_size = self.__get_existing_zpool_size(zpool)
                if zpool_available_size < self.controller.minimum_target_size:
                    raise SelectionError("Preserved root pool '%s' has "
                        "available space of '%s', which is insufficient "
                        "space to install to. Minimum space "
                        "required is '%s'."
                        % (zpool.name, str(zpool_available_size),
                        str(self.controller.minimum_target_size)))

        else:
            if zpool.action == "delete":
                self.logger.warning("Manifest specifies to delete non "
                    "existent zpool '%s'." % (zpool.name))
            elif zpool.action == "preserve":
                raise SelectionError("Cannot 'preserve' non existent zpool "
                    "'%s'." % (zpool.name))
            elif zpool.action == "use_existing":
                raise SelectionError("Cannot 'use_existing' non existent "
                    "zpool '%s'." % (zpool.name))
            else:
                # Attempting to create a new Zpool, ensure pool name
                # is not an existing directory as zpool create will fail.
                if os.path.isdir(os.path.join("/", zpool.name)):
                    if self.dry_run:
                        # Dry run mode, just post warning to log
                        self.logger.warning("Pool name '%s' is not valid, "
                            "directory exists with this name." % (zpool.name))
                    else:
                        raise SelectionError("Pool name '%s' is not valid, "
                            "directory exists with this name." % (zpool.name))

    def __get_existing_zpool_size(self, zpool):
        '''Retrieve the size available for this zpool via the "size"
           zpool property. Returned size is a Size object.
        '''
        if zpool.exists:
            propdict = zpool.get("size")
            retsize = Size(propdict.get("size", "0b"))
        else:
            retsize = Size("0b")

        return retsize

    def __get_zpool_available_size(self, zpool):
        '''Process all the devices in the first toplevel of this zpool
           returning what the available size for this zpool if created.

           "none" : concatenate size of all devices
           "mirror", "raidz*" : get size of smallest device

           returns Size object
        '''
        retsize = None

        if zpool.action in self.PRESERVED:
            # Pool is being preserved so no devices in desired,
            # Get size from discovered disks instead
            retsize = self.__get_existing_zpool_size(zpool)
        else:
            # Get available size from desired targets
            for vdev in zpool.children:
                if isinstance(vdev, Vdev):
                    vdev_devices = self.__get_vdev_devices(zpool.name,
                        vdev.name, self._disk_map)
                    if vdev.redundancy in self.TOPLEVEL_REDUNDANCY:
                        if vdev_devices:
                            for device in vdev_devices:
                                if retsize is None:
                                    retsize = copy.copy(device.size)
                                else:
                                    devsize = copy.copy(device.size)
                                    if vdev.redundancy == "none":
                                        # Concatenate device sizes together
                                        retsize = Size(str(retsize.byte_value +
                                            devsize.byte_value) +
                                            Size.byte_units)
                                    else:
                                        # Get size of smallest device
                                        if devsize < retsize:
                                            retsize = devsize
                            # Break after first Toplevel vdev
                            break
                        else:
                            raise SelectionError("Vdev '%s' on zpool '%s' "
                                "must contain at least one device." % \
                                (vdev.name, zpool.name))

        if retsize is None:
            raise SelectionError("Could not determine the available size in "
                "pool '%s'. Toplevel Vdev could not be found." % (zpool.name))

        return retsize

    def __validate_swap_and_dump(self, desired):
        '''Ensure at least one swap and one dump device exist in logical
           tree.

           If none exist, unless noswap or nodump are set to true we will, by
           default, create one of each in the root pool if sufficient space
           available.
        '''
        # Get Logical sections
        logical = desired.get_first_child(class_type=Logical)

        if logical is not None:
            # swap :
            if (not logical.noswap and len(self._swap_zvol_map) == 0) or \
                (not logical.nodump and self._dump_zvol is None):

                # One or both of swap and dump not already created, get
                # default type/sizes if we are to create them

                # Create swap/dump zvol in root pool
                swap_added = False
                dump_added = False
                for zpool in [z for z in logical.children if z.is_root]:

                    # This needs to be done for on the pool itself as we
                    # need to process this pool to get the available size
                    # To install to.
                    try:
                        (swap_type, swap_size, dump_type, dump_size) = \
                            self.controller.calc_swap_dump_size(\
                                self.controller.minimum_target_size,
                                self.__get_zpool_available_size(zpool))
                    except (SwapDumpGeneralError, SwapDumpSpaceError) as ex:
                        raise SelectionError("Error determining swap/dump "
                            "requirements.")

                    # Only process root pools (should only be one either way)
                    if not logical.noswap and len(self._swap_zvol_map) == 0:
                        # Swap does not exist so attempt to create
                        if swap_type == self.controller.SWAP_DUMP_ZVOL and \
                            swap_size > Size("0b"):
                            zvol_name = self.__get_unique_dataset_name(zpool,
                                                                       "swap")
                            self.__create_swap_dump_zvol(zpool, zvol_name,
                                "swap", swap_size)
                            swap_added = True

                    if not logical.nodump and self._dump_zvol is None:
                        # Dump does not exist so attempt to create
                        if dump_type == self.controller.SWAP_DUMP_ZVOL and \
                            dump_size > Size("0b"):
                            zvol_name = self.__get_unique_dataset_name(zpool,
                                                                       "dump")
                            self.__create_swap_dump_zvol(zpool, zvol_name,
                                "dump", dump_size)
                            dump_added = True

                if not swap_added and \
                    not logical.noswap and len(self._swap_zvol_map) == 0:
                    self.logger.warning("Failed to add default swap zvol to "
                        "root pool")

                if not dump_added and \
                    not logical.nodump and self._dump_zvol is None:
                    self.logger.warning("Failed to add default dump zvol to "
                        "root pool")

    def __get_unique_dataset_name(self, zpool, dataset_name):
        '''
            Ensure this dataset name does not exist in this zpool.
            If it does, then append N to end until unique.
        '''
        unique = False
        unique_name = dataset_name
        append_digit = 1
        while not unique:
            unique = True
            for child in zpool.children:
                if (isinstance(child, Filesystem) or \
                    isinstance(child, Zvol)) and \
                    child.name == unique_name:
                    unique_name = dataset_name + str(append_digit)
                    append_digit = append_digit + 1
                    unique = False
                    break

        return unique_name

    def __create_swap_dump_zvol(self, zpool, zvol_name, zvol_use, zvol_size):
        '''Create a swap or dump Zvol on a zpool.

           Input:
               zpool : zpool object to add zvol to
               zvol_name : Str zvol name
               zvol_use : Str zvol usage, "swap" or "dump"
               zvol_size : Size Object
        '''
        zvol = zpool.add_zvol(zvol_name, int(zvol_size.get(Size.mb_units)),
            Size.mb_units, use=zvol_use)

        if zvol_use == "swap":
            swap_key = zpool.name + ":swap"
            self._swap_zvol_map[swap_key] = zvol
        else:
            self._dump_zvol = zvol

    def __validate_logical(self, desired):
        '''Process Logical components of desired tree ensuring:
           - mirror, at least two devices
           - logmirror, at least two devices
           - raidz1, at least two devices
           - raidz2, at least three devices
           - raidz3, at least four devices
           - Ensure at least one of none|mirror|raidz exists per pool
           - Ensure only one BE specified per pool, if none add one.
           - Ensure only one DatasetOptions specified per pool
           - Ensure only one PoolOptions specified per pool
           - Ensure only one pool is set to root pool
           - root_pool, ensure single device or if multiple devices,
             redundancy is set to mirror.
           - Root pool cannot contain log or logmirror devices
        '''

        # Get Logical sections
        logicals = desired.get_children(class_type=Logical)

        # Validate correct number of devices per redundancy
        for logical in logicals:
            self.logger.debug("Validating desired  logical =\n%s\n" %
                (str(logical)))
            be = None
            found_be = False
            found_dataset_options = False
            found_pool_options = False
            found_root_pool = False
            found_swap = False
            found_dump = False
            self._remaining_zpool_map = \
                self.__compile_remaining_existing_devices_map(logical)
            for zpool in logical.children:
                if zpool.is_root:
                    if found_root_pool:
                        raise SelectionError("Root pool specified twice")
                    else:
                        found_root_pool = True

                        # Ensure Root pool size is large enough to install to
                        zpool_available_size = \
                            self.__get_zpool_available_size(zpool)
                        if zpool_available_size < \
                            self.controller.minimum_target_size:
                            raise SelectionError("Root pool '%s' has "
                                "available space of '%s', which is "
                                "insufficient space to install to. "
                                "Minimum space required is '%s'."
                                % (zpool.name, str(zpool_available_size),
                                str(self.controller.minimum_target_size)))

                # Perform some validations on zpool
                # Check if this zpool already exists etc
                self.__validate_zpool_actions(zpool)

                found_toplevel = False
                for child in zpool.children:
                    if isinstance(child, Vdev):
                        self.__validate_vdev(zpool, child)

                        # Ensure something other than log/cache/spare is set
                        if child.redundancy in self.TOPLEVEL_REDUNDANCY and \
                            not found_toplevel:
                            found_toplevel = True

                    elif isinstance(child, BE):
                        if not zpool.is_root:
                            raise SelectionError("BE '%s' cannot be part of "
                                "non root pool '%s'." %
                                (child.name, zpool.name))

                        if found_be:
                            raise SelectionError(
                                "More than one BE specified in zpool '%s'." % \
                                (zpool.name))
                        else:
                            found_be = True
                            be = child

                    elif isinstance(child, DatasetOptions):
                        if found_dataset_options:
                            raise SelectionError(
                                "More than one dataset_options specified "
                                "in zpool '%s'." % (zpool.name))
                        else:
                            found_dataset_options = True

                    elif isinstance(child, PoolOptions):
                        if found_pool_options:
                            raise SelectionError(
                                "More than one pool_options specified "
                                "zpool '%s'." % (zpool.name))
                        else:
                            found_pool_options = True

                    elif isinstance(child, Zvol):
                        if child.use == "swap":
                            found_swap = True
                        elif child.use == "dump":
                            found_dump = True

                # If the pool does not contain any toplevel vdevs throw
                # exception. For pools marked for deletion not an error.
                if not found_toplevel and zpool.action != "delete":
                    raise SelectionError("Must specify at least one toplevel"
                        " child redundancy in pool '%s'." % (zpool.name))

                if zpool.is_root:
                    if not found_be:
                        # Root pool with no BE, so insert one
                        self.logger.debug("Found root pool '%s' with no BE, "
                            "inserting one." % (zpool.name))

                        # Ensure BE name is unique and does not exist already
                        self._be = BE()
                        if self._be.exists:
                            raise SelectionError(
                                "BE '%s' specified in zpool '%s' already "
                                "exists. You must specify a unique "
                                "BE in the manifest." % \
                                (self._be.name, zpool.name))

                        self._be.mountpoint = self.be_mountpoint
                        zpool.insert_children(self._be)
                        found_be = True
                    else:
                        # Ensure mountpoint is set
                        if be.mountpoint is None:
                            be.mountpoint = self.be_mountpoint

            if not logical.noswap and not found_swap:
                raise SelectionError("At least one swap Zvol must exist.")

            if not logical.nodump and not found_dump:
                raise SelectionError("At least one dump Zvol must exist.")

            if not found_root_pool:
                raise SelectionError("No root pool specified.")

            if not found_be:
                raise SelectionError("No BE specified.")

    def __validate_vdev(self, zpool, child):
        '''
            Validate Vdev
            - Ensure correct number of devices for redundancy
            - Root pool contains correct redundancy type
            - Preserved pool contains no devices
        '''
        vdev_devices = self.__get_vdev_devices(zpool.name,
            child.name, self._disk_map)
        self.__validate_vdev_devices(zpool, child,
            vdev_devices)

        if not zpool.action in self.PRESERVED:
            if not vdev_devices:
                raise SelectionError(
                    "Vdev '%s' on zpool '%s' must contain at least one "
                    "device." % (child.name, zpool.name))
            elif ((not zpool.is_root and
                child.redundancy == "mirror") or \
                child.redundancy == "logmirror" or
                child.redundancy == "raidz" or
                child.redundancy == "raidz1") and \
                len(vdev_devices) < 2:
                vdev_key = zpool.name + ":" + child.name
                if vdev_key in self._vdev_added_map:
                    # Data pool where we added default child of
                    # type mirror, reset to "none"
                    self.logger.debug("Changing data redundancy"
                        " from 'mirror' to 'none'.")
                    child.redundancy = "none"
                else:
                    raise SelectionError(\
                        "Invalid %s redundancy specified in pool"
                        " '%s', child '%s'. "
                        "Must contain at least 2 devices." % \
                        (child.redundancy, zpool.name, child.name))

            elif child.redundancy == "raidz2" and \
                len(vdev_devices) < 3:
                raise SelectionError(\
                    "Invalid raidz2 redundancy specified in "
                    "pool '%s', child '%s'. "
                    "Must contain at least 3 devices." % \
                    (zpool.name, child.name))

            elif child.redundancy == "raidz3" and \
                len(vdev_devices) < 4:
                raise SelectionError(\
                    "Invalid raidz3 redundancy specified in "
                    "zpool '%s', child '%s'. "
                    "Must contain at least 4 devices." % \
                    (zpool.name, child.name))

            elif not vdev_devices:
                raise SelectionError(\
                    "Invalid '%s' redundancy specified in "
                    "zpool '%s', child '%s'. "
                    "Must contain at least 1 device." % \
                    (child.redundancy, zpool.name, child.name))

            elif zpool.is_root and len(vdev_devices) > 1:
                if child.redundancy == "none":
                    # Root pool with more than one device cannot
                    # have redundancy of "none", reset to "mirror"
                    self.logger.debug("Changing root redundancy"
                        " from 'none' to 'mirror'.")
                    child.redundancy = "mirror"
                elif child.redundancy in self.RAIDZ_REDUNDANCY:
                    raise SelectionError("Root pool redundancy"
                        " cannot be raidz*. "
                        "zpool '%s', child '%s'" % \
                        (zpool.name, child.name))
                elif child.redundancy in self.INVALID_ROOT_VDEV:
                    raise SelectionError("Root pool cannot"
                        " contain '%s' vdevs. "
                        "zpool '%s', child '%s'" % \
                        (child.redundancy, zpool.name, child.name))

            elif len(vdev_devices) == 1 and \
                child.redundancy == "mirror":
                vdev_key = zpool.name + ":" + child.name
                if zpool.is_root:
                    # Root pool with one device cannot
                    # have redundancy of "mirror", reset to "none"
                    self.logger.debug("Changing root redundancy"
                        " from 'mirror' to 'none'.")
                    child.redundancy = "none"
                elif vdev_key in self._vdev_added_map:
                    # Data pool where we added default child of
                    # type mirror, reset to "none"
                    self.logger.debug("Changing data redundancy"
                        " from 'mirror' to 'none'.")
                    child.redundancy = "none"

        if zpool.is_root and \
            child.redundancy in self.RAIDZ_REDUNDANCY:
            raise SelectionError("Root pool redundancy"
                " cannot be raidz. "
                "zpool '%s', child '%s'" % \
                (zpool.name, child.name))

        elif zpool.is_root and \
            child.redundancy in self.INVALID_ROOT_VDEV:
            raise SelectionError("Root pool cannot"
                " contain '%s' vdevs. "
                "zpool '%s', child '%s'" % \
                (child.redundancy, zpool.name, child.name))

    def __validate_vdev_devices(self, zpool, vdev, vdev_devices):
        '''
            Given a list of devices being used in this zpool/vdev, validate
            that these devices are not already being used in another zpool
            that exists and is not being destroyed or recreated by this
            install.

            self._remaining_zpool_map contains a list of devices that cannot
            be used in an install. This method assumes this has already been
            populated before calling this routine.

            Also validate that each device being used is physically greater
            than 64MB, or zpool create will fail.
        '''
        if vdev.redundancy in self.TOPLEVEL_REDUNDANCY:
            size_64mb = Size("64" + Size.mb_units)

        for device in vdev_devices:
            tmp_slice = None
            tmp_part = None
            tmp_disk = None
            if isinstance(device, Slice):
                tmp_slice = device
                if isinstance(device.parent, Partition):
                    tmp_disk = device.parent.parent
                else:
                    tmp_disk = device.parent
            elif isinstance(device, Partition):
                tmp_part = device
                tmp_disk = device.parent
            else:
                tmp_disk = device

            # Construct what device would be in zpool create
            ctd = ""
            if tmp_part is not None and tmp_slice is None:
                ctd = "p" + tmp_part.name
            elif tmp_part is None and tmp_slice is not None:
                ctd = "s" + tmp_slice.name
            ctd = ":" + tmp_disk.ctd + ctd

            matching_devs = [key for key in self._remaining_zpool_map \
                             if key.endswith(ctd)]
            if matching_devs:
                key_parts = matching_devs[0].split(':')
                raise SelectionError("Device '%s' already in use by zpool "
                                     " '%s'. Cannot be reused in zpool '%s'." %
                                     (key_parts[2], key_parts[0], zpool.name))
            else:
                # If just using disk, we need to append s0, when the pool
                # is created libzfs actually uses device s0 to create the
                # the pool, zpool status strips this s0 off when displaying
                # back to the user, but libzfs correctly returns s0.
                # So add s0 to end and check map again
                if tmp_part is None and tmp_slice is None:
                    ctd = ctd + "s0"
                    matching_devs = [key for key in self._remaining_zpool_map \
                                                    if key.endswith(ctd)]
                    if matching_devs:
                        key_parts = matching_devs[0].split(':')
                        raise SelectionError("Device '%s' already in use by "
                            "zpool '%s'. Cannot be reused in zpool '%s'." %
                            (key_parts[2], key_parts[0], zpool.name))

            if isinstance(device, Disk):
                if device.disk_prop is not None:
                    dev_size = device.disk_prop.dev_size
                else:
                    raise SelectionError("Disk device '%s' in vdev '%s' on "
                        "pool '%s' missing size specification." % \
                        (key_parts[2], vdev.name, key_parts[0]))
            else:
                dev_size = device.size

            if vdev.redundancy in self.TOPLEVEL_REDUNDANCY and \
                dev_size < size_64mb:
                raise SelectionError("Device '%s' in toplevel vdev '%s' "
                    " on zpool '%s' is less then minimum zpool device "
                    "size of 64MB." % (key_parts[2], vdev.name, key_parts[0]))

    def __compile_remaining_existing_devices_map(self, logical):
        '''
            Process list of self._discovered_zpool_map, along with
            all the zpools being defined in desired.logical, and come
            up with a unique list of devices that will exist on the system
            and cannot be specified in logical.desired.
        '''
        remaining_map = copy.copy(self._discovered_zpool_map)

        for zpool in logical.children:
            zpool_key = zpool.name + ":"
            if zpool.exists:
                # Desired zpool exists, regardless of action simply
                # remove all current devices relating to this zpool
                iter_remaining_map = copy.copy(remaining_map)
                for zpool_map_key in iter_remaining_map:
                    if zpool_map_key.startswith(zpool_key):
                        del remaining_map[zpool_map_key]
                del iter_remaining_map

        return remaining_map

    def __get_existing_zpool_map(self):
        '''
            For all zpools that have been discovered, get dictionary of
            devices for each zpool and populate private variable
            self._discovered_zpool_map.
        '''
        zpool_map = dict()

        # Cycle through existing zpool
        for zpool in self._discovered_zpools:
            # Get list of physical devices on this existing pool

            # Get dictionary of disk devices for this zpool
            # Must check zpool.exists, if get_vdev_mapping is called
            # with a pool that does not exist, zpool_get_config() cores
            # and self._discovered_zpools could be populated from tests
            if zpool.exists:
                vdev_map = vdevs._get_vdev_mapping(zpool.name)
            else:
                vdev_map = dict()
            for vdev_key in vdev_map:
                for device in vdev_map[vdev_key]:
                    # Get device ctd from end of device path
                    device_ctd = device.split('/')[-1]

                    # Create a dummy disk object for __find_disk() to work with
                    disk = Disk("foo")

                    # Retrieve the disk only portion of the ctd
                    match = re.match(DISK_RE, device_ctd, re.I)
                    if match is not None:
                        disk.ctd = match.group()

                        # Attempt to find a matching discovered disk
                        # this should always be successful
                        discovered_disk = self.__find_disk(disk)
                        if discovered_disk is not None:
                            devkey = zpool.name + ":" + disk.ctd + ":" + \
                                     device_ctd
                            zpool_map[devkey] = discovered_disk
                        else:
                            raise SelectionError("Unable to find discovered "
                                "disk '%s', used in zpool '%s'." %
                                (disk.ctd, zpool.name))
                    else:
                        # Zpool device is not a disk, must be a file
                        disk.ctd = device_ctd
                        devkey = zpool.name + ":" + device + ":" + \
                                 device_ctd
                        zpool_map[devkey] = discovered_disk
        return zpool_map

    def __validate_disks(self, desired):
        '''Process Disk components of desired tree ensuring:
           A device is uniquely identifiable as belonging to a zpool
           either via in_zpool and/or in_vdev being specified. A parent
           cannot be identifiable if it contains children, the identifiers
           must reside on the lowest child.

           - Disk validation :
               Whole-Disk, has kids - fail
               Whole-Disk, no kids, not identifiable - fail
               Whole-Disk, in root pool - fail

               Not Whole-Disk, no kids - fail
               Not Whole-Disk, has kids, is identifiable - fail as kids should
                   contain the identifying information not the disk
               Not whole-disk, has kids, not identifiable - good, process kids

               Two disks with same name, fail
               If root pool disk, ensure label is VTOC not GPT

               Disk has children, either partitions or slices must be VTOC

           - Partition validation :
               - To get to validate a partition, disk parent must be not
                 whole disk, and parent disk is not identifiable
               - Action other than create and use_existing are ignored.

               - for each create/use_existing partition :
                   - identifiable, has kids - fail should not have slices
                   - identifiable, no kids - good for non root pool
                   - identifiable, no kids - fail if root pool
                   - not identifiable, no kids - fail
                   - not identifiable, has kids - good, process kids(slices)

               - two partitions with same name on same disk, fail
               - Only one is_solaris partition exists on a disk

           - Slice validation :
               - To get to validate a slice on sparc, disk parent must be not
                 whole disk. and disk parent is not identifiable

               - Any action other than create is ignored
               - For each sparc create slices :
                   - identifiable - good
                   - identifiable, and is_swap - fail

               - For X86 slices, to get this far, parent partition must be
                 not identifiable and actioned create/use-existing
               - For each i386 create slice:
                   - identifiable - good
                   - identifiable, and is_swap - fail

               - two slices with same name on same disk, or partition, fail
               - At least one root pool slice must exist.
        '''

        # Get Disk sections
        disks = desired.get_children(class_type=Disk)
        self.logger.debug("Validating DESIRED Disks")
        self.logger.debug("Disks(Desired) =\n%s\n" %
            (self.__pretty_print_disk(disks)))

        tmp_disk_map = list()       # List of disk ctd's
        tmp_partition_map = list()  # list of disk:partiton
        tmp_slice_map = list()  # list of disk:slice or disk:partition:slice
        root_slice_found = False

        for disk in disks:
            if self.__check_disk_in_root_pool(disk) and disk.label != "VTOC":
                raise SelectionError(
                    "Root pool Disk '%s' must contain VTOC label not '%s' ." %
                    (self.__pretty_print_disk(disk), disk.label))

            # Sparc disk with slices must be VTOC labeled
            # X86 disk with partitions must also be VTOC labeled
            if disk.has_children and disk.label != "VTOC":
                if isinstance(disk.children[0], Slice):
                    raise SelectionError(
                        "Disk '%s' with %s slice(s) must contain VTOC label "
                        "not '%s' ." % (self.__pretty_print_disk(disk),
                        str(len(disk.children)), disk.label))
                else:
                    raise SelectionError(
                        "Disk '%s' with %s partition(s) must contain VTOC "
                        "label not '%s' ." % (self.__pretty_print_disk(disk),
                        str(len(disk.children)), disk.label))

            # Validate in_zpool specified and in_vdev not, but > 1 vdevs
            if disk.ctd in tmp_disk_map:
                raise SelectionError(
                    "Disk '%s' specified more than once." %
                    (self.__pretty_print_disk(disk)))

            # Add disk to temporary list map
            tmp_disk_map.append(disk.ctd)

            if disk.whole_disk:
                # Whole disk cannot be in root pool
                if self.__check_in_root_pool(disk):
                    raise SelectionError("Disk '%s', Using whole disk "
                        "and located in root pool not valid." % \
                        (self.__pretty_print_disk(disk)))

                # Whole disk cannot have children specified.
                if disk.has_children:
                    raise SelectionError("Disk '%s', Using whole disk "
                        "and has partition/slice specified is not valid." % \
                        (self.__pretty_print_disk(disk)))

                # Disk is not uniquely identifiable
                if not self.__device_is_identifiable(disk):
                    raise SelectionError("Disk '%s', Using whole disk "
                        "and not logically uniquely identifiable. "
                        "in_zpool '%s', in_vdev '%s'" % \
                        (self.__pretty_print_disk(disk), disk.in_zpool,
                        disk.in_vdev))
            else:
                # Not Whole-Disk, no kids - fail
                if len(disk.children) == 0:
                    raise SelectionError("Disk '%s' Not using whole disk "
                        "and no partition/slice specified which is invalid."
                        % (self.__pretty_print_disk(disk)))

                # Not Whole-Disk, has kids, is identifiable - fail
                if disk.has_children and \
                    self.__device_is_identifiable(disk):
                    raise SelectionError("Disk '%s', Not using whole disk, "
                        "has children and is logically uniquely identifiable"
                        " which is invalid.  in_zpool '%s', in_vdev '%s'" % \
                        (self.__pretty_print_disk(disk), disk.in_zpool,
                        disk.in_vdev))

                # Not whole-disk, has kids, not identifiable - good
                if disk.has_children and \
                    not self.__device_is_identifiable(disk):
                    # Process kids, identify should be set there
                    solaris_partition_found = False
                    for disk_kid in disk.children:
                        # Partition, check only exists once
                        if isinstance(disk_kid, Partition):
                            partkey = disk.ctd + ":" + disk_kid.name
                            if partkey in tmp_partition_map:
                                raise SelectionError("Partition '%s' "
                                    "specified twice on disk '%s'." % \
                                    (disk_kid.name,
                                    self.__pretty_print_disk(disk)))
                            tmp_partition_map.append(partkey)

                            # Ensure only one solaris partition resides on disk
                            if disk_kid.is_solaris and \
                               disk_kid.action != "delete":
                                if solaris_partition_found:
                                    raise SelectionError("Disk '%s' cannot "
                                        "contain multiple Solaris partitions."
                                        % (self.__pretty_print_disk(disk)))
                                solaris_partition_found = True

                            # Slice check only exists once on this disk/part.
                            for slc in disk_kid.children:
                                slicekey = disk.ctd + ":" + disk_kid.name + \
                                    ":" + slc.name
                                if slicekey in tmp_slice_map:
                                    raise SelectionError("Slice '%s' "
                                        "specified twice within partiton '%s'"
                                        " on disk '%s'." % \
                                        (slc.name, disk_kid.name,
                                        self.__pretty_print_disk(disk)))
                                tmp_slice_map.append(slicekey)

                                # Is identifiable, make sure not set for swap
                                if self.__device_is_identifiable(slc) and \
                                    slc.is_swap:
                                    raise SelectionError("Slice '%s' in disk "
                                        "'%s' cannot be assigned to swap and "
                                        "be part of a zpool. in_zpool '%s', "
                                        "in_vdev '%s'" % (slc.name,
                                        self.__pretty_print_disk(disk),
                                        slc.in_zpool, slc.in_vdev))

                        # Slice check only exists once on this disk
                        elif isinstance(disk_kid, Slice):
                            slicekey = disk.ctd + ":" + disk_kid.name
                            if slicekey in tmp_slice_map:
                                raise SelectionError("Slice '%s' "
                                    "specified twice on disk '%s'." % \
                                    (disk_kid.name,
                                    self.__pretty_print_disk(disk)))
                            tmp_slice_map.append(slicekey)

                            # Is identifiable, make sure not set for swap
                            if self.__device_is_identifiable(disk_kid) and \
                                disk_kid.is_swap:
                                raise SelectionError("Slice '%s' in disk "
                                    "'%s' cannot be assigned to swap and "
                                    "be part of a zpool. in_zpool '%s', "
                                    "in_vdev '%s'" % (disk_kid.name,
                                    self.__pretty_print_disk(disk),
                                    disk_kid.in_zpool, disk_kid.in_vdev))

                        # Not partition/slice throw error
                        else:
                            raise SelectionError("Invalid child element on "
                                "disk '%s' : '%s'." %
                                (self.__pretty_print_disk(disk), disk_kid))

                        # Partition, create or use_existing action
                        if isinstance(disk_kid, Partition) and \
                           disk_kid.action in \
                           ["create", "use_existing_solaris2"]:

                            # identifiable, has kids
                            if self.__device_is_identifiable(disk_kid) and \
                                disk_kid.has_children:
                                raise SelectionError("Partition '%s' on disk "
                                    "'%s' is logically uniquely "
                                    "identifiable and has slice children "
                                    "which is invalid. "
                                    "in_zpool '%s', in_vdev '%s'" % \
                                    (disk_kid.name,
                                    self.__pretty_print_disk(disk),
                                    disk_kid.in_zpool, disk_kid.in_vdev))

                            # identifiable, no kids, in root pool
                            if self.__device_is_identifiable(disk_kid) and \
                                len(disk_kid.children) == 0 and \
                                 self.__check_in_root_pool(disk_kid):
                                raise SelectionError("Partition '%s' on disk "
                                    "'%s' is logically uniquely "
                                    "identifiable with no slice children "
                                    "but is on root pool which is invalid. "
                                    "in_zpool '%s', in_vdev '%s'" % \
                                    (disk_kid.name,
                                    self.__pretty_print_disk(disk),
                                    disk_kid.in_zpool, disk_kid.in_vdev))

                            # not identifiable, no kids - fail
                            if not self.__device_is_identifiable(disk_kid) \
                               and len(disk_kid.children) == 0 \
                               and disk_kid.is_solaris:
                                raise SelectionError("Partition '%s' on disk "
                                    "'%s' is not logically uniquely "
                                    "identifiable and has no slice children "
                                    "whish is invalid. "
                                    "in_zpool '%s', in_vdev '%s'" % \
                                    (disk_kid.name,
                                    self.__pretty_print_disk(disk),
                                    disk_kid.in_zpool, disk_kid.in_vdev))

                            # has kids, check if root pool slice is here
                            # Creation of VTOC slices not in a pool is allowed.
                            if not self.__device_is_identifiable(disk_kid) \
                               and disk_kid.has_children:
                                for slc in disk_kid.children:
                                    if isinstance(slc, Slice) and \
                                        slc.action == "create":
                                        # X86 Slice not identifiable
                                        if self.__device_is_identifiable(slc) \
                                            and self.__check_in_root_pool(slc):
                                            root_slice_found = True
                                    elif not isinstance(slc, Slice):
                                        raise SelectionError("Invalid child "
                                          "element on partition '%s' : "
                                          "'%s'." % (disk_kid.name, str(slc)))

                        # Slice, create action, check if in root pool.
                        # Creation of VTOC slices not in a pool is allowed.
                        elif isinstance(disk_kid, Slice) and \
                            disk_kid.action == "create":
                            # Sparc Slice identifiable and in root pool
                            if self.__device_is_identifiable(disk_kid) and \
                               self.__check_in_root_pool(disk_kid):
                                root_slice_found = True

        # At least one root slice must be found over all disks
        if not root_slice_found:
            raise SelectionError("Could not find root pool slice on any disk. "
                "Valid Solaris installations must contain at least one "
                "root pool slice.")

    def __device_is_identifiable(self, device):
        '''A device can be uniquely identified by using one or both of
           it's in_zpool and in_vdev attributes.

           Input :
               device - A disk, partition or slice device Object

           Output :
               None : if not uniquely identifiable in logical section
               zpool/vdev tuple : Unique logical location
        '''
        unique_zpool = None
        unique_vdev = None

        # Both in_zpool and in_vdev are specified
        if device.in_zpool is not None and device.in_vdev is not None:
            vdev_key = device.in_zpool + ":" + device.in_vdev
            if vdev_key not in self._vdev_map:
                self.logger.debug("Device '%s' identification failed : "
                    "Combination does not exist. "
                    "in_zpool '%s', in_vdev '%s'." % \
                    (device.name, device.in_zpool, device.in_vdev))
                return None
            unique_zpool = self._zpool_map[device.in_zpool]
            unique_vdev = self._vdev_map[vdev_key]

        # in_zpool specified, in_vdev not specified
        elif device.in_zpool is not None and device.in_vdev is None:
            if device.in_zpool not in self._zpool_map:
                self.logger.debug("Device '%s' identification failed. "
                    "Pool does not exist. in_zpool '%s', in_vdev '%s'." % \
                    (device.name, device.in_zpool, device.in_vdev))
                return None

            unique_zpool = self._zpool_map[device.in_zpool]

            pool_vdevs = self.__get_vdevs_in_zpool(device.in_zpool)
            if len(pool_vdevs) > 1:
                self.logger.debug("Device '%s' identification failed. "
                    "More than one vdev in zpool. "
                    "in_zpool '%s', in_vdev '%s'." % \
                    (device.name, device.in_zpool, device.in_vdev))
                return None

            elif len(pool_vdevs) == 1:
                # Only one vdev in this zpool so therefore device is
                # uniquely identifiable, set in_vdev on this device
                # for completeness.
                device.in_vdev = pool_vdevs[0].name
                unique_vdev = pool_vdevs[0]

            else:
                # Pool has no vdevs, this should not be the case at
                # this juncture, throw exception.
                raise SelectionError("Zpool '%s' does not contain any "
                    "Vdev's." % (device.in_zpool))

        # in_zpool not specified, in_vdev specified
        elif device.in_zpool is None and device.in_vdev is not None:
            # The only way a device can be uniquely identified in this
            # Scenario is if the vdev name specified exists uniquely
            # when compared across all pools
            for vdev_key in self._vdev_map:
                if self._vdev_map[vdev_key].name == device.in_vdev:
                    if not unique_vdev:
                        zpool_name = vdev_key.split(":")[0]
                        unique_zpool = self._zpool_map[zpool_name]
                        unique_vdev = self._vdev_map[vdev_key]
                    else:
                        # 2nd Vdev with this name, so not unique
                        self.logger.debug(
                            "Device '%s' identification failed. Vdev not "
                            "unique. in_zpool '%s', in_vdev '%s'." % \
                            (device.name, device.in_zpool, device.in_vdev))
                        return None

            # Vdev not found at all
            if not unique_vdev:
                self.logger.debug("Device '%s' identification failed. "
                    "Vdev not found. in_zpool '%s', in_vdev '%s'." % \
                    (device.name, device.in_zpool, device.in_vdev))
                return None
            else:
                # We've found one unique vdev, set the device in_zpool
                # for completeness.
                device.in_zpool = unique_zpool.name

        # Neither are set so not identifiable
        else:
            return None

        return (unique_zpool, unique_vdev)

    def __get_vdevs_in_zpool(self, zpoolname):
        '''Given a zpool name, retrieve the list of vdevs in this
           pool from the vdev_map.
        '''

        pool_vdevs = list()
        start_vdev_key = zpoolname + ":"
        for vdev_key in self._vdev_map:
            if vdev_key.startswith(start_vdev_key):
                pool_vdevs.append(self._vdev_map[vdev_key])

        return pool_vdevs

    @staticmethod
    def __get_zpool_redundancies(zpool):
        '''Traverse all vdev children in a zpool returning a unique list
           of redundancy types defined in this zpool.
        '''
        vdev_redundancies = dict()

        for vdev in zpool.children:
            if isinstance(vdev, Vdev):
                vdev_redundancies[vdev.redundancy] = True

        return vdev_redundancies.keys()

    def __get_vdev_devices(self, zpool_name, vdev_name, device_map):
        '''Get list of devices with this vdev name.
           If not set then recursively check for in_vdev setting on children.

           Cater for device_map being either a list or a dictionary.

           If in_vdev set on both parent and children, throw exception.

           Device can be identified as part of a vdev either via in_vdev or
           in_zpool or both. As long as it's uniquely identifiable.

           Remember a vdev name is only unique within's it's zpool, different
           zpool's can contain vdevs with the same name.
        '''
        vdev_devices = list()

        if isinstance(device_map, dict):
            tmp_device_map = device_map.values()
        elif self.__is_iterable(device_map):
            tmp_device_map = device_map
        else:
            # Return now, as nothing to traverse
            return vdev_devices

        for device in tmp_device_map:
            identity_tuple = self.__device_is_identifiable(device)
            if identity_tuple:
                if (isinstance(device, Disk) or
                    isinstance(device, Partition)) and device.has_children:
                    # If disk or partition and has children, and is
                    # identifiable this is an error, as one/all of the
                    # children should contain identifying information
                    device_str = self.__get_device_type_string(device)
                    raise SelectionError("%s '%s' is uniquely identifiable "
                        "and it has children. Invalid, as children should "
                        "contain identifying information. "
                        "in_zpool '%s', in_vdev '%s'." % (device_str,
                        device.name, device.in_zpool, device.in_vdev))

                # Append this device if the found device matches both
                # zpool and vdev names
                if identity_tuple[0].name == zpool_name and \
                    identity_tuple[1].name == vdev_name:
                    vdev_devices.append(device)

            else:
                if device.in_zpool is not None or device.in_vdev is not None:
                    # Throw exception, as cannot identify uniquely yet
                    # some logical identification information present
                    device_str = self.__get_device_type_string(device)

                    if isinstance(device, Slice):
                        # Only raise exception if not a swap slice and
                        # slice is being not being deleted.
                        if device.action != "delete" and not device.is_swap:
                            raise SelectionError("Logical information present "
                                "on %s '%s', but is not enough to uniquely "
                                "identify it. in_zpool '%s', in_vdev '%s'." %
                                (device_str, device.name, device.in_zpool,
                                 device.in_vdev))
                    else:
                        raise SelectionError("Logical information present on "
                            "%s '%s', but is not enough to uniquely identify "
                            "it. in_zpool '%s', in_vdev '%s'." % (device_str,
                            device.name, device.in_zpool, device.in_vdev))

                if (isinstance(device, Disk) or
                    isinstance(device, Partition)) and device.has_children:
                    # Device has children which should identify location
                    tmp_devices = self.__get_vdev_devices(zpool_name,
                        vdev_name, device.children)
                    for dev in tmp_devices:
                        vdev_devices.append(dev)

        return vdev_devices

    @staticmethod
    def __get_device_type_string(device):
        '''Get a descriptive string for the device'''
        if isinstance(device, Disk):
            device_str = "Disk"
        elif isinstance(device, Partition):
            device_str = "Partition"
        elif isinstance(device, Slice):
            device_str = "Slice"
        return device_str

    def __check_disk_in_root_pool(self, disk):
        '''Tests if a specified disk is in the root pool
           if the disk does not have in_zpool, in_vdev specified
           then start processing children. If no chilcren throw
           error.
           Check all children, and if any one of them are in the root
           pool return true, otherwise return false.
        '''
        if self.__check_in_root_pool(disk):
            return True
        elif disk.has_children:
            for disk_kid in disk.children:
                if self.__check_in_root_pool(disk_kid):
                    return True

                if isinstance(disk_kid, Partition) and disk_kid.children > 0:
                    for slc in disk_kid.children:
                        if self.__check_in_root_pool(slc):
                            return True
        return False

    def __check_in_root_pool(self, device):
        '''Tests if a device (disk/partition/slice) is in the root pool.
        '''

        if device.in_zpool == self._root_pool.name:
            return True

        rpool_vdev_id = "%s:%s" % \
            (self._root_pool.name, device.in_vdev)

        if device.in_zpool is None and \
           rpool_vdev_id in self._vdev_map:
            # Assumption is we've validated the uniqueness of vdev
            # specification in the object earlier in __check_valid_zpool_vdev()
            return True

        return False

    def __handle_partition(self, partition, new_disk, discovered_disk):
        '''Handle the partition as specified in the manifest.

           Will return a new Partition object to be inserted in the DESIRED
           tree such that Target Instantiation is able to perform.
        '''
        # Ensure this is an i386 machine if partitions are specified.
        if platform.processor() != "i386":
            raise SelectionError(
                "Cannot specify partitions on %s machine architecture." % \
                (platform.processor()))

        existing_partition = discovered_disk.get_first_child(
            partition.name, class_type=Partition)

        if partition.action in ["preserve", "delete", "use_existing_solaris2"]:
            if existing_partition is None:
                # If it's delete action, just do nothing since it's not really
                # an issue to delete something that's not there.
                if partition.action == "delete":
                    self.logger.warn(
                        "Attempt to delete non-existant partition"
                        " %s on disk %s ignored" % (partition.name,
                        self.__pretty_print_disk(discovered_disk)))
                    # Return now since there's nothing to do.
                    return
                else:
                    raise SelectionError(
                        "Cannot %s partition %s that doesn't exist on disk %s"
                        % (partition.action, partition.name,
                           self.__pretty_print_disk(discovered_disk)))
            else:
                # Do nothing, just copy over.
                new_partition = copy.copy(existing_partition)
                new_partition.action = partition.action

                # Initialize logical information on deleted partitions
                if new_partition.action == "delete":
                    new_partition.in_zpool = None
                    new_partition.in_vdev = None

        elif partition.action == "create":
            if existing_partition is not None:
                self.logger.warn(
                    "Creating partition %s on disk %s will "
                    "destroy existing data." % \
                    (partition.name,
                     self.__pretty_print_disk(discovered_disk)))

            new_partition = copy.copy(partition)
        else:
            raise SelectionError("Unexpected action '%s' on partition %s"
                % (partition.name, partition.action))

        if partition.action in ["use_existing_solaris2", "create"]:
            # Mark partition as ACTIVE, if it's Solaris
            if new_partition.is_solaris:
                # Need to set attribute, since Partition.change_bootid
                # manipulates the parent object, which there isn't yet...
                # Only applies to primary partitions
                if partition.is_primary:
                    new_partition.bootid = Partition.ACTIVE

            if new_partition.size.sectors == 0 or \
               new_partition.start_sector is None:
                # According to DTD, if size is not specified, should use
                # parents size information.
                # If start_sector is None, try to allocate size into a gap.
                if partition.action == "create":
                    if partition.is_logical:
                        gaps = new_disk.get_logical_partition_gaps()
                    else:
                        gaps = new_disk.get_gaps()
                    largest_gap = None
                    for gap in gaps:
                        if new_partition.start_sector is None and \
                           new_partition.size.sectors != 0 and \
                           gap.size >= new_partition.size:
                            # Specified a size with only start_sector missing.
                            new_partition.start_sector = gap.start_sector
                            break
                        if largest_gap is None or \
                           gap.size.sectors > largest_gap.size.sectors:
                            largest_gap = gap
                    else:
                        # Will be skipped if searching for a gap to insert a
                        # partition of a given size succeeds.
                        if largest_gap is None or \
                           largest_gap.size < \
                           self.controller.minimum_target_size or \
                           largest_gap.size < new_partition.size:
                            raise SelectionError("Failed to find gap on disk"
                                " of sufficient size to put partition"
                                " %s in to" % (new_partition.name))
                        new_partition.start_sector = largest_gap.start_sector
                        new_partition.size = largest_gap.size
                else:
                    raise SelectionError(
                        "Cannot find size of existing partition '%s' on "
                        "discovered_disk '%s'"
                        % (new_partition.name, discovered_disk.name))

            # Need to do more than just copy
            if discovered_disk.disk_prop is not None and \
               new_partition.size > discovered_disk.disk_prop.dev_size:
                raise SelectionError(
                    "Partition %s has a size larger than the disk %s" %
                    (new_partition.name,
                    self.__pretty_print_disk(discovered_disk)))

            # Insert partition now, since shadowlist validation will require
            # that the disk be known for partitions or children.
            new_disk.insert_children(new_partition)

            # Check error service for errors as if we insert slices errors
            # Generated from this insert will get cleared both having the
            # the same mod_id.
            errors = errsvc.get_all_errors()
            # Found errors and they cannot be ignored
            if errors:
                # Print desired contents to log
                existing_desired = \
                    self.doc.persistent.get_first_child(Target.DESIRED)
                if existing_desired:
                    self.logger.debug("Desired =\n%s\n" % \
                        (str(existing_desired)))
                self.logger.debug("Partition =\n%s\n" % (str(new_partition)))
                errstr = \
                    "Following errors occurred processing partition :\n%s" % \
                    (str(errors[0]))
                raise SelectionError(errstr)

            # Only process solaris partitions
            if partition.is_solaris:
                if not partition.has_children:
                    # If it's a root pool, or we have a partition that's not in
                    # a pool we assume it should be in the root pool.
                    if self.__check_in_root_pool(partition) \
                       or (partition.in_zpool is None and \
                           partition.in_vdev is None and \
                           self._root_pool is not None):

                        # Need to add a slice since a root pool cannot exist on
                        # partition vdevs, must be slice vdevs
                        start = 1  # Will be rounded up to cylinder by TI
                        slice_size = new_partition.size.sectors
                        new_slice = new_partition.add_slice("0", start,
                            slice_size, Size.sector_units, force=True)

                        if partition.in_zpool is None and \
                           partition.in_vdev is None:

                            # Assume it should be in the root pool since
                            # nothing specific provided in the manifest
                            new_slice.in_zpool = self._root_pool.name
                            if self._root_vdev is not None:
                                new_slice.in_vdev = self._root_vdev.name
                        else:
                            # Copy in_zpool/vdev to slice, and remove from
                            # partition.
                            new_slice.in_zpool = new_partition.in_zpool
                            new_slice.in_vdev = new_partition.in_vdev
                            new_partition.in_zpool = None
                            new_partition.in_vdev = None

                else:
                    self.__handle_slices(partition.children,
                                         new_partition, existing_partition)
        else:
            # Insert partition now, since shadowlist validation will require
            # that the disk be known for partitions or children.
            new_disk.insert_children(new_partition)

        return new_partition

    def __handle_slice(self, orig_slice, parent_object, existing_parent_obj):
        '''Handle the slice as specified in the manifest.

           Will return a new Slice object to be inserted in the DESIRED
           tree such that Target Instantiation is able to perform.
        '''
        if orig_slice.name == "2":
            # Skip s2 definition, shouldn't be there, and Target Instantiation
            # will create
            self.logger.warning("Skipping orig_slice 2 definition")
            return None

        if existing_parent_obj is not None:
            existing_slice = existing_parent_obj.get_first_child(
                                    orig_slice.name, class_type=Slice)
        else:
            existing_slice = None

        if orig_slice.action in ["preserve", "delete"]:
            if existing_slice is None:
                # If it's delete action, just do nothing since it's not really
                # an issue to delete something that's not there.
                if orig_slice.action == "delete":
                    if isinstance(parent_object, Disk):
                        self.logger.warn(
                            "Attempt to delete non-existant slice"
                            " %s on disk %s ignored" %
                            (orig_slice.name,
                            self.__pretty_print_disk(parent_object)))
                    else:
                        self.logger.warn(
                            "Attempt to delete non-existant slice"
                            " %s on partition '%s', disk %s ignored" %
                            (orig_slice.name, parent_object.name,
                            self.__pretty_print_disk(parent_object.parent)))
                    # Return now since there's nothing to do.
                    return None
                else:
                    if isinstance(parent_object, Disk):
                        raise SelectionError(
                            "Cannot %s slice %s that doesn't exist on disk %s"
                            % (orig_slice.action, orig_slice.name,
                            self.__pretty_print_disk(parent_object)))
                    else:
                        raise SelectionError(
                            "Cannot %s slice %s that doesn't exist on "
                            "partition %s, disk %s" % (orig_slice.action,
                            orig_slice.name, parent_object.name,
                            self.__pretty_print_disk(parent_object.parent)))
            else:
                # Do nothing, just copy over.
                new_slice = copy.copy(existing_slice)
                new_slice.action = orig_slice.action
                # For slices being deleted initialize out logical info. This
                # Will ensure later on at least one slice gets assigned to the
                # root pool.
                if new_slice.action == "delete":
                    new_slice.in_zpool = None
                    new_slice.in_vdev = None

        elif orig_slice.action == "create":
            if existing_slice is not None:
                if isinstance(parent_object, Disk):
                    self.logger.warn(
                        "Creating slice %s on disk %s will "
                        "destroy existing data." % \
                        (orig_slice.name,
                        self.__pretty_print_disk(parent_object)))
                else:
                    self.logger.warn(
                        "Creating slice %s on partition %s, disk %s will "
                        "destroy existing data." % \
                        (orig_slice.name, parent_object.name,
                        self.__pretty_print_disk(parent_object.parent)))

            new_slice = copy.copy(orig_slice)
        else:
            raise SelectionError("Unexpected action '%s' on slice %s"
                % (orig_slice.name, orig_slice.action))

        if new_slice.action == "create":
            if isinstance(parent_object, Disk):
                if parent_object.disk_prop is not None and \
                   new_slice.size > parent_object.disk_prop.dev_size:
                    raise SelectionError(
                        "Slice %s has a size larger than the disk %s" %
                        (new_slice.name,
                         self.__pretty_print_disk(parent_object)))
            else:
                # It's a partition
                if parent_object.size is not None and \
                   new_slice.size > parent_object.size:
                    raise SelectionError(
                        "Slice %s has a size larger than the containing "
                        "partition %s" % (new_slice.name,
                        parent_object.name))

        if new_slice.action == "create" and (new_slice.size.sectors == 0 or
           new_slice.start_sector is None):
            # According to DTD, if size is not specified, should use
            # parents size information.

            if new_slice.size.sectors == 0 or new_slice.start_sector is None:
                # According to DTD, if size is not specified, should use
                # parents size information.
                # If start_sector is None, try to allocate size into a gap.
                if orig_slice.action == "create":
                    gaps = parent_object.get_gaps()
                    largest_gap = None
                    for gap in gaps:
                        if new_slice.start_sector is None and \
                           new_slice.size.sectors > 0 and \
                           gap.size >= new_slice.size:
                            # Specified a size with only start_sector missing.
                            new_slice.start_sector = gap.start_sector
                            break
                        if largest_gap is None or \
                           gap.size.sectors > largest_gap.size.sectors:
                            largest_gap = gap
                    else:
                        # Will be skipped if searching for a gap to insert a
                        # slice of a given size succeeds.
                        if largest_gap is None or \
                           largest_gap.size < \
                           self.controller.minimum_target_size:
                            raise SelectionError("Failed to find gap on disk"
                                " of sufficient size to put slice"
                                " %s in to" % (new_slice.name))
                        new_slice.start_sector = largest_gap.start_sector
                        new_slice.size = largest_gap.size

        return new_slice

    def __handle_slices(self, slices, new_parent_obj, existing_parent_obj):
        '''Process list of slices and attach to new_parent_obj as children.

           Returns a list of new slices.
        '''
        # Specifics in manifest take precedence, so
        # if they exist already, ignore them.
        # In wipe_disk scenario we don't want to merge
        if existing_parent_obj is not None and not self._wipe_disk and \
            ((isinstance(new_parent_obj, Disk)) or \
             (isinstance(new_parent_obj, Partition) and \
              new_parent_obj.action == "use_existing_solaris2")):
            tmp_slices = list()
            for exist_slice in existing_parent_obj.children:
                skip_slice = False
                for mf_slice in slices:
                    if mf_slice.name == exist_slice.name:
                        # Already inserted, skip
                        break
                else:
                    slice_copy = copy.copy(exist_slice)
                    # Remove in_zpool/in_vdev values
                    # because these should exist in
                    # manifest but don't and will cause
                    # validations to fail.
                    slice_copy.in_zpool = None
                    slice_copy.in_vdev = None

                    tmp_slices.append(slice_copy)

            # Temporarily skip validation since
            # may cause validation failures
            new_parent_obj.validate_children = False
            new_parent_obj.insert_children(tmp_slices)
            new_parent_obj.validate_children = True

        # Need to handle all preserved slices first inserting them into
        # new parent, this ensures get_gaps works for newly created slices
        for orig_slice in [s for s in slices if s.action == "preserve"]:
            new_slice = self.__handle_slice(orig_slice, new_parent_obj,
                                            existing_parent_obj)
            if new_slice is not None:
                new_parent_obj.insert_children(new_slice)

        # While processing slices, remember whether we found
        # any slices with an in_zpool or in_vdev, and if not
        # then we will use the first large enough slice.
        first_large_slice = None
        found_zpool_vdev_slice = False
        for orig_slice in [s for s in slices if s.action != "preserve"]:
            new_slice = self.__handle_slice(orig_slice, new_parent_obj,
                                            existing_parent_obj)
            if new_slice is not None:
                new_parent_obj.insert_children(new_slice)
                if new_slice.in_zpool is None and \
                   new_slice.in_vdev is None:
                    if not new_slice.is_swap and \
                       first_large_slice is None and \
                       new_slice.action == "create" and \
                       new_slice.size >= self.controller.minimum_target_size:
                        # Remember the first sufficiently large slice thats
                        # got a create or use_existing action
                        first_large_slice = new_slice
                else:
                    found_zpool_vdev_slice = True

        # Check to see if we didn't find any specific references to vdevs
        # Sets in_zpool/in_vdev on at least one slice, do not set on a slice
        # that has in_use set to swap
        if self._is_generated_root_pool and not found_zpool_vdev_slice:
            if first_large_slice is not None:
                # Set in_zpool/in_vdev on slice, and remove from
                # disk parent object (just in case)
                first_large_slice.in_zpool = self._root_pool.name
                if self._root_vdev is not None:
                    first_large_slice.in_vdev = self._root_vdev.name
                new_parent_obj.in_zpool = None
                new_parent_obj.in_vdev = None
            else:
                raise SelectionError(
                    "No slice large enough to install to was found on disk")

    def __handle_disk(self, disk):
        '''Handle a disk object.

           Find the disk in the discovered tree, take a copy, and then if
           necessary add/remove partitions based on version passed that came
           from the manifest.

           Returns: the new disk to be inserted into the DESIRED Tree
        '''

        self.logger.debug("Processing disk : %s" %
            self.__pretty_print_disk(disk))

        ret_disk = None
        errsvc.clear_error_list()

        discovered_disk = self.__find_disk(disk)

        if discovered_disk is None:
            raise SelectionError(
               "Unable to locate the disk '%s' on the system." %
                self.__pretty_print_disk(disk))

        if discovered_disk.ctd in self._disk_map:
            # Seems that the disk is specified more than once in the manifest!
            raise SelectionError(
                "Disk '%s' matches already used disk '%s'." %
                (self.__pretty_print_disk(disk), discovered_disk.name))

        # Check that in_zpool and in_vdev values from manifest are valid
        self.__check_valid_zpool_vdev(disk)
        self._wipe_disk = False

        if disk.whole_disk and not disk.has_children:
            # Traditional whole_disk scenario where we apply default layout
            # Only copy the disk, not it's children.
            disk_copy = copy.copy(discovered_disk)
            self._disk_map[disk_copy.ctd] = disk_copy
            self.logger.debug("Using Whole Disk")
            if disk.in_zpool is None and disk.in_vdev is None:
                self.logger.debug("Zpool/Vdev not specified")
                if self._is_generated_root_pool:
                    self.logger.debug("Assigning to temporary root pool")
                    # Assign to temporary root pool if one exists
                    disk.in_zpool = self._root_pool.name
                    disk.in_vdev = self._root_vdev.name
                elif self._root_pool is not None:
                    # Assign to real root pool if one exists
                    disk.in_zpool = self._root_pool.name

            if not self.__check_in_root_pool(disk):
                self.logger.debug("Disk Not in root pool")
                # We can leave it for ZFS to partition itself optimally
                disk_copy.whole_disk = True
                # Add vdev/zpool values to disk_copy
                disk_copy.in_zpool = disk.in_zpool
                disk_copy.in_vdev = disk.in_vdev
            else:
                disk_copy.whole_disk = False
                # When bug : 7037884 we can then add this back and support
                # The Changing of a GPT disk to VTOC automatically
                # disk_copy.label = "VTOC"
                self.logger.debug("Disk in root pool")

                # Layout disk using partitions since root pools can't use
                # EFI/GPT partitioned disks to boot from yet.
                self.logger.debug("Whole Disk, applying default layout")
                root_vdev = None
                if self._root_vdev is not None:
                    root_vdev = self._root_vdev.name
                elif disk.in_vdev is not None:
                    # If the disk specified a vdev, copy it.
                    root_vdev = disk.in_vdev
                self.controller.apply_default_layout(disk_copy, False, True,
                    in_zpool=self._root_pool.name, in_vdev=root_vdev)
            ret_disk = disk_copy
        else:
            if disk.whole_disk and disk.has_children:
                # Whole disk of True and disk has children interpreted as
                # wipe disk and replace with this layout.
                self._wipe_disk = True

            # Copy disk
            # merging of partitions and slices from manifest with existing
            # layouts is only done if not wiping the disk.
            disk_copy = copy.copy(discovered_disk)
            self._disk_map[disk_copy.ctd] = disk_copy

            # Get partitions and slices from manifest version of Disk
            partitions = disk.get_children(class_type=Partition)
            slices = disk.get_children(class_type=Slice)

            # Do some basic sanity checks

            # If not partitions, but have slices, fail now, if i386
            if platform.processor() == "i386" and not partitions and slices:
                raise SelectionError("Invalid specification of slices "
                        "outside of partition on the %s platform"
                        % (platform.processor()))

            # If partitions, fail now, if not i386
            if platform.processor() != "i386" and partitions:
                raise SelectionError("Invalid specification of partitions "
                        "on this %s platform" % (platform.processor()))

            if (platform.processor() == "i386" and not partitions) or \
               (platform.processor() != "i386" and not slices):
                raise SelectionError(
                    "If whole_disk is False, you need to provide"
                    " information for partitions or slices")

            # Disk with children either x86 or sparc must at the moment
            # have a VTOC label, GPT is only supported on whole disk
            # scenario with no children. Set label to be VTOC
            # When bug : 7037884 we can then add this back and support
            # The Changing of a GPT disk to VTOC automatically
            #disk_copy.label = "VTOC"

            if partitions:  # On X86
                # Process partitions, checking for use_existing_solaris2
                for partition in partitions:
                    # If there is no name specified only seek if no name
                    # provided.
                    if not partition.name and \
                       partition.action == "use_existing_solaris2":
                        # Pre-empt this by replacing it with a discovered
                        # Solaris2 partition if one exists
                        solaris_partition = None
                        for existing_partition in discovered_disk.children:
                            if existing_partition.is_solaris:
                                solaris_partition = existing_partition

                        if solaris_partition is None:
                            raise SelectionError(
                                "Cannot find a pre-existig Solaris "
                                "partition on disk %s"
                                % (self.__pretty_print_disk(discovered_disk)))
                        else:
                            # Found existing solaris partition to process
                            tmp_partition = copy.copy(solaris_partition)
                            # Ensure partition action maintained.
                            tmp_partition.action = partition.action
                            if not partition.has_children:
                                if solaris_partition.has_children:
                                    # Because no slices are being specified in
                                    # the manifest we have to assume we are to
                                    # create a slice for root.
                                    # TODO: Should this be looking for a gap?
                                    self.logger.warn(
                                        "Existing partition's slices are not "
                                        "being preserved")

                                # Temporarily skip validation since
                                # tmp_partition not yet in disk and will cause
                                # failures.
                                tmp_partition.validate_children = False

                                # Add a slice 0 for the root pool
                                # Size calculated automatically later.
                                tmp_slice = tmp_partition.add_slice("0", 1, 0,
                                    Size.sector_units, force=True)
                                tmp_partition.validate_children = True

                                # Assign to root pool
                                tmp_slice.in_zpool = self._root_pool.name
                                if self._root_vdev is not None:
                                    tmp_slice.in_vdev = self._root_vdev.name

                            else:
                                # Specifics in manifest take precedence, so
                                # copy first.
                                tmp_slices = list()
                                for mf_slice in partition.children:
                                    tmp_slices.append(copy.copy(mf_slice))

                                # Only merge partitions if not wiping disk
                                if not self._wipe_disk:
                                    for exist_slice in \
                                        solaris_partition.children:
                                        skip_slice = False
                                        for mf_slice in partition.children:
                                            if mf_slice.name == \
                                               exist_slice.name:
                                                # Already inserted, skip
                                                break
                                        else:
                                            slice_copy = copy.copy(exist_slice)
                                            # Remove in_zpool/in_vdev values
                                            # because these should exist in
                                            # manifest but don't and will
                                            # cause validations to fail.
                                            slice_copy.in_zpool = None
                                            slice_copy.in_vdev = None

                                            tmp_slices.append(slice_copy)

                                # Temporarily skip validation since
                                # tmp_partition not yet in disk and will cause
                                # failures.
                                tmp_partition.validate_children = False
                                tmp_partition.insert_children(tmp_slices)
                                tmp_partition.validate_children = True

                            # Do susbstitution
                            partitions.remove(partition)
                            partitions.insert(int(tmp_partition.name),
                                tmp_partition)
                            # Break now, since partitions list has changed.
                            break

                # Only merge partitions if not wiping disk
                if not self._wipe_disk:
                    # Copy over any existing partitions, if they are not in the
                    # manifest, since the manifest takes priority.
                    # Sort byname to ensure we handle primaries first.
                    skip_existing_logicals = False
                    for existing_partition in \
                        sorted(discovered_disk.children, \
                            key=attrgetter("name")):
                        for mf_partition in partitions:
                            if mf_partition.name == existing_partition.name:
                                if existing_partition.is_extended and \
                                mf_partition.action in ["create", "delete"]:
                                    # If we're replacing an extended partition
                                    # then we need to ensure any existing
                                    # logicals are not copied over,
                                    # effectively deleting them.
                                    skip_existing_logicals = True
                                break
                        else:
                            # Copy everything else, unless it's a logical and
                            # we're supposed to be skipping them.
                            if not (existing_partition.is_logical and
                                    skip_existing_logicals):
                                partitions.append(
                                    copy.copy(existing_partition))
                                # Also insert to new disk so gaps calculations
                                # work
                                disk_copy.insert_children(
                                    copy.copy(existing_partition))

                extended_partitions = [p for p in partitions if p.is_extended]
                if len(extended_partitions) > 1:
                    raise SelectionError(
                        "It is only possible to have at most 1 extended"
                        " partition defined")

                for partition in partitions:
                    if not self._wipe_disk:
                        if disk_copy.get_first_child(partition.name) \
                           is not None:
                            # Skip this, we've already processed it above.
                            continue

                    # Ensure partition is set to be in temporary root pool
                    # __handle_partition() relies on this.
                    if partition.is_solaris:
                        if self._is_generated_root_pool \
                           and not partition.has_children \
                           and partition.action == "create" \
                           and partition.in_zpool is None \
                           and partition.in_vdev is None:
                            # Assign to temporary root pool
                            partition.in_zpool = self._root_pool.name
                            partition.in_vdev = self._root_vdev.name

                    # Process partitions, and contained slices
                    new_partition = self.__handle_partition(partition,
                        disk_copy, discovered_disk)

                    # Insertion to disk done in __handle_partition()

            else:
                # Can assume we're on SPARC machine now.
                if len(slices) == 1 and slices[0].name == "2":
                    # There is only one slice we need to check to see if
                    # it's slice "2". If it is we need to add a slice "0"
                    # and set in_vdev and in_zpool.
                    # TODO: This will need to be updated for GPT when ready
                    # Add a slice
                    start = 1  # Will be rounded up to cylinder by TI
                    slice_size = \
                      disk_copy.disk_copy_prop.dev_size.sectors - start

                    new_slice = disk_copy.add_slice("0", start,
                        slice_size, Size.sector_units, force=True)
                    if slices[0].in_vdev is not None:
                        new_slice.in_vdev = slices[0].in_vdev
                    if self._root_pool is not None:
                        new_slice.in_zpool = self._root_pool.name
                else:
                    self.__handle_slices(slices, disk_copy, discovered_disk)

            ret_disk = disk_copy

        self.logger.debug("Finished processing disk : %s" %
            self.__pretty_print_disk(disk))

        # Check error service for errors
        errors = errsvc.get_all_errors()

        # Found errors and they cannot be ignored
        if errors:
            # Print desired contents to log
            existing_desired = \
                self.doc.persistent.get_first_child(Target.DESIRED)
            if existing_desired:
                self.logger.debug("Desired =\n%s\n" % (str(existing_desired)))
            self.logger.debug("Disk =\n%s\n" % (str(ret_disk)))
            errstr = "Following errors occurred processing disks :\n%s" % \
                (str(errors[0]))
            raise SelectionError(errstr)

        return ret_disk

    def __create_temp_logical_tree(self, existing_logicals):
        '''Create a set of logicals that we will use should there be no other
           logicals defined in the manifest.
        '''
        if existing_logicals:
            # Add Zpool to existing logical, pick first one
            logical = existing_logicals[0]
        else:
            logical = None

        logical = self.controller.apply_default_logical(logical,
            self.be_mountpoint, redundancy="mirror",
            unique_zpool_name=not self.dry_run)

        # There may be more than one pool in this logical, so need to
        # iterate over all pools breaking when root pool found.
        zpools = logical.get_children(class_type=Zpool)
        for zpool in zpools:
            if zpool.is_root:
                break
        else:
            # This should never happen as the controller method
            # apply_default_logical, will have created a root pool.
            raise SelectionError("Failed to find controller created root pool")

        vdev = zpool.get_first_child(class_type=Vdev)
        be = zpool.get_first_child(class_type=BE)

        # Set instance variables
        self._is_generated_root_pool = True
        self._root_pool = zpool
        self._root_vdev = vdev
        self._be = be
        # Add pool to maps so final validations will work
        self._zpool_map[zpool.name] = zpool
        vdev_key = zpool.name + ":" + vdev.name
        self._vdev_map[vdev_key] = vdev

        return logical

    def __cleanup_temp_logical(self, logical, existing_logicals):
        if not self._is_generated_root_pool:
            return

        if logical not in existing_logicals:
            logical.delete()
        else:
            logical.delete_children(self._root_pool)

        # Remove pool from maps since we're not using it.
        del self._zpool_map[self._root_pool.name]
        vdev_key = self._root_pool.name + ":" + self._root_vdev.name
        del self._vdev_map[vdev_key]
        # Reset instance variables
        self._is_generated_root_pool = False
        self._root_pool = None
        self._root_vdev = None
        self._be = None

    def __handle_target(self, target):
        '''Process target section in manifest'''

        # Reset all local map information
        self.__reset_maps()

        new_desired_target = None
        logical_inserted = False
        skip_disk_processing = False

        # Get Logical sections
        logicals = target.get_children(class_type=Logical)

        # It's possible that there are no logicial sections.
        if logicals:
            for logical in logicals:
                new_logical = self.__handle_logical(logical)
                if new_logical is not None:
                    if new_desired_target is None:
                        new_desired_target = self.__get_new_desired_target()
                    new_desired_target.insert_children(new_logical)

        if new_desired_target is None:
            all_whole_disk = None

            # Check if all disks are specified as whole disk and they
            # don't have logical identifiers, and finally that they don't
            # have any children.
            disks = target.get_children(class_type=Disk)
            for disk in disks:
                if disk.whole_disk and disk.in_zpool is None and \
                   disk.in_vdev is None and not disk.has_children:
                    if all_whole_disk is None:
                        all_whole_disk = True
                else:
                    all_whole_disk = False
                    break

            if all_whole_disk is not None and all_whole_disk:
                # Can use TargetController now
                # Call initialize again to ensure logicals created, since
                # previously called to not create logicals.
                self.controller.initialize(no_initial_disk=True,
                                           unique_zpool_name=not self.dry_run)

                # Disk specified in target may not contain a name, find
                # A matching disk in the discovered tree
                discovered_disks = list()
                for disk in disks:
                    dd = self.__find_disk(disk)
                    if dd is not None:
                        discovered_disks.append(dd)

                if not discovered_disks:
                    raise SelectionError("Failed to match target disk(s) "
                        "discovered disks.")

                selected_disks = self.controller.select_disk(discovered_disks,
                    use_whole_disk=True)

                # When bug : 7037884 we can then add this back and support
                # The Changing of a GPT disk to VTOC automatically
                #for disk in selected_disks:
                #    # Ensure we're using VTOC labelling until GPT integrated
                #    disk.label = "VTOC"

                # Target Controller will insert default root pool need to
                # Set this for validation of name later on
                self._is_generated_root_pool = True

                # Need to update the logical map, as new one just created
                new_desired_target = self.__get_new_desired_target()

                # Get New Logical sections
                logicals = new_desired_target.get_children(class_type=Logical)

                if logicals is not None and logicals:
                    for logical in logicals:
                        # A logical may have been specified just for
                        # the purposes of noswap and nodump, ensure
                        # This information is passed onto handle_logical
                        if self._nozpools:
                            logical.noswap = self._noswap
                            logical.nodump = self._nodump
                        # No need to insert into new_desired, already there
                        self.__handle_logical(logical)

                # Update disk map
                self.__add_disks_to_map(selected_disks)

                skip_disk_processing = True

        if not skip_disk_processing:
            if self._root_pool is None:
                # There is no zpool, so we will add one temporarily
                # This will allow us to fill-in the in_zpool/in_vdev for disks
                # that don't have any explicitly set already.
                tmp_logical = self.__create_temp_logical_tree(logicals)

                if new_desired_target is None:
                    new_desired_target = self.__get_new_desired_target()
                if tmp_logical not in logicals or self._nozpools:
                    # Insert new logical into desired tree
                    new_desired_target.insert_children(tmp_logical)
                else:
                    # Could be re-using existing logical section.
                    # Replace in desired tree with this one.
                    existing_logical = new_desired_target.get_first_child(
                                                    class_type=Logical)
                    if existing_logical:
                        new_desired_target.delete_children(existing_logical)
                    new_desired_target.insert_children(tmp_logical)

            # It's also possible to have no disks, if so install to first
            # available disk that is large enough to install to.
            # Should be cycling through manifest disks or discovered disks
            # looking at __handle_disk
            disks = target.get_children(class_type=Disk)

            # If no Disks, but have a logical section, then we need to
            # auto-select, and add disk.
            if not disks and self._root_pool is not None and \
                self._root_pool.action not in self.PRESERVED:
                disk = self.controller.select_initial_disk()

                if disk is not None:
                    self.logger.info("Selected Disk(s) : %s" % \
                        (self.__pretty_print_disk(disk)))
                    # When bug : 7037884 we can then add this back and support
                    # The Changing of a GPT disk to VTOC automatically
                    ## Ensure were using a VTOC label
                    #disk.label = "VTOC"
                    pool_vdevs = self.__get_vdevs_in_zpool(
                        self._root_pool.name)
                    root_vdev_name = None
                    if self._root_vdev is not None:
                        root_vdev_name = self._root_vdev.name
                    elif len(pool_vdevs) > 1:
                        self.logger.debug(
                            "Automatic disk selection failed. "
                            "More than one possible vdev in zpool. "
                            "in_zpool '%s'." % (self._root_pool.name))
                    elif len(pool_vdevs) == 1:
                        root_vdev_name = pool_vdevs[0].name

                    # Ensure using whole-disk in a way suitable for root pool
                    self.controller.apply_default_layout(disk, False, True,
                        in_zpool=self._root_pool.name, in_vdev=root_vdev_name)

                    if new_desired_target is None:
                        new_desired_target = self.__get_new_desired_target()
                    new_desired_target.insert_children(disk)

                    self._disk_map[disk.ctd] = disk

            for disk in disks:
                if self._is_generated_root_pool:
                    # Fail if manifest has disk references to temporary pool we
                    # just created.
                    if disk.in_zpool == self._root_pool.name or \
                       disk.in_vdev == self._root_vdev.name:
                        raise SelectionError(
                            "Invalid selection of non-existent pool"
                            " or vdev for disk")

                new_disk = self.__handle_disk(disk)
                if new_disk is not None:
                    if new_desired_target is None:
                        new_desired_target = self.__get_new_desired_target()
                    new_desired_target.insert_children(new_disk)

            # If disks were added to temporary root pool, make it permanent
            if self._is_generated_root_pool:
                # At this point any slices that were specified but don't
                # contain identifiable info, will cause no devices to be
                # returned.
                vdev_devices = self.__get_vdev_devices(self._root_pool.name,
                                                       self._root_vdev.name,
                                                       self._disk_map)
                if vdev_devices is not None and vdev_devices:
                    # Keep root pool since we used it.
                    self._is_generated_root_pool = False
                else:
                    self.__cleanup_temp_logical(logical, logicals)

        if new_desired_target is not None:
            self.logger.debug("Validating desired =\n%s\n" %
                (str(new_desired_target)))
            self.__validate_swap_and_dump(new_desired_target)
            self.__validate_logical(new_desired_target)
            self.__validate_disks(new_desired_target)
            # Do final validation before passing to Target Instantiation
            if not new_desired_target.final_validation():
                errors = errsvc.get_all_errors()
                if errors:
                    errstr = "Following errors occurred during final " \
                        "validation :\n%s" % (str(errors[0]))
                    raise SelectionError(errstr)
                else:
                    raise SelectionError("Final Validation Failed. See "
                        "install_log for more details.")

        return new_desired_target

    def select_targets(self, from_manifest, discovered, dry_run=False):
        '''The starting point for selecting targets.

           Arguments:

           - from_manifest: A referents to a list of target objects that were
                            imported from the manifest.

           - discovered:    A reference to the root node of the discovered
                            targets.

           - dry_run:       Target Selection dry_run indicator. Mainly used
                            by unit tests.

           If there are no targets in the manifest, we will defer to Target
           Controller to do the selection of the disk to install to.

           If there are targets, we will process them by traversing the tree
           using __handle_XXXX methods for each object type.
        '''

        if discovered is None:
            raise SelectionError("No installation targets found.")

        self.dry_run = dry_run

        # Store list of discovered disks
        self._discovered_disks = discovered.get_children(class_type=Disk)

        # Store list of discovered zpools
        self._discovered_zpools = discovered.get_descendants(class_type=Zpool)
        if len(self._discovered_zpools) > 0:
            # Store map of devices on discovered zpools
            self._discovered_zpool_map = self.__get_existing_zpool_map()

        if len(self._discovered_disks) == 0:
            raise SelectionError("No installation target disks found.")

        if from_manifest:
            self.logger.debug("from_manifest =\n%s\n" %
                              (str(from_manifest[0])))
        else:
            self.logger.debug("from_manifest = NONE\n")
        self.logger.debug("discovered =\n%s\n" % (str(discovered)))

        # Check if all Targets have children
        targets_have_children = False
        if from_manifest:
            for target in from_manifest:
                if target.has_children:
                    targets_have_children = True
                    break

        selected_disks = None
        new_target = None
        if from_manifest is None or not targets_have_children:
            # Default to TargetController's automatic mechanism
            initial_disks = self.controller.initialize(
                unique_zpool_name=not self.dry_run)

            # Occasionally initialize fails to select a disk because
            # it cannot find a slice large enough to install to, however
            # we are using whole disk, so just find first one large enough
            if not initial_disks:
                initial_disks = self.controller.select_initial_disk()

            self.logger.info("Selected Disk(s) : %s" % \
                (self.__pretty_print_disk(initial_disks)))

            # Ensure whole-disk is selected for each disk.
            selected_disks = self.controller.select_disk(initial_disks,
                use_whole_disk=True)

            # When bug : 7037884 we can then add this back and support
            # The Changing of a GPT disk to VTOC automatically
            #for disk in desired_disks:
            #    # Ensure we're using VTOC labelling until GPT integrated
            #    disk.label = "VTOC"

            # Target Controller will insert default root pool need to
            # Set this for validation of name later on
            self._is_generated_root_pool = True

            # Target Controller is not setting the mountpoint for the default
            # BE so need to set it here just in case.
            # Also getting the desired tree and doing some validation here
            # seems like a good idea too.

            # As desired tree has been configured, makes sense to fill out
            # The internal maps, and call various validate functions, doing
            # this ensure both target controller and target selection are
            # populating the desired tree in the same manner.

            existing_desired = \
                self.doc.persistent.get_first_child(Target.DESIRED)

            if existing_desired:
                # Traverse Logicals until we get the BE

                self.logger.debug("No targets specified in Manifest, "
                    "Target Controller has selected default target.")

                self.logger.debug("Target Controller Pre-Desired : \n%s\n" %
                    (str(existing_desired)))

                self.logger.debug("Target Selection ensuring BE "
                    "mountpoint set to '%s'." % (self.be_mountpoint))

                # Get New Logical sections
                logicals = existing_desired.get_children(class_type=Logical)

                # Update logical maps and set be mountpoint
                if logicals is not None and logicals:
                    be = None
                    for logical in logicals:
                        # A logical may have been specified just for
                        # the purposes of noswap and nodump, ensure
                        # This information is passed onto handle_logical
                        if self._nozpools:
                            logical.noswap = self._noswap
                            logical.nodump = self._nodump
                        # No need to insert into new_desired, already there
                        self.__handle_logical(logical)

                        # Get BE object from root pool
                        for zpool in \
                                [z for z in logical.children if z.is_root]:
                            be = zpool.get_first_child(class_type=BE)

                if be is not None:
                    self.logger.debug("Setting BE mountpoint to '%s'" %
                        (self.be_mountpoint))
                    be.mountpoint = self.be_mountpoint

                # Update disk map
                for disk in selected_disks:
                    if disk.ctd in self._disk_map:
                        # Seems that the disk is specified more than once in
                        # the manifest!
                        raise SelectionError(
                            "Disk '%s' matches already used disk '%s'." %
                            (self.__pretty_print_disk(disk), disk.ctd))
                    self._disk_map[disk.ctd] = disk

                # As TC has configured the logical section we also need
                # to ensure swap and dump zvols exist if required.
                self.logger.debug("Target Selection ensuring swap/dump "
                    "configured if required.")

                self.__validate_swap_and_dump(existing_desired)

                # Validate logical/disk portions of desired tree
                self.__validate_logical(existing_desired)
                self.__validate_disks(existing_desired)

                self.logger.debug("Target Controller Post-Desired : \n%s\n" %
                    (str(existing_desired)))

        else:
            # Can't rely on TargetController much here, so perform own
            # selections and interpret values from the manifest.

            if from_manifest:
                # The AI DTD only allows for one <target> element.
                new_target = self.__handle_target(from_manifest[0])
                if new_target is not None:
                    # Got a new DESIRED tree, so add to DOC
                    existing_desired = \
                        self.doc.persistent.get_first_child(Target.DESIRED)
                    if existing_desired:
                        self.doc.persistent.delete_children(existing_desired)
                    self.doc.persistent.insert_children(new_target)

        if not selected_disks and not new_target:
            raise SelectionError("Unable to find suitable target for install.")

        self.logger.debug("Selected disk(s): %s" % (repr(selected_disks)))

    def __check_valid_zpool_vdev(self, disk):
        '''Check that disk refers to known zpool and/or vdev
           Will raise an SelectionError exception if anything is wrong.
        '''
        if disk.in_zpool is not None and len(disk.in_zpool) > 0:
            if disk.in_zpool not in self._zpool_map:
                raise SelectionError(
                    "Disk %s specifies non-existent in_zpool: %s"
                    % (self.__pretty_print_disk(disk), disk.in_zpool))
            # Limit vdev match to specific zpool
            zpool_list_to_match = [disk.in_zpool]
        else:
            # Need to compare vdev to all known zpools.
            zpool_list_to_match = self._zpool_map.keys()

        # If only specify vdev, then try see if it exists
        # as a vdev in one of the known zpools
        if disk.in_vdev is not None and len(disk.in_vdev) > 0:
            vdev_matches = 0
            for zpool in zpool_list_to_match:
                vdev_id = "%s:%s" % \
                    (zpool, disk.in_vdev)
                if vdev_id in self._vdev_map:
                    vdev_matches += 1
            if vdev_matches == 0:
                raise SelectionError(
                    "Disk %s specifies non-existent in_vdev: %s"
                    % (self.__pretty_print_disk(disk), disk.in_vdev))
            elif vdev_matches > 1:
                raise SelectionError(
                    "Disk %s specifies non-unique in_vdev: %s"
                    % (self.__pretty_print_disk(disk), disk.in_vdev))

        # TODO : If disk.in_zpool and disk.in_vdev are none, should we
        # be checking the children here

        # If we got this far we're ok, otherwise an exception will be raised.
        return True

    def __get_new_desired_target(self):
        '''Create a new DESIRED tree using Target Controller
           initialize which performs the following :
           - Sets minimum_target_size
           - deletes any existing desired tree
           - Calls Target(Target.DESIRED)
           - Inserts Desired into DOC
        '''
        new_desired_target = \
            self.doc.persistent.get_first_child(Target.DESIRED)
        if new_desired_target is None:
            self.controller.initialize(no_initial_logical=True,
                                       unique_zpool_name=not self.dry_run)
            new_desired_target = \
                self.doc.persistent.get_first_child(Target.DESIRED)

        if new_desired_target is None:
            raise SelectionError("Failed to create new DESIRED tree.")

        return new_desired_target

    def parse_doc(self):
        '''Method for locating objects in the  data object cache (DOC) for
           use by the checkpoint.

           Will return a tuple of Data Object references for the Targets:

           (from_manifest, discovered)
        '''

        from_manifest = self.doc.find_path(
            "//[@solaris_install.auto_install.ai_instance.AIInstance?2]"
            "//[@solaris_install.target.Target?2]")
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)

        return (from_manifest, discovered)

    # Implement AbstractCheckpoint methods.
    def get_progress_estimate(self):
        '''Returns an estimate of the time this checkpoint will take
        '''
        return 3

    def execute(self, dry_run=False):
        '''Primary execution method used by the Checkpoint parent class
           to select the targets during an install.
        '''
        self.logger.info("=== Executing Target Selection Checkpoint ==")

        try:
            (from_manifest, discovered) = self.parse_doc()

            self.select_targets(from_manifest, discovered, dry_run)
        except Exception:
            self.logger.debug("%s" % (traceback.format_exc()))
            raise

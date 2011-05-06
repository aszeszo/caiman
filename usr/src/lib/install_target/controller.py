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

""" controller.py, TargetController and related classes.
"""

import logging
import os
import platform

from copy import copy, deepcopy

from solaris_install import Popen
from solaris_install.data_object.simple import SimpleXmlHandlerBase
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.libadm.const import V_ROOT
from solaris_install.target.logical import Logical, BE
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size

LOGGER = None

# If install image size not available, use 4GB
FALLBACK_IMAGE_SIZE = Size("4" + Size.gb_units)

# Values for Swap and Dump calculations.  All values are in MB
MIN_SWAP_SIZE = 512
MAX_SWAP_SIZE = (Size("32gb")).get(Size.mb_units)
MIN_DUMP_SIZE = 256
MAX_DUMP_SIZE = (Size("16gb")).get(Size.mb_units)
OVERHEAD = 1024
FUTURE_UPGRADE_SPACE = (Size("2gb")).get(Size.mb_units)
# Swap ZVOL is required if memory is below this
ZVOL_REQ_MEM = 900

VFSTAB_FILE = "/etc/vfstab"

# "TargetController data" is an area in the DataObjectCache
# intended for the TargetController class's private use.  It
# is identified by a top-level <target> element, with the name
# "TargetController data", under the DOC's persistent tree.
# See TargetControllerBackupEntry class for more details.
DATA_AREA_NAME = "TargetController data"

DEFAULT_LOGICAL_NAME = "logical"
DEFAULT_ZPOOL_NAME = "rpool"
DEFAULT_VDEV_NAME = "vdev"
VDEV_REDUNDANCY_NONE = "none"
VDEV_REDUNDANCY_MIRROR = "mirror"


class BadDiskError(Exception):
    ''' General purpose error class for when TargetController is unable
        to access a disk.
    '''
    pass

class SwapDumpGeneralError(Exception):
    ''' General exception for errors computing swap and dump values.
    '''
    pass

class SwapDumpSpaceError(Exception):
    ''' Not enough space in the target disk for successful installation.
    '''
    pass


class TargetController(object):
    ''' The TargetController (TC) class is intended to be used by all the
        Install client apps for the purpose of selecting the disk
        or disks for the install.  It creates and sets up the
        "desired targets" area in the DataObjectCache (DOC) in the manner
        expected by the TargetInstantiation (TI) checkpoint, which
        will typically be run later.

        TC also calculates minimum and recommended sizes for the installation
        target, based on the passed-in image size and calculates sizes
        for swap and dump devices, if required.

        NB:
        Where TC methods accept Disk objects as parameters, these can
        be the actual Disk objects discovered by TargetDiscovery
        (TD), which the calling application will have retrieved from the
        "discovered targets" area of the DOC.  Or, they can be other
        Disk objects which represent the same disks as the "discovered
        targets".  In this case, TargetController will locate the
        corresponding Disks from "discovered targets" before processing
        them.
        Where TC methods return Disk objects, these will always be
        (possibly modified) copies of those discovered disks: TC takes
        in references to the "discovered targets", makes copies of those
        objects, places the copies in "desired targets" and returns the
        copies to the calling code.

        TC does not itself control changes to the partitioning layout
        of the selected disk(s) - this is done directly by the
        application by operating on the Disk objects returned from
        TC's methods.

        TC also maintains a backup of the previously selected disk(s),
        so that if the user makes changes to the partitioning layout
        of the selected disk(s); then changes the selected disk(s);
        and then changes back to the original disk(s), the previous
        partitioning layout that they configured will not be lost.

        APIs:

        from solaris_install.target.controller import TargetController, \
            BadDiskError, SwapDumpGeneralError, SwapDumpSpaceError

        target_controller = TargetController(doc, debug=False)
        disks = target_controller.initialize(
            image_size=FALLBACK_IMAGE_SIZE,
            no_initial_disk=False,
            no_initial_logical=False,
            install_mountpoint="/a",
            unique_zpool_name=False)
        logical = target_controller.apply_default_logical(
            logical=None,
            mountpoint="/a",
            redundancy="none",
            unique_zpool_name=True)
        disk = target_controller.select_initial_disk()
        disks = target_controller.select_disk(
            disks,
            use_whole_disk=False)
        disks = target_controller.add_disk(
            disks,
            use_whole_disk=False)
        disks = target_controller.reset_layout(
            disk=None,
            use_whole_disk=False)
        target_controller.apply_default_layout(
            disk,
            use_whole_disk,
            wipe_disk=False,
            in_zpool=DEFAULT_ZPOOL_NAME,
            in_vdev=DEFAULT_VDEV_NAME)
        swap_type, swap_size, dump_type, dump_size = \
            target_controller.calc_swap_dump_size(
                installation_size,
                available_size,
                swap_included=False)
        target_controller.setup_vfstab_for_swap(
            pool_name,
            basedir)

        min_size = target_controller.minimum_target_size
        rec_size = target_controller.recommended_target_size

        type = TargetController.SWAP_DUMP_ZVOL
        type = TargetController.SWAP_DUMP_NONE
    '''

    SWAP_DUMP_ZVOL = "ZVOL"
    SWAP_DUMP_NONE = "None"

    #--------------------------------------------------------------------------
    # Public methods

    def __init__(self, doc, debug=False):
        ''' Initializer method.  Called by the constructor.

            Parameters:
            doc.  A reference to a DataObjectCache instance where
                TD places details of the "discovered targets" and
                where TC will create the "desired targets" area.
            debug=False.  If True, XML is generated for the backup
                area and will get written to logs.

            Returns: Nothing

            Raises: Nothing
        '''

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self._doc = doc
        self._debug = debug
        self._discovered_root = None
        self._discovered_disks = None
        self._desired_root = None
        self._backup_area = None
        self._need_backup = False
        self._logical = None
        self._zpool = None
        self._vdev = None
        self._be = None

        self._image_size = None
        self._mem_size = None
        self._minimum_target_size = None
        self._recommended_target_size = None
        self._swap_dump_computed = False
        self._swap_type = TargetController.SWAP_DUMP_NONE
        self._swap_size = None
        self._dump_type = TargetController.SWAP_DUMP_NONE
        self._dump_size = None

        self._this_processor = platform.processor()

        super(TargetController, self).__init__()

    def initialize(self, image_size=FALLBACK_IMAGE_SIZE,
        no_initial_logical=False, no_initial_disk=False,
        install_mountpoint="/a", unique_zpool_name=False):
        ''' Creates the top-level structure for the "desired targets" area
            in the DOC and, optionally, selects an initial disk to be the
            target for this install.

            The TargetDiscovery checkpoint must have run successfully,
            saving details of the system's storage devices in the
            "discovered targets" area of the DOC, before initialize()
            is called, or an error is raised.

            Parameters:
            image_size=FALLBACK_IMAGE_SIZE.  If specified, must be a Size
                object.  TC will use this value to compute the minimum
                disk size that can be selected.
            no_initial_logical=False. If set to True, then initialize will
                not set up a default rpool structure. Will also ensure 
                no default disk is selected.
            no_initial_disk=False.  If set to True, then initialize will
                not select an initial disk.  This may be useful for non-
                interactive installers, where they know before calling TC
                which disk(s) they will be installing on.
            install_mountpoint="/a". The mountpoint attribute of the
                created BE will be set to this value.
            unique_zpool_name=False If set to True, will ensure that the name
                of the pool will not match any existing zpools on the system.

            Returns: A list of the initially selected Disks.

            Raises: BadDiskError
        '''

        # Ensure that TD has already been successfully run by searching
        # for a <target name="discovered"> root node in the DOC. Save a
        # reference to this node for future use.
        self._discovered_root = self._doc.persistent.get_first_child(
            name=Target.DISCOVERED)
        if self._discovered_root is None:
            raise BadDiskError("No discovered targets available")

        self._image_size = image_size
        self._mem_size = _get_system_memory()
        # Reset these values to None so they get correctly recomputed
        self._minimum_target_size = None
        self._recommended_target_size = None

        # Clear out any previous "desired targets" from the DOC
        self._doc.persistent.delete_children(name=Target.DESIRED,
            class_type=Target)

        # Create a tree of DataObjects representing the initial
        # top-level nodes of the "desired targets" tree to be created
        # in the DOC.  The created tree will be similar to:
        #   <target name="desired">
        #       <!-- selected disks will be inserted here -->
        #       <logical>
        #           <zpool name="rpool" is_root="true">
        #               <vdev name="vdev"/>
        #               <be name="solaris" mountpoint="/a"/>
        #           </zpool>
        #       </logical>
        #   </target>
        self._desired_root = Target(Target.DESIRED)
        self._doc.persistent.insert_children(self._desired_root)

        # Return after creating Desired root node
        if no_initial_logical:
            return list()

        self._logical = self.apply_default_logical(
            mountpoint=install_mountpoint,
            unique_zpool_name=unique_zpool_name)
        self._desired_root.insert_children(self._logical)

        if no_initial_disk:
            return list()

        # select an initial disk and return it
        initial_disk = self.select_initial_disk()
        return_disks = self._add_disks([initial_disk], False)
        self._need_backup = True
        return return_disks

    def apply_default_logical(self, logical=None, mountpoint="/a",
        redundancy="none", unique_zpool_name=True):
        ''' Create a default logical layout for root pool.
            Only create logical element if not already done so, if not
            none it is assumed this logical contains no children.
            Optionally, ensure root pool name is unique and does not
            exist already.
        '''

        if logical is None:
            logical = Logical(DEFAULT_LOGICAL_NAME)

        self._zpool = logical.add_zpool(
            DEFAULT_ZPOOL_NAME, is_root=True)

        if unique_zpool_name:
            # Ensure this root pool name is unique
            if self._zpool.exists:
                self._zpool._name = self._get_unique_pool_name(self._zpool)
                LOGGER.warning("Default root zpool '%s' exists, Using '%s' " \
                    "instead." % (DEFAULT_ZPOOL_NAME, self._zpool._name))

        self._vdev = self._zpool.add_vdev(DEFAULT_VDEV_NAME, redundancy)
        self._be = BE()
        self._be.mountpoint = mountpoint
        self._zpool.insert_children(self._be)

        return logical

    def select_disk(self, disks, use_whole_disk=False):
        ''' Select one or more disks to be used for the install.
            If any disk(s) were previously selected, they will be
            replaced with the newly selected disks.

            Parameters:
            disks, either a single Disk object or a list of Disks
            use_whole_disk=False, specifies whether the selected
                disk(s) are to be used as entire disks or whether
                they will be divided into partitions

            Returns:
            A list containing the selected disk(s).

            Raises: BadDiskError
        '''

        # If initialize() has not already been called, call it.
        # In this situation we do not select an initial disk.
        if self._desired_root is None:
            self.initialize(no_initial_disk=True)

        # param disks can either be a singleton Disk object
        # or a tuple of Disk objects
        if isinstance(disks, Disk):
            disks = [disks]

        disks = self._get_corresponding_discovered_disks(disks)
        self._check_disks_are_suitable(disks)

        previous_disks = self._get_desired_disks()

        # Clear the previously selected disks (if any) from "desired targets"
        self._desired_root.delete_children(class_type=Disk,
            not_found_is_err=False)

        if self._need_backup:
            # Backup the previously selected disks
            self._backup_disks(previous_disks)

        return_disks = self._add_disks(disks, use_whole_disk)

        # If use_whole_disk=False on this call to select_disk(),
        # then we will need to back up the disk layout on the
        # next call to select_disk().  (If use_whole_disk=True, there
        # is no user-defined layout to back up.)
        if use_whole_disk == False:
            self._need_backup = True
        else:
            self._need_backup = False

        return return_disks

    def add_disk(self, disks, use_whole_disk=False):
        ''' Add one or more disks to the currently selected disks
            for this install.

            Parameters:
            disks, either a single Disk object or a list of Disks.
            use_whole_disk=False, specifies whether the selected
                disk(s) are to be used as entire disks or whether
                they will be divided into partitions

            Returns: A list containing the added disk(s).

            Raises: BadDiskError
        '''

        # If initialize() has not already been called, call it.
        # In this situation we do not select an initial disk.
        if self._desired_root is None:
            self.initialize(no_initial_disk=True)

        # param disks can either be a singleton Disk object
        # or a list of Disk objects
        if isinstance(disks, Disk):
            disks = [disks]

        disks = self._get_corresponding_discovered_disks(disks)
        self._check_disks_are_suitable(disks)

        # Check that disk(s) being added are not already in "desired targets"
        current_disks = self._get_desired_disks()
        if current_disks is not None:
            for current_disk in current_disks:
                for new_disk in disks:
                    if current_disk.name_matches(new_disk):
                        raise BadDiskError("Attempt to add same disk twice!")

        return_disks = self._add_disks(disks, use_whole_disk)

        return return_disks

    def reset_layout(self, disk=None, use_whole_disk=False):
        ''' Resets the partitioning layout of either all currently
            selected disks, or a specific disk, back to their
            original layout from "discovered targets". However
            for disks that have no usable partitions and/or slices
            the call to apply_default_layout will also reset the
            suggested layout before returning.

            Parameters:
            disk=None.  If not given, or None, then all the currently
                selected disks are reset.  Otherwise disk must be a
                single Disk object.
            use_whole_disk=False, specifies whether the selected
                disk(s) are to be used as entire disks or whether
                they will be divided into partitions

            Returns:
            A list containing the reset Disks.

            Raises:
            BadDiskError
        '''

        # Ensure initialize() has already been called.
        if self._desired_root is None:
            raise BadDiskError("No selected disks to reset!")

        current_disks = self._get_desired_disks()

        disks = list()
        if disk is None:
            # The user didn't say which disk(s) to reset.  So get from
            # the "discovered targets", the disks corresponding to
            # all the currently selected disks
            for current_disk in current_disks:
                for discovered_disk in self.discovered_disks:
                    if current_disk.name_matches(discovered_disk):
                        disks.append(discovered_disk)
        else:
            disks.append(disk)

        return_disks = list()
        for disk in disks:
            if disk.ctd not in \
                [disc_disk.ctd for disc_disk in self.discovered_disks]:
                raise BadDiskError(
                    "Trying to reset a disk not in discovered targets!")

            # find the disk in the descovered disks
            for disc_disk in self.discovered_disks:
                if disk.ctd == disc_disk.ctd:
                    break

            # remove equivalent disk from "desired targets"
            found = False
            for current_disk in current_disks:
                if disk.name_matches(current_disk):
                    self._desired_root.delete_children(children=current_disk,
                        not_found_is_err=True)
                    found = True

            if not found:
                raise BadDiskError("Trying to reset an unselected disk!")

            # re-insert a fresh copy of the disk, with the original
            # layout discovered by TD, into "desired targets". However
            # for disks that have no usable partitions and/or slices
            # the call to apply_default_layout will also reset the
            # suggested layout before returning.
            if disc_disk is not None:
                copy_disk = deepcopy(disc_disk)
                self.apply_default_layout(copy_disk, use_whole_disk, False)
                if self._fixup_disk(copy_disk, use_whole_disk):
                    self._desired_root.insert_children(copy_disk,
                        before=self._logical)
                return_disks.append(copy_disk)

        return return_disks

    def apply_default_layout(self, disk, use_whole_disk,
        wipe_disk=False, in_zpool=DEFAULT_ZPOOL_NAME,
        in_vdev=DEFAULT_VDEV_NAME):
        ''' Attempt to apply the default layout to a disk.
            Only apply to disks if we are not using whole disk.

            If wipe disk specified then delete all existing partition
            and slice information from the disk supplied.
        '''

        if use_whole_disk:
            return

        if wipe_disk:
            for obj in [Partition, Slice]:
                disk.delete_children(class_type=obj)

        partitions = disk.get_descendants(class_type=Partition)
        slices = disk.get_descendants(class_type=Slice)
        # set the start sector to one cylinder worth of sectors
        start = disk.geometry.cylsize
        slice_size = disk.disk_prop.dev_size.sectors - start

        if not partitions and not slices:
            # We need to add some back in to create the disk set up in such a
            # way that we end up with a bootable pool.
            if self._this_processor == "i386":
                new_partition = disk.add_partition("1", start, slice_size,
                    Size.sector_units, partition_type=191,
                    bootid=Partition.ACTIVE)

                new_slice = new_partition.add_slice("0", start, slice_size,
                    Size.sector_units)
            else:
                new_slice = disk.add_slice("0", start, slice_size,
                    Size.sector_units)
        else:
            # Compile a list of the usable slices, if any
            slice_list = list()
            for slc in slices:
                if slc.name != "2":
                    if slc.size >= self.minimum_target_size:
                        slice_list.append(slc)
                        break

            if self._this_processor == "sparc":
                # No Partitions to look through, just check the slices.

                if slice_list:
                    # We have a useable slice already, so nothing more to do
                    return

                # No useable slices. Clear the slices and add a root slice
                disk.delete_children(class_type=Slice)
                new_slice = disk.add_slice("0", start, slice_size,
                    Size.sector_units)
            else:
                for partition in partitions:
                    if partition.is_solaris and disk.label == "VTOC":
                        # Mark partition as ACTIVE to be sure, and change
                        # action to create to ensure active flag is set.
                        # Create shouldn't change existing VTOC unless the
                        # sizes differ for any reason, which they shouldn't
                        partition.action = "create"
                        if partition.is_primary:
                            partition.bootid = Partition.ACTIVE

                        if slice_list:
                            # We have a useable slice already, so nothing
                            # more to do.
                            return

                        # No useable slices. Clear the slices and add a
                        # root slice
                        partition.delete_children(class_type=Slice)
                        new_slice = partition.add_slice("0", start,
                            slice_size, Size.sector_units)
                        break
                else:
                    return

        new_slice.tag = V_ROOT
        new_slice.in_vdev = in_vdev
        new_slice.in_zpool = in_zpool

    def select_initial_disk(self):
        ''' Iterate through the disks discovered by TD and select
            one of them to be the initial install target.

            Returns: The selected Disk object

            Raises: BadDiskError
        '''

        # Check #1 - look for a disk has the disk_keyword "boot_disk"
        # and is big enough
        for disk in self.discovered_disks:
            if disk.is_boot_disk() and self._is_big_enough(disk):
                return disk

        # Check #2 - get 1st disk that is big enough
        for disk in self.discovered_disks:
            if self._is_big_enough(disk):
                return disk
        else:
            raise BadDiskError(
                "None of the available disks are big enough for install!")

    def calc_swap_dump_size(self, installation_size, available_size,
                            swap_included=False):
        ''' Calculate swap/dump, based on the amount of
            system memory, installation size and available size.

            The following rules are used for determining the type of
            swap to be created, whether swap zvol is required and the
            size of swap to be created.
 
            memory        type           required    size
            --------------------------------------------------
            <900mb        zvol           yes          0.5G (MIN_SWAP_SIZE)
            900mb-1G      zvol            no          0.5G (MIN_SWAP_SIZE)
            1G-64G        zvol            no          (0.5G-32G) 1/2 of memory
            >64G          zvol            no          32G (MAX_SWAP_SIZE)

            The following rules are used for calculating the amount
            of required space for dump.

            memory        type            size
            --------------------------------------------------
            <0.5G         zvol            256MB (MIN_DUMP_SIZE)
            0.5G-32G      zvol            256M-16G (1/2 of memory)
            >32G          zvol            16G (MAX_DUMP_SIZE)

            If slice/zvol is required, and there's not enough space in the,
            target, an error will be raised.  If swap zvol is
            not required, and there's not enough space in the target, as much
            space as available will be utilized for swap/dump

            Size of all calculation is done in MB
      
            Parameters:
            - installation_size: Size object.  The size required for
              the installation
            - available_size: Size object.  The available size on the
              target disk.
            - swap_included=False: Boolean.  Indicates whether required swap
              space is already included and validated in the installation size.

            Returns:
            Tuple consisting of:
                swap_type, swap_size, dump_type, dump_size
            whose types are:
                string, Size object, string, Size object

            Raise:
                SwapDumpSpaceError 
        '''

        if self._swap_dump_computed:
            # Only need to compute these once:
            return(self._swap_type, self._swap_size, self._dump_type,
                   self._dump_size)

        if (installation_size > available_size):
            LOGGER.error("Space required for installation: %s",
                          installation_size)
            LOGGER.error("Total available space: %s", available_size)
            raise SwapDumpSpaceError

        # Do all calcuations in MB
        installation_size_mb = installation_size.get(units=Size.mb_units)
        available_size_mb = available_size.get(units=Size.mb_units)
        swap_size_mb = self._get_required_swap_size()

        swap_required = False
        if swap_size_mb != 0:
            swap_required = True

        LOGGER.debug("Installation size: %s", installation_size)
        LOGGER.debug("Available size: %s", available_size)
        LOGGER.debug("Memory: %sMB. Swap Required: %s",
            self._mem_size, swap_required)

        if swap_required:
            # Make sure target disk has enough space for both swap and software
            if swap_included:
                required_size_mb = installation_size_mb
            else:
                required_size_mb = installation_size_mb + swap_size_mb
                if (available_size_mb < required_size_mb):
                    LOGGER.error("Space required for installation "
                        "with required swap: %s", required_size_mb)
                    LOGGER.error("Total available space: %s", available_size)
                    raise SwapDumpSpaceError
            
            dump_size_mb = self._calc_swap_or_dump_size(
                available_size_mb - required_size_mb,
                MIN_DUMP_SIZE, MAX_DUMP_SIZE)
        else:
            free_space_mb = available_size_mb - installation_size_mb
            swap_size_mb = self._calc_swap_or_dump_size(
                ((free_space_mb * MIN_SWAP_SIZE) / 
                (MIN_SWAP_SIZE + MIN_DUMP_SIZE)),
                MIN_SWAP_SIZE, MAX_SWAP_SIZE)
            dump_size_mb = self._calc_swap_or_dump_size(
                ((free_space_mb * MIN_DUMP_SIZE) /
                (MIN_SWAP_SIZE + MIN_DUMP_SIZE)),
                MIN_DUMP_SIZE, MAX_DUMP_SIZE)

        self._swap_size = Size(str(swap_size_mb) + Size.mb_units)
        if swap_size_mb > 0:
            self._swap_type = TargetController.SWAP_DUMP_ZVOL

        self._dump_size = Size(str(dump_size_mb) + Size.mb_units)
        if dump_size_mb > 0:
            self._dump_type = TargetController.SWAP_DUMP_ZVOL

        LOGGER.debug("Swap Type: %s", self._swap_type)
        LOGGER.debug("Swap Size: %s", self._swap_size)
        LOGGER.debug("Dump Type: %s", self._dump_type)
        LOGGER.debug("Dump Size: %s", self._dump_size)
        self._swap_dump_computed = True

        return (self._swap_type, self._swap_size, self._dump_type,
            self._dump_size)

    def setup_vfstab_for_swap(self, pool_name, basedir):
        '''Add the swap device to /etc/vfstab.
        '''
        swap_device = self._get_swap_device(pool_name)

        if swap_device is None:
            #nothing to do
            return

        fname = os.path.join(basedir, VFSTAB_FILE)
        try:
            with open (fname, 'a+') as vf:
                vf.write("%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n" % 
                    (swap_device, "-", "-", "swap", "-", "no", "-"))
        except IOError, ioe:
            LOGGER.error("Failed to write to %s", fname)
            LOGGER.exception(ioe)
            raise SwapDumpGeneralError

    @property
    def minimum_target_size(self):
        ''' The minimum amount of space required for an installation.

            This takes into account MIN_SWAP_SIZE required for
            low-memory system.
        
            Returns: Size object
        '''

        if self._minimum_target_size is None:
            swap_size_mb = self._get_required_swap_size()
            min_size_mb = self._image_size.get(units=Size.mb_units) \
                + OVERHEAD + swap_size_mb

            self._minimum_target_size = Size(str(min_size_mb) + Size.mb_units)

        return(self._minimum_target_size)

    @property
    def recommended_target_size(self):
        ''' The recommended size to perform an installation.

            This takes into account estimated space to perform an upgrade.

            Returns: Size object
        '''

        if self._recommended_target_size is None:
            rec_size_mb = self.minimum_target_size.get(units=Size.mb_units) \
                + FUTURE_UPGRADE_SPACE

            self._recommended_target_size = Size(str(rec_size_mb) \
                + Size.mb_units)

        return(self._recommended_target_size)

    #--------------------------------------------------------------------------
    # Private methods
    def _get_unique_pool_name(self, zpool):
        ''' Get the next available pool name that does not exist, via
            appending ascending numbers to end of the zpool.name.
        '''

        ztmp = copy(zpool)
        zcount = 1

        ztmp._name = zpool.name + str(zcount)
        while ztmp.exists:
            zcount += 1
            ztmp._name = zpool.name + str(zcount)

        return ztmp.name

    def _add_disks(self, disks, use_whole_disk):
        ''' Convenience method called from select_disk, add_disk
            and initialize.
        '''

        # if use_whole_disk is False, then check if there is a backup
        # available for this exact set of disks
        backup = None
        if not use_whole_disk:
            backup = self._fetch_from_backup(disks)

        return_disks = list()
        if backup is not None:
            self._backup_area.delete_children(
                children=backup,
                not_found_is_err=True)

            for disk in backup.disks:
                if self._fixup_disk(disk, use_whole_disk):
                    self._desired_root.insert_children(disk,
                        before=self._logical)
                    return_disks = backup.disks
        else:
            for disk in disks:
                copy_disk = deepcopy(disk)
                self.apply_default_layout(copy_disk, use_whole_disk, False)
                if not self._fixup_disk(copy_disk, use_whole_disk):
                    continue
                self._desired_root.insert_children(copy_disk,
                    before=self._logical)
                return_disks.append(copy_disk)

        # If there is now 1 disk selected, set the vdev redundancy
        # to "none".  Otherwise, set it to "mirror".
        if len(self._get_desired_disks()) == 1:
            self._vdev.redundancy = "none"
        else:
            self._vdev.redundancy = "mirror"

        return return_disks

    def _get_corresponding_discovered_disks(self, disks):
        ''' Given a list of Disk object, return the corresponding
            Disks from "desired targets" which represent those same
            disks.
        '''

        return_disks = list()
        for disk in disks:
            found = False
            for discovered_disk in self.discovered_disks:
                if disk == discovered_disk:
                    found = True
                    return_disks.append(disk)
                    break
                if disk.name_matches(discovered_disk):
                    found = True
                    return_disks.append(discovered_disk)
                    break
            if not found:
                raise BadDiskError("No equivalent Disk in discovered targets!")

        return return_disks

    def _check_disks_are_suitable(self, disks):
        ''' Convenience method that checks that the passed-in disks
            are all from the "discovered targets" list created by TD
            and that they are all large enough for installing Solaris.
            If either check fails for any disk an exception is raised.

            Returns: nothing

            Raises: BadDiskError
        '''

        for disk in disks:
            # confirm that the passed in disks are all from TD list
            # (they must be the actual Disk objects from TD, not copies).
            if disk not in self.discovered_disks:
                raise BadDiskError("Disk is not in discovered targets!")

            if not self._is_big_enough(disk):
                raise BadDiskError("Disk is not big enough for install")

    def _backup_disks(self, disks):
        ''' Make a backup of a set of disks.

            If the backup area does not already exist, create it.
            If there is already an older entry in the backup area
            for the exact combination of disks being backed up,
            then delete that backup entry.
            Finally, construct a new backup entry for the passed-in
            disks and save it in the backup area.

            Returns: nothing.
        '''

        if disks is None:
            return

        # If "TargetController data" area does not already exist, create it
        if self._backup_area is None:
            self._backup_area = Target(DATA_AREA_NAME)

            self._doc.persistent.insert_children(self._backup_area)

        # if an older backup of same disk(s) exists, delete it
        backup_entries = self._backup_area.get_children()
        if backup_entries is not None:
            for backup_entry in backup_entries:
                if backup_entry.contains_same_disks(disks):
                    self._backup_area.delete_children(children=backup_entry,
                        not_found_is_err=True)

        # Construct the new backup entry
        new_backup_entry = TargetControllerBackupEntry("backup")
        new_backup_entry.insert_children(disks)

        self._backup_area.insert_children(new_backup_entry)

    def _fetch_from_backup(self, disks):
        ''' Retrieve a list of Disks from the backup area that matches the
            passed-in disks, if such a backup exists.

            Iterates through the backup area, comparing the Disks in each
            backup entry with the list of Disks passed in.  If a match
            is found, then return the corresponding list of Disks from
            the backup area.

            The Disks passed in are typically objects taken directly from
            the "discovered targets" area, while the returned  Disks are
            copies of those objects containing the most recent layout
            modifications which the user has made for those disks.

            Returns a TargetControllerBackupEntry object if a match is found.
            Otherwise, returns None.
        '''

        if self._backup_area is None:
            return None

        backup_entries = self._backup_area.get_children()

        if backup_entries is None:
            return None

        for backup_entry in backup_entries:
            if backup_entry.contains_same_disks(disks):
                return backup_entry

        return None

    def _fixup_disk(self, disk, use_whole_disk):
        ''' Prepare the passed-in Disk object for placement
            in the "desired targets" area.

            Returns:
            True if disk or slice successfully setup;
            False if not.
        '''

        if not use_whole_disk:
            slices = disk.get_descendants(class_type=Slice)
            if not slices:
                if self._vdev is not None:
                    disk.in_vdev = self._vdev.name
                if self._zpool is not None:
                    disk.in_zpool = self._zpool.name
                return True
            else:
                if len(slices) == 1:
                    # There is only one slice we need to check to see if it's
                    # slice "2". If is it we need to add a slice "0" and set
                    # in_vdev and in_zpool.

                    # NB: This will need to be updated when GPT is supported

                    if slices[0].name == "2":
                        # Add a slice
                        start = 1
                        slice_size = disk.disk_prop.dev_size.sectors - start

                        # parent will either be a Partition (i386) or a
                        # Slice (sparc)
                        parent = slices[0].parent
                        new_slice = parent.add_slice("0", start, slice_size,
                            Size.sector_units)

                        new_slice.tag = V_ROOT

                        if self._vdev is not None:
                            new_slice.in_vdev = self._vdev.name
                        if self._zpool is not None:
                            new_slice.in_zpool = self._zpool.name
                        return True
                    else:
                        if self._vdev is not None:
                            slices[0].in_vdev = self._vdev.name
                        if self._zpool is not None:
                            slices[0].in_zpool = self._zpool.name
                        return True
                else:
                    for nextslice in slices:
                        if nextslice.name != "2" and int(nextslice.name) < 8:
                            # find the first slice that's big enough
                            # and move on
                            if nextslice.size >= self.minimum_target_size:
                                if self._vdev is not None:
                                    nextslice.in_vdev = self._vdev.name
                                if self._zpool is not None:
                                    nextslice.in_zpool = self._zpool.name
                                return True
                    return False
        else:
            new_slice = None
            # If user requested use_whole_disk, then:
            # - delete any partitions on the disk
            # - delete any slices on the disk
            # - set the whole_disk attribute on the disk

            self.apply_default_layout(disk, use_whole_disk=False,
                wipe_disk=True)
            # We don't want the whole disk here right now since that
            # causes zpool create to use an EFI label on the disk which
            # is not supported by ZFS boot. When EFI support is available
            # disk.whole_disk should be set to the value of us_whole_disk
            disk.whole_disk = False

            # Set the in_vdev and/or in_zpool attributes
            slices = disk.get_descendants(name="0", class_type=Slice)
            if slices:
                # There should only be one slice with name="0"
                slice_zero = slices[0]

                # Set the in_vdev and/or in_zpool attributes
                if self._vdev is not None:
                    slice_zero.in_vdev = self._vdev.name
                if self._zpool is not None:
                    slice_zero.in_zpool = self._zpool.name
                slice_zero.tag = V_ROOT
                return True
            return False

    @property
    def discovered_disks(self):
        ''' Returns a list of the disks discovered by TD.'''

        if self._discovered_disks is None:
            if self._discovered_root is None:
                return None

            self._discovered_disks = self._discovered_root.get_children(
                class_type=Disk)

        return self._discovered_disks

    def _get_desired_disks(self):
        ''' Returns the list of disks currently in desired targets.'''

        if self._desired_root is None:
            return None

        return self._desired_root.get_children(class_type=Disk)

    def _is_big_enough(self, disk):
        ''' Returns True if the passed in Disk is big enough
            to install Solaris; otherwise returns False.
        '''

        if disk.disk_prop is not None and disk.disk_prop.dev_size is not None:
            if disk.disk_prop.dev_size >= self.minimum_target_size:
                return True

        return False

    def _calc_swap_or_dump_size(self, available_space, min_size, max_size):
        ''' Calculates size of swap or dump based on amount of
            physical memory available.

            If less than calculated space is available, swap/dump size will be
            trimmed down to the avaiable space.  If calculated space
            is more than the max size to be used, the swap/dump size will
            be trimmed down to the maximum size to be used for swap/dump

            Parameters:
            - available_space: Space that can be dedicated to swap (MB)
	        - min_size: Minimum size to use (MB)
	        - max_size: Maximum size to use (MB)

            Returns:
               size of swap in MB
        '''

        if available_space == 0:
            return 0

        if self._mem_size < min_size:
            size = min_size
        else:
            size = self._mem_size / 2
            if size > max_size:
                size = max_size

        if available_space < size:
            size = available_space

        return int(size)

    def _get_required_swap_size(self):
        ''' Determines whether swap is required.  If so, the amount of
            space used for swap is returned.  If swap is not required,
            0 will be returned.  Value returned is in MB.

            If system memory is less than 900mb, swap is required.
            Minimum required space for swap is 0.5G (MIN_SWAP_SIZE).
        '''
   
        if self._mem_size < ZVOL_REQ_MEM:
            return MIN_SWAP_SIZE

        return 0

    def _get_swap_device(self, pool_name):
        ''' Return the string representing the device used for swap '''
        if self._swap_type == TargetController.SWAP_DUMP_ZVOL:
            return "/dev/zvol/dsk/" + pool_name + "/swap"

        return None


class TargetControllerBackupEntry(SimpleXmlHandlerBase):
    ''' This class is only used within the TargetController class.

        Class for storing backups of previously selected
        disks, so that they can be retrieved, with any
        layout changes that the user has made, if those
        disks are selected again.

        Each backup entry consists of a top-level object
        plus a unique conbination of one or more disk
        objects, which are stored as its children.

        Only a unique conbination of selected disks can be
        restored:  eg if the user had previously selected
        a disk on its own and is now selecting that disk
        as part of a tuple of disks, the backup will not
        be retrieved.

        This is a sub-class of SimpleXmlHandlerBase, meaning
        it can be stored in the DOC.
    '''

    # SimpleXmlHandlerBase class requires that this be redefined
    TAG_NAME = "backup_entry"

    def __init__(self, name):
        ''' Initializer method.'''
        super(TargetControllerBackupEntry, self).__init__(name)

    @property
    def disks(self):
        ''' Returns all the children objects, which will always be disks.'''
        return self.get_children(not_found_is_err=True)

    def contains_same_disks(self, disks):
        ''' Returns True if this objects's children represent
            the same list of Disks as the list of Disks passed in.

            Otherwise, returns False.

            Disks being the "same" means the current object and the
            passed-in list contain the same number of Disks and each
            of the passed-in Disks has the same identifier as one
            of the current object's Disks.
        '''

        backup_entry_disks = self.disks

        if len(backup_entry_disks) != len(disks):
            return False

        for disk in disks:
            found = False
            for backup_disk in backup_entry_disks:
                if disk.name_matches(backup_disk):
                    found = True
            if not found:
                return False

        return True

#------------------------------------------------------------------------------
# Module private functions

def _get_system_memory():
    ''' Returns the amount of memory available in the system '''

    memory_size = 0

    p = Popen.check_call(["/usr/sbin/prtconf"], stdout=Popen.STORE,
        stderr=Popen.STORE, logger=LOGGER)
    for line in p.stdout.splitlines():
        if "Memory size" in line:
            memory_size = int(line.split()[2])
            break

    if memory_size <= 0:
        # We should have a valid size now
        LOGGER.error("Unable to determine amount of system memory")
        raise SwapDumpGeneralError

    return memory_size

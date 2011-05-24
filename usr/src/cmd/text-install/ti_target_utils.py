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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#


'''
Functions for mapping UI objects and DOC objects.
'''

import logging
import platform

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.controller import TargetController, \
    DEFAULT_VDEV_NAME, DEFAULT_ZPOOL_NAME
from solaris_install.target.libadm.const import FD_NUMPART as MAX_PRIMARY_PARTS
from solaris_install.target.libadm.const import MAX_EXT_PARTS
from solaris_install.target.libadm.const import V_BACKUP, V_ROOT
from solaris_install.target.libdiskmgt import const as libdiskmgt_const
from solaris_install.target.logical import Zpool, BE
from solaris_install.target.physical import Disk, Partition, Slice, \
    BACKUP_SLICE, BOOT_SLICE
from solaris_install.target.shadow.physical import ShadowPhysical
from solaris_install.target.size import Size


ROOT_POOL = DEFAULT_ZPOOL_NAME

PART_TYPE_SOLARIS = 191 #191 is type "solaris"
BACKUP_SLICE_TEXT = "backup"
UNUSED_TEXT = "Unused"
EXTENDED_TEXT = "Extended"

UI_PRECISION = "0.05gb"

UI_TYPE_IN_USE = "UI Object In-use" # partition/slice in use
UI_TYPE_EMPTY_SPACE = "UI Object EMPTY"   # unused components
UI_TYPE_NOT_USED = "UI Object not-in-use" 

MAX_VTOC = "2tb"

# Can not use the V_NUMPAR value defined in solaris_install.target.libadm.const
# because it returns 16 slices for x86.  Define the number of slices
# here so it is 8 for both x86 and sparc.
MAX_SLICES = 8 

LOGGER = None


def get_desired_target_disk(doc):
    ''' Returns the first disk in the desired target subtree of the DOC.  '''

    desired_root = doc.persistent.get_descendants(name=Target.DESIRED, \
        class_type=Target, max_depth=2, not_found_is_err=True)[0]

    return(desired_root.get_descendants(class_type=Disk,
                                        not_found_is_err=True)[0])


def get_desired_target_zpool(doc):
    ''' Returns the first zpool in the desired target subtree of the DOC.  '''

    desired_root = doc.persistent.get_descendants(name=Target.DESIRED, \
        class_type=Target, max_depth=2, not_found_is_err=True)[0]

    return(desired_root.get_descendants(name=ROOT_POOL, class_type=Zpool,
                                        not_found_is_err=True)[0])


def get_desired_target_be(doc):
    ''' Returns the first BE in the desired target subtree of the DOC.  '''
    desired_root = doc.persistent.get_descendants(name=Target.DESIRED, \
        class_type=Target, max_depth=2, not_found_is_err=True)[0]

    return(desired_root.get_descendants(class_type=BE,
                                        not_found_is_err=True)[0])


def get_solaris_partition(doc):
    '''Returns the partition with type "solaris", if it exists '''

    desired_disk = get_desired_target_disk(doc)

    all_partitions = desired_disk.get_children(class_type=Partition)

    if not all_partitions:
        return None

    for part in all_partitions:
        if part.is_solaris:
            return part

    return None


def get_solaris_slice(doc):
    '''Finds the slice that have the root pool for installation, if exists '''

    if platform.processor() == "i386":
        desired_part = get_solaris_partition(doc)
    else:
        desired_part = get_desired_target_disk(doc)

    all_slices = desired_part.get_children(class_type=Slice)

    if not all_slices:
        return None

    for slice in all_slices:
        if slice.in_zpool == ROOT_POOL:
            return slice

    return None


def find_discovered_disk(disk, doc):
    ''' Search for the disk that's the same as the given disk
        found during Target Discovery
    
        Returns the object in the discovered target tree of the DOC.
 
        Raise RuntimeError() if disk is not found in discovered target.
    '''
    disc_root = doc.persistent.get_descendants(name=Target.DISCOVERED, \
        class_type=Target, max_depth=2, not_found_is_err=True)[0]
    discovered_disks = disc_root.get_children(class_type=Disk)

    if not discovered_disks:
        raise RuntimeError("Disk not found in discovered target")

    # look through all the disks, and find the one matching this one.
    # The "devid" string is compared to identify
    for disc_disk in discovered_disks:
        if disc_disk.devid == disk.devid:
            return disc_disk

    # A disk should be found, so, it's an error to be here
    raise RuntimeError("Disk not found in discovered target")


def discovered_obj_was_empty(obj, doc):
    '''Determine whether the given disk was empty when it was discovered '''

    discovered_obj = None
    if isinstance(obj, Disk):
        discovered_disk = find_discovered_disk(obj, doc)
        parts = discovered_disk.get_children(class_type=Partition)
        if (parts is not None) and (len(parts) > 0):
            return False
        discovered_obj = discovered_disk
    else:
        # find the discovered partition
        discovered_disk = find_discovered_disk(obj.parent, doc)

        parts = discovered_disk.get_children(class_type=Partition)
        if not parts:
            raise RuntimeError("Discovered disk should have partitions.  "
                               "However, no partition is found.")
        discovered_obj = get_part_by_num(obj.name, parts)
        if discovered_obj is None:
            raise RuntimeError("Discovered disk should have partitions %s.  "
                               "However, unable to find the partition.",
                               obj.name)
            
    slices = discovered_obj.get_children(class_type=Slice)
    if not slices:
        return False

    return True


def perform_final_validation(doc):

    LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

    LOGGER.info("Going to perform final validation of desired target")

    desired_root = doc.persistent.get_descendants(name=Target.DESIRED,
                                                  class_type=Target,
                                                  max_depth=2,
                                                  not_found_is_err=True)[0]

    LOGGER.debug(str(desired_root))

    errsvc.clear_error_list()

    if not desired_root.final_validation():
        all_errors = errsvc.get_all_errors()

        for err in all_errors:

            if not isinstance(err.error_data[liberrsvc.ES_DATA_EXCEPTION],
                              ShadowPhysical.SliceInUseError):
                LOGGER.error("Error module ID: %s.. error type: %s" % \
                             (err.get_mod_id(), str(err.get_error_type())))
                LOGGER.error("Error class: %r",
                             err.error_data[liberrsvc.ES_DATA_EXCEPTION])
                LOGGER.error("Exception value: %s",
                             err.error_data[liberrsvc.ES_DATA_EXCEPTION].value)
                raise ValueError("Desired target doesn't pass "
                                 "final validation")
            else:
                LOGGER.debug("SliceInUseError is OK")
                LOGGER.debug("Error module ID: %s.. error type: %s" % \
                             (err.get_mod_id(), str(err.get_error_type())))
                LOGGER.debug("Exception value: %s",
                             err.error_data[liberrsvc.ES_DATA_EXCEPTION].value)
    else:
        LOGGER.debug("No error from final validation")


def dump_doc(msg): 

    if not LOGGER.isEnabledFor(logging.DEBUG):
        return

    LOGGER.debug(msg)
    doc = InstallEngine.get_instance().doc
    disk = get_desired_target_disk(doc)
    LOGGER.debug(str(disk))


def name_sort(a, b):
    return cmp(a.name, b.name)


def size_sort(a, b):
    return cmp(a.size, b.size)


def get_part_by_num(number, existing_parts):
    ''' Return the partition/slice that have the given index.
        If none of the existing partition/slice have the given
        index, None will be returned.
    '''
    for ep in existing_parts:
        if str(ep.name) == str(number):
            return ep
    return None


def add_missed_parts(numbers, existing_parts, gaps, min_size, all_parts,
                     check_extended=False, adding_logical=False):

    have_extended = False

    LOGGER.debug("Enter add_missed_parts")
    LOGGER.debug("numbers: %s", numbers)
    LOGGER.debug("Existing parts: %s", existing_parts)
    LOGGER.debug("Gaps: %s", gaps)
    LOGGER.debug("Min size: %s", min_size)

    for num in numbers:
        part = get_part_by_num(num, existing_parts)
        if part is not None:
            all_parts[num].doc_obj = part
            LOGGER.debug(str(all_parts[num].doc_obj))
            if check_extended:
                # check whether this is an extended partition
                if part.is_extended:
                    have_extended = True
        elif len(gaps) > 0:
            # some space is still left 
            if (gaps[-1]).size >= min_size:
                # see if the largest one is big enough
                one_gap = gaps.pop()
                empty_space = EmptySpace(num, one_gap.start_sector,
                                         one_gap.size)
                all_parts[num].empty_space_obj = empty_space
            else:
                if adding_logical:
                    # do not create empty space objects for logical partitions
                    return None
                empty_space = EmptySpace(num, 0, Size("0gb"))
                all_parts[num].empty_space_obj = empty_space
        else:
            if adding_logical:
                # do not create empty space objects for logical partitions
                return None
            # no space is left.  Create 0 size empty spaces
            empty_space = EmptySpace(num, 0, Size("0gb"))
            all_parts[num].empty_space_obj = empty_space

    return have_extended


class EmptySpace(object):

    def __init__(self, name, start_sector, size):
        self.name = name
        self.start_sector = start_sector
        self.size = size


class UIDisk(object):

    ''' Object used to keep track of disk related information for UI '''

    def __init__(self, target_controller, parent=None, doc_obj=None):

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        if doc_obj is None:
            raise ValueError("doc_obj for UIDisk is needed")
        self.doc_obj = doc_obj
        self.tc = target_controller
        self.all_parts = list()
        self.have_logical = False

        if platform.processor() == "i386":
            max_all_parts = MAX_PRIMARY_PARTS + MAX_EXT_PARTS + 1
            for i in range(max_all_parts):
                part = UIPartition(self.tc, parent=self)
                self.all_parts.append(part)
        else:
            max_all_parts = MAX_SLICES
            for i in range(max_all_parts):
                part = UISlice(self.tc, parent=self)
                self.all_parts.append(part)

    def get_parts_in_use(self):
        in_use_parts = []
        for part in self.all_parts:
            if (part.ui_type == UI_TYPE_IN_USE) or \
               (part.ui_type == UI_TYPE_EMPTY_SPACE):
                in_use_parts.append(part)

        return in_use_parts  

    def add_unused_parts(self, no_part_ok=False):
        '''On x86: Sort through the logical and non-logical partitions and
        find the largest gaps. For non-logical partitions, create additional
        Unused partitions such that the number of
        non-logical partitions == MAX_STANDARD_PARTITIONS. For logical
        partitions, create additional Unused partitions such that the number of
        logical partitions == MAX_LOGICAL_PARTITIONS

        On SPARC: Create Unused slices in the largest gaps of empty space,
        so that there are exactly 8 slices

        For non-logical partitions, gaps smaller than 1 GB are ignored.
        For logical partitions, gaps smaller than 0.1 GB are ignored.

        '''

        # reset everything to be unused
        for part in self.all_parts:
            part.ui_type = UI_TYPE_NOT_USED

        existing_parts = self.doc_obj.get_children(class_type=Partition)

        if not existing_parts:
            # should have some slices
            existing_parts = self.doc_obj.get_children(class_type=Slice)
            if not existing_parts:
                if no_part_ok:
                    if platform.processor() == "i386":
                        numbers = range(1, MAX_PRIMARY_PARTS + 1)
                        use_partitions = True
                    else:
                        numbers = range(MAX_SLICES)
                        use_partitions = False
                else:
                    raise ValueError("Cannot determine if this disk has " \
                                     "partitions or slices")
                existing_parts = []
            else:
                use_partitions = False
                numbers = range(MAX_SLICES)

        else:
            # have partitions
            use_partitions = True
            numbers = range(1, MAX_PRIMARY_PARTS + 1)

        LOGGER.debug("num_existing parts = %d", len(existing_parts))

        existing_parts.sort(name_sort)

        LOGGER.debug(str(self.doc_obj))

        existing_gaps = self.doc_obj.get_gaps()

        # sort the gaps by size, smallest gaps first.  When using
        # the existing_gaps list, the largest gaps is used first, they
        # will be popped off the end of the list.
        existing_gaps.sort(size_sort)

        self.have_logical = add_missed_parts(numbers, existing_parts, \
            existing_gaps, Size("1" + Size.gb_units), self.all_parts, \
            check_extended=use_partitions)

        if use_partitions == False:
            # If there's a backup slice, move it to end of the list for display
            slice2 = self.all_parts[2]
            if slice2.ui_type == UI_TYPE_IN_USE:
                self.all_parts.remove(slice2)
                self.all_parts.append(slice2)

        if LOGGER.isEnabledFor(logging.DEBUG):
            for part in self.all_parts:
                try:
                    LOGGER.debug("After fill unused...%s: %s..size=%s",
                                 str(part.name), part.get_description(),
                                 str(part.size))
                except Exception, ex:
                    LOGGER.debug("after fill unused...%s", ex)
                    pass

        if not self.have_logical:
            return

        first_logical = MAX_PRIMARY_PARTS + 1
        numbers = range(first_logical, first_logical + MAX_EXT_PARTS)

        logical_part_gaps = self.doc_obj.get_logical_partition_gaps()

        # sort the gaps by size, smallest gaps first.  When using
        # the existing_gaps list, the largest gaps is used first, they
        # will be popped off the end of the list.
        logical_part_gaps.sort(size_sort)

        # Fill in all the missing logical if necessary
        add_missed_parts(numbers, existing_parts, logical_part_gaps,
                         Size("0.1" + Size.gb_units), self.all_parts,
                         adding_logical=True)
        
    @property
    def name(self):
        return self.doc_obj.name

    @property
    def size(self):
        return self.doc_obj.disk_prop.dev_size

    def get_extended_partition(self):
        if not self.have_logical:
            return None

        for part in self.all_parts:
            if part.ui_type == UI_TYPE_IN_USE and part.doc_obj.is_extended:
                return part
        return None

    def get_logicals(self):
        '''Retrieve all the logicals on this disk'''
        logicals = []
        for part in self.all_parts:
            if ((part.ui_type == UI_TYPE_IN_USE) or \
                (part.ui_type == UI_TYPE_EMPTY_SPACE)) and \
                (part.is_logical()):
                logicals.append(part)
        return logicals

    def get_standards(self):
        standards = []
        for part in self.all_parts:
            if ((part.ui_type == UI_TYPE_IN_USE) or \
                (part.ui_type == UI_TYPE_EMPTY_SPACE)) and \
                (not part.is_logical()):
                standards.append(part)
        return standards

    def get_solaris_data(self):
        if platform.processor() == "i386":
            for part in self.all_parts:
                if part.ui_type == UI_TYPE_IN_USE and part.doc_obj.is_solaris:
                    return part
        else:
            for part in self.all_parts:
                if (part.ui_type == UI_TYPE_IN_USE) and \
                    (part.doc_obj.in_zpool == ROOT_POOL):
                    return part

        return None
        
    @property
    def discovered_doc_obj(self):
        ''' Search for the same disk found during Target Discovery
    
            Returns the object in the discovered target tree of the DOC.
 
            Raise RuntimeError() if disk is not found in discovered target.
        '''
        doc = InstallEngine.get_instance().doc
        return(find_discovered_disk(self.doc_obj, doc))


class UIPartition(object):
    ''' Object used to keep track of partition related information for UI '''

    SOLARIS = 0xBF
    EXT_DOS = 0x05
    FDISK_EXTLBA = 0x0f
    UNUSED = None

    EDITABLE_PART_TYPES = [SOLARIS,
                           EXT_DOS,
                           FDISK_EXTLBA]

    KNOWN_LOGIC_TYPES = [UNUSED, SOLARIS]
    KNOWN_PART_TYPES = [UNUSED, SOLARIS, EXT_DOS] 
    
    def __init__(self, target_controller, parent=None, doc_obj=None):

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self._doc_obj = None
        self._empty_space_obj = None
        self.tc = target_controller
        self.all_parts = list()
        self._unused_parts_added = False
        self.parent = parent
        self.ui_type = UI_TYPE_NOT_USED
        self.cycle_types = None
        self.prev_cycle_idx = 0

        max_all_parts = MAX_SLICES

        for i in range(max_all_parts):
            part = UISlice(self.tc, parent=self)
            self.all_parts.append(part)

        if doc_obj != None:
            self.doc_obj = doc_obj

    @property
    def doc_obj(self):
        return self._doc_obj

    @doc_obj.setter
    def doc_obj(self, obj):
        if not isinstance(obj, Partition):
            raise TypeError("Object must be type Partition")

        self._doc_obj = obj
        self.ui_type = UI_TYPE_IN_USE
        if self.is_logical():
            self.cycle_types = UIPartition.KNOWN_LOGIC_TYPES
        else:
            self.cycle_types = UIPartition.KNOWN_PART_TYPES
            
    @property
    def empty_space_obj(self):
        return self._empty_space_obj

    @empty_space_obj.setter
    def empty_space_obj(self, obj):
        if not isinstance(obj, EmptySpace):
            raise TypeError("Object must be type EmptySpace")

        self._empty_space_obj = obj
        self.ui_type = UI_TYPE_EMPTY_SPACE
        self.cycle_types = UIPartition.KNOWN_PART_TYPES
    
    def set_unused(self):
        self.ui_type = UI_TYPE_NOT_USED
        self._empty_space_obj = None
        self._doc_obj = None

    @property
    def name(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.name
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return self.empty_space_obj.name
        else:
            raise RuntimeError("Partition not in use.  No name")

    @property
    def size(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.size
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return Size("0gb")
        else:
            raise RuntimeError("Partition not in use.  No size information.")

    @property
    def start_sector(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.start_sector
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return self.empty_space_obj.start_sector
        else:
            raise RuntimeError("Partition not in use.  No size information.")

    def get_end_sector(self):

        if self.ui_type == UI_TYPE_IN_USE:
            obj = self.doc_obj
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            obj = self.empty_space_obj
        else:
            raise RuntimeErorr("Partition not in used")

        size_in_sector = (obj.size).get(Size.sector_units)
        return (obj.start_sector + size_in_sector)

    def get_parts_in_use(self):
        in_use_parts = list()
        for part in self.all_parts:
            LOGGER.debug("looking at ui_type: %s", part.ui_type)
            if (part.ui_type == UI_TYPE_IN_USE) or \
               (part.ui_type == UI_TYPE_EMPTY_SPACE):
                in_use_parts.append(part)

        return in_use_parts  

    def add_unused_parts(self, no_part_ok=False):

        existing_parts = self.doc_obj.get_children(class_type=Slice)
        if (existing_parts is None) or (len(existing_parts) == 0):
            if no_part_ok:
                existing_parts = list()
            else:
                raise ValueError("Can't determine if this partition "
                                 "has slices")

        # remove the boot slice from the list of slices that gets displayed.
        boot_slice = None
        for slice in existing_parts:
            if int(slice.name) == BOOT_SLICE:
                boot_slice = slice
                break
        if boot_slice is not None:
            existing_parts.remove(boot_slice)

        numbers = range(MAX_SLICES)
        existing_parts.sort(name_sort)

        existing_gaps = self.doc_obj.get_gaps()
        # sort the gaps by size, smallest gaps first.  When using
        # the existing_gaps list, the largest gaps is used first, they
        # will be popped off the end of the list.
        existing_gaps.sort(size_sort)

        add_missed_parts(numbers, existing_parts, existing_gaps,
                         Size("1gb"), self.all_parts)

        # If there's a backup slice, move it to end of the list for display
        slice2 = self.all_parts[2]
        if slice2.ui_type == UI_TYPE_IN_USE:
            self.all_parts.remove(slice2)
            self.all_parts.append(slice2)

        if LOGGER.isEnabledFor(logging.DEBUG):
            for part in self.all_parts:
                try:
                    LOGGER.debug("UIPart: after fill unused...%s: %s..size=%s",
                                 str(part.name), part.get_description(),
                                 str(part.size))
                except Exception, ex:
                    LOGGER.debug("UIPart: after fill unused..." + str(ex))
                    pass

    def get_description(self):

        if self.ui_type == UI_TYPE_IN_USE:
            if self.doc_obj.is_extended:
                return EXTENDED_TEXT
            else:
                return libdiskmgt_const.PARTITION_ID_MAP[\
                    self.doc_obj.part_type]
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return UNUSED_TEXT
        else:
            raise RuntimeError("Partition not in use.  No descrption")

    @property
    def discovered_doc_obj(self):
        ''' Find the same object, if it exists, in the discovered
            object tree.
 
            Returns the object in discovered subtree, if found.
            Returns None otherwise.
        '''

        if self.ui_type != UI_TYPE_IN_USE:
            return None

        if self.parent is None:

            # The parent of the partition currently being worked on must be
            # the disk selected at the desired target
            doc = InstallEngine.get_instance().doc
            desired_disk = get_desired_target_disk(doc)

            # find the disk in discovered target
            parent_disc_obj = find_discovered_disk(desired_disk, doc)

        else:
            parent_disc_obj = self.parent.discovered_doc_obj

        # get all the discovered partitions 
        discovered_parts = parent_disc_obj.get_children(class_type=Partition)

        if not discovered_parts:
            return None

        # look through all the partitions, and find the one that
        # matches this one.  The partition name string is used
        # to identify the matching partition
        for part in discovered_parts:
            if str(part.name) == str(self.doc_obj.name):
                return part
            
        # Partition is not found.
        LOGGER.debug("can't find any partitions")
        return None

    def modified(self):
        ''' compare with the same object when it is discovered.
            only partition type and partition size is checked
            since that's the only thing the text installer allows
            users to change
 
            Returns True if size or partition type is changed compared to the
            discovered object.

            Returns False otherwise.
        '''
        if self.ui_type is not UI_TYPE_IN_USE:
            return False

        # object is newly added to the desired target.
        if self.discovered_doc_obj is None:
            return True
       
        if self.doc_obj.part_type != self.discovered_doc_obj.part_type:
            return True

        precision = Size(UI_PRECISION).get(Size.byte_units)
        discovered_size_byte = self.discovered_doc_obj.size.get(\
            Size.byte_units)
        size_byte = self.doc_obj.size.get(Size.byte_units)

        return (abs(discovered_size_byte - size_byte) > precision) 

    def get_max_size(self):
        '''Analyze nearby partitions and determine the total unused, available
        space that this partition could consume without affecting other
        partitions.
        
        Result is in gigabytes
        
        '''
        if self.is_logical():
            parts = self.parent.get_logicals()
            ext_part = self.parent.get_extended_partition()
        else:
            parts = self.parent.get_standards()
        if self not in parts:
            raise ValueError("This partition was not found on the "
                             "supplied disk")

        self_idx = parts.index(self)
        prev_part = None
        next_part = None

        for part in reversed(parts[:self_idx]):
            if part.ui_type == UI_TYPE_IN_USE:
                prev_part = part
                break
        for part in parts[self_idx + 1:]:
            if part.ui_type == UI_TYPE_IN_USE:
                next_part = part
                break

        LOGGER.debug("part:%s, idx: %s" % (self.get_description(), self_idx))

        msg_str = self.get_description() + ":"
        if prev_part is None:
            LOGGER.debug("No prev part")
            if self.is_logical():
                begin_avail_space = ext_part.doc_obj.start_sector
            else:
                begin_avail_space = 0
        else:
            try:
                begin_avail_space = prev_part.get_end_sector()
            except Exception:
                LOGGER.error("%s", prev_part)
                raise
        LOGGER.debug("begin_available space: %d", begin_avail_space)

        if next_part is None:
            LOGGER.debug("No next part")
            if self.is_logical():
                end_avail_space = ext_part.get_end_sector()
            else:
                disk_size = self.parent.doc_obj.disk_prop.dev_size
                end_avail_space = disk_size.get(Size.sector_units)
        else:
            end_avail_space = next_part.start_sector

        LOGGER.debug("end_available space: %d", end_avail_space)

        avail = end_avail_space - begin_avail_space

        LOGGER.debug("avail: %d", avail)

        if avail < 0:
            avail = 0

        return (Size(str(avail) + Size.sector_units))
    
    def editable(self):
        '''Returns True if it is possible to edit this partition's size'''

        if self.ui_type == UI_TYPE_IN_USE:
            if int(self.doc_obj.name) > MAX_PRIMARY_PARTS:
                return False

            if self.doc_obj.part_type in UIPartition.EDITABLE_PART_TYPES:
                return True
            else:
                return False

        return True

    def is_extended(self):
        if self.ui_type == UI_TYPE_IN_USE and self.doc_obj.is_extended:
            return True

        return False

    def is_logical(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.is_logical
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            if int(self.empty_space_obj.name) > MAX_PRIMARY_PARTS:
                return True
            return False
        else:
            raise RuntimeErorr("Partition not in used")

    def cycle_type(self, new_type=None, extra_type=None):
        '''Cycle this partition's type. Potential types are based on
        whether or not another Solaris partition exists, whether an extended
        partition exists, and whether or not this is a logical partition.
        
        If extra_types is passed in, it should be a list of other potential
        types. These types will also be considered when cycling.
        
        '''

        dump_doc("before change type")

        sol2_part = self.parent.get_solaris_data()
        has_solaris_part = (sol2_part is not None)
        
        ext_part = self.parent.get_extended_partition()
        has_extended = (ext_part is not None)
        
        # If this is the extended partition, and the Solaris2 partition
        # is a logical partition, allow for cycling from Extended to Solaris2
        if (has_extended and ext_part is self and
            has_solaris_part and sol2_part.is_logical()):
            has_solaris_part = False

        if new_type is not None:
            type_index = self.cycle_types.index(new_type)
            type_index = (type_index + 1) % len(self.cycle_types)
        else:
            if self.ui_type == UI_TYPE_EMPTY_SPACE:
                type_index = self.cycle_types.index(UIPartition.UNUSED)
                type_index = (type_index + 1) % len(self.cycle_types)
            else:
                # should have a doc_obj to reference
                if self.doc_obj.part_type in self.cycle_types:
                    type_index = self.cycle_types.index(self.doc_obj.part_type)
                    type_index = (type_index + 1) % len(self.cycle_types)
                else:
                    type_index = 0

        new_type = self.cycle_types[type_index]

        if new_type == UIPartition.UNUSED:
            LOGGER.debug("new type == unused")
        else:
            LOGGER.debug("new type == %s",
                         libdiskmgt_const.PARTITION_ID_MAP[new_type])

        if has_solaris_part and new_type == PART_TYPE_SOLARIS:
            self.cycle_type(new_type=new_type, extra_type=extra_type)
        elif has_extended and new_type == UIPartition.EXT_DOS:
            self.cycle_type(new_type=new_type, extra_type=extra_type)
        else:
            if self.ui_type == UI_TYPE_EMPTY_SPACE:
                LOGGER.debug("Partition used to be unsed.  Add partition with"
                             "type: %s, start_sec=%s, size=%s" %
                             (libdiskmgt_const.PARTITION_ID_MAP[new_type], 
                             self.empty_space_obj.start_sector,
                             self.get_max_size()))

                size_in_sector = self.empty_space_obj.size.get(\
                    Size.sector_units)

                new_part = self.parent.doc_obj.add_partition(self.name, \
                    self.empty_space_obj.start_sector, size_in_sector, \
                    size_units=Size.sector_units, partition_type=new_type)
                if new_part.is_solaris:
                    new_part.bootid = Partition.ACTIVE
            else:
                if new_type == UIPartition.UNUSED:
                    LOGGER.debug("Changing type to unused deleting %s",
                                 self.name)
                    self.parent.doc_obj.delete_partition(self.doc_obj)
                else:
                    LOGGER.debug("Changing type: %s to type %s",
                                 self.name,
                                 libdiskmgt_const.PARTITION_ID_MAP[new_type])
                    self.doc_obj.change_type(new_type)
                    if self.doc_obj.is_solaris:
                        self.doc_obj.bootid = Partition.ACTIVE
        dump_doc("after change type")

    def get_solaris_data(self):
        for part in self.all_parts:
            if part.ui_type == UI_TYPE_IN_USE and \
                part.doc_obj.in_zpool == ROOT_POOL:
                return part

        return None

    def __str__(self):
        result = ["UI Partiton: %s" % self.name]
        if self.ui_type == UI_TYPE_IN_USE:
            result.append("UI type: in use")
            result.append("Size: %s" % self.size)
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            result.append("UI type: empty space")
            result.append("Size: %s" % self.size)
        elif self.ui_type == UI_TYPE_NOT_USED:
            result.append("UI type: not used")
        else:
            result.append("UI type: UNKNOWN")
        return "\n".join(result)
    

class UISlice(object):
    ''' Object used to keep track of slice related information for UI '''

    UNUSED = None
    TYPES = [UNUSED, ROOT_POOL]

    def __init__(self, target_controller, parent=None):
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self._doc_obj = None
        self._empty_space_obj = None
        self.tc = target_controller
        self.all_parts = list()
        self._unused_parts_added = False
        self.parent = parent
        self.ui_type = UI_TYPE_NOT_USED

    @property
    def doc_obj(self):
        return self._doc_obj

    @doc_obj.setter
    def doc_obj(self, obj):
        if not isinstance(obj, Slice):
            raise TypeError("Object must be type Slice")

        self._doc_obj = obj
        self.ui_type = UI_TYPE_IN_USE

    @property
    def empty_space_obj(self):
        return self._empty_space_obj

    @empty_space_obj.setter
    def empty_space_obj(self, obj):
        if not isinstance(obj, EmptySpace):
            raise TypeError("Object must be type EmptySpace")

        self._empty_space_obj = obj
        self.ui_type = UI_TYPE_EMPTY_SPACE
    
    def set_unused(self):
        self.ui_type = UI_TYPE_NOT_USED
        self._empty_space_obj = None
        self._doc_obj = None

    @property
    def name(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.name
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return self.empty_space_obj.name
        else:
            raise RuntimeError("Partition not in use.  No name")

    @property
    def size(self):
        if self.ui_type == UI_TYPE_IN_USE:
            return self.doc_obj.size
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return Size("0gb")
        else:
            raise RuntimeError("Partition not in use.  No size information.")

    def get_end_sector(self):

        if self.ui_type == UI_TYPE_IN_USE:
            obj = self.doc_obj
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            obj = self.empty_space_obj
        else:
            raise RuntimeError("Partition not in use")

        size_in_sector = (obj.size).get(Size.sector_units)
        return (obj.start_sector + size_in_sector)

    def get_description(self):
        if self.ui_type == UI_TYPE_IN_USE:
            if self.doc_obj.tag == V_BACKUP:
                return BACKUP_SLICE_TEXT

            if self.doc_obj.in_zpool is not None:
                return self.doc_obj.in_zpool

            # try to get value from in_use dictionary
            in_use = self.doc_obj.in_use 
            if in_use is None:
                return self.doc_obj.name 

            if in_use['used_name']:
                return (in_use['used_name'])[0]

            if in_use['used_by']:
                return (in_use['used_by'])[0]

            return self.doc_obj.name 
        elif self.ui_type == UI_TYPE_EMPTY_SPACE:
            return UNUSED_TEXT
        else:
            raise RuntimeError("Slice not in use.")

    def get_max_size(self):
        '''Return the maximum possible size this slice could consume,
        in gigabytes, based on adjacent unused space
        
        '''

        if int(self.name) == BACKUP_SLICE:
            return self.size

        slices = self.parent.all_parts
        if self not in slices:
            raise ValueError("This slice not in the parent!")

        self_idx = slices.index(self)
        prev_slice = None
        next_slice = None
        
        # Search for the slice prior to this one with the largest "endblock"
        # Since existing slices may overlap, this could be any slice prior
        # to the current one.
        for slice_info in reversed(slices[:self_idx]):
            if (slice_info.ui_type != UI_TYPE_EMPTY_SPACE and \
                int(slice_info.name) != BACKUP_SLICE):
                if (prev_slice is None or
                    slice_info.get_end_sector() > prev_slice.get_end_sector()):
                    prev_slice = slice_info
        for slice_info in slices[self_idx + 1:]:
            if (slice_info.ui_type != UI_TYPE_EMPTY_SPACE and \
                int(slice_info.name) != BACKUP_SLICE):
                next_slice = slice_info
                break
        if prev_slice is None:
            start_pt = 0
        else:
            start_pt = prev_slice.get_end_sector()
        
        if next_slice is None:
            for slice_info in reversed(slices):
                # Use the backup slice to define the absolute max size
                # any given slice can be. (This is usually the last slice,
                # hence the use of a reversed iterator)
                if int(slice_info.name) == BACKUP_SLICE:
                    end_pt = slice_info.size.get(Size.sector_units)
                    break
            else:
                # Default to the parent's size if there happens to be no S2
                end_pt = self.parent.size.get(Size.sector_units)
        else:
            end_pt = next_slice.get_end_sector()

        max_space = end_pt - start_pt

        if max_space < 0:
            max_space = 0

        return (Size(str(max_space) + Size.sector_units))
    
    def editable(self):
        '''Returns True if it is possible to edit this partition's size'''
        if self.ui_type == UI_TYPE_IN_USE:
            if self.doc_obj.in_zpool == "rpool":
                return True

        return False

    @property
    def discovered_doc_obj(self):
        ''' Find the same object, if it exists, in the discovered
            object tree.
 
            Returns the object in discovered subtree, if found.
            Returns None otherwise.
        '''
        if self.ui_type != UI_TYPE_IN_USE:
            return None

        parent_disc_obj = self.parent.discovered_doc_obj

        # get all the discovered partitions 
        discovered_slices = parent_disc_obj.get_children(class_type=Slice)

        if (discovered_slices is None) or (len(discovered_slices) == 0):
            return None

        # look through all the partitions, and find the one matching that
        # matches this one.  The slice id is used
        # to identify the matching slice
        for slice in discovered_slices:
            if str(slice.name) == str(self.doc_obj.name):
                return slice
            
        # Slice is not found.
        return None

    def modified(self):
        ''' compare with the same object when it is discovered.
            only slice size is checked
            since that's the only thing the text installer allows
            users to change
 
            Returns True if slice type or size is changed compared to the
            discovered object.

            Returns False otherwise.
        '''
        if self.ui_type is not UI_TYPE_IN_USE:
            return False

        # object is newly added to the desired target.
        if self.discovered_doc_obj is None:
            return True
       
        precision = Size(UI_PRECISION).get(Size.byte_units)
        discovered_size_byte = self.discovered_doc_obj.size.get( \
            Size.byte_units)
        size_byte = self.doc_obj.size.get(Size.byte_units)

        if abs(discovered_size_byte - size_byte) > precision:
            return True

        return False

    def cycle_type(self, new_type=None, extra_type=None):
        '''Cycle this slide's type. 
        
        If extra_types is passed in, it should be a list of other potential
        types. These types will also be considered when cycling.
        
        '''

        dump_doc("before slice.cycle_type")

        has_solaris_data = (self.parent.get_solaris_data() is not None)

        types = set()
        types.update(UISlice.TYPES)
        if extra_type is not None:
            types.update(extra_type)
        types = list(types)
        types.sort()

        if new_type is not None:
            type_index = types.index(new_type)
            type_index = (type_index + 1) % len(types)
        else:
            if self.ui_type == UI_TYPE_EMPTY_SPACE:
                type_index = types.index(UISlice.UNUSED)
                type_index = (type_index + 1) % len(types)
            else:
                if self.doc_obj.in_zpool in types:
                    type_index = types.index(self.doc_obj.in_zpool)
                    type_index = (type_index + 1) % len(types)
                else:
                    type_index = 0

        new_type = types[type_index]

        if new_type == UIPartition.UNUSED:
            LOGGER.debug("new type == unused")
        else:
            LOGGER.debug("new type == %s", new_type)

        if has_solaris_data and new_type == ROOT_POOL:
            self.cycle_type(new_type=new_type, extra_type=extra_type)
        else:
            if self.ui_type == UI_TYPE_EMPTY_SPACE:
                if new_type == ROOT_POOL:
                    # making this the new root pool
                    size_in_sector = self.empty_space_obj.size.get( \
                        Size.sector_units)
                    LOGGER.debug("Used to be unused... adding new slice")
                    new_slice = self.parent.doc_obj.add_slice(self.name, \
                        self.empty_space_obj.start_sector, size_in_sector, \
                        size_units=Size.sector_units)
                    new_slice.in_zpool = ROOT_POOL
                    new_slice.in_vdev = DEFAULT_VDEV_NAME
                    new_slice.tag = V_ROOT
                else:
                    # setting it back to whatever value was discovered
                    discovered_obj = self.discovered_doc_obj
                    if discovered_obj is not None:
                        self.parent.doc_obj.insert_children(discovered_obj)
                    else:
                        LOGGER.debug("Unable to reset to discovered value")
                
            else:
                if new_type == UIPartition.UNUSED:
                    LOGGER.debug("Changing to unused, deleting")
                    LOGGER.debug("Target Call: deleting %s", self.name)
                    self.parent.doc_obj.delete_slice(self.doc_obj)
        dump_doc("AFTER change type")

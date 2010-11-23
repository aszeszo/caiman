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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Object to represent Disks
'''

from copy import copy, deepcopy
import logging
import platform

import osol_install.tgt as tgt
from osol_install.profile.disk_space import DiskSpace, round_to_multiple, \
                                            round_down
from osol_install.profile.partition_info import PartitionInfo, MIN_GAP_SIZE, \
                                            MIN_LOGICAL_GAP_SIZE
from osol_install.profile.slice_info import SliceInfo
from osol_install.text_install.ti_install_utils import InstallationError


def adjust_tgt_parts(tgt_objs, tgt_parent=None, ext_part=None):
    '''Modify a list of tgt.Partitions or tgt.Slices in place. For each item
    in the list, ensure that its offset is *past* the previous tgt object, and
    ensure that its size + offset doesn't cause it to overlap with the
    subsequent partition/slice.
    
    tgt.Partitions/Slices whose 'modified' flag is false are ignored. These
    are assumed to already exist on the disk (and assumed to not overlap);
    new Partitions/Slices are adjusted around the existing ones.
    
    tgt_objs: A list of tgt.Partitions or tgt.Slices. Logical partitions
                should NOT be mixed with standard partitions.
    tgt_parent: The tgt.Disk or tgt.Partition on which the tgt_objs are
                supposed to fit
    ext_part: The extended partition on which the tgt_objs are supposed to fit
    
    It is invalid to specify both tgt_parent and ext_part (ext_part will be
    ignored and the resulting disk layout could be indeterminate)
    
    '''
    
    if not tgt_objs:
        return
    
    if tgt_parent is not None:
        cylsz = tgt_parent.geometry.cylsz
        if isinstance(tgt_objs[0], tgt.Slice):
            # Checking slices on a partition/disk
            # Can start at 0
            min_offset = 0
            
            if isinstance(tgt_parent, tgt.Slice):
                # Using S2 to determine max. All blocks usable
                abs_max_end = tgt_parent.blocks
            else:
                # Using a disk or partition to determine max
                # Must leave 2 cylinders worth of space available
                abs_max_end = tgt_parent.blocks - 2 * cylsz
            
        else:
            # Checking partitions on a disk
            # Use the minimum partition offset as starting point
            # Don't exceed the end of the disk
            min_offset = PartitionInfo.MIN_OFFSET
            abs_max_end = tgt_parent.blocks
    elif ext_part is not None:
        # Logicals on an extended partition
        # Should have an offset past the start of the extended partition
        # Should not go past the end of the extended partition
        min_offset = ext_part.offset
        abs_max_end = ext_part.offset + ext_part.blocks
        cylsz = ext_part.geometry.cylsz
    else:
        raise TypeError("Must specify ext_part or tgt_parent keyword arg")
    
    for idx, tgt_obj in enumerate(tgt_objs):
        
        if tgt_obj.modified and tgt_obj.offset < min_offset:
            tgt_obj.offset = round_to_multiple(min_offset, cylsz)
        
        if tgt_obj is tgt_objs[-1]:
            # Last item in the list - don't let this obj slide past the end
            # of the disk/partition
            max_end = abs_max_end
        else:
            # More items in the list - don't let this obj overlap with the
            # next item
            max_end = tgt_objs[idx+1].offset - 1
        
        if tgt_obj.modified and tgt_obj.offset + tgt_obj.blocks > max_end:
            shift = (tgt_obj.offset + tgt_obj.blocks) - max_end
            new_blocks = tgt_obj.blocks - shift
            tgt_obj.blocks = round_down(new_blocks, cylsz)
        
        # Minimum offset for next obj should be past the end of this obj.
        # Preserve the current value of min_offset if it happens to be greater
        # than the end of this obj (for example, if this slice overlaps with,
        # and lies completely within, a prior slice)
        min_offset = max(min_offset, tgt_obj.offset + tgt_obj.blocks + 1)


# Pylint gets confused and thinks DiskInfo.size is a string but it's
# actually a DiskSpace object
# pylint: disable-msg=E1103
class DiskInfo(object):
    '''Represents a single disk on the system.'''
    
    FDISK = "fdisk"
    GPT = "gpt"
    VTOC = "vtoc"
    
    def __init__(self, blocksz=512, cylsz=None, boot=False, partitions=None,
                 slices=None, controller=None, label=None, name=None,
                 removable=False, serialno=None, size=None, vendor=None,
                 tgt_disk=None):
        '''Constructor takes either a tgt_disk, which should be a tgt.Disk
        object, or a set of parameters. If tgt_disk is supplied, all other
        parameters are ignored.
        
        '''
        self._size = None
        self._tgt_disk = tgt_disk
        self._ext_part_idx = 0
        self._sol_part_idx = 0
        self._unused_parts_added = False
        if tgt_disk:
            self.blocksz = tgt_disk.geometry.blocksz
            self.cylsz = tgt_disk.geometry.cylsz
            self.boot = tgt_disk.boot
            self.partitions = []
            self.slices = []
            if tgt_disk.children:
                if isinstance(tgt_disk.children[0], tgt.Slice):
                    for child in tgt_disk.children:
                        self.slices.append(SliceInfo(tgt_slice=child))
                else:
                    for child in tgt_disk.children:
                        self.partitions.append(PartitionInfo(tgt_part=child))
            self.controller = tgt_disk.controller
            self.label = set()
            if tgt_disk.gpt:
                self.label.add(DiskInfo.GPT)
            if tgt_disk.vtoc:
                self.label.add(DiskInfo.VTOC)
            if tgt_disk.fdisk:
                self.label.add(DiskInfo.FDISK)
            self.name = tgt_disk.name
            self.removable = tgt_disk.removable
            self.serialno = tgt_disk.serialno
            size = str(tgt_disk.blocks * self.blocksz) + "b"
            self.size = size
            self.vendor = tgt_disk.vendor
        else:
            self.blocksz = blocksz
            self.cylsz = cylsz
            self.boot = boot
            if partitions and slices:
                raise ValueError("A disk cannot have both partitions and"
                                 " slices")
            if partitions is None:
                partitions = []
            self.partitions = partitions
            if slices is None:
                slices = []
            self.slices = slices
            self.controller = controller
            self.label = label
            self.name = name
            self.removable = removable
            self.serialno = serialno
            self.size = size
            self.vendor = vendor
        self.use_whole_segment = False
        
        if platform.processor() == "i386":
            self.was_blank = not bool(self.partitions)
        else:
            self.was_blank = not bool(self.slices)
    
    def __str__(self):
        result = ["Disk Info (%s):" % self.name]
        result.append("Size: %s" % self.size)
        for part in self.partitions:
            result.append(str(part))
        for slice_info in self.slices:
            result.append(str(slice_info))
        return "\n".join(result)
    
    def get_type(self):
        '''Return this disk's 'type' (controller) as a string'''
        if self.controller is None:
            return ""
        else:
            return self.controller.upper()
    
    type = property(get_type)
    
    def get_size(self):
        '''Returns this disk's size as a DiskSpace object'''
        return self._size
    
    def set_size(self, size):
        '''Set this disk's size. size must be either a DiskSpace or a string
        that will be accepted by DiskSpace.__init__
        
        '''
        if isinstance(size, DiskSpace):
            self._size = deepcopy(size)
        else:
            self._size = DiskSpace(size)
    
    size = property(get_size, set_size)
    
    def get_blocks(self):
        '''Return the number of blocks on this disk'''
        return int(self.size.size_as("b") / self.blocksz)
    
    blocks = property(get_blocks)
    
    def get_solaris_data(self, check_multiples=False):
        '''Find and return the solaris partition (x86) or install target
        slice (sparc) on this disk.
        
        Returns None if one does not exist.
        
        '''
        if platform.processor() == "i386":
            parts = self.partitions
        else:
            parts = self.slices
        
        if (not check_multiples and self._sol_part_idx < len(parts) and
            parts[self._sol_part_idx].is_solaris_data()):
            return parts[self._sol_part_idx]
        
        solaris_data = None
        for part in parts:
            if part.is_solaris_data():
                if solaris_data is None:
                    self._sol_part_idx = parts.index(part)
                    solaris_data = part
                    if not check_multiples:
                        break
                elif check_multiples:
                    raise ValueError("Found multiple children with "
                                     "solaris data")
        
        return solaris_data
    
    def get_extended_partition(self):
        '''Find and return the Extended partition on this disk.
        Returns None if this disk has no extended partition.
        
        '''
        if (self._ext_part_idx < len(self.partitions) and
            self.partitions[self._ext_part_idx].is_extended()):
            return self.partitions[self._ext_part_idx]
        
        for part in self.partitions:
            if part.is_extended():
                self._ext_part_idx = part
                return part
        
        return None
    
    def get_logicals(self):
        '''Retrieve all the logicals on this disk'''
        logicals = []
        for part in self.partitions:
            if part.is_logical():
                logicals.append(part)
        return logicals
    
    def get_standards(self):
        '''Return all non-logical partitions'''
        standards = []
        for part in self.partitions:
            if not part.is_logical():
                standards.append(part)
        return standards
    
    def remove_logicals(self):
        '''Delete the logicals from this disk'''
        remove_all = []
        for part in self.partitions:
            if part.is_logical():
                remove_all.append(part)
        for part in remove_all:
            self.partitions.remove(part)
    
    def collapse_unused_logicals(self):
        '''Collapse adjacent unused logical partitions'''
        logicals = self.get_logicals()
        removal_count = 0
        for idx, logical in enumerate(logicals[:-1]):
            next_log = logicals[idx+1]
            if (logical.id == PartitionInfo.UNUSED and
                next_log.id == PartitionInfo.UNUSED):
                self.partitions.remove(next_log)
                removal_count += 1
        return removal_count
    
    def add_unused_parts(self):
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
        
        This method adds unused parts exactly once.

        '''
        if self._unused_parts_added:
            return

        if self.partitions:
            use_partitions = True
            parts = self.get_standards()
            parts.sort(cmp=PartitionInfo.compare)
            numbers = range(1, PartitionInfo.MAX_STANDARD_PARTITIONS + 1)
            start_pt = 0
        elif self.slices:
            use_partitions = False
            parts = copy(self.slices)
            parts.sort(cmp=SliceInfo.compare)
            numbers = range(SliceInfo.MAX_SLICES)
            numbers.remove(SliceInfo.BACKUP_SLICE)
            start_pt = 0
        else:
            raise ValueError("Cannot determine if this disk has partitions"
                             " or slices")
        backup_part = None
        if not use_partitions:
            for part in parts:
                if part.number == SliceInfo.BACKUP_SLICE:
                    backup_part = part
            if backup_part is not None:
                parts.remove(backup_part)
        
        min_gap_size = MIN_GAP_SIZE.size_as("b")
        gaps = []
        end_pt = 0
        for part in parts:
            if part.number in numbers:
                numbers.remove(part.number)
            start_pt = part.offset.size_as("b")
            gap_size = start_pt - end_pt
            if gap_size > min_gap_size:
                gaps.append((gap_size, end_pt))
            end_pt = part.get_endblock().size_as("b")
        end_disk = self.size.size_as("b")
        gap_size = end_disk - end_pt
        if gap_size > min_gap_size:
            gaps.append((gap_size, end_pt))
        # Sorting a list of tuples will sort by the first item in the tuple,
        # In this case, gap_size, such that the smallest gap is first.
        # Then, the largest gaps can be popped off the end of the list
        gaps.sort()
        for part_num in numbers:
            if gaps:
                gap = gaps.pop()
                offset = str(gap[1]) + "b"
            else:
                offset = str(end_pt) + "b"
            if use_partitions:
                new_part = PartitionInfo(part_num=part_num, offset=offset)
                self.partitions.append(new_part)
            else:
                new_part = SliceInfo(slice_num=part_num, offset=offset)
                self.slices.append(new_part)
        if not use_partitions and backup_part is None:
            new_part = SliceInfo(slice_num=SliceInfo.BACKUP_SLICE,
                                 size=self.size)
            self.slices.append(new_part)
        self.sort_disk_order()
        
        # now process the logical partitions
        if use_partitions:
            logicals = self.get_logicals()
            ext_part = self.get_extended_partition()
            if ext_part is not None:
                min_logical_gap_size = MIN_LOGICAL_GAP_SIZE.size_as("b")
                logical_gaps = []
                end_pt = ext_part.offset.size_as("b")
                                 	
                numbers = range(PartitionInfo.FIRST_LOGICAL, 
                    PartitionInfo.FIRST_LOGICAL + 
                    PartitionInfo.MAX_LOGICAL_PARTITIONS)
                for logical in logicals:
                    numbers.remove(logical.number)
                    start_pt = logical.offset.size_as("b") 
                    logical_gap_size = start_pt - end_pt
                    if logical_gap_size > min_logical_gap_size:
                        logical_gaps.append((logical_gap_size, end_pt))
                    end_pt = logical.get_endblock().size_as("b")
               
                end_disk = ext_part.get_endblock().size_as("b")
                logical_gap_size = end_disk - end_pt
                if logical_gap_size > min_logical_gap_size:
                    logical_gaps.append((logical_gap_size, end_pt))

                # Sorting a list of tuples will sort by the first item
                # in the tuple, in this case, logical_gap_size, such that
                # the smallest gap is first.
                logical_gaps.sort()    
                for number in numbers:
                    if logical_gaps:
                        logical_gap = logical_gaps.pop()
                        offset = str(logical_gap[1]) + "b"
                    else:
                        break
                    new_part = PartitionInfo(part_num=number, offset=offset)
                    self.partitions.append(new_part)

                self.sort_disk_order()

        self._unused_parts_added = True

    def append_unused_logical(self):
        '''Append a single unused logical partition to the disk.
        The last logical partition is assumed to be something *other*
        than an 'unused' partition
        
        '''
        ext_part = self.get_extended_partition()
        if ext_part is None:
            return None
        logicals = self.get_logicals()
        
        if len(logicals) > 0:
            last_log = logicals[-1]
            offset = last_log.get_endblock()
            part_num = last_log.number + 1
        else: # First logical on this disk
            offset = ext_part.offset
            part_num = PartitionInfo.FIRST_LOGICAL
        new_part = PartitionInfo(part_num=part_num, offset=offset)
        self.partitions.append(new_part)
        return new_part
    
    def sort_disk_order(self):
        '''Sort partitions/slices in disk order'''
        self.partitions.sort(cmp=PartitionInfo.compare)
        self.slices.sort(cmp=SliceInfo.compare)
    
    def get_parts(self):
        '''Return the list of partitions or slices, depending on what
        this disk has on it
        
        '''
        if self.partitions:
            return self.partitions
        else:
            return self.slices
    
    def to_tgt(self):
        '''Transfer the install profile information to tgt format

        ''' 
        if self._tgt_disk is not None:
            tgt_disk = self._tgt_disk
        else:
            name = self.name
            blocks = round_to_multiple(self.get_blocks(), self.cylsz)
            controller = self.controller
            boot = self.boot
            removable = self.removable
            vendor = self.vendor
            serialno = self.serialno
            geo = tgt.Geometry(cylsz=self.cylsz, blocksz=self.blocksz)
            tgt_disk = tgt.Disk(geo, name, blocks, controller=controller,
                                boot=boot, removable=removable,
                                vendor=vendor, serialno=serialno)
        
        backup_slice = None
        if self.partitions:
            sl_iter = iter(self.get_solaris_data().slices)
        else:
            sl_iter = iter(self.slices)
        for slice_ in sl_iter:
            if slice_.number == SliceInfo.BACKUP_SLICE:
                backup_slice = slice_._tgt_slice
                break
        
        tgt_disk.use_whole = self.use_whole_segment
        
        child_list = ()
        if not tgt_disk.use_whole:
            for partition in self.partitions:
                part = partition.to_tgt(self)
                if part is not None:
                    child_list += (part,)
                    tgt_disk.fdisk = True
            if not child_list:
                for slice_info in self.slices:
                    sl = slice_info.to_tgt(self)
                    if sl is not None:
                        child_list += (sl,)
                        tgt_disk.vtoc = True
        
        tgt_disk.children = child_list
        slice_parent = tgt_disk
        if child_list and isinstance(child_list[0], tgt.Partition):
            standards = []
            logicals = []
            ext_part = None
            for child in child_list:
                if child.id == PartitionInfo.DELETED:
                    continue
                if child.number > PartitionInfo.MAX_STANDARD_PARTITIONS:
                    logicals.append(child)
                else:
                    standards.append(child)
                    if child.id in PartitionInfo.EXTENDED:
                        ext_part = child
                if child.id == PartitionInfo.SOLARIS:
                    slice_parent = child
            adjust_tgt_parts(standards, tgt_parent=tgt_disk)
            if logicals:
                adjust_tgt_parts(logicals, ext_part=ext_part)
        
        slices = []
        for child in slice_parent.children:
            if child.number == SliceInfo.BACKUP_SLICE:
                continue
            slices.append(child)
        if backup_slice is not None:
            slice_parent = backup_slice
        adjust_tgt_parts(slices, tgt_parent=slice_parent)
        
        # print out the tgt_disk object for debugging
        logging.debug("%s", tgt_disk)
        
        return tgt_disk
    
    def create_default_layout(self):
        '''Create a reasonable default layout consisting of a single slice
        or partition that consumes the whole disk. In the slice case, also
        add the traditional backup slice.
        
        '''
        # do not allow size to exceed MAX_VTOC
        maxsz = min(self.get_size(), SliceInfo.MAX_VTOC)
        
        if platform.processor() == "sparc":
            whole_part = SliceInfo(slice_num=0, size=self.size,
                                   slice_type=SliceInfo.ROOT_POOL)
            backup_part = SliceInfo(slice_num=SliceInfo.BACKUP_SLICE,
                                    size=self.size)
            self.slices = [whole_part, backup_part]
            self.label.add(DiskInfo.VTOC)
        else:
            whole_part = PartitionInfo(part_num=1, size=maxsz,
                                       partition_id=PartitionInfo.SOLARIS)
            whole_part.create_default_layout()
            self.partitions = [whole_part]
            self.label.add(DiskInfo.FDISK)
    
    def get_install_dev_name_and_size(self):
        '''Returns the installation device name string and the size of the
        install device in MB.
        
        '''
        install_target = self.get_install_target()
        if install_target is None:
            logging.error("Failed to find device to install onto")
            raise InstallationError
        name = self.name + "s" + str(install_target.number)
        size = (int)(install_target.size.size_as("mb"))
        return (name, size)
    
    def get_install_device_size(self):
        '''Returns the size of the install device in MB. '''
        # Size is the second item in the tuple
        return self.get_install_dev_name_and_size()[1]
    
    def get_install_device(self):
        '''Returns the install device name string. '''
        # Install device is the first item in the tuple
        return self.get_install_dev_name_and_size()[0]
    
    def get_install_target(self):
        '''Returns the slice target of this installation'''
        try:
            install_target = self
            if install_target.partitions:
                install_target = install_target.get_solaris_data()
            install_target = install_target.get_solaris_data()
            return install_target
        except AttributeError:
            logging.debug("Install target not yet defined")
            return None
    
    def get_install_root_pool(self):
        ''' Returns name of the pool to be used for installation '''
        install_slice = self.get_install_target()
        if install_slice is None:
            logging.error("Failed to find device to install onto")
            raise InstallationError
        slice_type = install_slice.get_type()
        return (str(slice_type[1]))

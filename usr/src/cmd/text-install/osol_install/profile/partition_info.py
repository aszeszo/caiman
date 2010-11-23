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
Object to represent Partitions
'''

from copy import copy, deepcopy
import logging

import osol_install.tgt as tgt
from osol_install.profile.disk_space import DiskSpace, round_to_multiple, \
                                            round_down
from osol_install.profile.slice_info import SliceInfo, UI_PRECISION

# Minimum space between partitions before presenting it as 'unused' space
# Used by PartitionInfo.add_unused_parts()
MIN_GAP_SIZE = DiskSpace("1gb")

# Minimum space between logical partitions before presenting it as
# 'unused' space. Used by DiskInfo.add_unused_parts()
MIN_LOGICAL_GAP_SIZE = DiskSpace("100mb")

# Pylint gets confused and thinks PartitionInfo.size and PartitionInfo.offset
# are strings, but they are actually DiskSpace objects
# pylint: disable-msg=E1103
class PartitionInfo(object):
    '''Represents a single partition on a disk on the system.
    
    EDITABLE_PART_TYPES is a list of primary partition types for which
    modifying the size is supported.
    
    KNOWN_PART_TYPES is a list of primary partition types which can be
    created out of a previously unused block of space
    
    *_LOGIC_TYPES represent the same concepts applied to logical partitions'''
    
    UNUSED = None
    UNUSED_TEXT = "Unused"
    SOLARIS = 0xBF
    SOLARIS_ONE = 0x82
    EXT_DOS = 0x05
    FDISK_EXTLBA = 0x0f
    DELETED = 0
    
    LOGICAL_BLOCK_PAD = 63
    
    EXTENDED = [EXT_DOS, FDISK_EXTLBA]
    EXTENDED_TEXT = "Extended"
    
    EDITABLE_PART_TYPES = [SOLARIS,
                           EXT_DOS,
                           FDISK_EXTLBA]
    
    EDITABLE_LOGIC_TYPES = [SOLARIS]
    
    KNOWN_PART_TYPES = [UNUSED,
                        SOLARIS,
                        EXT_DOS]
    
    KNOWN_LOGIC_TYPES = [UNUSED]
    KNOWN_LOGIC_TYPES.extend(EDITABLE_LOGIC_TYPES)
    
    MIN_OFFSET = 1
    
    MAX_STANDARD_PARTITIONS = 4
    MAX_LOGICAL_PARTITIONS = 32
    FIRST_LOGICAL = 5
    
    def __init__(self, part_num=None, offset="0gb", size="0gb", slices=None,
                 blocksz=512, partition_id=UNUSED, tgt_part=None):
        '''Constructor takes either a tgt_part, which should be a tgt.Partition
        object, or a set of parameters. If tgt_part is supplied, all other
        parameters are ignored.
        
        '''
        self._sol_slice_idx = 0
        self._offset = None
        self._size = None
        self._tgt_part = tgt_part
        self.original_type = None
        self.previous_size = None
        if tgt_part:
            self.slices = []
            for child in tgt_part.children:
                self.slices.append(SliceInfo(tgt_slice=child))
            self.number = tgt_part.number
            offset = str(tgt_part.offset * tgt_part.geometry.blocksz) + "b"
            self.offset = offset
            size = str(tgt_part.blocks * tgt_part.geometry.blocksz) + "b"
            self.blocksz = tgt_part.geometry.blocksz
            self.size = size
            self.id = tgt_part.id
        else:
            if slices is None:
                slices = []
            self.slices = slices
            self.number = part_num
            self.offset = offset
            self.blocksz = blocksz
            self.size = size
            self.id = partition_id
        self.use_whole_segment = False
        self.boot_slice = None
        self.alt_slice = None
        self.orig_slices = copy(self.slices)
    
    def __str__(self):
        result = ["Partition Info (%s):" % self.number]
        result.append("Type: %s" % self.type)
        result.append("Offset: %s" % self.offset)
        result.append("Size: %s" % self.size)
        for slice_info in self.slices:
            result.append(str(slice_info))
        return "\n".join(result)
    
    @staticmethod
    def compare(left, right):
        '''Compare 2 tgt.Partition or PartitionInfo's in such a way that
        passing this method to list.sort() results in a list sorted by disk
        order.
        
        '''
        if isinstance(left, tgt.Partition):
            left = PartitionInfo(left)
        if not isinstance(left, PartitionInfo):
            return NotImplemented
        
        if isinstance(right, tgt.Partition):
            right = PartitionInfo(right)
        if not isinstance(right, PartitionInfo):
            return NotImplemented
        
        if left.is_logical() == right.is_logical():
            left_off = left.offset.size_as("b")
            right_off = right.offset.size_as("b")
            if left_off < right_off:
                return -1
            elif left_off > right_off:
                return 1
            else:
                return 0
        elif left.is_logical():
            return 1
        else:
            return -1
    
    def get_offset(self):
        '''Return this partition's offset as a DiskSpace object'''
        return self._offset
    
    def set_offset(self, offset):
        '''Set this partition's offset. Must be either a DiskSpace object
        or a string that will be accepted by DiskSpace.__init__
        
        '''
        if isinstance(offset, DiskSpace):
            self._offset = deepcopy(offset)
        else:
            self._offset = DiskSpace(offset)
    
    def get_size(self):
        '''Returns this partition's size as a DiskSpace object'''
        return self._size
    
    def set_size(self, size):
        '''Set this partition's size. size must be either a DiskSpace or a
        string that will be accepted by DiskSpace.__init__
        
        '''
        if isinstance(size, DiskSpace):
            self._size = deepcopy(size)
        else:
            self._size = DiskSpace(size)
    
    def get_type(self):
        '''Return this object's partition type'''
        return self.id
    
    def get_blocks(self):
        '''Return the number of blocks on this partition'''
        return int(self.size.size_as("b") / self.blocksz)
    
    blocks = property(get_blocks)
    offset = property(get_offset, set_offset)
    size = property(get_size, set_size)
    type = property(get_type)
    
    def is_logical(self):
        '''Returns true if this is a logical partition'''
        if self.number is not None:
            return (self.number > PartitionInfo.MAX_STANDARD_PARTITIONS)
        else:
            return False
    
    def is_extended(self):
        '''Returns True if this is an Extended Partition, False otherwise'''
        return (self.id in PartitionInfo.EXTENDED)
    
    def cycle_type(self, disk, extra_types=None):
        '''Cycle this partition's type. Potential types are based on
        whether or not another Solaris partition exists, whether an extended
        partition exists, and whether or not this is a logical partition.
        
        If extra_types is passed in, it should be a list of other potential
        types. These types will also be considered when cycling.
        
        '''
        if extra_types is None:
            extra_types = []
        types = set()
        sol2_part = disk.get_solaris_data()
        has_solaris_part = (sol2_part is not None)
        
        ext_part = disk.get_extended_partition()
        has_extended = (ext_part is not None)
        
        # If this is the extended partition, and the Solaris2 partition
        # is a logical partition, allow for cycling from Extended to Solaris2
        if (has_extended and ext_part is self and
            has_solaris_part and sol2_part.is_logical()):
            has_solaris_part = False
        
        if self.is_logical():
            types.update(PartitionInfo.KNOWN_LOGIC_TYPES)
        else:
            types.update(PartitionInfo.KNOWN_PART_TYPES)
        types.update(extra_types)
        types = list(types)
        types.sort()
        if self.id in types:
            logging.debug("type in types, cycling next")
            type_index = types.index(self.id)
            type_index = (type_index + 1) % len(types)
            self.id = types[type_index]
            logging.debug("now %s", self.id)
        else:
            logging.debug("type NOT in types, setting to types[0]")
            self.original_type = self.id
            self.id = types[0]
        if self.id == PartitionInfo.UNUSED:
            self.previous_size = self.size
            self.size = "0GB"
        elif has_solaris_part and self.id == PartitionInfo.SOLARIS:
            self.cycle_type(disk, extra_types)
        elif has_extended and self.is_extended():
            self.cycle_type(disk, extra_types)
    
    def get_description(self):
        '''
        Return a string suitable for representing this partition in a UI
        '''
        description = None
        if self.id == PartitionInfo.UNUSED:
            description = PartitionInfo.UNUSED_TEXT
        elif self.is_extended():
            description = PartitionInfo.EXTENDED_TEXT
        else:
            description = tgt.Partition.ID[self.id]
        return str(description)
    
    def get_max_size(self, disk):
        '''Analyze nearby partitions and determine the total unused, available
        space that this partition could consume without affecting other
        partitions.
        
        Result is in gigabytes
        
        '''
        if self.is_logical():
            parts = disk.get_logicals()
            ext_part = disk.get_extended_partition()
        else:
            parts = disk.get_standards()
        if self not in parts:
            raise ValueError("This partition was not found on the "
                             "supplied disk")
        self_idx = parts.index(self)
        prev_part = None
        next_part = None
        for part in reversed(parts[:self_idx]):
            if part.id != PartitionInfo.UNUSED:
                prev_part = part
                break
        for part in parts[self_idx+1:]:
            if part.id != PartitionInfo.UNUSED:
                next_part = part
                break
        msg_str = self.get_description() + ":"
        if prev_part is None:
            msg_str += "No prev part:"
            if self.is_logical():
                begin_avail_space = ext_part.offset.size_as("gb")
            else:
                begin_avail_space = 0
        else:
            try:
                begin_avail_space = prev_part.get_endblock().size_as("gb")
                msg_str += ("prev_part(%s).endblock=%s:" %
                            (prev_part.type, begin_avail_space))
            except Exception:
                logging.error("%s", prev_part)
                raise
        if next_part is None:
            if self.is_logical():
                msg_str += ("no next_part (ext_part size=%s):" %
                            ext_part.size.size_as("gb"))
                end_avail_space = ext_part.get_endblock().size_as("gb")
            else:
                msg_str += ("no next_part (disk_size=%s):" % 
                            disk.size.size_as("gb"))
                end_avail_space = disk.size.size_as("gb")
        else:
            end_avail_space = next_part.offset.size_as("gb")
            msg_str += ("next_part(%s).offset=%s:" %
                        (next_part.type, end_avail_space))
        logging.debug(msg_str)
        avail = min(end_avail_space - begin_avail_space,
                    SliceInfo.MAX_VTOC.size_as("gb"))
        if avail < 0:
            avail = 0
        return avail
    
    def get_endblock(self):
        '''Returns the ending 'offset' of this partition, as a DiskSpace'''
        try:
            start_pt = self.offset.size_as("b")
            end_pt = self.size.size_as("b")
            return DiskSpace(str(start_pt + end_pt) + "b")
        except AttributeError:
            raise AttributeError("%s does not have valid size data" %
                                 self.__class__.__name__)
    
    def get_solaris_data(self, check_multiples=False):
        '''Returns the slice within this partition that has the Solaris root
        pool.
        
        Raises AttributeError if there is no such slice
        
        '''
        if (not check_multiples and self._sol_slice_idx < len(self.slices) and
            self.slices[self._sol_slice_idx].is_solaris_data()):
            return self.slices[self._sol_slice_idx]
        
        solaris_data = None
        for slice_info in self.slices:
            if slice_info.is_solaris_data():
                if solaris_data is None:
                    self._sol_slice_idx = self.slices.index(slice_info)
                    solaris_data = slice_info
                    if not check_multiples:
                        break
                elif check_multiples:
                    raise ValueError("Found multiple slices with 'solaris'"
                                     "data on them")
        
        return solaris_data
    
    def editable(self, disk):
        '''Returns True if it is possible to edit this partition's size'''
        if self.is_extended():
            for logical in disk.get_logicals():
                if logical.id != PartitionInfo.UNUSED:
                    return False
        if self.id in PartitionInfo.EDITABLE_PART_TYPES:
            return True
        else:
            return False
    
    def sort_disk_order(self):
        '''Sort slices by disk order'''
        self.slices.sort(cmp=SliceInfo.compare)
    
    def get_parts(self):
        '''Return the slices on this partition. Provided for interface
        compatibility with DiskInfo.get_parts()
        
        '''
        return self.slices
    
    def add_unused_parts(self):
        '''Sort through the non-logical partitions, find the largest gaps,
        and create additional Unused partitions such that the number of
        non-logical partitions == MAX_STANDARD_PARTITIONS.
        
        Gaps smaller than 1 GB are ignored.
        
        Also note that the x86 boot slice (8) and x86 alt slice (9) are 
        hidden from view after calling this method. They're stored for 
        later retrieval in self.boot_slice and self.alt_slice respectively
        
        '''
        boot_slice = None
        for part in self.slices:
            if part.number == SliceInfo.x86_BOOT_SLICE:
                boot_slice = part
        if boot_slice is not None:
            self.boot_slice = boot_slice
            self.slices.remove(boot_slice)

        alt_slice = None
        for part in self.slices:
            if part.number == SliceInfo.x86_ALT_SLICE:
                alt_slice = part
        if alt_slice is not None:
            self.alt_slice = alt_slice
            self.slices.remove(alt_slice)
        
        parts = copy(self.slices)
        parts.sort(cmp=SliceInfo.compare)
        numbers = range(SliceInfo.MAX_SLICES)
        numbers.remove(SliceInfo.BACKUP_SLICE)
        backup_part = None
        for part in parts:
            if part.number == SliceInfo.BACKUP_SLICE:
                backup_part = part
                break
        if backup_part is not None:
            parts.remove(backup_part)
        start_pt = 0
        
        min_gap_size = MIN_GAP_SIZE.size_as("b")
        gaps = []
        end_pt = 0
        for part in parts:
            if part.number == SliceInfo.BACKUP_SLICE:
                continue
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
            new_part = SliceInfo(slice_num=part_num, offset=offset)
            self.slices.append(new_part)
            if len(self.slices) >= SliceInfo.MAX_SLICES:
                break
        if backup_part is None:
            new_part = SliceInfo(slice_num=SliceInfo.BACKUP_SLICE,
                                 size=self.size)
            self.slices.append(new_part)
        self.sort_disk_order()
    
    def adjust_offset(self, parent):
        '''Adjust this partition's offset such that it no longer overlaps
        with subsequent partitions, by comparing this partition's trailing
        edge with the next used partition's offset.
        
        Additionally, any unused partitions found are shifted to align
        with this partition's trailing edge, if needed
        
        '''
        if self.is_logical():
            parts = parent.get_logicals()
            ext_part = parent.get_extended_partition()
        else:
            parts = parent.get_standards()
        
        self_idx = parts.index(self)
        endblock = self.get_endblock()
        endblock_bytes = endblock.size_as("gb")
        unused_parts = []
        shift = None
        for part in parts[self_idx+1:]:
            if part.offset.size_as("gb") < endblock_bytes:
                if part.id == PartitionInfo.UNUSED:
                    unused_parts.append(part)
                else:
                    shift = endblock_bytes - part.offset.size_as("gb")
                    break
            else:
                break
        else:
            # Check to ensure we don't slip past the end of the disk
            # (or extended partition, if this is a logical partition)
            if self.is_logical():
                max_endblock = ext_part.get_endblock().size_as("gb")
            else:
                max_endblock = parent.size.size_as("gb")
            if endblock_bytes > max_endblock:
                shift = endblock_bytes - max_endblock
        
        if shift is not None:
            new_offset = max(0, self.offset.size_as("gb") - shift)
            self.offset = str(new_offset) + "gb"
        
        new_endblock = self.get_endblock()
        for part in unused_parts:
            part.offset = new_endblock
    
    def to_tgt(self, parent):
        '''Transfer the install profile information to tgt format'''
        
        if not self.modified():
            part = deepcopy(self._tgt_part)
        else:
            # Something changed, need to create a new one
            geo = tgt.Geometry(parent.cylsz, self.blocksz)
            
            if self.type == PartitionInfo.UNUSED:
                # Partition was deleted. Return an empty partition,
                # which will indicate to target instantiation to
                # delete this partition
                return tgt.Partition(geo, self.number, PartitionInfo.DELETED,
                                     0, 0, modified=True)
            
            offset = int(self.offset.size_as("b") / self.blocksz)
            offset = max(PartitionInfo.MIN_OFFSET, offset)
            blocks = self.get_blocks()
            
            if self.is_logical() or self.is_extended():
                # Ensure that the required minimum amount of empty space
                # precedes and follows this logical partition
                offset += PartitionInfo.LOGICAL_BLOCK_PAD
                blocks -= 2 * PartitionInfo.LOGICAL_BLOCK_PAD
            
            # offset must be a multiple of tgt.Geometry.cylsz
            offset = round_to_multiple(offset, geo.cylsz)
            blocks = round_down(blocks, geo.cylsz)
            
            part = tgt.Partition(geo, self.number, self.id, offset, blocks,
                                 modified=True)
        
        part.use_whole = self.use_whole_segment
        
        child_list = ()
        if not part.use_whole:
            slices = []
            if self.boot_slice is not None:
                slices.append(self.boot_slice)
            if self.alt_slice is not None:
                slices.append(self.alt_slice)
            slices.extend(self.slices)
            for slice_info in slices:
                sl = slice_info.to_tgt(parent)
                if sl is not None:
                    child_list += (sl,)
        
        part.children = child_list
        return (part)
         
    def modified(self, off_by=UI_PRECISION):
        '''Returns False if and only if this PartitionInfo was instantiated
        from a tgt.Partition, and this PartitionInfo does not differ in
        substance from the tgt.Partition from which it was instantiated.
        
        Size, offset, id and number are compared to determine whether this
        partition has been modified. Slices within this partition are not
        considered.
        
        off_by - A string or DiskSpace indicating a rounding factor. Any size
        data (offset, size) that differs by less than the given amount is
        assumed to be unchanged. e.g., if the tgt.Partition indicates a size
        of 10.05GB and this PartitionInfo has a size of 10.1GB, and off_by
        is the default of 0.1GB, then it is assumed that the represented
        partition has not changed. (The original tgt.Partition size should be
        used, for accuracy)
        
        '''
        if self._tgt_part is None:
            return True
        
        if not isinstance(off_by, DiskSpace):
            off_by = DiskSpace(off_by)
        off_by_bytes = off_by.size_as("b")
        
        if self.number != self._tgt_part.number:
            return True
        
        if self.id != self._tgt_part.id:
            return True
        
        tgt_size = self._tgt_part.blocks * self._tgt_part.geometry.blocksz
        if abs(tgt_size - self.size.size_as("b")) > off_by_bytes:
            return True
        
        tgt_offset = self._tgt_part.offset * self._tgt_part.geometry.blocksz
        if abs(tgt_offset - self.offset.size_as("b")) > off_by_bytes:
            return True
        
        return False
    
    def destroyed(self, off_by=UI_PRECISION):
        '''Returns True if this partition previously had data, and has also
        been modified. Also returns True if this is the Solaris2 partition,
        but the partition originally had no slices - the slice editing screen
        is skipped in such a case, so the user needs to be informed that the
        entire contents of the Solaris2 partition will be destroyed (as the
        entire partition will be used as the install target)
        
        '''
        if self._tgt_part is None:
            return False
        modified = self.modified(off_by)
        return modified or (self.is_solaris_data() and not self.orig_slices)
    
    def create_default_layout(self):
        '''Create a reasonable default layout, consisting of a single
        slice that consumes the entire partition (as well as defining the
        traditional backup slice)
        
        '''
        whole_part = SliceInfo(slice_num=0, size=self.size,
                               slice_type=SliceInfo.ROOT_POOL)
        backup_part = SliceInfo(slice_num=SliceInfo.BACKUP_SLICE,
                                size=self.size)
        self.slices = [whole_part, backup_part]
    
    def is_solaris_data(self):
        '''Returns True if this PartitionInfo would be the install target'''
        return self.id == PartitionInfo.SOLARIS


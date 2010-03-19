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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
Object to represent Slices
'''

from copy import deepcopy
from UserString import UserString
import logging

import osol_install.tgt as tgt
from osol_install.profile.disk_space import DiskSpace, round_to_multiple

UI_PRECISION = DiskSpace("0.05gb")


# Pylint gets confused and thinks SliceInfo.size and SliceInfo.offset
# are strings, but they are actually DiskSpace objects
# pylint: disable-msg=E1103
class SliceInfo(object):
    '''Represents a single slice on a partition or slice.'''
    MAX_SLICES = 8
    MAX_VTOC = DiskSpace("2tb")
    
    BACKUP_SLICE = 2
    x86_BOOT_SLICE = 8
    x86_ALT_SLICE = 9
    UNUSED = (None, None)
    UNUSED_TEXT = "Unused"
    DEFAULT_POOL = UserString("")
    ZPOOL = tgt.Slice.AZPOOL
    ZPOOL_TYPES = [tgt.Slice.AZPOOL, tgt.Slice.EZPOOL, tgt.Slice.SZPOOL,
                   tgt.Slice.CZPOOL]
    ROOT_POOL = (ZPOOL, DEFAULT_POOL)
    LEGACY = "legacy"
    UFS = tgt.Slice.FS
    UFS_TEXT = "UFS"
    UNKNOWN = "???"
    
    TYPES = [UNUSED,
             ROOT_POOL]
    
    def __init__(self, slice_num=0, size=None, offset=None, blocksz=512,
                 slice_type=None, readonly=False, unmountable=True,
                 tag=None, tgt_slice=None):
        '''Constructor takes either a tgt_slice, which should be a tgt.Slice
        object, or a set of parameters. If tgt_slice is supplied, all other
        parameters are ignored.
        
        '''
        self._tgt_slice = tgt_slice
        self._size = None
        self._offset = None
        self.previous_size = None
        if tgt_slice:
            size = str(tgt_slice.blocks * tgt_slice.geometry.blocksz) + "b"
            self.size = size
            offset = str(tgt_slice.offset * tgt_slice.geometry.blocksz) + "b"
            self.blocksz = tgt_slice.geometry.blocksz
            self.offset = offset
            self.number = tgt_slice.number
            self.readonly = tgt_slice.readonly
            self.type = (tgt_slice.type, tgt_slice.user)
            self.last_mount = tgt_slice.last_mount
            self.unmountable = tgt_slice.unmountable
            self.tag = tgt_slice.tag
        else:
            self.readonly = readonly
            if slice_type is None:
                slice_type = SliceInfo.UNUSED
            if len(slice_type) != 2:
                raise TypeError("slice_type must be tuple of length 2")
            self.type = slice_type
            self.unmountable = unmountable
            self.size = size
            self.blocksz = blocksz
            self.offset = offset
            self.number = slice_num
            self.last_mount = None
            self.tag = tag
        self.original_type = self.type
    
    def __str__(self):
        result = ["Slice Info (%s):" % self.number]
        result.append("Type: %s:%s" % self.type)
        result.append("Offset: %s" % self.offset)
        result.append("Size: %s" % self.size)
        return "\n".join(result)
    
    @staticmethod
    def compare(left, right):
        '''Returns an integer such that this method can be passed to
        list.sort() and the list will be sorted in disk layout order.
        
        The backup slice is always listed last
        
        '''
        if isinstance(left, tgt.Slice):
            left = SliceInfo(left)
        if not isinstance(left, SliceInfo):
            return NotImplemented
        
        if isinstance(right, tgt.Slice):
            right = SliceInfo(right)
        if not isinstance(right, SliceInfo):
            return NotImplemented
        
        if left.number == SliceInfo.BACKUP_SLICE:
            return 1
        elif right.number == SliceInfo.BACKUP_SLICE:
            return -1
        
        left_off = left.offset.size_as("b")
        right_off = right.offset.size_as("b")
        if left_off < right_off:
            return -1
        elif left_off > right_off:
            return 1
        else:
            return 0
    
    def get_offset(self):
        '''Return this slice's offset as a DiskSpace object'''
        return self._offset
    
    def set_offset(self, offset):
        '''Set this slice's offset. Must be either a DiskSpace object
        or a string that will be accepted by DiskSpace.__init__
        
        '''
        if isinstance(offset, DiskSpace):
            self._offset = deepcopy(offset)
        else:
            self._offset = DiskSpace(offset)
    
    def get_size(self):
        '''Returns this slice's size as a DiskSpace object'''
        return self._size
    
    def set_size(self, size):
        '''Set this slice's size. size must be either a DiskSpace or a
        string that will be accepted by DiskSpace.__init__
        
        '''
        if isinstance(size, DiskSpace):
            self._size = deepcopy(size)
        else:
            self._size = DiskSpace(size)
    
    def get_type(self):
        '''Returns this SliceInfo's 'type'
        Here for interface compatibility with PartitionInfo.get_type()'''
        return self.type
    
    def get_blocks(self):
        '''Return the number of blocks on this slice'''
        return int(self.size.size_as("b") / self.blocksz)
    
    size = property(get_size, set_size)
    offset = property(get_offset, set_offset)
    
    def get_description(self):
        '''Return a string suitable for representing this slice in a UI'''
        description = None
        if self.number == SliceInfo.BACKUP_SLICE:
            description = tgt.Slice.BACKUP
        elif self.type == SliceInfo.UNUSED:
            description = SliceInfo.UNUSED_TEXT
        elif self.type[0] == SliceInfo.UFS:
            if self.last_mount:
                description = self.last_mount
            else:
                description = SliceInfo.UFS_TEXT
        elif self.type[0] == tgt.Slice.UNKNOWN:
            if self.tag == tgt.Slice.UNKNOWN:
                description = SliceInfo.UNKNOWN
            else:
                description = self.tag
        elif self.type[1] and self.type[1] != tgt.Slice.UNKNOWN:
            description = self.type[1]
        else:
            description = self.type[0]
        return str(description)
    
    def cycle_type(self, parent, extra_types=None):
        '''Cycle this partition's type. If extra_types is given, it should
        be a list of additional types - these will be considered when cycling
        to the next type
        
        '''
        if extra_types is None:
            extra_types = []
        if self.number == SliceInfo.BACKUP_SLICE:
            return
        
        has_solaris_data = (parent.get_solaris_data() is not None)
        types = set()
        types.update(SliceInfo.TYPES)
        types.update(extra_types)
        types = list(types)
        types.sort()
        if self.type in types:
            logging.debug("type in types, cycling next")
            type_index = types.index(self.type)
            type_index = (type_index + 1) % len(types)
            self.type = types[type_index]
            logging.debug("now %s-%s", *self.type)
        else:
            logging.debug("type NOT in types, setting to types[0]")
            self.original_type = self.type
            self.type = types[0]
        if self.type == SliceInfo.UNUSED:
            self.previous_size = self.size
            self.size = "0GB"
        elif self.is_rpool():
            if has_solaris_data:
                self.cycle_type(parent, extra_types)
    
    def get_endblock(self):
        '''Returns the ending 'offset' of this slice, as a DiskSpace'''
        try:
            start_pt = self.offset.size_as("b")
            end_pt = self.size.size_as("b")
            return DiskSpace(str(start_pt + end_pt) + "b")
        except AttributeError:
            raise AttributeError("%s does not have valid size data" %
                                 self.__class__.__name__)
    
    def get_max_size(self, parent):
        '''Return the maximum possible size this slice could consume,
        in gigabytes, based on adjacent unused space
        
        '''
        if self.number == SliceInfo.BACKUP_SLICE:
            return self.size.size_as("gb")
        msg_str = "get_max_size:%s:" % self.number
        slices = parent.slices
        if self not in slices:
            raise ValueError("This slice not in the parent!")
        self_idx = slices.index(self)
        prev_slice = None
        next_slice = None
        
        # Search for the slice prior to this one with the largest "endblock"
        # Since existing slices may overlap, this could be any slice prior
        # to the current one.
        for slice_info in reversed(slices[:self_idx]):
            if (slice_info.type != SliceInfo.UNUSED and
                slice_info.number != SliceInfo.BACKUP_SLICE):
                if (prev_slice is None or
                    slice_info.get_endblock() > prev_slice.get_endblock()):
                    prev_slice = slice_info
        for slice_info in slices[self_idx+1:]:
            if (slice_info.type != SliceInfo.UNUSED and
                slice_info.number != SliceInfo.BACKUP_SLICE):
                next_slice = slice_info
                break
        if prev_slice is None:
            msg_str += "prev_part=None:start_pt=0:"
            start_pt = 0
        else:
            msg_str += "prev_part=%s:" % prev_slice.number
            start_pt = prev_slice.get_endblock().size_as("gb")
            msg_str += "start_pt=" + str(start_pt) + ":"
        
        if next_slice is None:
            msg_str += "next_part=None:end_pt="
            for slice_info in reversed(slices):
                # Use the backup slice to define the absolute max size
                # any given slice can be. (This is usually the last slice,
                # hence the use of a reversed iterator)
                if slice_info.number == SliceInfo.BACKUP_SLICE:
                    end_pt = slice_info.size.size_as("gb")
                    break
            else:
                # Default to the parent's size if there happens to be no S2
                end_pt = parent.size.size_as("gb")
            msg_str += str(end_pt) + ":"
        else:
            msg_str += "next_part=%s:" % next_slice.number
            end_pt = next_slice.offset.size_as("gb")
            msg_str += "end_pt=%s:" % end_pt
        max_space = end_pt - start_pt
        if max_space < 0:
            max_space = 0
        msg_str += "max_size=%s" % max_space
        logging.debug(msg_str)
        return max_space
    
    def editable(self, dummy):
        '''Returns True if the installer is capable of resizing this Slice'''
        return self.is_rpool()
    
    def adjust_offset(self, parent):
        '''Adjust this slice's offset such that it no longer overlaps
        with prior or subsequent slices, by comparing this slice's 
        offset with prior slices, and its endblock with subsequent ones.
        
        Additionally, any unused slices found are shifted to align
        with this slice's trailing edge, if needed.
        
        This function should only be called after ensuring that this slice's
        size is less than or equal its max_size (as given by get_max_size);
        the behavior of this function when attempting to adjust in both
        directions is undefined. Additionally, the slices on the parent
        should already be sorted in disk order.
        
        '''
        if self.number == SliceInfo.BACKUP_SLICE:
            return
        parts = parent.get_parts()
        self_idx = parts.index(self)
        endblock = self.get_endblock()
        endblock_bytes = endblock.size_as("gb")
        unused_parts = []
        
        pre_shift = 0
        for part in parts[:self_idx]:
            if (part.type == SliceInfo.UNUSED or
                part.number == SliceInfo.BACKUP_SLICE):
                continue
            overlap = (part.get_endblock().size_as("gb") -
                       self.offset.size_as("gb"))
            pre_shift = max(pre_shift, overlap)
        
        if pre_shift > 0:
            new_offset = self.offset.size_as("gb") + pre_shift
            self.offset = str(new_offset) + "gb"
        
        post_shift = None
        for part in parts[self_idx+1:]:
            if part.offset.size_as("gb") < endblock_bytes:
                if part.type == SliceInfo.UNUSED:
                    unused_parts.append(part)
                elif part.number != SliceInfo.BACKUP_SLICE:
                    post_shift = endblock_bytes - part.offset.size_as("gb")
                    break
            else:
                break
        else:
            # Check to ensure we don't slip past the end of the disk/partition
            max_endblock = parent.size.size_as("gb")
            if endblock_bytes > max_endblock:
                post_shift = endblock_bytes - max_endblock
        
        if post_shift is not None:
            new_offset = max(0, self.offset.size_as("gb") - post_shift)
            self.offset = str(new_offset) + "gb"
        new_endblock = self.get_endblock()
        for part in unused_parts:
            part.offset = new_endblock
    
    def to_tgt(self, parent):
        '''Transfer the install profile information to tgt format'''
        # Create tgt.Slice object

        if self.get_type() == SliceInfo.UNUSED:
            return None

        if not self.modified():
            return self._tgt_slice

        # Don't need to include the 'backup' slice, libti will
        # automatically create one appropriately
        if self.number == SliceInfo.BACKUP_SLICE:
            return None

        # Something changed, need to create a new one
        geo = tgt.Geometry(parent.cylsz, self.blocksz)

        # offset must be a multiple of tgt.Geometry.cylsz
        off = int(self.offset.size_as("b") / self.blocksz)
        offset = round_to_multiple(off, geo.cylsz)

        blocks = round_to_multiple(self.get_blocks(), geo.cylsz)

        tag = tgt.Slice.UNASSIGNED
        slice_type = self.type[0]
        user = self.type[1]
        sl = tgt.Slice(geo, self.number, tag, slice_type, offset, blocks,
                      modified=True, user=str(user), 
                      unmountable=self.unmountable, readonly=self.readonly)
        return (sl)
    
    def modified(self, off_by=UI_PRECISION):
        '''Returns False if and only if this SliceInfo was instantiated from
        a tgt.Slice, and this SliceInfo does not differ in substance
        from the tgt.Slice from which it was instantiated.
        
        Size, offset, type and number are compared to determine
        whether this slice has been modified.
        
        off_by - A string or DiskSpace indicating a rounding factor. Any size
        data (offset, size) that differs by less than the given amount is
        assumed to be unchanged. e.g., if the tgt.Slice indicates a size
        of 10.05GB and this SliceInfo has a size of 10.1GB, and off_by
        is the default of 0.1GB, then it is assumed that the represented
        slice has not changed. (The original tgt.Slice size should be
        used, for accuracy)
        
        '''
        if self._tgt_slice is None:
            return True
        
        if not isinstance(off_by, DiskSpace):
            off_by = DiskSpace(off_by)
        off_by_bytes = off_by.size_as("b")
        
        if self.number != self._tgt_slice.number:
            return True
        
        if self.type[0] != self._tgt_slice.type:
            return True
        
        if self.type[1] != self._tgt_slice.user:
            return True
        
        tgt_size = self._tgt_slice.blocks * self._tgt_slice.geometry.blocksz
        if abs(tgt_size - self.size.size_as("b")) > off_by_bytes:
            return True
        
        tgt_offset = self._tgt_slice.offset * self._tgt_slice.geometry.blocksz
        if abs(tgt_offset - self.offset.size_as("b")) > off_by_bytes:
            return True
        
        return False
    
    def destroyed(self, off_by=UI_PRECISION):
        '''Returns True if this slice previously had data, and has also
        been modified.
        
        '''
        if self.is_rpool():
            return True
        return (self._tgt_slice is not None and self.modified(off_by))
    
    def is_rpool(self):
        '''Returns True this slice is the default pool
        
        '''
        return (self.type[0] in SliceInfo.ZPOOL_TYPES and 
            self.type[1] == SliceInfo.DEFAULT_POOL)
    
    def is_solaris_data(self):
        return self.is_rpool()

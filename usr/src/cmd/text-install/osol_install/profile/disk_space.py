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
Object representing space on a disk (for example, a file, partition or slice)
'''


def round_to_multiple(num, mult):
    ''' Round the given number (num) up to a given multiple (mult) '''
    remainder = num % mult
    if (remainder == 0):
        return (num)	# num is already of the given multiple
    return (num + (mult - remainder))


def round_down(num, mult):
    ''' Round the given number (num) down to a given multiple (mult) '''
    return (num - (num % mult))


class DiskSpace(object):
    '''Represent a disk, partition or file's size in
    bytes, kb, mb, gb or tb
    
    '''
    SIZES = {"b" : 1,
             "kb" : 1024,
             "mb" : 1024**2,
             "gb" : 1024**3,
             "tb" : 1024**4}
    
    def __init__(self, size=None):
        '''size must be a string with a suffix of b, kb, mb, gb or tb'''
        self._size = 0
        self.size = size
    
    def __str__(self):
        return self.size_as_string()
    
    def set_size(self, size):
        '''Set the size to the string specified'''
        if size is None:
            self._size = 0
        else:
            self._size = DiskSpace.check_format(size)
    
    def size_as_string(self, unit_str="gb"):
        '''Return a string representing this object's size in the indicated
        units
        
        '''
        return str(self.size_as(unit_str)) + unit_str
    
    def size_as(self, unit_str="gb"):
        '''Return the size of this DiskSpace converted in scale to unit_str.
        unit_str defaults to gigabytes
        
        unit_str must be in DiskSpace.SIZES
        '''
        unit_str = unit_str.lower()
        if unit_str in DiskSpace.SIZES:
            return (self._size / DiskSpace.SIZES[unit_str])
        else:
            raise ValueError("%s not a recognized suffix" % unit_str)
    
    size = property(size_as, set_size)
    
    @staticmethod
    def check_format(input_str):
        '''Analyze a string to determine if it could represent a DiskSpace
        
        input_str must be a string object, or a TypeError will be raised
        
        Returns the object's size in bytes if input_str could represent
        a DiskSpace, and raises ValueError otherwise
        
        '''
        if not isinstance(input_str, basestring):
            raise TypeError("input_str must be a string")
        input_str = input_str.strip()
        # Determine whether the units are represented by a single character
        # (bytes, b), or two characters (kb, mb, gb, tb)
        if input_str[-2:-1].isdigit():
            units = input_str[-1:].lower()
            value = input_str[:-1]
        else:
            units = input_str[-2:].lower()
            value = input_str[:-2]
        if units in DiskSpace.SIZES:
            if value:
                # Raises a ValueError if value isn't a parseable float
                return float(value) * DiskSpace.SIZES[units]
            else:
                raise TypeError("Invalid value (%s)" % input_str)
        else:
            raise ValueError("Invalid units (%s)" % units)
    
    def __cmp__(self, other):
        if self._size > other._size:
            return 1
        if self._size < other._size:
            return -1
        return 0

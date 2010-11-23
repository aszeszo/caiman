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
Utility functions written in Python. Intended for use by the tgt module C code,
so that additional functions of tgt.* objects can be written in Python.
'''

import osol_install.tgt as tgt


def print_disk(tgt_disk, depth=0):
    '''Print out a tgt.Disk in a legible manner.
    This function is called by tgt.Disk.__str__
    
    '''
    tabs = "\t" * depth
    result = []
    result.append("%s--- Disk (%s) ---" % (tabs, tgt_disk.name))
    result.append("%sFdisk:VTOC:GPT" % tabs)
    result.append("%s%s:%s:%s" %
                  (tabs, tgt_disk.fdisk, tgt_disk.vtoc, tgt_disk.gpt))
    result.append("%sBlocks: %s (blocksz=%s)" %
                  (tabs, tgt_disk.blocks, tgt_disk.geometry.blocksz))
    result.append("%sSize: %s GB" %
                  (tabs, tgt_disk.blocks * tgt_disk.geometry.blocksz / 1024**3))
    if tgt_disk.children:
        if isinstance(tgt_disk.children[0], tgt.Partition):
            print_fn = print_partition
        else:
            print_fn = print_slice
        for child in tgt_disk.children:
            result.append(print_fn(child, depth=1))
    return "\n".join(result)


def print_partition(tgt_part, depth=0):
    '''Print out a tgt.Partition in a legible manner.
    This function is called by tgt.Partition.__str__
    
    '''
    tabs = "\t" * depth
    result = []
    result.append("%s--- Partition (%s) ---" % (tabs, tgt_part.number))
    result.append("%sType: %s" % (tabs, tgt_part.id_as_string()))
    result.append("%sOffset: %s (%s GB)" %
                  (tabs, tgt_part.offset,
                   tgt_part.offset * tgt_part.geometry.blocksz / 1024**3))
    result.append("%sBlocks: %s (%s GB)" %
                  (tabs, tgt_part.blocks,
                   tgt_part.blocks * tgt_part.geometry.blocksz / 1024**3))
    result.append("%sActive:%s" % (tabs, tgt_part.active))
    for child in tgt_part.children:
        result.append(print_slice(child, depth=(depth + 1)))
    return "\n".join(result)


def print_slice(tgt_slice, depth=0):
    '''Print out a tgt.Slice in a legible manner.
    This function is called by tgt.Slice.__str__
    
    '''
    tabs = "\t" * depth
    result = []
    result.append("%s--- Slice (%s) ---" % (tabs, tgt_slice.number))
    result.append("%sType: %s" % (tabs, tgt_slice.type))
    result.append("%sUser: %s" % (tabs, tgt_slice.user))
    result.append("%sOffset: %s (%s GB)" %
                  (tabs, tgt_slice.offset,
                   tgt_slice.offset * tgt_slice.geometry.blocksz / 1024**3))
    result.append("%sBlocks: %s (%s GB)" %
                  (tabs, tgt_slice.blocks,
                   tgt_slice.blocks * tgt_slice.geometry.blocksz / 1024**3))
    
    return "\n".join(result)


def print_all_disks(disks=None):
    ''' Print debugging information for all tgt disks
        
        Args: 
            disks: A list of tgt disk objects. If not specified,
                   run tgt.discover_target_data() and print out
                   all found disks

    '''

    if disks is None:
        disks = tgt.discover_target_data()
    for disk in disks:
        print str(disk)


if __name__ == '__main__':
    print_all_disks()

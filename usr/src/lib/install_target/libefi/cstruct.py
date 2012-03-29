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
""" C structures from libefi.so and libefi.h
"""

import ctypes as C
from solaris_install.target.cuuid import cUUID
from solaris_install.target.libefi import const

c_diskaddr = C.c_ulonglong
c_len = C.c_ulonglong

LEN_EFI_PAD = const.EFI_LABEL_SIZE - (
                  (5 * C.sizeof(c_diskaddr)) +
                  (7 * C.sizeof(C.c_uint)) +
                  (8 * C.sizeof(C.c_char)) +
                  C.sizeof(cUUID)
              )


class EFI_GPE_Attrs(C.Structure):
    _fields_ = [
        ("PartitionAttrs",    C.c_uint32, 16),
        ("Reserved2",         C.c_uint32, 16),
        ("Reserved1",         C.c_uint32, 31),
        ("RequiredPartition", C.c_uint32, 1)
    ]


class EFI_GPE(C.Structure):
    """ struct efi_gpe_t from /usr/include/sys/efi_partition.h
    """
    _fields_ = [
        ("efi_gpe_PartitionTypeGUID",   cUUID),
        ("efi_gpe_UniquePartitionGUID", cUUID),
        ("efi_gpe_StartingLBA",         c_diskaddr),
        ("efi_gpe_EndingLBA",           c_diskaddr),
        ("efi_gpe_Attributes",          EFI_GPE_Attrs),
        ("efi_gpe_PartitionName",       C.c_ushort * const.EFI_PART_NAME_LEN)
    ]


# The number of GPE entries that would fit into 16K
EFI_MAXPAR = const.EFI_MIN_ARRAY_SIZE / C.sizeof(EFI_GPE)


class EFI_GPT(C.Structure):
    """ struct efi_gpt_t from /usr/include/sys/efi_partition.h
    """
    _fields_ = [
        ("efi_gpt_Signature",                C.c_uint64),
        ("efi_gpt_Revision",                 C.c_uint),
        ("efi_gpt_HeaderSize",               C.c_uint),
        ("efi_gpt_HeaderCRC32",              C.c_uint),
        ("efi_gpt_Reserved1",                C.c_uint),
        ("efi_gpt_MyLBA",                    c_diskaddr),
        ("efi_gpt_AlternateLBA",             c_diskaddr),
        ("efi_gpt_FirstUsableLBA",           c_diskaddr),
        ("efi_gpt_LastUsableLBA",            c_diskaddr),
        ("efi_gpt_DiskGUID",                 cUUID),
        ("efi_gpt_PartitionEntryLBA",        c_diskaddr),
        ("efi_gpt_NumberOfPartitionEntries", C.c_uint),
        ("efi_gpt_SizeOfPartitionEntry",     C.c_uint),
        ("efi_gpt_PartitionEntryArrayCRC32", C.c_uint),
        ("efi_gpt_Reserved2",                C.c_char * LEN_EFI_PAD)
    ]


class DK_Part(C.Structure):
    """ struct dk_part_t from /usr/include/sys/efi_partitions.h
    """
    _fields_ = [
        ("p_start", c_diskaddr),   # starting LBA
        ("p_size",  c_diskaddr),   # size in blocks
        ("p_guid",  cUUID),        # partition type GUID
        ("p_tag",   C.c_ushort),   # converted to part'n type GUID
        ("p_flag",  C.c_ushort),   # attributes
        ("p_name",  C.c_char * const.EFI_PART_NAME_LEN),  # partition name
        ("p_uguid", cUUID),        # unique partition GUID
        ("p_resv",  C.c_uint * 8)  # future use - set to zero
    ]


class DK_GPT(C.Structure):
    """ struct dk_gpt from /usr/include/sys/efi_partitions.h
    """
    _fields_ = [
        ("efi_version",     C.c_uint),    # set to EFI_VERSION_CURRENT
        ("efi_nparts",      C.c_uint),    # number of partitions below
        ("efi_part_size",   C.c_uint),    # size of each partition entry
                                          # (unused)
        ("efi_lbasize",     C.c_uint),    # size of block in bytes
        ("efi_last_lba",    c_diskaddr),  # last block on the disk
        ("efi_first_u_lba", c_diskaddr),  # first block after labels
        ("efi_last_u_lba",  c_diskaddr),  # last block before backup labels
        ("efi_disk_uguid",  cUUID),       # unique disk GUID
        ("efi_flags",       C.c_uint),
        ("efi_reserved1",   C.c_uint),    # future use - set to zero
        ("efi_altern_lba",  c_diskaddr),  # lba of alternate GPT header
        ("efi_reserved",    C.c_uint * 12),  # future use - set to zero
        ("efi_parts",       DK_Part * EFI_MAXPAR)  # array of 128 partitions
    ]


class DKI_UN(C.Union):
    """ union dki_un from /usr/include/sys/efi_partitions.h
    """
    _fields_ = [
        ("_dki_data",    C.POINTER(EFI_GPT)),
        ("_dki_data_64", C.c_uint64)
    ]


class DK_EFI(C.Structure):
    _fields_ = [
        ("dki_lba",    c_diskaddr),  # starting block
        ("dki_length", c_len),       # length in blocks
        ("dki_un",     DKI_UN)
    ]


class Partition64(C.Structure):
    """ struct partition64 from /usr/include_sys/efi_partitions.h
    """
    _fields_ = [
        ("p_type",   cUUID),
        ("p_partno", C.c_uint),
        ("p_resv1",  C.c_uint),
        ("p_start",  c_diskaddr),
        ("p_size",   c_diskaddr)
    ]

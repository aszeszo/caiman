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
""" C structures from libadm(3LIB).
"""
import ctypes as C

from solaris_install.target.libadm import const


class extpartition(C.Structure):
    """ struct extpartition from /usr/include/sys/vtoc.h"""
    _fields_ = [
        ("p_tag", C.c_ushort),  # ID tag of partition
        ("p_flag", C.c_ushort),  # permission flags
        ("p_pad", C.c_ushort * 2),
        ("p_start", C.c_ulonglong),  # start sector number of partition
        ("p_size", C.c_ulonglong)   # number of blocks in partition
    ]


class extvtoc(C.Structure):
    """ struct extvtoc from /usr/include/sys/vtoc.h"""
    _fields_ = [
        ("v_bootinfo", C.c_uint64 * 3),  # info needed by mboot
        ("v_sanity", C.c_uint64),  # to verify vtoc sanity
        ("v_version", C.c_uint64),  # layout version
        ("v_volume", C.c_char * const.LEN_DKL_VVOL),  # volume name
        ("v_sectorsz", C.c_ushort),  # sector size in bytes
        ("v_nparts", C.c_ushort),  # number of partitions
        ("pad", C.c_ushort * 2),
        ("v_reserved", C.c_uint64 * 10),
        ("v_part", extpartition * const.V_NUMPAR),  # partition headers
        ("timestamp", C.c_uint64 * const.V_NUMPAR),  # partition timestamp
        ("v_asciilabel", C.c_char * const.LEN_DKL_ASCII)  # for compatibility
    ]

extvtocp = C.POINTER(extvtoc)

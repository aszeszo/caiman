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
""" C structures from libnvpair(3LIB).
"""
import ctypes as C

class nvpair(C.Structure):
    """ struct nvpair from /usr/include/sys/nvpair.h
    """
    _fields_ = [
        ("nvp_size",       C.c_int32), # size of this nvpair
        ("nvp_name_sz",    C.c_int16), # length of name string
        ("nvp_reserve",    C.c_int16), # not used
        ("nvp_value_elem", C.c_int32), # number of elements for array types
        ("nvp_type",       C.c_int)    # type of value (data_type_enum)
    ]

class nvlist(C.Structure):
    """ struct nvlist from /usr/include/sys/nvpair.h
    """
    _fields_ = [
        ("nvl_version", C.c_int32),
        ("nvl_nvflag",  C.c_uint32), # persistent flags
        ("nvl_priv",    C.c_uint64), # ptr to private data if not packed
        ("nvl_flag",    C.c_uint32),
        ("nvl_pad",     C.c_int32),  # currently not used, for alignment
    ]

nvpairp = C.POINTER(nvpair)
nvlistp = C.POINTER(nvlist)

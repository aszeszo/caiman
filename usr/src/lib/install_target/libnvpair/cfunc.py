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
""" C functions from libnvpair(3LIB).

NOTE:  This implementation of libnvpair for Python is not entirely complete.
The following functions are not currently available:

nv_alloc_*

nvlist_size
nvlist_pack
nvlist_unpack
nvlist_dup
nvlist_nvflag
nvlist_xalloc
nvlist_xpack
nvlist_xunpack
nvlist_xdup
nvlist_lookup_nv_alloc

nvlist_add_hrtime
nvlist_remove_all
nvlist_clear
nvlist_lookup_hrtime
nvlist_lookup_pairs
nvlist_lookup_nvpair_embedded_index

nvpair_type_is_array
"""

import ctypes as C

from solaris_install.target.libnvpair.cstruct import nvpairp, nvlistp

_LIBNVPAIR = C.CDLL("/usr/lib/libnvpair.so", use_errno=True)

# function mapping.  each line is:  (function name, return type, args)
_funcs = [
    ("nvlist_add_boolean", C.c_int, (nvlistp, C.c_char_p)),
    ("nvlist_add_boolean_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int), C.c_uint)),
    ("nvlist_add_boolean_value", C.c_int, (nvlistp, C.c_char_p, C.c_int)),
    ("nvlist_add_byte", C.c_int, (nvlistp, C.c_char_p, C.c_ubyte)),
    ("nvlist_add_byte_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_ubyte), C.c_uint)),
    ("nvlist_add_double", C.c_int, (nvlistp, C.c_char_p, C.c_double)),
    ("nvlist_add_int16", C.c_int, (nvlistp, C.c_char_p, C.c_int16)),
    ("nvlist_add_int16_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int16), C.c_uint)),
    ("nvlist_add_int32", C.c_int, (nvlistp, C.c_char_p, C.c_int32)),
    ("nvlist_add_int32_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int32), C.c_uint)),
    ("nvlist_add_int64", C.c_int, (nvlistp, C.c_char_p, C.c_int64)),
    ("nvlist_add_int64_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int64), C.c_uint)),
    ("nvlist_add_int8", C.c_int, (nvlistp, C.c_char_p, C.c_int8)),
    ("nvlist_add_int8_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int8), C.c_uint)),
    ("nvlist_add_nvlist", C.c_int, (nvlistp, C.c_char_p, nvlistp)),
    ("nvlist_add_nvlist_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(nvlistp), C.c_uint)),
    ("nvlist_add_nvpair", C.c_int, (nvlistp, nvpairp)),
    ("nvlist_add_string", C.c_int, (nvlistp, C.c_char_p, C.c_char_p)),
    ("nvlist_add_string_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_char_p), C.c_uint)),
    ("nvlist_add_uint16", C.c_int, (nvlistp, C.c_char_p, C.c_uint16)),
    ("nvlist_add_uint16_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint16), C.c_uint)),
    ("nvlist_add_uint32", C.c_int, (nvlistp, C.c_char_p, C.c_uint32)),
    ("nvlist_add_uint32_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint32), C.c_uint)),
    ("nvlist_add_uint64", C.c_int, (nvlistp, C.c_char_p, C.c_uint64)),
    ("nvlist_add_uint64_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint64), C.c_uint)),
    ("nvlist_add_uint8", C.c_int, (nvlistp, C.c_char_p, C.c_uint8)),
    ("nvlist_add_uint8_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint8), C.c_uint)),
    ("nvlist_alloc", C.c_int, (C.POINTER(nvlistp), C.c_uint, C.c_int)),
    ("nvlist_empty", C.c_int, (nvlistp,)),
    ("nvlist_exists", C.c_int, (nvlistp, C.c_char_p)),
    ("nvlist_free", None, (nvlistp,)),
    ("nvlist_lookup_boolean", C.c_int, (nvlistp, C.c_char_p)),
    ("nvlist_lookup_boolean_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_int)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_boolean_value", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int))),
    ("nvlist_lookup_byte", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_ubyte))),
    ("nvlist_lookup_byte_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_uint8)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_double", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_double))),
    ("nvlist_lookup_int16", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int16))),
    ("nvlist_lookup_int16_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_int16)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_int32", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int32))),
    ("nvlist_lookup_int32_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_int32)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_int64", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int64))),
    ("nvlist_lookup_int64_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_int64)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_int8", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_int8))),
    ("nvlist_lookup_int8_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_int8)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_nvlist", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(nvlistp))),
    ("nvlist_lookup_nvlist_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(nvlistp)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_nvpair", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(nvpairp))),
    ("nvlist_lookup_string", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_char_p))),
    ("nvlist_lookup_string_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_char_p)))),
    ("nvlist_lookup_uint16", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint16))),
    ("nvlist_lookup_uint16_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_uint16)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_uint32", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint32))),
    ("nvlist_lookup_uint32_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_uint32)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_uint64", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint64))),
    ("nvlist_lookup_uint64_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_uint64)),
            C.POINTER(C.c_uint))),
    ("nvlist_lookup_uint8", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.c_uint8))),
    ("nvlist_lookup_uint8_array", C.c_int,
        (nvlistp, C.c_char_p, C.POINTER(C.POINTER(C.c_uint8)),
            C.POINTER(C.c_uint))),
    ("nvlist_merge", C.c_int, (nvlistp, nvlistp, C.c_int)),
    ("nvlist_next_nvpair", nvpairp, (nvlistp, nvpairp)),
    ("nvlist_prev_nvpair", nvpairp, (nvlistp, nvpairp)),
    ("nvlist_remove", C.c_int, (nvlistp, C.c_char_p, C.c_int)),
    ("nvlist_remove_nvpair", C.c_int, (nvlistp, nvpairp)),
    ("nvpair_name", C.c_char_p, (nvpairp,)),
    ("nvpair_type", C.c_int, (nvpairp,)),
    ("nvpair_value_boolean_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_int)), C.POINTER(C.c_uint))),
    ("nvpair_value_boolean_value", C.c_int,
        (nvpairp, C.POINTER(C.c_int))),
    ("nvpair_value_byte", C.c_int, (nvpairp, C.POINTER(C.c_ubyte))),
    ("nvpair_value_byte_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_ubyte)), C.POINTER(C.c_uint))),
    ("nvpair_value_double", C.c_int, (nvpairp, C.POINTER(C.c_double))),
    ("nvpair_value_int16", C.c_int, (nvpairp, C.POINTER(C.c_int16))),
    ("nvpair_value_int16_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_int16)), C.POINTER(C.c_uint))),
    ("nvpair_value_int32", C.c_int, (nvpairp, C.POINTER(C.c_int32))),
    ("nvpair_value_int32_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_int32)), C.POINTER(C.c_uint))),
    ("nvpair_value_int64", C.c_int, (nvpairp, C.POINTER(C.c_int64))),
    ("nvpair_value_int64_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_int64)), C.POINTER(C.c_uint))),
    ("nvpair_value_int8", C.c_int, (nvpairp, C.POINTER(C.c_int8))),
    ("nvpair_value_int8_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_int8)), C.POINTER(C.c_uint))),
    ("nvpair_value_nvlist", C.c_int, (nvpairp, C.POINTER(nvlistp))),
    ("nvpair_value_nvlist_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(nvlistp)), C.POINTER(C.c_uint))),
    ("nvpair_value_string", C.c_int, (nvpairp, C.POINTER(C.c_char_p))),
    ("nvpair_value_string_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_char_p)), C.POINTER(C.c_uint))),
    ("nvpair_value_uint16", C.c_int, (nvpairp, C.POINTER(C.c_uint16))),
    ("nvpair_value_uint16_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_uint16)), C.POINTER(C.c_uint))),
    ("nvpair_value_uint32", C.c_int, (nvpairp, C.POINTER(C.c_uint32))),
    ("nvpair_value_uint32_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_uint32)), C.POINTER(C.c_uint))),
    ("nvpair_value_uint64", C.c_int, (nvpairp, C.POINTER(C.c_uint64))),
    ("nvpair_value_uint64_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_uint64)), C.POINTER(C.c_uint))),
    ("nvpair_value_uint8", C.c_int, (nvpairp, C.POINTER(C.c_uint8))),
    ("nvpair_value_uint8_array", C.c_int,
        (nvpairp, C.POINTER(C.POINTER(C.c_uint8)), C.POINTER(C.c_uint)))
]

# update the namespace of this module
v = vars()
for (function, restype, args) in _funcs:
    v[function] = getattr(_LIBNVPAIR, function)
    v[function].restype = restype
    v[function].argtypes = args

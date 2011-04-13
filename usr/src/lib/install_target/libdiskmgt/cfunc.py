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
"""
C functions from undocumented /usr/lib/libdiskmgt.so
"""
import ctypes as C
from solaris_install.target.libdiskmgt.cstruct import dm_desc, dm_cstring
from solaris_install.target.libnvpair import nvl

_LIBDISKMGT = C.CDLL("/usr/lib/libdiskmgt.so", use_errno=True)

# function mapping.  each line is:  (function name, return type, args)
_funcs = [
    ("dm_free_descriptor", None, (dm_desc,)),
    ("dm_free_descriptors", None, (C.POINTER(dm_desc),)),
    ("dm_free_name", None, (dm_cstring,)),
    ("dm_get_associated_descriptors", C.POINTER(dm_desc),
        (dm_desc, C.c_int, C.POINTER(C.c_int))),
    ("dm_get_associated_types", C.POINTER(C.c_int), (C.c_int,)),
    ("dm_get_attributes", nvl.NVList, (dm_desc, C.POINTER(C.c_int))),
    ("dm_get_descriptor_by_name", dm_desc,
        (C.c_int, C.c_char_p, C.POINTER(C.c_int))),
    ("dm_get_descriptors", C.POINTER(dm_desc),
        (C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_int))),
    ("dm_get_name", dm_cstring, (dm_desc, C.POINTER(C.c_int))),
    ("dm_get_stats", nvl.NVList, (dm_desc, C.c_int, C.POINTER(C.c_int))),
    ("dm_get_type", C.c_int, (dm_desc,)),
    ("dm_inuse", C.c_int, (C.c_char_p, C.POINTER(C.c_char_p), C.c_int))
]

# update the namespace of this module
v = vars()
for (function, restype, args) in _funcs:
    v[function] = getattr(_LIBDISKMGT, function)
    v[function].restype = restype
    v[function].argtypes = args

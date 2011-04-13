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
""" C functions from libadm(3LIB).
"""
import ctypes as C
from solaris_install.target.libadm.cstruct import extvtocp

_LIBADM = C.CDLL("/usr/lib/libadm.so", use_errno=True)

# function mapping.  each line is:  (function name, return type, args)
_funcs = [
    ("read_extvtoc", C.c_int, (C.c_int, (extvtocp),)),
    ("write_extvtoc", C.c_int, (C.c_int, (extvtocp),))
]

# update the namespace of this module
v = vars()
for (function, restype, args) in _funcs:
    v[function] = getattr(_LIBADM, function)
    v[function].restype = restype
    v[function].argtypes = args

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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#
"""
C functions from /usr/lib/libima.so
"""

import ctypes as C

from solaris_install.target.libima.cstruct import IMA_INITIATOR_AUTHPARMS, \
    IMA_OID, IMA_OID_LIST

_LIBIMA = C.CDLL("/usr/lib/libima.so")

# aliases from libima.h
IMA_UINT = C.c_int
IMA_STATUS = IMA_UINT

# function mapping.  Each line is:  (function name, return type, args)
_funcs = [
    ("IMA_FreeMemory", IMA_STATUS, (C.c_void_p,)),
    ("IMA_GetLhbaOidList", IMA_STATUS, (C.POINTER(C.POINTER(IMA_OID_LIST)),)),
    ("IMA_GetInitiatorAuthParms", IMA_STATUS, (IMA_OID, IMA_UINT,
        C.POINTER(IMA_INITIATOR_AUTHPARMS))),
    ("IMA_SetInitiatorAuthParms", IMA_STATUS, (IMA_OID, IMA_UINT,
        C.POINTER(IMA_INITIATOR_AUTHPARMS)))
]
v = vars()
for (function, restype, args) in _funcs:
    v[function] = getattr(_LIBIMA, function)
    v[function].restype = restype
    v[function].argtypes = args

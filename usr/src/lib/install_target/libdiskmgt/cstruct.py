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
""" C structures from libdiskmgt.so.
"""
import ctypes as C


# Typedef the descriptor type.
class dm_desc(C.c_uint64):
    """ A libdiskmgt.so descriptor
    """
    pass


# If we don't do this we leak memory.
class dm_cstring(C.c_char_p):
    """ wrapper so we can free memory
    """
    @property
    def value(self):
        return getattr(C.c_char_p, "value").__get__(self)

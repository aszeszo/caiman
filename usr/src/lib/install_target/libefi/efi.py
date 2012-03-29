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
""" Python packge with ctypes wrapper for libefi.so
"""
import ctypes as C

from solaris_install.target.libefi import cfunc, cstruct


def efi_free(dk_gptp):
    cfunc.efi_free(dk_gptp)


def efi_init(fh, num_parts):
    dk_gptp = C.pointer(cstruct.DK_GPT())
    err = cfunc.efi_alloc_and_init(fh, num_parts, C.byref(dk_gptp))
    if err < 0:
        raise OSError(err, "efi_alloc: %d" % err)
    return dk_gptp


def efi_read(fh):
    dk_gptp = C.pointer(cstruct.DK_GPT())
    err = cfunc.efi_alloc_and_read(fh, C.byref(dk_gptp))
    if err < 0:
        raise OSError(err, "efi_read: %d" % err)
    return dk_gptp


def efi_write(fh, dk_gptp):
    err = cfunc.efi_write(fh, dk_gptp)
    if err < 0:
        raise OSError(err, "efi_write: %d" % err)

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
""" Python packge with ctypes wrapper for libadm.so (undocumented).
"""
import ctypes as C

from solaris_install.target.libadm import cfunc, cstruct


def read_extvtoc(fh):
    extvtocp = C.pointer(cstruct.extvtoc())
    # pylint: disable-msg=E1101
    err = cfunc.read_extvtoc(fh, extvtocp)
    if err < 0:
        raise OSError(err, "read_extvtoc: %d" % err)
    return extvtocp


def write_extvtoc(fh, extvtocp):
    # pylint: disable-msg=E1101
    err = cfunc.write_extvtoc(fh, extvtocp)
    if err < 0:
        raise OSError(err, "write_extvtoc: %d" % err)

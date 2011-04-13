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

""" constants and enums from /usr/include/sys/vtoc.h and
/usr/include/sys/dklabel.h
"""
import platform

if platform.processor() == "i386":
    V_NUMPAR = NDKMAP = 16
else:
    V_NUMPAR = NDKMAP = 8

# partition permission flags
V_UNMNT = 1   # unmountable partition
V_RONLY = 16  # read only

# partition identification tags
V_UNASSIGNED = 0  # unassigned partition
V_BOOT = 1  # Boot partition
V_ROOT = 2  # Root filesystem
V_SWAP = 3  # Swap filesystem
V_USR = 4   # Usr filesystem
V_BACKUP = 5  # full disk
V_STAND = 6  # Stand partition
V_VAR = 7  # Var partition
V_HOME = 8   # Home partition
V_ALTSCTR = 9  # Alternate sector partition
V_CACHE = 10  # Cache (cachefs) partition
V_RESERVED = 11  # SMI reserved data

LEN_DKL_ASCII = 128
LEN_DKL_VVOL = 8

# other x86 partition constants from /usr/include/sys/dktp/fdisk.h
FD_NUMPART = 4  # number of primary partitions
MAX_EXT_PARTS = 32  # number of logical partitions

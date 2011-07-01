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
""" C structures from libdevinfo(3LIB).
"""
import ctypes as C
import logging
import os
import re

from solaris_install.target.libdiskmgt import const as ldm_const
from solaris_install.target.libdiskmgt import diskmgt
from solaris_install.target.libdevinfo import cfunc
from solaris_install.target.libdevinfo.cstruct import BootDevp
from solaris_install.logger import INSTALL_LOGGER_NAME as ILN


def get_curr_bootdisk():
    """ get_curr_bootdisk() - function to return the ctd string of the system's
    bootdisk
    """
    # set up a logger
    logger = logging.getLogger(ILN)

    # query libdevinfo for the bootdev list
    bootdevs = C.POINTER(BootDevp)()
    err = C.c_int()
    err = cfunc.devfs_bootdev_get_list("/", C.byref(bootdevs))

    # trap on DEVFS_ERROR.  Typically happens after fast-reboot
    if err == -1:
        logger.debug("devfs_bootdev_get_list():  unable to open " +
                      "GRUB disk map.  Did you fast-reboot?")
        return None
    # trap on all other errors
    elif err != 0:
        logger.debug("devfs_bootdev_get_list():  %s" % os.strerror(err))
        return None

    try:
        # walk the null terminated bootdevs list of boot_dev structures to
        # construct a simplier list to iterate over
        i = 0
        bootdev_list = []
        while bootdevs[i]:
            bootdev_list.append(bootdevs[i].contents)
            i += 1

        for bootdev in bootdev_list:
            # dereference the bootdev_trans char**
            ctd_path = bootdev.bootdev_trans.contents.value

            # ensure there's something present to split on
            if ctd_path is None:
                continue

            # calculate the ctd string from the full /dev path
            (_none, sep, disk) = ctd_path.partition("/dev/dsk/")
            if sep:
                ctd = re.split("[sp]", disk)[0]
            else:
                continue

            # check to see if it's a CD-ROM drive
            dmd = diskmgt.descriptor_from_key(ldm_const.ALIAS, ctd)
            alias = diskmgt.DMAlias(dmd.value)
            drive = alias.drive

            if not drive.cdrom:
                return ctd
    finally:
        cfunc.devfs_bootdev_free_list(bootdevs)

    return None

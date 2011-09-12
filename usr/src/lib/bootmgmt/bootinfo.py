#! /usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
Various classes that provide access to system- and boot-related information
"""

import logging

from bootmgmt.pysol import devfs_bootdev_get_list
from bootmgmt import BootmgmtUnsupportedOperationError

logger = logging.getLogger('bootmgmt')


class SystemFirmware(object):
    PROP_BOOT_DEVICE = 'boot-device'

    @staticmethod
    def get(firmware_name=None):
        from bootmgmt.backend.fw import BackendFWFactory
        return BackendFWFactory.get(firmware_name)

    def __init__(self, fw_name=None):
        self._fw_name = fw_name

    @property
    def fw_name(self):
        return self._fw_name

    def getprop(self, propname):
        if not propname == SystemFirmware.PROP_BOOT_DEVICE:
            raise BootmgmtUnsupportedOperationError('Property not supported')
        # libdevinfo's devfs_bootdev_get_list returns an ordered list of
        # boot devices.  The form of the return value is a tuple of tuples:
        # ((<physpath>, (<logicalpath1>, <logicalpath2>, ...), ...)
        if propname == SystemFirmware.PROP_BOOT_DEVICE:
            return devfs_bootdev_get_list()

    def setprop(self, propname, value):
        pass

    def delprop(self, propname): 
        pass

###############################################################################


class BootVariables(object):
    @staticmethod
    def get(sysroot=None, arch=None, osname='solaris'):
        if sysroot is None:
            return None
        from bootmgmt.backend.bootvars import BackendBootVarsFactory
        return BackendBootVarsFactory.get(sysroot, arch, osname)

    def __init__(self, sysroot=None):
        self.dirty = False
        self._sysroot = sysroot
        self._vardict = {}
        if not self._sysroot is None:
            self._read()

    def _read(self):
        pass

    def load(self, sysroot):
        self._sysroot = sysroot
        self._read()

    def write(self, inst, alt_dir=None):
        return None

    def getprop(self, propname):
        return None

    def setprop(self, propname, value):
        pass

    def delprop(self, propname):
        pass

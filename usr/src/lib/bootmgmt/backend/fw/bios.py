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
x86 BIOS firmware backend for pybootmgmt
"""

from ...bootinfo import SystemFirmware
from bootmgmt import BootmgmtUnsupportedOperationError, BootmgmtWriteError


class BIOSFirmware(SystemFirmware):
    def getprop(self, propname):
        return super(BIOSFirmware, self).getprop(propname)        

    def setprop(self, propname, value):
        """Setting properties is not supported on BIOS systems"""
        if propname == SystemFirmware.PROP_BOOT_DEVICE:
            raise BootmgmtWriteError('Properties are read-only on systems '
              'with BIOS firmware')
        raise BootmgmtUnsupportedOperationError('Properties cannot be set '
              'on systems with BIOS firmware')

    def delprop(self, propname):
        """Deleting properties is not supported on BIOS systems"""
        raise BootmgmtUnsupportedOperationError('Properties cannot be '
              'deleted on systems with BIOS firmware')


def firmware_backend():
    return BIOSFirmware

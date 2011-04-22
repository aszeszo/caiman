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
System firmware backend support for pybootmgmt
"""

from ...bootutil import get_current_arch_string
from ... import BootmgmtUnsupportedPlatformError
from ... import pysol
import sys

class BackendFWFactory(object):
    @staticmethod
    def get(fw_name):
        """Returns an instance of bootinfo.SystemFirmware corresponding to the
        firmware name passed in.  If fw_name is None, the system firmware type
        is autodetected and the appropriate child of SystemFirmware is returned
        """
        if fw_name is None:
            curarch = get_current_arch_string()
            # If this is a SPARC system, the appropriate class is obp
            if curarch == 'sparc':
                from . import obp
                return obp.firmware_backend()('obp')
            elif curarch == 'x86':
            # If this is an x86 system and the efi-systype property exists,
            # then this is a UEFI system and the property value specifies the
            # bit width.
                try:
                    efisystype = pysol.di_find_root_prop('efi-systype')
                except IOError as e:
                    # Problem while trying to get the property
                    # Set efisystype to None to force BIOS
                    efisystype = None

                if efisystype is None:
                    from . import bios
                    return bios.firmware_backend()('bios')
                else:
                    uefi_string = 'uefi' + efisystype
                    fwmod = __name__ + '.' + uefi_string
                    __import__(fwmod, level=0)
                    ns = sys.modules[fwmod]
                    return ns.firmware_backend()(uefi_string)
            else:
                raise BootmgmtUnsupportedPlatformError('Unknown platform '
                       '"%s"' % curarch)
        else:
            fwmod = __name__ + '.' + fw_name
            __import__(fwmod, level=0)
            ns = sys.modules[fwmod]
            return ns.firmware_backend()(fw_name)
        
        

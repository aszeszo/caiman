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
BootInstance autogenerator Solaris backend for pybootmgmt
"""

import libbe_py

from ...bootconfig import BootConfig, SolarisDiskBootInstance
from ...bootutil import LoggerMixin

class SolarisBootInstanceAutogenerator(LoggerMixin):
    pass

def autogenerate_boot_instances(bootconfig):
    sbia = SolarisBootInstanceAutogenerator()

    # XXX - Handle bootconfig instances that have boot_class != disk
    if bootconfig.boot_class != BootConfig.BOOT_CLASS_DISK:
        raise BootmgmtUnsupportedOperationError('XXX - Fix Me')

    # Use libbe_py to get the list of boot environments, then iterate
    # over the list, creating a new SolarisDiskBootInstance for each
    # Note that the title will just be the last portion of the bootfs
    # (i.e. <pool>/ROOT/<title>)
    retcode, belist = libbe_py.beList()
    if retcode != 0:
        sbia._debug('libbe_py.beList() failed; return code was ' + str(retcode))
        return []

    inst_list = []
    for bootenv in belist:
        if bootenv.get('orig_be_name', None) is None:
            continue  # skip over snapshots
        bootinst = SolarisDiskBootInstance(None, title=bootenv['orig_be_name'],
                                           bootfs=bootenv['root_ds'])
        if bootenv['active'] is True:
            sbia._debug('default boot instance is:\n' + str(bootinst))
            bootinst.default = True

        inst_list.append(bootinst)

    return inst_list

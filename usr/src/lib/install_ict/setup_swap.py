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

import grp
import os
import shutil
import solaris_install.ict as ICT

from solaris_install import Popen
from solaris_install.target.physical import Disk, Slice, Partition
from solaris_install.target.logical import Zvol


class SetupSwap(ICT.ICTBaseClass):
    '''ICT checkpoint that sets up the swap in /etc/vfstab on the target
       during an AI installation
    '''

    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(SetupSwap, self).__init__(name)

    def _get_swap_devices(self):
        '''Get a list of swap devices from DESIRED tree'''

        self.logger.debug("Searching for swap devices")

        swap_path = ""
        swap_devices = list()

        # Find swap slices
        slices = self.target.get_descendants(class_type=Slice)
        swap_slices = [s for s in slices if s.is_swap]
        for swap_slice in swap_slices:
            # Construct path
            if swap_slice.parent is not None and \
               swap_slice.parent.parent is not None and \
               isinstance(swap_slice.parent, Partition):
                slice_ctd = "%ss%s" % (swap_slice.parent.parent.ctd,
                    swap_slice.name)
            elif swap_slice.parent is not None and \
                 isinstance(swap_slice.parent, Disk):
                slice_ctd = "%ss%s" % (swap_slice.parent.ctd,
                    swap_slice.name)
            else:
                # Can't figure out path, so log and move on.
                self.logger.debug("Unable to determine path to slice %s",
                    str(swap_slice))
                continue
            
            swap_path = "/dev/dsk/%s" %(slice_ctd)
            self.logger.debug("Found swap slice %s", swap_path)
            swap_devices.append(swap_path)

        # Find swap zvol
        zvols = self.target.get_descendants(class_type=Zvol)
        swap_zvols = [zvol for zvol in zvols if zvol.use == "swap"]
        for swap_zvol in swap_zvols:
            if swap_zvol.parent is not None:
                zvol_path = "/dev/zvol/dsk/%s/%s" % \
                    (swap_zvol.parent.name, swap_zvol.name)
                self.logger.debug("Found swap zvol %s", swap_path)
                swap_devices.append(zvol_path)
            else:
                # Can't figure out path, so log and move on.
                self.logger.debug("Unable to determine path to zvol %s",
                    str(swap_zvol))

        return swap_devices

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Looks for swap devices in the DESIRED target tree, and adds each of
            these to the /etc/vfstab.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        self.logger.debug('ICT current task: Setting up swap devices')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        vfstab = os.path.join(self.target_dir, ICT.VFSTAB)

        swap_devices = self._get_swap_devices()

        if not dry_run:
            try:
                with open(vfstab, "a+") as vf:
                    for device in swap_devices:
                        vf.write("%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n" %
                            (device, "-", "-", "swap", "-", "no", "-"))
            except IOError, ioe:
                self.logger.debug(
                    "Failed to open file %s for writing." % (vfstab))
                self.logger.debug(str(ioe))
                raise RuntimeError(
                    "Unable to setup swap devices in file %s" % (vfstab))

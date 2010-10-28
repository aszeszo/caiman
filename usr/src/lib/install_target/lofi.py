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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

"""
Heavyweight python interface to lofi
"""

import os
import os.path
import subprocess
import sys

_NULL = open("/dev/null", "r+")
LOFIADM = "/usr/sbin/lofiadm"
MKFILE = "/usr/sbin/mkfile"
MOUNT = "/usr/sbin/mount"
NEWFS = "/usr/sbin/newfs"
UMOUNT = "/usr/sbin/umount"

class Lofi(object):
    """ class representing a loopback interface.  The backing-store does not
    have to exist; it can be created
    """
    def __init__(self, ramdisk, mountpoint, size=0):
        """ constructor for the class

        ramdisk - path to the file to use as a backing store
        mountpoint - path to mount the file as a loopback device
        size - size of the file to create
        """
        self.ramdisk = ramdisk
        self.mountpoint = mountpoint
        self.size = size

        self.lofi_device = None
        self._mounted = False

        self.nbpi = None

    @property
    def exists(self):
        return os.path.exists(self.ramdisk)

    @property
    def mounted(self):
        return self._mounted

    @mounted.setter
    def mounted(self, val):
        self._mounted = val

    def create_ramdisk(self):
        if not self.exists:
            # create the file first
            cmd = [MKFILE, "%dk" % self.size, self.ramdisk]
            subprocess.check_call(cmd)

    def create(self):
        # create the ramdisk (if needed)
        self.create_ramdisk()

        # create the lofi device
        cmd = [LOFIADM, "-a", self.ramdisk]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        result, err = p.communicate()
        self.lofi_device = result.strip()
        if p.returncode != 0:
            raise RuntimeError("Unable to create lofi device: " + err)

        # newfs it
        cmd = [NEWFS]
        if self.nbpi is not None:
            cmd.append("-i")
            cmd.append(str(self.nbpi))
        cmd.append(self.lofi_device.replace("lofi", "rlofi"))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        out, err = p.communicate("y\n")
        p.wait()
        if p.returncode != 0:
            raise RuntimeError("Unable to newfs lofi device: " + err)

        # ensure a directory exists to mount the lofi device to
        if not os.path.exists(self.mountpoint):
            os.mkdir(self.mountpoint)

        cmd = [MOUNT, "-F", "ufs", "-o", "rw", self.lofi_device,
               self.mountpoint]
        subprocess.check_call(cmd, stdout=_NULL, stderr=_NULL)
        self.mounted = True

    def unmount(self):
        """ class method to unmount the ramdisk
        """
        if self.mounted:
            cmd = [UMOUNT, "-f", self.mountpoint]
            subprocess.check_call(cmd)
            self.mounted = False

    def destroy(self):
        """ class method to unmount and destroy the lofi device
        """
        if not self.exists:
            return

        self.unmount()

        # there is an undocumented -f flag to lofiadm to 'force' the destroy
        # command.
        cmd = [LOFIADM, "-f", "-d", self.lofi_device]
        subprocess.check_call(cmd)

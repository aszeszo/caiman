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

""" library interface for simple zpool commands
"""

import subprocess

from solaris_install.target import zfs as zfs_lib

_NULL = open("/dev/null", "r+")
ZPOOL = "/usr/sbin/zpool"
ZFS = "/usr/sbin/zfs"

class ZpoolError(RuntimeError):
    pass

class Zpool(object):
    """class for creation and deletion of zpools
    """
    def __init__(self, name, vdev_list, mountpoint=None):
        """ constructor for the class

        name - zpool name
        vdev - single string or list of strings of valid vdevs
        mountpoint - optional path to mount the zpool at
        """
        self.name = name
        
        if not isinstance(vdev_list, list):
            # convert a single vdev into a list with one element
            self.vdev_list = [vdev_list]
        else:
            self.vdev_list = vdev_list

        self.mountpoint = mountpoint

        self.datasets = None
        if self.exists:
            self.refresh_datasets()
    
    @property
    def exists(self):
        command = [ZPOOL, "list", self.name]
        exists = subprocess.call(command, stdout=_NULL, stderr=_NULL)
        return (exists == 0)
    
    def refresh_datasets(self):
        command = [ZFS, "list", "-H", "-t", "all", "-o", "name", "-r",
                   self.name]
        popen = subprocess.Popen(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        dataset_names, stderr = popen.communicate()
        
        if stderr or popen.returncode:
            raise subprocess.CalledProcessError(popen.returncode, command)
        
        self.datasets = []
        for dataset in dataset_names.splitlines():
            self.datasets.append(zfs_lib.Dataset(dataset))

    def set(self, propname, propvalue):
        cmd = [ZPOOL, "set", "%s=%s" % (propname, propvalue), self.name]
        subprocess.check_call(cmd)

    def get(self, propname):
        cmd = [ZPOOL, "get", propname]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        result, trash = p.communicate()
        if p.returncode:
            raise subprocess.CalledProcessError("get of %s failed" % propname)
        return result.strip()

    def create(self):
        """ class method to create the zpool from the vdevs
        """
        cmd = [ZPOOL, "create"]

        # add the mountpoint if specified
        if self.mountpoint is not None:
            cmd.append("-m")
            cmd.append(self.mountpoint)

        cmd.append(self.name)
        try:
            cmd.append(" ".join(self.vdev_list))
        except TypeError:
            # there is a None in the vdev_list:
            raise RuntimeError("Invalid entry in vdev_list:  " + \
                               str(self.vdev_list))
        subprocess.check_call(cmd)

    def destroy(self, force=False):
        """ class method to destroy the zpool
        """
        if self.exists:
            cmd = [ZPOOL, "destroy"]
            if force:
                cmd.append("-f")
            cmd.append(self.name)

            subprocess.check_call(cmd)

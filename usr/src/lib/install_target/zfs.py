#!/usr/bin/python
#
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

'''
Heavyweight (due to use of subprocess) python interface to ZFS
'''

import subprocess

_NULL = open("/dev/null", "r+")
ZFS = "/usr/sbin/zfs"

class Dataset(object):
    '''Class representing a ZFS dataset. Dataset does not have to exist;
    it can be created (see Dataset.create())
    
    ZFS properties of the dataset, if it exists, can be read/modified as
    if they were native attributes.
    
    Note: This class does not support 'arbitrary' attributes. The only valid
    attributes are "name" and valid ZFS properties.
    
    '''
    
    __slots__ = ["name"]
    
    def __init__(self, name):
        
        self.name = name
    
    # __getattr__ is only run if "name" is not already a defined attribute
    # of this object (i.e., it doesn't yet exist in __slots__)
    def __getattr__(self, name):
        
        if self.exists:
            try:
                return self.get(name)
            except subprocess.CalledProcessError:
                raise AttributeError("%s not a ZFS property" % name)
        else:
            raise AttributeError("Can't get %s for non-existent dataset" % name)
    
    def __setattr__(self, name, value):
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            try:
                self.set(name, value)
            except subprocess.CalledProcessError:
                raise AttributeError("'%s' is an invalid ZFS property" % name)
    
    def snapshot(self, snapshot_name, overwrite=False):
        snap = self.snapname(snapshot_name)
        if overwrite and snap in self.snapshot_list:
            self.destroy(snapshot_name)
        command = [ZFS, "snapshot", snap]
        subprocess.check_call(command)
    
    def snapname(self, short_name):
        '''Returns the full (dataset@snapshot) name based on the given
        short name'''
        return self.name + "@" + short_name
    
    def _snapshots(self):
        ''' Get list of snapshots.  Snapshots returned will be in creation
            time order with the earliest first '''
        command = [ZFS, "list", "-H", "-o", "name", "-t", "snapshot", "-s", "creation", "-r", self.name]
        popen = subprocess.Popen(command, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        snapshots, stderr = popen.communicate()
        if stderr or popen.returncode:
            raise CalledProcessError(stderr or popen.returncode, command)
        return snapshots.splitlines()
    
    # Probably a bit heavyweight for a property
    snapshot_list = property(_snapshots)
    
    def rollback(self, to_snapshot, recursive=False):
        command = [ZFS, "rollback"]
        if recursive:
            command.append("-r")
        command.append(self.snapname(to_snapshot))
        subprocess.check_call(command)
    
    def create(self):
        if not self.exists:
            command = [ZFS, "create", "-p", self.name]
            subprocess.check_call(command)

    def set(self, property, value):
        command = [ZFS, "set", "%s=%s" % (property, value), name]
        subprocess.check_call(command)
    
    def get(self, property):
        command = [ZFS, "get", "-H", "-o", "value", property, self.name]
        popen = subprocess.Popen(command, stdout=subprocess.PIPE)
        result, none_ = popen.communicate()
        if popen.returncode:
            raise subprocess.CalledProcessError("get of %s failed" % property,
                                                command)
        return result.strip()
    
    def destroy(self, snapshot=None, recursive=False):
        command = [ZFS, "destroy"]
        if recursive:
            command.append("-r")
        if snapshot is not None:
            command.append(self.snapname(snapshot))
        else:
            command.append(self.name)
        subprocess.check_call(command)

    def _exists(self):
        command = [ZFS, "list", self.name]
        exists = subprocess.call(command, stdout=_NULL, stderr=_NULL)
        return (exists == 0)
    
    # Also probably a bit heavyweight for a property
    exists = property(_exists)

class Zvol(Dataset):
    """ class representing a zvol.  Inherits from Dataset
    """
    def __init__(self, name):
        super(Zvol, self).__init__(name)

    def create(self, size):
        """ class method to create a zvol.  requires the size argument
        """
        if not self.exists:
            command = [ZFS, "create", "-p", "-V", size, self.name]
            subprocess.check_call(command)

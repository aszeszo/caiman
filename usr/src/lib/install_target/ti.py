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

""" ti.py - checkpoint to instantiate targets
"""

import logging
import os
import os.path
import shutil
import subprocess
import sys
import solaris_install.target.lofi as lofi_lib
import solaris_install.target.zfs as zfs_lib
import solaris_install.target.zpool as zpool_lib

from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint

from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine

# import all of the DOC class objects
from solaris_install.target.target_spec import *

class TargetInstantiation(Checkpoint):
    """ class to instantiate targets
    """

    def __init__(self, name):
        super(TargetInstantiation, self).__init__(name)

        self.zpool_list = list()
        self.vdev_list = list()
        self.dataset_list = list()

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 1

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint
        """
        self.doc = InstallEngine.get_instance().data_object_cache

        if len(self.doc.get_descendants(class_type=Target)) == 0:
            raise RuntimeError("No target nodes specified")

        # pull and parse the list of zpools (if present)
        self.zpool_list = self.doc.get_descendants(class_type=Zpool)
        self.parse_zpool_list()

        # pull and parse the list of datasets
        self.dataset_list = self.doc.get_descendants(class_type=Dataset)
        self.parse_dataset_list()

    def get_vdev_names(self, zpool_entry):
        """ class method to extract all of the vdev names from the DOC
        """
        vdev_list = []
        vdev_doc_list = zpool_entry.get_descendants(class_type=Vdev)
        for vdev_entry in vdev_doc_list:
            disk_list = vdev_entry.get_descendants(class_type=Disk)
            for disk_entry in disk_list:
                disk_name_list = disk_entry.get_descendants(
                    class_type=DiskName)
                for name_entry in disk_name_list:
                    if name_entry.name_type == "ctd":
                        vdev_list.append(name_entry.name)
        return vdev_list

    def parse_zpool_list(self):
        """ class method used to parse the zpool list
        """
        # walk the list
        for zpool_entry in self.zpool_list:
            # create a Zpool object
            new_zpool = zpool_lib.Zpool(zpool_entry.name)
            if zpool_entry.action == "create":
                # destroy the zpool first
                new_zpool.destroy(force=True)

                # get the vdevs
                new_zpool.vdev_list = self.get_vdev_names(zpool_entry)

                # create the zpool
                new_zpool.create()
            elif zpool_entry.action == "delete":
                new_zpool.destroy()
            elif zpool_entry.action == "preserve":
                if not new_zpool.exists:
                    # get the vdevs
                    new_zpool.vdev_list = self.get_vdev_names(zpool_entry)

                    # create the zpool
                    new_zpool.create()
                
    def parse_dataset_list(self):
        """ class method used to parse the dataset list
        """
        # walk the list
        for dataset_entry in self.dataset_list:
            filesystem_list = dataset_entry.get_descendants(
                class_type=Filesystem)
            # walk all filesystems
            for filesystem_entry in filesystem_list:
                # create a new filesystem object
                new_fs = zfs_lib.Dataset(filesystem_entry.dataset_path)

                if filesystem_entry.action == "create":
                    # destroy the dataset first
                    if new_fs.exists:
                        new_fs.destroy()
                    new_fs.create()
                elif filesystem_entry.action == "delete":
                    if new_fs.exists:
                        new_fs.destroy()
                elif filesystem_entry.action == "preserve":
                    # if the dataset doesn't exist, create it
                    if not new_fs.exists:
                        new_fs.create()

            zvol_list = dataset_entry.get_descendants(class_type=Zvol)
            # walk all zvols
            for zvol_entry in zvol_list:
                # create a new filesystem object
                new_zv = zfs_lib.Zvol(zvol_entry.name)

                # get the size entry from the DOC
                size_entry = zvol_entry.get_descendants(class_type=Size)[0]

                if zvol_entry.action == "create":
                    # destroy the dataset first
                    if new_zv.exists:
                        new_zv.destroy()
                    new_zv.create(size_entry.val)
                elif zvol_entry.action == "delete":
                    new_zv.destroy()
                elif zvol_entry.action == "preserve":
                    # if the dataset doesn't exist, create it
                    if not new_zv.exists:
                        new_zv.create()

    def execute(self, dry_run=False):
        """ Primary execution method use by the Checkpoint parent class
        """
        self.logger.debug("Executing Target Instantiation")

        self.parse_doc()



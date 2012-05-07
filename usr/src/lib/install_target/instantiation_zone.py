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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

""" instantiation.py - target instantiation checkpoint.  Parses the Data Object
Cache for physical and logical targets.
"""
from solaris_install import ApplicationData
from solaris_install.engine import InstallEngine
from solaris_install.target import Target
from solaris_install.target.instantiation import TargetInstantiation
from solaris_install.target.logical import BE, DatasetOptions, \
    Filesystem, Zpool, Options

ALT_POOL_DATASET = "alt_pool_dataset"


class TargetInstantiationZone(TargetInstantiation):
    """ class to instantiate targets
    """

    def __init__(self, name):
        super(TargetInstantiation, self).__init__(name)

        # lists for specific elements in the DOC
        self.logical_list = list()

        self.pool_dataset = None

    def parse_doc(self):
        """ class method for parsing the data object cache (DOC) objects
        for use by this checkpoint
        """

        # doc and target nodes
        self.doc = InstallEngine.get_instance().data_object_cache
        self.target = self.doc.get_descendants(name=Target.DESIRED,
                                               class_type=Target)[0]

        # get the alternate "pool" dataset underwhich to instantiate the target
        app_data = self.doc.persistent.get_first_child( \
            class_type=ApplicationData)
        if app_data:
            self.pool_dataset = app_data.data_dict.get(ALT_POOL_DATASET)

        if not self.pool_dataset:
            raise RuntimeError("No alternate 'pool' dataset specified")

        self.logical_list = self.target.get_descendants(class_type=Zpool)

    def create_logicals(self):
        """ method used to parse the logical targets and create the objects
        with action of "create".
        """

        for zpool in self.logical_list:
            # For a zone root, we process the BE and filesystems.
            be_list = zpool.get_children(class_type=BE)
            fs_list = zpool.get_children(class_type=Filesystem)

            # Process filesystems.
            be_fs_list = list()
            be_fs_zfs_properties_list = list()
            shared_fs_list = list()
            shared_fs_zfs_properties_list = list()
            for fs in fs_list:
                if fs.action == "create":
                    # if mountpoint is set then append to zfs_options
                    zfs_options = fs.get_first_child(class_type=Options)
                    if fs.mountpoint:
                        if zfs_options:
                            # Add mountpoint to zfs_options data_dict
                            zfs_options.data_dict["mountpoint"] = fs.mountpoint
                        else:
                            # Create new Options object
                            zfs_options = Options(fs.name,
                                                {"mountpoint": fs.mountpoint})

                    if fs.in_be:
                        # Append filesystem name to BE filesystem list
                        be_fs_list.append(fs.name)
                        be_fs_zfs_properties_list.append(zfs_options)
                    else:
                        # Append filesystem name to shared filesystem list
                        shared_fs_list.append(fs.name)
                        shared_fs_zfs_properties_list.append(zfs_options)

            # Initialize BE with the specified in_be filesystems.
            for be in be_list:
                be.init(self.dry_run, self.pool_dataset, nested_be=True,
                        fs_list=be_fs_list,
                        fs_zfs_properties=be_fs_zfs_properties_list,
                        shared_fs_list=shared_fs_list,
                        shared_fs_zfs_properties=shared_fs_zfs_properties_list)

    def execute(self, dry_run=False):
        """ Primary execution method use by the Checkpoint parent class
        """
        self.logger.debug("Executing Target Instantiation Zone")
        self.dry_run = dry_run

        self.parse_doc()

        # set up logical devices (BE and filesystems)
        if self.logical_list:
            self.create_logicals()

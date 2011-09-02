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

"""
varshared.py - /var /var/share dataset creation checkpoint.
Creates BE /var dataset and global /var/shared dataset.
"""
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.target import Target
from solaris_install.target.logical import Filesystem, Zvol, Zpool

VAR_DATASET_NAME = "var"
VAR_DATASET_MOUNTPOINT = "/var"
SHARED_DATASET_NAME = "VARSHARE"
SHARED_DATASET_MOUNTPOINT = "/var/share"


class VarSharedDatasetError(Exception):
    """Error generated during var/shared filesystem processing"""

    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg


class VarSharedDataset(Checkpoint):
    """ class to create /var /var/share datasets
    """

    def __init__(self, name):
        super(VarSharedDataset, self).__init__(name)

        # lists for specific elements in the DOC
        self.zpool_list = list()
        self.zvol_list = list()
        self.fs_list = list()
        self._root_pool = None

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 1

    def parse_doc(self):
        """ method for parsing data object cache (DOC) objects for use by the
        checkpoint
        """
        # doc and target nodes
        self.doc = InstallEngine.get_instance().data_object_cache
        self.target = self.doc.get_descendants(name=Target.DESIRED,
                                               class_type=Target,
                                               not_found_is_err=True)[0]

        # List of Zpool nodes
        self.zpool_list = self.target.get_descendants(class_type=Zpool,
                                                      not_found_is_err=True)

        # List of Zvols
        self.zvol_list = self.target.get_descendants(class_type=Zvol)

        # List of Filesystems
        self.fs_list = self.target.get_descendants(class_type=Filesystem)

    def in_dataset_list(self, dsname, dsmp):
        """
        Search the list of Zvol's and Filesystems in the DESIRED tree for
        matching name or mountpoint. Return the first matching object found.

        Paramaters:
            dslist  -   List of Zvols/Filesystems
            dsname  -   Dataset name to check for
            dsmp    -   Dataset mountpoint to check for
        """
        # Need to parse through entire list of Zvol's and Datasets
        # checking for both name and mountpoint matches, cannot simply
        # call get_descendants as mountpoint not a valid argument.
        for zv in self.zvol_list:
            if zv.name == dsname:
                return zv

        for fs in self.fs_list:
            if fs.name == dsname or fs.mountpoint == dsmp:
                return fs

        return None

    @property
    def root_pool(self):
        if self._root_pool is not None:
            return self._root_pool

        for root_pool in [z for z in self.zpool_list if z.is_root]:
            self._root_pool = root_pool

        return self._root_pool

    def add_filesystem(self, fsname, fsmp, in_be):
        """
        Add filesystem to root pool.

        Paramaters:
            fsname    -   Filesystem name to add.
            fsmp      -   Filesystem mountpoint
            in_be     -   Filesystem within BE or not
        """
        # Get Root pool
        if self.root_pool is not None:
            fs = self.root_pool.add_filesystem(fsname, mountpoint=fsmp)
            fs.in_be = in_be
        else:
            if in_be:
                raise VarSharedDatasetError("Failed to add '%s' in_be "
                    "filesystem object, the root pool could not be "
                    "located." % (fsname))
            else:
                raise VarSharedDatasetError("Failed to add '%s' "
                    "filesystem object, the root pool could not be "
                    "located." % (fsname))

    def process_filesystem(self, dsname, dsmountpoint):
        """
        Process desired tree for given filesystem and mountpoint.

        Parameters:
            dsname          -   Dataset name to create
            dsmountpoint    -   Dataset mountpoint

        - Filesystem of name "var", mountpoint "/var", and in_be=True
          must be created by the installer. If any Zvol/Filesystem exists in
          the DESIRED tree that conflicts with this raise exception.

        - Filesystem of name "shared", mountpoint "/var/shared", and
          in_be=False must be created by the installer. If any Zvol/Filesystem
          exists in the DESIRED tree that conflicts with this raise exception.
        """

        # Process Zvol/Filesystem list, ensure fs does not exist
        desired_ds = self.in_dataset_list(dsname, dsmountpoint)
        if desired_ds is not None:
            if isinstance(desired_ds, Zvol):
                raise VarSharedDatasetError("Invalid Zvol specified with "
                        "restricted name '%s'. A dataset of this name is "
                        "created as a filesystem during installation. " % \
                        (dsname))

            else:
                # Filesystem instance found.
                # Fail if Filesystem is not on root pool
                if not desired_ds.parent.is_root:
                    raise VarSharedDatasetError("Filesystem '%s' being "
                        "created on non-root pool '%s'." % \
                        (dsname, desired_ds.parent.name))

                # Fail if name not correct
                if desired_ds.name != dsname:
                    raise VarSharedDatasetError("Invalid dataset name '%s' "
                        "provided for filesystem being mounted on '%s'. "
                        "Must be set to '%s'." % \
                        (desired_ds.name, dsmountpoint, dsname))

                # Fail if mountpoint not correct
                if desired_ds.mountpoint != dsmountpoint and \
                    not (desired_ds.mountpoint is None and \
                    dsname == VAR_DATASET_NAME):
                    raise VarSharedDatasetError("Invalid dataset mountpoint "
                        "'%s' provided for filesystem '%s'. "
                        "Must be set to '%s'" % \
                        (desired_ds.mountpoint, dsname, dsmountpoint))

                # Fail if "var" Filesystem outside BE
                if not desired_ds.in_be and dsname == VAR_DATASET_NAME:
                    raise VarSharedDatasetError("Filesystem '%s' is being "
                        "specified outside of root pool Boot Environment." % \
                        (dsname))

                # Fail if "shared" Filesystem inside BE
                if desired_ds.in_be and dsname == SHARED_DATASET_NAME:
                    raise VarSharedDatasetError("Filesystem '%s' is being "
                        "specified inside of root pool Boot Environment." % \
                        (dsname))

                # At this point we have a Filesystem object which matches
                # what is required by installation, no need to add new object
                # to desired tree, simply return.
                return

        # If we get to here, we have not found filesystem in desired tree
        # So we need to add it as a filesystem to the root pool
        if dsname == VAR_DATASET_NAME:
            self.add_filesystem(dsname, dsmountpoint, in_be=True)
        else:
            self.add_filesystem(dsname, dsmountpoint, in_be=False)

    def execute(self, dry_run=False):
        """ Primary execution method use by the Checkpoint parent class
        """
        self.logger.debug("Executing Var Share Dataset Addition")

        self.parse_doc()

        # Process /var in_be Filesystem and /var/shared global Filesystem
        # Uncomment line below when implementing SHARED_DATASET
        for fs, mp in [(VAR_DATASET_NAME, VAR_DATASET_MOUNTPOINT)]:
#                       (SHARED_DATASET_NAME, SHARED_DATASET_MOUNTPOINT)]:
            self.process_filesystem(fs, mp)

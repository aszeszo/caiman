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

""" target_selection_zone.py - Select Install Target(s)
"""

import copy
import platform

from solaris_install import ApplicationData
from solaris_install.engine import InstallEngine
from solaris_install.target import Target
from solaris_install.target.controller import DEFAULT_LOGICAL_NAME
from solaris_install.target.instantiation_zone import ALT_POOL_DATASET
from solaris_install.target.logical import Logical, BE, Filesystem
from solaris_install.auto_install.checkpoints.target_selection import \
     TargetSelection, SelectionError


class TargetSelectionZone(TargetSelection):
    """ TargetSelectionZone - Checkpoint to select install target.

        This checkpoint selects the install target(s) for a zone based on
        the information provided as the zone's alternate pool dataset and the
        target information provided in the AI Manifest.

        If it's not possible to determine a selection, then a SelectionError
        exception will be raised, causing the installation to fail.
    """

    def __init__(self, name, be_mountpoint="/a"):
        super(TargetSelectionZone, self).__init__(name, be_mountpoint)

        # instance attributes
        self.be_mountpoint = be_mountpoint
        self.doc = InstallEngine.get_instance().data_object_cache

        # set the zone's alternate pool dataset
        self.selected_dataset = None

        # set the platform
        self.arch = platform.processor()

    def select_zone_targets(self, from_manifest):
        '''Logic to select the targets for a zone.

           Given the alternate pool dataset, and the targets from the
           manifest, make the selections.

           If no suitable selection can be made, then the SelectionError
           exception will be raised.  This should only be the cause if the
           selected alternate pool dataset does not exist.

           Returns a new set of Targets that can be insterted into the
           Data Object Cache for TargetInstantiationZone to use.

        '''

        # The selected alternate pool dataset must be set
        if self.selected_dataset is None:
            raise SelectionError("No dataset selected as alternate pool "
                                 "dataset.")

        # Verify selected dataset exists
        fs = Filesystem(self.selected_dataset)
        if not fs.exists:
            raise SelectionError("Dataset (%s) does not exist." % \
                                 self.selected_dataset)

        if from_manifest:
            self.logger.debug("from_manifest =\n%s\n" % \
                              (str(from_manifest[0])))
        else:
            self.logger.debug("from_manifest is empty\n")

        # Instantiate desired target, logical, and zpool objects.
        target = Target(Target.DESIRED)
        logical = Logical(DEFAULT_LOGICAL_NAME)
        logical.noswap = True
        logical.nodump = True
        zpool = logical.add_zpool(self.selected_dataset)

        for manifest_target in from_manifest:
            # Copy filesystem children into desired zpool
            for fs in manifest_target.get_descendants(class_type=Filesystem):
                zpool.insert_children(copy.deepcopy(fs))

            # Copy BE children into desired zpool
            for be in manifest_target.get_descendants(class_type=BE):
                zpool.insert_children(copy.deepcopy(be))

        # Check if we have a BE object under zpool.
        # If not, create one.
        be_list = zpool.get_children(class_type=BE)
        if not be_list:
            # Instantiate new BE object and insert it into zpool.
            be = BE()
            zpool.insert_children(be)
        else:
            # Zpool will have only one BE object.
            be = be_list[0]

        # Set BE's mountpoint to the mountpoint we need
        # to mount it at to do the installation.
        be.mountpoint = self.be_mountpoint

        # Insert desired logical object into the desired target object.
        target.insert_children(logical)

        # Insert desired target object into the DOC.
        self.doc.persistent.insert_children(target)

    def parse_doc(self):
        """ Method for locating objects in the  data object cache (DOC) for
            use by the checkpoint.

            Will return a Data Object reference for the Targets from the
            manifest.
        """

        from_manifest = self.doc.find_path(
            "//[@solaris_install.auto_install.ai_instance.AIInstance?2]"
            "//[@solaris_install.target.Target?2]")

        app_data = self.doc.persistent.get_first_child( \
            class_type=ApplicationData)
        if app_data:
            self.selected_dataset = app_data.data_dict.get(ALT_POOL_DATASET)

        return from_manifest

    # Implement AbstractCheckpoint methods.
    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 3

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class
            to select the targets during an install.
        """
        self.logger.debug("=== Executing Target Selection Zone Checkpoint ==")

        from_manifest = self.parse_doc()

        self.select_zone_targets(from_manifest)

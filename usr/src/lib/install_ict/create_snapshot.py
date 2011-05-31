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

import solaris_install.ict as ICT
from solaris_install import ApplicationData
from solaris_install.target.instantiation_zone import ALT_POOL_DATASET
from solaris_install.target.logical import Options
from solaris_install.target.libbe.be import be_create_snapshot


class CreateSnapshot(ICT.ICTBaseClass):
    '''ICT checkpoint class creates an initial snapshot of the installed
       boot environment data set.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used.
        '''
        super(CreateSnapshot, self).__init__(name)

        # The default name for the initial snapshot
        self.snapshot_name = 'install'

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Creates snapshots for the specified data set once the
            installation completes.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message provides the steps that would be
              run for the checkpoint.

            Returns:
            - Nothing
              On failure, a RuntimeError is raised by the cfunc interface.
        '''

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Get the name of the initial boot environment
        be_name = self.boot_env.name

        # Get the snapshot name. This is optional, so it may not exist
        # get_descendants returns an empty list if not found.
        snapshot = self.boot_env.get_descendants(class_type=Options)
        if snapshot:
            self.snapshot_name = snapshot[0].options_str

        self.logger.debug("Creating initial snapshot. be: %s, snapshot: %s",
                          be_name, self.snapshot_name)

        # See if we're operating on a nested BE by getting the alternate
        # pool dataset.  This should be set by the application.
        alt_pool_dataset = None
        app_data = None
        app_data = self.doc.persistent.get_first_child( \
            class_type=ApplicationData)
        if app_data:
            alt_pool_dataset = app_data.data_dict.get(ALT_POOL_DATASET)

        if not dry_run:
            # Create the initial snapshot of the installed system
            be_create_snapshot(be_name, self.snapshot_name,
                altpool=alt_pool_dataset)

    def get_progress_estimate(self):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.
        '''
        #XXXThis needs to be more accurately determined
        return 5

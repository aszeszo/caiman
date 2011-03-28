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
from solaris_install import Popen


class BootArchive(ICT.ICTBaseClass):
    '''ICT checkpoint updates the boot archive using bootadm(1M).
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(BootArchive, self).__init__(name)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Execute in a subprocess the following command:
                   /usr/sbin/bootadm update-archive -R target_directory

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        self.logger.debug('ICT current task: updating the boot archive')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Run bootadm
        #XXX This should probably eventually be migrated once libbootmgt
        #goes back
        cmd = [ICT.BOOTADM, 'update-archive', '-R', self.target_dir]
        if dry_run:
            self.logger.debug('Executing: %s', cmd)
        if not dry_run:
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                logger=self.logger)

    def get_progress_estimate(self):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.
        '''
        return 20

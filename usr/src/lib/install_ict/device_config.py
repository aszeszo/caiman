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


class DeviceConfig(ICT.ICTBaseClass):
    '''ICT checkpoint sets up the dev namespace on the target using
       devfsadm(1M) if installing from IPS.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(DeviceConfig, self).__init__(name)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Execute in a subprocess the following command:
                   /usr/sbin/devfsadm -R target_directory

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''

        self.logger.debug('ICT current task: setting up device namespace')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Run devfsadm
        cmd = [ICT.DEVFSADM, '-R', self.target_dir]
        if dry_run:
            self.logger.debug('Executing: ', cmd)

        if not dry_run:
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                logger=self.logger)

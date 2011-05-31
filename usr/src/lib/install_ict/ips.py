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

import os

import solaris_install.ict as ICT
import pkg.client.api_errors as api_errors
import pkg.client.image as image

from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.target import Target
from solaris_install.target.logical import BE


class SetFlushContentCache(ICT.ICTBaseClass):
    '''ICT checkpoint to flush the IPS content cache.

        The SetFlushContentCache restores the original IPS default to not purge
        the IPS download cache.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
        '''
        super(SetFlushContentCache, self).__init__(name)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        self.logger.debug('ICT current task: Set IPS '
                          'flush-content-cache-on-success')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Restore the original IPS default and
        # set purging the IPS download cache to "False"
        self.logger.debug('Executing: Set IPS flush-content-cache-on-success '
                          'to False')
        if not dry_run:
            try:
                img = image.Image(root=self.target_dir, user_provided_dir=True)
                img.set_property('flush-content-cache-on-success', 'False')
            except api_errors.ImageNotFoundException, err:
                self.logger.debug("No IPS image found at install target")

            # The above call will end up leaving our process's cwd
            # in the image's root area, which will cause pain later
            # on in trying to unmount the image.  So we manually
            # change dir back to "/".
            os.chdir("/")

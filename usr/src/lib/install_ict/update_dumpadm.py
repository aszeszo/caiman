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
import os
import shutil


class UpdateDumpAdm(ICT.ICTBaseClass):
    '''ICT checkpoint class updates the dumpadm.conf file to customize
       it according to the install parameters.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used.
        '''
        super(UpdateDumpAdm, self).__init__(name)

        # Define the location of the dumpadm file
        self.dumpadmfile = '/etc/dumpadm.conf'

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Updates the dumpadm.conf file to customize it according
            to the install parameters.  (This is just temporary solution,
            as dumpadm(1M) -r option does not work. This issue is tracked
            by Bugster CR 6835106. Once this bug is fixed,dumpadm(1M) -r
            should be used for manipulating /etc/dumpadm.conf instead.)

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message provides the steps that would be
              run for the checkpoint.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''

        # Check if source dumpadm.conf file exists
        if not os.path.exists(self.dumpadmfile):
            self.logger.info("Dump device was not configured during the "
                             "installation, %s file will not be created on "
                             "the target." % (self.dumpadmfile))
            return

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        dumpadmfile_dest = os.path.join(self.target_dir,
                                        ICT.DUMPADM_CONF)

        self.logger.debug("Copying %s to %s", ICT.DUMPADM_CONF,
                          dumpadmfile_dest)

        if not dry_run:
            if not os.path.exists(os.path.dirname(dumpadmfile_dest)):
                os.makedirs(os.path.dirname(dumpadmfile_dest))
            
            shutil.copyfile(self.dumpadmfile, dumpadmfile_dest)

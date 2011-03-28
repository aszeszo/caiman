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


class InitializeSMF(ICT.ICTBaseClass):
    '''ICT checkpoint sets up an smf repository and corrects
       the smf system profile.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(InitializeSMF, self).__init__(name)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Initializing SMF involves two sub-tasks:
            - Copy /lib/svc/seed/global.db to /etc/svc/repository.db
            - Create symlinks to the correct system profile files

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        # The smf source and destination
        source_db = None
        destination_db = None

        self.logger.debug('ICT current task: Setting up the SMF repository')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Set up the smf source and destination
        source_db = os.path.join(self.target_dir, ICT.GLOBAL_DB)
        destination_db = os.path.join(self.target_dir, ICT.REPO_DB)

        sys_profile_dict = {
            ICT.GEN_LTD_NET_XML:
                os.path.join(self.target_dir, ICT.GENERIC_XML),
            ICT.NS_DNS_XML:
                os.path.join(self.target_dir, ICT.NAME_SVC_XML),
            ICT.INETD_XML:
                os.path.join(self.target_dir, ICT.INETD_SVCS_XML),
            os.path.basename(ICT.SC_PROFILE):
                os.path.join(self.target_dir, ICT.PROFILE_SITE)}

        self.logger.debug("Copying %s to %s", source_db, destination_db)
        if not dry_run:
            # copy the source data base to the destination data base
            shutil.copy2(source_db, destination_db)

        self.logger.debug("ICT current task: "
                          "Creating symlinks to system profile")
        if not dry_run:
            for key, value in sys_profile_dict.items():
                if os.path.exists(value):
                    os.unlink(value)
                self.logger.debug("Creating a symlink between %s and %s",
                                  key, value)
                os.symlink(key, value)

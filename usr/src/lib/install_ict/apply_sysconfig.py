#!/usr/bin/python
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

import grp
import os
import shutil
import solaris_install.ict as ICT
from stat import S_IRUSR

from solaris_install import Popen


class ApplySysConfig(ICT.ICTBaseClass):
    '''ICT checkpoint that applies the system configuration SMF profile
       to the target during an AI installation'''

    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(ApplySysConfig, self).__init__(name)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Validates the profile against service configuration DTD
            using svccfg.

            Copies the profiles in PROFILE_DIR to the profile destination
            to the target during an AI installation.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        self.logger.debug('ICT current task: Applying the system '
                          'configuration profile')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        sc_profile_dst = os.path.join(self.target_dir, ICT.PROFILE_DEST)

        # make list of files in profile input directory
        self.logger.debug("Checking for %s", ICT.PROFILE_DIR)
        if not dry_run:
            if not os.access(ICT.PROFILE_DIR, os.F_OK):
                self.logger.debug("%s does not exist", ICT.PROFILE_DIR)
                self.logger.debug("There are no system configuration profiles "
                                  "to apply")
                return

        if not dry_run:
            if not os.path.exists(sc_profile_dst):
                os.makedirs(sc_profile_dst)
                # read-only by user (root)
                os.chmod(sc_profile_dst, S_IRUSR)
                # chown root:sys
                os.chown(sc_profile_dst, 0, grp.getgrnam(ICT.SYS).gr_gid)

        for root, dirs, files in os.walk(ICT.PROFILE_DIR, topdown=False):
            for name in files:
                # only copy files matching the template 'profileNNNN.xml'
                if not name.startswith('profile') or not name.endswith('.xml'):
                    continue

                self.logger.debug("Applying profile %s", name)
                # validate against DTD using svccfg
                cmd = [ICT.SVCCFG, 'apply', '-n ', os.path.join(root, name)]
                if dry_run:
                    self.logger.debug('Executing: %s', cmd)
                if not dry_run:
                    os.environ[ICT.SVCCFG_DTD] = os.path.join(self.target_dir,
                                                              ICT.SVC_BUNDLE)
                    os.environ[ICT.SVCCFG_REPOSITORY] = os.path.join(
                                                              self.target_dir,
                                                              ICT.SVC_REPO)
                    Popen.check_call(cmd, stdout=Popen.STORE, \
                                     stderr=Popen.STORE,
                        logger=self.logger)

                fdst = os.path.join(sc_profile_dst, name)

                self.logger.debug('Copying %s to %s', name, fdst)
                if not dry_run:
                    shutil.copy(os.path.join(root, name), fdst)
                    # read-only by user (root)
                    os.chmod(fdst, S_IRUSR)
                    # chown root:sys
                    os.chown(fdst, 0, grp.getgrnam(ICT.SYS).gr_gid)

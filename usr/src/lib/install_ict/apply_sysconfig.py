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

# Checkpoint specific dictionary and keys
APPLY_SYSCONFIG_DICT = "apply_sysconfig_dict"
APPLY_SYSCONFIG_PROFILE_KEY = "profile"


class ApplySysConfig(ICT.ICTBaseClass):
    '''ICT checkpoint that applies the system configuration SMF profile(s)
       to the target during an AI installation'''

    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(ApplySysConfig, self).__init__(name)

        self.profile = None

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Validates the profile against service configuration DTD
            using svccfg.

            Copies a profile or directory of profiles to the smf site profile
            directory in the target destination area.  The path of the profile
            or directory of profiles is stored in a data dictionary in the DOC
            with a name defined by this checkpoint.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''
        self.logger.debug('ICT current task: Applying the system '
                          'configuration profile(s)')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        sc_profile_dst = os.path.join(self.target_dir, ICT.PROFILE_DEST)

        # Get the profile specification from the specific
        # data dictionary stored in the DOC
        as_doc_dict = self.doc.volatile.get_first_child( \
            name=APPLY_SYSCONFIG_DICT)

        # If dictionary not set, or profile value not set in
        # dictionary, there's no work to do.
        if as_doc_dict is not None:
            self.profile = as_doc_dict.data_dict.get( \
                APPLY_SYSCONFIG_PROFILE_KEY)

        if self.profile is None:
            self.logger.debug("No profile given.")
            return

        self.logger.debug("Checking for profile %s", self.profile)

        # If profile does not exist, there's no work to do
        if not os.access(self.profile, os.F_OK):
            self.logger.debug("Cannot access profile %s" % self.profile)
            self.logger.debug("There are no system configuration profiles "
                              "to apply")
            return

        # Make sure destination directory exists.
        if not dry_run:
            if not os.path.exists(sc_profile_dst):
                os.makedirs(sc_profile_dst)
                # read-only by user (root)
                os.chmod(sc_profile_dst, S_IRUSR)
                # chown root:sys
                os.chown(sc_profile_dst, 0, grp.getgrnam(ICT.SYS).gr_gid)

        # profile may be a file or directory, handle either case.
        profile_list = list()
        if os.path.isdir(self.profile):
            self.logger.debug("Processing profile directory %s", self.profile)
            for root, dirs, files in os.walk(self.profile, topdown=False):
                for name in files:
                    # Add name to list of profile files to process.
                    profile_list.append(os.path.join(root, name))
        else:
            self.logger.debug("Processing profile file %s", self.profile)
            profile_list.append(self.profile)

        for profile in profile_list:
            self.logger.debug("Applying profile %s", profile)
            # validate against DTD using svccfg
            cmd = [ICT.SVCCFG, 'apply', '-n ', profile]
            if dry_run:
                self.logger.debug('Executing: %s', cmd)
            if not dry_run:
                os.environ[ICT.SVCCFG_DTD] = os.path.join(self.target_dir,
                                                          ICT.SVC_BUNDLE)
                os.environ[ICT.SVCCFG_REPOSITORY] = os.path.join(
                                                          self.target_dir,
                                                          ICT.SVC_REPO)
                Popen.check_call(cmd, stdout=Popen.STORE, \
                                 stderr=Popen.STORE, logger=self.logger)

            fdst = os.path.join(sc_profile_dst, os.path.basename(profile))

            self.logger.debug('Copying %s to %s', profile, fdst)
            if not dry_run:
                shutil.copy(profile, fdst)
                # read-only by user (root)
                os.chmod(fdst, S_IRUSR)
                # chown root:sys
                os.chown(fdst, 0, grp.getgrnam(ICT.SYS).gr_gid)

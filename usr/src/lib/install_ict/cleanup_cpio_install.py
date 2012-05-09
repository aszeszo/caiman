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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

import os
import shutil

import pkg.client.api as api
import pkg.client.api_errors as api_errors
import solaris_install.ict as ICT

from stat import S_IREAD, S_IRGRP, S_IROTH

from solaris_install import PKG5_API_VERSION
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import CPIOSpec
from solaris_install.transfer.info import IPSSpec
from solaris_install.transfer.ips import InstallCLIProgressTracker
from solaris_install.transfer.info import Software


VOLSETID = '.volsetid'


class CleanupCPIOInstall(ICT.ICTBaseClass):
    '''
       The CleanupCPIOInstall checkpoint performs clean up on the system after
       a live CD install. This checkpoint performs the following when the
       the execute method is called:
       - Creates /etc/mnttab if it doesn't already exist and chmods it to the
         correct values
       - Removes files and directories that are not needed by the installed
         system
       - Remove miscellanous directory trees used as work areas during
         installation
       - Remove install-specific packages that are not needed by the installed
         system
       - Reset pkg(1) image UUID for preferred publisher
       - Relocate configuration files from the save directory
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
        '''
        super(CleanupCPIOInstall, self).__init__(name)

        self.cleanup_list = ['.livecd', VOLSETID, '.textinstall',
                             'etc/sysconfig/language', '.liveusb',
                             'a', 'bootcd_microroot', 'var/user/jack',
                             'var/cache/gdm/jack/dmrc', 'var/cache/gdm/jack/']

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

        # Variable used to store the result of a pkg api plan_uninstall
        pkg_rval = False

        # List to hold requested packages to be removed
        pkg_rm_node = []

        # Dictionary and lists used to hold the results of package info check
        # for packages in the list of packages requested for removal
        pkg_ret_info = {}
        pkgs_found = []
        pkgs_notfound = []
        pkgs_illegal = []

        # Variables used to check for valid packages
        info_local = True
        info_needed = api.PackageInfo.ALL_OPTIONS

        # The software node containing packages, directories and files that
        # need removal
        soft_list = None

        self.logger.debug('ICT current task: cleanup install')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # For GRUB2 based media there is a .volsetid derived ident file that
        # identifies the root of the image during GRUB2 configuration. It
        # needs to be removed from the target if present.
        # eg. if the contents of .volsetid are "ABC-123" then the ident file
        # name will be (dot)volsetid: ".ABC-123"
        volsetid = None
        if VOLSETID in self.cleanup_list:
            vpath = os.path.join(self.target_dir, VOLSETID)
            with open(vpath, 'r') as vpath_fh:
                volsetid = vpath_fh.read().strip()
        if volsetid and \
            os.path.exists(os.path.join(self.target_dir, '.' + volsetid)):
            self.cleanup_list.append('.' + volsetid)

        # Get the list of install specific items that need to be removed.
        # Check for both IPS packages and files and directories
        # If no items are designated, an empty list is returned.
        soft_list = self.doc.get_descendants(name=self.name,
                                             class_type=Software)

        if soft_list:
            soft_node = soft_list[0]

            # Get the list of install specific packages that need to
            # be removed.
            try:
                pkg_rm_node = soft_node.get_children(class_type=IPSSpec)[0]
            except IndexError:
                # No IPS packages have been specified
                pass

            # Get the list of install specific files that need to be removed.
            try:
                file_rm_node = soft_node.get_children(class_type=CPIOSpec)[0]
                self.cleanup_list.extend(file_rm_node.contents)
            except IndexError:
                # No additional CPIO contents have been specified
                pass

        # Create the mnttab file
        self.logger.debug('Executing: Create /etc/mnttab file')
        if not dry_run:
            mnttab = os.path.join(self.target_dir, ICT.MNTTAB)
            mnttab_dir = os.path.dirname(mnttab)

            # Create the directory that holds the mnttab file,
            # if it does not exist.
            if not os.access(mnttab_dir, os.F_OK):
                os.makedirs(mnttab_dir)

            # Create the mnttab file if it does not exist.
            if not os.access(mnttab, os.F_OK):
                open(mnttab, 'w').close()
                os.chmod(mnttab, S_IREAD | S_IRGRP | S_IROTH)

        # Remove and miscellaneous directories used as work areas
        self.logger.debug('Executing: Remove miscellaneous work directories '
                          'from /var/tmp')
        for root, dirs, files in os.walk(os.path.join(self.target_dir,
                                         'var/tmp'), topdown=False):
            for name in files:
                self.logger.debug('Removing %s', name)
                if not dry_run:
                    os.unlink(os.path.join(root, name))

            for work_dir in dirs:
                self.logger.debug('Removing %s', work_dir)
                if not dry_run:
                    os.rmdir(os.path.join(root, work_dir))

        self.logger.debug('Executing: Remove miscellaneous work directories '
                          'from /mnt')
        for root, dirs, files in os.walk(os.path.join(self.target_dir,
                                         'mnt'), topdown=False):
            for name in files:
                self.logger.debug('Removing %s', name)
                if not dry_run:
                    os.unlink(os.path.join(root, name))
            for work_dir in dirs:
                self.logger.debug('Removing %s', work_dir)
                if not dry_run:
                    os.rmdir(os.path.join(root, work_dir))

        if not dry_run:
            try:
                api_inst = api.ImageInterface(self.target_dir,
                               PKG5_API_VERSION,
                               InstallCLIProgressTracker(self.logger),
                               None,
                               ICT.PKG_CLIENT_NAME)

            except api_errors.VersionException, ips_err:
                raise ValueError("The IPS API version specified, "
                                 + str(ips_err.received_version) +
                                 " does not agree with "
                                 "the expected version, "
                                 + str(ips_err.expected_version))

        # Remove install-specific packages that are not needed
        if pkg_rm_node and len(pkg_rm_node.contents) > 0:
            self.logger.debug("Executing: Remove unneeded install-specific "
                              "packages")

            # Check that all of the packages are valid packages
            # before trying to uninstall them
            self.logger.debug('Validating the packages to be uninstalled '
                '%s', pkg_rm_node.contents)

            if not dry_run:
                try:
                    pkg_ret_info = api_inst.info(pkg_rm_node.contents,
                                                 info_local,
                                                 info_needed)
                except api_errors.NoPackagesInstalledException:
                    self.logger.debug("no packages from the uninstall list "
                                      "are installed")

                if pkg_ret_info:
                    pkgs_found = pkg_ret_info[api.ImageInterface.INFO_FOUND]
                    pkgs_notfound = pkg_ret_info[
                                    api.ImageInterface.INFO_MISSING]
                    pkgs_illegal = pkg_ret_info[
                                   api.ImageInterface.INFO_ILLEGALS]

                    for notfound in pkgs_notfound:
                        self.logger.debug("'%s' is not installed - skipping"
                                          % notfound)
                        pkg_rm_node.contents.remove(notfound)

                    for illegal in pkgs_illegal:
                        self.logger.debug("'%s' is not a legal package for "
                                          "this install image - skipping"
                                          % illegal)
                        pkg_rm_node.contents.remove(illegal)

            # Uninstall the packages
            if not pkgs_found:
                self.logger.debug('No packages to uninstall')
            else:
                self.logger.debug('Uninstalling the packages...')
                self.logger.debug('%s', pkg_rm_node.contents)
                if not dry_run:
                    # Reset the value to false
                    pkg_rval = False
                    try:
                        pkg_args = pkg_rm_node.get_first_child(
                            Args.ARGS_LABEL, Args)
                    except ObjectNotFoundError, err:
                        # No package arguments have been defined
                        pass

                    if pkg_args:
                        pkg_rval = api_inst.gen_plan_uninstall(
                            pkg_rm_node.contents, **pkg_args.arg_dict)
                    else:
                        pkg_rval = api_inst.plan_uninstall(
                            pkg_rm_node.contents)

                if pkg_rval:
                    api_inst.prepare()
                    api_inst.execute_plan()
                    api_inst.reset()
                else:
                    self.logger.debug('Unable to uninstall install specific '
                                      'packages')

        # Reset the pkg(1) image UUID to the preferred publisher
        self.logger.debug('Executing: Setting the UUID to the preferred '
                          'publisher')
        if not dry_run:
            publisher = api_inst.get_highest_ranked_publisher()
            publisher.reset_client_uuid()

        #
        # Now that all pkg(5) operations are finished, restore files
        # from the save directory. This order of steps is intentional,
        # as pkg(5) operations may have wanted to modify files which
        # are to be restored.
        #
        # As an example, uninstalling media/internal package removed
        # media specific 'jack' user from the target system. That (among other
        # things) removed related entry from shadow(4) file (now to be
        # restored from save area).
        #
        savedir = os.path.join(self.target_dir, 'save')
        if os.path.exists(savedir):
            self.logger.debug('Executing: Relocate configuration files')
            for root, dirs, files in os.walk(savedir, topdown=False):
                if not files:
                    continue

                target = root.replace('/save', '')
                if not dry_run:
                    if not os.access(target, os.F_OK):
                        os.makedirs(target, 0755)

                for name in files:
                    src_file = os.path.join(root, name)
                    dst_file = os.path.join(target, name)
                    self.logger.debug('Moving %s to %s', src_file, dst_file)
                    if not dry_run:
                        #
                        # Use shutil.move(), as it transfers also file
                        # permissions and ownership. Assuming that files
                        # in save area were created with desired permissions
                        # and ownership.
                        #
                        shutil.move(src_file, dst_file)

            shutil.rmtree(savedir)

        # Remove the files and directories in the cleanup_list
        self.logger.debug('Executing: Cleanup of %s', self.cleanup_list)
        for cleanup_name in self.cleanup_list:
            cleanup = os.path.join(self.target_dir, cleanup_name)
            self.logger.debug("Removing %s", cleanup)
            if not dry_run:
                if os.access(cleanup, os.F_OK):
                    if os.path.isfile(cleanup):
                        os.unlink(cleanup)
                    else:
                        os.rmdir(cleanup)

    def get_progress_estimate(self):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.
        '''
        #XXXThis needs to be determined more accurately
        return 60

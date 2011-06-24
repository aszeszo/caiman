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

""" ai_configuration.py - AI Configuration
"""

import os
import shutil
import urllib

from solaris_install import ApplicationData, Popen, CalledProcessError
from solaris_install.auto_install import TRANSFER_FILES_CHECKPOINT
from solaris_install.configuration.configuration import Configuration
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.ict import SVCCFG
from solaris_install.target import Target
from solaris_install.target.instantiation_zone import ALT_POOL_DATASET
from solaris_install.target.logical import Filesystem

# Define constants
XMLLINT = '/usr/bin/xmllint'

# Checkpoint specific AI ApplicationData dictionary keys
AI_SERVICE_LIST_FILE = "service_list_file"


class AIConfigurationError(Exception):
    '''Error generated when a configuration error is detected'''

    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg

    def __str__(self):
        return self.msg


class AIConfiguration(Checkpoint):
    """ AIConfiguration - Checkpoint to process configuration
        specifications in the AI manifest.
    """

    def __init__(self, name):
        super(AIConfiguration, self).__init__(name)

        self.app_data = None
        self.service_list_file = None
        self.alt_pool_dataset = None
        self.zone_confs = list()

    def validate_zone_configuration(self, dry_run=False):
        """ Method to download and validate all zone configurations
            specified in the AI manifest.  This method will also query
            the AI installation service (if provided) to download
            AI manifest and SC profiles for the zones specified.
        """

        TMP_ZONES_DIR = os.path.join(self.app_data.work_dir, "zones")
        TMP_ZONES_CONFIG_LIST = os.path.join(TMP_ZONES_DIR, "config_list")
        TMP_ZONES_CONFIG_OUTPUT = os.path.join(TMP_ZONES_DIR, "config_output")
        TMP_ZONES_INSTALL_DIR = os.path.join(TMP_ZONES_DIR, "install")

        TARGET_ZONES_INSTALL_DIR = "/var/zones/install"

        # Clear out the TMP_ZONES_DIR directory in case it exists.
        shutil.rmtree(TMP_ZONES_DIR, ignore_errors=True)

        # Create TMP_ZONES_DIR directory
        os.makedirs(TMP_ZONES_DIR)

        try:
            with open(TMP_ZONES_CONFIG_LIST, 'w') as zones_config_list:
                # Copy all 'source' entries to a local area.
                for conf in self.zone_confs:
                    self.logger.info("Zone name: " + conf.name)
                    self.logger.info("   source: " + conf.source)

                    # Make subdirectory to store this zone's files.  The name
                    # of the zone is used as the name of the subdirectory.
                    os.makedirs(os.path.join(TMP_ZONES_INSTALL_DIR, conf.name))

                    # Retrieve the zone config file.
                    try:
                        (filename, headers) = urllib.urlretrieve(conf.source,
                            os.path.join(TMP_ZONES_INSTALL_DIR, conf.name,
                                         "config"))
                    except urllib.ContentTooShortError, er:
                        raise AIConfigurationError("Retrieval of zone config "
                            "file (%s) failed: %s" % (conf.name, str(er)))

                    # Append this zone's local config file path
                    zones_config_list.write(filename + "\n")

                    # Retrieve this zone's AI manifest and profile(s) from a
                    # remote installation service if service_list_file is
                    # provided.
                    if self.service_list_file is not None:
                        cmd = ["/usr/bin/ai_get_manifest", "-e",
                               "-o", os.path.join(TMP_ZONES_INSTALL_DIR,
                               conf.name, "ai_manifest.xml"),
                               "-p", os.path.join(TMP_ZONES_INSTALL_DIR,
                               conf.name, "profiles"),
                               "-c", "zonename=" + conf.name,
                               "-s", self.service_list_file]
                        try:
                            Popen.check_call(cmd, stdout=Popen.STORE,
                                             stderr=Popen.STORE,
                                             logger=self.logger)
                        except CalledProcessError, er:
                            raise AIConfigurationError("AI manifest query for "
                                "zone (%s) failed: %s" % (conf.name, str(er)))
        except IOError, er:
            raise AIConfigurationError("IO Error during zone validation: "
                                       "%s" % str(er))

        # Pass the create a file with the list of zone config files in it
        # to "/usr/sbin/zonecfg auto-install-report", which will parse the
        # config files, do any necessary validation of the zone configurations,
        # and yield an output file that will contain a list of directories
        # and datasets that are required to exist for the given zone configs
        # to work.

        cmd = ['/usr/sbin/zonecfg', 'auto-install-report',
               '-f', TMP_ZONES_CONFIG_LIST, '-o', TMP_ZONES_CONFIG_OUTPUT]
        try:
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                             logger=self.logger)
        except CalledProcessError, er:
            raise AIConfigurationError("Zone configurations failed "
                                       "to validate.")

        directories = list()
        datasets = list()
        try:
            with open(TMP_ZONES_CONFIG_OUTPUT, 'r') as zones_config_output:
                for line in zones_config_output:
                    (name, value) = line.strip().split("=", 2)

                    if name == "zonepath_parent":
                        directories.append(value)
                    elif name == "zfs_dataset":
                        datasets.append(value)
                    else:
                        raise AIConfigurationError("Failure: unknown keyword "
                            "in %s: %s" % (TMP_ZONES_CONFIG_OUTPUT, name))
        except IOError, er:
            raise AIConfigurationError("Could not read zone config output "
                                       "file (%s): %s" % \
                                       (TMP_ZONES_CONFIG_OUTPUT, str(er)))

        # TODO: Check that all zonepath_parent values are directories that
        # will not exist under a filesystem dataset that is inside the BE.

        # Ensure all zfs_dataset values are specified to be created
        # on the installed system.  At this point, Target Selection
        # should have already run, so we should be able to grab the
        # DESIRED filesystems from the DOC to make sure these datasets
        # are specified.
        if datasets:
            target = self.doc.get_descendants(name=Target.DESIRED,
                class_type=Target, not_found_is_err=True)[0]
            fs_list = target.get_descendants(class_type=Filesystem)

            if fs_list:
                for dataset in datasets:
                    if dataset not in [fs.full_name for fs in fs_list]:
                        raise AIConfigurationError("The following dataset is "
                            "specified in a zone configuration but does not "
                            "exist in the AI manifest: %s" % dataset)

        # Ensure all AI manifests and SC profiles are valid.
        for zone in os.listdir(TMP_ZONES_INSTALL_DIR):
            zone_dir = os.path.join(TMP_ZONES_INSTALL_DIR, zone)

            manifest = os.path.join(zone_dir, "ai_manifest.xml")
            if os.path.isfile(manifest):
                # Validate AI manifest.
                cmd = [XMLLINT, '--valid', manifest]
                if dry_run:
                    self.logger.debug('Executing: %s', cmd)
                else:
                    Popen.check_call(cmd, stdout=Popen.STORE,
                        stderr=Popen.STORE, logger=self.logger)

            profiles_dir = os.path.join(zone_dir, "profiles")
            if os.path.isdir(profiles_dir):
                for profile in os.listdir(profiles_dir):
                    profile_file = os.path.join(profiles_dir, profile)
                    if os.path.isfile(profile_file):
                        # Validate SC profile.
                        cmd = [SVCCFG, 'apply', '-n ', profile_file]
                        if dry_run:
                            self.logger.debug('Executing: %s', cmd)
                        else:
                            Popen.check_call(cmd, stdout=Popen.STORE, \
                                stderr=Popen.STORE, logger=self.logger)

        # Add the zone configuration directory into the dictionary in the DOC
        # that will be processed by the transfer-ai-files checkpoint which will
        # copy files over to the installed root.
        tf_doc_dict = None
        tf_doc_dict = self.doc.volatile.get_first_child( \
            name=TRANSFER_FILES_CHECKPOINT)
        if tf_doc_dict is None:
            # Initialize new dictionary in DOC
            tf_dict = dict()
            tf_doc_dict = DataObjectDict(TRANSFER_FILES_CHECKPOINT,
                tf_dict)
            self.doc.volatile.insert_children(tf_doc_dict)
        else:
            tf_dict = tf_doc_dict.data_dict

        tf_dict[TMP_ZONES_INSTALL_DIR] = TARGET_ZONES_INSTALL_DIR

    def parse_doc(self):
        """ class method for parsing the data object cache (DOC) objects
        for use by this checkpoint
        """
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache

        # Get a reference to ApplicationData object
        self.app_data = self.doc.persistent.get_first_child( \
            class_type=ApplicationData)

        if self.app_data:
            # Get the installation service list file
            self.service_list_file = \
                self.app_data.data_dict.get(AI_SERVICE_LIST_FILE)

            # See if an alternate pool dataset is set.
            self.alt_pool_dataset = \
                self.app_data.data_dict.get(ALT_POOL_DATASET)

        if not self.service_list_file:
            self.logger.debug("No service list provided.")

        # Get all configuration components from the DOC
        self.conf_list = self.doc.get_descendants(class_type=Configuration)

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 2

    def execute(self, dry_run=False):
        """ Execution method

            This method will process all configuration components that are
            in the AI manifest.
        """

        self.parse_doc()

        # AI currently only supports configuration of type 'zone'.
        # Iterate all 'zone' configuration components and process them,
        # ignore all other types.
        for conf in self.conf_list:
            if conf.type is not None and \
                    conf.type == Configuration.TYPE_VALUE_ZONE:
                self.zone_confs.append(conf)
            else:
                self.logger.debug('Unsupported configuration type "' +
                        conf.type + '".  Ignoring ...')

        if self.zone_confs:
            if not self.alt_pool_dataset:
                self.validate_zone_configuration(dry_run=dry_run)
            else:
                # If alt_pool_dataset is not none, we're installing
                # a zone, so we ignore configuration of type 'zone'
                self.logger.debug('Configurations of type "' +
                    Configuration.TYPE_VALUE_ZONE + '" not supported '
                    'when installing a zone.  Ignoring ...')

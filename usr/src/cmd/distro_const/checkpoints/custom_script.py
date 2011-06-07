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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

""" custom_script.py - Runs a custom script as a checkpoint.
"""
from solaris_install import DC_LABEL, Popen
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint


class CustomScript(Checkpoint):
    """ CustomScript - class to execute a custom script
    """

    def __init__(self, name, command):
        super(CustomScript, self).__init__(name)

        self.doc = InstallEngine.get_instance().data_object_cache
        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)[0].data_dict
        self.pkg_img_path = self.dc_dict["pkg_img_path"]
        self.ba_build = self.dc_dict["ba_build"]

        # If command is over multiple lines, join with spaces, and then strip
        # any spaces at the ends.
        self.command = " ".join(command.splitlines()).strip()

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
        """
        # This value will need to change based on the duration of the custom
        # script.  Set it to 1 second by default.
        return 1

    def replace_strings(self):
        """ replace_strings() - method to replace any DOC-specific patterns
        and/or DC-specific patterns
        """
        # replace DOC-specific patterns
        self.command = self.doc.str_replace_paths_refs(self.command)

        if self.command is None:
            raise RuntimeError("Invalid command: '%s'" % self.command)

        # replace DC-specific patterns
        self.command = self.command.replace("{PKG_IMAGE_PATH}",
                                            self.pkg_img_path)
        self.command = self.command.replace("{BOOT_ARCHIVE}", self.ba_build)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Custom Script Checkpoint ===")
        self.logger.info("Custom Script provided is: '%s'" % self.command)

        # replace DOC and DC strings in the command
        self.replace_strings()

        self.logger.info("Custom Script to run is: '%s'" % self.command)

        if not dry_run:
            p = Popen.check_call(self.command, shell=True, stdout=Popen.STORE,
                                 stderr=Popen.STORE, logger=self.logger)

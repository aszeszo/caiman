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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

""" custom_script.py - Runs a custom script as a checkpoint.
"""
import re

from subprocess import PIPE, Popen

from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.engine import InstallEngine


class CustomScript(Checkpoint):
    """ CustomScript - class to execute a custom script
    """

    def __init__(self, name, command):
        super(CustomScript, self).__init__(name)

        self.__replacement_re = re.compile("%{([^}]+)}")

        self.doc = InstallEngine.get_instance().data_object_cache

        # If command is over multiple lines, join with spaces, and then strip
        # any spaces at the ends.
        self.command = " ".join(command.splitlines()).strip()
        self.command_to_execute = self.doc.str_replace_paths_refs(self.command)

        if self.command_to_execute is None:
            raise RuntimeError("Invalid command: '%s'" % \
                self.command_to_execute)

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
        """
        # This value will need to change based on the duration of the custom
        # script.  Set it to 1 second by default.
        return 1

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Custom Script Checkpoint ===")

        self.logger.info("Custom Script provided is: '%s'" % self.command)

        command_to_execute = self.doc.str_replace_paths_refs(self.command)

        self.logger.info("Custom Script to run is: '%s'" %
            command_to_execute)

        if not dry_run and command_to_execute is not None:
            p = Popen(command_to_execute, shell=True, stdout=PIPE,
                      stderr=PIPE)

            # log the output of both stdout and stderr to the debug log
            outs, errs = p.communicate()

            self.logger.info("custom script stdout:")
            for line in outs.splitlines():
                self.logger.debug(line)

            self.logger.info("custom script stderr:")
            for line in errs.splitlines():
                self.logger.debug(line)

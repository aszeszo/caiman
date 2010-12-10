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

""" ai_publish_pkg - Publish the package image area into an pkg(5) repository
"""
import os
import os.path
import subprocess

from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const import DC_LABEL, DC_PERS_LABEL
from solaris_install.distro_const.distro_spec import Distro
from solaris_install.engine import InstallEngine

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()

_NULL = open("/dev/null", "r+")


class AIPublishPackages(Checkpoint):
    """ class to publish the package image area into a repository
    """

    DEFAULT_ARG = {"pkg_name": None, "pkg_repo": None, "prefix": None}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(AIPublishPackages, self).__init__(name)

        self.pkg_name = arg.get("pkg_name")
        self.pkg_repo = arg.get("pkg_repo")
        self.prefix = arg.get("prefix")

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.dc_pers_dict = {}
        self.pkg_img_path = None
        self.tmp_dir = None
        self.media_dir = None

        self.distro_name = None

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 60

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache
        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)[0].data_dict

        try:
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.tmp_dir = self.dc_dict["tmp_dir"]
            self.media_dir = self.dc_dict["media_dir"]
            dc_pers_dict = self.doc.persistent.get_children(name=DC_PERS_LABEL,
                class_type=DataObjectDict)
            if dc_pers_dict:
                self.dc_pers_dict = dc_pers_dict[0].data_dict
            # pkg name is always stored in the persistent tree
            self.ai_pkg_version = self.dc_pers_dict["auto-install"]

            distro = self.doc.volatile.get_children(class_type=Distro)
            self.distro_name = distro[0].name
        except KeyError:
            raise RuntimeError("Error retrieving a value from the DOC")

        if self.pkg_repo is None:
            self.pkg_repo = "file://%s/ai_image_repo" % self.media_dir

        if self.prefix is None:
            self.prefix = "ai-image"

        if self.pkg_name is None:
            self.pkg_name = "image/%s@%s" % (self.distro_name,
                                             self.ai_pkg_version)

    def create_repository(self):
        """ class method to create the repository
        """
        self.logger.info("creating repository")

        # create the repository if the specified protocol is "file:"
        if self.pkg_repo.startswith("file:"):
            cmd = [cli.PKGSEND, "-s", self.pkg_repo, "create-repository",
                   "--set-property", "publisher.prefix=%s" % self.prefix]
            subprocess.check_call(cmd)

        # open the repository
        cmd = [cli.PKGSEND, "-s", self.pkg_repo, "open", self.pkg_name]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=_NULL)
        outs, _none = p.communicate()

        # split the output to get the environment variable needed for pkgsend
        # transactions.  Splitting on None splits on whitespace.
        _none, rest = outs.strip().split(None, 1)
        variable, value = rest.split("=", 1)
        os.environ[variable] = value

        # import the image
        cmd = [cli.PKGSEND, "-s", self.pkg_repo, "import", self.pkg_img_path]
        subprocess.check_call(cmd, stdout=_NULL, stderr=_NULL)

        # close/abandon the current transaction/repository
        cmd = [cli.PKGSEND, "-s", self.pkg_repo, "close"]
        subprocess.check_call(cmd, stdout=_NULL, stderr=_NULL)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing AI Publish Packages Checkpoint ===")

        self.parse_doc()

        # create the repository
        self.create_repository()

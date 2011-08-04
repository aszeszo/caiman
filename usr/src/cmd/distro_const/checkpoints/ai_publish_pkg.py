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

""" ai_publish_pkg - Publish the package image area into an pkg(5) repository
"""
import platform
import urlparse

from solaris_install import DC_LABEL, DC_PERS_LABEL, CalledProcessError, \
    Popen, run
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const.distro_spec import Distro
from solaris_install.engine import InstallEngine

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()


class AIPublishPackages(Checkpoint):
    """ class to publish the package image area into a repository
    """

    SVC_NAME_ATTR = "com.oracle.install.service_name"
    DEFAULT_ARG = {"pkg_name": None, "pkg_repo": None, "prefix": None}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(AIPublishPackages, self).__init__(name)

        self.pkg_name = arg.get("pkg_name")
        self.pkg_repo = arg.get("pkg_repo")
        self.prefix = arg.get("prefix")
        self._service_name = arg.get("service_name")

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
           
            # service-name is always stored in the persistent tree 
            self._service_name = self.dc_pers_dict["service-name"]

            distro = self.doc.volatile.get_children(class_type=Distro)
            self.distro_name = distro[0].name
        except KeyError:
            raise RuntimeError("Error retrieving a value from the DOC")

        if self.pkg_repo is None:
            self.pkg_repo = "file://%s/ai_image_repo" % self.media_dir

        if self.prefix is None:
            self.prefix = "ai-image"

        if self.pkg_name is None:
            name = "pkg://%s/install-image/solaris-auto-install@%s" % \
                (self.prefix, self.ai_pkg_version)
            self.pkg_name = name

    @property
    def service_name(self):
        return self._service_name

    def create_repository(self):
        """ class method to create the repository
        """
        self.logger.info("Creating repository")

        # Create the repository (as needed) if it's a local path (no scheme)
        # or file:/// scheme.
        scheme = urlparse.urlsplit(self.pkg_repo).scheme
        if scheme in ("file", ""):
            # Try to create the repo (it may already exist)
            cmd = [cli.PKGREPO, "create", self.pkg_repo]
            repo = run(cmd, check_result=Popen.ANY)

            if repo.returncode == 0:
                # New repo was created. Add the publisher and make it default
                cmd = [cli.PKGREPO, "-s", self.pkg_repo, "add-publisher",
                       self.prefix]
                run(cmd)
                cmd = [cli.PKGREPO, "-s", self.pkg_repo, "set",
                       "publisher/prefix=%s" % self.prefix]
                run(cmd)

        # Generate a manifest file
        cmd = [cli.PKGSEND, "generate", self.pkg_img_path]
        generate = run(cmd)
        manifest = [generate.stdout]

        arch = platform.processor()
        manifest.append("set name=variant.arch value=%s\n" % arch)
        manifest.append("set name=%s value=%s variant.arch=%s\n" %
                        (self.SVC_NAME_ATTR, self.service_name, arch))
        manifest.append("set name=pkg.fmri value=%s\n" % self.pkg_name)
        manifest = "".join(manifest)

        self.logger.info("Publishing %s", self.pkg_name)
        cmd = [cli.PKGSEND, "-s", self.pkg_repo, "publish", "-d",
               self.pkg_img_path]
        pkgsend = Popen(cmd, stdin=Popen.PIPE, stdout=Popen.PIPE,
                        stderr=Popen.PIPE)
        stdout, stderr = pkgsend.communicate(manifest)
        if stderr.strip() or pkgsend.returncode:
            pkgsend.stdout = stdout
            pkgsend.stderr = stderr
            raise CalledProcessError(pkgsend.returncode, cmd, popen=pkgsend)
        else:
            self.logger.info(stdout.strip())

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing AI Publish Packages Checkpoint ===")

        self.parse_doc()

        # create the repository
        self.create_repository()

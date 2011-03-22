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

""" test_ai_publish_pkg

 Test program for ai_publish_package

"""

import os
import os.path
import shutil
import tempfile
import unittest

import testlib

from solaris_install.distro_const.checkpoints.ai_publish_pkg \
    import AIPublishPackages
from solaris_install.engine import InstallEngine


class TestCreateRepository(unittest.TestCase):
    """ test case to test the create_repository() method of ai_publish_pkg
    """

    def setUp(self):
        InstallEngine()
        # create a dummy filesystem with some files created in the proper
        # location
        self.filelist = ["/file1", "/file2", "/file3", "/file4"]
        self.app = None

    def tearDown(self):
        # remove all the directories
        shutil.rmtree(self.app.pkg_img_path, ignore_errors=True)
        shutil.rmtree(self.app.tmp_dir, ignore_errors=True)
        shutil.rmtree(self.app.media_dir, ignore_errors=True)
        InstallEngine._instance = None

    def test_default_options(self):
        """ test case for testing the default options
        """
        self.app = AIPublishPackages("Test APP")
        self.app.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.app.tmp_dir = tempfile.mkdtemp(dir="/var/tmp", prefix="app_")
        self.app.media_dir = tempfile.mkdtemp(dir="/var/tmp", prefix="app_")

        self.app.pkg_repo = "file://%s/ai_image_repo" % self.app.media_dir
        self.app.prefix = "ai-image"
        self.app.pkg_name = "image/distro_name@5.11-0.149"
        self.app._service_name = "test-service"
        self.app.ai_pkg_version = "5.11-0.100"

        # create the repository
        self.app.create_repository()

        # verify the directory was created
        self.assert_(os.path.isdir(os.path.join(self.app.media_dir,
                                                "ai_image_repo")))

        # verify a cfg_cache file was created
        self.assert_(os.path.isfile(os.path.join(self.app.media_dir,
                                                 "ai_image_repo",
                                                 "pkg5.repository")))

    def test_arguments(self):
        """ test case for testing the arguments passed in
        to the ai-publish-pkg checkpoint
        """
        d = tempfile.mkdtemp(dir="/var/tmp", prefix="app_repo_")
        args = {}
        args["pkg_name"] = "test@5.11-0.100"
        args["pkg_repo"] = "file://%s/test_repo" % d
        args["prefix"] = "test-prefix"
        args["service_name"] = "test-service"
        self.app = AIPublishPackages("Test APP", arg=args)
        self.app.pkg_img_path = testlib.create_filesystem(*self.filelist)
        self.app.tmp_dir = tempfile.mkdtemp(dir="/var/tmp", prefix="app_")
        self.app.media_dir = tempfile.mkdtemp(dir="/var/tmp", prefix="app_")
        self.app.ai_pkg_version = "5.11-0.100"

        # create the repository
        self.app.create_repository()

        # verify the directory was created
        self.assert_(os.path.isdir(d))

        # verify a cfg_cache file was created
        self.assert_(os.path.isfile(os.path.join(d, "test_repo",
                                                 "pkg5.repository")))


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
'''
Tests auto install to a specified XML Manifest
'''

import os
import sys
import unittest

from solaris_install.auto_install import auto_install
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestAutoInstallManifest(unittest.TestCase):
    '''Tests to auto installation succeeds with -m specified manifest '''
    AI = None

    def setUp(self):
        '''
        Create a auto_install client for testing with.
        '''
        self.AI = None

    def tearDown(self):
        '''
        Clean Up
        '''
        if self.AI is not None:
            # Reset the Engine for next test
            if self.AI.engine is not None:
                reset_engine(self.AI.engine)

            # Remove install log as test has succeeded
            if os.path.isfile(self.AI.INSTALL_LOG):
                os.remove(self.AI.INSTALL_LOG)

            self.AI = None

    def test_manifest_install_auto_reboot_true(self):
        '''
        Test installation with manifest containing auto_reboot set to true
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testmanifest = os.environ['SRC'] + \
            "/cmd/auto-install/test/manifest_auto_reboot_true.xml"
        args = ["-n", "-s", "target-selection", "-m", testmanifest]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except KeyboardInterrupt:
            pass

    def test_manifest_install_auto_reboot_false(self):
        '''
        Test installation with manifest containing auto_reboot set to false
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testmanifest = os.environ['SRC'] + \
            "/cmd/auto-install/test/manifest_auto_reboot_false.xml"
        args = ["-n", "-s", "target-selection", "-m", testmanifest]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except KeyboardInterrupt:
            pass

    def test_manifest_install_auto_reboot_not_set(self):
        '''
        Test installation with manifest containing auto_reboot set to not set
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testmanifest = os.environ['SRC'] + \
            "/cmd/auto-install/test/manifest_auto_reboot_not_set.xml"
        args = ["-n", "-s", "target-selection", "-m", testmanifest]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except KeyboardInterrupt:
            pass

    def test_manifest_auto_reboot_invalid(self):
        '''
        Test installation with a manifest that fails to parse.
        Achieved by setting auto_reboot to an invalid value
        exitval should be set to AI_EXIT_FAILIRE
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testmanifest = os.environ['SRC'] + \
            "/cmd/auto-install/test/manifest_auto_reboot_invalid.xml"
        args = ["-n", "-s", "target-selection", "-m", testmanifest]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, None)
            self.assertEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except:
            raise

if __name__ == '__main__':
    unittest.main()

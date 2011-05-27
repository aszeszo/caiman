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
Tests auto install with script which derives the manifest to be used
'''

import os
import unittest

from solaris_install.auto_install import auto_install
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestAutoInstallScript(unittest.TestCase):
    '''Tests to auto installation succeeds with -m specified derived script '''

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

    def test_shell_script(self):
        '''
        Test installation with derived manifest shell script
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testscript = os.environ['SRC'] +  \
            "/cmd/auto-install/checkpoints/test/test_shell_script.sh"
        args = ["-n", "-s", "target-discovery", "-m", testscript]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except KeyboardInterrupt:
            pass

    def test_python_script(self):
        '''
        Test installation with derived manifest python script
        '''
        # To run tests bldenv script will have been run, thus we can assume
        # that $SRC environment variable will be set.
        testscript = os.environ['SRC'] +  \
            "/cmd/auto-install/checkpoints/test/test_python_script.py"
        args = ["-n", "-s", "target-discovery", "-m", testscript]

        try:
            self.AI = auto_install.AutoInstall(args)
            self.assertNotEqual(self.AI, None)
            self.AI.perform_autoinstall()
            self.assertNotEqual(self.AI.exitval, self.AI.AI_EXIT_FAILURE)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    unittest.main()

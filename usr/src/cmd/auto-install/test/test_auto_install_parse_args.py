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
Tests to ensure argument parsing errors are printed

All these tests should throw a parsing error. AutoInstall instance will not
be created and thus an InstallEngine instance is also not created.
'''

import os
import unittest

from solaris_install.auto_install import auto_install


class TestAutoInstallParseArgs(unittest.TestCase):
    '''Tests to ensure errors are reported for incorrect command line args '''

    AI = None

    def setUp(self):
        '''
        Nothing to really set up, so just pass
        '''
        self.AI = None

    def tearDown(self):
        '''
        As nothing was specifically set up, there's nothing to tear down.
        '''
        if self.AI is not None:
            # Reset the Engine for next test
            if self.AI.engine is not None:
                reset_engine(self.AI.engine)

            # Remove install log as test has succeeded
            if os.path.isfile(self.AI.INSTALL_LOG):
                os.remove(self.AI.INSTALL_LOG)

    def test_no_disk_manifest(self):
        '''
        Test if no disk or manifest is specified fail
        '''
        args = ["-n"]
        try:
            self.AI = auto_install.AutoInstall(args)
        except:
            pass

        self.assertEqual(self.AI, None)

    def test_break_before_after_ti(self):
        '''
        Test that both break before and after ti are not specified
        '''
        args = ["-n", "-m", "testmanifest", "-i", "-I"]
        AI = None
        try:
            AI = auto_install.AutoInstall(args)
        except:
            pass

        self.assertEqual(AI, None)

    def test_invalid_argument(self):
        '''
        Test passing of unknown/invalid argument
        '''
        args = ["-n", "-x"]
        try:
            self.AI = auto_install.AutoInstall(args)
        except:
            pass

        self.assertEqual(self.AI, None)

    def test_z_and_Z(self):
        '''
        Test passing -z and -Z options independently should fail
        '''
        args = ["-m", "testmanifest", "-z", "zone1"]
        try:
            self.AI = auto_install.AutoInstall(args)
        except:
            pass

        self.assertEqual(self.AI, None)

        args = ["-m", "testmanifest", "-Z", "foo/bar/dataset"]
        try:
            self.AI = auto_install.AutoInstall(args)
        except:
            pass

        self.assertEqual(self.AI, None)


if __name__ == '__main__':
    unittest.main()

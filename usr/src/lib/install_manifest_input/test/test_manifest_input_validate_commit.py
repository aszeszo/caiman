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
'''
Module to test Manifest Input Module validate and commit functionality.
'''

import os
import unittest

import solaris_install.manifest_input as milib

from solaris_install.manifest_input.mim import ManifestInput

# Eventually bring names into convention.
#pylint: disable-msg=C0103


class TestMIMValidateCommitCommon(unittest.TestCase):
    '''
    Tests for Manifest Input Module Validate and Commit functionality.
    '''

    ROOT = os.environ["ROOT"]
    BASE_MANIFEST = ROOT + "/usr/share/auto_install/manifest/ai_manifest.xml"
    SCHEMA = ROOT + "/usr/share/install/ai.dtd"
    AIM_MANIFEST_FILE = "/tmp/mim_test.xml"
    IN_XML_FILE = "/tmp/test_main.xml"

    OVERLAY = True

    def setUp(self):
        '''
        Set the file for the Manifest Input Module to initialize from.
        '''
        os.environ["AIM_MANIFEST"] = self.AIM_MANIFEST_FILE

    def tearDown(self):
        '''
        Remove any files created during tests.
        '''
        if os.path.exists(self.AIM_MANIFEST_FILE):
            os.unlink(self.AIM_MANIFEST_FILE)
        if os.path.exists(self.IN_XML_FILE):
            os.unlink(self.IN_XML_FILE)

    def create_small_xml(self):
        '''
        Create a small XML file which doesn't match the AI DTD.
        '''
        with open(self.IN_XML_FILE, "w") as in_xml:
            in_xml.write('<auto_install/>\n')

    def validate(self, validate_this):
        '''
        Load and perform validation on file given as input.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(validate_this, not self.OVERLAY)
        mim.validate()


class TestValidate1(TestMIMValidateCommitCommon):
    '''
    Verify that a bogus file gives an error on validation.
    '''

    def setUp(self):
        '''
        Create a small XML file which doesn't match the AI DTD.
        '''
        TestMIMValidateCommitCommon.setUp(self)
        self.create_small_xml()

    def test_validate_1(self):
        '''
        Verify that our tiny bogus XML file does not validate.
        '''
        self.assertRaises(milib.MimDTDInvalid, self.validate,
                          self.IN_XML_FILE)


class TestValidate2(TestMIMValidateCommitCommon):
    '''
    Verify that a bogus file gives an error on validation.
    '''

    def setUp(self):
        '''
        Set up environment for validation.
        '''
        TestMIMValidateCommitCommon.setUp(self)

    def test_validate_2(self):
        '''
        Load a manifest and validate it.
        '''
        self.validate(self.BASE_MANIFEST)


class TestCommit1(TestMIMValidateCommitCommon):
    '''
    Verify commit functionality
    '''

    def setUp(self):
        '''
        Prepare so that mim module init doesn't find a file to load.
        '''
        TestMIMValidateCommitCommon.setUp(self)
        if os.path.exists(self.AIM_MANIFEST_FILE):
            os.unlink(self.AIM_MANIFEST_FILE)

    def test_commit_1(self):
        '''
        Test proper handling of an empty tree.
        '''
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        self.assertRaises(milib.MimEmptyTreeError, mim.commit)

    def test_commit_2(self):
        '''
        Test that validation takes place when requested.
        '''
        self.create_small_xml()
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.IN_XML_FILE, not self.OVERLAY)
        self.assertRaises(milib.MimDTDInvalid, mim.commit)

    def test_commit_3(self):
        '''
        Test that file gets written without validation when requested.
        '''
        self.create_small_xml()
        mim = ManifestInput(self.AIM_MANIFEST_FILE, self.SCHEMA)
        mim.load(self.IN_XML_FILE, not self.OVERLAY)
        mim.commit(validate=False)

if __name__ == "__main__":
    unittest.main()

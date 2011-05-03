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
"""
test_target_manifest - very simple test case used to test target sections of AI
manifests.

NOTE:  If you want to change which XML file is tested, simply update the
MANIFEST variable
"""
import os.path
import unittest

import solaris_install.target

from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser
from solaris_install.data_object import ParsingError
from solaris_install.data_object.cache import DataObjectCache

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST = "%s/test_target_manifest.xml" % TEST_DIR
INVALID_MANIFEST = "%s/test_invalid_manifest.xml" % TEST_DIR


class TestTargetManfiest(unittest.TestCase):
    def setUp(self):
        self.doc = DataObjectCache()

    def tearDown(self):
        self.doc = None

    def test_xml(self):
        try:
            mp = ManifestParser("manifest-parser", MANIFEST,
                                validate_from_docinfo=False)
        except ManifestError, err:
            self.fail(str(err))

        # test to make sure the DOC classes parse the manifest correctly
        try:
            mp.parse(doc=self.doc)
        except ManifestError, err:
            self.fail(str(err))

    def test_invalid_disk_xml(self):
        try:
            mp = ManifestParser("manifest-parser", INVALID_MANIFEST,
                                validate_from_docinfo=False)
        except ManifestError, err:
            self.fail(str(err))

        # test to make sure the DOC classes fail to parse with a ManifestError
        self.assertRaises(ManifestError, mp.parse, doc=self.doc)

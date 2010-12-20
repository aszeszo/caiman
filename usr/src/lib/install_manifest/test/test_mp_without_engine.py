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

'''ManifestParser tests without InstallEngine'''


import logging
import unittest

from lxml import etree

import common
from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser
from solaris_install.data_object import ParsingError
from solaris_install.data_object.cache import DataObjectCache

####################################################################
# importing these classes causes them to be registered with the DOC
####################################################################
# pylint: disable-msg=W0614
from solaris_install.distro_const.configuration import *
from solaris_install.distro_const.distro_spec import *
from solaris_install.distro_const.execution_checkpoint import *
from solaris_install.target.target_spec import *
from solaris_install.transfer.info import *


class ManifestParserWithoutEngine(unittest.TestCase):
    '''ManifestParser tests without InstallEngine'''

    def setUp(self):
        '''instantiate the DOC'''
        self.doc = DataObjectCache()

    def tearDown(self):
        '''Clear the DOC'''
        self.doc = None


    def test_mp_no_engine_no_doc(self):
        '''
            test_mp_no_engine_no_doc - parse standard manifest without importing to DOC
        '''
        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                validate_from_docinfo=True)
        except ManifestError, err:
            self.fail(str(err))

        try:
            mp_cp.parse()
        except ManifestError, err:
            self.fail(str(err))


    def test_mp_no_engine_doc(self):
        '''
            test_mp_no_engine_doc - parse standard manifest and import to DOC
        '''
        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                validate_from_docinfo=True)
        except ManifestError, err:
            self.fail(str(err))

        try:
            mp_cp.parse(doc=self.doc)
        except ManifestError, err:
            self.fail(str(err))

        # Check some expected values from the cache
        distro_list = self.doc.get_descendants(class_type=Distro)
        self.assertTrue(len(distro_list) == 1)
        self.assertTrue(distro_list[0].name == "OpenSolaris_X86.iso")

    def test_mp_no_engine_dtd_error(self):
        '''
            test_mp_no_engine_dtd_error - DTDParseError raised if DTD contains invalid syntax
        '''

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                dtd_file=common.DTD_INVALID)
        except ManifestError, err:
            self.fail(str(err))

        try:
            mp_cp.parse(doc=self.doc)
        except ManifestError, err:
            # Ensure exception wrapped inside ManifestError is a DTDParseError
            self.assertTrue(isinstance(err.orig_exception, etree.DTDParseError))
            # Check the string representation while we're at it
            self.assertTrue(str(err).count("DTDParseError") > 0)
        else:
            self.fail("ManifestError should have been raised")


    def test_mp_no_engine_parse_error(self):
        '''
            test_mp_no_engine_parse_error - ParsingError raised when import to DOC fails
        '''

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_PARSE_ERROR,
                validate_from_docinfo=False)
        except ManifestError, err:
            self.fail(str(err))

        try:
            mp_cp.parse(doc=self.doc)
        except ManifestError, err:
            # Ensure exception wrapped inside ManifestError is a ParsingError
            self.assertTrue(isinstance(err.orig_exception, ParsingError))
            # Check the string representation while we're at it
            self.assertTrue(str(err).count("ParsingError") > 0)
        else:
            self.fail("ManifestError should have been raised")

if __name__ == '__main__':
    unittest.main()

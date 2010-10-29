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

'''ManifestParser tests for _load_manifest method'''


import logging
import unittest

from lxml import etree

import common
from solaris_install.logger import InstallLogger
from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser


class ManifestParserLoadManifest(unittest.TestCase):
    '''ManifestParser tests for _load_manifest method'''

    def setUp(self):
        '''Set up logging'''
        logging.setLoggerClass(InstallLogger)


    def test_mp_load_manifest_valid(self):
        '''
            test_mp_load_manifest_valid - load and validate standard manifest
        '''

        validate_from_docinfo = True
        load_defaults = False
        call_xinclude = False
        path = "/dc/distro"
        attribute = "http_proxy"
        attribute_value = "http://example.com"

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                validate_from_docinfo=validate_from_docinfo,
                load_defaults=load_defaults,
                call_xinclude=call_xinclude)
        except ManifestError, err:
            self.fail(str(err))

        try:
            tree = mp_cp._load_manifest(dtd_validation=validate_from_docinfo,
                attribute_defaults=load_defaults)
        except ManifestError, err:
            self.fail(str(err))

        # confirm some expected value from the XML tree
        elements = tree.xpath(path)
        self.assertEqual(len(elements), 1)
        self.assertTrue(elements[0].attrib.has_key(attribute))
        self.assertEqual(elements[0].get(attribute), attribute_value)


    def test_mp_load_manifest_defaults(self):
        '''
            test_mp_load_manifest_defaults - load a standard manifest with attribute defaults
        '''

        validate_from_docinfo = False
        load_defaults = True
        call_xinclude = False

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                validate_from_docinfo=validate_from_docinfo,
                load_defaults=load_defaults,
                call_xinclude=call_xinclude)
        except ManifestError, err:
            self.fail(str(err))

        try:
            tree = mp_cp._load_manifest(dtd_validation=validate_from_docinfo,
                attribute_defaults=load_defaults)
        except ManifestError, err:
            self.fail(str(err))

        # confirm some expected value from the XML tree
        # (this needs to wait until some more DataObject classes are written)


    def test_mp_load_manifest_xinclude(self):
        '''
            test_mp_load_manifest_xinclude - load a manifest with XInclude statements
        '''

        validate_from_docinfo = False
        load_defaults = False
        call_xinclude = True
        path = "/dc/distro/target/target_device/swap/zvol"
        attribute = "name"
        attribute_value = "swap"

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_XINCLUDE,
                validate_from_docinfo=validate_from_docinfo,
                load_defaults=load_defaults,
                call_xinclude=call_xinclude)
        except ManifestError, err:
            self.fail(str(err))

        try:
            tree = mp_cp._load_manifest(dtd_validation=validate_from_docinfo,
                attribute_defaults=load_defaults)
        except ManifestError, err:
            self.fail(str(err))

        # confirm some expected value from the XInclude'd portion of the XML tree
        elements = tree.xpath(path)
        self.assertEqual(len(elements), 1)
        self.assertTrue(elements[0].attrib.has_key(attribute))
        self.assertEqual(elements[0].get(attribute), attribute_value)


    def test_mp_load_manifest_syntax(self):
        '''
            test_mp_load_manifest_syntax - ensure XMLSyntaxError raised for bad manifest
        '''

        validate_from_docinfo = False
        load_defaults = False
        call_xinclude = False

        try:
            mp_cp = ManifestParser("manifest-parser",
                common.MANIFEST_SYNTAX_ERROR,
                validate_from_docinfo=validate_from_docinfo,
                load_defaults=load_defaults,
                call_xinclude=call_xinclude)
        except ManifestError, err:
            self.fail(str(err))

        try:
            tree = mp_cp._load_manifest(dtd_validation=validate_from_docinfo,
                attribute_defaults=load_defaults)
        except ManifestError, err:
            # confirm the reason for faiing was an XMLSyntaxError
            self.assertTrue(isinstance(err.orig_exception, etree.XMLSyntaxError))
        else:
            self.fail("_load_manifest should have failed.")


if __name__ == '__main__':
    unittest.main()

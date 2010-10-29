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

'''ManifestWriter tests without InstallEngine'''

import logging
import unittest

import common
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser
from solaris_install.manifest.writer import ManifestWriter

####################################################################
# importing these classes causes them to be registered with the DOC
####################################################################
# pylint: disable-msg=W0614
#from solaris_install.distro_const.configuration import *
#from solaris_install.distro_const.distro_spec import *
#from solaris_install.distro_const.execution_checkpoint import *
from solaris_install.target.target_spec import *
#from solaris_install.transfer.transfer_info import *


class ManifestParserWithoutEngine(unittest.TestCase):
    '''ManifestWriter tests without InstallEngine'''

    def setUp(self):
        '''instantiate the Engine so that the DOC is created'''
        self.doc = DataObjectCache()

    def tearDown(self):
        '''Force all content of the DOC to be cleared.'''
        self.doc = None


    def test_mw_no_engine_empty_doc(self):
        '''
            test_mw_no_engine_empty_doc - write manifest from empty DOC
        '''

        try:
            manifest_writer = ManifestWriter("manifest-writer",
                common.MANIFEST_OUT_OK)
            manifest_writer.write(self.doc)
        except ManifestError, err:
            self.fail(str(err))

        # Confirm the output manifest looks as expected
        self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
            0, '<root/>') == True)


    ### COMMENTED OUT UNTIL DC code is pushed
    #def test_mw_no_engine_dc_simple(self):
    #    '''
    #        test_mw_no_engine_dc_simple - read in and write out a standard manifest
    #    '''

    #    try:
    #        manifest_parser = ManifestParser("manifest-parser",
    #            common.MANIFEST_DC,
    #            validate_from_docinfo=True)
    #        manifest_parser.parse(doc=self.doc)
    #        manifest_writer = ManifestWriter("manifest-writer",
    #            common.MANIFEST_OUT_OK)
    #        manifest_writer.write(self.doc)
    #    except ManifestError, err:
    #        self.fail(str(err))

    #    # Confirm the output manifest looks as expected
    #    self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
    #        0, '<root>') == True)
    #    self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
    #        -1, '</root>') == True)


    def test_mw_no_engine_with_xslt(self):
        '''
            test_mw_no_engine_with_xslt - read a manifest, then transform it and write it out
        '''

        try:
            manifest_parser = ManifestParser("manifest-parser",
                common.MANIFEST_DC,
                validate_from_docinfo=True)
            manifest_parser.parse(doc=self.doc)

            # We cannot test validate_from_docinfo=True on the output
            # until the to_xml() methods of the relevant classes in
            # other modules return XML that conforms to the schema

            manifest_writer = ManifestWriter("manifest-writer",
                common.MANIFEST_OUT_OK,
                xslt_file=common.XSLT_DOC_TO_DC,
                validate_from_docinfo=False)
            manifest_writer.write(self.doc)
        except ManifestError, err:
            self.fail(str(err))

        # Confirm the output manifest looks as expected
        self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
            1, '<dc>') == True)
        self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
            -1, '</dc>') == True)


if __name__ == '__main__':
    unittest.main()

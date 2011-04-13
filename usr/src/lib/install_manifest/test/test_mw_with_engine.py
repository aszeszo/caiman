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

'''ManifestWriter tests using InstallEngine'''


import logging
import os.path
import unittest

import common
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import reset_engine, \
    get_new_engine_instance
from solaris_install.manifest import ManifestError

####################################################################
# importing these classes causes them to be registered with the DOC
####################################################################
# pylint: disable-msg=W0614
from solaris_install.distro_const.configuration import *
from solaris_install.distro_const.distro_spec import *
from solaris_install.distro_const.execution_checkpoint import *
from solaris_install.target import Target
from solaris_install.transfer.info import *


class ManifestParserWithEngine(unittest.TestCase):
    '''ManifestWriter tests using InstallEngine'''

    def setUp(self):
        '''instantiate the Engine so that the DOC is created'''
        self.engine = get_new_engine_instance()

    def tearDown(self):
        '''Force all content of the DOC to be cleared.'''
        reset_engine()


    def test_mw_engine_simple(self):
        '''
            test_mw_engine_simple - read in and then write out a standard manifest
        '''
        my_args = [common.MANIFEST_DC]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = True
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestParser checkpoint failed")

        my_args = [common.MANIFEST_OUT_OK]
        my_kwargs = {}
        my_kwargs["xslt_file"] = common.XSLT_DOC_TO_DC
        my_kwargs["validate_from_docinfo"] = False
        my_kwargs["dtd_file"] = None

        self.engine.register_checkpoint("manifest_writer",
            "solaris_install/manifest/writer",
            "ManifestWriter",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestWriter checkpoint failed")

        # Confirm the output manifest looks as expected
        self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
            1, '<dc>') == True)
        self.assertTrue(common.file_line_matches(common.MANIFEST_OUT_OK,
            -1, '</dc>') == True)


    def test_mw_engine_invalid_file(self):
        '''
            test_mw_engine_invalid_file - try to write to file in non-existent dir
        '''

        # Repeat of test_mw_with_engine_simple, but change output file
        # and ensure test fails
        my_args = [common.MANIFEST_DC]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = True
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestParser checkpoint failed")

        my_args = [common.MANIFEST_OUT_NON_EXISTENT]
        my_kwargs = {}
        my_kwargs["xslt_file"] = common.XSLT_DOC_TO_DC
        my_kwargs["validate_from_docinfo"] = False
        my_kwargs["dtd_file"] = None

        self.engine.register_checkpoint("manifest_writer",
            "solaris_install/manifest/writer",
            "ManifestWriter",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_FAILED,
            "ManifestWriter checkpoint should have failed")

        # Confirm the output manifest wasn't created
        self.assertTrue(os.path.exists(common.MANIFEST_OUT_NON_EXISTENT)
            == False)


    def test_mw_engine_nonexistent_xslt(self):
        '''
            test_mw_engine_nonexistent_xslt - try to transform using non-existing XSLT file
        '''
        # Repeat of test_mw_with_engine_simple, but change xslt file
        # and ensure test fails
        my_args = [common.MANIFEST_DC]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = True
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestParser checkpoint failed")

        my_args = [common.MANIFEST_OUT_OK]
        my_kwargs = {}
        my_kwargs["xslt_file"] = common.XSLT_NON_EXISTENT
        my_kwargs["validate_from_docinfo"] = False
        my_kwargs["dtd_file"] = None

        self.engine.register_checkpoint("manifest_writer",
            "solaris_install/manifest/writer",
            "ManifestWriter",
            args=my_args,
            kwargs=my_kwargs)

        try:
            status = self.engine.execute_checkpoints()[0]
        except ManifestError:
            pass
        else:
            self.assertEqual(status, InstallEngine.CP_INIT_FAILED)

    def test_mw_engine_invalid_xslt(self):
        '''
            test_mw_engine_invalid_xslt - use XSLT file with invalid syntax
        '''
        my_args = [common.MANIFEST_DC]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = True
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestParser checkpoint failed")

        my_args = [common.MANIFEST_OUT_OK]
        my_kwargs = {}
        my_kwargs["xslt_file"] = common.XSLT_INVALID
        my_kwargs["validate_from_docinfo"] = False
        my_kwargs["dtd_file"] = None

        self.engine.register_checkpoint("manifest_writer",
            "solaris_install/manifest/writer",
            "ManifestWriter",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_FAILED,
            "ManifestWriter checkpoint should have failed")


if __name__ == '__main__':
    unittest.main()

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

'''ManifestWriter dry_run tests'''


import logging
import unittest

import common
from solaris_install.configuration.configuration import *
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import reset_engine, \
    get_new_engine_instance
from solaris_install.manifest import ManifestError
from solaris_install.manifest.writer import ManifestWriter

####################################################################
# importing these classes causes them to be registered with the DOC
####################################################################
# pylint: disable-msg=W0614
from solaris_install.distro_const.distro_spec import *
from solaris_install.distro_const.execution_checkpoint import *
from solaris_install.target import Target
from solaris_install.transfer.info import *

class ManifestParserWithEngine(unittest.TestCase):
    '''ManifestWriter dry_run tests'''

    def setUp(self):
        '''instantiate the Engine so that the DOC is created'''
        self.engine = get_new_engine_instance()

    def tearDown(self):
        '''Force all content of the DOC to be cleared.'''
        reset_engine()


    def test_mw_dry_run(self):
        '''
            test_mw_dry_run - confirm output file is changed if dry_run=True
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

        if status != InstallEngine.EXEC_SUCCESS:
            self.fail("ManifestParser checkpoint failed")

        # By-pass the engine for running ManifestWriter, so we
        # can verify the object's attributes

        try:
            mw_cp = ManifestWriter("manifest-writer", common.MANIFEST_OUT_OK)
            mw_cp.execute()
        except ManifestError, err:
            self.fail(str(err))

        self.assertTrue(mw_cp._manifest == common.MANIFEST_OUT_OK)

        # Run it again so we can be sure outfile already exists,
        # and therefore must be changed
        try:
            mw_cp.execute(dry_run=True)
        except ManifestError, err:
            self.fail(str(err))

        self.assertTrue(mw_cp._manifest != common.MANIFEST_OUT_OK)



if __name__ == '__main__':
    unittest.main()

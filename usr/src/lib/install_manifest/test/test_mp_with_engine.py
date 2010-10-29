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

'''ManifestParser Tests using InstallEngine'''


import logging
import unittest

import common
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import reset_engine, \
    get_new_engine_instance

####################################################################
# importing these classes causes them to be registered with the DOC
####################################################################
# pylint: disable-msg=W0614
#from solaris_install.distro_const.configuration import *
#from solaris_install.distro_const.distro_spec import *
#from solaris_install.distro_const.execution_checkpoint import *
from solaris_install.target.target_spec import *
#from solaris_install.transfer.transfer_info import *


class ManifestParserWithEngine(unittest.TestCase):
    '''ManifestParser Tests using InstallEngine'''

    def setUp(self):
        '''instantiate the Engine so that the DOC is created'''
        self.engine = get_new_engine_instance()

    def tearDown(self):
        '''Force all content of the DOC to be cleared.'''
        reset_engine()


    ### COMMENTED OUT UNTIL DC code is pushed
    #def test_mp_engine_simple(self):
    #    '''
    #        test_mp_engine_simple - import and validate a standard manifest
    #    '''
    #    my_args = [common.MANIFEST_DC]
    #    my_kwargs = {}
    #    my_kwargs["validate_from_docinfo"] = True
    #    my_kwargs["load_defaults"] = False

    #    self.engine.register_checkpoint("manifest_parser",
    #        "solaris_install/manifest/parser",
    #        "ManifestParser",
    #        args=my_args,
    #        kwargs=my_kwargs)

    #    status = self.engine.execute_checkpoints()[0]

    #    self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
    #        "ManifestParser checkpoint failed [%s]" % status)

    #    # Check some expected value from the cache
    #    distro_list = \
    #        self.engine.data_object_cache.get_descendants(class_type=Distro)
    #    self.assertEqual(len(distro_list), 1)
    #    self.assertTrue(distro_list[0].name == "OpenSolaris_X86.iso")

    def test_mp_engine_validate(self):
        '''
            test_mp_engine_validate - use validate_from_docinfo=None to validate if DTD specified
        '''
        my_args = [common.MANIFEST_DC_DTD_PATH]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = None
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_SUCCESS,
            "ManifestParser checkpoint failed")


    def test_mp_engine_doesnt_validate(self):
        '''
            test_mp_engine_doesnt_validate - execution fails if validation requested and fails
        '''
        my_args = [common.MANIFEST_INVALID]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = None
        my_kwargs["load_defaults"] = False

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_FAILED,
            "ManifestParser checkpoint should have failed")


    def test_mp_engine_no_dtd_ref(self):
        '''
            test_mp_engine_no_dtd_ref - confirm error if validate_...=True and DTD not specified
        '''
        my_args = [common.MANIFEST_NO_DTD_REF]
        my_kwargs = {}
        my_kwargs["validate_from_docinfo"] = True

        self.engine.register_checkpoint("manifest_parser",
            "solaris_install/manifest/parser",
            "ManifestParser",
            args=my_args,
            kwargs=my_kwargs)

        status = self.engine.execute_checkpoints()[0]

        self.assertEqual(status, InstallEngine.EXEC_FAILED,
            "ManifestParser checkpoint should have failed")


if __name__ == '__main__':
    unittest.main()

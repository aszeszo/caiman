#!/usr/bin/python2.6
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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''

import os
import shutil
import tempfile
import unittest

import osol_install.auto_install.service as service
import osol_install.auto_install.service_config as config
import osol_install.auto_install.delete_service as delete_service


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.'''

    @classmethod
    def setUpClass(cls):
        '''Class-level set up'''
        tempdirname = tempfile.mkdtemp(dir="/tmp")
        cls.config_svcdirpath = config.AI_SERVICE_DIR_PATH
        config.AI_SERVICE_DIR_PATH = tempdirname

        # create service
        cls.imagedir = tempfile.mkdtemp(dir="/tmp")
        props = {config.PROP_SERVICE_NAME: 'mysvc',
                 config.PROP_STATUS: 'off',
                 config.PROP_TXT_RECORD: 'aiwebserver=myserver:5555',
		 config.PROP_IMAGE_PATH: cls.imagedir}
        config.create_service_props('mysvc', props)
        cls.myservice = service.AIService('mysvc')

    @classmethod
    def tearDownClass(cls):
        '''Class-level teardown'''
        if os.path.exists(config.AI_SERVICE_DIR_PATH):
            shutil.rmtree(config.AI_SERVICE_DIR_PATH)
        config.AI_SERVICE_DIR_PATH = cls.config_svcdirpath
        if os.path.exists(cls.imagedir):
            shutil.rmtree(cls.imagedir)

    def test_parse_valid_options(self):
        '''Ensure valid args/options pass'''
        myargs = ["mysvc", "-r", "-y"]
        delete_service.parse_options(myargs)

    def test_parse_no_service_name(self):
        '''Ensure service name is required'''
        myargs = []
        self.assertRaises(SystemExit, delete_service.parse_options, myargs)

    def test_parse_too_many_args(self):
        '''Ensure too many args caught'''
        myargs = ["mysvc", "yoursvc"]
        self.assertRaises(SystemExit, delete_service.parse_options, myargs)

    def test_parse_nosuch_service(self):
        '''Ensure no such service caught'''
        myargs = ["nosuchservice"]
        self.assertRaises(SystemExit, delete_service.parse_options, myargs)
        myargs = ["servicewithslash/"]
        self.assertRaises(SystemExit, delete_service.parse_options, myargs)


if __name__ == '__main__':
    unittest.main()

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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''

import unittest
import os
import shutil
import tempfile

import osol_install.auto_install.service as service
import osol_install.auto_install.service_config as config


class TestService(unittest.TestCase):
    '''Tests for service'''

    @classmethod
    def setUpClass(cls):
        '''unit test set up'''
        tempdirname = tempfile.mkdtemp(dir="/tmp")
        cls.config_svcdirpath = config.AI_SERVICE_DIR_PATH
        config.AI_SERVICE_DIR_PATH = tempdirname

    @classmethod
    def tearDownClass(cls):
        '''Class-level variable teardown'''
        if os.path.exists(config.AI_SERVICE_DIR_PATH):
            shutil.rmtree(config.AI_SERVICE_DIR_PATH)
        config.AI_SERVICE_DIR_PATH = cls.config_svcdirpath

    def setUp(self):
        '''unit test set up'''
        self.imagedir = tempfile.mkdtemp(dir="/tmp")

    def tearDown(self):
        '''unit test tear down'''
        if os.path.exists(self.imagedir):
            shutil.rmtree(self.imagedir)

    def test_update_wanboot_imagepath(self):
        '''verify update_wanboot_imagepath updates imagepath correctly'''

        # create original wanboot.conf file
        wanboot_txt = (
            "root_server=http://10.134.125.136:5555/cgi-bin/wanboot-cgi\n"
            "root_file=%(path)s/boot/platform/sun4v/boot_archive\n"
            "boot_file=%(path)s/platform/sun4v/wanboot\n"
            "system_conf=system.conf\n"
            "encryption_type=\n"
            "signature_type=\n"
            "server_authentication=no\n"
            "client_authentication=no=\n") % {'path': self.imagedir}

        wanbootconf = os.path.join(self.imagedir, service.WANBOOTCONF)
        with open(wanbootconf, 'w') as wfp:
            wfp.write(wanboot_txt)

        # create service
        props = {config.PROP_SERVICE_NAME: 'mysvc',
                 config.PROP_IMAGE_PATH: self.imagedir}
        config.set_service_props('mysvc', props)
        myservice = service.AIService('mysvc')

        # Update path in wanboot file, read file back in, and
        # ensure file is updated properly.
        newpath = '/export/mydir/newpath'
        expected_text = wanboot_txt.replace(self.imagedir, newpath)
        myservice.update_wanboot_imagepath(self.imagedir, newpath)
        with open(wanbootconf, 'r') as wanboot_file:
            new_wanboot_txt = wanboot_file.read()
        self.assertEqual(new_wanboot_txt, expected_text)


if __name__ == '__main__':
    unittest.main()

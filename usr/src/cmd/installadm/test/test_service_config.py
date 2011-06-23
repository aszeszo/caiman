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
import osol_install.auto_install.service_config as config


class ServiceConfig(unittest.TestCase):
    '''Tests for service_config''' 

    @classmethod
    def setUpClass(cls):
        '''unit test set up'''
        tempdirname = tempfile.mkdtemp(dir="/tmp")
        cls.config_svcdirpath = config.AI_SERVICE_DIR_PATH
        config.AI_SERVICE_DIR_PATH = tempdirname

    @classmethod
    def tearDownClass(cls):
        '''Class-level variable teardown'''
        config.AI_SERVICE_DIR_PATH = cls.config_svcdirpath

    def tearDown(self):
        '''unit test tear down'''
        if os.path.exists(config.AI_SERVICE_DIR_PATH):
            shutil.rmtree(config.AI_SERVICE_DIR_PATH)

    def test_get_configfile_path(self):
        '''verify config file path '''
        path = config._get_configfile_path('myservice')
        expected = os.path.join(config.AI_SERVICE_DIR_PATH, 'myservice',
                                config.CFGFILE)
        self.assertEqual(path, expected)

    def test_write_and_read_configfile(self):
        '''verify write and read config file'''
        svc = 'mysvc'
        props = {'french': 'fries', 'banana': 'split'}
        config._write_service_config(svc, props)
        cfg = config._read_config_file(svc)
        self.assertTrue(cfg)
        self.assertTrue(config.SERVICE in cfg.sections())
        data = dict(cfg.items(config.SERVICE))
        self.assertEqual(data['version'], config.CURRENT_VERSION)
        self.assertEqual(data['french'], 'fries')
        self.assertEqual(data['banana'], 'split')

    def test_get_service_props(self):
        '''test get_service_props'''
        svc = 'mysvc'
        props = {'dark': 'chocolate', 'green': 'tea'}
        config._write_service_config(svc, props)
        propdict = config.get_service_props(svc)
        self.assertEqual(propdict['version'], config.CURRENT_VERSION)
        self.assertEqual(propdict['dark'], 'chocolate')
        self.assertEqual(propdict['green'], 'tea')

    def test_get_service_port(self):
        '''test get_service_port'''
        svc = 'mysvc'
        props = {config.PROP_SERVICE_NAME: svc,
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_TXT_RECORD: 'aiwebserver=ais:46502',
                 config.PROP_IMAGE_PATH: '/tmp/myimage'}
        config._write_service_config(svc, props)
        port = config.get_service_port(svc)
        self.assertEqual(port, '46502')

    def test_is_service_and_is_enabled(self):
        '''test is_service() and is_enabled()'''
        svc = 'myservice'
        props = {config.PROP_STATUS: config.STATUS_ON}
        config._write_service_config(svc, props)
        self.assertTrue(config.is_service(svc))
        self.assertTrue(config.is_enabled(svc))
        props = {config.PROP_STATUS: config.STATUS_OFF}
        config.set_service_props(svc, props)
        self.assertFalse(config.is_enabled(svc))

    def test_get_all_service_names(self):
        '''test get_all_service_names'''
        props = {'fudge': 'brownie'}
        config._write_service_config('s1', props)
        config._write_service_config('s2', props)
        config._write_service_config('s3', props)
        config._write_service_config('s4', props)
        config._write_service_config('s5', props)
        services = config.get_all_service_names()
        self.assertEqual(len(services), 5)
        self.assertTrue('s1' in services and 's2' in services and 
                        's3' in services and 's4' in services and 
                        's5' in services)

    def test_get_all_service_props(self):
        '''test get_all_service_props'''
        props = {'hot': 'fudge'}
        config._write_service_config('s1', props)
        props = {'ice': 'cream'}
        config._write_service_config('s2', props)
        props = {'apple': 'pie'}
        config._write_service_config('s3', props)
        all_props = config.get_all_service_props()
        self.assertEqual(all_props['s1'], {'version': config.CURRENT_VERSION,
                         'hot': 'fudge'})
        self.assertEqual(all_props['s2'], {'version': config.CURRENT_VERSION,
                         'ice': 'cream'}) 
        self.assertEqual(all_props['s3'], {'version': config.CURRENT_VERSION,
                         'apple': 'pie'})

    def test_verify_key_properties(self):
        '''test verify_key_properties'''
        # success cases
        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_TXT_RECORD: 'aiwebserver=ais:5555',
                 config.PROP_IMAGE_PATH: '/tmp/myimage'}
        config.verify_key_properties('s1', props)

        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_TXT_RECORD: 'aiwebserver=ais:5555',
                 config.PROP_ALIAS_OF: 'mybasesvc'}
        config.verify_key_properties('s1', props)

        # failure cases
        props = {config.PROP_SERVICE_NAME: 's1'}
        self.assertRaises(config.ServiceCfgError,
                          config.verify_key_properties, 'not_s1', props)

        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_TXT_RECORD: 'aiwebserver=ais:5555',
                 config.PROP_IMAGE_PATH: '/tmp/myimage'}
        self.assertRaises(config.ServiceCfgError,
                          config.verify_key_properties, 's1', props)

        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_IMAGE_PATH: '/tmp/myimage'}
        self.assertRaises(config.ServiceCfgError,
                          config.verify_key_properties, 's1', props)

        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_TXT_RECORD: 'aiwebserver=ais5555',
                 config.PROP_IMAGE_PATH: '/tmp/myimage'}
        self.assertRaises(config.ServiceCfgError,
                          config.verify_key_properties, 's1', props)


        props = {config.PROP_SERVICE_NAME: 's1',
                 config.PROP_STATUS: config.STATUS_ON,
                 config.PROP_TXT_RECORD: 'aiwebserver=ais:5555'}
        self.assertRaises(config.ServiceCfgError,
                          config.verify_key_properties, 's1', props)

    def test_delete_service_props(self):
        '''verify delete_service_props'''
        svc = 'mysvc'
        props = {'fudge': 'brownie'}
        config._write_service_config(svc, props)
        self.assertTrue(config.is_service(svc))
        config.delete_service_props(svc)
        self.assertFalse(config.is_service(svc))

    def test_get_aliased_services(self):
        '''test get_aliased_services'''

        props = {config.PROP_SERVICE_NAME: 'base1'}
        config._write_service_config('base1', props)
        props = {config.PROP_SERVICE_NAME: 'alias1',
                 config.PROP_ALIAS_OF: 'base1'}
        config._write_service_config('alias1', props)
        props = {config.PROP_SERVICE_NAME: 'alias2',
                 config.PROP_ALIAS_OF: 'alias1'}
        config._write_service_config('alias2', props)
        aliased = config.get_aliased_services('base1')
        self.assertTrue(aliased == ['alias1'])
        aliased = config.get_aliased_services('base1', recurse=True)
        self.assertTrue(aliased == ['alias1', 'alias2'])
        
    def test_clients(self):
        '''test clients'''

        props = {config.PROP_SERVICE_NAME: 's1'}
        config._write_service_config('s1', props)
        config.add_client_info('s1', '01AABBCCDDAABB',
                               {config.FILES: ['/tmp/foo', '/tmp/bar'],
                                config.BOOTARGS: 'console=ttya'})
        self.assertTrue(config.is_client('01AABBCCDDAABB'))
        self.assertFalse(config.is_client('01AABBCCDDAABC'))
        svc, clientdict = config.find_client('01AABBCCDDAABB')
        self.assertEqual(svc, 's1')
        self.assertEqual(clientdict[config.FILES], ['/tmp/foo', '/tmp/bar'])
        self.assertEqual(clientdict[config.BOOTARGS], 'console=ttya')

        config.add_client_info('s1', '01AAAAAAAAAAAA',
                               {config.FILES: ['/tmp/aaa', '/tmp/AAA']})
        clientdict = config.get_clients('s1')
        self.assertEqual(clientdict.keys(), ['01AABBCCDDAABB',
                                             '01AAAAAAAAAAAA'])
        self.assertEqual(clientdict['01AAAAAAAAAAAA'][config.FILES],
                         ['/tmp/aaa', '/tmp/AAA'] )

        config.remove_client_from_config('s1', '01AABBCCDDAABB')
        clientdict = config.get_clients('s1')
        self.assertTrue('01AABBCCDDAABB' not in clientdict)


if __name__ == '__main__':
    unittest.main()

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

""" test_ai_smf_service

 Test program for ai_smf_service
"""

import os
import sys
import tempfile
import unittest
from subprocess import Popen, PIPE

import osol_install.libaiscf as smf

from  osol_install.auto_install.ai_smf_service import is_pg, \
    get_pg_props, set_pg_props, get_all_pg_props


AI_SVC = 'svc:/system/install/server:default'

def add_prop_group(pg_name):
    '''
    Add a property group to the AI service
    Input:
        pg_name - An AI service property group name
    Return:
        None

    '''
    pg_name = 'AI' + pg_name
    cmdout = ''
    cmderr = ''

    cmd = ['/usr/sbin/svccfg', '-s', AI_SVC, 'addpg', pg_name, 'application']
    try:
        (cmdout, cmderr) = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
    except OSError, err:
        fail('OSError cmd: %s failed with: %s') % (cmd, err)

    if cmderr:
        if cmderr.find('already exists') >= 0:
            print('cmderr cmd: %s failed with: %s', cmd, cmderr)
            print('Ignoring error. Continuing')
        else:
            fail('cmderr cmd: %s failed with: %s') % (cmd, cmderr)

def del_prop_group(pg_name):
    '''
    Remove a property group from the AI service
    Input:
        pg_name - An AI service property group name
    Return:
        None

    '''
    pg_name = 'AI' + pg_name
    cmdout = ''
    cmderr = ''
    cmd = [ '/usr/sbin/svccfg', '-s', AI_SVC, 'delpg', pg_name ]

    try:
        (cmdout, cmderr) = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
    except OSError, err:
        fail('OSError cmd: %s failed with: %s') % (cmd, err)

    if cmderr:
        fail('cmderr cmd: %s failed with: %s') % (cmd, cmderr)

class TestAISmfService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        '''class test set up '''
        cls.pgname = os.path.basename(tempfile.mkstemp()[1])
        add_prop_group(cls.pgname)
        cls.pgname2 = os.path.basename(tempfile.mkstemp()[1])
        add_prop_group(cls.pgname2)

    @classmethod
    def tearDownClass(cls):
        '''class test tear down '''
        del_prop_group(cls.pgname)
        del_prop_group(cls.pgname2)

    def test_is_pg(self):
        ''' test ai_smf_service is_pg'''
        self.assertTrue(is_pg(self.pgname))

        # Exercise is_pg()
        pg_tst_name = '_zippy_the_pin_head'
        self.assertFalse(is_pg(pg_tst_name))

    def test_set_get_pg_props(self):
        ''' test set_pg_props, get_pg_props and get_all_pg_props'''
        props = {'hair': 'blond', 'eyes': 'hazel'}
        set_pg_props(self.pgname, props)
        props = {'teeth': 'chipped', 'nose': 'crooked'}
        set_pg_props(self.pgname2, props)

        # Exercise get_pg_props()
        ret_props = get_pg_props(self.pgname)
        self.assertTrue(ret_props['hair'] == 'blond')
        self.assertTrue(ret_props['eyes'] == 'hazel')

        prop_dict = get_all_pg_props()
        self.assertTrue(prop_dict[self.pgname]['hair'] == 'blond')
        self.assertTrue(prop_dict[self.pgname]['eyes'] == 'hazel')
        self.assertTrue(prop_dict[self.pgname2]['teeth'] == 'chipped')
        self.assertTrue(prop_dict[self.pgname2]['nose'] == 'crooked')

if __name__ == '__main__':

    unittest.main()

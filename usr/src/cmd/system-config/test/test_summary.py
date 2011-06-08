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

from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.summary import SummaryScreen
import terminalui

terminalui.init_logging("test")


class MockAll(object):
    '''Generic Mock object that 'never' raises an AttributeError'''
    
    def __getattr__(self, name):
        return self
    
    def __getitem__(self, idx):
        return self
    
    def __call__(self, *args, **kwargs):
        return self


class TestSummary(unittest.TestCase):
    
    def setUp(self):
        self.SummaryScreen__init__ = SummaryScreen.__init__
        SummaryScreen.__init__ = lambda x, y: None
        self.summary = SummaryScreen(None)
        self.summary.sysconfig = MockAll()
    
    def tearDown(self):
        SummaryScreen.__init__ = self.SummaryScreen__init__
        self.summary = None
    
    def test_get_tz_summary(self):
        '''SummaryScreen.get_tz_summary() generates "Time Zone: <timezone>" '''
        self.summary.sysconfig.system.tz_timezone = "UTC"
        
        tz_summary = self.summary.get_tz_summary()
        
        self.assertEquals("Time Zone: UTC", tz_summary)
    
    def test_get_users_no_root(self):
        '''SummaryScreen.get_users() with no root user warns
           of the lack of root user'''
        root = MockAll()
        root.password = None
        self.summary.sysconfig.users.root = root
        self.summary.sysconfig.users.user = MockAll()
        
        user_summary = self.summary.get_users()
        self.assertTrue("  Warning: No root password set" in user_summary,
                        '"Warning: No root password set" not in "%s"'
                        % user_summary)
    
    def test_get_users_no_user(self):
        '''SummaryScreen.get_users() with no primary user indicates
           lack of primary user'''
        primary = MockAll()
        primary.login_name = None
        self.summary.sysconfig.users.root = MockAll()
        self.summary.sysconfig.users.user = primary
        
        user_summary = self.summary.get_users()
        self.assertTrue("  No user account" in user_summary,
                        '"No user account" not in "%s"' % user_summary)
    
    def test_get_users_primary_user(self):
        '''SummaryScreen.get_users() with primary user
           indicates user's login'''
        primary = MockAll()
        primary.login_name = "test"
        self.summary.sysconfig.users.root = MockAll()
        self.summary.sysconfig.users.user = primary
        
        user_summary = self.summary.get_users()
        self.assertTrue("  Username: test" in user_summary,
                        '"Username: test" not in "%s"' % user_summary)

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

from solaris_install.sysconfig.network_nic_configure import NICConfigure
import terminalui
from terminalui.base_screen import UIMessage


terminalui.init_logging("test")


class MockIPField(object):
    
    def __init__(self, ip="1.2.3.4"):
        self.ip = ip
    
    def get_text(self):
        return self.ip


class TestNICConfigure(unittest.TestCase):
    '''Test NICConfigure screen'''
    
    def setUp(self):
        self.NICConfigure__init__ = NICConfigure.__init__
        NICConfigure.__init__ = lambda x, y: None
        self.nic_screen = NICConfigure(None)
    
    def tearDown(self):
        NICConfigure.__init__ = self.NICConfigure__init__
        
        self.nic_screen = None
    
    def test_validate_valid_netmask(self):
        '''NICConfigure.validate() succeeds when Netmask is valid'''
        self.nic_screen.ip_field = MockIPField()
        self.nic_screen.netmask_field = MockIPField("255.255.255.0")
        self.nic_screen.gateway_field = MockIPField()
        self.nic_screen.dns_field = MockIPField()
        self.nic_screen.domain_field = MockIPField()
        self.nic_screen.validate()
    
    def test_validate_invalid_netmask(self):
        '''NICConfigure.validate() fails when Netmask is invalid'''
        self.nic_screen.ip_field = MockIPField()
        self.nic_screen.netmask_field = MockIPField("1.2.3.4")
        self.nic_screen.gateway_field = MockIPField()
        self.nic_screen.dns_field = MockIPField()
        try:
            self.nic_screen.validate()
        except UIMessage as uimsg:
            # Can't use 'assertRaises', as we need to examine the
            # exception object's details
            self.assertEquals(uimsg.args[0],"'1.2.3.4' is not a valid netmask")
        else:
            self.fail("Expected NICConfigure.validate() to fail")

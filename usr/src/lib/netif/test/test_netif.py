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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
'''Testcase for netif interfaces

To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''
import unittest

from osol_install.libaimdns import getifaddrs
from osol_install.netif import if_indextoname, if_nameindex, if_nametoindex


# pylint: disable-msg=R0201
class TestNetif(unittest.TestCase):
    '''Class: TestNetif - tests the netif interfaces
    '''
    def test_if_interfaces(self):
        '''method to test the netif if_indextoname and if_nametoindex
        '''
        interfaces = if_nameindex()
        for inter in interfaces:
            assert interfaces[inter] == if_indextoname(inter), \
                'Unable to match interface %s' % interfaces[inter]

            assert inter == if_nametoindex(interfaces[inter]), \
                'Unable to match %d index' % inter

    def test_if_names(self):
        '''method to test the netif if_nameindex()
        '''
        interfaces = if_nameindex()
        # note: getifaddrs() skips loopback and point-to-point,
        #       therefore, test only that the getifaddrs interfaces
        #       are in the if_nameindex interfaces
        ifaddrs = getifaddrs()
        for inter in ifaddrs:
            assert inter in interfaces.values(), \
                'Unable to find %s' % inter
# pylint: enable-msg=R0201

if __name__ == '__main__':
    unittest.main()

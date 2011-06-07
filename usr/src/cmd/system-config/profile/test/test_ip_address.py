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

from solaris_install.sysconfig.profile.ip_address import IPAddress


NETMASKS = [
(32, '255.255.255.255'),
(31, '255.255.255.254'),
(30, '255.255.255.252'),
(29, '255.255.255.248'),
(28, '255.255.255.240'),
(27, '255.255.255.224'),
(26, '255.255.255.192'),
(25, '255.255.255.128'),
(24, '255.255.255.0'),
(23, '255.255.254.0'),
(22, '255.255.252.0'),
(21, '255.255.248.0'),
(20, '255.255.240.0'),
(19, '255.255.224.0'),
(18, '255.255.192.0'),
(17, '255.255.128.0'),
(16, '255.255.0.0'),
(15, '255.254.0.0'),
(14, '255.252.0.0'),
(13, '255.248.0.0'),
(12, '255.240.0.0'),
(11, '255.224.0.0'),
(10, '255.192.0.0'),
(9, '255.128.0.0'),
(8, '255.0.0.0'),
(7, '254.0.0.0'),
(6, '252.0.0.0'),
(5, '248.0.0.0'),
(4, '240.0.0.0'),
(3, '224.0.0.0'),
(2, '192.0.0.0'),
(1, '128.0.0.0'),
(0, '0.0.0.0'),
]


class TestIPAddress(unittest.TestCase):
    
    def test_get_address_none(self):
        '''IPAddress.address property with no address set returns default'''
        ip = IPAddress()
        self.assertEquals("0.0.0.0", ip.address)
    
    def test_get_address_none_w_netmask(self):
        '''IPAddress.address property with no address and netmask
           returns 0.0.0.0/24'''
        ip = IPAddress(netmask="255.255.255.0")
        self.assertEquals("0.0.0.0/24", ip.address)
    
    def test_get_address(self):
        '''IPAddress.address property with address set returns address'''
        ip = IPAddress("1.2.3.4")
        self.assertEquals("1.2.3.4", ip.address)
    
    def test_get_address_w_netmask(self):
        '''IPAddress.address property with address and netmask
           set returns correctly'''
        ip = IPAddress("1.2.3.4", netmask="255.255.255.0")
        self.assertEquals("1.2.3.4/24", ip.address)
    
    def test_convert_address(self):
        '''IPAddress.convert_address() returns correct segments'''
        segments = IPAddress.convert_address("1.0.128.255")
        self.assertEquals([1, 0, 128, 255], segments)
    
    def test_convert_good_netmask(self):
        '''IPAddress.convert_address() succeeds when checking netmask'''
        segments = IPAddress.convert_address("255.0.0.0", check_netmask=True)
        self.assertEquals([255, 0, 0, 0], segments)
    
    def test_convert_bad_length(self):
        '''IPAddress.convert_address() fails when length is incorrect'''
        self.assertRaises(ValueError, IPAddress.convert_address,
                          "1.2.3.4.5")
        self.assertRaises(ValueError, IPAddress.convert_address,
                          "1.2.3")
    
    def test_as_binary_string(self):
        '''IPAddress.as_binary_string() returns a proper binary string'''
        binary = IPAddress.as_binary_string(range(255))
        self.assertTrue("1" in binary)
        self.assertTrue("0" in binary)
        self.assertFalse(binary.strip("10"))
    
    def test_netmask_prefix(self):
        '''IPAddress.netmask_prefix() returns correct values'''
        for mask in NETMASKS:
            ip = IPAddress(netmask=mask[1])
            self.assertEquals(mask[0], ip.netmask_prefix())
    
    def test_incremental_full_ip(self):
        '''IPAddress.incremental_check() parses a full IPAddress properly'''
        segments = IPAddress.incremental_check("1.2.3.4")
        self.assertEquals([1, 2, 3, 4], segments)
    
    def test_incremental_partial_ip(self):
        '''IPAddress.incremental_check() parses a partial IPAddress properly'''
        segments = IPAddress.incremental_check("1.2.3")
        self.assertEquals([1, 2, 3], segments)
        
        segments = IPAddress.incremental_check("1")
        self.assertEquals([1], segments)
    
    def test_incremental_blank(self):
        '''IPaddress.incremental_check() parses a blank string properly'''
        segments = IPAddress.incremental_check("")
        self.assertEquals([], segments)
    
    def test_incremental_ip_too_long(self):
        '''IPAddress.incremental_check() rejects a too-long IP'''
        try:
            segments = IPAddress.incremental_check("1.2.3.4.5")
        except ValueError as err:
            # Not using 'assertRaises' as we need to examine the ValueError
            self.assertEquals("Too many octets", err.args[0])
    
    def test_incremental_non_int_segment(self):
        '''IPAddress.incremental_check() rejects non-integer values'''
        try:
            segments = IPAddress.incremental_check("1.0x2.3.4")
        except ValueError as err:
            # Not using 'assertRaises' as we need to examine the ValueError
            self.assertEquals("Only numbers and '.' (period) are allowed",
                              err.args[0])
    
    def test_incremental_segment_too_small(self):
        '''IPAddress.incremental_check() rejects negative segments'''
        try:
            segments = IPAddress.incremental_check("1.-2.3.4")
        except ValueError as err:
            # Not using 'assertRaises' as we need to examine the ValueError
            self.assertEquals("Only numbers and '.' (period) are allowed",
                              err.args[0])
    
    def test_incremental_segment_too_big(self):
        '''IPAddress.incremental_check() rejects values >255'''
        try:
            segments = IPAddress.incremental_check("1.2.3.455")
        except ValueError as err:
            # Not using 'assertRaises' as we need to examine the ValueError
            self.assertEquals("Values should be between 0 and 255",
                              err.args[0])


if __name__ == '__main__':
    unittest.main()

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

import unittest
import osol_install.auto_install.verifyXML as verifyXML


class TestCheckFunctions(unittest.TestCase):

    def test_checkIPv4_1(self):
        '''Ensure that ipv4 address is properly converted and zero padded'''
        ipv4 = verifyXML.checkIPv4('192.168.0.1')
        self.assertEqual(ipv4, '192168000001')

    def test_checkIPv4_2(self):
        '''Ensure that exception is thrown if octet in ipv4 address is > 255'''
        self.assertRaises(ValueError, verifyXML.checkIPv4, '192.256.0.1')

    def test_checkIPv4_3(self):
        '''Ensure that exception is thrown if ipv4 address has more then
        4 octets'''
        self.assertRaises(ValueError, verifyXML.checkIPv4, '192.168.2.0.1')

    def test_checkIPv4_4(self):
        '''Ensure that exception is thrown if ipv4 address has less then
        4 octets'''
        self.assertRaises(ValueError, verifyXML.checkIPv4, '192.168.1')

    def test_checkMAC_1(self):
        '''Ensure that MAC address is properly converted and padded'''
        mac = verifyXML.checkMAC('00:11:2:33:04:FF')
        self.assertEqual(mac, '0011023304ff')

    def test_checkMAC_2(self):
        '''Ensure that dash is accepted delimiter in MAC address'''
        mac = verifyXML.checkMAC('00-11-2-33-04-FF')
        self.assertEqual(mac, '0011023304ff')

    def test_checkMAC_3(self):
        '''Ensure that exception is thrown if MAC address has 7 bytes'''
        self.assertRaises(ValueError, verifyXML.checkMAC, '0:1:2:3:4:5:6')

    def test_checkArch_1(self):
        '''Ensure that correct arch passes'''
        verifyXML.checkArch('i86pc')

    def test_checkArch_2(self):
        '''Ensure exception is thrown for incorrect arch'''
        self.assertRaises(ValueError, verifyXML.checkArch, 'i386')

    def test_checkCPU_1(self):
        '''Ensure that correct CPU passes'''
        verifyXML.checkCPU('i386')

    def test_checkCPU_2(self):
        '''Ensure exception is thrown for incorrect cpu type'''
        self.assertRaises(ValueError, verifyXML.checkCPU, 'i86pc')

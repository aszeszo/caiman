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

from lxml import etree
import unittest

from solaris_install.sysconfig.profile.network_info import NetworkInfo


class TestNetworkInfo(unittest.TestCase):
    
    def test_set_type_valid(self):
        '''NetworkInfo.type = <valid value> succeeds'''
        net = NetworkInfo()
        net.type = NetworkInfo.MANUAL
        self.assertEquals(net.type, NetworkInfo.MANUAL)
        net.type = NetworkInfo.AUTOMATIC
        self.assertEquals(net.type, NetworkInfo.AUTOMATIC)
        net.type = NetworkInfo.NONE
        self.assertEquals(net.type, NetworkInfo.NONE)
    
    def test_set_type_invalid(self):
        '''NetworkInfo.type = <arbitrary value> fails'''
        net = NetworkInfo()
        self.assertRaises(ValueError, NetworkInfo.type.fset, net, "foo")
        self.assertRaises(ValueError, NetworkInfo.type.fset, net, [])
        self.assertRaises(ValueError, NetworkInfo.type.fset, net, 1)

class TestNetworkInfo_to_xml(unittest.TestCase):
    
    def test_automatic(self):
        '''NetworkInfo.to_xml() looks correct for type = AUTOMATIC'''
        nic = NetworkInfo()
        nic.type = NetworkInfo.AUTOMATIC
        xml = nic.to_xml()[0]
        for instance in xml:
            if instance.get("name") == "nwam":
                self.assertEquals("true", instance.get("enabled"))
            elif instance.get("name") == "default":
                self.assertEquals("false", instance.get("enabled"))
            else:
                self.fail("Unexpected subelement found: %s" %
                          etree.tostring(instance, pretty_print=True))
    
    def test_none(self):
        '''NetworkInfo.to_xml() looks correct for type = NONE'''
        nic = NetworkInfo()
        nic.type = NetworkInfo.NONE
        xml = nic.to_xml()[0]
        for instance in xml:
            if instance.get("name") == "nwam":
                self.assertEquals("false", instance.get("enabled"))
            elif instance.get("name") == "default":
                self.assertEquals("true", instance.get("enabled"))
            else:
                self.fail("Unexpected subelement found: %s" %
                          etree.tostring(instance, pretty_print=True))
    
    def test_manual(self):
        '''NetworkInfo.to_xml() looks correct for type = MANUAL'''
        nic = NetworkInfo(dns_address="1.2.3.4")
        nic.type = NetworkInfo.MANUAL
        xml = nic.to_xml()
        for svc in xml:
            if svc.get("name") == "network/physical":
                net_phys = svc
            elif svc.get("name") == "network/install":
                net_install = svc
            else:
                self.fail("Unexpected service found: %s" %
                           etree.tostring(svc, pretty_print=True))
        for instance in net_phys:
            if instance.get("name") == "nwam":
                self.assertEquals("false", instance.get("enabled"))
            elif instance.get("name") == "default":
                self.assertEquals("true", instance.get("enabled"))
        
        for prop_group in net_install.iterchildren().next():
            if prop_group.get("name") not in ("install_ipv4_interface",
                                              "install_ipv6_interface"):
                self.fail("Unexpected property group of network/dns/install: "
                          "%s" % etree.tostring(prop_group, pretty_print=True))


if __name__ == '__main__':
    unittest.main()

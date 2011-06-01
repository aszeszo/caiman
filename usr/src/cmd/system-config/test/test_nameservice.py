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

from solaris_install.sysconfig.nameservice import NSDomain, NSDNSServer, \
        NSDNSSearch, NSLDAPProfile, NSLDAPProxyBindInfo, NSNISIP
import solaris_install.sysconfig.nameservice as nsv
from terminalui.base_screen import UIMessage


class MockField(object):

    def __init__(self, val):
        self._val = val
    
    def get_text(self):
        return self._val


class TestNS(unittest.TestCase):
    '''Test Name Services screens'''
    
    def setUp(self):
        self.NSDomain__init__ = NSDomain.__init__ 
        self.NSDNSServer__init__ = NSDNSServer.__init__ 
        self.NSDNSSEARCH__init__ = NSDNSSearch.__init__ 
        self.NSLDAPProfile__init__ = NSLDAPProfile.__init__ 
        self.NSLDAPProxyBindInfo_init_ = NSLDAPProxyBindInfo.__init__ 
        self.NSNISIP__init__ = NSNISIP.__init__ 
        NSNISIP.__init__ = self.NSNISIP__init__
        NSDomain.__init__ = lambda x, y: None
        NSDNSServer.__init__ = lambda x, y: None
        NSDNSSearch.__init__ = lambda x, y: None
        NSLDAPProfile.__init__ = lambda x, y: None
        NSLDAPProxyBindInfo.__init__ = lambda x, y: None
        NSNISIP.__init__ = lambda x, y: None
        self.ns_domain = NSDomain(None)
        self.ns_dnsserver = NSDNSServer(None)
        self.ns_dnssearch = NSDNSSearch(None)
        self.ns_ldapprofile = NSLDAPProfile(None)
        self.ns_ldapproxy = NSLDAPProxyBindInfo(None)
        self.ns_nisip = NSNISIP(None)

    def tearDown(self):
        NSDomain.__init__ = self.NSDomain__init__
        NSDNSServer.__init__ = self.NSDNSServer__init__
        NSDNSSearch.__init__ = self.NSDNSSEARCH__init__
        NSLDAPProfile.__init__ = self.NSLDAPProfile__init__
        NSLDAPProxyBindInfo.__init__ = self.NSLDAPProxyBindInfo_init_
        NSNISIP.__init__ = self.NSNISIP__init__

    def test_validate_ns_validate_method(self):
        ''' Test SCI tool name service validation method - all screens '''
        self.ns_domain.domain = MockField('dom.ain')
        self.assertEqual(self.ns_domain.validate(), None)
        self.ns_domain.domain = MockField('dom ain')
        self.assertRaises(UIMessage, self.ns_domain.validate)

        self.ns_dnsserver.dns_server_list = []
        for i in range(3):
            self.ns_dnsserver.dns_server_list += [MockField('1.1.1.1')]
        self.assertEqual(self.ns_dnsserver.validate(), None)
        self.ns_dnsserver.dns_server_list[0] = MockField('1.1.1.')
        self.assertRaises(UIMessage, self.ns_dnsserver.validate)

        self.ns_dnssearch.dns_search_list = []
        for i in range(6):
            self.ns_dnssearch.dns_search_list += [MockField('dom.ain')]
        self.assertEqual(self.ns_dnssearch.validate(), None)
        self.ns_dnssearch.dns_search_list[0] = MockField('dom ain')
        self.assertRaises(UIMessage, self.ns_dnssearch.validate)

        self.ns_ldapprofile.ldap_profile = MockField('profile')
        self.ns_ldapprofile.ldap_ip = MockField('1.1.1.1')
        self.assertEqual(self.ns_ldapprofile.validate(), None)
        self.ns_ldapprofile.ldap_profile = MockField('prof ile')
        self.assertRaises(UIMessage, self.ns_ldapprofile.validate)

        self.ns_ldapproxy.ldap_pb_dn = MockField('distinguishedname')
        self.ns_ldapproxy.ldap_pb_psw = MockField('password')
        self.assertEqual(self.ns_ldapproxy.validate(), None)
        self.ns_ldapproxy.ldap_pb_dn = MockField('distinguished bad name')
        self.assertRaises(UIMessage, self.ns_ldapproxy.validate)

        self.ns_nisip.nis_ip = MockField('1.1.1.1')
        self.assertEqual(self.ns_nisip.validate(), None)
        self.ns_nisip.nis_ip = MockField('1.1.1.')
        self.assertRaises(UIMessage, self.ns_nisip.validate)

    def test_validate_ns_validation_functions(self):
        ''' Test SCI tool name service validation functions '''
        # LDAP profile
        self.assertRaises(UIMessage, nsv.validate_ldap_profile, '')
        self.assertRaises(UIMessage, nsv.validate_ldap_profile, 'bad profile')
        self.assertRaises(UIMessage, nsv.validate_ldap_profile, 'bad"profile')
        self.assertEqual(nsv.validate_ldap_profile('goodprofile'), None)
        # LDAP distinguished name
        self.assertRaises(UIMessage, nsv.validate_ldap_proxy_dn, '')
        self.assertRaises(UIMessage, nsv.validate_ldap_proxy_dn, 'bad DN')
        self.assertRaises(UIMessage, nsv.validate_ldap_proxy_dn, 'bad"DN')
        self.assertEqual(nsv.validate_ldap_proxy_dn('goodDN'), None)
        # IP address
        self.assertRaises(UIMessage, nsv.validate_ip, '1.2.1.')
        self.assertRaises(UIMessage, nsv.validate_ip, '  ')
        self.assertEqual(nsv.validate_ip('1.1.1.1'), None)
        self.assertTrue(nsv.incremental_validate_ip(MockField('1.2.3.4')))
        # incremental IP address
        self.assertRaises(UIMessage, nsv.incremental_validate_ip,
                          MockField(' '))
        self.assertRaises(UIMessage, nsv.incremental_validate_ip,
                          MockField('x'))
        self.assertEqual(nsv.inc_validate_nowhite_nospecial(MockField('ok')),
                         None)
        self.assertRaises(UIMessage, nsv.incremental_validate_ip,
                          MockField('"'))
        self.assertRaises(UIMessage, nsv.incremental_validate_ip,
                          MockField(' '))
        # domain
        self.assertRaises(UIMessage, nsv.validate_domain, 'domain.')
        self.assertRaises(UIMessage, nsv.validate_domain, 'domain-')
        self.assertRaises(UIMessage, nsv.validate_domain, 'domain%')
        self.assertEqual(nsv.validate_domain('ddd.ooo.mmm.aaa.iii.n'), None)
        # incremental domain
        self.assertEqual(nsv.incremental_validate_domain(MockField('a')),
                         None)
        self.assertRaises(UIMessage, nsv.incremental_validate_domain,
                          MockField(' '))
        self.assertRaises(UIMessage, nsv.incremental_validate_domain,
                          MockField('%'))


if __name__ == '__main__':
        unittest.main()

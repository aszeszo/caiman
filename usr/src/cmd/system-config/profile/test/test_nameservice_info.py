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

from solaris_install.sysconfig.profile.nameservice_info import NameServiceInfo


SAMPLE_NONE_XML = '''<root>
  <service version="1" type="service" name="system/name-service/switch">
    <property_group type="application" name="config">
      <propval type="astring" name="default" value="files"/>
      <propval type="astring" name="printer" value="user files"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="system/name-service/cache">
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/dns/client">
    <instance enabled="false" name="default"/>
  </service>
</root>
'''

SAMPLE_DNS_XML = '''<root>
  <service version="1" type="service" name="system/name-service/switch">
    <property_group type="application" name="config">
      <propval type="astring" name="default" value="files"/>
      <propval type="astring" name="host" value="files dns mdns"/>
      <propval type="astring" name="printer" value="user files"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="system/name-service/cache">
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/dns/client">
    <property_group type="application" name="config">
      <property type="net_address" name="nameserver">
        <net_address_list>
          <value_node value="1.1.1.1"/>
        </net_address_list>
      </property>
      <propval type="astring" name="domain" value="my.domain.com"/>
      <property type="astring" name="search">
        <astring_list>
          <value_node value="my.domain.com"/>
        </astring_list>
      </property>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
'''

SAMPLE_LDAP_XML = '''<root>
  <service version="1" type="service" name="system/name-service/switch">
    <property_group type="application" name="config">
      <propval type="astring" name="default" value="files ldap"/>
      <propval type="astring" name="printer" value="user files ldap"/>
      <propval type="astring" name="netgroup" value="ldap"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="system/name-service/cache">
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/dns/client">
    <instance enabled="false" name="default"/>
  </service>
  <service version="1" type="service" name="network/ldap/client">
    <property_group type="application" name="config">
      <propval type="astring" name="profile" value="default"/>
      <property type="host" name="server_list">
        <host_list>
          <value_node value="1.1.1.1"/>
        </host_list>
      </property>
      <propval type="astring" name="search_base" value="default"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/nis/domain">
    <property_group type="application" name="config">
      <propval type="hostname" name="domainname" value="my.domain.com"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
</root>
'''

SAMPLE_NIS_XML = '''<root>
  <service version="1" type="service" name="system/name-service/switch">
    <property_group type="application" name="config">
      <propval type="astring" name="default" value="files nis"/>
      <propval type="astring" name="printer" value="user files nis"/>
      <propval type="astring" name="netgroup" value="nis"/>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="system/name-service/cache">
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/dns/client">
    <instance enabled="false" name="default"/>
  </service>
  <service version="1" type="service" name="network/nis/domain">
    <property_group type="application" name="config">
      <propval type="hostname" name="domainname" value="my.domain.com"/>
      <property type="host" name="ypservers">
        <host_list>
          <value_node value="1.1.1.1"/>
        </host_list>
      </property>
    </property_group>
    <instance enabled="true" name="default"/>
  </service>
  <service version="1" type="service" name="network/nis/client">
    <instance enabled="true" name="default"/>
  </service>
</root>
'''


class TestNameServiceInfoToXML(unittest.TestCase):

    def test_to_xml_no_name_service(self):
        '''Test SCI tool name service to_xml method - no name service'''
        self._gen_to_xml(NameServiceInfo(
                         dns=False,
                         domain='my.domain.com',
                         dns_server=['1.1.1.1'], dns_search=['my.domain.com']),
                         SAMPLE_NONE_XML)

    def test_to_xml_dns(self):
        '''Test SCI tool name service to_xml method - DNS'''
        self._gen_to_xml(NameServiceInfo(
                         dns=True,
                         domain='my.domain.com',
                         dns_server=['1.1.1.1'], dns_search=['my.domain.com']),
                         SAMPLE_DNS_XML)

    def test_to_xml_ldap(self):
        '''Test SCI tool name service to_xml method - LDAP'''
        self._gen_to_xml(NameServiceInfo(
                         dns=False,
                         domain='my.domain.com',
                         nameservice='LDAP', ldap_ip='1.1.1.1'),
                         SAMPLE_LDAP_XML)

    def test_to_xml_nis(self):
        '''Test SCI tool name service to_xml method - NIS'''
        self._gen_to_xml(NameServiceInfo(
                         dns=False,
                         domain='my.domain.com',
                         nameservice='NIS', nis_ip='1.1.1.1', nis_auto=1),
                         SAMPLE_NIS_XML)

    def _gen_to_xml(self, nsv, compare_with_this):
        '''Compare the NameServiceInfo.to_xml() output with a baseline
            (see above).
        Only concerned with structure, so values are ignored.  '''
        xml = nsv.to_xml()
        xml_root = etree.fromstring("<root/>")
        xml_root.extend(xml)
        xml_str = etree.tostring(xml_root, pretty_print=True)
        xml_lines = xml_str.splitlines()
        compare_with = compare_with_this.splitlines()
        for xml_line, compare_with_line in zip(xml_lines, compare_with):
            if "<propval" in compare_with_line or \
                    "value_node" in compare_with_line:
                continue
            self.assertEqual(xml_line, compare_with_line)


if __name__ == '__main__':
    unittest.main()

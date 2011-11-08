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

import os
import shutil
import tempfile
import unittest

import solaris_install.js2ai as js2ai
import lxml.etree as etree

from subprocess import call
from solaris_install.js2ai.common import ConversionReport
from solaris_install.js2ai.common import KeyValues
from solaris_install.js2ai.common import pretty_print as pretty_print
from solaris_install.js2ai.common import fetch_xpath_node
from solaris_install.js2ai.common import SYSIDCFG_FILENAME, ATTRIBUTE_VALUE
from solaris_install.js2ai.conv_sysidcfg import DEFAULT_FIXED, AUTOMATIC
from solaris_install.js2ai.conv_sysidcfg import XMLSysidcfgData
from test_js2ai import failure_report, fetch_log


def get_network_setting(xml_data):
    """Retrieves the active_np setting value from xml tree"""
    network_value = fetch_xpath_node(xml_data.tree,
                                     "/service_bundle[@type='profile']"
                                     "/service[@name='network/physical']"
                                     "/instance[@name='default']"
                                     "/property_group[@name='netcfg']"
                                     "/propval[@name='active_ncp']")
    ncp = network_value.get(ATTRIBUTE_VALUE)
    return ncp


def get_network_interface(xml_data, ipv4=True):
    """Retrieves the network interface setting value from xml tree"""
    if ipv4:
        grp_name = "install_ipv4_interface"
    else:
        grp_name = "install_ipv6_interface"
    network_node = fetch_xpath_node(xml_data.tree,
                                     "/service_bundle[@type='profile']"
                                     "/service[@name='network/install']"
                                     "/instance[@name='default']"
                                     "/property_group[@name='%s']"
                                     "/propval[@name='name']" % grp_name)
    interface = network_node.get(ATTRIBUTE_VALUE).split("/")
    return interface[0]


class Test_Sysidcfg_Valid(unittest.TestCase):
    """The tests in this class, test for valid syntax forms supported for
       the conversion.  Once the syntax test passes a 2nd test is perform
       to validate the resulting xml output.

    """

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)
        js2ai.logger_setup(self.working_dir)

    def sysidcfg_failure_report(self, xml_data, report):
        """Generate the failure report"""
        buffer = "\nResulting XML Tree: "
        if xml_data.tree is None:
            buffer += "No data available"
        else:
            buffer += "\n\n" + pretty_print(xml_data.tree)
        buffer += "\n\n\n" + failure_report(report, self.log_file)
        return buffer

    def tearDown(self):
        """Test tear down"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def get_xml_contents(self, filename):
        """Read in the xml file and return it's contents"""
        x = etree.parse(filename)
        return etree.tostring(x, pretty_print=True)

    def validate_xml_output(self, xml_data):
        """Outputs the xml data to a file and then performs a validation test
           on the resulting file

        """
        self.assertNotEquals(xml_data.tree, None)
        filename = os.path.join(self.working_dir, SYSIDCFG_FILENAME + ".xml")
        js2ai.write_xml_data(xml_data.tree, None, filename)
        retcode = call("/usr/sbin/svccfg apply -n " + filename, shell=True)
        self.assertEquals(retcode, 0, "Validation of xml failed:\n\n" +
        self.get_xml_contents(filename))

    def validate_network_automatic(self, xml_data):
        """Validates that network interface is set to Automatic"""
        self.assertEquals(get_network_setting(xml_data), AUTOMATIC,
                          "expected setting of %s got %s\n\n%s\n\n%s" %
                          (AUTOMATIC, DEFAULT_FIXED,
                          etree.tostring(xml_data.tree, pretty_print=True),
                          fetch_log(self.log_file)))

    def validate_network_defaultfixed(self, xml_data):
        """Validates that network interface is set to DefaultFixed"""
        self.assertEquals(get_network_setting(xml_data), DEFAULT_FIXED,
                          "expected setting of %s got %s\n\n%s\n\n%s" %
                          (DEFAULT_FIXED, AUTOMATIC,
                           etree.tostring(xml_data.tree, pretty_print=True),
                           fetch_log(self.log_file)))

    def default_dict_setup(self):
        """Setups up a dictorion with base settings that will prevent
           warning messages from being generated

        """
        data = dict()
        payload = dict()
        payload["hostname"] = "host1"
        key_value = KeyValues("network_interface", ["NONE", payload], 1)
        data[key_value.line_num] = key_value
        key_value = KeyValues("root_password", ["encrypted_password"], 2)
        data[key_value.line_num] = key_value
        return data

    def test_sysidcfg_name_service_none1(self):
        """Tests sysidcfg name_service=None"""
        data = self.default_dict_setup()
        key_value = KeyValues("name_service", ["None"], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report, xml_data.conversion_report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        # default_dict_setup will add
        # network_interface = NONE {hostname=xxx}
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_none2(self):
        """Tests sysidcfg name_service=None results in network = Automatic"""
        data = dict()
        key_value = KeyValues("name_service", ["None"], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_DNS(self):
        """Tests sysidcfg name_service=DNS {args}"""
        # name_service=DNS {domain_name=mydomain_name
        #   name_server=131.188.30.105,131.188.30.101,131.188.30.40
        #   search=info.de,more-info.de,even-more-info.de}
        data = self.default_dict_setup()
        payload = dict()
        payload["domain_name"] = "mydomain_name"
        payload["name_server"] = "131.188.30.105,131.188.30.101,131.188.30.40"
        payload["search"] = "info.de,more-info.de,even-more-info.de"
        key_value = KeyValues("name_service", ["DNS", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_NIS(self):
        """Tests sysidcfg name_service=NIS {args..}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["domain_name"] = "domain_name"
        payload["name_server"] = "host(129.91.159.000)"
        key_value = KeyValues("name_service", ["NIS", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_LDAP(self):
        """Tests sysidcfg name_service=LDAP {args..}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["domain_name"] = "us.oracle.com"
        payload["profile"] = "default"
        payload["profile_server"] = "172.31.2.1"
        payload["proxy_dn"] = \
            "cn=proxyagent,ou=profile,dc=west,dc=example,dc=com"
        payload["proxy_password"] = "password"
        key_value = KeyValues("name_service", ["LDAP", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_LDAP_wo_opt_arg(self):
        """Tests sysidcfg name_service=LDAP without opt args"""
        data = self.default_dict_setup()
        payload = dict()
        payload["domain_name"] = "us.oracle.com"
        payload["profile"] = "default"
        payload["profile_server"] = "172.31.2.1"
        key_value = KeyValues("name_service", ["LDAP", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_primary_no_args(self):
        """Tests sysidcfg network_interface=PRIMARY"""
        data = self.default_dict_setup()
        payload = dict()
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        # Warning for missing hostname and for PRIMARY may not be same
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_primary_dhcp(self):
        """Tests sysidcfg network_interface=PRIMARY {dhcp}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["dhcp"] = ""
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        # Warning for missing hostname and for PRIMARY may not be same
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_more_than_one_ipv6(self):
        """Tests sysidcfg network interface eri0 with no errors

           network_interface=eri1 {protocol_ipv6=yes hostname=host1}
           network_interface=eri2 {primary protocol_ipv6=yes hostname=host2}
        """
        data = self.default_dict_setup()
        payload = dict()
        payload["hostname"] = "host1"
        payload["protocol_ipv6"] = "yes"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        payload = dict()
        payload["primary"] = ""
        payload["hostname"] = "host2"
        payload["protocol_ipv6"] = "yes"
        key_value = KeyValues("network_interface", ["eri2", payload], 5)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        # error for network interface eril
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 0,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)
        self.assertEquals(get_network_interface(xml_data, False), "eri2")

    def test_sysidcfg_network_interface_more_than_one_ipv4(self):
        """Tests sysidcfg network interface eri0 with no errors

           network_interface=eri0 {hostname=host0 ....}
           network_interface=eri1 {hostname=host1 ....}
           network_interface=eri2 {primary hostname=host2 ....}
        """
        data = dict()
        payload = dict()
        payload["hostname"] = "host0"
        payload["ip_address"] = "192.168.2.6"
        payload["netmask"] = "255.255.255.0"
        payload["default_route"] = "192.168.2.1"
        key_value = KeyValues("network_interface", ["eri0", payload], 1)
        data[key_value.line_num] = key_value
        payload = dict()
        payload["hostname"] = "host1"
        payload["ip_address"] = "192.168.2.7"
        payload["netmask"] = "255.255.255.0"
        payload["default_route"] = "192.168.2.1"
        key_value = KeyValues("network_interface", ["eri1", payload], 2)
        data[key_value.line_num] = key_value
        payload = dict()
        payload["primary"] = ""
        payload["hostname"] = "host2"
        payload["ip_address"] = "192.168.2.8"
        payload["netmask"] = "255.255.255.0"
        payload["default_route"] = "192.168.2.1"
        key_value = KeyValues("network_interface", ["eri2", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        # error for network interface eril
        self.assertEquals(report.unsupported_items, 2,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)
        self.assertEquals(get_network_interface(xml_data), "eri2")

    def test_sysidcfg_network_interface_PRIMARY_dhcp_ipv6(self):
        """Tests sysidcfg network_interface PRIMARY  dhcp ipv6=yes"""
        data = self.default_dict_setup()
        payload = dict()
        payload["dhcp"] = ""
        payload["protocol_ipv6"] = "yes"
        payload["hostname"] = "host1"
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_value_dhcp(self):
        """Tests sysidcfg network_interface=eri0 {dhcp hostname=host1}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["dhcp"] = ""
        payload["hostname"] = "host1"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_dhcp_ipv6(self):
        """Tests sysidcfg dhcp ipv6=yes

           network_interface=eri0 {dhcp protocol_ipv6=yes hostname=host1}

        """
        data = self.default_dict_setup()
        payload = dict()
        payload["dhcp"] = ""
        payload["protocol_ipv6"] = "yes"
        payload["hostname"] = "host1"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_dhcp_ipv6_no(self):
        """Tests sysidcfg dhcp ipv6=no

           network_interface=eri0 {dhcp protocol_ipv6=no hostname=host1}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["hostname"] = "host1"
        payload["dhcp"] = ""
        payload["protocol_ipv6"] = "no"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_wargs(self):
        """Tests sysidcfg network interface eri0 with no errors

           network_interface=eri0 {hostname=host1
                        ip_address=192.168.2.7
                        netmask=255.255.255.0
                        protocol_ipv6=no
                        default_route=None}
        """
        data = self.default_dict_setup()
        payload = dict()
        payload["hostname"] = "host1"
        payload["ip_address"] = "192.168.3.8"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "None"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_ipv6(self):
        """Tests sysidcfg network interface eri0 with no errors

           network_interface=eri0 {protocol_ipv6=yes hostname=host1}
        """
        data = self.default_dict_setup()
        payload = dict()
        payload["hostname"] = "host1"
        payload["protocol_ipv6"] = "yes"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_none(self):
        """Tests sysidcfg network_interface=NONE"""
        data = self.default_dict_setup()
        payload = dict()
        key_value = KeyValues("network_interface", ["NONE", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        # Warning for missing hostname
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_none_whost(self):
        """Tests sysidcfg network_interface=NONE {hostname=host1}"""
        data = self.default_dict_setup()
        payload = dict()
        payload["hostname"] = "host1"
        key_value = KeyValues("network_interface", ["NONE", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_keyboard1(self):
        """Tests keyboard=French"""
        data = self.default_dict_setup()
        data[3] = KeyValues("keyboard", ["French"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)
        # default_dict_setup will add
        # network_interface = NONE {hostname=xxx}
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_keyboard2(self):
        """Tests keyboard=English only to make sure network DefaultFixed"""
        data = dict()
        data[3] = KeyValues("keyboard", ["French"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_root_pswd(self):
        """Tests root_password=encrypted_password"""
        data = dict()
        data[1] = KeyValues("root_password", ["encrypted_password"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        # Warning for missing hostname
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_xml_output(xml_data)
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_security_policy_none(self):
        """Tests for no error if security_policy=None"""
        data = self.default_dict_setup()
        data[3] = KeyValues("security_policy", ["None"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)

    def test_sysidcfg_service_profile_limited_net(self):
        """Tests service_profile=limited_net"""
        data = self.default_dict_setup()
        data[3] = KeyValues("service_profile", ["limited_net"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)

    def test_sysidcfg_system_locale(self):
        """Tests system_locale=en.UTF-8"""
        data = self.default_dict_setup()
        data[3] = KeyValues("system_locale", ["en.UTF-8"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)

    def test_sysidcfg_terminal(self):
        """Tests terminal=vt100"""
        data = self.default_dict_setup()
        data[3] = KeyValues("terminal", ["vt100"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)

    def test_sysidcfg_timeserver_localhost(self):
        """Tests time_server=localhost"""
        data = self.default_dict_setup()
        data[3] = KeyValues("timeserver", ["localhost"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)

    def test_sysidcfg_timezone(self):
        """Tests timezone=US/Eastern"""
        data = self.default_dict_setup()
        data[3] = KeyValues("timezone", ["US/Eastern"], 3)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), False,
                          self.sysidcfg_failure_report(xml_data, report))
        self.validate_xml_output(xml_data)


class Test_Sysidcfg_Invalid(unittest.TestCase):

    def setUp(self):
        """Setup for tests"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)
        js2ai.logger_setup(self.working_dir)

    def tearDown(self):
        """Test tear down"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def validate_network_automatic(self, xml_data):
        """Validates that network interface is set to Automatic"""
        self.assertEquals(get_network_setting(xml_data), AUTOMATIC,
                          "expected setting of %s got %s\n\n%s\n\n%s" %
                          (AUTOMATIC, DEFAULT_FIXED,
                          etree.tostring(xml_data.tree, pretty_print=True),
                          fetch_log(self.log_file)))

    def validate_network_defaultfixed(self, xml_data):
        """Validates that network interface is set to DefaultFixed"""
        self.assertEquals(get_network_setting(xml_data), DEFAULT_FIXED,
                          "expected setting of %s got %s\n\n%s\n\n%s" %
                          (DEFAULT_FIXED, AUTOMATIC,
                           etree.tostring(xml_data.tree, pretty_print=True),
                           fetch_log(self.log_file)))

    def test_sysidcfg_name_service_invalid(self):
        """Tests sysidcfg name_service=xyz {args..}"""
        data = dict()
        payload = dict()
        payload["domain_name"] = "domain_name"
        payload["name_server"] = "host(129.91.159.000)"
        key_value = KeyValues("name_service", ["xyz", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        #  name service entry doesn't get added so default becomes automated
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_DNS_incomplete(self):
        """Tests sysidcfg name_service=DNS {args}"""
        # name_service=DNS {domain_name=mydomain_name
        #   name_server=
        #   search=info.de,more-info.de,even-more-info.de}
        data = dict()
        payload = dict()
        payload["domain_name"] = "mydomain_name"
        payload["search"] = "info.de,more-info.de,even-more-info.de"
        key_value = KeyValues("name_service", ["DNS", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        #  name service entry doesn't get added so default becomes automated
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_none_wargs(self):
        """Tests sysidcfg name_service=None {extra_arg}"""
        data = dict()
        payload = dict()
        payload["extra_arg"] = "anything"
        key_value = KeyValues("name_service", ["None", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        # name_service line gets ignored
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_DNS_bad_ip(self):
        """Tests sysidcfg name_service=DNS {args}"""
        data = dict()
        payload = dict()
        payload["domain_name"] = "mydomain_name"
        payload["name_server"] = "13a.188.30.105,131.188.30.101,131.188.30.40"
        payload["search"] = "info.de,more-info.de,even-more-info.de"
        key_value = KeyValues("name_service", ["DNS", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        #  name service gets added bad ip is not outputed
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_DNS_extra_args(self):
        """Tests sysidcfg name_service=DNS {args}"""
        data = dict()
        payload = dict()
        payload["domain_name"] = "mydomain_name"
        payload["name_server"] = "131.188.30.101,131.188.30.40"
        payload["search"] = "info.de,more-info.de,even-more-info.de"
        payload["extra1"] = "extra"
        payload["extra2"] = ""
        key_value = KeyValues("name_service", ["DNS", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 2,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 3,
                          failure_report(report, self.log_file))
        # name service added extra args ignored
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_LDAP(self):
        """Tests sysidcfg name_service=LDAP {args..}"""
        data = dict()
        payload = dict()
        payload["domain_name"] = "domain_name"
        payload["profile"] = "profile_name"
        payload["profile_server"] = "ip_address"
        payload["proxy_dn"] = "proxy_bind_dn"
        payload["proxy_password"] = "password"
        payload["extra_arg"] = "anything"
        key_value = KeyValues("name_service", ["LDAP", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        # name_service line is rejected
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_NISplus(self):
        """Tests sysidcfg name_service=NIS+ {args..}"""
        data = dict()
        payload = dict()
        payload["domain_name"] = "domain_name"
        payload["name_server"] = "host(129.91.159.000)"
        key_value = KeyValues("name_service", ["NIS+", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 4,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_PRIMARY_dhcp_ipv6_no(self):
        """Tests sysidcfg network_interface=PRIMARY {dhcp protocol_ipv6=no}"""
        data = dict()
        payload = dict()
        payload["dhcp"] = ""
        payload["protocol_ipv6"] = "no"
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 3,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_PRIMARY_dhcp_ipv6_extra_arg(self):
        """Tests sysidcfg network_interface=PRIMARY ipv6 with extra args"""
        data = dict()
        payload = dict()
        payload["dhcp"] = ""
        payload["protocol_ipv6"] = "yes"
        payload["default_router"] = "129.91.159.9"
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 3,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_PRIMARY_wargs(self):
        """Tests sysidcfg network_interface=PRIMARY {valid args}"""
        data = dict()
        payload = dict()
        payload["ip_address"] = "192.168.3.8"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "None"
        key_value = KeyValues("network_interface", ["PRIMARY", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_primary_wargs(self):
        """Tests sysidcfg with error for primary

           network_interface=eri0 {primary
                        hostname=host1
                        netmask=255.255.255.0
                        protocol_ipv6=no
                        default_route=192.168.2.1}
        """
        data = dict()
        payload = dict()
        payload["primary"] = ""
        payload["hostname"] = "host123"
        payload["ip_address"] = "192.168.3.8"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "None"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_dhcp_wextra_arg(self):
        """Tests sysidcfg network_interface=eri0 {dhcp doit=yes}"""
        data = dict()
        payload = dict()
        payload["dhcp"] = ""
        payload["doit"] = "yes"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_no_args(self):
        """Tests sysidcfg network_interface=eri0"""
        data = dict()
        payload = dict()
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        # network_interface isn't valid sets to automated
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_value_no_args2(self):
        """Tests sysidcfg network_interface=eri0"""
        data = dict()
        key_value = KeyValues("network_interface", ["eri1", None], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        # network_interface isn't valid sets to automated
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_value_missing_ipaddr(self):
        """Tests sysidcfg with error for missing ip_address

           network_interface=eri0 {hostname=host1
                        netmask=255.255.255.0
                        protocol_ipv6=no
                        default_route=192.168.2.1}
        """
        data = dict()
        payload = dict()
        payload["hostname"] = "host123"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "None"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_value_invalid_default_route(self):
        """Tests sysidcfg with error for missing ip_address

           network_interface=eri0 {hostname=host1
                        ip_addres=192.168.3.8
                        netmask=255.255.255.0
                        protocol_ipv6=no
                        default_route=192.168.2.1}
        """
        data = dict()
        payload = dict()
        payload["hostname"] = "host123"
        payload["ip_address"] = "192.168.3.8"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "129.abc"
        key_value = KeyValues("network_interface", ["eri1", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_none_extra_interface(self):
        """Tests network_interface=NONE and extra illegal interface"""
        data = dict()
        key_value1 = KeyValues("network_interface", ["NONE", None], 1)
        data[key_value1.line_num] = key_value1
        key_value2 = KeyValues("network_interface", ["eri1", None], 2)
        data[key_value2.line_num] = key_value2
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_none_invalidhost(self):
        """Tests sysidcfg network_interface=NONE {hostname=123$$host1}"""
        data = dict()
        payload = dict()
        payload["hostname"] = "123$$host1"
        key_value = KeyValues("network_interface", ["NONE", payload], 1)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_network_interface_primary_extra_interface(self):
        """Tests network_interface=PRIMARY and extra illegal interface"""
        data = dict()
        data[1] = KeyValues("network_interface", ["PRIMARY", None], 1)
        data[2] = KeyValues("network_interface", ["eri2", None], 2)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 3,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_network_interface_value_extra_interface(self):
        """Tests network_interface=eg0 {params} and extra illegal interface"""
        data = dict()
        payload = dict()
        payload["hostname"] = "host1"
        payload["ip_address"] = "192.168.3.8"
        payload["netmask"] = "255.255.255.0"
        payload["protocol_ipv6"] = "no"
        payload["default_route"] = "None"
        data[1] = KeyValues("network_interface", ["eri1", payload], 1)
        data[2] = KeyValues("network_interface", ["eri2", payload], 2)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_name_service_DNS_simple(self):
        """Tests sysidcfg name_service=DNS """
        data = dict()
        key_value = KeyValues("name_service", ["DNS", None], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        # name_service incomplete rejected, goes to automatic
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_name_service_DNS_bad_ip(self):
        """Tests sysidcfg name_service=DNS {args}"""
        # name_service=DNS {domain_name=mydomain_name
        #   name_server=131.188.30.10a
        #   search=info.de,more-info.de,even-more-info.de}
        data = dict()
        payload = dict()
        payload["domain_name"] = "mydomain_name"
        payload["name_server"] = "131.188.30.10a"
        payload["search"] = "info.de,more-info.de,even-more-info.de"
        key_value = KeyValues("name_service", ["DNS", payload], 3)
        data[key_value.line_num] = key_value
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 3,
                          failure_report(report, self.log_file))
        self.validate_network_defaultfixed(xml_data)

    def test_sysidcfg_keyboard_w2nd_keyborad_defined(self):
        """Tests failure for 2nd keyboard defined"""
        data = dict()
        data[1] = KeyValues("keyboard", ["French"], 1)
        data[2] = KeyValues("keyboard", ["German"], 2)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_keyboard_extra_arg(self):
        """Tests keyboard for too many args"""
        data = dict()
        data[1] = KeyValues("keyboard", ["French", "extra_arg"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_nfs_domain(self):
        """Tests for non support of nfs_domain keyword"""
        data = dict()
        data[1] = KeyValues("nfs_domain", ["dynamic"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_root_pswd_2nd_defined(self):
        """Tests failure for 2nd root password defined"""
        data = dict()
        data[1] = KeyValues("root_password", ["encrypted_password"], 1)
        data[2] = KeyValues("root_password", ["encrypted_password"], 2)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 1,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_root_pswd_too_many_args(self):
        """Tests root_password for too many args"""
        data = dict()
        data[1] = KeyValues("root_password",
                            ["encrypted_password", "extra_arg"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_security_policy_kerberos(self):
        """Tests for non support of security_policy kerberos"""
        data = dict()
        data[1] = KeyValues("security_policy", ["kerberos"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_security_policy_invalid(self):
        """Tests for no error if security_policy invalid policy"""
        data = dict()
        data[1] = KeyValues("security_policy", ["my_policy"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_service_profile_open(self):
        """Tests service_profile=open"""
        data = dict()
        data[1] = KeyValues("service_profile", ["open"], 1)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_service_profile_duplicate(self):
        """Tests failure for 2nd service_profile defined"""
        data = dict()
        data[1] = KeyValues("service_profile", ["limited_net"], 1)
        data[2] = KeyValues("service_profile", ["open"], 2)
        report = ConversionReport()
        xml_data = XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))
        self.validate_network_automatic(xml_data)

    def test_sysidcfg_service_profile_too_many_args(self):
        """Tests service_profile for too many args"""
        data = dict()
        data[1] = KeyValues("service_profile", ["limited_net", "extra_arg"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_service_profile_invalid(self):
        """Tests for error if service_profile specified is invalid"""
        data = dict()
        data[1] = KeyValues("service_profile", ["my_policy"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_terminal_too_many_args(self):
        """Tests terminal for too many args"""
        data = dict()
        data[1] = KeyValues("terminal", ["vt100", "extra_arg"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_timeserver_unsupported(self):
        """Tests time_server=host1"""
        data = dict()
        data[1] = KeyValues("timeserver", ["host1"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_timeserver_too_many_args(self):
        """Tests timeserver for too many args"""
        data = dict()
        data[1] = KeyValues("timeserver", ["localhost", "extra_arg"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_timezone_duplicate(self):
        """Tests failure for 2nd timezone defined"""
        data = dict()
        data[1] = KeyValues("timezone", ["US/Eastern"], 1)
        data[2] = KeyValues("timezone", ["US/Mountain"], 2)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))

    def test_sysidcfg_timezone_too_many_args(self):
        """Tests timezone for too many args"""
        data = dict()
        data[1] = KeyValues("timezone", ["US/Central", "extra_arg"], 1)
        report = ConversionReport()
        XMLSysidcfgData(data, report)
        self.assertEquals(report.has_errors(), True,
                          failure_report(report, self.log_file))
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, self.log_file))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.validation_errors, 0,
                          failure_report(report, self.log_file))
        self.assertEquals(report.warnings, 2,
                          failure_report(report, self.log_file))


if __name__ == '__main__':
    unittest.main()

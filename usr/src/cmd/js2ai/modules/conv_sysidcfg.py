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
"""Class used to convert Solaris 10 sysidcfg to the new format used by
new Solaris installer

"""
import common
import logging
import os.path
import re

from common import _
from common import fetch_xpath_node as fetch_xpath_node
from default_xml import SVC_BUNDLE_XML_DEFAULT
from ip_address import IPAddress
from lxml import etree
from solaris_install.js2ai.common import SYSIDCFG_FILENAME
from StringIO import StringIO

TYPE_APPLICATION = "application"
TYPE_ASTRING = "astring"
TYPE_COUNT = "count"
TYPE_NET_ADDRESS = "net_address"
TYPE_NET_ADDRESS_V4 = "net_address_v4"
TYPE_SERVICE = "service"
TYPE_SYSTEM = "system"

MAXHOSTNAMELEN = 255

# word,word pattern
COMMA_PATTERN = re.compile("\s*([^,]+)\s*,?")

# Parse data in the form host1(129.00.00.000),host2(121.000.000.000)
# We are only concerned with seperating the hostname and ip address
# out of this structure.
HOST_IP_PATTERN = re.compile("\s*([^,\(]+)(\(([^,\)]*)\))?\s*,?")

SYSIDCFG_XML_START = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">
"""


class XMLSysidcfgData(object):
    """Object used to represent the sysidcfg file"""
    # Syntax Rules for the sysidcfg File
    #
    # You can use two types of keywords in the sysidcfg file: independent and
    # dependent. Dependent keywords are guaranteed to be unique only within
    # independent keywords. A dependent keyword exists only when it is
    # identified with its associated independent keyword.
    #
    # In this example, name_service is the independent keyword, while
    # domain_name and name_server are the dependent keywords:
    #
    # name_service=NIS {domain_name=marquee.central.example.com
    # name_server=connor(192.168.112.3)}
    #
    # Syntax Rules
    # 1. Independent keywords can be listed in any order.
    # 2. Keywords are not case sensitive.
    # 3. Enclose all dependent keywords in curly braces ({}) to tie them to
    #    their associated independent keyword.
    # 4. Values can optionally be enclosed in single or double quotes
    # 5. For all keywords except the network_interface keyword, only one
    #    instance of a keyword is valid. However, if you specify the keyword
    #    more than once, only the first instance of the keyword is used.

    def __init__(self, sysidcfg_dict, report, default_tree, logger):

        if logger is None:
            logger = logging.getLogger("js2ai")
        self.logger = logger
        self.sysidcfg_dict = sysidcfg_dict
        self._report = report
        self._defined_net_interfaces = []
        self._default_network = None
        self._keyboard_layout = None
        self._hostname = None
        self._name_service = None
        self._root_prop_group = None
        self._service_bundle = None
        self._service_profile = None
        self._terminal = None
        self._timeserver = None
        self._timezone = None

        self._svc_install_config = None
        self._svc_system_keymap = None
        self._svc_network_physical = None

        if default_tree is None:
            default_tree = etree.parse(StringIO(SVC_BUNDLE_XML_DEFAULT))
        self._tree = default_tree
        self.__process_sysidcfg()

    def __check_payload(self, line_num, keyword, payload):
        """Check the payload (dict) to see if any elements are contained in it.
        Flag these extra elements as conversion errors

        """
        if payload is None:
            return
        for key, value in payload.iteritems():
            # Not all keywords will have values
            if value is None or value == "":
                pstr = key
            else:
                pstr = key + "=" + value
            self.logger.error(_("%(file)s: line %(lineno)d: unrecognized "
                                "option for '%(keyword)s' specified: "
                                "%(value)s") % \
                                {"file": SYSIDCFG_FILENAME, \
                                 "lineno": line_num, "keyword": keyword,
                                 "value": pstr})
            self._report.add_process_error()

    @property
    def conversion_report(self):
        """Conversion Report associated with this object"""
        return self._report

    def __convert_keyboard(self, line_num, keyword, values):
        """Converts the keyboard keyword/values from the sysidcfg into
        the proper xml output for the Solaris configuration file for the
        auto installer.

        """
        # Syntax:
        #   keyboard=keyboard_layout
        #
        # The valid keyboard_layout strings are defined on Solaris 10 in the
        # /usr/share/lib/keytables/type_6/kbd_layouts file.

        # converting to:
        #
        # <service name='system/keymap' version='1' type='service'>
        #   <instance name='default' enabled="true">
        #       <property_group name='keymap' type='system'>
        #           <propval name='layout' type='astring' value='Czech' />
        #       </property_group>
        #   </instance>
        # </service>

        if self._keyboard_layout is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        self._keyboard_layout = values[0]
        svc_system_keymap = \
            fetch_xpath_node(self._service_bundle,
                             "./service[@name='system/keymap']")
        # Does the default xml have an existing entry that we need to replace
        if svc_system_keymap is not None:
            self.__remove_children(svc_system_keymap)
        else:
            svc_system_keymap = \
                self.__create_service_node(self._service_bundle,
                                           "system/keymap")
        instance = self.__create_instance_node(svc_system_keymap)
        prop_group = self.__create_propgrp_node(instance,
                                                "keymap", TYPE_SYSTEM)
        self.__create_propval_node(prop_group, "layout",
                                   TYPE_ASTRING, self._keyboard_layout)

    def __convert_hostname(self, line_num, hostname):
        """Convert the hostname specified in the sysidcfg statement to the
        proper xml output for the Solaris configuration file for the
        auto installer.

        """
        if self._hostname is not None:
            self.logger.error(_("%(file)s: line %(lineno)d: only one hostname"
                                " can be defined, currently it's defined as "
                                "'%(hostname)s'") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num,
                                 "hostname": self._hostname})
            self._report.add_conversion_error()
            return

        if not self.__is_valid_hostname(hostname):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid hostname:"
                                "'%(hostname)s'") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num,
                                 "hostname": self._hostname})
            self._report.add_conversion_error()
            return

        other_sc_params = \
            self.__fetch_sys_install_config_prpgrp("other_sc_params")
        self._hostname = \
            fetch_xpath_node(other_sc_params,
                             "propval[@name='hostname']")
        if self._hostname is not None:
            self._hostname.set(common.ATTRIBUTE_VALUE, hostname)
        else:
            self.__create_propval_node(other_sc_params, "hostname",
                                       TYPE_ASTRING, hostname)

    def __convert_name_service_dns(self, line_num, keyword, payload):
        """Convert the DNS name service specified in the sysidcfg statement
        to the proper xml output for Solaris configuration file for the
        auto installer.

        """
        #
        # sysidcfg syntax:
        #
        #
        # name_service=DNS {domain_name=domain-name
        #         name_server=ip-address,ip-address,ip-address
        #         search=domain-name,domain-name,domain-name,
        #         domain-name,domain-name,domain-name}
        #
        # domain_name=domain-name
        #
        #    Specifies the domain name.
        #
        # name_server=ip-address
        #
        #   Specifies the IP address of the DNS server. You can specify up to
        #   three IP addresses as values for the name_server keyword.
        #
        # search=domain-name
        #
        #   (Optional) Specifies additional domains to search for name service
        #   information. You can specify up to six domain names to search.
        #   The total length of each search entry cannot exceed 250 characters.
        #
        #
        # converting to:
        #
        # <service name='network/dns/install' version='1' type='service'>
        #   <instance name='default' enabled='true'>
        #       <property_group name='install_props' type='application'>
        #           <property name='nameserver' type='net_address'>
        #               <net_address_list>
        #                   <value_node value='10.0.0.1'/>
        #               </net_address_list>
        #           </property>
        #           <propval name='domain' type='astring' value='exam.com'/>
        #           <property name='search' type='astring'>
        #               <astring_list>
        #                   <value_node value='example.com'/>
        #               </astring_list>
        #           </property>
        #       </property_group>
        #   </instance>
        # </service>

        self._name_service = \
            fetch_xpath_node(self._service_bundle,
                             "./service[@name='network/dns/install']")
        if self._name_service is not None:
            self.__remove_children(self._name_service)
        else:
            self._name_service = \
                self.__create_service_node(self._service_bundle,
                                           "network/dns/install")
        instance_node = \
            self.__create_instance_node(self._name_service)
        prop_grp = self.__create_propgrp_node(instance_node,
                                              "install_props",
                                              TYPE_APPLICATION)
        if payload is None:
            return

        name_server = payload.pop("name_server", None)
        if name_server is not None:
            prop = self.__create_prop_node(prop_grp, "nameserver",
                                           TYPE_NET_ADDRESS)
            plist = etree.SubElement(prop, "net_address_list")
            server_list = COMMA_PATTERN.findall(name_server)
            for ip_address in server_list:
                if self.__is_valid_ip(line_num, ip_address, _("ip address")):
                    self.__create_value_node(plist, ip_address)

        domain_name = payload.pop("domain_name", None)
        if domain_name is not None:
            self.__create_propval_node(prop_grp, "domain",
                                       TYPE_ASTRING, domain_name)

        search = payload.pop("search", None)
        if search is not None:
            prop = self.__create_prop_node(prop_grp, "search",
                                           TYPE_ASTRING)
            plist = etree.SubElement(prop, "astring_list")
            search_list = COMMA_PATTERN.findall(search)
            for search_element in search_list:
                self.__create_value_node(plist, search_element)

        # Are there any more keys left in the dictionary that we need to flag
        self.__check_payload(line_num, keyword, payload)

    def __convert_name_service_nis(self, line_num, keyword, payload):
        """Convert the NIS name service specified in the sysidcfg statement
        to the proper xml output for the Solaris configuration file for the
        auto installer. Currently NIS is not supported via the auto installer

        """
        # sysidcfg form:
        #
        # name_service=NIS {domain_name=domain-name
        #                    name_server=hostname(ip-address)}

        # The xml structures here will need to change
        # They are losely based on the xml for DNS since the
        # required structures for this is currently not available
        # or known

        # The below commented out code has been tested to ensure that
        # it properly parses the arguments for NIS from the sysidcfg
        # file.  When NIS support becomes available this code should be
        # uncommented and expanded up
        #
        #self._name_service = \
        #    fetch_xpath_node(self._service_bundle,
        #                     "./service[@name='network/nis/install']")
        #if self._name_service is not None:
        #    self.__remove_children(self._name_service)
        #else:
        #    self._name_service =\
        #        self.__create_service_node(self._service_bundle,
        #                                   "network/nis/install")
        #instance_node =\
        #    self.__create_instance_node(self._name_service)
        #prop_grp = self.__create_propgrp_node(instance_node,
        #                                     "intall_props", TYPE_APPLICATION)
        #
        #name_server = payload.pop("name_server", None)
        #if name_server is not None:
        #    prop = self.__create_prop_node(prop_grp, "nameserver",
        #                                   TYPE_NET_ADDRESS)
        #   list = etree.SubElement(prop, "net_address_list")
        #    server_list = self.HOST_IP_PATTERN.findall(name_server)
        #    for entry in server_list:
        #        hostname = entry[0]
        #        ip_address = entry[1]
        #
        #
        #domain_name = payload.pop("domain_name", None)
        #if domain_name is not None:
        #    domain = self.__create_prop_node(prop_grp, "domain", TYPE_ASTRING)
        #    domain.set(common.ATTRIBUTE_VALUE, domain_name)
        #
        # Are there any more keys left in the dictionary that we need to flag
        #self.__check_payload(line_num, keyword, payload)

        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "name service specified. DNS or NONE is currently"
                            " the only supported name servce selection.") % \
                            {"file": SYSIDCFG_FILENAME, \
                             "lineno": line_num})
        self._report.add_unsupported_item()

    def __convert_name_service_nisplus(self, line_num, keyword, payload):
        """Convert the NIS+ name service specified in the sysidcfg statement
        to the proper xml output for the Solaris configuration file for the
        auto installer.  NIS+ is no longer supported once NIS is supported the
        NIS+ entry will be converted to NIS

        """
        # sysidcfg form:
        #
        # name_service=NIS+ {domain_name=domain-name
        #                    name_server=hostname(ip-address)}

        # NIS plus is no longer supported in Solaris.
        # Convert this to standard NIS.  Output warning in log file
        #self.logger.warning(_("%(file)s: line %(lineno)d: NIS+ is no longer"
        #                    "supported.  Using NIS instead.") % \
        #                    {"file": SYSIDCFG_FILENAME, \
        #                     "lineno": line_num})
        #self._convert_name_service_NIS(line_num, keyword, payload)

        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                             "name service specified.  DNS or None is "
                            "currently the only supported name servce"
                            "selection.") % \
                            {"file": SYSIDCFG_FILENAME,
                             "lineno": line_num})
        self._report.add_unsupported_item()

    def __convert_name_service_none(self, line_num, keyword, payload):
        """Convert the NONE name service specified in the sysidcfg statement
        to the proper xml output for the Solaris configuration file for the
        auto installer.

        """
        # sysidcfg form:
        #
        # name_service=None
        if payload is not None:
            self.__invalid_syntax(line_num, keyword)
            return

        # Need to set the _name_service to some value so our duplicate
        # keyword check will work if first occurrance is None
        self._name_service = "None"

    def __convert_name_service_ldap(self, line_num, keyword, payload):
        """Convert the LDAP name service specified in the sysidcfg statement
        to the proper xml output for the Solaris configuration file for the
        auto installer. Currently LDAP is not supported via the auto installer

        """
        # sysidcfg form:
        #
        # name_service=LDAP {domain_name=domain_name
        #                    profile=profile_name profile_server=ip_address
        #                    proxy_dn="proxy_bind_dn" proxy_password=password}
        #
        # domain_name - profile_name Specifies the name of the LDAP profile you
        #       want to use to configure the system.
        # profile
        # profile_server
        # proxy_bind_dn (Optional) - Specifies the proxy bind distinguished
        #       name. You must enclose the proxy_bind_dn value in
        #       double quotes.
        #
        # proxy_password (Optional) - Specifies the client proxy password
        #

        #domain_name = payload.pop("domain_name", None)
        #profile_name = payload.pop("profile", None)
        #profile_server = payload.pop("ip_address", None)
        #proxy_bind_dn = payload.pop("proxy_bind_dn", None)
        #password = payload.pop("proxy_password", None)

        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "name service specified. DNS or NONE is currently"
                            " the only supported name servce selection.") % \
                            {"file": SYSIDCFG_FILENAME, \
                             "lineno": line_num})
        self._report.add_unsupported_item()

    name_service_conversion_dict = {
        "NIS": __convert_name_service_nis,
        "NIS+": __convert_name_service_nisplus,
        "DNS": __convert_name_service_dns,
        "LDAP": __convert_name_service_ldap,
        "NONE": __convert_name_service_none,
        }

    def __convert_name_service(self, line_num, keyword, values):
        """Converts the name_service keyword/values specified in the sysidcfg
        statement to the proper xml output for the Solaris configuration
        file for the auto installer.

        """
        if self._name_service is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return

        name_service = values[0].upper()
        length = len(values)
        if length == 1:
            payload = None
        else:
            payload = values[1]
        try:
            function_to_call = \
                self.name_service_conversion_dict[name_service]
        except KeyError:
            self.logger.error(_("%(file)s: line %(lineno)d: unrecognized "
                                "unsupported name service specified: "
                                "%(service)s") % \
                                {"file": SYSIDCFG_FILENAME, \
                                 "lineno": line_num,
                                 "service": values[0]})
            self._report.add_process_error()
        else:

            # The user specified to overide current default name service
            # Remove any existing ones from the xml tree we are working
            # against
            self.__remove_selected_children(self._service_bundle,
                                            "/network/*/install")
            function_to_call(self, line_num, keyword, payload)

    def __configure_network_interface_none(self, line_num, payload):
        """Configure the network interface to None"""
        # output form:
        #
        # network_interface=None {hostname=hostname}
        #
        # <service name="system/install/config" version="1" type="service">
        #   <instance name="default" enabled="true">
        #   ..
        #     <property_group name="other_sc_params" type="application">
        #       <propval name="hostname" type="astring" value="opensolaris"/>
        #     </property_group>
        #   </instance>
        # </service>

        # <service name='network/physical' version='1' type='service'>
        #   <instance name='default' enabled='true'/>
        #   <instance name='nwam' enabled='false'/>
        # </service>
        #
        # NOTICE that default should be enabled.  This only configures
        # the loopback interface, which is equivalent to what the text
        # installer does today one selects 'None' on Network screen.
        #

        self.__create_network_interface(nwam_setting=False,
                                        default_setting=True)

        # Are there any more keys left in the dictionary that we need to flag
        self.__check_payload(line_num, "network_interface=NONE", payload)

        # If there are any other interfaces defined flag them as errors
        for network in self._defined_net_interfaces:
            line_num = network[0]
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "network interface, NONE interface "
                                "previously defined, ignoring") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": network[0]})
            self._report.add_process_error()

    def __configure_network_interface_primary(self, line_num, payload):
        """Converts the network_interface keyword/values from the sysidcfg into
        the appropriate equivalent Solaris xml configuration

        """
        # Solaris installer:
        #
        # The only support we can provide in Solaris for PRIMARY is
        # via nwam and DHCP.  Not a perfect match but it's the best fit
        #
        self.__create_network_interface(nwam_setting=True,
                                        default_setting=False)

        # Do we have a payload to configure
        if payload is None or len(payload) == 0:
            # Nothing left to do
            pass
        else:
            dhcp = payload.pop("dhcp", None)
            ipv6 = payload.pop("protocol_ipv6", None)
            if dhcp is not None:
                if ipv6 is None or ipv6 == "yes":
                    # This configuration is 100% compatible
                    # with the default behavior of NWAM
                    pass
                else:
                    self.logger.error(
                        _("%(file)s: line %(lineno)d: when the "
                          "PRIMARY interface is specified, by default the "
                          "system will be configured for both IPv4 and IPv6 "
                          "via NWAM. Disabling IPv6 is not supported.  If "
                          "you wish to ensure that that only IPv4 is "
                          "configured it will be necessary to replace "
                          "the PRIMARY option with the interface you "
                          "wish to configure.") % \
                          {"file": SYSIDCFG_FILENAME, \
                           "lineno": line_num})
                    self._report.add_conversion_error()

                if len(payload) != 0:
                    self.logger.error(
                        _("%(file)s: line %(lineno)d: unexpected "
                          "option(s) specified. If you are using the "
                          "dhcp option, the only other option you "
                          "can specify is protocol_ipv6.") % \
                          {"file": SYSIDCFG_FILENAME, \
                           "lineno": line_num})
                    self._report.add_process_error()
            else:  # dhcp is None

                # Although we don't use the next values remove them from the
                # payload so we can do a syntax check for extra unsupported
                # args. We don't validate these. If the user switches to the
                # interface from PRIMARY to an another interface then we'll
                # validate them
                ip_address = payload.pop("ip_address", None)
                netmask = payload.pop("netmask", None)
                default_route = payload.pop("default_route", None)

                self.logger.error(
                    _("%(file)s: line %(lineno)d: when the "
                      "PRIMARY interface is specified, by default the "
                      "system will be configured for both IPv4 and IPv6 "
                      "via NWAM.  The options specified will be ignored. "
                      "If you wish to configure the interface with the "
                      "specified options replace PRIMARY with the name of the "
                      "interface that should be configured.") % \
                    {"file": SYSIDCFG_FILENAME, \
                     "lineno": line_num})
                self._report.add_conversion_error()

                # Are there any more keys left in the dict that we need to flag
                self.__check_payload(line_num,
                                     "network_interface=PRIMARY", payload)

        # If there are any other interfaces defined flag them as errors
        for network in self._defined_net_interfaces:
            line_num = network[0]
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "network interface, PRIMARY network interface "
                                "previously defined, ignoring") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num})
            self._report.add_process_error()

    def __configure_network_physical_ipv4(self, line_num, interface, payload):
        """Configures the IPv4 interface for the interface specified by the
        user by generating the proper xml structure used by the Solaris
        auto installer

        """
        if payload is None or len(payload) == 0:
            return

        primary = payload.pop("primary", None)
        if primary is not None:
            self.logger.error(_("%(file)s: line %(lineno)d: defining an "
                                "interface as primary is not supported, "
                                "ignorning setting") %
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num})
            self._report.add_unsupported_item()

        ip_address = payload.pop("ip_address", None)
        if ip_address is not None:
            if not self.__is_valid_ip(line_num, ip_address, _("ip address")):
                return

        netmask = payload.pop("netmask", None)
        if netmask is not None:
            if not self.__is_valid_ip(line_num, netmask, _("netmask")):
                return

        default_route = payload.pop("default_route", None)
        if default_route is not None and default_route.lower() != "none":
            if not self.__is_valid_ip(line_num, default_route,
                                      _("default route")):
                # Unlike ip_address and netmask if the default route has
                # an error go ahead and create network entry
                default_route = None

        # For Solaris we have to create get the CIDR for the netmask
        # and combine it with the ip_address
        if ip_address is None and netmask is None:
            address = None
        elif ip_address is not None and netmask is not None:
            address = IPAddress(ip_address, netmask)
        else:
            address = None

        if address is None:
            self.logger.error(_("%(file)s: line %(lineno)d: unable to "
                                "complete configuration of IPv4 interface for "
                                "'%(interface)s', values must be specified for"
                                " both ip_address and netmask.  Configuring"
                                " system for NWAM") %
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num,
                                 "interface": interface})
            self._report.add_conversion_error()

            # Since we only support a single interface at this time, we want
            # to make the system usable.  To ensure that we will use NWAM
            # we clear _default_network since it may have been set in the
            # creation of a IPv6 network.  This is the key we use to determine
            # whether or not to create a NWAM or default network
            #
            # At the point in time when the installer supports multiple network
            # interfaces this should be removed and a simple check of
            # whether there are any defined networks should be performed.
            #
            self._default_network = None
            return

        # output form example:
        #
        # <service name="network/install" version="1" type="service">
        #   <instance name="default" enabled="true">
        #     <property_group name='install_ipv4_interface' type='application'>
        #       <propval name='name' type='astring' value='bge0/v4'/>
        #       <propval name='address_type' type='astring' value='static'/>
        #       <propval name='static_address' type='net_address_v4'
        #                value='10.0.0.10/8'/>
        #       <propval name='default_route' type='net_address_v4'
        #                value='10.0.0.1'/>
        #     </property_group>
        #   </instance>
        # </service>
        if self._default_network is None:
            network_install = self.__create_service_node(self._service_bundle,
                                                         "network/install")
            self._default_network = \
                self.__create_instance_node(network_install, "default")

        ipv4_network = \
            self.__create_propgrp_node(self._default_network,
                                       "install_ipv4_interface",
                                       TYPE_APPLICATION)
        self.__create_propval_node(ipv4_network, "name", TYPE_ASTRING,
                                    interface + "/v4")
        self.__create_propval_node(ipv4_network, "address_type",
                                    TYPE_ASTRING, "static")
        if address is not None:
            self.__create_propval_node(ipv4_network, "static_address",
                                        TYPE_NET_ADDRESS_V4,
                                        address.get_address())
        if default_route is not None and default_route.lower() != "none":
            self.__create_propval_node(ipv4_network, "default_route",
                                        TYPE_NET_ADDRESS_V4, default_route)

    def __configure_network_interface_dhcp(self, line_num, interface, payload):
        """Configures the specified interface as dhcp for ipv4 and ipv6 (if
        specified)

        """

        # output form example:
        #
        # <service name="network/install" version="1" type="service">
        #    <instance name="default" enabled="true">
        #      <property_group name="install_ipv4_interface"
        #               type="application">
        #        <propval name="name" type="astring" value="nge0/v4"/>
        #        <propval name="address_type" type="astring" value="dhcp"/>
        #      </property_group>
        #      <property_group name="install_ipv6_interface"
        #               type="application">
        #        <propval name="name" type="astring" value="nge0/v6"/>
        #        <propval name="address_type" type="astring" value="dhcp"/>
        #        <propval name="stateless" type="astring" value="yes"/>
        #        <propval name="stateful" type="astring" value="yes"/>
        #      </property_group>
        #    </instance>
        # </service>
        # <service name="network/physical" version="1" type="service">
        #    <instance name="nwam" enabled="false"/>
        #    <instance name="default" enabled="true"/>
        # </service>
        #
        if self._default_network is None:
            network_install = self.__create_service_node(self._service_bundle,
                                                         "network/install")
            self._default_network = \
                self.__create_instance_node(network_install, "default")

        ipv4_network = \
            self.__create_propgrp_node(self._default_network,
                                       "install_ipv4_interface",
                                       TYPE_APPLICATION)
        self.__create_propval_node(ipv4_network, "name", TYPE_ASTRING,
                                    interface + "/v4")
        self.__create_propval_node(ipv4_network, "address_type",
                                    TYPE_ASTRING, "dhcp")

        # if ipv6 was specified add it
        ipv6 = payload.pop("protocol_ipv6", "no")
        if ipv6.lower() == "yes":
            self.__configure_network_physical_ipv6(interface, True)
        if len(payload) != 0:
            self.logger.error(_("%(file)s: line %(lineno)d: unexpected "
                                "option(s) specified. If you are using the "
                                "dhcp option, the only other option you "
                                "can specify is protocol_ipv6.") % \
                            {"file": SYSIDCFG_FILENAME, \
                            "lineno": line_num})
            self._report.add_process_error()
            return

        # Create default network
        self.__create_network_interface(nwam_setting=False,
                                        default_setting=True)

    def __configure_network_physical_ipv6(self, interface, dhcp=False):
        """Configures the IPv6 interface for the interface specified by the
        user by generating the proper xml structure used by the Solaris
        auto installer

        """
        # output form:
        #
        # <service name="network/install" version="1" type="service">
        #   <instance name="default" enabled="true">
        #   <property_group name="install_ipv6_interface" type="application">
        #       <propval name="name" type="astring" value="net0/v6"/>
        #       <propval name="address_type" type="astring" value="xxxx"/>
        #       <propval name="stateless" type="astring" value="yes"/>
        #       <propval name="stateful" type="astring" value="yes"/>
        #   </property_group>
        #   </instance>
        # </service>
        #
        # where xxxx is addrconf or dhcp
        #
        if self._default_network is None:
            network_install = self.__create_service_node(self._service_bundle,
                                                         "network/install")
            self._default_network = \
                self.__create_instance_node(network_install, "default")

        ipv6_interface = \
            self.__create_propgrp_node(self._default_network,
                                       "install_ipv6_interface",
                                       TYPE_APPLICATION)
        self.__create_propval_node(ipv6_interface, "name", TYPE_ASTRING,
                                    interface + "/v6")
        if dhcp:
            address_type = "dhcp"
        else:
            address_type = "addrconf"
        self.__create_propval_node(ipv6_interface, "address_type",
                                    TYPE_ASTRING, address_type)
        self.__create_propval_node(ipv6_interface, "stateless",
                                    TYPE_ASTRING, "yes")
        self.__create_propval_node(ipv6_interface, "stateful",
                                    TYPE_ASTRING, "yes")

    def __configure_network_interface(self):
        """Converts the network_interface keyword/values from the sysidcfg into
        the new xml format

        """
        if len(self._defined_net_interfaces) == 0:
            # User didn't define any network interfaces.  Make sure the
            # default_xml object has a defined network interface.  If not
            # create one
            # Setup a nwam interface
            svc_network_physical = \
                fetch_xpath_node(self._service_bundle,
                                 "./service[@name='network/physical']")
            if svc_network_physical is None:
                # Create NWAM network
                self.__create_network_interface(nwam_setting=True,
                                                default_setting=False)
            return

        # The user specified one or more network
        # This means we want to override all network information
        # in the default_xml object.
        self.__remove_selected_children(self._service_bundle,
                                        "/network/install")

        network = self._defined_net_interfaces.pop(0)
        line_num = network[0]
        interface = network[1].lower()
        payload = network[2]
        if payload is not None:
            hostname = payload.pop("hostname", None)
            if hostname is not None:
                self.__convert_hostname(line_num, hostname)
        if interface == "none":
            self.__configure_network_interface_none(line_num, payload)
            return
        elif interface == "primary":
            self.__configure_network_interface_primary(line_num, payload)
            return
        if payload is None or len(payload) == 0:
            self.logger.error(_("%(file)s: line %(lineno)d: unsupported  "
                                "configuration.  Configuring"
                                " system for NWAM") %
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num})
            self._report.add_unsupported_item()
            # Create NWAM network
            self.__create_network_interface(nwam_setting=True,
                                            default_setting=False)
            return
        else:
            dhcp = payload.pop("dhcp", None)
            if dhcp is not None:
                self.__configure_network_interface_dhcp(line_num, interface,
                                                        payload)
                return
            ipv6 = payload.pop("protocol_ipv6", "no")
            if ipv6.lower() == "yes":
                self.__configure_network_physical_ipv6(interface)

            self.__configure_network_physical_ipv4(line_num, interface,
                                               payload)

            # Are there any more keys left in the dict that we need to flag
            self.__check_payload(line_num, "network_interface", payload)

        # Currently the installer only supports a single NIC interface
        # so we need to flag any additional ones as unsupported
        for network in self._defined_net_interfaces:
            line_num = network[0]
            interface = network[1]
            self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                                "network interface '%(interface)s', installer "
                                "currently only supports configuring a single "
                                "interface") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num,
                                 "interface": interface})
            self._report.add_unsupported_item()

        # Make sure we have at least 1 network interface configured
        if self._default_network is None:
            # Nothing is configured, which means the users choices errored out
            # Since we always want a network configured, we configure for NWAM
            self.__create_network_interface(nwam_setting=True,
                                            default_setting=False)
        else:
            # Configure for default network
            self.__create_network_interface(nwam_setting=False,
                                            default_setting=True)

    def __convert_nfs4_domain(self, line_num, keyword, values):
        """Converts the nfs4_domain keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg syntax:
        #   nfs4_domain=dynamic
        #       or custom_domain_name like
        #   nfs4_domain=example.com
        #
        # SCI Doc states:
        #   Legacy sysid tools provide configuration screens for configuring
        #   kerberos and NFSv4 domain. SCI tool will not support configuration
        # of those areas.
        self.__unsupported_keyword(line_num, keyword, values)

    def __convert_root_password(self, line_num, keyword, values):
        """Converts the root_passord keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg syntax:
        #   root_password=encrypted_password
        #
        # Possible values are encrypted from /etc/shadow.
        #
        # convert to:
        #
        # <service name="system/install/config" version="1" type="service">
        #   <instance name="default" enabled="true">
        #       <property_group name="root_account" type="application">
        #           <propval name="password" type="astring"
        #                    value="9Nd/cwBcNWFZg"/>
        #       </property_group>
        #   </instance>
        # </service>
        if self._root_prop_group is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return

        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        self._root_prop_group = \
            self.__fetch_sys_install_config_prpgrp("root_account")
        for child in self._root_prop_group:
            self._root_prop_group.remove(child)
        self.__create_propval_node(self._root_prop_group, "password",
                                   TYPE_ASTRING, values[0])

    def __convert_security_policy(self, line_num, keyword, values):
        """Converts the security_policy keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg syntax:
        #
        # security_policy=kerberos {default_realm=FQDN
        #       admin_server=FQDN kdc=FQDN1, FQDN2, FQDN3}
        #
        # or
        #
        # security_policy=NONE
        #
        # SCI Doc states:
        #   Legacy sysid tools provide configuration screens for configuring
        #   kerberos and NFSv4 domain. SCI tool will not support configuration
        #   of those areas.
        #
        # If the security policy is anything other than None indicate to the
        # user that this setting is not supported or it's invalid
        policy = values[0].lower()
        if policy == "none":
            # Nothing to do
            return
        elif policy == "kerberos":
            self.logger.error(_("%(file)s: line %(line_num)d: unsupported "
                                "security policy of kerberos specified. Only "
                                "a value of 'NONE' is supported." %
                                {"file": SYSIDCFG_FILENAME,
                                 "line_num": line_num}))
            self._report.add_unsupported_item()
        else:
            self.__invalid_syntax(line_num, keyword)

    def __convert_service_profile(self, line_num, keyword, values):
        """Converts the service_profile keyword/values from the sysidcfg into
        the new xml format

        """
        #
        # Valid values:
        #   service_profile=limited_net
        #   service_profile=open
        #
        # limited_net specifies that all network services, except for Secure
        # Shell, are either disabled or constrained to respond to local
        # requests only. After installation, any individual network service
        # can be enabled by using the svcadm and svccfg commands.
        # open specifies that no network service changes are made during
        # installation.
        #
        # If the service_profile keyword is not present in the sysidcfg file,
        # no changes are made to the status of the network services during
        # installation.
        #
        if self._service_profile is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return

        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        self._service_profile = values[0]

        if self._service_profile == "limited_net":
            # This is what Solaris installer does by default so no change
            # is needed to make this occur
            pass
        elif self._service_profile == "open":
            # TODO: Add reference to man page that tells user the steps of
            # how to do this
            self.logger.error(_("%(file)s: line %(line_num)d: the service "
                                "profile option 'open' is not available. "
                                "The system will be configured with "
                                "'service_profile=limited_net'. Additional "
                                "services can be enabled later in the "
                                "System Configuration manifest.") %
                                {"file": SYSIDCFG_FILENAME,
                                 "line_num": line_num})
            self._report.add_unsupported_item()
        else:
            self.__invalid_syntax(line_num, keyword)

    def __convert_system_locale(self, line_num, keyword, values):
        """Converts the system_locale keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg syntax:
        #   system_locale=locale
        #
        # where locale is /usr/lib/locale (Solaris 10).
        #
        #
        self.__unsupported_keyword(line_num, keyword, values)

    def __convert_terminal(self, line_num, keyword, values):
        """Converts the terminal keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg syntax:
        #   terminal=terminal_type
        #
        # where terminal_type is a value from /usr/share/lib/terminfo/* on
        # Solaris 10.
        #
        # convert to:
        #
        # <service name="system/console-login" version="1" type="service">
        #   <property_group name="ttymon" type="application">
        #       <propval name="terminal_type" type="astring" value="vt100"/>
        #   </property_group>
        # </service>

        if self._terminal is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return

        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        svc_console_login = \
            fetch_xpath_node(self._service_bundle,
                             "./service[@name='system/console-login']")
        if svc_console_login is None:
            svc_console_login = \
                self.__create_service_node(self._service_bundle,
                                           "system/console-login")
        prp_group = fetch_xpath_node(svc_console_login,
                                     "./property_group[@name='ttymon']")
        if prp_group is None:
            prp_group = self.__create_propgrp_node(svc_console_login,
                                                   "ttymon", TYPE_APPLICATION)
        self._terminal = \
            fetch_xpath_node(prp_group, "propval[@name='terminal_type']")
        if self._terminal is None:
            self.__create_propval_node(prp_group, "terminal_type",
                                       TYPE_ASTRING, values[0])

    def __convert_timeserver(self, line_num, keyword, values):
        """Converts the timeserver keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg format:
        #   timeserver=localhost
        #   timeserver=hostname
        #   timeserver=ip_address
        #
        # Timezone is part of the install config service.  Convert to:
        #
        # <service name="system/install/config" version="1" type="service">
        #   ....
        #   <instance name="default" enabled="true">
        #     <property_group name="other_sc_params" type="application">
        #       <propval name="timeserver" type="astring" value="hostname"/>
        #       ....
        #     </property_group>
        #   </instance>
        # </service>
        #

        if self._timeserver is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return

        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        if values[0] != "localhost":
            self.logger.error(_("%(file)s: line %(line_num)d: unsupported "
                                "timeserver value of '%(setting)s' specified. "
                                "Only a value of 'localhost' is supported.") %
                                {"file": SYSIDCFG_FILENAME,
                                 "line_num": line_num,
                                 "setting": values[0]})
            self._report.add_unsupported_item()

    def __convert_timezone(self, line_num, keyword, values):
        """Converts the timezone keyword/values from the sysidcfg into
        the new xml format

        """
        # sysidcfg format:
        #   timezone=timezone
        #
        # Timezone is part of the install config service.  Convert to:
        #
        # <service name="system/install/config" version="1" type="service">
        #   ....
        #   <instance name="default" enabled="true">
        #     <property_group name="other_sc_params" type="application">
        #       <propval name="timezone" type="astring" value="GMT"/>
        #       ....
        #     </property_group>
        #   </instance>
        # </service>
        #

        if self._timezone is not None:
            # Generate duplicate keyword
            self.__duplicate_keyword(line_num, keyword, values)
            return
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return

        other_sc_params = \
            self.__fetch_sys_install_config_prpgrp("other_sc_params")
        self._timezone = \
            fetch_xpath_node(other_sc_params, "propval[@name='timezone']")
        if self._timezone is not None:
            self._timezone.set(common.ATTRIBUTE_VALUE, values[0])
        else:
            self._timezone = self.__create_propval_node(other_sc_params,
                                                        "timezone",
                                                        TYPE_ASTRING,
                                                        values[0])

    def __create_instance_node(self, parent, name="default",
                               enabled_state="true"):
        """Create a <instance> node with a parent of 'parent'

        <instance name="name" enabled="enabled_state">

        """
        node = etree.SubElement(parent, common.ELEMENT_INSTANCE)
        node.set(common.ATTRIBUTE_NAME, name)
        node.set(common.ATTRIBUTE_ENABLED, enabled_state)
        return node

    def __create_network_interface(self, nwam_setting, default_setting):
        """Create the nwam and default network node settings

        <service name='network/physical' version='1' type='service'>
          <instance name='default' enabled='default_settings'/>
          <instance name='nwam' enabled='nwam_settings'/>
        </service>

        """
        service = fetch_xpath_node(self._service_bundle,
                                   "./service[@name='network/physical']")
        if service is not None:
            self.__remove_children(service)
        else:
            service = self.__create_service_node(self._service_bundle,
                                                "network/physical")
        self.__create_instance_node(service, "nwam", str(nwam_setting).lower())
        self.__create_instance_node(service, "default",
                                    str(default_setting).lower())

    def __create_prop_node(self, parent, name, prop_type):
        """Create a <property> node with a parent of 'parent'

        <property name="name" type="prop_type">

        """
        node = etree.SubElement(parent, common.ELEMENT_PROPERTY)
        node.set(common.ATTRIBUTE_NAME, name)
        node.set(common.ATTRIBUTE_TYPE, prop_type)
        return node

    def __create_propgrp_node(self, parent, name, propgrp_type):
        """Create a <property_group> node with a parent of 'parent'

        <property_group name="name" type="propgrp_type">

        """
        node = etree.SubElement(parent, common.ELEMENT_PROPERTY_GROUP)
        node.set(common.ATTRIBUTE_NAME, name)
        node.set(common.ATTRIBUTE_TYPE, propgrp_type)
        return node

    def __create_propval_node(self, parent, name, propval_type, value):
        """Create a <propval> node with a parent of 'parent'

        <propval name="name" type="propval_type" value="value"/>

        """
        node = etree.SubElement(parent, common.ELEMENT_PROPVAL)
        node.set(common.ATTRIBUTE_NAME, name)
        node.set(common.ATTRIBUTE_TYPE, propval_type)
        node.set(common.ATTRIBUTE_VALUE, value)
        return node

    def __create_service_node(self, parent, name, version="1",
                              service_type=TYPE_SERVICE):
        """Create a <service> node with a parent of 'parent'

        <service name="name" version="1" type="service">

        """
        service = etree.SubElement(parent, common.ELEMENT_SERVICE)
        service.set(common.ATTRIBUTE_NAME, name)
        service.set(common.ATTRIBUTE_VERSION, version)
        service.set(common.ATTRIBUTE_TYPE, service_type)
        return service

    def __create_value_node(self, parent, value):
        """Create a node with a value attribute set to 'value'"""
        node = etree.SubElement(parent, common.ELEMENT_VALUE_NODE)
        node.set(common.ATTRIBUTE_VALUE, value)
        return node

    def __duplicate_keyword(self, line_num, keyword, values):
        """Generate a duplicate keyword error"""
        self.logger.error(_("%(file)s: line %(lineno)d: invalid entry, "
                            "duplicate keyword encountered: %(key)s") % \
                            {"file": SYSIDCFG_FILENAME,
                             "lineno": line_num, \
                             "key": keyword})
        self._report.add_process_error()

    def __fetch_sys_install_config_instance(self):
        """Fetch system install config node from tree if it exist, otherwise
        create it.

        <service name="system/install/config" type="service" version="1">

        """
        if self._svc_install_config is None:
            xpath = ("./service[@name='system/install/config']"
                     "[@type='service'][@version='1']")
            self._svc_install_config = \
                fetch_xpath_node(self._service_bundle, xpath)
        if self._svc_install_config is None:
            self._svc_install_config = \
                self.__create_service_node(self._service_bundle,
                                           "system/install/config")
        instance = fetch_xpath_node(self._svc_install_config,
                                          "./instance[@name='default']")
        if instance is None:
            instance = self.__create_instance_node(self._svc_install_config)
        return instance

    def __fetch_sys_install_config_prpgrp(self, name):
        """From the system/install/config service fetch the property group
        specified by 'name'

        """
        instance = self.__fetch_sys_install_config_instance()
        xpath = "./property_group[@name='{grp_name}']".format(grp_name=name)
        other = fetch_xpath_node(instance, xpath)
        if other is None:
            other = self.__create_propgrp_node(instance, name,
                                               TYPE_APPLICATION)
        return other

    def __invalid_syntax(self, line_num, keyword):
        """Generate an invalid syntax error"""
        self.logger.error(_("%(file)s: line %(lineno)d: invalid syntax "
                            "for keyword '%(key)s' specified") % \
                            {"file": SYSIDCFG_FILENAME, \
                             "lineno": line_num, "key": keyword})
        self._report.add_process_error()

    def __is_valid_hostname(self, hostname):
        """Perform a basic validation of the hostname
        Return True if valid, False otherwise

        """
        if len(hostname) > MAXHOSTNAMELEN:
            return False
        # A single trailing dot is legal
        # strip exactly one dot from the right, if present
        if hostname.endswith("."):
            hostname = hostname[:-1]
        disallowed = re.compile("[^A-Z\d-]", re.IGNORECASE)

        # Split by labels and verify individually
        return all(
            (label and len(label) <= 63         # length is within proper range
             and not label.startswith("-")
             and not label.endswith("-")        # no bordering hyphens
             and not disallowed.search(label))  # contains only legal chars
            for label in hostname.split("."))

    def __is_valid_ip(self, line_num, ip_address, label):
        """Check ipaddress.  If not valid flag with appropriate error msg"""
        try:
            IPAddress.incremental_check(ip_address)
        except ValueError:
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "%(label)s specified '%(ip)s'") % \
                                {"file": SYSIDCFG_FILENAME,
                                 "lineno": line_num,
                                 "label": label,
                                 "ip": ip_address})
            self._report.add_conversion_error()
            return False
        return True

    def __remove_children(self, parent):
        """Remove all children from the parent xml node"""
        if parent is not None:
            for child in parent:
                parent.remove(child)

    def __remove_selected_children(self, parent, xpath):
        """Remove the children from the parent that match the specified xpath

        """
        entries = parent.xpath(xpath)
        for entry in entries:
            parent.remove(entry)

    def __store_network_interface(self, line_num, keyword, values):
        """Store the network interface information for later processing"""
        # sysidcfg syntax:
        #
        # network_interface=NONE, PRIMARY, value
        #
        # where value is a name of a network interface, for example, eri0 or
        # hme0.
        #
        # For the NONE keyword, the options are:
        #
        # hostname=hostname
        #
        # For example,
        #
        # network_interface=NONE {hostname=feron}
        #
        # For the PRIMARY and value keywords, the options are:
        #
        #   primary (used only with multiple network_interface lines)
        #   dhcp
        #   hostname=hostname
        #   ip_address=ip_address
        #   netmask=netmask
        #   protocol_ipv6=yes | no
        #   default_route=ip_address (IPv4 address only)
        #
        # If you are using the dhcp option, the only other option you can
        # specify is protocol_ipv6. For example:
        #
        #   network_interface=PRIMARY {dhcp protocol_ipv6=yes}
        #
        # If you are not using DHCP, you can specify any combination of the
        # other keywords as needed. If you do not use any of the keywords,
        # omit the curly braces.
        #
        #   network_interface=eri0 {hostname=feron
        #   	ip_address=172.16.2.7
        #    	netmask=255.255.255.0
        #    	protocol_ipv6=no
        #   	default_route=172.16.2.1}
        #
        interface = values[0]
        length = len(values)
        if length == 1:
            payload = None
        else:
            payload = values[1]
        data = (line_num, interface, payload)
        self._defined_net_interfaces.append(data)

    @property
    def tree(self):
        """Return the xml tree associated with this object"""
        return self._tree

    def __unsupported_keyword(self, line_num, keyword, values):
        """Generate an unsupported keyword error"""
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "keyword: %(key)s") % \
                            {"file": SYSIDCFG_FILENAME, \
                             "lineno": line_num, \
                             "key": keyword})
        self._report.add_unsupported_item()

    # The SCI design doc states:
    #   Legacy sysid tools provide configuration screens for configuring
    #   kerberos and NFSv4 domain. SCI tool will not support configuration
    #   of those areas.
    # Therefore we can't support "security_policy" and "nfs4_domain"
    sysidcfg_conversion_dict = {
        "keyboard": __convert_keyboard,
        "name_service": __convert_name_service,
        "nfs4_domain": __unsupported_keyword,
        "network_interface": __store_network_interface,
        "root_password": __convert_root_password,
        "security_policy": __convert_security_policy,
        "service_profile": __convert_service_profile,
        "system_locale": __convert_system_locale,
        "terminal": __convert_terminal,
        "timeserver": __convert_timeserver,
        "timezone": __convert_timezone,
        }

    def __process_sysidcfg(self):
        """Process the profile by taking all keyword/values pairs and
           generating the associated xml for the key value pairs
        """
        if self.sysidcfg_dict is None or len(self.sysidcfg_dict) == 0:
            # There's nothing to convert.  This is a valid condition if
            # the file couldn't of been read for example
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            return

        self._service_bundle = \
            fetch_xpath_node(self._tree,
                             "/service_bundle[@type='profile']")

        if self._service_bundle is None:
            tree = etree.parse(StringIO(SVC_BUNDLE_XML_DEFAULT))
            expected_layout = etree.tostring(tree, pretty_print=True,
                        encoding="UTF-8")
            raise ValueError(_("Specified default xml file does not conform to"
                               " the expected layout of:\n%(layout)s") %
                               {"layout": expected_layout})

        keys = sorted(self.sysidcfg_dict.keys())
        for key in keys:
            key_value_obj = self.sysidcfg_dict[key]
            if key_value_obj is None:
                raise ValueError

            keyword = key_value_obj.key.lower()
            value = key_value_obj.values
            line_num = key_value_obj.line_num
            if line_num is None or value is None or keyword is None:
                raise ValueError

            try:
                function_to_call = self.sysidcfg_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(line_num, keyword, value)
            else:
                function_to_call(self, line_num, keyword, value)

        # All the elements have been processed at this point in time.
        self.__configure_network_interface()

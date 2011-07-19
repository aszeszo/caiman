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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Class and functions supporting representing a NIC and locating
the NICs installed on the system by name (using dladm)
'''

import logging
from solaris_install import Popen, CalledProcessError
from solaris_install.data_object import DataObject
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile.ip_address import IPAddress
from solaris_install.sysconfig.profile.nameservice_info import NameServiceInfo
from solaris_install.sysconfig.profile import SMFConfig, SMFInstance, \
     SMFPropertyGroup, NETWORK_LABEL


_LOGGER = None


def LOGGER():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
    return _LOGGER


class NetworkInfo(SMFConfig):
    '''Represents a NIC and its network settings'''

    AUTOMATIC = "automatic"
    MANUAL = "manual"
    NONE = "none"
    DEFAULT_NETMASK = "255.255.255.0"

    ETHER_NICS = None

    LABEL = NETWORK_LABEL

    @staticmethod
    def find_links():
        '''Use dladm show-link to find available network interfaces (NICs).
        Filter out NICs with 'allow-address' mandated from global zone
        (this type of NIC can be configured for non-global zone with exclusive
        IP stack), since those kind of NICs are controlled from global zone
        and can't be configured within non-global zone.
        '''

        if NetworkInfo.ETHER_NICS is not None:
            return NetworkInfo.ETHER_NICS
        
        argslist = ['/usr/sbin/dladm', 'show-link', '-o', 'link', '-p']

        try:
            dladm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                           stderr=Popen.STORE, logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'dladm show-link -o link -p' "
                          "failed with following error: %s", error)

            return []

        nic_list = dladm_popen.stdout.strip()

        #
        # pylint: disable-msg=E1103
        # nic_list is a string
        # Start with empty list of NICs and add those which are eligible
        # for configuration.
        #
        NetworkInfo.ETHER_NICS = []
        all_nics = nic_list.splitlines()

        for nic in all_nics:
            argslist = ['/usr/sbin/dladm', 'show-linkprop', '-c', '-p',
                        'allowed-ips', '-o', 'value', nic]

            try:
                dladm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                               stderr=Popen.STORE,
                                               logger=LOGGER())
            except CalledProcessError as error:
                LOGGER().warn("'dladm show-linkprop -c -p allowed-ips -o "
                              "value' failed with following error: %s", error)
                continue

            allowed_ips = dladm_popen.stdout.strip()

            #
            # If vanity name exists for link, use it.
            #
            argslist = ['/usr/sbin/dladm', 'show-phys', '-L', '-o',
                        'vanity', '-p', nic]
            try:
                dladm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                               stderr=Popen.STORE,
                                               logger=LOGGER())
            except CalledProcessError:
                n = nic
            else:
                n = dladm_popen.stdout.strip()
                #
                # It was observed that in some cases (e.g. in non-global
                # zone with exclusive IP stack) dladm reports success, but
                # returns empty string. Use non-vanity NIC name in that case.
                #
                if not n:
                    n = nic

            #
            # Add particular NIC to the list if 'allowed-ips' link property
            # is not configured (is empty).
            #
            LOGGER().info("%s allowed-ips: <%s>" % (n, allowed_ips))
            if not allowed_ips:
                NetworkInfo.ETHER_NICS.append(n)

        # sort the final list
        NetworkInfo.ETHER_NICS.sort()
        return NetworkInfo.ETHER_NICS

    def __init__(self, nic_name=None, net_type=None, ip_address=None,
                 netmask=None, gateway=None, dns_address=None, domain=None):
        DataObject.__init__(self, self.LABEL)

        self.nic_name = nic_name
        self.type = net_type
        self.ip_address = ip_address
        if netmask is None:
            netmask = NetworkInfo.DEFAULT_NETMASK
        self.netmask = netmask
        self.gateway = gateway
        self.dns_address = dns_address
        self.domain = domain
        self.find_defaults = True

    def __repr__(self):
        result = ["NIC %s:" % self.nic_name]
        result.append("Type: %s" % self.type)
        if self.type == NetworkInfo.MANUAL:
            result.append("IP: %s" % self.ip_address)
            result.append("Netmask: %s" % self.netmask)
            result.append("Router: %s" % self.gateway)
            result.append("DNS: %s" % self.dns_address)
            result.append("Domain: %s" % self.domain)
        return "\n".join(result)

    # pylint: disable-msg=E0202
    @property
    def type(self):
        return self._type

    # pylint: disable-msg=E1101
    # pylint: disable-msg=E0102
    # pylint: disable-msg=E0202
    @type.setter
    def type(self, value):
        if value not in [NetworkInfo.AUTOMATIC, NetworkInfo.MANUAL,
                         NetworkInfo.NONE, None]:
            raise ValueError("'%s' is an invalid type."
                             "Must be one of %s" % (value,
                             [NetworkInfo.AUTOMATIC, NetworkInfo.MANUAL,
                              NetworkInfo.NONE]))
        # pylint: disable-msg=W0201
        self._type = value

    def find_dns(self):
        '''Try to determine the DNS info of the NIC if DHCP is running
        Returns True if this action was successful
        
        '''
        dns_server = self._run_dhcpinfo("DNSserv",
                                        maxent=NameServiceInfo.MAXDNSSERV)
        if dns_server:
            self.dns_address = dns_server.splitlines()
            return True
        else:
            return False

    def find_gateway(self):
        '''Try to determine the router of the NIC if DHCP is running
        Returns True if this action was successful

        '''
        gateway = self._run_dhcpinfo("Router")
        if gateway:
            self.gateway = gateway
            return True
        else:
            return False

    def find_domain(self):
        '''Try to determine the domain info of the NIC if DHCP is running
        Returns True if this action was successful

        '''
        domain = self._run_dhcpinfo("DNSdmain")
        if domain:
            self.domain = domain
            return True
        else:
            return False

    def find_netmask(self):
        '''Try to determine the netmask info of the NIC if DHCP is running
        Returns True if this action was successful

        '''
        netmask = self._run_dhcpinfo("Subnet")
        if netmask:
            self.netmask = IPAddress(netmask)
            return True
        else:
            return False

    def get_ifconfig_data(self):
        '''Returns a dictionary populated with the data returned from ifconfig
        Returns None if the call to ifconfig fails in some way

        '''
        argslist = ['/sbin/ifconfig', self.nic_name]
        try:
            ifconfig_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                              stderr=Popen.STORE,
                                              logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'ifconfig' failed with following error: %s", error)
            return None

        # pylint: disable-msg=E1103
        # ifconfig_out is a string
        ifconfig_out = ifconfig_popen.stdout.split()
        link_data = {}
        link_data['flags'] = ifconfig_out[1]
        ifconfig_out = ifconfig_out[2:]
        for i in range(len(ifconfig_out) / 2):
            link_data[ifconfig_out[2 * i]] = ifconfig_out[2 * i + 1]
        return link_data

    def _run_dhcpinfo(self, code, maxent=1):
        '''Run the dhcpinfo command against this NIC, requesting 'code'
        maxent - for lists, if >1, return a list with maxent max length
        
        This function always returns successfully; if the underlying call
        to dhcpinfo fails, then None is returned.
        '''
        ifconfig_data = self.get_ifconfig_data()
        if not ifconfig_data or ifconfig_data['flags'].count("DHCP") == 0:
            LOGGER().warn("This connection is not using DHCP")
            return None

        argslist = ['/sbin/dhcpinfo',
                    '-i', self.nic_name,
                    '-n', str(maxent),
                    code]
        try:
            dhcp_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                          stderr=Popen.STORE, logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'dhcpinfo -i %s -n %s' failed with following error:"
                          " %s" % (self.nic_name, maxent, error))
            return None
            
        # pylint: disable-msg=E1103
        # dhcpout is a string
        return dhcp_popen.stdout.rstrip("\n")
    
    def to_xml(self):
        data_objects = []

        net_physical = SMFConfig("network/physical")
        data_objects.append(net_physical)

        net_default = SMFInstance("default", enabled=True)
        net_physical.insert_children(net_default)

        netcfg_prop = SMFPropertyGroup("netcfg")
        net_default.insert_children(netcfg_prop)

        if self.type == NetworkInfo.AUTOMATIC:
            netcfg_prop.setprop(name="active_ncp", ptype="astring",
                                value="Automatic")
        elif self.type == NetworkInfo.MANUAL:
            netcfg_prop.setprop(name="active_ncp", ptype="astring",
                                value="DefaultFixed")

            net_install = SMFConfig('network/install')
            data_objects.append(net_install)

            net_install_default = SMFInstance("default", enabled=True)
            net_install.insert_children([net_install_default])

            ipv4 = SMFPropertyGroup('install_ipv4_interface')
            ipv6 = SMFPropertyGroup('install_ipv6_interface')
            net_install_default.insert_children([ipv4, ipv6])

            static_address = IPAddress(self.ip_address, netmask=self.netmask)

            # IPv4 configuration
            ipv4.add_props(static_address=static_address,
                           name='%s/v4' % self.nic_name,
                           address_type='static')

            #
            # IPv4 default route is optional. If it was not configured
            # on Network screen, do not populate related smf property.
            #
            if self.gateway:
                ipv4.add_props(default_route=self.gateway)

            # IPv6 configuration
            ipv6.add_props(name='%s/v6' % self.nic_name,
                           address_type='addrconf',
                           stateless='yes',
                           stateful='yes')
            
        return [do.get_xml_tree() for do in data_objects]

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False

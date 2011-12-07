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
from operator import itemgetter
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

    # type of network configuration
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    NONE = "none"
    FROMGZ = "fromgz"

    DEFAULT_NETMASK = "255.255.255.0"

    ETHER_NICS = None
    FROMGZ_NICS_NUM = None

    LABEL = NETWORK_LABEL

    NIC_NAME_KEY = "name"
    NIC_DEV_KEY = "device"
    NIC_LINK_KEY = "link"

    @staticmethod
    def find_links():
        '''Use dladm show-link to find available network interfaces (NICs).
        Filter out NICs with 'allowed-address' mandated from global zone
        (this type of NIC can be configured for non-global zone with exclusive
        IP stack), since those kind of NICs are controlled from global zone
        and can't be configured within non-global zone.

        Construct set of available NICs as a list of dictionaries which
        describe each NIC as
        { NIC_NAME_KEY: 'vanity name', NIC_DEV_KEY: 'device name',
          NIC_LINK_KEY: 'link name'}.

        If vanity name or device name can't be obtained for particular link,
        then following simplified form is used to describe NIC:
        { NIC_NAME_KEY: 'link name', NIC_DEV_KEY: '',
          NIC_LINK_KEY: 'link name'}.

        Return tuple containing
         * dictionary of configurable NICs
         * number of NICs mandated from global zone via allowed-address
           zone property.
        '''

        if NetworkInfo.ETHER_NICS is not None \
            and NetworkInfo.FROMGZ_NICS_NUM is not None:
            return (NetworkInfo.ETHER_NICS, NetworkInfo.FROMGZ_NICS_NUM)

        NetworkInfo.ETHER_NICS = []
        NetworkInfo.FROMGZ_NICS_NUM = 0
        
        argslist = ['/usr/sbin/dladm', 'show-link', '-o', 'link', '-p']

        try:
            dladm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                           stderr=Popen.STORE, logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'dladm show-link -o link -p' "
                          "failed with following error: %s", error)

            return (NetworkInfo.ETHER_NICS, NetworkInfo.FROMGZ_NICS_NUM)

        nic_list = dladm_popen.stdout.strip()

        #
        # pylint: disable-msg=E1103
        # nic_list is a string
        # Start with empty list of NICs and add those which are eligible
        # for configuration.
        #
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
            # Add particular NIC to the list only if 'allowed-ips' link
            # property is not configured (is empty). Count number of NICs
            # which are configured from global zone.
            #
            if allowed_ips:
                LOGGER().info("%s allowed-ips: <%s>" % (nic, allowed_ips))
                NetworkInfo.FROMGZ_NICS_NUM += 1
                continue

            #
            # If vanity name exists for link, use it as NIC name
            # and store physical link name as a NIC device.
            #
            argslist = ['/usr/sbin/dladm', 'show-phys', '-L', '-o',
                        'vanity,device', '-p', nic]
            try:
                n_name = nic
                n_dev = ""

                dladm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                               stderr=Popen.STORE,
                                               logger=LOGGER())
            except CalledProcessError:
                LOGGER().warn("'dladm show-phys -L -o vanity,device -p %s' "
                              "failed.", nic)
            else:
                n = dladm_popen.stdout.strip()
                #
                # The returned string is in form of "vanity_name:device_name".
                #
                # Populate NIC item from vanity name and device name
                # only if both vanity name and device name were obtained.
                # Otherwise use link name for NIC name leaving device
                # portion empty.
                #
                # Also, it was observed that in some cases (e.g. in non-global
                # zone with exclusive IP stack) 'dladm show-phys' reports
                # success, but returns empty string, so account for that.
                #
                vanity_device = n.split(':')
                if len(vanity_device) == 2 and vanity_device[0] \
                   and vanity_device[1]:
                    n_name = vanity_device[0]
                    #
                    # If vanity name and device name are the same, there
                    # is no point to keep both.
                    #
                    if vanity_device[0] != vanity_device[1]:
                        n_dev = vanity_device[1]

            NetworkInfo.ETHER_NICS.append({NetworkInfo.NIC_NAME_KEY: n_name,
                                           NetworkInfo.NIC_DEV_KEY: n_dev,
                                           NetworkInfo.NIC_LINK_KEY: nic})

        # sort the final list - use NIC name as the sort key
        NetworkInfo.ETHER_NICS.sort(key=itemgetter(NetworkInfo.NIC_NAME_KEY))
        return (NetworkInfo.ETHER_NICS, NetworkInfo.FROMGZ_NICS_NUM)

    def __init__(self, nic_iface=None, net_type=None, ip_address=None,
                 netmask=None, gateway=None, dns_address=None, domain=None):
        DataObject.__init__(self, self.LABEL)

        self.nic_iface = nic_iface
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
        result = ["NIC %s:" % self.get_nic_desc(self.nic_iface)]
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
                         NetworkInfo.NONE, NetworkInfo.FROMGZ, None]:
            raise ValueError("'%s' is an invalid type."
                             "Must be one of %s" % (value,
                             [NetworkInfo.AUTOMATIC, NetworkInfo.MANUAL,
                              NetworkInfo.NONE, NetworkInfo.FROMGZ]))
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

    @staticmethod
    def get_nic_desc(nic):
        '''Generate and return NIC description for given network interface.
        Description is in form of "NIC name (NIC device)" - e.g. "net0 (bge0)".
        If device info was not populated, return just NIC name.

        '''
        if nic[NetworkInfo.NIC_DEV_KEY]:
            nic_desc = "%s (%s)" % (nic[NetworkInfo.NIC_NAME_KEY],
                                    nic[NetworkInfo.NIC_DEV_KEY])
        else:
            nic_desc = nic[NetworkInfo.NIC_NAME_KEY]

        return nic_desc

    @staticmethod
    def get_nic_link(nic):
        '''Returns NIC link name for given network interface - e.g. "bge0".
        NIC link name is used by ipadm(1m) or dhcpinfo(1) to refer particular
        network interface.

        '''
        return nic[NetworkInfo.NIC_LINK_KEY]

    @staticmethod
    def get_nic_name(nic):
        '''Returns NIC name for given network interface - e.g. "net0".
        NIC name is provided to user for purposes of selecting network
        interface on 'Manual Network Configuration' screen. It is either
        vanity name or physical device name (if vanity name is not
        available).

        '''
        return nic[NetworkInfo.NIC_NAME_KEY]

    def _nic_is_under_dhcp_control(self):
        '''Returns True if selected NIC is controlled by DHCP.
        Returns False otherwise.

        '''

        #
        # Obtain type for all ipadm address objects created over given NIC.
        # Then search for presence of 'dhcp' type which indicates IPv4
        # address object controlled by DHCP.
        #
        argslist = ['/usr/sbin/ipadm', 'show-addr', '-p', '-o', 'type',
                    self.get_nic_link(self.nic_iface) + "/"]
        try:
            ipadm_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                           stderr=Popen.STORE,
                                           logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'ipadm' failed with following error: %s", error)
            return False

        if 'dhcp' in ipadm_popen.stdout.split():
            return True
        else:
            return False

    def _run_dhcpinfo(self, code, maxent=1):
        '''Run the dhcpinfo command against this NIC, requesting 'code'
        maxent - for lists, if >1, return a list with maxent max length
        
        This function always returns successfully; if the underlying call
        to dhcpinfo fails, then None is returned.
        '''
        nic_link = self.get_nic_link(self.nic_iface)

        if not self._nic_is_under_dhcp_control():
            LOGGER().warn("This connection is not using DHCP")
            return None

        argslist = ['/sbin/dhcpinfo',
                    '-i', nic_link,
                    '-n', str(maxent),
                    code]
        try:
            dhcp_popen = Popen.check_call(argslist, stdout=Popen.STORE,
                                          stderr=Popen.STORE, logger=LOGGER())
        except CalledProcessError as error:
            LOGGER().warn("'dhcpinfo -i %s -n %s %s' failed with following "
                          "error: %s", nic_link, str(maxent), code, error)
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

            nic_name = self.get_nic_name(self.nic_iface)

            # IPv4 configuration
            ipv4.add_props(static_address=static_address,
                           name='%s/v4' % nic_name,
                           address_type='static')

            #
            # IPv4 default route is optional. If it was not configured
            # on Network screen, do not populate related smf property.
            #
            if self.gateway:
                ipv4.add_props(default_route=self.gateway)

            # IPv6 configuration
            ipv6.add_props(name='%s/v6' % nic_name,
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

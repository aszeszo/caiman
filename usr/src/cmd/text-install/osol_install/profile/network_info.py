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

'''
Class and functions supporting representing a NIC and locating
the NICs installed on the system by name (using dladm)
'''

import logging
from subprocess import Popen, PIPE

from osol_install.profile.ip_address import IPAddress


class NetworkInfo(object):
    '''Represents a NIC and its network settings'''
    
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    NONE = "none"
    DEFAULT_NETMASK = "255.255.255.0"
    
    ETHER_NICS = None
    
    @staticmethod
    def find_links():
        '''Use dladm show-ether to find the physical ethernet links
        on the system
        
        '''
        
        if NetworkInfo.ETHER_NICS is not None:
            return NetworkInfo.ETHER_NICS
        
        argslist = ['/usr/sbin/dladm', 'show-ether', '-o', 'LINK', '-p']
        
        try:
            (nic_list, dladm_err) = Popen(argslist, stdout=PIPE,
                                          stderr=PIPE).communicate()
        except OSError, err:
            logging.warn("OSError occurred: %s", err)
            return []
        if dladm_err:
            logging.warn("Error occurred during call to dladm: %s", dladm_err)
        # pylint: disable-msg=E1103
        # nic_list is a string
        NetworkInfo.ETHER_NICS = nic_list.splitlines()
        NetworkInfo.ETHER_NICS.sort()
        return NetworkInfo.ETHER_NICS

    def __init__(self, nic_name=None, net_type=None, ip_address=None,
                 netmask=None, gateway=None, dns_address=None, domain=None):
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
    
    def __str__(self):
        result = ["NIC %s:" % self.nic_name]
        result.append("Type: %s" % self.type)
        if self.type == NetworkInfo.MANUAL:
            result.append("IP: %s" % self.ip_address)
            result.append("Netmask: %s" % self.netmask)
            result.append("Gateway: %s" % self.gateway)
            result.append("DNS: %s" % self.dns_address)
            result.append("Domain: %s" % self.domain)
        return "\n".join(result)
    
    def find_dns(self):
        '''Try to determine the DNS info of the NIC if DHCP is running
        Returns True if this action was successful
        
        '''
        dns_server = self._run_dhcpinfo("DNSserv")
        if dns_server:
            self.dns_address = dns_server
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
            (ifconfig_out, ifconfig_err) = Popen(argslist, stdout=PIPE,
                                                 stderr=PIPE).communicate()
        except OSError, err:
            logging.warn("Failed to call ifconfig: %s", err)
            return None
        if ifconfig_err:
            logging.warn("Error occurred during call to ifconfig: %s",
                         ifconfig_err)
            return None
        # pylint: disable-msg=E1103
        # ifconfig_out is a string
        ifconfig_out = ifconfig_out.split()
        link_data = {}
        link_data['flags'] = ifconfig_out[1]
        ifconfig_out = ifconfig_out[2:]
        for i in range(len(ifconfig_out) / 2):
            link_data[ifconfig_out[2*i]] = ifconfig_out[2*i+1]
        return link_data
    
    def _run_dhcpinfo(self, code):
        '''Run the dhcpinfo command against this NIC, requesting 'code' '''
        ifconfig_data = self.get_ifconfig_data()
        if not ifconfig_data or ifconfig_data['flags'].count("DHCP") == 0:
            logging.warn("This connection not using DHCP")
            return None
        
        argslist = ['/sbin/dhcpinfo',
                    '-i', self.nic_name,
                    '-n', '1',
                    code]
        try:
            (dhcpout, dhcperr) = Popen(argslist, stdout=PIPE,
                                       stderr=PIPE).communicate()
        except OSError, err:
            logging.warn("OSError ocurred during dhcpinfo call: %s", err)
            return None
        
        if dhcperr:
            logging.warn("Error ocurred during dhcpinfo call: ", dhcperr)
        
        # pylint: disable-msg=E1103
        # dhcpout is a string
        return dhcpout.rstrip("\n")

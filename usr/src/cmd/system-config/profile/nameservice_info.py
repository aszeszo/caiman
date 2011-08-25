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
Class and functions supporting name services
'''

import logging
import nss

from solaris_install.data_object import DataObject
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile import NAMESERVICE_LABEL, SMFConfig, \
        SMFInstance, SMFPropertyGroup


_LOGGER = None
# creates oft-used SMF instance list enabling default service
ENABLED_DEFAULT_SERVICE_LIST = [SMFInstance('default', enabled=True)]


def LOGGER():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
    return _LOGGER


class NameServiceInfo(SMFConfig):
    '''Represents the Name service selected'''

    LABEL = NAMESERVICE_LABEL
    MAXDNSSERV = 3    # number of DNS server input fields
    NIS_CHOICE_AUTO = 0
    NIS_CHOICE_MANUAL = 1
    LDAP_CHOICE_NO_PROXY_BIND = 0
    LDAP_CHOICE_PROXY_BIND = 1

    def __init__(self, nameservice=None, domain='',
                 dns=True, dns_server=[], dns_search=[],
                 ldap_profile='default', ldap_ip='', ldap_search_base='',
                 ldap_proxy_bind=LDAP_CHOICE_NO_PROXY_BIND, ldap_pb_dn='',
                 ldap_pb_psw='', nis_ip='', nis_auto=NIS_CHOICE_AUTO):
        DataObject.__init__(self, self.LABEL)
        self.nameservice = nameservice
        self.domain = domain
        # DNS-specific
        self.dns = dns
        self.dns_server = dns_server
        self.dns_search = dns_search
        # LDAP-specific
        self.ldap_profile = ldap_profile
        self.ldap_ip = ldap_ip
        self.ldap_search_base = ldap_search_base
        self.ldap_proxy_bind = ldap_proxy_bind
        self.ldap_pb_dn = ldap_pb_dn
        self.ldap_pb_psw = ldap_pb_psw
        # NIS-specific
        self.nis_auto = nis_auto
        self.nis_ip = nis_ip

    def __repr__(self):
        return '\n'.join(["NS %s:" % self.nameservice,
                          "DNS? %s" % self.dns,
                          "DNSserv: %s" % self.dns_server,
                          "DNSsearch: %s" % self.dns_search,
                          "Domain: %s" % self.domain,
                          "LDAPprofname: %s" % self.ldap_profile,
                          "LDAPprofip: %s" % self.ldap_ip,
                          "LDAP search base: %s" % self.ldap_search_base,
                          "LDAPpbchoice: %s" % self.ldap_proxy_bind,
                          "LDAPpbdn: %s" % self.ldap_pb_dn,
                          "LDAPpbpsw: %s" % self.ldap_pb_psw,
                          "NISauto: %s" % self.nis_auto,
                          "NISip: %s" % self.nis_ip])

    def to_xml(self):
        data_objects = []
        if not self.dns and self.nameservice is None:
            # if no name services, files only
            LOGGER().info('setting name service to files only')
        # configure svc:system/name-service/switch
        LOGGER().info('preparing profile with nsswitch')
        # set NS switch service objects according to user's selection
        data_objects.append(_set_nsswitch(self.dns, self.nameservice))
        # enable name service cache
        data_objects.append(_enable_service('system/name-service/cache'))
        LOGGER().debug('to_xml:name service type=%s', self.nameservice)
        LOGGER().info(self)
        if self.dns:
            LOGGER().info('preparing profile for DNS')
            dns = SMFConfig('network/dns/client')
            data_objects.append(dns)
            # configure 'config' property group
            dns_props = SMFPropertyGroup('config')
            dns.insert_children([dns_props])
            # configure DNS nameservers
            if self.dns_server:
                # filter empty values from list
                ilist = [val for val in self.dns_server if val]
                if ilist:
                    proptype = 'net_address'
                    nameserver = dns_props.setprop("property", "nameserver",
                                                   proptype)
                    nameserver.add_value_list(propvals=ilist,
                                              proptype=proptype)
            if self.dns_search:
                # filter empty values from list
                ilist = [val for val in self.dns_search if val]
                if ilist:
                    search = dns_props.setprop("property", "search", "astring")
                    search.add_value_list(propvals=[" ".join(ilist)])
            # configure default service instance
            dns.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
        else:
            # explicitly disable DNS client service
            dns = SMFConfig('network/dns/client')
            dns.insert_children([SMFInstance('default', enabled=False)])
            data_objects.append(dns)
        if self.nameservice == 'LDAP':
            LOGGER().info('preparing profile for LDAP')
            ldap = SMFConfig('network/ldap/client')
            data_objects.append(ldap)
            # configure 'config' property group
            ldap_config_props = SMFPropertyGroup('config')
            ldap.insert_children([ldap_config_props])
            # add properties to 'config' property group
            ldap_config_props.setprop("propval", "profile", "astring",
                                      self.ldap_profile)
            proptype = 'host'
            nameserver = ldap_config_props.setprop("property", "server_list",
                                                   proptype)
            nameserver.add_value_list(propvals=[self.ldap_ip],
                                      proptype=proptype)
            ldap_config_props.setprop("propval", "search_base", "astring",
                                      self.ldap_search_base)
            # if user chose to provide proxy bind info
            if self.ldap_proxy_bind == self.LDAP_CHOICE_PROXY_BIND:
                # create and add properties to 'cred' property group
                ldap_cred_props = SMFPropertyGroup('cred')
                ldap.insert_children([ldap_cred_props])
                ldap_cred_props.setprop("propval", "bind_dn", "astring",
                                        self.ldap_pb_dn)
                # encrypt password if encryption method was integrated
                # otherwise, user must enter encrypted password
                # the check for the method can be removed after integration
                if hasattr(nss.nssscf, 'ns1_convert'):
                    psw = nss.nssscf.ns1_convert(self.ldap_pb_psw)
                else:
                    psw = self.ldap_pb_psw
                ldap_cred_props.setprop("propval", "bind_passwd", "astring",
                                        psw)
            # configure default service instance
            ldap.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
        # For NIS, user is given automatic (broadcast) or manual
        # specification of NIS server.  If automatic, just set broadcast.
        # Note: NIS domain is set below for LDAP as well as NIS
        if self.nameservice == 'NIS' or \
                (self.nameservice == 'LDAP' and self.domain):
            LOGGER().info('preparing profile for NIS')
            # manual NIS server and/or domain for LDAP and NIS
            if self.domain or (self.nis_auto == self.NIS_CHOICE_MANUAL and
                               self.nameservice == 'NIS'):
                # enable network/nis/domain smf service
                nis = SMFConfig('network/nis/domain')
                data_objects.append(nis)
                # configure 'config' property group
                nis_props = SMFPropertyGroup('config')
                nis.insert_children([nis_props])
                # configure domain for NIS or LDAP
                if self.domain:
                    LOGGER().info('setting NIS domain: %s', self.domain)
                    nis_props.setprop("propval", "domainname", "hostname",
                                      self.domain)
                # manual configuration naming NIS server explicitly
                if self.nis_auto == self.NIS_CHOICE_MANUAL and \
                        self.nameservice == 'NIS':
                    proptype = 'host'
                    nis_ip = nis_props.setprop("property", "ypservers",
                                               proptype)
                    nis_ip.add_value_list(propvals=[self.nis_ip],
                                          proptype=proptype)
                # configure default service instance
                nis.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
            # enable network/nis/client smf service
            if self.nameservice == 'NIS':
                nis_client = SMFConfig('network/nis/client')
                data_objects.append(nis_client)
                # automatic NIS configuration (broadcast)
                if self.nis_auto == self.NIS_CHOICE_AUTO:
                    # configure 'config' property group
                    nis_client_props = SMFPropertyGroup('config')
                    nis_client.insert_children([nis_client_props])
                    # set NIS broadcast property
                    nis_client_props.setprop("propval", "use_broadcast",
                                             "boolean", "true")
                # configure default service instance
                nis_client.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
        return [do.get_xml_tree() for do in data_objects]

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False


def _set_nsswitch(dns, nameservice):
    ''' configure name services switch table
    for svc: system/name-service/switch
    Arg:
        nameservice - name service NIS, DNS, or LDAP
    Returns:
        SMFconfig service with properties set
    '''
    svc = SMFConfig('system/name-service/switch')
    # configure default instance
    props = SMFPropertyGroup('config')
    svc.insert_children([props])
    # set name service sources per name service
    if dns:
        # set combination with DNS
        source_dict = {
                None: {
                    'default': 'files',
                    'host': 'files dns',
                    'printer': 'user files'},
                'LDAP': {
                    'default': 'files ldap',
                    'host': 'files dns',
                    'printer': 'user files ldap'},
                'NIS': {
                    'default': 'files nis',
                    'host': 'files dns',
                    'printer': 'user files nis'}
                }[nameservice]
    else:
        # set name service sources per name service
        source_dict = {
                None: {
                    'default': 'files',
                    'printer': 'user files'},
                'LDAP': {
                    'default': 'files ldap',
                    'printer': 'user files ldap',
                    'netgroup': 'ldap'},
                'NIS': {
                    'default': 'files nis',
                    'printer': 'user files nis',
                    'netgroup': 'nis'}
                }[nameservice]
    for prop in source_dict:
        props.setprop('propval', prop, 'astring', source_dict[prop])
    # configure default service instance
    svc.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
    return svc


def _enable_service(service_name):
    ''' enable a service by name
    Args:
        service_name - name of service to enable - no properties
    Returns:
        SMFconfig service enabled
    '''
    svc = SMFConfig(service_name)
    svc.insert_children(ENABLED_DEFAULT_SERVICE_LIST)
    return svc


def _disable_ns(data_objects):
    ''' disable all name services
    Arg: data_objects - list of service objects to affect
    Effect: append all name services, disabling them explicitly
    Note: this is not presently used, since disabling name-service-switch
        results in disabling the GNOME desktop as a result of a dependency
        chain.
    '''
    for svcn in [
            # switch and cache
            "network/name-service/switch",
            "network/name-service/cache",
            # DNS
            "network/dns/client",
            # LDAP
            "network/ldap/client",
            # NIS client and server
            "network/nis/domain",
            "network/nis/client",
            "network/nis/server",
            "network/nis/passwd",
            "network/nis/update",
            "network/nis/xfr",
            # supporting services for NIS
            "network/rpc/keyserv"]:
        svc = SMFConfig(svcn)
        data_objects.append(svc)
        # configure default instance, disabled
        svc.insert_children([SMFInstance('default', enabled=False)])

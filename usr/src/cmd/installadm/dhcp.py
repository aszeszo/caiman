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
Classes, methods and related routines used in the configuration and management
of the ISC DHCP server (dhcpd(8)).
'''
import logging
import os
import re
import socket
import struct
import sys
import time

import osol_install.auto_install.installadm_common as com

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.libaimdns import getifaddrs
from solaris_install import Popen


VERSION = "0.1"
INVALID_IP = "0.0.0.0"
NETSTAT = "/usr/bin/netstat"
DOMAINNAME = "/usr/bin/domainname"
GETENT = "/usr/bin/getent"
SVCS = "/usr/bin/svcs"
SVCADM = "/usr/sbin/svcadm"
SVCCFG = "/usr/sbin/svccfg"
SVCPROP = "/usr/bin/svcprop"

DHCP_SERVER_IPV4_SVC = "svc:/network/dhcp/server:ipv4"

# Mappings for name services (DNS, NIS) and related properties
_ns_map = {'dns': {'SVC_NAME': "svc:/network/dns/client",
                   'DOMAIN_PROP': "config/domain",
                   'SERVER_PROP': "config/nameserver"},
           'nis': {'SVC_NAME': "svc:/network/nis/domain",
                   'DOMAIN_PROP': "config/domainname",
                   'SERVER_PROP': "config/ypservers"}}

# These lists may be used to validate action arguments to the control() method.
SMF_SUPPORTED_ACTIONS = ('enable', 'disable', 'restart')
SMF_ONLINE_ACTIONS = ('enable', 'restart')
SMF_HARD_RESET_ACTIONS = ('disable', 'enable')

# This dictionary may be used to look up and confirm an expected state
# transition after invoking one of the above supported actions (i.e. the action
# keys the value of the expected state once that action has been invoked).
SMF_EXPECTED_STATE = {'enable': 'online',
                      'disable': 'disabled',
                      'restart': 'online'}

# Regular expression strings
IP_PATTERN = "\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
X86_VCI_PATTERN = 'match if \(sub.*"PXEClient"\);'
SPARC_VCI_PATTERN = 'match if not \(sub.*"PXEClient"\);'

# Set up some block-quoted strings for the ISC DHCP configuration file.
# We have a set of base options we want for any new file, and also we can
# set up each type of configuration stanza here.
#
# First is the configuration file base, containing the stock options we'd
# like set for any new configuration.
CFGFILE_BASE = """# dhcpd.conf
#
# Configuration file for ISC dhcpd
# (created by installadm(1M))
#

default-lease-time 900;
max-lease-time 86400;

# If this DHCP server is the official DHCP server for the local
# network, the authoritative directive should be uncommented.
authoritative;

# Set logging facility (accompanies setting in syslog.conf)
log-facility local7;
"""

# A set of strings to use when setting name services configuration data during
# file initialization. These are currently server-wide (global) attributes and
# are included when we initialize a new base config file, but all entries are
# optional, so we have a separate string for each setting.
CFGFILE_DNS_DOMAIN_STRING = """option domain-name "%s";
"""
CFGFILE_DNS_SERVERS_STRING = """option domain-name-servers %s;
"""
CFGFILE_NIS_DOMAIN_STRING = """option nis-domain "%s";
"""
CFGFILE_NIS_SERVERS_STRING = """option nis-servers %s;
"""

# The following defines a block quote for subnet stanzas. These stanzas
# describe the details of a subnet which will be supported by the DHCP
# server.
# Optionally passed in the format list:
#   subnet - Base address of the subnet (e.g. 10.0.0.0)
#   netmask - Netmask for the subnet (e.g. 255.255.255.0)
#   loaddr - Lowest address of IP range
#   hiaddr - Highest address of IP range
#   broadcast - Broadcast for the subnet (e.g. 10.0.0.255)
#   routers - A comma-seperated list of router(s) for the subnet
#   nextserver - Host which provides boot file data for clients
CFGFILE_SUBNET_STANZA = """
subnet %(subnet)s netmask %(netmask)s {
  range %(loaddr)s %(hiaddr)s;
  option broadcast-address %(broadcast)s;
  option routers %(routers)s;
  next-server %(nextserver)s;
}
"""

# These strings are used to build the subnet stanza in parts
# when more than one IP address range is supplied
CFGFILE_SUBNET_HEADER_STRING = """
subnet %(subnet)s netmask %(netmask)s { """

CFGFILE_SUBNET_FOOTER_STRING = """  option broadcast-address %(broadcast)s;
  option routers %(routers)s;
  next-server %(nextserver)s;
}
"""

# This string can be used when adding a new range to an existing subnet.
CFGFILE_SUBNET_RANGE_STRING = """  range %(loaddr)s %(hiaddr)s;
"""

# The following defines a block quote for an x86 class stanza. Class stanzas
# set details for an entire architecture.
# Optionally passed in the format list:
#   bootfile - The bootfile for this architecture class
CFGFILE_PXE_CLASS_STANZA = """
class "PXEBoot" {
  match if (substring(option vendor-class-identifier, 0, 9) = "PXEClient");
  filename "%(bootfile)s";
}
"""

# The following defines a block quote for a SPARC class stanza. Class stanzas
# set details for an entire architecture. Note we use 'not PXE' here as there
# is no VCI that indicates SPARC.
# Optionally passed in the format list:
#   bootfile - The bootfile for this architecture class
CFGFILE_SPARC_CLASS_STANZA = """
class "SPARC" {
  match if not (substring(option vendor-class-identifier, 0, 9) = "PXEClient");
  filename "%(bootfile)s";
}
"""

# This string can be used when adding a new bootfile to an existing class.
CFGFILE_CLASS_BOOTFILE_STRING = """  filename "%(bootfile)s";
"""

# The following defines a block quote for an host-specific stanza. These
# stanzas set details for an specific host, based upon ethernet address.
# Optionally passed in the format list:
#   hostname - Label for this stanza
#   macaddr - Ethernet (mac) address of the client
#   bootfile - Bootfile for this client
CFGFILE_HOST_STANZA = """
host %(hostname)s {
  hardware ethernet %(macaddr)s;
  filename "%(bootfile)s";
}
"""


class DHCPServerError(StandardError):
    '''
    A universal DHCP server error class.
    '''
    pass


class _DHCPConfigStanza(object):
    '''
    Parent class of all ISC DHCP configuration stanzas. All subclasses are
    initialized with configuration-specific data and used to create new
    configuration file entries. Once created, these objects provide the
    format_config() method which may be invoked and will return a formatted
    string which is suitable for a new entry in the configuration file.
    '''
    def __init__(self):
        self.block = None

    def format_stanza(self):
        '''
        Return a formatted stanza for use in an ISC DHCP configuration file.
        '''
        if self.block is not None:
            return self.block % self.__dict__


class _DHCPConfigBase(_DHCPConfigStanza):
    '''
    DHCP configuration class containing base configuration data.  This should
    only be employed when a new configuration file is being created.
    '''
    def __init__(self):
        self.block = CFGFILE_BASE


class _DHCPConfigSubnet(_DHCPConfigStanza):
    '''
    DHCP configuration class containing data for a subnet stanza.
    Constructor arguments:
        subnet - Base address of the subnet (e.g. 10.0.0.0)
        netmask - Netmask for the subnet (e.g. 255.255.255.0)
        loaddr - Lowest address of IP range
        hiaddr - Highest address of IP range
        broadcast - Broadcast for the subnet (e.g. 10.0.0.255)
        routers - A comma-seperated list of router(s) for the subnet
    '''
    def __init__(self, subnet, netmask, loaddr, hiaddr,
                 broadcast, routers, nextserver):
        self.block = CFGFILE_SUBNET_STANZA
        self.subnet = subnet
        self.netmask = netmask
        self.loaddr = loaddr
        self.hiaddr = hiaddr
        self.broadcast = broadcast
        self.routers = routers
        self.nextserver = nextserver


class _DHCPConfigPXEClass(_DHCPConfigStanza):
    '''
    DHCP configuration class containing the data to describe a PXE client
    architecture class stanza.
    Constructor arguments:
        bootfile - The bootfile for this architecture class
    '''
    def __init__(self, bootfile):
        self.block = CFGFILE_PXE_CLASS_STANZA
        self.bootfile = bootfile


class _DHCPConfigSPARCClass(_DHCPConfigStanza):
    '''
    DHCP configuration class containing the data to describe a SPARC client
    architecture class stanza.
    Constructor arguments:
        bootfile - The bootfile for this architecture class
    '''
    def __init__(self, bootfile):
        self.block = CFGFILE_SPARC_CLASS_STANZA
        self.bootfile = bootfile


class _DHCPConfigHost(_DHCPConfigStanza):
    '''
    DHCP configuration class containing the data for a host-specific stanza.
    Construtor arguments:
        hostname - Label for this stanza
        macaddr - Ethernet (mac) address of the client
        bootfile - Bootfile for this client
    '''
    def __init__(self, hostname, macaddr, bootfile):
        self.block = CFGFILE_HOST_STANZA
        self.hostname = hostname
        self.macaddr = macaddr
        self.bootfile = bootfile


class DHCPData(object):
    '''
    Parent class of all ISC DHCP configuration data classes. This and its
    subclasses are really convenience classes for passing data around. Ideally,
    a subclass will define an attribute set that maps to the configuration data
    for what it is meant to represent, and then populate its set of attributes
    during initialization.
    '''
    def __init__(self):
        pass


class DHCPSubnet(DHCPData):
    '''
    DHCP data class containing data related to a subnet.
    Constructor arguments:
        server - The DHCPServer object to query
        subnet_ip - Base address of the subnet (e.g. 10.0.0.0)
    Attributes:
        subnet_ip - Base address of the subnet (e.g. 10.0.0.0)
        ranges - A list of tuples, each tuple consisting of the
                 low and high addresses of a range in the subnet
    '''
    def __init__(self, server, subnet_ip):

        if not isinstance(server, DHCPServer):
            raise ValueError('object passed not a DHCPServer object')

        self.subnet_ip = subnet_ip
        self.ranges = list()

        # Set up a regular expression to extract the low and high addresses
        # of a range from a 'range' string in the configuration data.
        regexp = re.compile("^range\s+(%s)\s+(%s)" % (IP_PATTERN, IP_PATTERN))

        # Populate the 'ranges' list of tuples by applying the regexp across
        # the DHCP server's current config and checking for our subnet_ip.
        matches = filter(bool, map(regexp.match, server._current_config()))
        self.ranges = [m.groups()
            for m in matches
                if _get_subnet(m.group(1), _get_mask(m.group(1))) == subnet_ip]


class DHCPArchClass(DHCPData):
    '''
    DHCP data class containing data related to an architecture-specific
    entry in the DHCP configuration.
    Constructor arguments:
        server - The DHCPServer object to query
        arch - The architecture class being queried
    Attributes:
        arch - The architecture of this architecture class entry
        bootfile - The bootfile for this architecture class
    '''
    def __init__(self, server, arch, bootfile=None):
        self.server = server
        self.arch = arch
        self.bootfile = bootfile

    @classmethod
    def get_arch(cls, server, arch):
        '''
        Instantiate and return a DHCPArchClass object only if there is one
        currently configured for this arch. Otherwise, return None.
        '''
        if not isinstance(server, DHCPServer):
            raise ValueError('object passed not a DHCPServer object')

        # The x86 class is determined by the VCI "PXEClient". For SPARC, we
        # use "not x86", since we only support the two architectures, and
        # there is no simple way to determine a SPARC client explicitly.
        if arch == 'i386':
            regexp = re.compile(X86_VCI_PATTERN)
        elif arch == 'sparc':
            regexp = re.compile(SPARC_VCI_PATTERN)
        else:
            raise DHCPServerError(_("unsupported architecture: %s") % arch)

        # Search for 'class' stanzas in the config data. If one is found,
        # initialize a new list to 'record' each line of the class stanza.  If
        # we find that it's for the architecture in question, then we can break
        # out of parsing once we're done reading it all in. If not, move on to
        # the next class, if there are any.
        found = False
        bootfile = None
        classlines = list()
        for line in server._current_config():
            if line.startswith("class"):
                # New class stanza, init a new class list
                classlines = list()
                continue
            if line.endswith("}") and found:
                # We're at the end of the class we wanted. The classlines list
                # now contains each line of the class stanza for this
                # architecture.
                break
            m = regexp.search(line)
            if m is not None:
                # We've found the class stanza for this architecture.
                found = True
            classlines.append(line)

        # If we found our class, snag the bootfile if set
        if found:
            regexp = re.compile('^filename\s+"(\S+)";')
            matches = [m.group(1)
                for m in filter(bool, map(regexp.match, classlines))]
            if matches:
                bootfile = matches[0]

        # Finally, if we found the class, instantiate and return a
        # DHCPArchClass object.
        if found:
            return cls(server, arch, bootfile)
        else:
            return None

    def set_bootfile(self, bootfile):
        '''
        Set the provided bootfile string as the default bootfile for this
        architecture.
        '''
        logging.debug("dhcp.set_bootfile: arch %s, bootfile '%s'", self.arch,
                      bootfile)

        if self.bootfile is not None:
            raise DHCPServerError(_("%s architecture already has a bootfile "
                                    "set in the DHCP configuration") %
                                    self.arch)
        self._edit_class_bootfile('set', bootfile)
        self.bootfile = bootfile

    def unset_bootfile(self):
        '''
        Remove the bootfile setting for this architecture. This is used
        when the default service for an architecture is deleted.
        '''
        logging.debug("dhcp.unset_bootfile: arch %s", self.arch)

        if self.bootfile is None:
            raise DHCPServerError(_("attempting to unset bootfile for %s "
                                    "architecture; no bootfile currently set")
                                    % self.arch)
        self._edit_class_bootfile('update')
        self.bootfile = None

    def update_bootfile(self, bootfile):
        '''
        Update an existing bootfile for this architecture.
        '''
        logging.debug("dhcp.update_bootfile: arch %s, bootfile '%s'",
                      self.arch, bootfile)

        self._edit_class_bootfile('update', bootfile)
        self.bootfile = bootfile

    def _edit_class_bootfile(self, action, bootfile=None):
        '''
        Locate the class stanza for this architecture, if it exists, and either
        set or update the bootfile setting for it, depending upon action.
        Arguments:
            action - either 'set' or 'update'
            bootfile - the bootfile to set or update to.
        Note: If action is 'update' and bootfile is "None", the bootfile will
        be unset entirely.
        '''
        if action not in ['set', 'update']:
            raise ValueError(_("invalid action: %s") % action)

        if action == 'set' and bootfile is None:
            raise ValueError(_("action 'set' requires bootfile"))

        # This is the workhorse for both 'set_bootfile', 'unset_bootfile' and
        # 'update_bootfile'. We need to walk through the config data and make a
        # copy, watching for this architecture's class stanza as we traverse.
        # When we find it, update the bootfile setting as requested and then
        # finish the copy.

        # The x86 class is determined by the VCI "PXEClient". For SPARC, we
        # use "not x86", since we only support the two architectures, and
        # there is no simple way to determine a SPARC client explicitly.
        if self.arch == 'i386':
            vci_re = re.compile(X86_VCI_PATTERN)
        elif self.arch == 'sparc':
            vci_re = re.compile(SPARC_VCI_PATTERN)
            bootfile = fixup_sparc_bootfile(bootfile, True)
        else:
            raise DHCPServerError(_("unsupported architecture: %s") % \
                self.arch)

        bootfile_re = re.compile('filename\s+\S+;')

        # Create a dictionary for use in the format string below
        bf = {'bootfile': bootfile}

        current_cfgfile = self.server._properties['config_file']
        tmp_cfgfile = "%s~" % current_cfgfile

        # Get the full configuration file, not just this server's current
        # config, as we'll be making a copy of the current file for editing.
        current_lines = list()
        with open(current_cfgfile, "r") as current:
            current_lines = current.readlines()

        # Now make the copy, adding or updating the bootfile when we get to
        # this architecture's class stanza. This gets a little involved, but
        # the alternative appears to be to duplicate this entire block of code
        # for updating or adding a new entry, which is not ideal. So, excessive
        # comments are provided intentionally.
        in_class = False
        seek_bootfile = False
        edit_complete = False
        with open(tmp_cfgfile, "w") as tmp_cfg:
            for line in current_lines:
                if not edit_complete:
                    # We have not yet updated or set a new bootfile, so keep
                    # checking for class stanzas and for the lines to edit
                    # inside the class stanza once found. For a 'set' action,
                    # we'll just drop in the new line after the match line. For
                    # an 'update', we'll go further and actually find the
                    # existing bootfile setting and swap our new one for it.
                    if line.startswith("class"):
                        # We have found the beginning of a class stanza, so set
                        # our flag. Now, moving through the next set of lines,
                        # the rest of this routine will know we're inside a
                        # class stanza and can perform accordingly.
                        in_class = True
                    if line.strip().endswith("}"):
                        # We are out of this particular class, so unset our
                        # flag and move on. Note we could assert that
                        # seek_bootfile shouldn't be set here (see below), but
                        # it could be possible to have more than one class
                        # stanza for this architecture. So, just unset that
                        # flag as well.
                        in_class = False
                        seek_bootfile = False
                    if seek_bootfile:
                        if bootfile_re.search(line) is not None:
                            # We're at the bootfile line in the class for this
                            # architecture, and we want to update it (i.e. the
                            # action is 'update'). If the bootfile argument is
                            # set, then we're updating to a new bootfile
                            # setting. Create a new entry and drop it in,
                            # leaving the old one behind. If a new bootfile
                            # wasn't passed, then we're unsetting the bootfile
                            # altogether - just leave this line behind.  Either
                            # way,  set our 'done' flag. We'll then just copy
                            # the rest of the file and return.
                            if bootfile is not None:
                                tmp_cfg.write(CFGFILE_CLASS_BOOTFILE_STRING % \
                                    bf)
                            edit_complete = True
                            continue
                    if in_class:
                        if vci_re.search(line) is not None:
                            # We've found the class for this architecture
                            if action == 'set':
                                # We're setting a new bootfile for the class we
                                # just entered. We haven't yet written the VCI
                                # line to the new file yet, so write it now,
                                # then drop in the bootfile as well and set our
                                # 'done' flag. We'll then just copy the rest of
                                # the file and return.
                                tmp_cfg.write(line)
                                tmp_cfg.write(CFGFILE_CLASS_BOOTFILE_STRING % \
                                    bf)
                                edit_complete = True
                                continue
                            else:
                                # We're updating an existing bootfile setting,
                                # so start looking for it by setting the seek
                                # flag, then move onto the next line.
                                seek_bootfile = True
                # Write each line from the old file to the new as we traverse
                tmp_cfg.write(line)

        # Ok, we're done writing lines from the old file to the new. Let's
        # ensure we've made our edit. If not, for whatever reason, we should
        # inform the enduser that manual DHCP configuration might be required.
        if edit_complete == False:
            print cw(_("\nFailed to update the DHCP configuration. An error "
                       "occured while setting the new bootfile (%s) for the "
                       "%s architecture in the current DHCP configuration "
                       "file (%s). Please ensure the bootfile is properly set "
                       "before using this service. Please see dhcpd(8) for "
                       "further information.\n") %
                       (bootfile, self.arch, current_cfgfile))

        # Finally, rename the new temporary file to the configfile and return.
        os.rename(tmp_cfgfile, current_cfgfile)


class DHCPServer(object):
    '''
    DHCPServer is used to represent and interact with the ISC DHCP server on
    the host system. The server can be configured and monitored via this class.
    '''
    def __init__(self):
        self._version = VERSION
        self.ip_version = 'IPv4'

    @property
    def _state(self):
        '''
        Retrieve the current state of the ISC DHCP server's SMF service (e.g.
        'online') and returns it as a string.
        '''
        cmd = [SVCS, "-Ho", "STATE", DHCP_SERVER_IPV4_SVC]
        p = Popen.check_call(cmd, stdout=Popen.STORE,
                             stderr=Popen.STORE, logger='',
                             stderr_loglevel=logging.DEBUG)

        return p.stdout.strip()

    def is_online(self):
        '''
        Returns True if the DHCP server is online.
        '''
        return self._state == 'online'

    def is_configured(self):
        '''
        Returns True if the DHCP server is configured.
        '''
        return os.path.exists(self._properties['config_file'])

    @property
    def _properties(self):
        '''
        Retrieve the current properties for the ISC DHCP server's SMF service
        and return to the caller as a dict keyed by property name.
        '''
        cmd = [SVCCFG, "-s", DHCP_SERVER_IPV4_SVC, "listprop", "config"]
        p = Popen.check_call(cmd, stdout=Popen.STORE,
                             stderr=Popen.STORE, logger='',
                             stderr_loglevel=logging.DEBUG)

        # Set up a regular expression to map the properties and settings
        regexp = re.compile('config/(\S+)\s+\S+\s+(\S+)')

        # Apply the regular expression across the svccfg output, then build up
        # the dict from it and return it.
        return dict([m.groups()
            for m in filter(bool, map(regexp.match, p.stdout.splitlines()))])

    def _current_config(self):
        '''
        Generator which retrieves the current configuration of the DHCP server
        from its configuration file. Note all comments and log() lines are
        removed to simplify searching returned data for keywords.
        '''
        if self.is_configured():
            for line in open(self._properties['config_file']):
                line = line.partition('#')[0].strip()
                if line.startswith("log") or line == '':
                    continue
                yield line

    def init_config(self):
        '''
        Create a new base configuration file for use with a new DHCP server.
        '''
        logging.debug("dhcp.init_config: creating new DHCP server")

        if self.is_configured():
            raise DHCPServerError(_("init_config failed, file already exists"))

        # Initialize a base configuration and create a new file with it
        new_stanza = _DHCPConfigBase()
        self._add_stanza_to_config_file(new_stanza)

        # Add configured name services to the global configuration
        self._add_name_services()

    def _add_name_services(self):
        '''
        Discovers name services available on the server and adds them to the
        global scope of the DHCP configuration. DNS and NIS are supported, both
        of which are optional for AI services.
        '''
        # Note the protocol dependencies: NIS requires a domain and any number
        # of optional servers, DNS requires at least one server and an optional
        # domain.
        lines = list()
        dns_servers = _get_nameservers('dns')
        if dns_servers is not None:
            lines.append(CFGFILE_DNS_SERVERS_STRING % dns_servers)
            dns_domain = _get_domain('dns')
            if dns_domain is not None:
                lines.append(CFGFILE_DNS_DOMAIN_STRING % dns_domain)

        nis_domain = _get_domain('nis')
        if nis_domain is not None:
            lines.append(CFGFILE_NIS_DOMAIN_STRING % nis_domain)
            nis_servers = _get_nameservers('nis')
            if nis_servers is not None:
                lines.append(CFGFILE_NIS_SERVERS_STRING % nis_servers)

        if lines:
            # At least one name service is configured. Format the text that
            # is saved off with a header and print it to the config file.
            lines.insert(0, '\n# Global name services\n')
            lines.append('\n')
            with open(self._properties['config_file'], 'a') as cfg:
                cfg.writelines(lines)

    def control(self, action):
        '''
        Used to start and stop the DHCP server. This method effects change in
        server state via the SMF service associated with it.  It may be
        enabled, disabled or, if needed, restarted to enact any pending
        configuration changes.
        '''
        logging.debug("dhcp.control: invoking 'svcadm %s'", action)

        if action not in SMF_SUPPORTED_ACTIONS:
            raise ValueError(_("unsupported action on DHCPServer object: %s")
                               % action)

        cmd = [SVCADM, action, DHCP_SERVER_IPV4_SVC]
        Popen.check_call(cmd, stderr=Popen.STORE)

        # Delay a second to allow for the change to propagate
        time.sleep(1)

        if self._state != SMF_EXPECTED_STATE[action]:
            # This action did not result in the expected state. If the action
            # was a reset or start, try a hard reset. If that fails, or if this
            # wasn't either flavor of online, throw an exception.
            if action in SMF_ONLINE_ACTIONS:
                for action in SMF_HARD_RESET_ACTIONS:
                    cmd = [SVCADM, action, DHCP_SERVER_IPV4_SVC]
                    Popen.check_call(cmd, stderr=Popen.STORE)
                    time.sleep(1)
                if self._state == SMF_EXPECTED_STATE[action]:
                    return
            logging.debug("dhcp.control: unexpected service state: %s",
                          self._state)
            raise DHCPServerError(cw(_("DHCP server is in an unexpected "
                                       "state: action [%s] state [%s]") % 
                                       (action, self._state)))

    def _add_stanza_to_config_file(self, new_stanza):
        '''
        Add the stanza passed to the server's configuration file.
        '''
        with open(self._properties['config_file'], 'a') as cfg:
            cfg.write(new_stanza.format_stanza())

    @property
    def _subnets(self):
        '''
        Return a list of DHCPSubnet objects representing each of the subnets
        that are currently configured.
        '''
        # Set up a utility to test for subnet strings
        def _subnet_check(s):
            if s is not None:
                return s.startswith("subnet")

        # Set up a regular expression to extract the subnet IP from a 'subnet'
        # string in the configuration data.
        regexp = re.compile("^subnet\s+(%s)" % IP_PATTERN)

        # Build a list of all subnet IPs in the current config. Innermost scope
        # filters for "subnet" lines, the map applies the regular expression,
        # and the outer filter will iterate on the matches.
        nets = list()
        nets = [m.group(1)
            for m in filter(bool, map(regexp.match,
                filter(_subnet_check, self._current_config())))]

        # Now build up and return a list of DHCPSubnet objects
        return [DHCPSubnet(self, subnet_ip) for subnet_ip in nets]

    def lookup_subnet(self, subnet_ip):
        '''
        Return a DHCPSubnet object representing the subnet defined by
        subnet_ip. Return None if not found.
        '''
        for net in self._subnets:
            if net.subnet_ip == subnet_ip:
                return net

    def add_address_range(self, ipaddr, count, bootserver):
        '''
        Add a new range of IP addresses to the DHCP configuration, adding a new
        subnet stanza if necessary. If this particular subnet is already be in
        the configuration file, we will simply add the range to the existing
        subnet. Raises DHCPServerError if the high address will be out of
        bounds, if an IP range collision will occur or for any formatting
        issues.
        Arguments:
            ipaddr - Starting DHCP address for this subnet entry
            count - Number of DHCP addresses to allocate (range)
            bootserver - IP address of bootserver (can be passed as None)
        '''
        # Validate IP address argument is a valid 'A.B.C.D' format
        m = re.match("^\d{1,3}\.\d{1,3}\.\d{1,3}\.(\d{1,3})$", ipaddr)
        if m is None:
            raise ValueError("add_address_range: bad IP format [%s]" % ipaddr)

        # Find the subnet and netmask for this IP
        netmask = _get_mask(ipaddr)
        subnet_ip = _get_subnet(ipaddr, netmask)

        # Set the low and high addresses of the IP range.
        loaddr = ipaddr
        hiaddr = _set_and_check_hiaddr(subnet_ip, netmask, loaddr, count)

        # Check to see if this subnet is already configured.
        subnet = self.lookup_subnet(subnet_ip)
        if subnet:
            # This subnet is already in the configuration file.  If there are
            # any IP address ranges also set, ensure that our new range will
            # not cause duplication.
            if subnet.ranges:
                _check_subnet_for_overlap(subnet, loaddr, hiaddr)

            logging.debug("dhcp: adding new range to existing subnet [%s]: "
                          "loaddr [%s] hiaddr [%s]", subnet, loaddr, hiaddr)

            # This range is not in use, so we can now add a new range to the
            # subnet stanza.
            self._add_range_to_subnet(subnet, loaddr, hiaddr)
        else:
            # There is no entry for this subnet. Before we add it, we'll need
            # to sort out its netmask, broadcast address and default route.
            broadcast = _get_broadcast_address(subnet_ip, netmask)
            router = _get_default_route_for_subnet(subnet_ip)

            if bootserver is not None:
                nextserver = bootserver
            else:
                nextserver = _get_nextserver_ip_for_subnet(subnet_ip, netmask)

            if nextserver is None:
                raise DHCPServerError(cw(_("Unable to determine local IP "
                                           "address for network %s. Possible "
                                           "unsupported configuration.") %
                                           subnet_ip))

            logging.debug("dhcp: adding new network to DHCP config: subnet "
                          "[%s] mask [%s] loaddr [%s] hiaddr [%s] bcast [%s]"
                          "router [%s] server [%s]", subnet, loaddr, hiaddr,
                          broadcast, router, nextserver)

            # Now we can build up a new subnet stanza
            new_stanza = _DHCPConfigSubnet(subnet_ip, netmask, loaddr, hiaddr,
                                           broadcast, router, nextserver)
            self._add_stanza_to_config_file(new_stanza)

    def _add_range_to_subnet(self, subnet, loaddr, hiaddr):
        '''
        Add a new IP range to an already established subnet stanza. This can
        be used while adding a new subnet if we find the subnet is already
        configured and the IP range is available.
        Arguments:
            subnet - DHCPSubnet object for this subnet
            loaddr - low-side address of this new pool's range
            hiaddr - high-side address of this new pool's range
        '''
        if not isinstance(subnet, DHCPSubnet):
            raise ValueError('object passed not a DHCPSubnet object')

        # Create a dictionary for use in the format string below
        new_range = dict()
        new_range = {'loaddr': loaddr, 'hiaddr': hiaddr}

        current_cfgfile = self._properties['config_file']
        tmp_cfgfile = "%s~" % current_cfgfile

        # Set up a regular expression to extract the subnet IP from a 'subnet'
        # string in the configuration data.
        regexp = re.compile("^subnet\s+(%s)" % IP_PATTERN)

        # Get the full configuration file, not just this server's current
        # config, as we'll be making a copy of the current file for editing.
        current_lines = list()
        with open(current_cfgfile, "r") as current:
            current_lines = current.readlines()

        # Make the copy, and when we hit our subnet, add our range to it
        with open(tmp_cfgfile, "w") as tmp_cfg:
            for line in current_lines:
                tmp_cfg.write(line)
                m = regexp.match(line)
                if m is not None and m.group(1) == subnet.subnet_ip:
                    tmp_cfg.write(CFGFILE_SUBNET_RANGE_STRING % new_range)

        # Rename the temporary new file to the configfile
        os.rename(tmp_cfgfile, current_cfgfile)

    @property
    def _hosts(self):
        '''
        Return a list of hardware addresses that are currently configured in
        the DHCP server. Since we're really only concerned with whether there
        is an entry or not, we can just work with hardware addresses.
        '''
        # Set up a regular expression to extract the hardware address from an
        # address string in the configuration data.
        regexp = re.compile("^hardware ethernet\s+(\S+);")

        # Now apply the regexp across the current config data, assembling all
        # of the hardware addresses in a list, and return it.
        return [m.group(1)
            for m in filter(bool, map(regexp.match, self._current_config()))]

    def host_is_configured(self, address):
        '''
        Return True if this hardware address is already configured in the DHCP
        server.
        '''
        for host in self._hosts:
            if host.lower() == address.lower():
                return True
        return False

    def add_host(self, macaddr, bootfile, hostname=None):
        '''
        Add a host stanza to the DHCP configuration.
        Arguments:
            macaddr - Hardware ethernet address of the client
            bootfile - Bootfile to set for this client
            hostname - Label for this stanza (optional)
        '''
        logging.debug("dhcp.add_host: adding host [%s] bootfile '%s'",
                      macaddr, bootfile)

        if hostname is None:
            hostname = macaddr.replace(':', '')

        if self.host_is_configured(macaddr):
            raise DHCPServerError(_("host [%s] already present in the DHCP "
                                    "configuration") % macaddr)

        new_stanza = _DHCPConfigHost(hostname, macaddr, bootfile)
        self._add_stanza_to_config_file(new_stanza)

    def remove_host(self, macaddr):
        '''
        Remove the host stanza related to the hardware address 'macaddr'.
        '''
        logging.debug("dhcp.remove_host: removing host [%s]", macaddr)

        current_cfgfile = self._properties['config_file']
        tmp_cfgfile = "%s~" % current_cfgfile

        # Get the full configuration file, not just this server's current
        # config, as we'll be making a copy of the current file for editing.
        current_cfg = list()
        with open(current_cfgfile, "r") as current:
            current_cfg = current.readlines()

        # Set up a regular expression to search for the proper host stanza
        regexp = re.compile(macaddr)

        found = False
        in_host = False
        remove_finished = False
        new_cfg = list()
        hostlines = list()
        consec_newlines = 0
        # Walk through the current configuration lines, adding them to a new
        # list (which we will write out to the new copy of the configuration
        # file). If we hit a host stanza, start saving the strings off in a
        # separate list, since it might be the host stanza we are removing and
        # we won't know until we hit the 'hardware ethernet' line. If it's not
        # the stanza we want to remove, then we can just add it to the new list
        # and move on.
        for line in current_cfg:
            # When removing stanzas, errant newlines can build up over time.
            if line == '\n':
                consec_newlines += 1
                if consec_newlines > 1:
                    continue
            else:
                consec_newlines = 0

            if not remove_finished:
                if line.startswith("host"):
                    # We're in a host stanza, init a new list and start saving
                    # this stanza to it.
                    in_host = True
                    hostlines = list()
                    hostlines.append(line)
                    continue
                if in_host and line.strip().endswith("}"):
                    # We're at the end of a host stanza, clear our flag.
                    in_host = False

                    # Add this final line to the hostlines list.
                    hostlines.append(line)

                    # If we've not found our host yet, then this host stanza
                    # we've just hit the end of needs to be written out to the
                    # new file; add these lines to 'new_cfg'.
                    if not found:
                        new_cfg.extend(hostlines)
                        continue

                    # If we have found the host we're removing, set our
                    # finished flag and just move on, leaving this host
                    # stanza behind.
                    remove_finished = True
                    continue
                if in_host and regexp.search(line):
                    # We've found the right host stanza
                    found = True

            # If we're in a host stanza, tuck this line away on the current
            # hostlines list. Otherwise, add it to the new configuration file.
            if in_host:
                hostlines.append(line)
            else:
                new_cfg.append(line)

        # Write out the configuration lines, sans our host stanza, to the
        # tempfile, then move the tempfile over to the configuration file.
        with open(tmp_cfgfile, "w") as tmp_cfg:
            for line in new_cfg:
                tmp_cfg.write(line)

        os.rename(tmp_cfgfile, current_cfgfile)

    def _get_arch_class(self, arch):
        '''
        If found, return a DHCPArchClass object that represents the currently
        configured architecture class from the DHCP configuration file.
        Arguments:
            arch - either 'i386' or 'sparc'
        '''
        return DHCPArchClass.get_arch(self, arch)

    def arch_class_is_set(self, arch):
        '''
        Returns True if there is currently an architecture-based class stanza
        in the DHCP server configuration.
        Arguments:
            arch - either 'i386' or 'sparc'
        '''
        if self._get_arch_class(arch) is not None:
            return True
        else:
            return False

    def add_arch_class(self, arch, bootfile):
        '''
        Add an x86 architecture class to the DHCP configuration.
        Arguments:
            arch - The architecture to set this bootfile for.
            bootfile - The bootfile
        '''
        logging.debug("dhcp.add_arch_class: arch [%s] bootfile [%s]", arch,
                      bootfile)

        if self.arch_class_is_set(arch):
            raise DHCPServerError(_("the %s architecture already has a class "
                                    "set in the DHCP configuration") % arch)

        if arch == 'i386':
            new_stanza = _DHCPConfigPXEClass(bootfile)
        elif arch == 'sparc':
            bootfile = fixup_sparc_bootfile(bootfile, True)
            new_stanza = _DHCPConfigSPARCClass(bootfile)
        else:
            raise ValueError(_("invalid architecture: %s") % arch)

        self._add_stanza_to_config_file(new_stanza)

    def get_bootfile_for_arch(self, arch):
        '''
        Returns the current bootfile set on this architecture, or None if its
        not set (or if this architecture is not configured at all).
        Arguments:
            arch - either 'i386' or 'sparc'
        '''
        arch_class = self._get_arch_class(arch)
        if arch_class is not None:
            return arch_class.bootfile
        else:
            return None

    def add_bootfile_to_arch(self, arch, bootfile):
        '''
        Add 'bootfile' to the architecture class specified.
        Arguments:
            arch - The architecture to set this bootfile for
            bootfile - The bootfile
        Raises DHCPServerError if the class does not exist or if the bootfile
        is already set.
        '''
        arch_class = self._get_arch_class(arch)
        if arch_class is None:
            raise DHCPServerError(_("class must exist to set bootfile"))
        arch_class.set_bootfile(bootfile)

    def update_bootfile_for_arch(self, arch, bootfile):
        '''
        Update the existing bootfile in place.
        Arguments:
            arch - The architecture to update
            bootfile - The bootfile
        Raises DHCPServerError if the class does not exist.
        '''
        arch_class = self._get_arch_class(arch)
        if arch_class is None:
            raise DHCPServerError(_("class must exist to update bootfile"))
        arch_class.update_bootfile(bootfile)

    def unset_bootfile_for_arch(self, arch):
        '''
        Clear the bootfile setting for this architecture.
        '''
        arch_class = self._get_arch_class(arch)
        if arch_class is None:
            raise DHCPServerError(_("class must exist to unset bootfile"))
        arch_class.unset_bootfile()


def _get_mask(ipaddr):
    '''
    Derive the netmask for this subnet by either retrieving it from netmasks(4)
    or from the output of ifaddrs(). Since we've come through the rest of the
    installadm code, we know that at least one of these requirements will be
    met. Raise DHCPServerError if it cannot be determined for whatever reason.
    '''
    logging.debug("dhcp._get_mask: ipaddr [%s]", ipaddr)

    # Check netmasks(4) for an entry.
    cmd = [GETENT, "netmasks", ipaddr]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', check_result=Popen.ANY,
                         stderr_loglevel=logging.DEBUG)
    if p.returncode == 0:
        (sn, sep, netmask) = p.stdout.partition(' ')
        if sep:
            logging.debug("dhcp._get_mask: found mask [%s]", netmask.strip())
            return netmask.strip()

    # If no netmasks entry is found, then we'll have to see if we can determine
    # it from an IP address on this host. Walk the list of up NICs, and using
    # their IP addresses and masks determine which subnet they are members of.
    # Then, test that same netmask and our IP to determine if we are a member.
    for addr in getifaddrs().values():
        (ip, sep, mask) = addr.rpartition("/")
        if sep:
            this_mask = com._convert_cidr_mask(int(mask))
            this_net = _get_subnet(ip, this_mask)
            if _ip_is_in_network(ipaddr, this_net, this_mask):
                logging.debug("dhcp._get_mask: found mask [%s]", this_mask)
                return this_mask

    # If no netmasks entry is found and there is no NIC up, then fail.
    logging.debug("dhcp._get_mask: no mask found")
    raise DHCPServerError(_("unable to determine netmask for [%s]") % ipaddr)


def _get_nextserver_ip_for_subnet(subnet_ip, netmask):
    '''
    Return the local IP address to use as 'nextserver' (the server that
    clients will request boot files from) for the passed subnet. If there
    is a single IP address configured, just return that. Otherwise, determine
    the correct IP address based upon membership in the subnet.
    '''
    logging.debug("dhcp._get_nextserver_ip_for_subnet: subnet_ip %s "
                  "netmask %s", subnet_ip, netmask)

    ifaddrs = dict()
    ifaddrs = getifaddrs()

    # If there is only one IP address configured on this system, return it.
    if len(ifaddrs) == 1:
        addr = ifaddrs.values()[0]
        (ip, sep, mask) = addr.rpartition("/")
        if sep:
            logging.debug("dhcp._get_nextserver_ip_for_subnet: found %s", ip)
            return ip

    # This is a multihomed server, so walk the list of configured addresses
    # and return the first IP address that is a member of subnet_ip.
    for addr in ifaddrs.values():
        (ip, sep, mask) = addr.rpartition("/")
        if sep:
            if _ip_is_in_network(ip, subnet_ip, netmask):
                logging.debug("dhcp._get_nextserver_ip_for_subnet: found "
                              "%s", ip)
                return ip


def _get_subnet(ipaddr, netmask):
    '''
    Derive the subnet of this IP address and return it in "A.B.C.D" format.
    '''
    ipaddr_int = struct.unpack('L', socket.inet_aton(ipaddr))[0]
    mask_int = struct.unpack('L', socket.inet_aton(netmask))[0]
    return socket.inet_ntoa(struct.pack('L', ipaddr_int & mask_int))


def _get_broadcast_address(subnet_ip, netmask_ip):
    '''
    Calculate the broadcast address for this subnet from the subnet address
    and its netmask.
    '''
    subnet_int = struct.unpack('L', socket.inet_aton(subnet_ip))[0]
    netmask_int = struct.unpack('L', socket.inet_aton(netmask_ip))[0]
    return socket.inet_ntoa(struct.pack('L',
                            subnet_int | (0xffffffff - netmask_int)))


def _ip_is_in_network(ipaddr, subnet_ip, netmask):
    '''
    Return True if ipaddr is a member of the subnet_ip network.
    '''
    ipaddr_int = struct.unpack('L', socket.inet_aton(ipaddr))[0]
    subnet_int = struct.unpack('L', socket.inet_aton(subnet_ip))[0]
    netmask_int = struct.unpack('L', socket.inet_aton(netmask))[0]
    return (ipaddr_int & netmask_int) == (subnet_int & netmask_int)


def _set_and_check_hiaddr(subnet_ip, netmask, loaddr, count):
    '''
    For establishing the high end of a range. Given the low-side and a count,
    return the A.B.C.D form of the high address. Also ensure it's not above
    the upper bound for the network. Raises a ValueError if the format of
    loaddr is bad, and DHCPServerError if it will result in the high address
    being outside of the upper bound of this network.
    '''
    regexp = re.compile("^(\d{1,3}\.\d{1,3}\.\d{1,3}\.)(\d{1,3})$")
    m = regexp.match(loaddr)
    if m is None:
        raise ValueError("set_and_check_hiaddr: bad format %s", loaddr)

    hituple = int(m.group(2)) + (count - 1)
    hiaddr = m.expand(m.group(1) + str(hituple))
    if hituple > 255 or not _ip_is_in_network(hiaddr, subnet_ip, netmask):
        raise DHCPServerError(_("set_and_check_hiaddr: high address based " \
            "upon start IP (-i) and count (-c) will result in out of bounds"))
    return hiaddr


def _check_subnet_for_overlap(subnet, loaddr, hiaddr):
    '''
    Passed a DHCPSubnet object, determine if we will create an overlap in
    addresses with the proposed new range, defined by loaddr and hiaddr, with
    any existing ranges. If an overlap would occur, raises DHCPServerError.
    '''
    if not isinstance(subnet, DHCPSubnet):
        raise ValueError('object passed not a DHCPSubnet object')

    # Set up a regular expression to pull the last tuple from IP and use it to
    # pull off the last tuple of the addrs passed in.  Then build a set
    # consisting of the entire range.
    regexp = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.(\d{1,3})$")
    new_addrs = [int(m.group(1))
        for m in filter(bool, map(regexp.match, [loaddr, hiaddr]))]
    new_set = set(range(new_addrs[0], (new_addrs[1] + 1)))

    # Now do the same for each range that is configured for this subnet and
    # compare to our new set as we iterate through.  If any duplicates are
    # found, we have an overlap, and we'll fail the allocation.
    for r in subnet.ranges:
        addrs = [int(m.group(1)) for m in filter(bool, map(regexp.match, r))]
        if new_set & set(range(addrs[0], (addrs[1] + 1))):
            raise DHCPServerError(cw(_("check_subnet_for_overlap: adding "
                                       "range causes overlap on subnet %s")
                                       % subnet.subnet_ip))


def _get_domain(svc):
    '''
    Returns the domainname of the name service passed as 'svc'. Supported
    values of svc are 'dns' and 'nis'. Returns None if no domainname is
    set or if the svc passed is not online.
    '''
    if svc not in ['dns', 'nis']:
        raise ValueError(_("invalid name service: %s") % svc)

    service = _ns_map[svc]['SVC_NAME']
    prop = _ns_map[svc]['DOMAIN_PROP']

    cmd = [SVCS, "-Ho", "STATE", service]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', stderr_loglevel=logging.DEBUG)
    if p.stdout.strip() != 'online':
        return None

    cmd = [SVCPROP, "-p", prop, service]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', stderr_loglevel=logging.DEBUG)
    
    return p.stdout.strip()


def _get_nameservers(svc):
    '''
    Returns a comma-separated string of name server(s) for the protocol named
    in 'svc' if any are configured. Supported values of svc are 'dns' and
    'nis'. Returns None if no servers are found, or if the svc passed is not
    online.
    '''
    if svc not in ['dns', 'nis']:
        raise ValueError(_("invalid name service: %s") % svc)

    service = _ns_map[svc]['SVC_NAME']
    prop = _ns_map[svc]['SERVER_PROP']

    cmd = [SVCS, "-Ho", "STATE", service]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', stderr_loglevel=logging.DEBUG)
    if p.stdout.strip() != 'online':
        return None

    cmd = [SVCPROP, "-p", prop, service]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', stderr_loglevel=logging.DEBUG)
    servers = p.stdout.strip().split()
    if servers is not None:
        servers = ', '.join([ip for ip in servers])

    return servers


def _get_default_route_for_subnet(subnet_ip):
    '''
    Find the default route for the subnet passed.
    '''
    logging.debug("dhcp._get_default_route_for_subnet: subnet_ip %s",
                  subnet_ip)

    # Since we have a requirement to be connected to the subnets we're
    # configuring (in check-server-setup), we can find a default route
    # in netstat output.
    cmd = [NETSTAT, "-nr"]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger='', stderr_loglevel=logging.DEBUG)

    regexp = re.compile('^default\s+(%s)\s+' % IP_PATTERN)
    for route in [m.group(1)
        for m in filter(bool, map(regexp.match, p.stdout.splitlines()))]:
            if _ip_is_in_network(route, subnet_ip, _get_mask(route)):
                logging.debug("dhcp._get_default_route_for_subnet: found  %s",
                              route)
                return route

    print >> sys.stderr, cw(_("\nUnable to determine a route for network %s. "
                              "Setting the route temporarily to %s; this "
                              "should be changed to an appropriate value in "
                              "the DHCP configuration file. Please see "
                              "dhcpd(8) for further information.\n") %
                              (subnet_ip, INVALID_IP))

    logging.debug("dhcp._get_default_route_for_subnet: no route found")
    return INVALID_IP


def fixup_sparc_bootfile(bootfile, verbose=False):
    '''
    For a SPARC bootfile, ensure that a useful IP address is set on the
    webserver portion of the address string. From service.py, we have a
    bootfile for SPARC clients that includes the $serverIP string, which is
    used by AI clients to determine their bootserver IP address. But, we
    cannot use this in a DHCP configuration, so we have to fix that here.
    '''
    # We don't support multiple subnet configurations yet, so we should
    # be able to simply use the IP address returned from get_valid_networks().
    valid_nets = list(com.get_valid_networks())
    if valid_nets:
        ipaddr = valid_nets[0] 
    else:
        if verbose:
            print >> sys.stderr, cw(_("\nNo networks are currently set to "
                                      "work with install services. Verify the "
                                      "install/server SMF properties are set "
                                      "properly. See installadm(1M) for "
                                      "further information. The SPARC "
                                      "bootfile setting in the local DHCP "
                                      "server requires manual configuration. "
                                      "Please see dhcpd(8) for further "
                                      "information.\n"))
        logging.debug("dhcp.fixup_sparc_bootfile: no IP found")
        return bootfile

    # If we have more than one network configured, warn and use the first.
    if len(valid_nets) > 1 and verbose:
        print >> sys.stderr, cw(_("\nMore than one subnet is configured for "
                                  "use with AI. Using IP address '%s'. Please "
                                  "ensure this is a suitable address to use "
                                  "for SPARC install clients. See "
                                  "installadm(1M) further information.\n") %
                                  ipaddr)

    logging.debug("dhcp.fixup_sparc_bootfile: setting IP address %s", ipaddr)
    return re.sub('\$serverIP', ipaddr, bootfile)

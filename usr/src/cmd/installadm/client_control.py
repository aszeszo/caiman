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
AI create-client / delete-client
'''
import logging
import os
import re
import shutil
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.dhcp as dhcp
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.grub as grub
import osol_install.auto_install.service_config as config

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.auto_install.service import AIService
from solaris_install import force_delete


def _cleanup_files(client_id, more_files=()):
    '''
    Removes any files that might have been used by this client at
    some point. For simplicity's sake, we check both architectures.
    '''
    # The following files may be vestiges from failed calls to delete-service,
    # old versions of installadm, etc.
    # More care must be taken to avoid unintentionally clobbering desired
    # config.
    cleanup = [_menulst_path(client_id),               # x86 menu.lst file
               _pxegrub_path(client_id)[1],            # x86 pxegrub symlink
               os.path.join(com.BOOT_DIR, client_id)]  # SPARC symlink

    # Now add in any files passed by the caller
    cleanup.extend(more_files)

    # Search for pre-multihomed, subnet-specific SPARC directories
    # (e.g., /etc/netboot/192.168.0.0/010011AABB/) and add those.
    subnet = re.compile(dhcp.IP_PATTERN)
    for f in os.listdir(com.BOOT_DIR):
        if subnet.match(f):
            d = os.path.join(com.BOOT_DIR, f, client_id)
            if os.path.isdir(d):
                cleanup.append(d)

    # Finally, delete any files or directories from our list that
    # might exist on the system.
    for f in cleanup:
        if os.access(f, os.F_OK) or os.path.islink(f):
            force_delete(f)


def _menulst_path(client_id):
    return os.path.join(com.BOOT_DIR, grub.MENULST + "." + client_id)


def _pxegrub_path(client_id):
    return client_id, os.path.join(com.BOOT_DIR, client_id)


def setup_x86_client(service, mac_address, bootargs=''):
    ''' Set up an x86 client

    Creates a relative symlink from the <svcname>'s bootfile to
        /etc/netboot/<client_id>
    Creates /etc/netboot/menu.lst.<client_id> boot configuration file
    Adds client info to AI_SERVICE_DIR_PATH/<svcname>/.config file

    Arguments:
              image_path - directory path to AI image
              mac_address - client MAC address (as formed by
                            MACAddress class, i.e., 'ABABABABABAB')
              bootargs = bootargs of client (x86)
    Returns: Nothing

    '''
    # create a client-identifier (01 + MAC ADDRESS)
    client_id = "01" + mac_address

    menulst = os.path.join(service.config_dir, grub.MENULST)
    client_menulst = _menulst_path(client_id)

    # copy service's menu.lst file to menu.lst.<client_id>
    try:
        shutil.copy(menulst, client_menulst)
    except IOError as err:
        print >> sys.stderr, cw(_("Unable to copy grub menu.lst file: %s") %
           err.strerror)
        return

    # create a symlink from the boot directory to the sevice's bootfile.
    # note this must be relative from the boot directory.
    bootfile, pxegrub_path = _pxegrub_path(client_id)
    os.symlink("./" + service.dhcp_bootfile, pxegrub_path)

    clientinfo = {config.FILES: [client_menulst, pxegrub_path]}

    # if the client specifies bootargs, use them. Otherwise, inherit
    # the bootargs specified in the service (do nothing)
    if bootargs:
        grub.update_bootargs(client_menulst, service.bootargs, bootargs)
        clientinfo[config.BOOTARGS] = bootargs

    config.add_client_info(service.name, client_id, clientinfo)

    # Configure DHCP for this client if the configuration is local, otherwise
    # suggest the configuration addition. Note we only need to do this for
    # x86-based clients, not SPARC.
    server = dhcp.DHCPServer()
    if server.is_configured():
        # We'll need the actual hardware ethernet address for the DHCP entry,
        # rather than the non-delimited string that 'mac_address' is.
        full_mac = AIdb.formatValue('mac', mac_address)
        try:
            print cw(_("Adding host entry for %s to local DHCP configuration.")
                       % full_mac)
            server.add_host(full_mac, bootfile)
        except dhcp.DHCPServerError as err:
            print cw(_("Unable to add host (%s) to DHCP configuration: %s") %
                      (full_mac, err))
            return

        if server.is_online():
            try:
                server.control('restart')
            except dhcp.DHCPServerError as err:
                print >> sys.stderr, cw(_("\nUnable to restart the DHCP SMF "
                                          "service: %s\n" % err))
                return
        else:
            print cw(_("\nLocal DHCP configuration complete, but the DHCP "
                       "server SMF service is offline. To enable the "
                       "changes made, enable: %s.\nPlease see svcadm(1M) "
                       "for further information.\n") % 
                       dhcp.DHCP_SERVER_IPV4_SVC)
    else:
        # No local DHCP, tell the user all about their boot configuration
        valid_nets = list(com.get_valid_networks())
        if valid_nets:
            server_ip = valid_nets[0]

        print cw(_("No local DHCP configuration found. If not already "
                   "configured, the following should be added to the DHCP "
                   "configuration:"))
        print _("\t%-20s : %s\n\t%-20s : %s" %
               ("Boot server IP", server_ip, "Boot file", bootfile))

        if len(valid_nets) > 1:
            print cw(_("\nNote: determined more than one IP address "
                       "configured for use with AI. Please ensure the above "
                       "'Boot server IP' is correct.\n"))



def setup_sparc_client(service, mac_address):
    '''
    Creates symlink from /etc/netboot/<client_id> to
        /etc/netboot/<svcname>
    Adds client info to AI_SERVICE_DIR_PATH/<svcname>/.config file
    Arguments:
              image_path - directory path to AI image
              mac_address - client MAC address (as formed by
                            MACAddress class, i.e., 'ABABABABABAB')
    Returns: Nothing

    '''
    # create a client-identifier (01 + MAC ADDRESS)
    client_id = "01" + mac_address

    source = service.mountpoint
    link_name = os.path.join(com.BOOT_DIR, client_id)
    logging.debug("creating symlink from %s to %s", link_name, source)
    os.symlink(source, link_name)
    clientinfo = {config.FILES: [link_name]}
    config.add_client_info(service.name, client_id, clientinfo)


def remove_client(client_id):
    ''' Remove client configuration

        If client configuration incomplete (e.g., dangling symlink),
        cleanup anyway.

     '''
    logging.debug("Removing client config for %s", client_id)

    (service, datadict) = config.find_client(client_id)
    more_files = list()
    if service:
        # remove client info from .config file
        config.remove_client_from_config(service, client_id)
        if AIService(service).arch == 'i386':
            # suggest dhcp unconfiguration
            remove_client_dhcp_config(client_id)

    # remove client specific symlinks/files
    _cleanup_files(client_id, more_files)


def remove_client_dhcp_config(client_id):
    '''
    If a local DHCP server is running, remove any client configuration for
    this client from its configuration. If not, inform end-user that the
    client-service binding should no longer be referenced in the DHCP
    configuration.
    '''
    server = dhcp.DHCPServer()
    if server.is_configured():
        # A local DHCP server is configured. Check for a host entry and remove
        # it if found.
        mac_address = client_id[2:]
        mac_address = AIdb.formatValue('mac', mac_address)
        if server.host_is_configured(mac_address):
            print cw(_("Removing host entry '%s' from local DHCP "
                       "configuration.") % mac_address)
            server.remove_host(mac_address)

            if server.is_online():
                try:
                    server.control('restart')
                except dhcp.DHCPServerError as err:
                    print >> sys.stderr, cw(_("Unable to restart the DHCP "
                                              "SMF service: %s" % err))
                    return
    else:
        # No local DHCP configuration, inform user that it needs to be
        # unconfigured elsewhere.
        print cw(_("No local DHCP configuration found. Unless it will be "
                   "reused, the bootfile '%s' may be removed from the DHCP "
                   "configuration\n" % client_id))

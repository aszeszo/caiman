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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''
AI create-client
'''
import gettext
import logging
import os

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.client_control as clientctrl
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service as svc
import osol_install.auto_install.service_config as config

from optparse import OptionParser, OptionValueError

from bootmgmt import BootmgmtError
from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen


def get_usage():
    ''' get usage for create-client'''
    return(_(
        'create-client\t[-b|--boot-args <property>=<value>,...] \n'
        '\t\t-e|--macaddr <macaddr> -n|--service <svcname>'))


def parse_options(cmd_options=None):
    '''
    Parse and validate options
    '''

    def check_MAC_address(option, opt_str, value, parser):
        '''
        Check MAC address as an OptionParser callback
        Postcondition: sets value to proper option if check passes
        Raises: OptionValueError if MAC address is malformed
        '''
        try:
            value = str(com.MACAddress(value))
        except com.MACAddress.MACAddressError as err:
            raise OptionValueError(str(err))
        setattr(parser.values, option.dest, value)

    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage)

    # accept multiple -b options (so append to a list)
    parser.add_option("-b", "--boot-args", dest="boot_args", action="append",
                      type="string", nargs=1,
                      help=_("boot arguments to pass to Solaris kernel"))
    parser.add_option("-e", "--macaddr", dest="mac_address", action="callback",
                      nargs=1, type="string",
                      help=_("MAC address of client to add"),
                      callback=check_MAC_address)
    parser.add_option("-n", "--service", dest="service_name", action="store",
                      type="string",
                      help=_("Service to associate client with"), nargs=1)
    (options, args) = parser.parse_args(cmd_options)

    if args:
        parser.error(_("Unexpected argument(s): %s" % args))

    # check that we got a service name and mac address
    if options.service_name is None:
        parser.error(_("Service name is required "
                       "(-n|--service <service name>)."))
    if options.mac_address is None:
        parser.error(_("MAC address is required (-e|--macaddr <macaddr>)."))

    # Verify that the server settings are not obviously broken.
    # These checks cannot be complete, but check for things which
    # will definitely cause failure.
    logging.debug("Calling %s", com.CHECK_SETUP_SCRIPT)
    ret = Popen([com.CHECK_SETUP_SCRIPT]).wait()
    if ret:
        raise SystemExit(1)

    # validate service name
    try:
        com.validate_service_name(options.service_name)
    except ValueError as err:
        raise SystemExit(err)

    # check that the service exists
    service_props = config.get_service_props(options.service_name)
    if not service_props:
        raise SystemExit(_("The specified service does not exist: %s\n") %
                       options.service_name)

    # get the image_path from the service
    try:
        # set image to be a InstalladmImage object
        image = svc.AIService(options.service_name).image
    except KeyError:
        raise SystemExit(_("\nThe specified service does not have an "
                           "image_path property.\n"))

    # ensure we are not passed bootargs for a SPARC as we do not
    # support that
    if options.boot_args and image.arch == "sparc":
        parser.error(_("Boot arguments not supported for SPARC clients.\n"))

    options.arch = image.arch

    logging.debug("options = %s", options)

    return options


def create_new_client(arch, service, mac_address, bootargs=None,
                      suppress_dhcp_msgs=False):
    '''Create a new client of a service and ensure the Automated
       Install SMF service is enabled.

       Input: arch - architecture of service ('i386' or 'sparc')
              service - The AIService to attach to
              mac_address - mac address of client
              bootargs - boot arguments to insert in client menu.lst file (x86)
              suppress_dhcp_msgs - if True, suppresses informational messages
                                   about DHCP configuration
       Returns: Nothing

    '''
    logging.debug("creating new client for service %s, mac %s, "
                  "arch %s, bootargs %s, suppress_dhcp_msgs=%s",
                  service.name, mac_address, arch, bootargs,
                  suppress_dhcp_msgs)
    if arch == 'i386':
        clientctrl.setup_x86_client(service, mac_address, bootargs=bootargs,
                                    suppress_dhcp_msgs=suppress_dhcp_msgs)
    else:
        clientctrl.setup_sparc_client(service, mac_address)

    # If the installation service this client is being created for
    # is not enabled, print warning to the user.
    if not config.is_enabled(service.name):
        logging.debug("service is disabled: %s", service.name)
        print cw(_("\nWarning: the installation service, %s, is disabled. "
                   "To enable it, use 'installadm enable %s'.") %
                   (service.name, service.name))


def do_create_client(cmd_options=None):
    '''Parse the user supplied arguments and create the specified client'''

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    # parse server options
    options = parse_options(cmd_options)

    bootargs = ''
    if options.boot_args:
        bootargs = ",".join(options.boot_args).lstrip().rstrip() + ","
        logging.debug('bootargs=%s', bootargs)

    clientctrl.remove_client("01" + options.mac_address,
                             suppress_dhcp_msgs=True)

    # wrap the whole program's execution to catch exceptions as we should not
    # throw them anywhere
    service = svc.AIService(options.service_name)
    try:
        create_new_client(options.arch, service,
                          options.mac_address, bootargs)
    except (OSError, BootmgmtError, aismf.ServicesError,
            config.ServiceCfgError, svc.MountError) as err:
        raise SystemExit(_('\nError: Unable to create client, %s:\n%s') %
                         (options.mac_address, err))


if __name__ == "__main__":
    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")
    do_create_client()

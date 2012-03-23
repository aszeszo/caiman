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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
'''
AI delete-service
'''
import gettext
import logging
import os
import sys

import osol_install.auto_install.client_control as clientctrl
import osol_install.auto_install.dhcp as dhcp
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.auto_install.service import AIService, DEFAULT_ARCH


def get_usage():
    ''' get usage for delete-service'''
    return(_('delete-service [-r|--autoremove] [-y|--noprompt] <svcname>]'))


def parse_options(cmd_options=None):
    '''
    Parse and validate options when called as delete-service
    Args: None
    Returns: A tuple of a dictionary of service properties of service
             to delete and an options object

    '''
    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage)
    parser.add_option("-r", "--autoremove", dest="autoremove",
                      action="store_true",
                      default=False,
                      help=_("Request removal of dependent alias services "
                             "and clients"))
    parser.add_option('-y', "--noprompt", action="store_true",
                      dest="noprompt", default=False,
                      help=_('Suppress confirmation prompts and proceed with '
                      'service deletion'))

    (options, args) = parser.parse_args(cmd_options)

    # Confirm install service's name was passed in
    if not args:
        parser.error(_("Missing required argument, <svcname>"))
    elif len(args) > 1:
        parser.error(_("Too many arguments: %s") % args)

    service_name = args[0]

    # validate service name
    try:
        com.validate_service_name(service_name)
    except ValueError as err:
        raise SystemExit(err)
    if not config.is_service(service_name):
        raise SystemExit(_("\nError: The specified service does "
                           "not exist: %s\n") % service_name)

    # add service_name to the options
    options.service_name = service_name
    logging.debug("options = %s", options)

    return options


def remove_dhcp_configuration(service):
    '''
    Determines if a local DHCP server is running and if this service's bootfile
    is set as the architecture's default boot service. If it is, we'll unset it
    as we're deleting the service. If the DHCP configuration isn't local,
    inform the end-user that the DHCP configuration should not reference this
    bootfile any longer.
    '''
    logging.debug("in remove_dhcp_configuration, service=%s", service.name)

    # Skip SPARC services, since they share a global bootfile
    if service.arch == 'sparc':
        return

    server = dhcp.DHCPServer()
    if server.is_configured():
        # Server is configured. Regardless of its current state, check for
        # this bootfile in the service's architecture class. If it is set as
        # the default for this architecture, unset it.
        try:
            arch_class = dhcp.DHCPArchClass.get_arch(server, service.arch)
        except dhcp.DHCPServerError as err:
            print >> sys.stderr, cw(_("\nUnable to access DHCP configuration: "
                                      "%s\n" % err))
            return

        if arch_class is None or arch_class.bootfile is None:
            # nothing to do
            return

        logging.debug("arch_class.bootfile is %s", arch_class.bootfile)
        if isinstance(arch_class.bootfile, list):
            # The list consists of tuples: (archval, relpath to bootfile)
            # e.g., [('00:00', '<svcname>/boot/grub/pxegrub2'),..]
            # Using the first tuple, get the service name.
            relpath = arch_class.bootfile[0][1]
        else:
            relpath = arch_class.bootfile
        parts = relpath.partition('/')
        arch_svcname = parts[0]

        if arch_svcname == service.name:
            try:
                print cw(_("Removing this service's bootfile(s) from local "
                           "DHCP configuration\n"))
                arch_class.unset_bootfile()
            except dhcp.DHCPServerError as err:
                print >> sys.stderr, cw(_("\nUnable to unset this service's "
                                          "bootfile(s) in the DHCP "
                                          "configuration: %s\n" % err))
                return

            if server.is_online():
                try:
                    server.control('restart')
                except dhcp.DHCPServerError as err:
                    print >> sys.stderr, cw(_("\nUnable to restart the DHCP "
                                              "SMF service: %s\n" % err))


def delete_specified_service(service_name, auto_remove, noprompt):
    ''' Delete the specified Automated Install Service
    Input: service_name - service name
           auto_remove - boolean, True if dep. aliases and clients should
                         be removed, False otherwise
           noprompt - boolean, True if warning about removing
                           default-<arch> service should be suppressed
    '''
    logging.debug("delete_specified_service %s %s %s", service_name,
                  auto_remove, noprompt)

    service = AIService(service_name)

    # If the '-r' option has not been specified, look for all
    # dependent aliases and clients
    all_aliases = config.get_aliased_services(service_name, recurse=True)
    if not auto_remove:
        all_clients = config.get_clients(service_name).keys()
        for ale in all_aliases:
            all_clients.extend(config.get_clients(ale).keys())

        # if any aliases or clients are dependent on this service, exit
        if all_aliases or all_clients:
            raise SystemExit(cw(_("\nError: The following aliases and/or "
                                  "clients are dependent on this service:\n\n"
                                  "%s\n\nPlease update or delete them prior "
                                  "to deleting this service or rerun this "
                                  "command using the -r|--autoremove option "
                                  "to have them automatically removed.\n") %
                                  '\n'.join(all_aliases + all_clients)))

    # Prompt user if they are deleting the default-sparc or default-i386 alias
    if not noprompt:
        sname = None
        if service_name in DEFAULT_ARCH:
            sname = service_name
        else:
            default_alias = set(DEFAULT_ARCH) & set(all_aliases)
            if default_alias:
                sname = ''.join(default_alias)
        if sname:
            arch = sname.split('default-')[1]
            _warning = """
            WARNING: The service you are deleting, or a dependent alias, is
            the alias for the default %(arch)s service. Without the '%(name)s'
            service, %(arch)s clients will fail to boot unless explicitly
            assigned to a service using the create-client command.
            """ % {'arch': arch,
                   'name': sname}

            print >> sys.stderr, cw(_(_warning))
            prompt = _("Are you sure you want to delete this alias? [y/N]: ")
            if not com.ask_yes_or_no(prompt):
                raise SystemExit(1)

    # If there are dependent aliases or clients, then remove these first
    aliases = config.get_aliased_services(service_name)
    for dependent in aliases:
        logging.debug("recursively calling delete_specified_service for %s",
                       dependent)
        delete_specified_service(dependent, True, True)

    clients = config.get_clients(service_name).keys()
    for dependent in clients:
        logging.debug("calling remove_client for %s", dependent)
        clientctrl.remove_client(dependent)

    logging.debug("now deleting service %s", service_name)

    # remove DHCP bootfile configuration for this service, if set
    remove_dhcp_configuration(service)

    # stop the service first (avoid pulling files out from under programs)
    try:
        service.delete()
    except StandardError as err:
        # Bail out if the service could not be unmounted during the disable,
        # as it won't be possible to delete necessary files.
        print >> sys.stderr, _("\nService could not be deleted.")
        raise SystemExit(err)

    # if this was the last service, go to maintenance
    config.check_for_enabled_services()


def do_delete_service(cmd_options=None):
    '''
    Entry point for delete_service

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for this "
                           "command.\n"))

    # parse server options
    options = parse_options(cmd_options)
    delete_specified_service(options.service_name, options.autoremove,
                             options.noprompt)


if __name__ == "__main__":
    # initialize gettext
    gettext.install('ai', '/usr/lib/locale')

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_delete_service()

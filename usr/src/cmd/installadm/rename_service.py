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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
"""
AI rename-service
"""
import gettext
import logging
import os
import sys

import osol_install.auto_install.client_control as clientctrl
import osol_install.auto_install.create_client as create_client
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from bootmgmt import BootmgmtError
from osol_install.auto_install.image import ImageError
from osol_install.auto_install.installadm_common import _, \
    validate_service_name, cli_wrap as cw
from osol_install.auto_install.service import AIService, MountError, \
    DEFAULT_ARCH


def get_usage():
    ''' get usage for rename-service'''
    return(_('rename-service\t<svcname> <newsvcname>'))


def parse_options(cmd_options=None):
    """
    Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: tuple consisting of svcname and newsvcname
    """

    usage = '\n' + get_usage()

    parser = OptionParser(usage=usage)

    # Get the parsed arguments using parse_args()
    unused, args = parser.parse_args(cmd_options)

    if len(args) < 2:
        parser.error(_("Missing one or more required arguments."))
    elif len(args) > 2:
        parser.error(_("Too many arguments: %s" % args))

    svcname = args[0]
    newsvcname = args[1]

    # validate service names
    try:
        validate_service_name(newsvcname)
    except ValueError as err:
        parser.error(err)

    logging.debug("Renaming %s to %s", svcname, newsvcname)

    return (svcname, newsvcname)


def do_rename_service(cmd_options=None):
    '''Rename a service and update all associated aliases and clients.

    Note: Errors that occur during the various rename stages
    are printed, but the other stages will continue, with the hopes
    of leaving the final product as close to functional as possible

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for this "
                           "command.\n"))

    (svcname, newsvcname) = parse_options(cmd_options)

    # Ensure the service to rename is a valid service
    if not config.is_service(svcname):
        raise SystemExit(_("\nFailed to find service %s\n") % svcname)

    # Ensure the new name is not already a service
    if config.is_service(newsvcname):
        raise SystemExit(_("\nService or alias already exists: %s\n") %
                           newsvcname)

    # Don't allow renaming to/from the 'default-<arch>' aliases
    if svcname in DEFAULT_ARCH:
        raise SystemExit(_('\nYou may not rename the "%s" service.\n') %
                           svcname)

    if newsvcname in DEFAULT_ARCH:
        raise SystemExit(cw(_('\nYou may not rename a service to be the '
                              'default service for an architecture. To create '
                              'the default-sparc or default-i386 service '
                              'aliases, use "installadm create-service '
                              '-t|--aliasof."\n')))

    # Unmount old service
    was_mounted = False
    try:
        oldservice = AIService(svcname)
        if oldservice.mounted():
            was_mounted = True
            logging.debug("disabling %s", svcname)
            oldservice.disable(force=True)
    except (MountError, ImageError) as err:
        raise SystemExit(err)

    # remove old mountpoint
    try:
        os.rmdir(oldservice.mountpoint)
    except OSError as err:
        # Just make a note if unable to cleanup mountpoint
        logging.debug(err)

    # Remove clients whose base service has been renamed
    clients = config.get_clients(svcname)
    for clientid in clients.keys():
        clientctrl.remove_client(clientid, suppress_dhcp_msgs=True)

    try:
        oldservice.rename(newsvcname)
    except BootmgmtError as err:
        raise SystemExit(err)

    # Update aliases whose base service has been renamed
    aliases = config.get_aliased_services(svcname)
    failures = list()
    for alias in aliases:
        props = {config.PROP_ALIAS_OF: newsvcname}
        config.set_service_props(alias, props)

    # Mount the renamed service if it was mounted
    newservice = AIService(newsvcname)
    if was_mounted:
        try:
            logging.debug("enabling %s", newsvcname)
            newservice.enable()
        except (MountError, ImageError) as err:
            failures.append(err)
            print >> sys.stderr, err

    # Re-add clients whose base service has been renamed
    arch = newservice.arch
    for clientid in clients.keys():
        # strip off leading '01'
        client = clientid[2:]
        bootargs = None
        if config.BOOTARGS in clients[clientid]:
            bootargs = clients[clientid][config.BOOTARGS]
        try:
            create_client.create_new_client(arch, newservice, client,
                bootargs=bootargs, suppress_dhcp_msgs=True)
        except BootmgmtError as err:
            failures.append(err)
            print >> sys.stderr, (_('\nError: Unable to recreate client, '
                                    '%s:\n%s') % (client, err))
    if failures:
        return 1
    return 0


if __name__ == '__main__':
    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")
    do_rename_service()

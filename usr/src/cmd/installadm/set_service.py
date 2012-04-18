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
AI set-service
"""
import gettext
import logging
import os
import sys

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.create_client as create_client
import osol_install.auto_install.client_control as clientctrl
import osol_install.auto_install.service as svc
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from bootmgmt import BootmgmtError
from osol_install.auto_install.installadm_common import _, \
    validate_service_name, cli_wrap as cw


SERVICE_PROPS = [config.PROP_DEFAULT_MANIFEST, 'aliasof', 'imagepath']


def get_usage():
    """
    get usage for set-service
    """
    usage = _(
        'set-service\t-o|--option <prop>=<value> <svcname>\n'
        '\t\tprop=value can be:\n'
        '\t\t\taliasof=<existing_service>\n'
        '\t\t\tdefault-manifest=<manifest/script name>\n'
        '\t\t\timagepath=<newpath>')
    return(usage)


def parse_options(cmd_options=None):
    """
    Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    """

    usage = '\n' + get_usage()

    parser = OptionParser(usage=usage)
    parser.add_option("-o", "--option", dest="propval",
                      default=None, help=_("Set property of a service:"
                      "<-o|--option <property>=<value>"))

    options, args = parser.parse_args(cmd_options)

    # Check for correct number of args
    if len(args) != 1:
        if not len(args):
            err_msg = _("Missing required argument, <svcname>")
        else:
            err_msg = _("Unexpected argument(s): %s") % args[1:]
        parser.error(err_msg)

    # Check that we have a property/value
    if not options.propval:
        parser.error(_("Missing required option, -o|--option."))

    options.svcname = args[0]

    try:
        prop, value = get_prop_val(options.propval)
    except  ValueError as err:
        parser.error(err)

    options.prop = prop
    options.value = value

    return options


def get_prop_val(propval):
    '''
    get property and value

    Extract property and value from user input, propval
    Returns: tuple consisting of property, value
    Raises: ValueError on malformed name=value string in propval.
    '''
    parts = propval.partition('=')
    if parts[1]:
        if not parts[0]:
            raise ValueError(_("Missing property name in '%s'\n") % propval)
        elif parts[0].lower() not in SERVICE_PROPS:
            raise ValueError(_("Unknown property: '%s'\n") % parts[0])
        elif not parts[2]:
            raise ValueError(_("Missing value for property '%s'\n") % parts[0])
    else:
        raise ValueError(_("Option must be of the form <property>=<value>\n"))
    return parts[0], parts[2]


def do_set_service_default_manifest(options):
    '''
    Handle default_manifest property processing.
    '''
    service = svc.AIService(options.svcname)
    try:
        service.set_default_manifest(options.value)
    except ValueError as error:
        raise SystemExit(error)


def set_aliasof(options):
    '''Change a service's base service'''
    logging.debug("set alias %s's basesvc to %s",
                  options.svcname, options.value)
    basesvcname = options.value
    aliasname = options.svcname

    if not config.is_service(basesvcname):
        raise SystemExit(_('\nError: Service does not exist: %s\n') %
                         basesvcname)

    if aliasname == basesvcname:
        raise SystemExit(_('\nError: Alias name same as service name: %s\n') %
                         aliasname)

    aliassvc = svc.AIService(aliasname)
    if not aliassvc.is_alias():
        raise SystemExit(_('\nError: Service exists, but is not an '
                           'alias: %s\n') % aliasname)

    basesvc_arch = svc.AIService(basesvcname).arch
    aliassvc_arch = aliassvc.arch
    if basesvc_arch != aliassvc_arch:
        raise SystemExit(_("\nError: Architectures of service and alias "
                           "are different.\n"))

    if aliassvc.is_aliasof(basesvcname):
        raise SystemExit(_("\nError: %(aliasname)s is already an alias "
                           "of %(svcname)s\n") % {'aliasname': aliasname, \
                           'svcname': basesvcname})

    if svc.AIService(basesvcname).is_alias():
        raise SystemExit(_("\nError: Cannot alias to another alias.\n"))

    # Make sure we aren't creating inter dependencies
    all_aliases = config.get_aliased_services(aliasname, recurse=True)
    if basesvcname in all_aliases:
        raise SystemExit(cw(_("\nError: %(aliasname)s can not be made an "
                              "alias of %(svcname)s because %(svcname)s is "
                              "dependent on %(aliasname)s\n") %
                              {'aliasname': aliasname, \
                               'svcname': basesvcname}))

    # Remove clients of alias
    clients = config.get_clients(aliasname)
    for clientid in clients.keys():
        clientctrl.remove_client(clientid, suppress_dhcp_msgs=True)

    failures = list()
    try:
        aliassvc.update_basesvc(basesvcname)
    except (OSError, config.ServiceCfgError, BootmgmtError) as err:
        print >> sys.stderr, (_("Failed to set 'aliasof' property of : %s") %
                                aliasname)
        print >> sys.stderr, err
        failures.append(err)
    except svc.MultipleUnmountError as err:
        print >> sys.stderr, _("Failed to disable alias")
        print >> sys.stderr, err
        failures.append(err)
    except svc.MountError as err:
        print >> sys.stderr, _("Failed to enable alias")
        print >> sys.stderr, err
        failures.append(err)
    except svc.UnsupportedAliasError as err:
        print >> sys.stderr, err
        failures.append(err)

    # Re-add clients to updated alias
    arch = aliassvc_arch
    for clientid in clients.keys():
        # strip off leading '01'
        client = clientid[2:]
        bootargs = None
        if config.BOOTARGS in clients[clientid]:
            bootargs = clients[clientid][config.BOOTARGS]
        # Don't suppress messages, because user may need to update
        # DHCP configuration
        try:
            create_client.create_new_client(arch, aliassvc, client,
                bootargs=bootargs, suppress_dhcp_msgs=False)
        except BootmgmtError as err:
            failures.append(err)
            print >> sys.stderr, (_('\nError: Unable to recreate client, '
                                    '%s:\n%s') % (client, err))
    if failures:
        return 1
    return 0


def set_imagepath(options):
    '''Change the location of a service's image'''

    logging.debug("set %s imagepath to %s",
                  options.svcname, options.value)
    new_imagepath = options.value.strip()

    service = svc.AIService(options.svcname)
    if service.is_alias():
        raise SystemExit(cw(_('\nError: Can not change the imagepath of an '
                           'alias.')))

    if not os.path.isabs(new_imagepath):
        raise SystemExit(_("\nError: A full pathname is required for the "
                           "imagepath.\n"))

    if os.path.exists(new_imagepath):
        raise SystemExit(_("\nError: The imagepath already exists: %s\n") %
                         new_imagepath)

    if os.path.islink(new_imagepath):
        raise SystemExit(_("\nError: The imagepath may not be a symlink.\n"))

    new_imagepath = new_imagepath.rstrip('/')
    try:
        service.relocate_imagedir(new_imagepath)
    except (svc.MountError, aismf.ServicesError, BootmgmtError) as error:
        raise SystemExit(error)


def do_set_service(cmd_options=None):
    '''
    Set a property of a service
    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for this "
                           "command."))

    options = parse_options(cmd_options)

    # validate service name
    try:
        validate_service_name(options.svcname)
    except ValueError as err:
        raise SystemExit(str(err))

    logging.debug("options %s", options)

    if not config.is_service(options.svcname):
        raise SystemExit(_('\nError: Service does not exist: %s\n') %
                         options.svcname)

    if options.prop == "default-manifest":
        do_set_service_default_manifest(options)
    elif options.prop == "aliasof":
        return set_aliasof(options)
    elif options.prop == "imagepath":
        return set_imagepath(options)
    # Future set-service options can go here in an "else" clause...


if __name__ == '__main__':
    gettext.install("solaris_install_installadm", "/usr/share/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_set_service()

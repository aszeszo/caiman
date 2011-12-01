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
installadm - administration of AI services, manifests, and clients
'''
import logging
import os
import sys
import traceback

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.service_config as config

from optparse import OptionParser, SUPPRESS_HELP

from osol_install.auto_install import create_client
from osol_install.auto_install import create_profile
from osol_install.auto_install import create_service
from osol_install.auto_install import delete_client
from osol_install.auto_install import delete_manifest
from osol_install.auto_install import delete_profile
from osol_install.auto_install import delete_service
from osol_install.auto_install import export
from osol_install.auto_install import list as ai_list
from osol_install.auto_install import publish_manifest
from osol_install.auto_install import rename_service
from osol_install.auto_install import set_criteria
from osol_install.auto_install import set_service
from osol_install.auto_install import validate_profile
from osol_install.auto_install.installadm_common import _, \
    CHECK_SETUP_SCRIPT, validate_service_name, XDEBUG, setup_logging, \
    cli_wrap as cw
from osol_install.auto_install.image import ImageError
from osol_install.auto_install.service import AIService, MountError, \
    VersionError, InvalidServiceError
from solaris_install import Popen, CalledProcessError


DEFAULT_LOG_LEVEL = logging.WARN
DEBUG_LOG_LEVEL = logging.DEBUG


def get_enable_usage():
    ''' get usage for enable'''
    usage = _('enable\t<svcname>')
    return(usage)


def get_disable_usage():
    ''' get usage for disable'''
    usage = _('disable\t<svcname>')
    return(usage)


def get_help_usage():
    ''' get usage for help'''
    usage = _('help\t[<subcommand>]')
    return(usage)


def do_enable_service(cmd_options=None):
    ''' Enable a service

    Parse the supplied arguments then enable the specified service.

    Input:
        List of command line options
    Return:
        None
    Raises:
        SystemExit if missing permissions, invalid service name, or
        if attempt to enable the service or the smf service fails.

    '''
    logging.log(XDEBUG, '**** START do_enable_service ****')

    usage = '\n' + get_enable_usage()
    parser = OptionParser(usage=usage)

    args = parser.parse_args(cmd_options)[1]

    # Check for privileges
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    # Check for correct number of args
    if len(args) != 1:
        if len(args) == 0:
            parser.error(_("Missing required argument, <svcname>"))
        else:
            parser.error(_("Too many arguments: %s") % args)

    svcname = args[0]

    if not config.is_service(svcname):
        err_msg = _("The service does not exist: %s\n") % svcname
        parser.error(err_msg)

    # Verify that the server settings are not obviously broken.
    # These checks cannot be complete, but do check for things
    # which will definitely cause failure.
    ret = Popen([CHECK_SETUP_SCRIPT]).wait()
    if ret:
        return 1

    logging.log(XDEBUG, 'Enabling install service %s', svcname)
    try:
        service = AIService(svcname)
        service.enable()
    except (aismf.ServicesError, config.ServiceCfgError, ImageError,
            MountError) as err:
        raise SystemExit(err)
    except InvalidServiceError as err:
        raise SystemExit(cw(_("\nThis service may not be enabled until all "
                              "invalid manifests and profiles have been "
                              "corrected or removed.\n")))


def do_disable_service(cmd_options=None):
    ''' Disable a service

    Disable the specified service and optionally update the service's
    properties to reflect the new status.

    Input:
        List of command line options
    Return:
        None
    Raises:
        SystemExit if missing permissions, invalid service name, or
        if attempt to place smf service in maintenance fails.

    '''
    logging.debug('**** START do_disable_service ****')

    usage = '\n' + get_disable_usage()
    parser = OptionParser(usage=usage)

    (options, args) = parser.parse_args(cmd_options)

    # Check for privileges
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    # Check for correct number of args
    if len(args) != 1:
        if len(args) == 0:
            parser.error(_("Missing required argument, <svcname>"))
        else:
            parser.error(_("Too many arguments: %s") % args)

    svcname = args[0]

    # validate service name
    try:
        validate_service_name(svcname)
    except ValueError as err:
        raise SystemExit(err)

    if not config.is_service(svcname):
        err_msg = _("The service does not exist: %s\n") % svcname
        parser.error(err_msg)

    prop_data = config.get_service_props(svcname)

    if prop_data and config.PROP_STATUS not in prop_data:
        err_msg = _("The property, status, is missing for %s.\n") % svcname
        parser.error(err_msg)

    if prop_data[config.PROP_STATUS] == config.STATUS_OFF:
        err_msg = _("The service is not running: %s\n") % svcname
        parser.error(err_msg)

    try:
        logging.debug("Disabling install service %s", svcname)
        service = AIService(svcname)
        service.disable(force=True)
    except (config.ServiceCfgError, aismf.ServicesError, MountError) as err:
        raise SystemExit(err)
    except CalledProcessError:
        return 1


def main():
    ''' installadm main

    Parse the command line arguments and invoke sub-command.

    Returns:
        The return from the invoked sub-command.
        4 if VersionError encountered

    '''
    # sub_cmds is a dictionary. The value for each subcommand key
    # is a tuple consisting of the method to call to invoke the
    # subcommand and the method to call to get usage for the subcommand.
    sub_cmds = {
        'create-service':    (create_service.do_create_service,
                              create_service.get_usage()),
        'delete-service':    (delete_service.do_delete_service,
                              delete_service.get_usage()),
        'rename-service':    (rename_service.do_rename_service,
                              rename_service.get_usage()),
        'set-service':       (set_service.do_set_service,
                              set_service.get_usage()),
        'list':              (ai_list.do_list,
                              ai_list.get_usage()),
        'enable':            (do_enable_service,
                              get_enable_usage()),
        'disable':           (do_disable_service,
                              get_disable_usage()),
        'create-client':     (create_client.do_create_client,
                              create_client.get_usage()),
        'create-profile':    (create_profile.do_create_profile,
                              create_profile.get_create_usage()),
        'update-profile':    (create_profile.do_update_profile,
                              create_profile.get_update_usage()),
        'delete-client':     (delete_client.do_delete_client,
                              delete_client.get_usage()),
        'create-manifest':   (publish_manifest.do_publish_manifest,
                              publish_manifest.get_create_usage()),
        'add-manifest':      (publish_manifest.do_publish_manifest,  # alias
                              publish_manifest.get_create_usage()),
        'update-manifest':   (publish_manifest.do_update_manifest,
                              publish_manifest.get_update_usage()),
        'delete-manifest':   (delete_manifest.do_delete_manifest,
                              delete_manifest.get_usage()),
        'delete-profile':    (delete_profile.do_delete_profile,
                              delete_profile.get_usage()),
        'export':            (export.do_export,
                              export.get_usage()),
        'remove':            (delete_manifest.do_delete_manifest,  # alias
                              delete_manifest.get_usage()),
        'set-criteria':      (set_criteria.do_set_criteria,
                              set_criteria.get_usage()),
        'validate':          (validate_profile.do_validate_profile,
                              validate_profile.get_usage()),
        'help':              (None, get_help_usage())
        }

    # cmds is a list of subcommands used to dictate the order of
    # the commands listed in the usage output
    cmds = ["create-service",
            "delete-service",
            "rename-service",
            "set-service",
            "list",
            "enable",
            "disable",
            "create-client",
            "delete-client",
            "create-manifest",
            "update-manifest",
            "delete-manifest",
            "create-profile",
            "update-profile",
            "delete-profile",
            "export",
            "validate",
            "set-criteria",
            "help",
            ]

    usage_str = "Usage: installadm [options] <subcommand> <args> ..."
    for entry in cmds:
        usage_str += '\n' + sub_cmds[entry][1]
    parser = OptionParser(usage=usage_str)

    # add private debug option, which provides console output that might
    # be useful during development or bug fixing.
    parser.add_option("-d", "--debug", action="count", dest="debug",
                      default=0, help=SUPPRESS_HELP)

    # Find subcommand in sys.argv and save index to know which
    # options/args to pass to installadm and which options to
    # pass to subcommand
    sub_cmd = None
    index = 0
    for index, arg in enumerate(sys.argv):
        if arg in sub_cmds:
            sub_cmd = arg
            break

    # Exit if no subcommand was provided.
    if not sub_cmd:
        parser.print_help(file=sys.stderr)
        sys.exit(2)

    # Pass arguments up to subcommand to installadm parser
    # The rest of the arguments will be passed to the
    # subcommand later.
    #
    (options, args) = parser.parse_args(sys.argv[1:index])

    if args:
        parser.error(_("Unexpected argument(s): %s" % args))

    # Set up logging to the specified level of detail
    if options.debug == 0:
        options.log_level = DEFAULT_LOG_LEVEL
    elif options.debug == 1:
        options.log_level = DEBUG_LOG_LEVEL
    elif options.debug >= 2:
        options.log_level = XDEBUG
    try:
        setup_logging(options.log_level)
    except IOError, err:
        parser.error("%s '%s'" % (err.strerror, err.filename))

    logging.debug("installadm options: verbosity = %s", options.log_level)

    if sub_cmd == 'help':
        if len(sys.argv[index:]) == 1:
            # print full usage
            parser.print_help()
        else:
            # print help for single subcommand
            subcmd = sys.argv[index + 1]
            if subcmd in sub_cmds:
                print(sub_cmds.get(sys.argv[index + 1], None)[1])
            else:
                parser.print_help()
        sys.exit()

    else:
        # make sure we have the installadm smf service
        try:
            aismf.get_smf_instance()
        except aismf.ServicesError as err:
            raise SystemExit(err)

        # Invoke the function which implements the specified subcommand
        func = sub_cmds[sub_cmd][0]

        logging.debug("Invoking subcommand: %s %s",
                      func.func_name, sys.argv[index + 1:])
        try:
            return func(sys.argv[index + 1:])
        except VersionError as err:
            print >> sys.stderr, err
            return 4
        except Exception:
            sys.stderr.write(_("%s:\n"
                               "\tUnhandled error encountered:\n") % sub_cmd)
            traceback.print_exc(file=sys.stderr)
            sys.stderr.write(_("\tPlease report this as a bug at "
                               "http://defect.opensolaris.org\n"))
            return 1


if __name__ == '__main__':
    sys.exit(main())

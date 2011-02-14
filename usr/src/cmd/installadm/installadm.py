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
from optparse import OptionParser, SUPPRESS_HELP

from osol_install.auto_install import create_client
from osol_install.auto_install import delete_client
from osol_install.auto_install import delete_manifest 
from osol_install.auto_install import delete_service 
from osol_install.auto_install import list as ai_list 
from osol_install.auto_install import publish_manifest
from osol_install.auto_install import set_criteria
from osol_install.auto_install.ai_smf_service import \
    PROP_STATUS, InstalladmAISmfServicesError, check_for_enabled_services, \
    enable_install_service, get_pg_props, is_pg, set_pg_props
from osol_install.auto_install.installadm_common import _,  \
    CHECK_SETUP_SCRIPT, CREATE_SERVICE_BINARY, SERVICE_DISABLE, \
    SETUP_SERVICE_SCRIPT, STATUS_OFF, validate_service_name
from solaris_install import Popen


DEFAULT_LOG_LEVEL = "warn"
DEBUG_LOG_LEVEL = "debug"
LOG_FORMAT = ("%(filename)s:%(lineno)d %(message)s")


def get_cs_usage():
    ''' get usage for create-service'''
    usage = _(
        'create-service\t[-b <boot property>=<value>,...]\n'
        '\t\t[-f <bootfile>]\n'
        '\t\t[-n <svcname>]\n'
        '\t\t[-i <dhcp_ip_start>]\n'
        '\t\t[-c <count_of_ipaddr>]\n'
        '\t\t[-s <image ISO file>]\n'
        '\t\t<targetdir>')
    return(usage)

def get_enable_usage():
    ''' get usage for enable'''
    usage = _('enable\t<svcname>')
    return(usage)

def get_disable_usage():
    ''' get usage for disable'''
    usage = _('disable\t[-t|--temporary] <svcname>')
    return(usage)

def get_help_usage():
    ''' get usage for help'''
    usage = _('help\t[<subcommand>]')
    return(usage)

def setup_logging(log_level):
    '''Initialize the logger, logging to stderr at log_level,
       log_level defaults to warn

    Input:
        Desired log level for logging
    Return:
        None
    Raises:
        IOError if log level invalid

    '''
    log_level = log_level.upper()
    if hasattr(logging, log_level):
        log_level = getattr(logging, log_level.upper())
    else:
        raise IOError(2, 'Invalid log-level', log_level.lower())

    # set up logging to stderr
    logging.basicConfig(stream=sys.stderr, level=log_level, format=LOG_FORMAT)
    
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
    logging.debug('**** START do_enable_service ****')

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

    # validate service name
    try:
        validate_service_name(svcname)
    except ValueError as err:
        raise SystemExit(err)

    # Verify that the server settings are not obviously broken.
    # These checks cannot be complete, but do check for things
    # which will definitely cause failure.
    ret = Popen([CHECK_SETUP_SCRIPT]).wait()
    if ret:
        return 1

    logging.debug('Enabling install service %s', svcname)
    try:
        enable_install_service(svcname)
    except InstalladmAISmfServicesError as err:
        raise SystemExit(err)


def do_disable_service(cmd_options=None):
    ''' Disable a service

    Disable the specified service and optionally update the service's
    properties to reflect the new status.
    If the -t flag is specified, the service property group should not
    be updated to status=off. If -t is not specified, it should be.

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
    parser = OptionParser(usage = usage)
    parser.add_option('-t', '--temporary', dest = 'temporary', 
                      default = False, action='store_true',
                      help = _('Don\'t update service property group '
                               'status to off.'))

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
 
    # Get the service properties.
    if not is_pg(svcname):
        err_msg = _("The service does not exist: %s\n") % svcname
        parser.error(err_msg)

    pg_data = get_pg_props(svcname)

    if not PROP_STATUS in pg_data.keys():
        err_msg = _("The property, status, is missing for %s.\n") % svcname
        parser.error(err_msg)

    if pg_data[PROP_STATUS] == STATUS_OFF:
        err_msg = _("The service is not running: %s\n") % svcname
        parser.error(err_msg)

    # Stop the service
    cmd = [SETUP_SERVICE_SCRIPT, SERVICE_DISABLE, svcname]

    logging.debug("Disabling install service %s", svcname)
    ret = Popen(cmd).wait()
    if ret:
        return 1

    # If -t not specified then update the status in service's property group
    if not options.temporary:
        props = {PROP_STATUS: STATUS_OFF}
        set_pg_props(svcname, props)
        # If no longer needed, put install instance into
        # maintenance
        try:
            check_for_enabled_services()
        except InstalladmAISmfServicesError as err:
            raise SystemExit(err)

def do_create_service(cmdargs):
    '''
    Create a service

    Pass all command line options to create_service binary.
    '''
    logging.debug("**** START do_create_service ****")

    cmdargs.insert(0, CREATE_SERVICE_BINARY)
    logging.debug("Calling %s", cmdargs)
    return Popen(cmdargs).wait()


def main():
    ''' installadm main

    Parse the command line arguments and invoke sub-command.

    Returns:
        The return from the invoked sub-command.

    '''
    # sub_cmds is a dictionary. The value for each subcommand key 
    # is a tuple consisting of the method to call to invoke the 
    # subcommand and the method to call to get usage for the subcommand. 
    sub_cmds = {
        'create-service'   : (do_create_service, 
                              get_cs_usage()),
        'delete-service'   : (delete_service.do_delete_service, 
                              delete_service.get_usage()),
        'list'             : (ai_list.do_list, 
                              ai_list.get_usage()), 
        'enable'           : (do_enable_service, 
                              get_enable_usage()),
        'disable'          : (do_disable_service, 
                              get_disable_usage()),
        'create-client'    : (create_client.do_create_client, 
                              create_client.get_usage()),
        'delete-client'    : (delete_client.do_delete_client, 
                              delete_client.get_usage()),
        'add-manifest'     : (publish_manifest.do_publish_manifest, 
                              publish_manifest.get_usage()),
        'add'              : (publish_manifest.do_publish_manifest,  # alias
                              publish_manifest.get_usage()), 
        'delete-manifest'  : (delete_manifest.do_delete_manifest, 
                              delete_manifest.get_usage()),
        'remove'           : (delete_manifest.do_delete_manifest,  # alias
                              delete_manifest.get_usage()),  
        'set-criteria'     : (set_criteria.do_set_criteria, 
                              set_criteria.get_usage()),
        'help'             : (None, get_help_usage())      
        }

    # cmds is a list of subcommands used to dictate the order of
    # the commands listed in the usage output
    cmds = ["create-service", "delete-service", "list", "enable",
            "disable", "create-client", "delete-client", "add-manifest",
            "delete-manifest", "set-criteria", "help"]

    usage_str = "Usage: installadm [options] <subcommand> <args> ..."
    for entry in cmds:
        usage_str += '\n' + sub_cmds[entry][1]
    parser = OptionParser(usage=usage_str)

    # add private debug option, which provides console output that might
    # be useful during development or bug fixing.
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=False, help=SUPPRESS_HELP)

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
        parser.print_help()
        sys.exit(2)

    # Pass arguments up to subcommand to installadm parser
    # The rest of the arguments will be passed to the
    # subcommand later.
    #
    (options, args) = parser.parse_args(sys.argv[1:index])

    if args:
        parser.error(_("Unexpected argument(s): %s" % args))

    # Set up logging to the specified level of detail
    if options.debug:
        options.log_level = DEBUG_LOG_LEVEL
    else:
        options.log_level = DEFAULT_LOG_LEVEL
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
            subcmd = sys.argv[index+1] 
            if subcmd in sub_cmds:
                print(sub_cmds.get(sys.argv[index+1], None)[1])
            else:
                parser.print_help()
        sys.exit()

    else:
        # Invoke the function which implements the specified subcommand
        func = sub_cmds[sub_cmd][0]

        logging.debug("Invoking subcommand: %s %s",
                      func.func_name, sys.argv[index+1:])
        try:
            return func(sys.argv[index+1:])
        except Exception:
            sys.stderr.write(_("%s:\n"
                               "\tUnhandled error encountered:\n") % sub_cmd)
            traceback.print_exc(limit=2, file=sys.stderr)
            sys.stderr.write(_("\tPlease report this as a bug at "
                               "http://defect.opensolaris.org\n"))

if __name__ == '__main__':

    sys.exit(main())


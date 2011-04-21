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

"""
AI set-service
"""

import gettext
import logging
import os

from optparse import OptionParser

from osol_install.auto_install.properties import set_default, \
    get_service_info, DEFAULT_MANIFEST_PROP
from osol_install.auto_install.installadm_common import validate_service_name
from solaris_install import AI_DATA, _

SERVICE_PROPS = [DEFAULT_MANIFEST_PROP]


def get_usage():
    """
    get usage for set-service
    """
    usage = _(
        'set-service\t-o|--option <prop>=<value> ... <svcname>\n'
        '\t\tprop=value can be:\n'
#        '\t\t\tglobal-menu=true|false\n'
#        '\t\t\tname=<new_svcname>\n'
#        '\t\t\talias=<alias_name>\n'
        '\t\t\tdefault-manifest=<manifest/script name>')
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
            parser.error(_("Missing required argument, <svcname>"))
        else:
            parser.error(_("Unexpected argument(s): %s") % args[1:])

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
    try:
        service_dir, dummy, dummy = get_service_info(options.svcname)
    except StandardError, err:
        raise SystemExit(str(err))

    mfest_file = "/".join([service_dir, AI_DATA, options.value])
    if not os.path.exists(mfest_file):
        raise SystemExit(_("Manifest \"%s\" is not registered "
                           "with service") % options.value)
    try:
        set_default(options.svcname, options.value)
    except StandardError, err:
        raise SystemExit(str(err))


def do_set_service(cmd_options=None):
    '''
    Set a property of a service
    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    options = parse_options(cmd_options)

    # validate service name
    try:
        validate_service_name(options.svcname)
    except ValueError as err:
        raise SystemExit(str(err))

    logging.debug("options %s" % options)

    if options.prop == "default-manifest":
        do_set_service_default_manifest(options)

    # XXX Future services can go here in an "else" clause...


if __name__ == '__main__':
    import sys
    gettext.install("ai", "/usr/lib/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_set_service(sys.argv)

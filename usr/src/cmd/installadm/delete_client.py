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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
'''
AI delete-client
'''
import gettext
import logging
import os

import osol_install.auto_install.client_control as clientctrl
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _


def get_usage():
    ''' get usage for delete-client'''
    return(_('delete-client\t<macaddr>'))


def parse_options(cmd_options=None):
    ''' Parse and validate options '''

    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage)
    (options, args) = parser.parse_args(cmd_options)

    # check that we got the client's name passed in
    if not args:
        parser.error(_("Missing required argument, <macaddr>"))
    elif len(args) > 1:
        parser.error(_("Too many arguments: %s") % args)

    # Create a macAddress object and exit if MAC is not valid
    try:
        options.mac = com.MACAddress(args[0])
    except com.MACAddress.MACAddressError, err:
        raise SystemExit("Error:\t" + str(err))

    options.origmac = args[0]
    logging.debug("options = %s", options)

    return options


def do_delete_client(cmd_options=None):
    '''
    Parse the user supplied arguments and delete the specified
    client.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command.\n"))

    options = parse_options(cmd_options)
    clientid = '01' + str(options.mac)
    if not config.is_client(clientid):
        raise SystemExit(_("\nError: Client does not exist: %s\n" %
                           options.origmac))
    
    clientctrl.remove_client(clientid)


if __name__ == "__main__":

    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")

    do_delete_client()

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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
'''

A/I Delete Client Functions and Command

'''

import sys
import os
import gettext
import os.path
import traceback
from optparse import OptionParser

import delete_service
import osol_install.auto_install.installadm_common as com

def parse_options():
    '''
    Parse and validate options
    Args: None
    Returns: A tuple of a class object representing client to delete
             and an options object
    '''

    parser = OptionParser(usage=_("usage: %prog [options] MAC_address"))
    (options, args) = parser.parse_args()

    # check that we got the client's name passed in
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)

    # Create a macAddress object and exit if MAC is not valid
    try:
        mac = com.MACAddress(args[0])
    except com.MACAddress.MACAddressError, e:
        raise SystemExit("Error:\t" + str(e))

    client = delete_service.Client_Data(mac)
    # we do not deleteImage for a delete-client so set it False
    options.deleteImage = False

    return (client, options)

if __name__ == "__main__":
    # store application name for error string use
    prog = os.path.basename(sys.argv[0])

    # wrap whole command's execution to catch exceptions as we should not throw
    # them anywhere
    try:
        # initialize gettext
        gettext.install("ai", "/usr/lib/locale")

        # check that we are root
        if os.geteuid() != 0:
            raise SystemExit(_("Error:\tRoot privileges are required to "
                               "execute the %s %s command.\n") %
                             ("installadm", prog))

        (client, options) = parse_options()

        # remove files
        delete_service.remove_files(client, options.deleteImage)

        # clean-up any DHCP macros
        delete_service.remove_DHCP_macro(client)

    # catch SystemExit exceptions and pass them as raised
    except SystemExit, e:
        # append the program name, colon and newline to any errors raised
        raise SystemExit("%s:\n\t%s" % (prog, str(e)))
    # catch all other exceptions to print a disclaimer clean-up failed and may
    # be incomplete, they should run again to see if it will work
    except:
        sys.stderr.write(_("%s:\n"
                           "\tPlease report this as a bug at "
                           "http://defect.opensolaris.org:\n"
                           "\tUnhandled error encountered:\n") %
                        (prog))
        # write an abbreviated traceback for the user to report
        traceback.print_exc(limit=2, file=sys.stderr)

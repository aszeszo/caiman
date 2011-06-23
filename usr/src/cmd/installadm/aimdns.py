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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
Auto Installer mDNS and DNS Service Discovery class and application.
'''
import atexit
import gettext
import os
import signal
import sys

import pybonjour as pyb

import osol_install.auto_install.aimdns_mod as aimdns

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _


def parse_options():
    '''Parses and validate options

    Args
        None

    Globals
        None

    Returns
        a dictionary of the valid options

            {
                'verbose':Bool,
                'interface':interface_name (i.e., iwh0),
                'comment':string (comment for the server),
                'timeout':time (length of time to wait per request),
                'service':SName (service name to find),
                'browse':Bool (browse mode),
                'register':SName (service name to register),
                'port':port (port number for the service),
            }

    Raises
        None
    '''
    desc = _("Multicast DNS (mDNS) & DNS Service Directory Automated "
                "Installations utility. "
                "Or with -f option, Find a service. "
                "Or with -b option, Browse the services. "
                "Or with -r option, Register a service. "
                "Or with -i option, Browse, Find, Register on a "
                "specific interface. "
                "Or with -c option, Comment for a mDNS record(s) being "
                "registered. "
                "Or with -t option, set the timeout for the operation. "
                "Or with -p option, set the port number for the registration. "
                "Or with -v option, Verbose output.")

    usage = _("usage: %prog [[-v][-i <interface>][-t <timeout>]]\n"
                "\t[-f <servicename>] |\n"
                "\t[-b] |\n"
                "\t[-r <servicename> -p <port>] [[-c comment]] |\n")

    parser = OptionParser(usage=usage, description=desc)

    parser.add_option('-v', '--verbose', dest='verbose', default=False,
                      action='store_true',
                      help=_('turn on verbose mode'))

    parser.add_option('-i', '--interface', dest='interface', default=None,
                      type='string',
                      help=_('interface to browse, find or register on'))

    parser.add_option('-c', '--comment', dest='comment', default=None,
                      type='string',
                      help=_('comment used in service registration'))

    parser.add_option('-t', '--timeout', dest='timeout', default=None,
                      type='int',
                      help=_('set the timeout for the operation'))

    parser.add_option('-p', '--port', dest='port', default=None,
                      type='int',
                      help=_('set the port for the ad hoc registration'))

    parser.add_option("-f", "--find", dest="service", default=None,
                      type="string",
                      help=_("find a named service"))

    parser.add_option("-b", "--browse", dest="browse", default=False,
                      action="store_true",
                      help=_("browse the services"))

    parser.add_option("-r", "--register", dest="register", default=None,
                      type="string",
                      help=_("register a service, root privileges required"))

    (loptions, args) = parser.parse_args()

    if args:
        parser.error(_('unknown argument(s): %s') % args)

    if loptions.register is not None and os.geteuid() != 0:
        parser.error(_('root privileges required with the "-r" operation.'))

    if [bool(loptions.browse), bool(loptions.register),
        bool(loptions.service)].count(True) > 1:
        parser.error(_('"-f", "-b", and "-r" operations are mutually '
                       'exclusive.'))

    if not loptions.browse and not loptions.register and not loptions.service:
        parser.error(_('must specify an operation of "-f", "-b", or "-r".'))

    if loptions.register and not loptions.port:
        parser.error(_('must specify a "port" for the "-r" operation.'))

    if not loptions.register and loptions.port:
        parser.error(_('"-p" option only valid for the "-r" operation.'))

    if not loptions.register and loptions.comment:
        parser.error(_('"-c" option only valid for the "-r" operation.'))

    return loptions


def on_exit(signum=0, frame=None):
    '''Callback invoked when SIGTERM is received,
       or when the program is exiting

    Args
        signum - standard argument for callback
        frame  - standard argument for callback, not used

    Globals
        AIMDNS - instance of AImDNS class

    Returns
        None

    Raises
        None
    '''
    AIMDNS.clear_sdrefs()


def main(mdns):
    '''main program.

    Args
        aimdns - instance of AImDNS class

    Globals
        None

    Returns
        None

    Raises
        None
    '''
    atexit.register(on_exit)
    try:
        gettext.install("ai", "/usr/lib/locale")
        options = parse_options()
        comments = options.comment
        mdns.verbose = options.verbose

        if options.timeout:
            mdns.timeout = options.timeout

        # setup SIGTERM handling to ensure cleanup of PID file
        signal.signal(signal.SIGTERM, on_exit)

        if options.register:
            # register single service
            mdns.register(interfaces=options.interface, port=options.port,
                          servicename=options.register, comments=comments)
        elif options.browse:
            # browse services
            if mdns.browse():
                mdns.print_services()
            else:
                if options.verbose:
                    print _('No services found')
                else:
                    print _('-:None')
                    return 1
        elif options.service:
            # find a service
            if mdns.find(servicename=options.service):
                mdns.print_services()
            else:
                if options.verbose:
                    print _('Service "%s" not found') % options.service
                else:
                    print _("-:%s") % options.service
                    return 1
    except aimdns.AIMDNSError, err:
        print err
        return 1
    except pyb.BonjourError, err:
        print 'mDNS failure:error code', err.errorCode
        return 1

    return 0

if __name__ == '__main__':
    AIMDNS = aimdns.AImDNS()
    sys.exit(main(AIMDNS))

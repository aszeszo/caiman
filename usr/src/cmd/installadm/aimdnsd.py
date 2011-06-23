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
import linecache
import os
import signal
import sys

import pybonjour as pyb

import osol_install.auto_install.aimdns_mod as aimdns

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _
from solaris_install import Popen

# location of the process ID file
PIDFILE = '/var/run/aimdnsd'
REMOVE_PID = False


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
                'timeout':time (length of time to wait per request),
            }

    Raises
        None
    '''
    desc = _("Multicast DNS (mDNS) & DNS Service Directory Automated "
                "Installations utility. "
                "Or with -t option, set the timeout for the operation. "
                "Or with -v option, Verbose output.")

    usage = _("usage: %prog [[-v][-t <timeout>]]\n")

    parser = OptionParser(usage=usage, description=desc)

    parser.add_option('-v', '--verbose', dest='verbose', default=False,
                      action='store_true',
                      help=_('turn on verbose mode'))

    parser.add_option('-t', '--timeout', dest='timeout', default=None,
                      type='int',
                      help=_('set the timeout for the operation'))

    (loptions, args) = parser.parse_args()

    if args:
        parser.error(_('unknown argument(s): %s') % args)

    return loptions


def store_pid():
    '''Store the process ID for registering all services.

    Args
        None

    Globals
        PIDFILE    - location to store the register PID, the PID is used by
                     installadm delete-service/create-service, used
        REMOVE_PID - flag to indicate if the PID file should be removed,
                     modified

    Returns
        None

    Raises
        None
    '''
    global REMOVE_PID

    # ensure that the PIDFILE is removed
    REMOVE_PID = True

    if os.path.exists(PIDFILE):
        try:
            linecache.checkcache(PIDFILE)
            pid = int(linecache.getline(PIDFILE, 1).strip('\n'))
            # see if aimdns is still running via pgrep
            cmd = ["/usr/bin/pgrep", "aimdns"]
            pgrep_proc = Popen.check_call(cmd, stdout=Popen.STORE,
                                          stderr=Popen.STORE,
                                          check_result=Popen.ANY)
            if pgrep_proc.stderr:
                print pgrep_proc.stderr
            else:
                for pgrep_pid in pgrep_proc.stdout.split('\n')[:-1]:
                    runpid = int(pgrep_pid)
                    if runpid == pid:
                        sys.stderr.write(_('error:aimdns already running '
                                           '(pid %d)\n') % pid)
                        sys.exit(1)
        except ValueError:
            # var/run/aimdns file left over, truncate via open it.
            pass

    with open(PIDFILE, 'w+') as pidfile:
        mystr = str(os.getpid()) + '\n'
        pidfile.write(mystr)


def remove_pid():
    '''Removes the process ID file.

    Args
        None

    Globals
        PIDFILE    - location to store the register PID, the PID is used by
                     installadm delete-service/create-service, used
        REMOVE_PID - flag to indicate if the PID file should be removed, used

    Returns
        None

    Raises
        None
    '''
    if REMOVE_PID:
        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)


def on_exit(signum=0, frame=None):
    '''Callback invoked when SIGTERM is received,
       or when the program is exiting

    Args
        signum - standard argument for callback
        frame  - standard argument for callback, not used

    Globals
        None

    Returns
        None

    Raises
        None
    '''
    remove_pid()
    AIMDNS.clear_sdrefs()
    if signum == signal.SIGTERM:
        sys.exit(0)


def main(mdns):
    '''main program.

    Args
        None

    Globals
        REMOVE_PID - sets to true for registering all services operation

    Returns
        None

    Raises
        None
    '''
    atexit.register(on_exit)
    try:
        gettext.install("ai", "/usr/lib/locale")
        options = parse_options()
        mdns.verbose = options.verbose

        if options.timeout:
            mdns.timeout = options.timeout

        # setup SIGTERM handling to ensure cleanup of PID file
        signal.signal(signal.SIGTERM, on_exit)

        # save the PID information so that SIGHUP can be used by other apps
        store_pid()
        # register all the services
        mdns.register_all()
    except aimdns.AIMDNSError, err:
        print err
        return 1
    except pyb.BonjourError, err:
        print 'Registration failed for mDNS records (%d)' % err.errorCode
        return 1

    return 0

if __name__ == '__main__':
    AIMDNS = aimdns.AImDNS()
    sys.exit(main(AIMDNS))

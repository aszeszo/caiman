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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
'''

A/I Create-Client

'''

import sys
import gettext
import os
import socket
import traceback
import os.path
from optparse import OptionParser, OptionValueError

import osol_install.auto_install.installadm_common as com
import osol_install.libaiscf as smf

def parse_options():
    """
    Parse and validate options
    Args: None
    Returns: A tuple of an AIservice object representing service to use
             and an options object
    """

    def check_MAC_address(option, opt_str, value, parser):
        """
        Check MAC address as an OptionParser callback
        Postcondition: sets value to proper option if check passes
        Raises: OptionValueError if MAC address is malformed
        """
        try:
            value = str(com.MACAddress(value))
        except com.MACAddress.MACAddressError, e:
            raise OptionValueError(str(e))
        setattr(parser.values, option.dest, value)

    parser = OptionParser(usage=_("usage: %prog -e <macaddr> -n <svcname> "
                                  "[-b <property>=<value>,...]\n\t"
                                  "[-t <imagepath>]"))
    # accept multiple -b options (so append to a list)
    parser.add_option("-b", dest="boot_args", action="append", type="string",
                      nargs=1, help=_("boot arguments to pass Solaris kernel"))
    parser.add_option("-e", dest="mac_address", action="callback", nargs=1,
                      type="string", help=_("MAC address of client to add"),
                      callback=check_MAC_address)
    parser.add_option("-n", dest="service_name", action="store", type="string",
                      help=_("Service to associate client with"), nargs=1)
    parser.add_option("-t", dest="image_path", action="store", type="string",
                      help=_("Path to AI image directory for client"), nargs=1)
    (options, args) = parser.parse_args()

    # check that we did not get anything unexptected handed in
    if len(args) != 0 or not (options.mac_address and options.service_name):
        parser.print_help()
        sys.exit(1)

    # check the system has the AI install SMF service available
    try:
        smf_instance = smf.AISCF(FMRI="system/install/server")
    except KeyError:
        parser.error(_("The system does not have the "
                         "system/install/server SMF service.\n"))

    # check the service exists
    if options.service_name not in smf_instance.services.keys():
        parser.error(_("The specified service does not exist: %s\n") %
                         options.service_name)

    # store AIservice object in options.service
    options.service = smf.AIservice(smf_instance, options.service_name)

    # if image_path not specified, set it to the SMF service's image_path
    if not options.image_path:
        try:
            options.image_path = options.service['image_path']
        except KeyError:
            parser.error(_("The specified service does not have an image_path "
                           "property; please provide one.\n"))
        # set options.image to be an AIImage object
        image = com.AIImage(dir_path=options.image_path)

    # else, an image path was passed in, ensure it is the same architecture
    # as the service
    else:
        image = com.AIImage(dir_path=options.image_path)
        try:
            service_image = com.AIImage(dir_path=options.service['image_path'])
            # ensure the passed in image is the same architecture as the
            # service
            if image.arch is not service_image.arch:
                parser.error(_("The specified image is not the correct "
                               "architecture; please provide a %s image.\n") %
                             service_image.arch)
        except KeyError:
            parser.error(_("The specified service does not have an image_path "
                           "property; please provide one.\n"))
        # if the service's image is bad, do not complain since we
        # were passed in a different image
        except com.AIImage.AIImageError:
            # call image.arch and ensure it is okay, if so then continue
            if image.arch is not None:
                pass
    options.image = image

    # ensure we are not passed bootargs for a SPARC as we do not
    # support that
    if options.boot_args and options.image.arch == "SPARC":
        parser.error(_("Boot arguments not supported for SPARC clients.\n"))

    # return the AIservice object
    return (options)

def setup_tftp_links(service_name, image_path, mac_address, boot_args="null"):
    """
    Function to call into setup_tftp_links script
    Arguments:
              service_name - the AI service to add the client to
              image_path - directory path to AI image
              mac_address - client MAC address (to be interpreted by
                            MACAddress class)
              boot_args - list of boot arguments to pass via GRUB
    Returns: Nothing
    Raises: SystemExit if command fails
    """
    # create a DHCP client-identifier (01 + MAC ADDRESS)
    client_id = "01" + mac_address
    cmd = {"cmd": ["/usr/lib/installadm/setup-tftp-links", "client",
                   service_name, "unknown", image_path, client_id,
                   boot_args]}
    try:
        cmd = com.run_cmd(cmd)
    except SystemExit, e:
        raise SystemExit(_("Unable to setup x86 client: %s\n") % e)
    print cmd["out"]

def setup_sparc_client(image_path, mac_address):
    """
    Function to call setup-sparc_client script
    Arguments:
              image_path - directory path to AI image
              mac_address - client MAC address (to be interpreted by
                            MACAddress class)
    Returns: Nothing
    Raises: SystemExit if command fails
    """
    # create a DHCP client-identifier (01 + MAC ADDRESS)
    client_id = "01" + mac_address
    # get the host IP address (this only gets the IP of the host's
    # nodename not all interface IP addresses)
    server_ip = socket.gethostbyname(socket.gethostname())
    http_port = "5555"
    cgibin_wanboot_cgi = "/cgi-bin/wanboot-cgi"
    cmd = {"cmd": ["/usr/lib/installadm/setup-sparc", "client", client_id,
                   image_path]}
    try:
        cmd = com.run_cmd(cmd)
    except SystemExit, e:
        raise SystemExit(_("Unable to setup SPARC client: %s\n") % e)
    print cmd["out"]

def setup_dhcp(mac_address, arch):
    """
    Function to call setup-dhcp script
    Arguments:
              mac_address - client MAC address (to be interpreted by
                            MACAddress class)
              arch - architecture to setup for ("SPARC" or "X86")
    Returns: Nothing
    Raises: SystemExit if command fails
    """
    # create a DHCP client-identifier (01 + MAC ADDRESS)
    client_id = "01" + mac_address
    # get the host IP address (this only gets the IP of the host's nodename not
    # all interface IP addresses)
    server_ip = socket.gethostbyname(socket.gethostname())
    http_port = "5555"
    cgibin_wanboot_cgi = "/cgi-bin/wanboot-cgi"
    boot_file = "http://" + server_ip + ":" + http_port + cgibin_wanboot_cgi
    cmd = {"cmd": ["/usr/lib/installadm/setup-dhcp", "client", arch, server_ip,
                   client_id, boot_file]}
    try:
        cmd = com.run_cmd(cmd)
    except SystemExit:
        # Print nothing if setup-dhcp returns non-zero. setup-dhcp takes care
        # of providing instructions for the user in that case.
        print cmd["out"]
        # print script's std. err. output as the SystemExit exception message
        # if there was any (otherwise, just ignore this as setup-dhcp returns 1
        # for manual setup needed)
        if cmd["err"]:
            exe = SystemExit(cmd["err"])
            # pass the return code
            exe.code = cmd["subproc"].returncode
            # return the exception
            raise exe
        else:
            return

        print cmd["out"]

        print _("Enabled network boot by adding a macro named %s\n"
                "to DHCP server with:\n"
                "  Boot server IP     (BootSrvA) : %s\n"
                "  Boot file          (BootFile) : %s\n") % \
              (client_id, server_ip, boot_file)


if __name__ == "__main__":
    # store application name for error string use
    # argv is our application name
    prog = os.path.basename(sys.argv[0])

    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tRoot privileges are required to "
                           "execute the %s %s command.\n") %
                         ("installadm", prog))

    # parse server options
    options = parse_options()

    # wrap the whole program's execution to catch exceptions as we should not
    # throw them anywhere
    try:

        if options.image.arch == "X86":
            if options.boot_args:
                setup_tftp_links(options.service_name,
                                 options.image.path,
                                 options.mac_address,
                                 ",".join(options.boot_args) + ",")
            else:
                setup_tftp_links(options.service_name,
                                 options.image.path,
                                 options.mac_address)
        else:
            setup_sparc_client(options.image.path,
                               options.mac_address)

        setup_dhcp(options.mac_address, options.image.arch)

    # catch SystemExit exceptions and pass them as raised
    # also catch AIImage errors and pass them as SystemExits
    except (SystemExit, com.AIImage.AIImageError) as e:
        # raise the new exception with exit code
        raise SystemExit("%s:\n\t%s" % (prog, e))
    # catch all other exceptions
    except:
        # write an abbreviated traceback for the user to report
        sys.stderr.write(_("%s:\n"
                           "\tPlease report this as a bug at "
                           "http://defect.opensolaris.org:\n"
                           "\tUnhandled error encountered:\n") % prog)
        traceback.print_exc(limit=2, file=sys.stderr)

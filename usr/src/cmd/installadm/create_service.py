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

AI create-service

'''

import gettext
import logging
from optparse import OptionParser, OptionValueError
import os
import socket
import sys

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com
import osol_install.libaimdns as libaimdns
import osol_install.libaiscf as libaiscf

from solaris_install import CalledProcessError, Popen


_ = com._
BASE_DEF_SVC_NAME = "_install_service_"


def check_ip_address(option, opt_str, value, parser):
    '''Check IP address as an OptionParser callback
    Postcondition: sets value to proper option if check passes
    Raises: OptionValueError if IP address is malformed
    
    '''
    segments = value.split(".")
    if len(segments) != 4:
        raise OptionValueError(_("Malformed IP address: '%s'") % value)
    for segment in segments:
        try:
            segment = int(segment)
            if segment < 0 or segment > 255:
                raise OptionValueError(_("Malformed IP address: '%s'") % value)
        except ValueError, TypeError:
            raise OptionValueError(_("Malformed IP address: '%s'") % value)
    setattr(parser.values, option.dest, value)


def check_targetdir(srcimage, targetdir):
    '''
    Check if target dir exists.  If it exists, check whether it has 
    a valid net image. An empty dir is ok.

    Raises: ValueError if a problem exists with targetdir

    '''
    req_file = os.path.join(targetdir, com.AI_NETIMAGE_REQUIRED_FILE)
    
    if srcimage:
        # targetdir must not exist, or must be empty
        if os.path.exists(targetdir):
            try:
                dirlist = os.listdir(targetdir)
            except OSError as err:
                raise ValueError(err)
            
            if dirlist:
                if com.AI_NETIMAGE_REQUIRED_FILE in dirlist:
                    raise ValueError(_("There is a valid image at (%s). "
                                       "Please delete the image and try "
                                       "again.") % targetdir)
                else:
                    raise ValueError(_("Target directory is not empty."))
    else:
        if not os.path.exists(targetdir):
            raise ValueError(_("The specified target, %s, does not exist") %
                             targetdir)
        if not os.path.exists(req_file):
            raise ValueError(_("The specified target, %s, does not contain"
                               " a valid existing image.") % targetdir)


def get_usage():
    ''' get usage for create-service'''
    return(_(
        'create-service\t[-b|--boot-args <boot property>=<value>,...] \n'
        '\t\t[-f|--bootfile <bootfile>] \n'
        '\t\t[-n|--service <svcname>] \n'
        '\t\t[-c|--ip-count <count_of_ipaddr>] \n'
        '\t\t[-i|--ip-start <dhcp_ip_start>] \n'
        '\t\t[-s|--source <srcimage>] \n'
        '\t\t<targetdir>'))


def parse_options(cmd_options=None):
    '''
    Parse and validate options
    Args: sub-command, target directory
    
    Returns: An options record containing
        bootargs
        bootfile
        dhcp_ip_count
        dhcp_ip_start
        srcimage
        svcname
        targetdir
    
    '''
    logging.debug('**** START installadm.create_service.parse_options ****\n')
    
    usage = '\n' + get_usage()
    description = _('Establishes an Automated Install network service.')
    parser = OptionParser(usage=usage, prog="create-service",
                          description=description)
    parser.add_option('-b', '--boot-args', dest='bootargs', action='append',
                      default=[],
                      help=_('Comma separated list of <property>=<value>'
                             ' pairs to add to the x86 Grub menu entry'))
    parser.add_option('-f', '--bootfile', dest='bootfile', help=_('boot file'))
    parser.add_option('-n', '--service', dest='svcname',
                      help=_('service name'))
    parser.add_option('-i', '--ip-start', dest='dhcp_ip_start', type='string',
                      help=_('DHCP Starting IP Address'), action="callback",
                      callback=check_ip_address)
    parser.add_option('-c', '--ip-count', dest='dhcp_ip_count',
                      type='int', help=_('DHCP Count of IP Addresses'))
    parser.add_option('-s', '--source', dest='srcimage', type='string',
                      help=_('Image ISO file'))
    
    options, args = parser.parse_args(cmd_options)
    
    # check that we have a target dir
    if not args:
        parser.error(_("Missing required argument, <targetdir>"))
    elif len(args) > 1:
        parser.error(_('Too many arguments: %s') % args)
    
    options.targetdir = args[0]
    
    # if service name provided, validate it
    if options.svcname:
        try:
            com.validate_service_name(options.svcname)
        except ValueError as err:
            parser.error(err)

        # Give error is service already exists
        if aismf.is_pg(options.svcname):
            parser.error(_('Service already exists: %s') % options.svcname)

    # check dhcp related options
    # don't allow DHCP setup if multihomed
    if options.dhcp_ip_start or options.dhcp_ip_count:
        if com.is_multihomed():
            msg = _('DHCP server setup is not available on machines '
                    'with multiple network interfaces (-i and -c options '
                    'are disallowed).')
            parser.error(msg)
        
        # Confirm options -i and -c are both provided 
        if options.dhcp_ip_count is None:
            parser.error(_('If -i option is provided, -c option must '
                           'also be provided'))
        if not options.dhcp_ip_start:
            parser.error(_('If -c option is provided, -i option must '
                           'also be provided'))
        
        # Confirm count of ip addresses is positive
        if options.dhcp_ip_count < 1:
            parser.error('"-c <count_of_ipaddr>" must be greater than zero.')
    
    # Make sure targetdir meets requirements
    try:
        check_targetdir(options.srcimage, options.targetdir)
    except ValueError as error:
        raise SystemExit(error)
    
    return options


def setup_dhcp_server(ip_start, ip_count, dhcp_macro, dhcpbfile, arch):
    '''Set-up DHCP server for given AI service, IP addresses and clients'''
    
    # dhcp setup script calls ripped from C implementation of create-service
    
    logging.debug("setup_dhcp_server: ip_start=%s, ip_count=%s, "
                  "dhcp_macro=%s, dhcpbfile=%s, arch=%s" % 
                  (ip_start, ip_count, dhcp_macro, dhcpbfile, arch))
    if ip_count:
        logging.debug("Calling %s %s %s %s", com.SETUP_DHCP_SCRIPT,
                      com.DHCP_SERVER, ip_start, str(ip_count))
        # The setup-dhcp server call takes care of printing output for
        # the user so there is no need to check the result. If the call
        # returns an error code, an exception is thrown, which the caller
        # of this function should handle.
        Popen.check_call([com.SETUP_DHCP_SCRIPT, com.DHCP_SERVER, ip_start,
                         str(ip_count)])
    
    # The setup-dhcp macro call takes care of printing output for the
    # user so there is no need to check the result.
    logging.debug("Calling %s %s %s %s %s", com.SETUP_DHCP_SCRIPT,
                  com.DHCP_MACRO, arch, dhcp_macro, dhcpbfile)
    Popen([com.SETUP_DHCP_SCRIPT, com.DHCP_MACRO, arch, dhcp_macro,
           dhcpbfile]).wait()
    
    if ip_count:
        logging.debug("Calling %s %s %s %s %s", com.SETUP_DHCP_SCRIPT,
                      com.DHCP_ASSIGN, ip_start, str(ip_count), dhcp_macro)
        # The setup-dhcp assign call takes care of printing output for
        # the user. A failure is not considered fatal, so just print an
        # additional message for the user.
        try:
            Popen.check_call([com.SETUP_DHCP_SCRIPT, com.DHCP_ASSIGN, ip_start,
                             str(ip_count), dhcp_macro])
        except CalledProcessError:
            print >> sys.stderr, _("Failed to assign DHCP macro to IP "
                                   "address. Please assign manually.\n")


def get_default_service_name():
    ''' get default service name

        Returns: default name for service, _install_service_<num>

    '''
    count = 1
    svc_name = BASE_DEF_SVC_NAME + str(count)
    while aismf.is_pg(svc_name):
        count += 1
        svc_name = BASE_DEF_SVC_NAME + str(count)
    return svc_name


def get_a_free_tcp_port(service_instance, hostname):
    ''' get next free tcp port 

        Looks for next free tcp port number, starting from 46501

        Input: smf install server instance, hostname
        Returns: next free tcp port number if one found or 
                 None if no free port found
             
    '''
    # determine ports in use by other install services
    existing_ports = set()
    for name in service_instance.services:
        service = libaiscf.AIservice(service_instance, name)
        svckeys = service.keys()
        if aismf.PROP_TXT_RECORD in svckeys:
            port = service[aismf.PROP_TXT_RECORD].split(':')[-1]
            existing_ports.add(int(port))

    logging.debug("get_a_free_tcp_port, existing_ports=%s", existing_ports)

    starting_port = 46501
    ending_port = socket.SOL_SOCKET  # last socket is 65535
    mysock = None
    for port in xrange(starting_port, ending_port):
        try:
            # skip ports of existing install services
            if port in existing_ports:
                continue
            mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mysock.bind((hostname, port))
        except socket.error: 
            continue
        else: 
            logging.debug("found free tcp port: %s" % port)
            mysock.close()
            break
    else:
        logging.debug("no available tcp port found")
        return None
            
    return port


def _get_image_version(targetdir):
    ''' extract image version from version file rooted at target directory
        returns image version as float
    '''
    version = 0.0
    try:
        with open(os.path.join(targetdir, "auto_install/version")) as vfile:
            for line in vfile:
                key, did_split, version = line.partition("=")
                if did_split and key.strip() == "IMAGE_VERSION":
                    version = float(version)
    except (IOError, OSError, ValueError, TypeError):
        version = 0.0
    return version


def do_create_service(cmd_options=None):
    '''
    This method sets up the install service by:
        - checking the network configuration
        - creating the target image directory from an iso
        - creating the smf property group
        - enabling tftp service or configuring wanboot
        - configuring dhcp if desired
    
    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required"
                           " for this command."))

    logging.debug('**** START do_create_service ****')

    # make sure we have the installadm smf service
    try:
        inst = libaiscf.AISCF(FMRI="system/install/server")
    except KeyError:
        raise SystemExit(_("Error: The system does not have the "
                           "system/install/server SMF service"))

    options = parse_options(cmd_options)

    logging.debug('options: %s', options)
    
    # Verify that the server settings are not obviously broken
    # (i.e., check for things which will definitely cause failure).
    logging.debug('Check if the host server can support AI Install services.')
    cmd = [com.CHECK_SETUP_SCRIPT, 
           options.dhcp_ip_start if options.dhcp_ip_start else '']
    logging.debug('Calling %s', cmd)
    if Popen(cmd).wait():
        raise SystemExit(1)
    
    # Obtain the host server hostname and IP address
    options.server_hostname = socket.gethostname()
    logging.debug("options.server_hostname=%s", options.server_hostname)

    if com.is_multihomed():
        options.server_ip = "$serverIP"
    else:
        options.server_ip = socket.gethostbyname(options.server_hostname)
    
    logging.debug("options.server_ip=%s", options.server_ip)

    options.status = aismf.STATUS_ON
    
    # Setup the image
    # If the targetdir doesn't exist, the script creates it
    if options.srcimage:
        cmd = [com.SETUP_IMAGE_SCRIPT, com.IMAGE_CREATE, options.srcimage,
               options.targetdir]
        logging.debug('Calling %s', cmd)
        if Popen(cmd).wait():
            raise SystemExit(1)
    
    # Check for compatibility with old service setup
    image_vers = _get_image_version(options.targetdir)
    logging.debug('Image version %s' % image_vers)
    if image_vers < 1:
        compatibility_port = True
    else:
        compatibility_port = False

    logging.debug("compatibility port=%s", compatibility_port)

    # Check whether image is sparc or x86 by checking existence
    # of key directories
    try:
        image_arch = com.get_image_arch(options.targetdir)
    except ValueError as err:
        raise SystemExit(err)
    logging.debug("image_arch=%s", image_arch)
    
    # Determine port information
    http_port = libaimdns.getinteger_property(com.SRVINST, com.PORTPROP)

    if compatibility_port:
        port = get_a_free_tcp_port(inst, options.server_hostname)
        if not port:
            raise SystemExit(_("Cannot find a free port to start the "
                               "web server."))
    else:
        port = http_port

    # set text record to:
    #   (if multihomed)   "aiwebserver=$serverIP:<port>"
    #   (if single-homed) "aiwebserver=<server hostname>:<port>"
    options.txt_record = '%s=%s:%u' % (com.AIWEBSERVER,
                                       options.server_hostname,
                                       port)

    logging.debug("options.txt_record=%s", options.txt_record)

    # get default service name, if needed
    if not options.svcname:
        options.svcname = get_default_service_name()

    logging.debug("options.svcname=%s", options.svcname)

    # Save location of service in format <server_ip_address>:<port>
    # It will be used later for setting service discovery fallback
    # mechanism. For multihomed, options.server_ip is: "$serverIP"
    srv_address = '%s:%u' % (options.server_ip, port)

    logging.debug("srv_address=%s", srv_address)

    # if no bootfile provided, use the svcname
    if not options.bootfile:
        options.bootfile = options.svcname
    
    # Configure SMF
    service_data = {aismf.PROP_SERVICE_NAME: options.svcname,
                    aismf.PROP_IMAGE_PATH: options.targetdir,
                    aismf.PROP_BOOT_FILE: options.bootfile,
                    aismf.PROP_TXT_RECORD: options.txt_record,
                    aismf.PROP_STATUS: aismf.STATUS_ON}
    logging.debug("service_data=%s", service_data)
    aismf.create_pg(options.svcname, service_data)
    
    # Register & enable service
    # (Also enables system/install/server, as needed)
    try:
        aismf.enable_install_service(options.svcname)
    except aismf.InstalladmAISmfServicesError as err:
        raise SystemExit(err)

    if image_arch == 'sparc':
        # Always use $serverIP keyword as setup-dhcp will
        # substitute in the correct IP addresses. 
        dhcpbfile = 'http://%s:%u/%s' % ("$serverIP", http_port,
                                         com.WANBOOTCGI)
    else:
        dhcpbfile = options.bootfile
    
    # Configure DHCP
    if options.srcimage:
        dhcp_macro = 'dhcp_macro_' + options.bootfile
        logging.debug('Calling setup_dhcp_server %s %s %s %s %s', 
                       options.dhcp_ip_start, options.dhcp_ip_count,
                       dhcp_macro, dhcpbfile, image_arch)
        try:
            setup_dhcp_server(options.dhcp_ip_start, options.dhcp_ip_count,
                              dhcp_macro, dhcpbfile, image_arch)
        except CalledProcessError:
            raise SystemExit(1)
    
    # Setup wanboot for SPARC or TFTP for x86
    if image_arch == 'sparc':
        cmd = [com.SETUP_SPARC_SCRIPT, com.SPARC_SERVER, options.targetdir,
               options.svcname, srv_address]
        logging.debug('Calling %s', cmd)
        if Popen(cmd).wait():
            raise SystemExit(1)
    else:
        if not options.bootargs:
            options.bootargs.append("null")
        cmd = [com.SETUP_TFTP_LINKS_SCRIPT, com.TFTP_SERVER, options.svcname,
               options.targetdir, options.bootfile]
        cmd.extend(options.bootargs)
        logging.debug('Calling %s', cmd)
        if Popen(cmd).wait():
            raise SystemExit(1)


if __name__ == '__main__':
    # initialize gettext
    gettext.install('ai', '/usr/lib/locale')
    do_create_service()

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

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config
from osol_install.auto_install.service import AIService, AIServiceError, \
    DEFAULT_ARCH, MountError, UnsupportedAliasError
from osol_install.auto_install.image import is_iso, InstalladmIsoImage
from solaris_install import Popen, CalledProcessError


_ = com._
BASE_DEF_SVC_NAME = "install_service"


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
        except (ValueError, TypeError):
            raise OptionValueError(_("Malformed IP address: '%s'") % value)
    setattr(parser.values, option.dest, value)


def check_imagepath(imagepath):
    '''
    Check if image path exists.  If it exists, check whether it has 
    a valid net image. An empty dir is ok.

    Raises: ValueError if a problem exists with imagepath

    '''
    # imagepath must not exist, or must be empty
    if os.path.exists(imagepath):
        try:
            dirlist = os.listdir(imagepath)
        except OSError as err:
            raise ValueError(err)
        
        if dirlist:
            if com.AI_NETIMAGE_REQUIRED_FILE in dirlist:
                raise ValueError(_("There is a valid image at (%s). "
                                   "\nPlease delete the image and try "
                                   "again.") % imagepath)
            else:
                raise ValueError(_("Target directory is not empty."))


def get_usage():
    ''' get usage for create-service'''
    return(_(
        'create-service\n'
        '\t\t[-n|--service <svcname>] \n'
        '\t\t[-t|--aliasof <existing_service>] \n'
        '\t\t[-s|--source <ISO>] \n'
        '\t\t[-b|--boot-args <boot property>=<value>,...] \n'
        '\t\t[-i|--ip-start <dhcp_ip_start>] \n'
        '\t\t[-c|--ip-count <count_of_ipaddr>] \n'
        '\t\t[-B|--bootfile-server <server_ipaddr>] \n'
        '\t\t[-d|--imagepath <imagepath>]\n'
        '\t\t[-y|--noprompt]'))


def parse_options(cmd_options=None):
    '''
    Parse and validate options
    
    Returns: An options record containing
        aliasof
        bootargs
        dhcp_ip_count
        dhcp_ip_start
        dhcp_bootserver
        noprompt
        srcimage
        svcname
        imagepath 
    
    '''
    logging.log(com.XDEBUG, '**** START installadm.create_service.'
                'parse_options ****\n')
    
    usage = '\n' + get_usage()
    description = _('Establishes an Automated Install network service.')
    parser = OptionParser(usage=usage, prog="create-service",
                          description=description)
    parser.add_option('-b', '--boot-args', dest='bootargs', action='append',
                      default=list(),
                      help=_('Comma separated list of <property>=<value>'
                             ' pairs to add to the x86 Grub menu entry'))
    parser.add_option('-d', '--imagepath', dest='imagepath', default=None,
                      help=_("Path at which to create the net image"))
    parser.add_option('-t', '--aliasof', dest='aliasof', default=None,
                      help=_("Service being created is alias of this serivce"))
    parser.add_option('-n', '--service', dest='svcname',
                      help=_('service name'))
    parser.add_option('-i', '--ip-start', dest='dhcp_ip_start', type='string',
                      help=_('DHCP Starting IP Address'), action="callback",
                      callback=check_ip_address)
    parser.add_option('-c', '--ip-count', dest='dhcp_ip_count',
                      type='int', help=_('DHCP Count of IP Addresses'))
    parser.add_option('-B', '--bootfile-server', dest='dhcp_bootserver',
                      type='string', help=_('DHCP Boot Server Address'),
                      action="callback", callback=check_ip_address)
    parser.add_option('-s', '--source', dest='srcimage',
                      help=_('Auto Install ISO'))
    parser.add_option('-y', "--noprompt", action="store_true",
                      dest="noprompt", default=False,
                      help=_('Suppress confirmation prompts and proceed with '
                      'service creation using default values'))
    
    options, args = parser.parse_args(cmd_options)
    
    if args:
        parser.error(_('Unexpected argument(s): %s') % args)
    
    # if service name provided, validate it
    if options.svcname:
        try:
            com.validate_service_name(options.svcname)
        except ValueError as err:
            parser.error(err)
        
        # Give error if service already exists
        if config.is_service(options.svcname):
            parser.error(_('Service already exists: %s') % options.svcname)
    
    # If creating an alias, only allow additional options -n, -b, 
    # and -y
    if options.aliasof:
        if (options.dhcp_ip_start or options.dhcp_ip_count or 
            options.imagepath or options.srcimage):
            parser.error(_('\nOnly options -n|--service, -b|--boot-args, '
                           'and -y|--noprompt\nmay be specified with '
                           '-t|--aliasof.'))
        if not options.svcname:
            parser.error(_('\nOption -n|--service is required with the '
                            '-t|--aliasof option'))
    else:
        if not options.srcimage:
            parser.error(_("-s|--source or -t|--aliasof is required"))
        name = options.svcname
        if name in DEFAULT_ARCH:
            raise SystemExit(_('Default services must be created as aliases. '
                               ' Use -t|--aliasof.'))

    # check dhcp related options
    if options.dhcp_ip_start or options.dhcp_ip_count:
        if com.is_multihomed():
            # don't allow DHCP setup if multihomed
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

    if options.dhcp_bootserver:
        # Confirm if the -B is provided, that -i/-c are also
        if options.dhcp_ip_count is None:
            parser.error(_('If -B option is provided, -i option must '
                           'also be provided'))
    
    # Make sure imagepath meets requirements
    if options.imagepath:
        options.imagepath = options.imagepath.strip()
    if options.imagepath:
        if not options.imagepath == '/':
            options.imagepath = options.imagepath.rstrip('/')
        try:
            check_imagepath(options.imagepath)
        except ValueError as error:
            raise SystemExit(error)
    
    return options


def default_path_ok(svc_name, image_path=None):
    ''' check if default path for service image is available

    Returns: True if default path is ok to use (doesn't exist)
             False otherwise

    '''
    # if image_path specified by the user, we won't be
    # using the default path, so no need to check
    if image_path:
        return True

    def_imagepath = os.path.join(com.IMAGE_DIR_PATH, svc_name)
    if os.path.exists(def_imagepath):
        return False
    return True


def get_default_service_name(image_path=None):
    ''' get default service name
    
    Returns: default name for service, _install_service_<num>
    
    '''
    count = 1
    basename = BASE_DEF_SVC_NAME
    svc_name = basename + "_" + str(count)
    
    while (config.is_service(svc_name) or 
        not default_path_ok(svc_name, image_path)):
        count += 1
        svc_name = basename + "_" + str(count)
    return svc_name


def do_alias_service(options):
    ''' Create an alias of a service

    '''
    # Ensure that the base service is a service
    if not config.is_service(options.aliasof):
        raise SystemExit(_("Service does not exist: %s") % options.aliasof)

    basesvc = AIService(options.aliasof)

    # Ensure that the base service is not an alias
    if basesvc.is_alias():
        raise SystemExit(_("Error: Cannot create alias of another alias."))

    logging.debug("Creating alias of service %s", options.aliasof)

    image = basesvc.image

    print _("Creating alias %s") % options.svcname

    logging.debug("Creating AIService aliasname %s base svc=%s, bootargs=%s",
                  options.svcname, options.aliasof, options.bootargs)
    try:
        service = AIService.create(options.svcname, image,
                                   alias=options.aliasof,
                                   bootargs=options.bootargs)
    except AIServiceError as err:
        raise SystemExit(err)

    # if recreating default-sparc alias, recreate symlinks
    if service.is_default_arch_service() and image.arch == 'sparc':
        logging.debug("Recreating default-sparc symlinks")
        service.do_default_sparc_symlinks(options.svcname)

    # Register & enable service
    # (Also enables system/install/server, as needed)
    try:
        service.enable()
    except (aismf.ServicesError, config.ServiceCfgError, MountError) as err:
        raise SystemExit(err)


def should_be_default_for_arch(newservice):
    '''
    Determine if newservice should be the baseservice of default-<arch>
    (i.e., first service of architecture and aliasable)

    Input: service object for newly created service
    Returns: True if default-<arch> alias should be created
             False otherwise

    '''
    if newservice.image.version < 3:
        return False
    services = config.get_all_service_names()
    make_default = True
    for service in services:
        if service == newservice.name:
            continue
        svc = AIService(service)
        if svc.arch == newservice.arch and svc.image.version >= 3:
            make_default = False
            break

    logging.debug("should_be_default_for_arch service %s, arch=%s, returns %s",
                  newservice.name, newservice.arch, make_default)
    return make_default


def do_create_baseservice(options):
    '''
    This method sets up the install service by:
        - creating the target image directory from an iso
        - creating the smf property group
        - enabling tftp service or configuring wanboot
        - configuring dhcp if desired
    
    '''
    if is_iso(options.srcimage):
        # get default service name, if needed
        if not options.svcname:
            options.svcname = get_default_service_name(options.imagepath)

        # If imagepath not specified, verify that default image path is
        # ok with user
        if not options.imagepath:
            defaultdir = com.IMAGE_DIR_PATH
            if options.svcname:
                imagepath = os.path.join(defaultdir, options.svcname)
                prompt = (_("OK to use default image path: %s? [y/N]: " %
                          imagepath))
            else:
                prompt = (_("OK to use subdir of %s to store image? [y/N]: " %
                          defaultdir))
            try:
                if not options.noprompt:
                    if not com.ask_yes_or_no(prompt):
                        raise SystemExit(_('\nPlease re-enter command with '
                                           'desired --imagepath'))
            except KeyboardInterrupt:
                raise SystemExit(1)

            options.imagepath = os.path.join(com.IMAGE_DIR_PATH,
                                             options.svcname)
            try:
                check_imagepath(options.imagepath)
            except ValueError as error:
                raise SystemExit(error)
            logging.debug('Using default image path: %s', options.imagepath)

        print _("Creating service: %s") % options.svcname
        logging.debug("Creating ISO based service '%s'", options.svcname)
        try:
            image = InstalladmIsoImage.unpack(options.srcimage,
                                              options.imagepath)
        except CalledProcessError as err:
            raise SystemExit(err.popen.stderr)
    else:
        raise SystemExit(_("Source image is not a valid ISO file"))

    if options.dhcp_ip_start:
        service = AIService.create(options.svcname, image,
                                   options.dhcp_ip_start,
                                   options.dhcp_ip_count,
                                   options.dhcp_bootserver,
                                   bootargs=options.bootargs)
    else:
        service = AIService.create(options.svcname, image,
                                   bootargs=options.bootargs)
    
    # Register & enable service
    # (Also enables system/install/server, as needed)
    try:
        service.enable()
    except (aismf.ServicesError, config.ServiceCfgError, MountError) as err:
        raise SystemExit(err)
    
    # create default-<arch> alias if this is the first aliasable
    # service of this architecture
    if should_be_default_for_arch(service):
        defaultarch = 'default-' + image.arch
        print (_("Creating %s alias.") % defaultarch)
        try:
            defaultarchsvc = AIService.create(defaultarch, image,
                                              bootargs=options.bootargs,
                                              alias=options.svcname)
        except UnsupportedAliasError as err:
            # Print the error, but have installadm exit successfully.
            # Since the user did not explicitly request this alias,
            # it's not a problem if an alias can't be made for this service
            print err
            return 0

        # For sparc, create symlinks for default sparc service
        if image.arch == 'sparc':
            logging.debug("Creating default-sparc symlinks")
            defaultarchsvc.do_default_sparc_symlinks(defaultarch)

        # Register & enable default-<arch> service
        try:
            defaultarchsvc.enable()
        except (aismf.ServicesError, config.ServiceCfgError,
                MountError) as err:
            raise SystemExit(err)


def do_create_service(cmd_options=None):
    ''' Create either a base service or an alias '''

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required"
                           " for this command."))

    logging.log(com.XDEBUG, '**** START do_create_service ****')

    options = parse_options(cmd_options)

    logging.debug('options: %s', options)
    
    # Check the network configuration. Verify that the server settings
    # are not obviously broken (i.e., check for things which will definitely
    # cause failure).
    logging.debug('Check if the host server can support AI Install services.')
    cmd = [com.CHECK_SETUP_SCRIPT,
           options.dhcp_ip_start if options.dhcp_ip_start else '']
    logging.debug('Calling %s', cmd)
    if Popen(cmd).wait():
        raise SystemExit(1)
    
    # convert options.bootargs to a string
    if options.bootargs:
        options.bootargs = ",".join(options.bootargs) + ","
    else:
        options.bootargs = ''

    if options.aliasof:
        return(do_alias_service(options))
    else:
        return(do_create_baseservice(options))


if __name__ == '__main__':
    # initialize gettext
    gettext.install('ai', '/usr/lib/locale')
    do_create_service()

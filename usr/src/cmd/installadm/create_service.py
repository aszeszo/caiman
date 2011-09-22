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

import errno
import gettext
import logging
import os
import shutil
import stat
import sys
import tempfile

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config
import pkg.client.api_errors
import pkg.client.history

from optparse import OptionParser, OptionValueError
from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.auto_install.service import AIService, AIServiceError, \
    DEFAULT_ARCH, MountError, UnsupportedAliasError
from osol_install.auto_install.image import ImageError, InstalladmIsoImage, \
    InstalladmPkgImage, is_iso
from solaris_install import Popen, CalledProcessError


BASE_DEF_SVC_NAME = "solarisx"


def check_ip_address(option, opt_str, value, parser):
    '''Check IP address as an OptionParser callback
    Postcondition: sets value to proper option if check passes
    Raises: OptionValueError if IP address is malformed
    
    '''
    segments = value.split(".")
    if len(segments) != 4:
        raise OptionValueError(_("\nMalformed IP address: '%s'\n") % value)
    for segment in segments:
        try:
            segment = int(segment)
            if segment < 0 or segment > 255:
                raise OptionValueError(_("\nMalformed IP address: '%s'\n") %
                                         value)
        except (ValueError, TypeError):
            raise OptionValueError(_("\nMalformed IP address: '%s'\n") % value)
    setattr(parser.values, option.dest, value)


def check_imagepath(imagepath):
    '''
    Check if image path exists.  If it exists, check whether it has 
    a valid net image. An empty dir is ok.

    Raises: ValueError if a problem exists with imagepath

    '''
    # imagepath must be a full path
    if not os.path.isabs(imagepath):   
        raise ValueError(_("\nA full pathname is required for the "
                           "image path.\n"))

    # imagepath must not exist, or must be empty
    if os.path.exists(imagepath):
        try:
            dirlist = os.listdir(imagepath)
        except OSError as err:
            raise ValueError(err)
        
        if dirlist:
            if com.AI_NETIMAGE_REQUIRED_FILE in dirlist:
                raise ValueError(_("\nThere is a valid image at (%s)."
                                   "\nPlease delete the image and try "
                                   "again.\n") % imagepath)
            else:
                raise ValueError(_("\nTarget directory is not empty: %s\n") %
                                 imagepath)


def set_permissions(imagepath):
    ''' Set the permissions for the imagepath to 755 (rwxr-xr-x).
        Read, Execute other permissions are necessary for the
        webserver and tftpd to be able to read the imagepath.

        Raises SystemExit if the stat and fstat st_ino differ.
    '''
    image_stat = os.stat(imagepath)
    fd = os.open(imagepath, os.O_RDONLY)
    fd_stat = os.fstat(fd)
    if fd_stat.st_ino == image_stat.st_ino:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                      stat.S_IRGRP | stat.S_IXGRP | \
                      stat.S_IROTH | stat.S_IXOTH)
    else:
        raise SystemExit(_("The imagepath (%s) changed during "
                           "permission assignment") % imagepath)
    os.close(fd)


def get_usage():
    ''' get usage for create-service'''
    return(_(
        'create-service\n'
        '\t\t[-n|--service <svcname>] \n'
        '\t\t[-t|--aliasof <existing_service>] \n'
        '\t\t[-p|--publisher <prefix>=<origin>] \n'
        '\t\t[-a|--arch <architecture>] \n'
        '\t\t[-s|--source <FMRI/ISO>] \n'
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
        arch
        aliasof
        bootargs
        dhcp_ip_count
        dhcp_ip_start
        dhcp_bootserver
        noprompt
        publisher
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
    parser.add_option('-a', '--arch', dest='arch', default=None,
                      choices=("i386", "sparc"),
                      help=_("ARCHITECTURE (sparc or i386), desired "
                             "architecture of resulting service when creating "
                             "from a pkg."))
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
                      type='string',
                      help=_('FMRI or Auto Install ISO'))
    parser.add_option('-p', '--publisher', help=_("A pkg(5) publisher, in the"
                      " form '<prefix>=<uri>', from which to install the "
                      "client image"))
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
            parser.error(_('\nService already exists: %s\n') % options.svcname)
    
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
        name = options.svcname
        if name in DEFAULT_ARCH:
            raise SystemExit(_('\nDefault services must be created as '
                               'aliases. Use -t|--aliasof.\n'))

    # provide default for srcimage, now that we're done option checking
    if options.srcimage is None:
        options.srcimage = "pkg:/install-image/solaris-auto-install"

    # check dhcp related options
    if options.dhcp_ip_start or options.dhcp_ip_count:
        if com.is_multihomed():
            # don't allow DHCP setup if multihomed
            parser.error(cw(_('\nDHCP server configuration is unavailable on '
                              'hosts with multiple network interfaces (-i and '
                              '-c options are disallowed).\n')))
        
        # Confirm options -i and -c are both provided 
        if options.dhcp_ip_count is None:
            parser.error(_('\nIf -i option is provided, -c option must '
                           'also be provided\n'))
        if not options.dhcp_ip_start:
            parser.error(_('\nIf -c option is provided, -i option must '
                           'also be provided\n'))
        
        # Confirm count of ip addresses is positive
        if options.dhcp_ip_count < 1:
            parser.error(_('\n"-c <count_of_ipaddr>" must be greater than '
                           'zero.\n'))

    if options.dhcp_bootserver:
        # Confirm if the -B is provided, that -i/-c are also
        if options.dhcp_ip_count is None:
            parser.error(_('\nIf -B option is provided, -i option must '
                           'also be provided\n'))
    
    if is_iso(options.srcimage):
        if options.arch is not None:
            parser.error(_("The --arch option is invalid for ISO-based "
                           "services"))
        if options.publisher is not None:
            parser.error(_("The --publisher option is invalid for "
                           "ISO-based services"))

    if options.publisher:
        # Convert options.publisher from a string of form 'prefix=uri' to a
        # tuple (prefix, uri)
        publisher = options.publisher.split("=")
        if len(publisher) != 2:
            parser.error(_('Publisher information must match the form: '
                           '"<prefix>=<URI>"'))
        options.publisher = publisher
    
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


def default_path_ok(svc_name, specified_path=None):
    ''' check if default path for service image is available

    Returns: True if default path is ok to use (doesn't exist)
             False otherwise

    '''
    # if path specified by the user, we won't be
    # using the default path, so no need to check
    if specified_path:
        return True

    def_imagepath = os.path.join(com.IMAGE_DIR_PATH, svc_name)
    if os.path.exists(def_imagepath):
        return False
    return True


def get_default_service_name(image_path=None, image=None, iso=False):
    ''' get default service name
    
    Input:   specified_path - imagepath, if specified by user
             image - image object created from image
             iso - boolean, True if service is iso based, False otherwise
    Returns: default name for service. 
             For iso-based services, the default name is based
             on the SERVICE_NAME from the .image_info file if available,
             otherwise is BASE_DEF_SVC_NAME_<num>
             For pkg based services, the default name is obtained
             from pkg metadata, otherwise BASE_DEF_SVC_NAME_<num>

    '''
    if image:
        # Try to generate a name based on the metadata. If that 
        # name exists, append a number until a unique name is found.
        count = 0
        if iso:
            basename = image.read_image_info().get('service_name')
        else:
            basename = image.get_basename()
        try:
            com.validate_service_name(basename)
            svc_name = basename
        except ValueError:
            basename = BASE_DEF_SVC_NAME
            count = 1
            svc_name = basename + "_" + str(count)
    else:
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
        raise SystemExit(_("\nService does not exist: %s\n") % options.aliasof)

    basesvc = AIService(options.aliasof)

    # Ensure that the base service is not an alias
    if basesvc.is_alias():
        raise SystemExit(_("\nError: Cannot create alias of another alias.\n"))

    image = basesvc.image
    if options.svcname in DEFAULT_ARCH:
        if ((image.arch == 'sparc' and 'sparc' not in options.svcname) or
            (image.arch == 'i386' and 'i386' not in options.svcname)):
            raise SystemExit(cw(_("\nError: %s can not be an alias of a "
                                  "service with a different architecture.\n") % 
                                  options.svcname))
            
    logging.debug("Creating alias of service %s", options.aliasof)

    print _("\nCreating alias %s\n") % options.svcname

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
    except (config.ServiceCfgError, MountError) as err:
        raise SystemExit(err)
    except aismf.ServicesError as err:
        # don't error out if the service is successfully created
        # but the services fail to start - just print out the error
        # and proceed
        print err


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
        - creating the target image directory from an iso or pkg
        - creating the /var/ai service structure
        - enabling tftp service or configuring wanboot
        - configuring dhcp if desired
    
    '''
    tempdir = None
    print _("\nCreating service from: %s") % options.srcimage
    if is_iso(options.srcimage):
        have_iso = True
        # get default service name, if needed
        logging.debug("Creating ISO based service" )
    else:
        have_iso = False
        logging.debug("Creating pkg(5) based service")

    # If imagepath specified by user, use that.
    # If imagepath not specified  by user:
    #    a) if svcname specified by user, set up image in
    #       <default image path>/<svcname>
    #    b) if svcname not specified by user, set up image in
    #       <tmp location> and move to <default image path>/<svcname>
    #       once svcname is determined.

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
                                       'desired --imagepath\n'))
        except KeyboardInterrupt:
            raise SystemExit(1)

        # If we know the svcname, we know where to put the image.
        # Otherwise, put the image into a temp directory and move
        # it to correct location when we know it later
        if options.svcname:
            options.imagepath = os.path.join(com.IMAGE_DIR_PATH,
                                             options.svcname)
            try:
                check_imagepath(options.imagepath)
            except ValueError as error:
                raise SystemExit(error)
        else:
            try:
                os.makedirs(com.IMAGE_DIR_PATH)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise
            tempdir = tempfile.mkdtemp(dir=com.IMAGE_DIR_PATH)
            options.imagepath = tempdir
        logging.debug('Using default image path: %s', options.imagepath)

    # create the image area
    if have_iso:
        try:
            image = InstalladmIsoImage.unpack(options.srcimage,
                                              options.imagepath)
        except CalledProcessError as err:
            raise SystemExit(err.popen.stderr)
    else:
        try:
            image = InstalladmPkgImage.image_create(options.srcimage,
                                                    options.imagepath,
                                                    arch=options.arch,
                                                    publisher=options.publisher)
        except (ImageError,
                pkg.client.api_errors.ApiException) as err:
            if isinstance(err, pkg.client.api_errors.VersionException):
                print >> sys.stderr, cw(_("The IPS API version specified, "
                    + str(err.received_version) +
                    ", is incompatible with the expected version, "
                    + str(err.expected_version) + "."))
            elif isinstance(err, pkg.client.api_errors.CatalogRefreshException):
                for pub, error in err.failed:
                    print >> sys.stderr, "   "
                    print >> sys.stderr, str(error)
                if err.errmessage:
                    print >> sys.stderr, err.errmessage
            shutil.rmtree(options.imagepath, ignore_errors=True)
            raise SystemExit(err)

    # get default service name, if needed
    if not options.svcname:
        if tempdir and options.imagepath == tempdir:
            specified_path = None
        else:
            specified_path = options.imagepath
        options.svcname = get_default_service_name(specified_path,
                                                   image=image, iso=have_iso)

    print _("\nCreating service: %s\n") % options.svcname

    # If image was created in temporary location, move to correct
    # location now that we know the svcname.
    if tempdir is not None:
        new_imagepath = os.path.join(com.IMAGE_DIR_PATH, options.svcname)
        try:
            check_imagepath(new_imagepath)
        except ValueError as error:
            # leave image in temp location so that service can be created
            logging.debug('unable to move image to %s: %s',
                          new_imagepath, error)
        else:
            options.imagepath = image.move(new_imagepath)
            logging.debug('image moved to %s', options.imagepath)

    set_permissions(options.imagepath)
    print _("Image path: %s\n") % options.imagepath
    try:
        if options.dhcp_ip_start:
            service = AIService.create(options.svcname, image,
                                       options.dhcp_ip_start,
                                       options.dhcp_ip_count,
                                       options.dhcp_bootserver,
                                       bootargs=options.bootargs)
        else:
            service = AIService.create(options.svcname, image,
                                       bootargs=options.bootargs)
    except AIServiceError as err:
        raise SystemExit(err)
    
    # Register & enable service
    # (Also enables system/install/server, as needed)
    got_services_error = False
    try:
        service.enable()
    except (config.ServiceCfgError, MountError) as err:
        raise SystemExit(err)
    except aismf.ServicesError as svc_err:
        # Don't print the error now.  It will either get printed out
        # upon exit or when services are enabled after creating the 
        # alias
        got_services_error = True

    # create default-<arch> alias if this is the first aliasable
    # service of this architecture
    if should_be_default_for_arch(service):
        defaultarch = 'default-' + image.arch
        print (_("\nCreating %s alias.\n") % defaultarch)
        try:
            defaultarchsvc = AIService.create(defaultarch, image,
                                              bootargs=options.bootargs,
                                              alias=options.svcname)
        except AIServiceError as err:
            raise SystemExit(err)
        except UnsupportedAliasError as err:
            if got_services_error:
                # Print the services error string before printing the 
                # unsupported alias error
                print svc_err, '\n'

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
        except (config.ServiceCfgError, MountError) as err:
            raise SystemExit(err)
        except aismf.ServicesError as err:
            print err
    elif got_services_error:
        # Print the services start error generated when creating the service
        print svc_err


def do_create_service(cmd_options=None):
    ''' Create either a base service or an alias '''

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for this "
                           "command.\n"))

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

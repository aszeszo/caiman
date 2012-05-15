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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.

"""
AI update-service
"""

import gettext
import logging
import os
import sys
from optparse import OptionParser

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.image as img
import osol_install.auto_install.service as svc
import osol_install.auto_install.service_config as config
import osol_install.auto_install.set_service as setsvc
import pkg.client.api_errors

from osol_install.auto_install.image import InstalladmPkgImage
from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import check_auth_and_euid, SERVICE_AUTH, \
    UnauthorizedUserError


def get_usage():
    '''get usage for update-service'''
    return(_(
        'update-service\t[-p|--publisher <prefix>=<origin>]\n'
        '\t\t[-s|--source <FMRI>] <svcname>'))


def parse_options(cmd_options=None):
    '''Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: options object

    '''
    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage)
    parser.add_option('-s', '--source', dest='srcimage', help=_('FMRI'))
    parser.add_option('-p', '--publisher', help=_("A pkg(5) publisher, in "
                      "the form '<prefix>=<uri>', from which to update the "
                      "image. Specified publisher becomes the sole publisher "
                      "of the updated image."))

    # Get the parsed arguments using parse_args()
    options, args = parser.parse_args(cmd_options)

    # Confirm service name was passed in
    if not args:
        parser.error(_("Missing required argument, <svcname>"))
    elif len(args) > 1:
        parser.error(_("Too many arguments: %s") % args)

    options.service_name = args[0]

    # ensure service exists
    if not config.is_service(options.service_name):
        raise SystemExit(_("\nError: The specified service does "
                           "not exist: %s\n") % options.service_name)

    service = svc.AIService(options.service_name,
                            image_class=InstalladmPkgImage)
    if not service.is_alias():
        raise SystemExit(cw(_("Error: '%s' is not an alias. The target of "
                              "'update-service' must be an alias.") %
                              service.name))

    options.service = service

    if options.publisher is not None:
        # Convert options.publisher from a string of form 'prefix=uri' to a
        # tuple (prefix, uri) and strip each entry
        publisher = map(str.strip, options.publisher.split("="))
        if len(publisher) != 2:
            parser.error(_('Publisher information must match the form: '
                           '"<prefix>=<URI>"'))
        options.publisher = publisher

    logging.debug("options=%s", options)
    return options


def do_update_service(cmd_options=None):
    '''Update a service - currently only an alias

    Copy the baseservice of an alias, update it, create a service using
    the updated image, and re-alias the alias to the new service.

    '''
    # check for authorization and euid
    try:
        check_auth_and_euid(SERVICE_AUTH)
    except UnauthorizedUserError as err:
        raise SystemExit(err)

    options = parse_options(cmd_options)

    service = options.service
    try:
        if not service.image.is_pkg_based():
            raise SystemExit(cw(
                _("\nError: '%s' is aliased to an iso based service. Only "
                  "aliases of pkg(5) based services are updatable.") %
                  options.service_name))
    except pkg.client.api_errors.VersionException as err:
        print >> sys.stderr, cw(_("The IPS API version specified, %(specver)s,"
            " is incompatible with the expected version, %(expver)s.") %
            {'specver': str(err.received_version),
             'expver': str(err.expected_version)})
        raise SystemExit()

    fmri = [options.srcimage] if options.srcimage else None
    base_svc = svc.AIService(service.basesvc,
                             image_class=InstalladmPkgImage)

    new_image = None
    try:
        print _("Copying image ...")
        new_image = base_svc.image.copy(prefix=base_svc.name)
        print _('Updating image ...')
        update_needed = new_image.update(fmri=fmri,
                                         publisher=options.publisher)
    except (ValueError, img.ImageError,
            pkg.client.api_errors.ApiException) as err:
        # clean up copied image
        if new_image:
            new_image.delete()
        print >> sys.stderr, cw(_("Attempting to update the service %s"
            " failed for the following reasons:") % service.name)
        if isinstance(err, pkg.client.api_errors.CatalogRefreshException):
            for pub, error in err.failed:
                print >> sys.stderr, "   "
                print >> sys.stderr, str(error)
            if err.errmessage:
                print >> sys.stderr, err.errmessage
        raise SystemExit(err)

    if not update_needed:
        # No update needed, remove copied image
        new_image.delete()
        print _("No updates are available.")
        return 4

    # Get the service name from the updated image metadata
    new_svcname = img.get_default_service_name(image=new_image)

    # Determine imagepath and move image there
    new_path = new_image.path
    new_imagepath = os.path.join(os.path.dirname(new_path), new_svcname)
    try:
        img.check_imagepath(new_imagepath)
    except ValueError as error:
        # Leave image in temp location rather than fail. User can
        # update imagepath later if desired.
        logging.debug('unable to move image from %s to %s: %s',
                      new_path, new_imagepath, error)
    else:
        new_path = new_image.move(new_imagepath)
        logging.debug('image moved to %s', new_path)
    finally:
        img.set_permissions(new_path)

    # create new service based on updated image
    print _("Creating new %(arch)s service: %(newsvc)s") % \
            {'arch': new_image.arch, 'newsvc': new_svcname}
    new_service = svc.AIService.create(new_svcname, new_image)

    # Register & enable service
    # (Also enables system/install/server, as needed)
    try:
        service.enable()
    except (config.ServiceCfgError, svc.MountError) as err:
        raise SystemExit(err)
    except aismf.ServicesError as err:
        # don't error out if the service is successfully created
        # but the services fail to start - just print out the error
        # and proceed
        print err

    print _("Aliasing %(alename)s to %(newsvc)s ...\n") % \
            {'alename': service.name, 'newsvc': new_svcname}
    failures = setsvc.do_update_basesvc(service, new_service.name)
    if failures:
        return 1
    return 0


if __name__ == '__main__':
    # initialize gettext
    gettext.install("solaris_install_installadm", "/usr/share/locale")
    do_update_service()

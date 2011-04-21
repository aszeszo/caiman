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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
High-level property functions
"""

import os.path

from osol_install.auto_install.ai_smf_service import get_pg_props, \
    set_pg_props, PROP_IMAGE_PATH, PROP_TXT_RECORD
import osol_install.libaiscf as smf
from solaris_install import AI_SERVICE_DIR_PATH, AI_DATA, _

# SMF name of default-manifest property for a service.
DEFAULT_MANIFEST_PROP = 'default-manifest'

# More descriptive way of passing the third arg of set_default().
SKIP_MANIFEST_CHECK = True


def get_service_info(service_name):
    ''' return information about requested AI service
    Arg: service_name - name of AI service
    Returns: tuple: service directory, database name, image path
    Raises: SystemExit if failure to find service or find valid database file
    '''
    try:
        svc = smf.AIservice(smf.AISCF(FMRI="system/install/server"),
                            service_name)
    except KeyError:
        raise SystemExit(_("Error: Failed to find service %s") % service_name)

    # Get the install service's data directory and database path
    try:
        image_path = svc[PROP_IMAGE_PATH]
        port = svc[PROP_TXT_RECORD].rsplit(':')[-1]
    except KeyError, err:
        raise SystemExit(_("SMF data for service %s is corrupt. Missing "
                           "property: %s\n") % (service_name, err))

    service_dir = os.path.abspath(AI_SERVICE_DIR_PATH + service_name)
    # Ensure we are dealing with a new service setup
    if not os.path.exists(service_dir):
        # compatibility service setup
        service_dir = os.path.abspath(AI_SERVICE_DIR_PATH + port)

    # Check that the service directory and database exist
    database = os.path.join(service_dir, "AI.db")
    if not (os.path.isdir(service_dir) and os.path.exists(database)):
        raise SystemExit("Error: Invalid AI service directory: %s" %
                         service_dir)
    return service_dir, database, image_path


def set_default(service_name, manifest_name, skip_manifest_check=False):
    """
    Make manifest "manifest_name" the default for service "service_name"
    """
    # Get directory of where manifests live.
    service_dir, dummy, dummy = get_service_info(service_name)

    # Verify manifest with mname exists.
    if not skip_manifest_check:
        manifest_path = os.path.join(service_dir, AI_DATA, manifest_name)
        if not os.path.isfile(manifest_path):
            raise ValueError(_("Manifest %s does not exist." % manifest_path))

    # Set default-manifest property to mname.
    new_defprop = {DEFAULT_MANIFEST_PROP: manifest_name}
    set_pg_props(service_name, new_defprop)


def get_default(service_name):
    """
    Return the mname of the default for the service "service_name"
    """

    try:
        prop_dict = get_pg_props(service_name)
    except KeyError:
        raise ValueError(_("Failed to find service %s" % service_name))

    try:
        return prop_dict[DEFAULT_MANIFEST_PROP]
    except KeyError:
        raise KeyError(_("\"%(prop)s\" property is missing from "
                         "service %(serv)s") %
                         {"prop": DEFAULT_MANIFEST_PROP, "serv": service_name})

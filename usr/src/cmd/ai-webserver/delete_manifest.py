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
# Copyright (c) 2008, 2012, Oracle and/or its affiliates. All rights reserved.
"""
AI delete-manifest
"""
import gettext
import logging
import os
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _
from osol_install.auto_install.service import AIService


def get_usage():
    ''' get usage for delete-manifest'''
    return(_('delete-manifest\t-m|--manifest <manifest/script name> \n'
             '\t\t-n|--service <svcname>'))


def parse_options(cmd_options=None):
    """
    Parse and validate options
    """

    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage)

    parser.add_option("-m", "--manifest", dest="manifest_name",
                      default=None, help=_("Name of manifest"))
    parser.add_option("-n", "--service", dest="service_name",
                      default=None, help=_("Name of install service."))
    parser.add_option("-i", "--instance", dest="instance", default=None,
                      help=_("manifest instance to remove (internal option)"),
                      type="int", metavar="manifest instance")

    (options, args) = parser.parse_args(cmd_options)

    # check for required options
    if options.service_name is None:
        parser.error(_("Service name is required "
                       "(-n|--service <service name>)."))
    if options.manifest_name is None:
        parser.error(_("Manifest name is required "
                       "(-m|--manifest <manifest_name>)."))
    if args:
        parser.error(_("Unexpected argument(s): %s" % args))

    if not config.is_service(options.service_name):
        raise SystemExit(_("Not a valid service: %s") % options.service_name)

    options.svcdir_path = AIService(options.service_name).config_dir
    logging.debug("options = %s", options)
    return options


def delete_manifest_from_db(db, manifest_instance, service_name, data_loc):
    """
    Remove manifest from DB
    """
    instance = manifest_instance[1]
    # check to see that the manifest is found in the database (as entered)
    if manifest_instance[0] not in AIdb.getManNames(db.getQueue()):
        # since all manifest names have to have .xml appended try adding that
        if manifest_instance[0] + '.xml' in AIdb.getManNames(db.getQueue()):
            man_name = manifest_instance[0] + '.xml'
        else:
            raise SystemExit(_("Error:\tManifest %s not found in database!" %
                             manifest_instance[0]))
    else:
        man_name = manifest_instance[0]

    service = AIService(service_name)
    # Do not delete if this manifest is set up as the default.
    if man_name == service.get_default_manifest():
        raise ValueError(_("Error:\tCannot delete default manifest %s.") %
                         man_name)

    # if we do not have an instance remove the entire manifest
    if instance is None:
        # remove manifest from database
        query = AIdb.DBrequest("DELETE FROM manifests WHERE name = '%s'" %
                               AIdb.sanitizeSQL(man_name), commit=True)
        db.getQueue().put(query)
        query.waitAns()
        # run getResponse to handle and errors
        query.getResponse()

        # clean up file on file system
        try:
            os.remove(os.path.join(service.manifest_dir, man_name))
        except OSError:
            print >> sys.stderr, _("Warning:\tUnable to find file %s for " +
                                   "removal!") % man_name

    # we are removing a specific instance
    else:
        # check that the instance number is within bounds for that manifest
        # (0..numInstances)
        if instance > AIdb.numInstances(man_name, db.getQueue()) or \
            instance < 0:
            raise SystemExit(_("Error:\tManifest %s has %i instances" %
                             (man_name,
                              AIdb.numInstances(man_name, db.getQueue()))))

        # remove instance from database
        query = ("DELETE FROM manifests WHERE name = '%s' AND "
                "instance = '%i'") % (AIdb.sanitizeSQL(man_name), instance)
        query = AIdb.DBrequest(query, commit=True)
        db.getQueue().put(query)
        query.waitAns()
        # run getResponse to handle and errors
        query.getResponse()

        # We may need to reshuffle manifests to prevent gaps in instance
        # numbering as the DB routines expect instances to be contiguous and
        # increasing. We may have removed an instance with instances numbered
        # above thus leaving a gap.

        # get the number of instances with a larger instance
        for num in range(instance, AIdb.numInstances(man_name,
                                                     db.getQueue()) + 1):
            # now decrement the instance number
            query = ("UPDATE manifests SET instance = '%i' WHERE "
                    "name = '%s' ") % (num - 1, AIdb.sanitizeSQL(man_name))
            query += "AND instance = '%i'" % num
            query = AIdb.DBrequest(query, commit=True)
            db.getQueue().put(query)
            query.waitAns()
            # run getResponse to handle and errors
            query.getResponse()

        # remove file if manifest is no longer in database
        if man_name not in AIdb.getManNames(db.getQueue()):
            try:
                os.remove(os.path.join(service.manifest_dir, man_name))
            except OSError:
                print >> sys.stderr, _("Warning: Unable to find file %s for " +
                                       "removal!") % man_name


def do_delete_manifest(cmd_options=None):
    '''
    Delete a manifest from an install service.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    options = parse_options(cmd_options)

    if not os.path.exists(os.path.join(options.svcdir_path, "AI.db")):
        raise SystemExit(_("Error: Need a valid AI service directory"))

    aisql = AIdb.DB(os.path.join(options.svcdir_path, 'AI.db'), commit=True)
    aisql.verifyDBStructure()
    try:
        delete_manifest_from_db(aisql,
                                (options.manifest_name, options.instance),
                                options.service_name,
                                options.svcdir_path)
    except ValueError as error:
        raise SystemExit(error)

if __name__ == '__main__':
    gettext.install("solaris_install_aiwebserver", "/usr/share/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_delete_manifest()

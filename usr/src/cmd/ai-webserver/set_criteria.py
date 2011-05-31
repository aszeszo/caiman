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

"""
AI set-criteria
"""

import gettext
import logging
import lxml.etree
import os
import sys

from optparse import OptionParser

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc
import osol_install.auto_install.publish_manifest as pub_man

from osol_install.auto_install.installadm_common import validate_service_name
from osol_install.auto_install.properties import get_service_info
from solaris_install import AI_DATA, _


def get_usage():
    ''' get usage for set-criteria'''
    return(_(
        'set-criteria\t-m|--manifest <manifest/script name>\n'
        '\t\t-p|--profile <profile_name> ...\n'
        '\t\t-n|--service <svcname>\n'
        '\t\t-c|--criteria <criteria=value|range> ... |\n'
        '\t\t-C|--criteria-file <criteria.xml> |\n'
        '\t\t-a|--append-criteria <criteria=value|range> ... '))


def parse_options(cmd_options=None):
    """
    Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: command line options in dictionary
    Raises: The DataFiles initialization of manifest(s) A/I, SC, SMF looks for
            many error conditions and, when caught, are flagged to the user
            via raising SystemExit exceptions.
    """

    usage = '\n' + get_usage()

    parser = OptionParser(usage=usage)
    parser.add_option("-a", "--append-criteria", dest="criteria_a",
                      action="append", default=[],
                      help=_("Specify criteria to append: "
                      "<-a criteria=value|range> ..."),
                      metavar="CRITERIA")
    parser.add_option("-c", "--criteria", dest="criteria_c", action="append",
                      default=[], help=_("Specify criteria: "
                      "<-c criteria=value|range> ..."),
                      metavar="CRITERIA")
    parser.add_option("-C", "--criteria-file", dest="criteria_file",
                      default=None, help=_("Specify name of criteria "
                      "XML file."))
    parser.add_option("-m", "--manifest", dest="manifest_name",
                      default=None, help=_("Specify name of manifest "
                      "to set criteria for."))
    parser.add_option("-n", "--service", dest="service_name",
                      default=None, help=_("Specify name of install "
                      "service."))
    parser.add_option("-p", "--profile", dest="profile_name", action="append",
                      default=[], help=_("Specify name of profile "
                      "to set criteria for."))

    # Get the parsed options using parse_args().  We know we don't have
    # args, so check to make sure there are none.
    options, args = parser.parse_args(cmd_options)
    if len(args):
        parser.error(_("Unexpected argument(s): %s" % args))

    # Check that we have the install service's name and
    # an AI manifest name
    if options.service_name is None:
        parser.error(_("A service name is required."))
    # Either criteria for a manifest or profile is being set
    if not options.profile_name and options.manifest_name is None:
        parser.error(_("Must supply a manifest name and/or profile names."))
    # check for one of -a, -c, and -C
    if not (options.criteria_a or options.criteria_c or options.criteria_file):
        parser.error(_("Must specify either -a, -c or -C."))

    # validate service name
    try:
        validate_service_name(options.service_name)
    except ValueError as err:
        parser.error(err)

    logging.debug("options = %s", options)

    # check that we aren't mixing -a, -c, and -C
    if (options.criteria_a and options.criteria_c) or \
        (options.criteria_a and options.criteria_file) or \
        (options.criteria_c and options.criteria_file):
        parser.error(_("Options used are mutually exclusive."))

    return options


def check_published_manifest(service_dir, dbn, manifest_name):
    """
    Used for checking that a manifest is already published in the
    install service specified.  Checks to make sure manifest
    exists in the install service's DB, and that the manifest also
    exists in the install service's published files area.
    Args:
          service_dir - config directory of install service to check.
          dbn - dbn object of install service to check against.
          manifest_name - name of manifest to check.
    Postconditions: None
    Returns: True if manifest exists in install service
             False if manifest does not exist.
    """

    # Check if manifest exists in the service's criteria DB.
    if AIdb.sanitizeSQL(manifest_name) not in AIdb.getManNames(dbn.getQueue()):
        print(_("Error: install service does not contain the specified "
                "manifest: %s") % manifest_name)
        return False

    # Check if manifest file exists in the service's published area.
    published_path = os.path.join(service_dir, AI_DATA, manifest_name)

    if not os.path.exists(published_path):
        print(_("Error: manifest missing from published area: %s") %
                published_path)
        return False

    return True


def set_criteria(criteria, iname, dbn, table, append=False):
    """
    Set a manifest's record in the criteria database with the
    criteria provided.
    If append is True -- append ones that aren't already set for
    the manifest, and replace ones that are.
    if append is False -- completely remove all criteria already
    set for the manifest, and use only the criteria specified.
    """

    # Build a list of criteria nvpairs to update
    nvpairs = list()

    # we need to fill in the criteria or NULLs for each criteria the database
    # supports (so iterate over each criteria)
    for crit in AIdb.getCriteria(dbn.getQueue(), table=table, onlyUsed=False,
            strip=True):

        # Determine if this crit is a range criteria or not.
        is_range_crit = AIdb.isRangeCriteria(dbn.getQueue(), crit)

        # Get the value from the manifest
        values = criteria[crit]

        # the criteria manifest didn't specify this criteria
        if values is None:
            # If we not appending criteria, then we must write in NULLs
            # for this criteria since we're removing all criteria not
            # specified.
            if not append:
                # if the criteria we're processing is a range criteria, fill in
                # NULL for two columns, MINcrit and MAXcrit
                if is_range_crit:
                    nvpairs.append("MIN" + crit + "=NULL")
                    nvpairs.append("MAX" + crit + "=NULL")
                # this is a single value
                else:
                    nvpairs.append(crit + "=NULL")

        # Else if this is a value criteria (not a range), insert the
        # value as a space-separated list of values in case a list of
        # values have been given. 
        elif not is_range_crit:
            nvstr = crit + "='" + AIdb.sanitizeSQL(" ".join(values)) + "'"
            nvpairs.append(nvstr)

        # Else the values are a list this is a range criteria
        else:
            # Set the MIN column for this range criteria
            nvpairs.append("MIN" + crit + "=" +
                    AIdb.format_value(crit, values[0]))

            # Set the MAX column for this range criteria
            nvpairs.append("MAX" + crit + "=" +
                    AIdb.format_value(crit, values[1]))

    query = "UPDATE " + table + " SET " + ",".join(nvpairs) + \
            " WHERE name='" + iname + "'"

    # update the DB
    query = AIdb.DBrequest(query, commit=True)
    dbn.getQueue().put(query)
    query.waitAns()
    # in case there's an error call the response function (which
    # will print the error)
    query.getResponse()


def do_set_criteria(cmd_options=None):
    '''
    Modify the criteria associated with a manifest.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    options = parse_options(cmd_options)

    # get AI service directory, database name
    service_dir, database, dummy = get_service_info(options.service_name)

    # Check that the service directory and database exist
    if not (os.path.isdir(service_dir) and os.path.exists(database)):
        raise SystemExit("Error: Invalid AI service directory: %s" %
                         service_dir)

    # Open the database
    dbn = AIdb.DB(database, commit=True)

    # Check to make sure that the manifest whose criteria we're
    # updating exists in the install service.
    if options.manifest_name and not check_published_manifest(
            service_dir, dbn, options.manifest_name):
        raise SystemExit(1)

    # Process and validate criteria from -a, -c, or -C, and store
    # store the criteria in a Criteria object.
    try:
        if options.criteria_file:
            root = pub_man.verifyCriteria(pub_man.DataFiles.criteriaSchema,
                    options.criteria_file, dbn, AIdb.MANIFESTS_TABLE)
        elif options.criteria_a:
            criteria_dict = pub_man.criteria_to_dict(options.criteria_a)
            root = pub_man.verifyCriteriaDict(pub_man.DataFiles.criteriaSchema,
                    criteria_dict, dbn, AIdb.MANIFESTS_TABLE)
        elif options.criteria_c:
            criteria_dict = pub_man.criteria_to_dict(options.criteria_c)
            root = pub_man.verifyCriteriaDict(pub_man.DataFiles.criteriaSchema,
                    criteria_dict, dbn, AIdb.MANIFESTS_TABLE)
        else:
            raise SystemExit("Error: Missing required criteria.")

    except (AssertionError, IOError, ValueError) as err:
        raise SystemExit(err)
    except (lxml.etree.LxmlError) as err:
        raise SystemExit(_("Error:\tmanifest error: %s") % err)

    # Instantiate a Criteria object with the XML DOM of the criteria.
    criteria = pub_man.Criteria(root)

    if options.manifest_name:
        # Ensure the criteria we're adding/setting for this manifest doesn't
        # cause a criteria collision in the DB.
        colliding_criteria = pub_man.find_colliding_criteria(criteria, dbn,
                             exclude_manifests=[options.manifest_name])
        # If we're appending criteria pass the manifest name
        if options.criteria_a:
            pub_man.find_colliding_manifests(criteria, dbn, colliding_criteria,
                    append_manifest=options.manifest_name)
        else:
            pub_man.find_colliding_manifests(criteria, dbn, colliding_criteria,
                                             append_manifest=None)
    # validate criteria for profile
    for pname in options.profile_name:
        if not sc.is_name_in_table(pname, dbn.getQueue(), AIdb.PROFILES_TABLE):
            raise SystemExit(_("Error:\tservice has no profile named %s." %
                pname))
        # Validate profile criteria
        sc.validate_criteria_from_user(criteria, dbn, AIdb.PROFILES_TABLE)

    # all validation complete - update database

    # indicate whether criteria are added or replaced
    if options.criteria_a:
        append = True  # add new criteria
    else:
        append = False  # replace any existing criteria with new
    if options.manifest_name:
        # Update the criteria for manifest
        set_criteria(criteria, options.manifest_name, dbn,
                AIdb.MANIFESTS_TABLE, append)
        print >> sys.stderr, _("Criteria updated for manifest %s.") % \
                options.manifest_name
    for pname in options.profile_name:
        # Update the criteria for profile
        set_criteria(criteria, pname, dbn, AIdb.PROFILES_TABLE, append)
        print >> sys.stderr, _("Criteria updated for profile %s.") % pname

if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_set_criteria()

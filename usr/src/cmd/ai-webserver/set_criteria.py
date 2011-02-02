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
import lxml.etree
from optparse import OptionParser
import os.path

import publish_manifest as pub_man
import osol_install.auto_install.AI_database as AIdb
import osol_install.libaiscf as smf


def parse_options(cmd_options=None):
    """
    Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: the DataFiles object populated and initialized
    Raises: The DataFiles initialization of manifest(s) A/I, SC, SMF looks for
            many error conditions and, when caught, are flagged to the user
            via raising SystemExit exceptions.
    """

    usage = _("usage: %prog -n service_name -m AI_manifest_name"
              " [-c|-a <criteria=value|range> ...] | -C criteria_file")

    parser = OptionParser(usage=usage, prog="set-criteria")
    parser.add_option("-a", dest="criteria_a", action="append",
                      default=[], help=_("Specify criteria to append: "
                      "<-a criteria=value|range> ..."))
    parser.add_option("-c", dest="criteria_c", action="append",
                      default=[], help=_("Specify criteria: "
                      "<-c criteria=value|range> ..."))
    parser.add_option("-C",  dest="criteria_file",
                      default=None, help=_("Specify name of criteria "
                      "XML file."))
    parser.add_option("-m",  dest="manifest_name",
                      default=None, help=_("Specify name of manifest "
                      "to set criteria for."))
    parser.add_option("-n",  dest="service_name",
                      default=None, help=_("Specify name of install "
                      "service."))

    # Get the parsed options using parse_args().  We know we don't have
    # args, so check to make sure there are none.
    options, args = parser.parse_args(cmd_options)
    if len(args):
        parser.error(_("Unexpected arguments: %s" % args))

    # Check that we have the install service's name and
    # an AI manifest name
    if options.service_name is None or options.manifest_name is None:
        parser.error(_("Missing one or more required options."))

    # check that we aren't mixing -a, -c, and -C
    if (options.criteria_a and options.criteria_c) or \
        (options.criteria_a and options.criteria_file) or \
        (options.criteria_c and options.criteria_file):
        parser.error(_("Options used are mutually exclusive."))

    return options


def check_published_manifest(service_dir, db, manifest_name):
    """
    Used for checking that a manifest is already published in the
    install service specified.  Checks to make sure manifest
    exists in the install service's DB, and that the manifest also
    exists in the install service's published files area.
    Args:
          service_dir - config directory of install service to check.
          db - db object of install service to check against.
          manifest_name - name of manifest to check.
    Postconditions: None
    Returns: True if manifest exists in install service
             False if manifest does not exist.
    """

    # Check if manifest exists in the service's criteria DB.
    if AIdb.sanitizeSQL(manifest_name) not in AIdb.getManNames(db.getQueue()):
        print(_("Error: install service does not contain the specified "
                "manifest: %s") % manifest_name)
        return False

    # Check if manifest file exists in the service's published area.
    published_path = os.path.join(service_dir, "AI_data", manifest_name)

    if not os.path.exists(published_path):
        print(_("Error: manifest missing from published area: %s") %
                published_path)
        return False

    return True


def format_value(crit, value):
    """
    Format's a value (for use with set_criteria()) based on its
    criteria type.
    Args: crit - the criteria name.
          value - the value to format.
    Returns:
          Formatted value for (used by set_criteria()) to use in
          a string to query the install service's DB.
    """
    # For the value "unbounded", we store this as "NULL" in the DB.
    if value == "unbounded":
        return "NULL"
    else:
        formatted_val = "'" + AIdb.sanitizeSQL(str(value).upper()) + "'"

        # If its the "mac" criteria, must add a special hex operand
        if crit == "mac":
            return "x" + formatted_val

        return formatted_val


def set_criteria(criteria, manifest_name, db, append=False):
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
    for crit in AIdb.getCriteria(db.getQueue(), onlyUsed=False, strip=True):

        # Get the value from the manifest
        values = criteria[crit]

        # the critera manifest didn't specify this criteria
        if values is None:
            # If we not appending criteria, then we must write in NULLs
            # for this criteria since we're removing all criteria not
            # specified.
            if not append:
                # if the criteria we're processing is a range criteria, fill in
                # NULL for two columns, MINcrit and MAXcrit
                if AIdb.isRangeCriteria(db.getQueue(), crit):
                    nvpairs.append("MIN" + crit + "=NULL")
                    nvpairs.append("MAX" + crit + "=NULL")
                # this is a single value
                else:
                    nvpairs.append(crit + "=NULL")

        # this is a single criteria (not a range)
        elif isinstance(values, basestring):
            # translate "unbounded" to a database NULL
            if values == "unbounded":
                nvstr = crit + "=NULL"
            else:
                # use lower case for text strings
                nvstr = crit + "='" + AIdb.sanitizeSQL(str(values).lower()) \
                        + "'"
            nvpairs.append(nvstr)

        # Else the values are a list this is a range criteria
        else:
            # Set the MIN column for this range criteria
            nvpairs.append("MIN" + crit + "=" + format_value(crit, values[0]))

            # Set the MAX column for this range criteria
            nvpairs.append("MAX" + crit + "=" + format_value(crit, values[1]))

    query = "UPDATE manifests SET " + ",".join(nvpairs) + \
            " WHERE name='" + manifest_name + "'"

    # update the DB
    query = AIdb.DBrequest(query, commit=True)
    db.getQueue().put(query)
    query.waitAns()
    # in case there's an error call the response function (which
    # will print the error)
    query.getResponse()


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")

    options = parse_options()

    # Get the SMF service object for the install service specified.
    try:
        svc = smf.AIservice(smf.AISCF(FMRI="system/install/server"),
                            options.service_name)
    except KeyError:
        raise SystemExit(_("Error: Failed to find service %s") %
                         options.service_name)

    # Get the install service's data directory and database path
    service_dir = os.path.abspath("/var/ai/" + options.service_name)
    # Ensure we are dealing with a new service setup
    if not os.path.exists(service_dir):
        # compatibility service setup
        try:
            # txt_record is of the form "aiwebserver=example:46503" so split
            # on ":" and take the trailing portion for the port number
            port = svc['txt_record'].rsplit(':')[-1]
        except KeyError, err:
            parser.error(_("SMF data for service %s is corrupt. Missing "
                           "property: %s\n") % (options.service_name, err))
        service_dir = os.path.abspath("/var/ai/" + port)

    database = os.path.join(service_dir, "AI.db")

    # Check that the service directory and database exist
    if not (os.path.isdir(service_dir) and os.path.exists(database)):
        raise SystemExit("Error: Invalid AI service directory: %s" %
                         service_dir)

    # Open the database
    db = AIdb.DB(database, commit=True)

    # Check to make sure that the manifest whose criteria we're
    # updating exists in the install service.
    if not check_published_manifest(service_dir, db, options.manifest_name):
        raise SystemExit(1)

    # Process and validate criteria from -a, -c, or -C, and store
    # store the criteria in a Criteria object.
    try:
        if options.criteria_file:
            root = pub_man.verifyCriteria(pub_man.DataFiles.criteriaSchema,
                                          options.criteria_file, db)
        elif options.criteria_a:
            criteria_dict = pub_man.criteria_to_dict(options.criteria_a)
            root = pub_man.verifyCriteriaDict(pub_man.DataFiles.criteriaSchema,
                                              criteria_dict, db)
        elif options.criteria_c:
            criteria_dict = pub_man.criteria_to_dict(options.criteria_c)
            root = pub_man.verifyCriteriaDict(pub_man.DataFiles.criteriaSchema,
                                              criteria_dict, db)
    except (AssertionError, IOError, ValueError) as err:
        raise SystemExit(err)
    except (lxml.etree.LxmlError) as err:
        raise SystemExit(_("Error:\tmanifest error: %s") % err)

    # Instantiate a Criteria object with the XML DOM of the criteria.
    criteria = pub_man.Criteria(root)

    # Ensure the criteria we're adding/setting for this manifest doesn't
    # cause a criteria collision in the DB.
    colliding_criteria = pub_man.find_colliding_criteria(criteria, db,
                             exclude_manifests=[options.manifest_name])
    # If we're appending criteria pass the manifest name
    if options.criteria_a:
        pub_man.find_colliding_manifests(criteria, db, colliding_criteria,
                                         append_manifest=options.manifest_name)
    else:
        pub_man.find_colliding_manifests(criteria, db, colliding_criteria,
                                         append_manifest=None)

    # Update the criteria for this manifest.
    if options.criteria_a:
        set_criteria(criteria, options.manifest_name, db, append=True)
    else:
        set_criteria(criteria, options.manifest_name, db, append=False)

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
AI publish_manifest
"""
import gettext
import logging
import os

import lxml.etree

from optparse import OptionParser

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.data_files as df
import osol_install.auto_install.service_config as config
from osol_install.auto_install.installadm_common import _
from osol_install.auto_install.service import AIService

INFINITY = str(0xFFFFFFFFFFFFFFFF)

# Modes of operation.
DO_CREATE = True
DO_UPDATE = False

# Eventually rename functions to convention.


def get_create_usage():
    '''usage for create-manifest'''
    return _('create-manifest\t-n|--service <svcname>\n'
             '\t\t-f|--file <manifest/script file> \n'
             '\t\t[-m|--manifest <manifest/script name>]\n'
             '\t\t[-c|--criteria <criteria=value|range> ... | \n'
             '\t\t -C|--criteria-file <criteria.xml>]  \n'
             '\t\t[-d|--default]')


def get_update_usage():
    '''get usage for update-manifest'''
    return _('update-manifest\t-n|--service <svcname>\n'
             '\t\t-f|--file <manifest/script file> \n'
             '\t\t[-m|--manifest <manifest/script name>]')


def parse_options(do_create, cmd_options=None):
    """
    Parse and validate options
    Args: - do_create (True) or do_update (False)
          - Optional cmd_options, used for unit testing. Otherwise, cmd line
            options handled by OptionParser
    Returns: the DataFiles object populated and initialized
    Raises: The DataFiles initialization of manifest(s) A/I, SC, SMF looks for
            many error conditions and, when caught, are flagged to the user
            via raising SystemExit exceptions.

    """
    if do_create:
        usage = '\n' + get_create_usage()
    else:
        usage = '\n' + get_update_usage()
    parser = OptionParser(usage=usage)
    if do_create:
        parser.add_option("-c", "--criteria", dest="criteria_c",
                          action="append", default=list(), help=_("Criteria: "
                          "<-c criteria=value|range> ..."), metavar="CRITERIA")
        parser.add_option("-C", "--criteria-file", dest="criteria_file",
                          default=None, help=_("Path to criteria XML file."))
        parser.add_option("-d", "--default", dest="set_as_default",
                          default=False, action='store_true',
                          help=_("Set manifest as default "))
    parser.add_option("-f", "--file", dest="manifest_path",
                      default=None, help=_("Path to manifest file "))
    parser.add_option("-m", "--manifest", dest="manifest_name",
                      default=None, help=_("Name of manifest"))
    parser.add_option("-n", "--service", dest="service_name",
                      default=None, help=_("Name of install service."))

    # Get the parsed options using parse_args().  We know we don't have
    # args, so we're just grabbing the first item of the tuple returned.
    options, args = parser.parse_args(cmd_options)

    if len(args):
        parser.error(_("Unexpected argument(s): %s" % args))

    if not do_create:
        options.criteria_file = None
        options.criteria_c = None
        options.set_as_default = False

    # options are:
    #    -c  criteria=<value/range> ...       (create only)
    #    -C  XML file with criteria specified (create only)
    #    -d  set manifest as default          (create only)
    #    -n  service name
    #    -f  path to manifest file
    #    -m  manifest name

    # check that we got the install service's name.
    if options.service_name is None:
        parser.error(_("Missing required option "
                       "-n <service_name>."))

    # check that we got the AI manifest.
    if options.manifest_path is None:
        parser.error(_("Missing required option "
                       "-f <manifest/script file>."))

    logging.debug("options = %s", options)

    criteria_dict = None
    if do_create:
        # check that we aren't mixing -c and -C
        # Note: -c and -C will be accepted for create, not for update.
        if options.criteria_c and options.criteria_file:
            parser.error(_("Options used are mutually exclusive."))

        # if we have criteria from cmd line, convert into dictionary
        if options.criteria_c:
            try:
                criteria_dict = criteria_to_dict(options.criteria_c)
            except ValueError as err:
                parser.error(err)

        elif options.criteria_file:
            if not os.path.exists(options.criteria_file):
                parser.error(_("Unable to find criteria file: %s") %
                             options.criteria_file)

    if not config.is_service(options.service_name):
        raise SystemExit(_("Failed to find service %s") % options.service_name)

    # Get the service's imagepath. If service is an alias, the
    # base service's imagepath is obtained.
    service = AIService(options.service_name)
    try:
        image_path = service.image.path
    except KeyError as err:
        raise SystemExit(_("Data for service %s is corrupt. Missing "
                           "property: %s\n") % (options.service_name, err))

    service_dir = service.config_dir
    dbname = service.database_path

    try:
        files = df.DataFiles(service_dir=service_dir, image_path=image_path,
                             database_path=dbname,
                             manifest_file=options.manifest_path,
                             manifest_name=options.manifest_name,
                             criteria_dict=criteria_dict,
                             criteria_file=options.criteria_file,
                             service_name=options.service_name,
                             set_as_default=options.set_as_default)
    except (AssertionError, IOError, ValueError) as err:
        raise SystemExit(err)
    except (lxml.etree.LxmlError) as err:
        raise SystemExit(_("Error:\tmanifest error: %s") % err)

    return(files)


def criteria_to_dict(criteria):
    """
    Convert criteria list into dictionary. This function is intended to be
    called by a main function, or the options parser, so it can potentially
    raise the SystemExit exception.
    Args: criteria in list format: [ criteria=value, criteria=value, ... ]
          where value can be a:  single string value
                                 space-separated string value (list of values)
                                 range (<lower>-<upper>)
    Returns: dictionary of criteria { criteria: value, criteria: value, ... }
             with all keys in lower case, values are case-sensitive.
    Raises: ValueError on malformed name=value strings in input list.
    """
    cri_dict = dict()
    for entry in criteria:
        entries = entry.partition("=")

        if entries[1]:
            if not entries[0]:
                raise ValueError(_("Missing criteria name in "
                                   "'%s'\n") % entry)
            elif entries[0].lower() in cri_dict:
                raise ValueError(_("Duplicate criteria: '%s'\n") %
                             entries[0])
            elif not entries[2]:
                raise ValueError(_("Missing value for criteria "
                                   "'%s'\n") % entries[0])
            cri_dict[entries[0].lower()] = entries[2]
        else:
            raise ValueError(_("Criteria must be of the form "
                               "<criteria>=<value>\n"))

    return cri_dict


def find_colliding_criteria(criteria, db, exclude_manifests=None):
    """
    Returns: A dictionary of colliding criteria with keys being manifest name
             and instance tuples and values being the DB column names which
             collided
    Args:    criteria - Criteria object holding the criteria that is to be
                        added/set for a manifest.
             db - AI_database object for the install service.
             exclude_manifests -A list of manifest names from DB to ignore.
                                This arg is passed in when we're calling this
                                function to find criteria collisions for an
                                already published manifest.
    Raises:  SystemExit if: criteria is not found in database
                            value is not valid for type (integer and
                            hexadecimal checks)
                            range is improper
    """
    class Fields(object):
        """
        Define convenience indexes
        """
        # manifest name is row index 0
        MANNAME = 0
        # manifest instance is row index 1
        MANINST = 1
        # criteria is row index 2 (when a single valued criteria)
        CRIT = 2
        # minimum criteria is row index 2 (when a range valued criteria)
        MINCRIT = 2
        # maximum criteria is row index 3 (when a range valued criteria)
        MAXCRIT = 3

    # collisions is a dictionary to hold keys of the form (manifest name,
    # instance) which will point to a comma-separated string of colliding
    # criteria
    collisions = dict()

    # verify each range criteria in the manifest is well formed and collect
    # collisions with database entries
    for crit in criteria:
        # gather this criteria's values from the manifest
        man_criterion = criteria[crit]

        # Determine if this crit is a range criteria or not.
        is_range_crit = AIdb.isRangeCriteria(db.getQueue(), crit,
            AIdb.MANIFESTS_TABLE)

        # Process "value" criteria here (check if the criteria exists in
        # DB, and then find collisions)
        if not is_range_crit:
            # only check criteria in use in the DB
            if crit not in AIdb.getCriteria(db.getQueue(),
                                            onlyUsed=False, strip=False):
                raise SystemExit(_("Error:\tCriteria %s is not a " +
                                   "valid criteria!") % crit)

            # get all values in the database for this criteria (and
            # manifest/instance pairs for each value)
            db_criteria = AIdb.getSpecificCriteria(
                db.getQueue(), crit,
                provideManNameAndInstance=True,
                excludeManifests=exclude_manifests)

            # will iterate over a list of the form [manName, manInst, crit,
            # None]
            for row in db_criteria:
                # check if a value in the list of values to be added is equal
                # to a value in the list of values for this criteria for this
                # row
                for value in man_criterion:
                    if AIdb.is_in_list(crit, value, str(row[Fields.CRIT]),
                        None):
                        # record manifest name, instance and criteria name
                        try:
                            collisions[row[Fields.MANNAME],
                                       row[Fields.MANINST]] += crit + ","
                        except KeyError:
                            collisions[row[Fields.MANNAME],
                                       row[Fields.MANINST]] = crit + ","

        # This is a range criteria.  (Check that ranges are valid, that
        # "unbounded" gets set to 0/+inf, ensure the criteria exists
        # in the DB, then look for collisions.)
        else:
            # Clean-up NULL's and change "unbounded"s to 0 and
            # really large numbers in case this Python does
            # not support IEEE754.  Note "unbounded"s are already
            # converted to lower case during manifest processing.
            if man_criterion[0] == "unbounded":
                man_criterion[0] = "0"
            if man_criterion[1] == "unbounded":
                man_criterion[1] = INFINITY
            if crit == "mac":
                # convert hex mac address (w/o colons) to a number
                try:
                    man_criterion[0] = long(str(man_criterion[0]).upper(), 16)
                    man_criterion[1] = long(str(man_criterion[1]).upper(), 16)
                except ValueError:
                    raise SystemExit(_("Error:\tCriteria %s "
                                       "is not a valid hexadecimal value") %
                                     crit)
            else:
                # this is a decimal value
                try:
                    man_criterion = [long(str(man_criterion[0]).upper()),
                                     long(str(man_criterion[1]).upper())]
                except ValueError:
                    raise SystemExit(_("Error:\tCriteria %s "
                                       "is not a valid integer value") % crit)

            # Check for a properly ordered range (with unbounded being 0 or
            # Inf.) but ensure both are not unbounded.
            # Check for:
            #       a range of zero to inf -- not a valid range
            #  and
            #       min > max -- range order reversed
            #
            if (man_criterion[0] == 0 and man_criterion[1] == long(INFINITY)):
                raise SystemExit(_("Error:\tCriteria %s is not a valid range, "
                                   "MIN and MAX unbounded.") % crit)

            if ((man_criterion[0] != 0 and
                 man_criterion[1] != long(INFINITY)) and
                (long(man_criterion[0]) > long(man_criterion[1]))):
                raise SystemExit(_("Error:\tCriteria %s is not a valid range, "
                                   "MIN > MAX.") % crit)
            # check to see that this criteria exists in the database columns
            man_crit = AIdb.getCriteria(db.getQueue(), onlyUsed=False,
                                        strip=False)
            if 'MIN' + crit not in man_crit and 'MAX' + crit not in man_crit:
                raise SystemExit(_("Error:\tCriteria %s is not a "
                                   "valid criteria!") % crit)
            db_criteria = AIdb.getSpecificCriteria(
                db.getQueue(), 'MIN' + crit, 'MAX' + crit,
                provideManNameAndInstance=True,
                excludeManifests=exclude_manifests)

            # will iterate over a list of the form [manName, manInst, mincrit,
            # maxcrit]
            for row in db_criteria:
                # arbitrarily large number in case this Python does
                # not support IEEE754
                db_criterion = ["0", INFINITY]

                # now populate in valid database values (i.e. non-NULL values)
                if row[Fields.MINCRIT]:
                    db_criterion[0] = row[Fields.MINCRIT]
                if row[Fields.MAXCRIT]:
                    db_criterion[1] = row[Fields.MAXCRIT]
                if crit == "mac":
                    # use a hexadecimal conversion
                    db_criterion = [long(str(db_criterion[0]), 16),
                                    long(str(db_criterion[1]), 16)]
                else:
                    # these are decimal numbers
                    db_criterion = [long(str(db_criterion[0])),
                                    long(str(db_criterion[1]))]

                # these three criteria can determine if there's a range overlap
                if((man_criterion[1] >= db_criterion[0] and
                   db_criterion[1] >= man_criterion[0]) or
                   man_criterion[0] == db_criterion[1]):
                    # range overlap so record the collision
                    try:
                        collisions[row[Fields.MANNAME],
                                   row[Fields.MANINST]] += "MIN" + crit + ","
                        collisions[row[Fields.MANNAME],
                                   row[Fields.MANINST]] += "MAX" + crit + ","
                    except KeyError:
                        collisions[row[Fields.MANNAME],
                                   row[Fields.MANINST]] = "MIN" + crit + ","
                        collisions[row[Fields.MANNAME],
                                   row[Fields.MANINST]] += "MAX" + crit + ","
    return collisions


def find_colliding_manifests(criteria, db, collisions, append_manifest=None):
    """
    For each manifest/instance pair in collisions check that the manifest
    criteria diverge (i.e. are not exactly the same) and that the ranges do not
    collide for ranges.
    Raises if: a range collides, or if the manifest has the same criteria as a
    manifest already in the database (SystemExit raised)
    Returns: Nothing
    Args: criteria - Criteria object holding the criteria that is to be
                     added/set for a manifest.
          db - AI_database object for the install service.
          collisions - a dictionary with collisions, as produced by
                       find_colliding_criteria()
          append_manifest - name of manifest we're appending criteria to.
                            This arg is passed in when we're calling this
                            function to find criteria collisions for an
                            already published manifest that we're appending
                            criteria to.
    """

    # If we're appending criteria to an already published manifest, get a
    # dictionary of the criteria that's already published for that manifest.
    if append_manifest is not None:
        published_criteria = AIdb.getManifestCriteria(append_manifest, 0,
                                                      db.getQueue(),
                                                      humanOutput=True,
                                                      onlyUsed=False)

    # check every manifest in collisions to see if manifest collides (either
    # identical criteria, or overlaping ranges)
    for man_inst in collisions:
        # get all criteria from this manifest/instance pair
        db_criteria = AIdb.getManifestCriteria(man_inst[0],
                                               man_inst[1],
                                               db.getQueue(),
                                               humanOutput=True,
                                               onlyUsed=False)

        # iterate over every criteria in the database
        for crit in AIdb.getCriteria(db.getQueue(),
                                     onlyUsed=False, strip=False):

            # Get the criteria name (i.e. no MIN or MAX)
            crit_name = crit.replace('MIN', '', 1).replace('MAX', '', 1)
            # Set man_criterion to the key of the DB criteria or None
            man_criterion = criteria[crit_name]

            if man_criterion and crit.startswith('MIN'):
                man_criterion = man_criterion[0]
            elif man_criterion and crit.startswith('MAX'):
                man_criterion = man_criterion[1]

            # If man_criterion is still None, and if we're appending criteria
            # to an already published manifest, look for criteria in the
            # published set of criteria for the manifest we're appending to
            # as well, because existing criteria might cause a collision,
            # which we need to compare for.
            if man_criterion is None and append_manifest is not None:
                man_criterion = published_criteria[str(crit)]
                # replace database NULL's with Python None
                if man_criterion == '':
                    man_criterion = None

            # set the database criteria
            if db_criteria[str(crit)] == '':
                # replace database NULL's with a Python None
                db_criterion = None
            else:
                db_criterion = db_criteria[str(crit)]

            # Replace unbounded's in the criteria (i.e. 0/+inf)
            # with a Python None.
            if isinstance(man_criterion, basestring) and \
               man_criterion == "unbounded":
                man_criterion = None

            # check to determine if this is a range collision by using
            # collisions and if not are the manifests divergent

            if((crit.startswith('MIN') and
                collisions[man_inst].find(crit + ",") != -1) or
               (crit.startswith('MAX') and
                collisions[man_inst].find(crit + ",") != -1)
              ):
                if str(db_criterion).lower() != str(man_criterion).lower():
                    raise SystemExit(_("Error:\tManifest has a range "
                                       "collision with manifest:%s/%i"
                                       "\n\tin criteria: %s!") %
                                     (man_inst[0], man_inst[1],
                                      crit.replace('MIN', '', 1).
                                      replace('MAX', '', 1)))

            # Either the range did not collide or this is not a range
            # criteria.  (If the value of this criteria in the db does
            # not equal the value of this criteria for the set of criteria
            # to check, we can break out knowing we diverge for this
            # manifest/instance)
            elif not db_criterion and not man_criterion:
                # Neither the value for this criteria in the db nor
                # the value for for this criteria in the given set of
                # criteria to check are populated.  Loop around to
                # check the next criteria.
                continue
            elif not db_criterion or not man_criterion:
                # One of the two are not populated, we can break knowing
                # they're different.
                break
            else:
                # Both are populated.  If none of values in the list for
                # this criteria to be added are equal to any of the values
                # in the list for this criteria from the db, there will be
                # no collision.  We can break out.
                if not [value for value in man_criterion if \
                    AIdb.is_in_list(crit, value, str(db_criterion), None)]:
                    break

        # end of for loop and we never broke out (collision)
        else:
            raise SystemExit(_("Error:\tManifest has same criteria as " +
                               "manifest: %s/%i!") %
                             (man_inst[0], man_inst[1]))


def do_publish_manifest(cmd_options=None):
    '''
    Publish a manifest, associating it with an install service.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tRoot privileges are required for "
                           "this command."))

    # load in all the options and file data.  Validate proper manifests.
    data = parse_options(DO_CREATE, cmd_options)

    service = AIService(data.service_name)
    # Disallow multiple manifests or scripts with the same mname.
    manifest_path = os.path.join(service.manifest_dir, data.manifest_name)
    if os.path.exists(manifest_path):
        raise SystemExit(_("Error:\tName %s is already registered with "
                           "this service.") % data.manifest_name)

    # if criteria are provided, make sure they are a unique set.
    if data.criteria:
        find_colliding_manifests(data.criteria, data.database,
            find_colliding_criteria(data.criteria, data.database))

    # Add all manifests to the database, whether default or not, and whether
    # they have criteria or not.
    df.insert_SQL(data)

    # move the manifest into place
    df.place_manifest(data, manifest_path)

    # if we have a default manifest do default manifest handling
    if data.set_as_default:
        service.set_default_manifest(data.manifest_name)


def do_update_manifest(cmd_options=None):
    '''
    Update the contents of an existing manifest.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tRoot privileges are required for "
                           "this command."))

    # load in all the options and file data.  Validate proper manifests.
    data = parse_options(DO_UPDATE, cmd_options)

    service = AIService(data.service_name)
    manifest_path = os.path.join(service.manifest_dir, data.manifest_name)

    if not os.path.exists(manifest_path):
        raise SystemExit(_("Error:\tNo manifest or script with name "
                           "%s is registered with this service.\n"
                           "\tPlease use installadm "
                           "create-manifest instead.") %
                           data.manifest_name)

    # move the manifest into place
    df.place_manifest(data, manifest_path)


if __name__ == '__main__':
    gettext.install("solaris_install_aiwebserver", "/usr/share/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_publish_manifest()

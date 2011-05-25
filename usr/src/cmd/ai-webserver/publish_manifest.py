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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

"""

AI publish_manifest

"""

import errno
import gettext
import logging
import lxml.etree
import os.path
import pwd
import shutil
import StringIO
import sys

from stat import S_IRUSR, S_IWUSR
from optparse import OptionParser

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.verifyXML as verifyXML

from osol_install.auto_install.installadm_common import validate_service_name
from osol_install.auto_install.properties import set_default, get_service_info
from solaris_install import _, AI_DATA, KSH93_SHEBANG, PYTHON_SHEBANG

INFINITY = str(0xFFFFFFFFFFFFFFFF)
IMG_AI_MANIFEST_DTD = "auto_install/ai.dtd"
SYS_AI_MANIFEST_DTD = "/usr/share/install/ai.dtd"

IMG_AI_MANIFEST_SCHEMA = "auto_install/ai_manifest.rng"

# Modes of operation.
DO_ADD = True
DO_UPDATE = False

# 0600 for chmod
PERM_OWNER_RW = S_IRUSR + S_IWUSR

# Eventually rename functions to convention.
# pylint: disable-msg=C0103


def get_add_usage():
    """
    get usage for add-manifest
    """
    return(_(
        'add-manifest\t-n|--service <svcname>\n'
        '\t\t-f|--file <manifest_file/script file> \n'
        '\t\t[-m|--manifest <manifest/script name>]\n'
        '\t\t[-c|--criteria <criteria=value|range> ... | \n'
        '\t\t -C|--criteria-file <criteria.xml>]  \n'
        '\t\t[-d|--default]'))


def get_update_usage():
    """
    get usage for update-manifest
    """
    return(_(
        'update-manifest\t-n|--service <svcname>\n'
        '\t\t-f|--file <manifest/script file> \n'
        '\t\t-m|--manifest <manifest/script name>'))


def parse_options(do_add, cmd_options=None):
    """
    Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: the DataFiles object populated and initialized
    Raises: The DataFiles initialization of manifest(s) A/I, SC, SMF looks for
            many error conditions and, when caught, are flagged to the user
            via raising SystemExit exceptions.

    """
    if do_add:
        usage = '\n' + get_add_usage()
    else:
        usage = '\n' + get_update_usage()
    parser = OptionParser(usage=usage)
    if do_add:
        parser.add_option("-c", "--criteria", dest="criteria_c",
                          action="append", default=[], help=_("Criteria: "
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

    if not do_add:
        options.criteria_file = None
        options.criteria_c = None
        options.set_as_default = False

    # options are:
    #    -c  criteria=<value/range> ...       (add only)
    #    -C  XML file with criteria specified (add only)
    #    -d  set manifest as default          (add only)
    #    -n  service name
    #    -f  path to manifest file
    #    -m  manifest name

    # check that we got the install service's name and an AI manifest.
    if options.manifest_path is None or options.service_name is None:
        parser.error(_("Missing one or more required options."))

    logging.debug("options = %s", options)

    # validate service name
    try:
        validate_service_name(options.service_name)
    except ValueError as err:
        parser.error(err)

    criteria_dict = None
    if do_add:
        # check that we aren't mixing -c and -C
        # Note: -c and -C will be accepted for add, not for update.
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

    # get AI service database info
    service_dir, dbname, image_path = get_service_info(options.service_name)
    try:
        files = DataFiles(service_dir=service_dir, image_path=image_path,
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
          where value can be a:  single value
                                 range (<lower>-<upper>)
    Returns: dictionary of criteria { criteria: value, criteria: value, ... }
             with all keys and values in lower case
    Raises: ValueError on malformed name=value strings in input list.
    """
    cri_dict = {}
    for entry in criteria:
        entries = entry.lower().partition("=")

        if entries[1]:
            if not entries[0]:
                raise ValueError(_("Missing criteria name in "
                                   "'%s'\n") % entry)
            elif entries[0] in cri_dict:
                raise ValueError(_("Duplicate criteria: '%s'\n") %
                             entries[0])
            elif not entries[2]:
                raise ValueError(_("Missing value for criteria "
                                   "'%s'\n") % entries[0])
            cri_dict[entries[0]] = entries[2]
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

        # check "value" criteria here (check the criteria exists in DB, and
        # then find collisions)
        if isinstance(man_criterion, basestring):
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
                # check if the database and manifest values differ
                if(str(row[Fields.CRIT]).lower() ==
                   str(man_criterion).lower()):
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

            # the range did not collide or this is a single value (if we
            # differ we can break out knowing we diverge for this
            # manifest/instance)
            elif str(db_criterion).lower() != str(man_criterion).lower():
                # manifests diverge (they don't collide)
                break

        # end of for loop and we never broke out (diverged)
        else:
            raise SystemExit(_("Error:\tManifest has same criteria as " +
                               "manifest: %s/%i!") %
                             (man_inst[0], man_inst[1]))


def insert_SQL(files):
    """
    Ensures all data is properly sanitized and formatted, then inserts it into
    the database
    Args: None
    Returns: None
    """
    query = "INSERT INTO manifests VALUES("

    # add the manifest name to the query string
    query += "'" + AIdb.sanitizeSQL(files.manifest_name) + "',"
    # check to see if manifest name is already in database (affects instance
    # number)
    if AIdb.sanitizeSQL(files.manifest_name) in \
        AIdb.getManNames(files.database.getQueue()):
            # database already has this manifest name get the number of
            # instances
        instance = AIdb.numInstances(AIdb.sanitizeSQL(files.manifest_name),
                                     files.database.getQueue())
    # this a new manifest
    else:
        instance = 0

    # actually add the instance to the query string
    query += str(instance) + ","

    # we need to fill in the criteria or NULLs for each criteria the database
    # supports (so iterate over each criteria)
    for crit in AIdb.getCriteria(files.database.getQueue(),
                                 onlyUsed=False, strip=False):
        # for range values trigger on the MAX criteria (skip the MIN's
        # arbitrary as we handle rows in one pass)
        if crit.startswith('MIN'):
            continue

        # get the values from the manifest
        values = files.criteria[crit.replace('MAX', '', 1)]

        # If the critera manifest didn't specify this criteria, fill in NULLs
        if values is None:
            # use the criteria name to determine if this is a range
            if crit.startswith('MAX'):
                query += "NULL,NULL,"
            # this is a single value
            else:
                query += "NULL,"

        # this is a single criteria (not a range)
        elif isinstance(values, basestring):
            # translate "unbounded" to a database NULL
            if values == "unbounded":
                query += "NULL,"
            else:
                # use lower case for text strings
                query += "'" + AIdb.sanitizeSQL(str(values).lower()) + "',"

        # else values is a range
        else:
            for value in values:
                # translate "unbounded" to a database NULL
                if value == "unbounded":
                    query += "NULL,"
                # we need to deal with mac addresses specially being
                # hexadecimal
                elif crit.endswith("mac"):
                    # need to insert with hex operand x'<val>'
                    # use an upper case string for hex values
                    query += "x'" + AIdb.sanitizeSQL(str(value).upper()) + \
                             "',"
                else:
                    query += AIdb.sanitizeSQL(str(value).upper()) + ","

    # strip trailing comma and close parentheses
    query = query[:-1] + ")"

    # update the database
    query = AIdb.DBrequest(query, commit=True)
    files.database.getQueue().put(query)
    query.waitAns()
    # in case there's an error call the response function (which will print the
    # error)
    query.getResponse()


def _copy_file(source, target):
    """
    Copy a file from source to target, and prepare for use by webserver.
    """
    # Copy the script.
    try:
        shutil.copyfile(source, target)
    except IOError as err:
        raise SystemExit(_("Error:\tUnable to copy script to dest: "
                           "\n\t%s: %s") % (err.strerror, err.filename))

    # change read and write for owner
    os.chmod(target, PERM_OWNER_RW)

    webserver_id = pwd.getpwnam('webservd').pw_uid
    # change to user/group webserver/root (uid/gid 0)
    os.chown(target, webserver_id, 0)


def place_manifest(files):
    """
    If manifest does not exist, copies new manifest into place and sets correct
    permissions and ownership
    Args: files - DataFiles object holding all of the relevant and verified
                  information for the manifest we're publishing.
    Returns: None
    Raises : Error, Unable to write destination manifest.
             Errors if _copy_file fails.
    """

    if files.manifest_is_script:
        root = None
    elif files.is_dtd:
        root = files.AI_root
    else:
        root = files.criteria_root

    # Write out the manifest.
    if root:

        # Remove all <ai_criteria> elements if they exist.
        for tag in root.xpath('/ai_criteria_manifest/ai_criteria'):
            tag.getparent().remove(tag)

        try:
            root.write(files.stored_manifest_path, pretty_print=True)
        except IOError as err:
            raise SystemExit(_("Error:\tUnable to store destination "
                               "manifest:\n\t%s") % err)

        # change read and write for owner
        os.chmod(files.stored_manifest_path, PERM_OWNER_RW)

        webserver_id = pwd.getpwnam('webservd').pw_uid
        # change to user/group webserver/root (uid/gid 0)
        os.chown(files.stored_manifest_path, webserver_id, 0)

    # "manifest" is a script
    else:
        _copy_file(files.manifest_path, files.stored_manifest_path)


def verifyCriteria(schema, criteria_path, db, table=AIdb.MANIFESTS_TABLE,
        is_dtd=True):
    """
    Used for verifying and loading criteria XML from a Criteria manifest,
    which can be a combined Criteria manifest (for backwards compatibility
    in supporting older install services) or a criteria manifest with just
    criteria.
    Args:       schema - path to schema file for criteria manifest.
                criteria_path - path to criteria XML manifest file to verify.
                db - database object for install service
                table - database table, distinguishing manifests from profiles
                is_dtd - criteria file should contain criteria only, no
                         AI or SC manifest info
    Raises IOError:
        *if the schema does not open
        *if the XML file does not open
    Raises ValueError:
        *if the XML is invalid according to the schema or has a syntax error
    Returns:    A valid XML DOM of the criteria manifest and all MAC and IPV4
                values are formatted according to
                verifyXML.prepValuesAndRanges().
    """
    schema = open(schema, 'r')

    # Remove AI and SC elements from within the Criteria manifests if
    # they exist.  We validate those separately later.
    try:
        crit = lxml.etree.parse(criteria_path)
    except lxml.etree.XMLSyntaxError, err:
        raise ValueError(_("Error: %s") % err.error_log.last_error)

    ai_sc_list = list()
    ai_sc_paths = (".//ai_manifest_file", ".//ai_embedded_manifest",
                   ".//sc_manifest_file", ".//sc_embedded_manifest")
    for path in ai_sc_paths:
        elements = crit.iterfind(path)

        for elem in elements:
            if is_dtd:
                raise ValueError(_("Error:\tCriteria file should not contain "
                                   "AI or SC manifest tags: %s") %
                                 criteria_path)
            ai_sc_list.append(elem)
            elem.getparent().remove(elem)

    # Verify the remaing DOM, which should only contain criteria
    root, errors = (verifyXML.verifyRelaxNGManifest(schema,
            StringIO.StringIO(lxml.etree.tostring(crit.getroot()))))
    logging.debug('criteria file passed RNG validation')

    if errors:
        raise ValueError(_("Error:\tFile %s failed validation:\n\t%s") %
                         (criteria_path, root.message))
    try:
        verifyXML.prepValuesAndRanges(root, db, table)
    except ValueError, err:
        raise ValueError(_("Error:\tCriteria manifest error: %s") % err)

    # Reinsert AI and SC elements back into the criteria_root DOM.
    for ai_sc_element in ai_sc_list:
        root.getroot().append(ai_sc_element)

    return root


def verifyCriteriaDict(schema, criteria_dict, db, table=AIdb.MANIFESTS_TABLE):
    """
    Used for verifying and loading criteria from a dictionary of criteria.
    Args:       schema - path to schema file for criteria manifest.
                criteria_dict - dictionary of criteria to verify, in the form
                                of { criteria: value, criteria: value, ... }
                db - database object for install service
                table - database table, distinguishing manifests from profiles
    Raises IOError:
               * if the schema does not open
           ValueError:
                * if the criteria_dict dictionary is empty
                * if the XML is invalid according to the schema
           AssertionError:
                * if a value in the dictionary is empty
    Returns:    A valid XML DOM of the criteria and all MAC and IPV4 values
                are formatted according to verifyXML.prepValuesAndRanges().
    """
    schema = open(schema, 'r')

    if not criteria_dict:
        raise ValueError("Error:\tCriteria dictionary empty: %s\n"
                         % criteria_dict)

    root = lxml.etree.Element("ai_criteria_manifest")

    for name, value_or_range in criteria_dict.iteritems():

        if value_or_range is None:
            raise AssertionError(_("Error: Missing value for criteria "
                                   "'%s'") % name)

        crit = lxml.etree.SubElement(root, "ai_criteria")
        crit.set("name", name)

        # If criteria is a range, split on "-" and add to
        # XML DOM as a range element.
        if AIdb.isRangeCriteria(db.getQueue(), name, table):
            # Split on "-"
            range_value = value_or_range.split('-', 1)

            # If there was only a single value, means user specified
            # this range criteria as a single value, add it as a single
            # value
            if len(range_value) == 1:
                value_elem = lxml.etree.SubElement(crit, "value")
                value_elem.text = value_or_range
            else:
                range_elem = lxml.etree.SubElement(crit, "range")
                range_elem.text = " ".join(range_value)
        else:
            value_elem = lxml.etree.SubElement(crit, "value")
            value_elem.text = value_or_range

    # Verify the generated criteria DOM
    root, errors = verifyXML.verifyRelaxNGManifest(schema,
                        StringIO.StringIO(lxml.etree.tostring(root)))
    if errors:
        raise ValueError(_("Error: Criteria failed validation:\n\t%s") %
                           root.message)

    try:
        verifyXML.prepValuesAndRanges(root, db, table)
    except ValueError, err:
        raise ValueError(_("Error:\tCriteria error: %s") % err)

    return root


# The criteria class is a list object with an overloaded get_item method
# to act like a dictionary, looking up values from an underlying XML DOM.
class Criteria(list):
    """
    Wrap list class to provide lookups in the criteria file when requested
    """
    def __init__(self, criteria_root):
        # store the criteria manifest DOM root
        self._criteria_root = criteria_root
        # call the _init_() for the list class with a generator provided by
        # find_criteria() to populate this _criteria() instance.
        super(Criteria, self).__init__(self.find_criteria())

    def find_criteria(self):
        """
        Find criteria from the criteria DOM.
        Returns: A generator providing all criteria name attributes from
                 <ai_criteria> tags
        """

        if self._criteria_root is None:
            return

        root = self._criteria_root.findall(".//ai_criteria")

        # actually find criteria
        for tag in root:
            for child in tag.getchildren():
                if (child.tag == "range" or child.tag == "value") and \
                    child.text is not None:
                    # criteria names are lower case
                    yield tag.attrib['name'].lower()
                else:
                    # should not happen according to schema
                    raise AssertionError(_("Criteria contains no values"))

    def get_criterion(self, criterion):
        """
        Return criterion out of the criteria DOM
        Returns: A list for range criterion with a min and max entry
                 A string for value criterion
        """

        if self._criteria_root is None:
            return None

        source = self._criteria_root
        for tag in source.getiterator('ai_criteria'):
            crit = tag.get('name')
            # compare criteria name case-insensitive
            if crit.lower() == criterion.lower():
                for child in tag.getchildren():
                    if child.tag == "range":
                        # this is a range response (split on white space)
                        return child.text.split()
                    elif child.tag == "value":
                        # this is a value response (strip white space)
                        return child.text.strip()
                    # should not happen according to schema
                    elif child.text is None:
                        raise AssertionError(_("Criteria contains no values"))
        return None

    """
    Look up a requested criteria (akin to dictionary access) but for an
    uninitialized key will not raise an exception but return None)
    """
    __getitem__ = get_criterion

    # disable trying to update criteria
    __setitem__ = None
    __delitem__ = None


class DataFiles(object):
    """
    Class to contain and work with data files necessary for program
    """
    # schema for validating an AI criteria manifest
    criteriaSchema = "/usr/share/auto_install/criteria_schema.rng"
    # DTD for validating an SMF SC manifest
    smfDtd = "/usr/share/lib/xml/dtd/service_bundle.dtd.1"

    def __init__(self, service_dir=None, image_path=None,
                 database_path=None, manifest_file=None,
                 criteria_dict=None, criteria_file=None, manifest_name=None,
                 service_name=None, set_as_default=False):

        """
        Initialize DataFiles instance. All parameters optional, however, proper
        setup order asurred, if all data provided upon instantiation.
        """

        #
        # State variables
        #################
        #

        # Variable to cache criteria class for criteria property
        self._criteria_cache = None

        # Holds path to AI manifest being published (may not be set if an
        # embedded manifest)
        self._manifest = None

        self.criteria_dict = criteria_dict
        self.criteria_file = criteria_file

        # Flag to indicate we're operating with the newer AI DTD,
        # or with the older AI rng schema
        self.is_dtd = True

        # Flag to indicate that the "manifest" is really a script.
        # This is to support derived manifests.
        self.manifest_is_script = False

        # Flag to indicate to set the current manifest as the default.
        self.set_as_default = set_as_default

        # Store service name
        self.service_name = service_name

        #
        # File system path variables
        ############################
        #

        # Check AI Criteria Schema exists
        if not os.path.exists(self.criteriaSchema):
            raise IOError(_("Error:\tUnable to find criteria_schema: " +
                            "%s") % self.criteriaSchema)

        # Check SC manifest SMF DTD exists
        if not os.path.exists(self.smfDtd):
            raise IOError(_("Error:\tUnable to find SMF system " +
                            "configuration DTD: %s") % self.smfDtd)

        # A/I Manifest Schema
        self._AIschema = None

        # Holds path to service directory (i.e. /var/ai/46501)
        self._service = None
        if service_dir:
            self.service = service_dir

        # Holds path to AI image
        self._imagepath = None
        if image_path:
            self.image_path = image_path
            # set the AI schema once image_path is set
            self.set_AI_schema()

        # Holds database object for criteria database
        self._db = None
        if database_path:
            # Set Database Path and Open SQLite3 Object
            self.database = database_path
            # verify the database's table/column structure (or exit if errors)
            self.database.verifyDBStructure()

        # Holds DOM for criteria manifest
        self.criteria_root = None

        # Determine if we're operating with the newer AI DTD,
        # or with the older AI rng schema
        try:
            lxml.etree.DTD(self.AI_schema)
            self.is_dtd = True
        except lxml.etree.DTDParseError:
            try:
                lxml.etree.RelaxNG(file=self.AI_schema)
                self.is_dtd = False
            except lxml.etree.RelaxNGParseError:
                raise ValueError(_("Error: Unable to determine AI manifest "
                                   "validation type.\n"))

        self._manifest_name = manifest_name
        self.manifest_is_script = self.manifest_is_a_script(manifest_file)

        # Bypass XML verification if script passed in instead of a manifest.
        if self.manifest_is_script:
            self._manifest = manifest_file

        # Verify the AI manifest to make sure its valid
        elif self.is_dtd:
            self._manifest = manifest_file
            self.verify_AI_manifest()

            # Holds DOMs for SC manifests
            self._smfDict = dict()

            # Look for a SC manifests specified within the manifest file
            # sets _smfDict DOMs
            self.find_SC_from_manifest(self.AI_root, self.manifest_path)
        else:
            # Holds path for manifest file (if reference to AI manifest URI
            # found inside the combined Criteria manifest)
            self._manifest = None

            self.criteria_path = manifest_file
            self.criteria_root = verifyCriteria(self.criteriaSchema,
                                                 self.criteria_path,
                                                 self.database,
                                                 is_dtd=self.is_dtd)

            # Holds DOM for AI manifest
            self.AI_root = None

            # Since we were provided a combined criteria manifest, look for
            # an A/I manifest specified by the criteria manifest
            if self.criteria_root:

                # This will set _manifest to be the AI manifest path (if a
                # file), or set AI_root to the correct location in the
                # criteria DOM (if embedded), or exit (if unable to find an
                # AI manifest)
                self.find_AI_from_criteria()

                # This will parse _manifest (if it was set from above), load
                # it into an XML DOM and set AI_root to it.  The AI_root DOM
                # will then be verified.  The function will exit on error.
                self.verify_AI_manifest()

                # Holds DOMs for SC manifests
                self._smfDict = dict()

                # Look for a SC manifests specified within the manifest file
                # sets _smfDict DOMs
                self.find_SC_from_manifest(self.criteria_root,
                                           self.criteria_path)

        # Process criteria from -c, or -C.  This will setup criteria_root
        # as a DOM and will overwrite the DOM from criteria found in a
        # combined Criteria manifest.
        if self.criteria_file:
            self.criteria_path = self.criteria_file
            root = verifyCriteria(self.criteriaSchema, self.criteria_path,
                                  self.database, is_dtd=self.is_dtd)
            # Set this criteria into criteria_root
            self.set_criteria_root(root)
        elif self.criteria_dict:
            root = verifyCriteriaDict(self.criteriaSchema, self.criteria_dict,
                                      self.database)
            # Set this criteria into criteria_root
            self.set_criteria_root(root)

    @property
    def criteria(self):
        """
        Function to provide access to criteria class (and provide caching of
        class created)
        Returns: A criteria instance
        """
        # if we don't have a cached _criteria class, create one and update the
        # cache
        if not self._criteria_cache:
            self._criteria_cache = Criteria(self.criteria_root)
        # now return cached _criteria class
        return self._criteria_cache

    def open_database(self, db_file):
        """
        Sets self._db (opens database object) and errors if already set or file
        does not yet exist
        Args: A file path to an SQLite3 database
        Raises: SystemExit if path does not exist,
                AssertionError if self._db is already set
        Returns: Nothing
        """
        if not os.path.exists(db_file):
            raise SystemExit(_("Error:\tFile %s is not a valid database "
                               "file") % db_file)
        elif self._db is None:
            self._db = AIdb.DB(db_file, commit=True)
        else:
            raise AssertionError('Opening database when already open!')

    def get_database(self):
        """
        Returns self._db (database object) and errors if not set
        Raises: AssertionError if self._db is not yet set
        Returns: SQLite3 database object
        """
        if isinstance(self._db, AIdb.DB):
            return (self._db)
        else:
            raise AssertionError('Database not yet open!')

    database = property(get_database, open_database, None,
                        "Holds database object for criteria database")

    def get_service(self):
        """
        Returns self._service and errors if not yet set
        Raises: AssertionError if self._service is not yet set
        Returns: String object
        """
        if self._service is not None:
            return(self._service)
        else:
            raise AssertionError('Service not yet set!')

    def set_service(self, serv=None):
        """
        Sets self._service and errors if already set
        Args: A string path to an AI service directory
        Raises: SystemExit if path does not exist,
                AssertionError if self._service is already set
        Returns: Nothing
        """
        if not os.path.isdir(serv):
            raise SystemExit(_("Error:\tDirectory %s is not a valid AI "
                               "directory") % serv)
        elif self._service is None:
            self._service = os.path.abspath(serv)
        else:
            raise AssertionError('Setting service when already set!')

    service = property(get_service, set_service, None,
                       "Holds path to service directory (i.e. /var/ai/46501)")

    def find_SC_from_manifest(self, manifest_root, manifest_path):
        """
        Find SC manifests as referenced in the manifest file.  We search for
        embedded SC manifests first, then do a subsequent search for SC file
        references and expand them in-place in the manifest_root DOM, to be
        embedded SC manifests.
        Preconditions: None
        Postconditions: self._smfDict will be a dictionary containing all
                        SC manifest DOMs
        Raises: AssertionError: - if manifest_root or manifest_path are not set
                                - if two SC manifests are named the same
        Args:   manifest_root - a valid XML DOM of the manifest from which
                                will find SC manifests.
                manifest_path - a path to the file from which manifest_root
                        was created.
        Returns: None
        """
        root = manifest_root.iterfind(".//sc_embedded_manifest")

        # For each SC manifest embedded: verify it, adding it to the
        # dictionary of SMF SC manifests
        for SC_man in root:
            # strip the comments off the SC manifest
            xml_data = lxml.etree.tostring(SC_man.getchildren()[0])
            xml_data = xml_data.replace("<!-- ", "").replace("-->", "")
            xml_data = StringIO.StringIO(xml_data)
            # parse and read in the SC manifest
            self._smfDict[SC_man.attrib['name']] = \
                self.verify_SC_manifest(xml_data, name=SC_man.attrib['name'])

        root = manifest_root.iterfind(".//sc_manifest_file")

        # For each SC manifest file: get the URI and verify it, adding it to
        # the dictionary of SMF SC manifests (this means we can support a
        # manifest file with multiple SC manifests embedded or referenced)
        for SC_man in root:
            if SC_man.attrib['name'] in self._smfDict:
                raise AssertionError(_("Error:\tTwo SC manifests with name %s")
                                     % SC_man.attrib['name'])
            # if this is an absolute path just hand it off
            if os.path.isabs(str(SC_man.attrib['URI'])):
                self._smfDict[SC_man.attrib['name']] = \
                    self.verify_SC_manifest(SC_man.attrib['URI'])
            # this is not an absolute path - make it one
            else:
                self._smfDict[SC_man.attrib['name']] = \
                    self.verify_SC_manifest(os.path.join(os.path.dirname(
                                          manifest_path),
                                          SC_man.attrib['URI']))

            # Replace each SC manifest file element in the manifest root DOM
            # with an embedded manifest, using the content from its referenced
            # file, which has just been loaded into the _smfDict of SC DOMs.
            old_sc = self._smfDict[SC_man.attrib['name']]
            new_sc = lxml.etree.Element("sc_embedded_manifest")
            new_sc.set("name", SC_man.get("name"))
            new_sc.text = "\n\t"
            new_sc.tail = "\n"
            embedded_sc = lxml.etree.Comment(" <?xml version='%s'?>\n\t" %
                        old_sc.docinfo.xml_version +
                        lxml.etree.tostring(old_sc, pretty_print=True,
                                encoding=unicode, xml_declaration=False))
            embedded_sc.tail = "\n"

            new_sc.append(embedded_sc)
            SC_man.getparent().replace(SC_man, new_sc)

    def find_AI_from_criteria(self):
        """
        Find AI manifest as referenced or embedded in a criteria manifest.
        Preconditions: self.criteria_root is a valid XML DOM
        Postconditions: self.manifest_path will be set if using a free-standing
                        AI manifest otherwise self.AI_root will be set to a
                        valid XML DOM for the AI manifest
        Raises: ValueError for XML processing errors
                           for no ai_manifest_file specification
                AssertionError if criteria_root not set
        """
        if self.criteria_root is None:
            raise AssertionError(_("Error:\tcriteria_root not set!"))

        # Try to find an embedded AI manifest.
        root = self.criteria_root.find(".//ai_embedded_manifest")
        if root is not None:
            self.AI_root = root.find(".//ai_manifest")
            if self.AI_root is not None:
                return
            else:
                raise ValueError(_("Error: <ai_embedded_manifest> missing "
                                       "<ai_manifest>"))

        # Try to find an AI manifest file reference.
        root = self.criteria_root.find(".//ai_manifest_file")

        if root is not None:
            try:
                if os.path.isabs(root.attrib['URI']):
                    self.manifest_path = root.attrib['URI']
                else:
                    # if we do not have an absolute path try using the criteria
                    # manifest's location for a base
                    self.manifest_path = \
                        os.path.join(os.path.dirname(self.criteria_path),
                                     root.attrib['URI'])
                return
            except KeyError:
                raise ValueError(_("Error: <ai_manifest_file> missing URI"))

        raise ValueError(_("Error: No <ai_manifest_file> or "
                           "<ai_embedded_manifest> element in "
                           "criteria manifest."))

    @property
    def AI_schema(self):
        """
        Returns self._AIschema and errors if not yet set
        Args: None
        Raises: AssertionError if self._AIschema is not yet set
        Returns: String object
        """
        if self._AIschema is not None:
            return (self._AIschema)
        else:
            raise AssertionError('AIschema not set')

    def set_AI_schema(self):
        """
        Sets self._AIschema and errors if imagepath not yet set.
        Args: None
        Raises: SystemExit if unable to find a valid AI schema
        Returns: None
        """
        if os.path.exists(os.path.join(self.image_path,
                                       IMG_AI_MANIFEST_DTD)):
            self._AIschema = os.path.join(self.image_path,
                                          IMG_AI_MANIFEST_DTD)
        elif os.path.exists(os.path.join(self.image_path,
                                         IMG_AI_MANIFEST_SCHEMA)):
            self._AIschema = os.path.join(self.image_path,
                                         IMG_AI_MANIFEST_SCHEMA)
        else:
            if os.path.exists(SYS_AI_MANIFEST_DTD):
                self._AIschema = SYS_AI_MANIFEST_DTD
                print (_("Warning: Using AI manifest dtd <%s>\n") %
                        self._AIschema)
            else:
                raise SystemExit(_("Error:\tUnable to find an AI dtd!"))

    def get_image_path(self):
        """
        Returns self._imagepath and errors if not set
        Raises: AssertionError if self._imagepath is not yet set
        Returns: String object
        """
        if self._imagepath is not None:
            return (self._imagepath)
        else:
            raise AssertionError('Imagepath not set')

    def set_image_path(self, imagepath):
        """
        Sets self._imagepath but exits if already set or not a directory
        Args: image path to a valid AI image
        Raises: SystemExit if image path provided is not a directory
                AssertionError if image path is already set
        Returns: None
        """
        if not os.path.isdir(imagepath):
            raise SystemExit(_("Error:\tInvalid imagepath " +
                               "directory: %s") % imagepath)
        if self._imagepath is None:
            self._imagepath = os.path.abspath(imagepath)
        else:
            raise AssertionError('imagepath already set')

    image_path = property(get_image_path, set_image_path, None,
                        "Holds path to service's AI image")

    def get_manifest_path(self):
        """
        Returns self._manifest and errors if not set
        Raises: AssertionError if self._manifest is not yet set
        Returns: String object path to AI manifest
        """
        if self._manifest is not None:
            return(self._manifest)
        else:
            raise AssertionError('Manifest path not yet set!')

    def set_manifest_path(self, mani=None):
        """
        Sets self._manifest and errors if already set
        Args: path to an AI manifest
        Raises: AssertionError if manifest is already set
        Returns: None
        """
        if self._manifest is None:
            self._manifest = os.path.abspath(mani)
        else:
            raise AssertionError('Setting manifest when already set!')

    manifest_path = property(get_manifest_path, set_manifest_path, None,
                             "Holds path to AI manifest being published")

    @property
    def manifest_name(self):
        """
        Returns: name if passed on command line, manifest name if defined
                 in the AI manifest, otherwise defaults to name of file
        Raises: SystemExit if neither <ai_manifest> or <auto_install>
                can be found or if there is another problem identifying
                the manifest
        """
        attrib_name = None
        if not self.manifest_is_script:
            if self.AI_root.getroot().tag == "ai_manifest":
                attrib_name = self.AI_root.getroot().attrib['name']
            elif self.AI_root.getroot().tag == "auto_install":
                try:
                    ai_instance = self.AI_root.find(".//ai_instance")
                except lxml.etree.LxmlError, err:
                    raise SystemExit(_("Error:\tAI manifest error: %s") % err)

                if 'name' in ai_instance.attrib:
                    attrib_name = ai_instance.attrib['name']
            else:
                raise SystemExit(_("Error:\tCan not find either <ai_manifest> "
                                   "or <auto_install> tags!"))

        # Use name if passed on command line, else internal name if
        # defined, otherwise default to name of file
        if self._manifest_name:
            name = self._manifest_name
        elif attrib_name:
            name = attrib_name
        else:
            name = os.path.basename(self.manifest_path)
        return name

    @property
    def stored_manifest_path(self):
        """
        Returns the full path of the stored manifest or script.
        """
        return os.path.join(self.get_service(), AI_DATA,
                                self.manifest_name)

    def verify_AI_manifest(self):
        """
        Used for verifying and loading AI manifest as defined by
            DataFiles._AIschema.
        Args: None.
        Preconditions:  Expects its is_dtd variable to be set to determine
                        how to validate the AI manifest.
        Postconditions: Sets AI_root on success to a XML DOM of the AI
                        manifest.
        Raises: IOError on file open error.
                ValueError on validation error.
        """
        schema = file(self.AI_schema, 'r')

        try:
            xml_data = file(self.manifest_path, 'r')
        except AssertionError:
            # manifest path will be unset if we're not using a separate file
            # for A/I manifest so we must emulate a file
            xml_data = StringIO.StringIO(lxml.etree.tostring(self.AI_root))

        if self.is_dtd:
            self.AI_root, errors = verifyXML.verifyDTDManifest(self.AI_schema,
                                                                xml_data)

            if errors:
                err = '\n'.join(errors)
                raise ValueError(_("Error: AI manifest failed validation:\n%s")
                                 % err)

            ai_instance = self.AI_root.find(".//ai_instance")

        else:
            self.AI_root, errors = verifyXML.verifyRelaxNGManifest(schema,
                                                                    xml_data)

            if errors:
                # catch if we are not using a manifest we can name with
                # manifest_path
                try:
                    # manifest_path is a property that may raise an
                    # AssertionError
                    man_path = self.manifest_path
                    raise ValueError(_("Error:\tFile %s failed validation:"
                                 "\n\t%s") %
                                 (os.path.basename(man_path),
                                  errors.message))
                # manifest_path will throw an AssertionError if it does not
                # have a path use a different error message
                except AssertionError:
                    raise ValueError(_("Error: AI manifest failed validation:"
                                   "\n\t%s") % errors.message)

            # Replace the <ai_manifest_file> element (if one exists) with an
            # <ai_embedded_manifest> element, using content from its referenced
            # file which was just loaded into the AI_root XML DOM
            ai_manifest_file = self.criteria_root.find(".//ai_manifest_file")

            if ai_manifest_file is not None:
                new_ai = lxml.etree.Element("ai_embedded_manifest")
                # add newlines to separate ai_embedded_manifest
                # from children
                new_ai.text = "\n\t"
                new_ai.tail = "\n"
                self.AI_root.getroot().tail = "\n"
                new_ai.append(self.AI_root.getroot())

                ai_manifest_file.getparent().replace(ai_manifest_file, new_ai)

            ai_instance = self.criteria_root.find(".//ai_manifest")

        # Set/update the name inside the DOM
        ai_instance.set("name", self.manifest_name)

    def verify_SC_manifest(self, data, name=None):
        """
        Used for verifying and loading SC manifest
        Args:    data - file path, or StringIO object.
                 name - Optionally, takes a name to provide error output,
                        as a StringIO object will not have a file path to
                        provide.
        Returns: Provide an XML DOM for the SC manifest
        Raises:  SystemExit on validation or file open error.
        """
        if not isinstance(data, StringIO.StringIO):
            try:
                data = file(data, 'r')
            except IOError:
                if name is None:
                    raise SystemExit(_("Error:\tCan not open: %s") % data)
                else:
                    raise SystemExit(_("Error:\tCan not open: %s") % name)
        xml_root, errors = verifyXML.verifyDTDManifest(self.smfDtd, data)
        if errors:
            if not isinstance(data, StringIO.StringIO):
                print >> sys.stderr, (_("Error:\tFile %s failed validation:") %
                                      data.name)
            else:
                print >> sys.stderr, (_("Error:\tSC Manifest %s failed "
                                        "validation:") % name)
            for err in xml_root:
                print >> sys.stderr, err
            raise SystemExit()
        return(xml_root)

    @classmethod
    def manifest_is_a_script(cls, manifest_filepath):
        """
        Returns True if given manifest is supported by Derived Manifests.

        Raises a SystemExit exception if an unsupported script type is found.
        """
        manifest_fobj = open(manifest_filepath)
        first_line = manifest_fobj.readline()
        manifest_fobj.close()
        if first_line.startswith("#!"):
            if (first_line.find(KSH93_SHEBANG) == -1 and
                first_line.find(PYTHON_SHEBANG) == -1):
                print >> sys.stderr, "Unsupported script format.  " \
                    "Python and ksh93 scripts are supported."
                raise SystemExit(errno.EINVAL)
            return True
        return False

    def set_criteria_root(self, root=None):
        """
        Used to set criteria_root DOM with the criteria from the passed
        in root DOM.  If criteria_root already exists, overwrite its
        <ai_criteria> elements with the criteria found in root.  If
        criteria_root doesn't already exist, simply set the root DOM
        passed in as criteria_root.

        Args: root - A DOM for a criteria manifest
        Postconditions: criteria_root will be set with a criteria manifest
                        DOM, or have its <ai_criteria> elements replaced with
                        the criteria from the root DOM passed in.
        """

        # If the criteria_root is not yet set, set it to the root
        # DOM passed in.
        if self.criteria_root is None:
            self.criteria_root = root

        # Else criteria_root already exists (because this is being
        # called with an older install service where the manifest input
        # is a combined Criteria manifest), use the criteria specified
        # in 'root' to overwrite any criteria in criteria_root.
        else:
            # Remove all <ai_criteria> elements if they exist.
            removed_criteria = False
            path = '/ai_criteria_manifest/ai_criteria'
            for tag in self.criteria_root.xpath(path):
                removed_criteria = True
                tag.getparent().remove(tag)

            # If we removed a criteria from criteria_root, this means
            # criteria was also specified in a combined Criteria manifest.
            # Warn user that those will be ignored, and criteria specified
            # on the command line via -c or -C override those.
            if removed_criteria:
                print("Warning: criteria specified in multiple places.\n"
                      "  Ignoring criteria from combined Criteria manifest "
                      "file.\n")

            # Append all criteria from the new criteria root.
            ai_criteria = root.iterfind(".//ai_criteria")

            self.criteria_root.getroot().extend(ai_criteria)


def do_publish_manifest(cmd_options=None):
    '''
    Publish a manifest, associating it with an install service.

    '''
    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tRoot privileges are required for "
                           "this command."))

    # load in all the options and file data.  Validate proper manifests.
    data = parse_options(DO_ADD, cmd_options)

    # Disallow multiple manifests or scripts with the same mname.
    if os.path.exists(data.stored_manifest_path):
        raise SystemExit(_("Error:\tName %s is already registered with "
                           "this service.") % data.manifest_name)

    # if criteria are provided, make sure they are a unique set.
    if data.criteria:
        find_colliding_manifests(data.criteria, data.database,
            find_colliding_criteria(data.criteria, data.database))

    # Add all manifests to the database, whether default or not, and whether
    # they have criteria or not.
    insert_SQL(data)

    # move the manifest into place
    place_manifest(data)

    # if we have a default manifest do default manifest handling
    if data.set_as_default:
        set_default(data.service_name, data.manifest_name)


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

    if not os.path.exists(data.stored_manifest_path):
        raise SystemExit(_("Error:\tNo manifest or script with name "
                           "%s is registered with this service.\n"
                           "\tPlease use installadm add-manifest instead.") %
                           data.manifest_name)

    # move the manifest into place
    place_manifest(data)


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_publish_manifest()

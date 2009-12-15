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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
"""

A/I Publish_Manifest

"""

import os.path
import sys
import StringIO
import gettext
import lxml.etree
import hashlib
from optparse import OptionParser

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.verifyXML as verifyXML
import osol_install.libaiscf as smf

INFINITY = str(0xFFFFFFFFFFFFFFFF)
IMG_AI_MANIFEST_SCHEMA = "/auto_install/ai_manifest.rng"
SYS_AI_MANIFEST_SCHEMA = "/usr/share/auto_install/ai_manifest.rng"

def parse_options():
    """
    Parse and validate options
    Args: None
    Returns: the DataFiles object populated and initialized
    Raises: The DataFiles initialization of manifest(s) A/I, SC, SMF looks for
            many error conditions and, when caught, are flagged to the user
            via raising SystemExit exceptions.
    """

    usage = _("usage: %prog service_name criteria_manifest")
    parser = OptionParser(usage=usage)
    # since no options are specified simply retrieve the args list
    # args should be a list with indices:
    # 0 - service name
    # 1 - manifest path to work with
    args = parser.parse_args()[1]

    # check that we got the install service's name and
    # a criteria manifest
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    # get an AIservice object for requested service
    try:
        svc = smf.AIservice(smf.AISCF(FMRI="system/install/server"), args[0])
    except KeyError:
        raise SystemExit(_("Error:\tFailed to find service %s") % args[0])

    # argument two is the criteria manifest
    crit_manifest = args[1]

    # get the service's data directory path and imagepath
    try:
        image_path = svc['image_path']
        # txt_record is of the form "aiwebserver=jumprope:46503" so split on ":"
        # and take the trailing portion for the port number
        port = svc['txt_record'].rsplit(':')[-1]
    except KeyError:
        raise SystemExit(_("SMF data for service %s is corrupt.\n") %
                         args[0])
    service_dir = os.path.abspath("/var/ai/" + port)

    # check that the service and imagepath directories exist,
    # and the AI.db, criteria_schema.rng and ai_manifest.rng files
    # are present otherwise the service is misconfigured
    if not (os.path.isdir(service_dir) and
            os.path.exists(os.path.join(service_dir, "AI.db"))):
        raise SystemExit("Error:\tNeed a valid A/I service directory")

    files = DataFiles(service_dir = service_dir, image_path = image_path,
                      database_path = os.path.join(service_dir, "AI.db"),
                      criteria_path = crit_manifest)

    return(files)

def find_colliding_criteria(files):
    """
    Returns: A dictionary of colliding criteria with keys being manifest name
             and instance tuples and values being the DB column names which
             collided
    Args: DataFiles object with a valid _criteria_root and database object
    Raises: SystemExit if: criteria is not found in database
                           value is not valid for type (integer and hexadecimal
                             checks)
                           range is improper
    """
    # define convenience strings:
    class fields(object):
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
    for crit in files.criteria:
        # gather this criteria's values from the manifest
        man_criterion = files.criteria[crit]

        # check "value" criteria here (check the criteria exists in DB, and
        # then find collisions)
        if not isinstance(man_criterion, list):
            # only check criteria in use in the DB
            if crit not in AIdb.getCriteria(files.database.getQueue(),
                                            onlyUsed=False, strip=False):
                raise SystemExit(_("Error:\tCriteria %s is not a " +
                                   "valid criteria!") % crit)

            # get all values in the database for this criteria (and
            # manifest/instance paris for each value)
            db_criteria = AIdb.getSpecificCriteria(
                files.database.getQueue(), crit, None,
                provideManNameAndInstance=True)

            # will iterate over a list of the form [manName, manInst, crit,
            # None]
            for row in db_criteria:
                # check if the database and manifest values differ
                if(str(row[fields.CRIT]).lower() == str(man_criterion).lower()):
                    # record manifest name, instance and criteria name
                    try:
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] += crit + ","
                    except KeyError:
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] = crit + ","

        # This is a range criteria.  (Check that ranges are valid, that
        # "unbounded" gets set to 0/+inf, ensure the criteria exists
        # in the DB, then look for collisions.)
        else:
            # check for a properly ordered range (with unbounded being 0 or
            # Inf.) but ensure both are not unbounded
            if(
               # Check for a range of -inf to inf -- not a valid range
               (man_criterion[0] == "unbounded" and
                man_criterion[1] == "unbounded"
               ) or
               # Check min > max -- range order reversed
               (
                (man_criterion[0] != "unbounded" and
                 man_criterion[1] != "unbounded"
                ) and
                (man_criterion[0] > man_criterion[1])
               )
              ):
                raise SystemExit(_("Error:\tCriteria %s "
                                   "is not a valid range (MIN > MAX) or "
                                   "(MIN and MAX unbounded).") % crit)

            # Clean-up NULL's and changed "unbounded"s to 0 and
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

            # check to see that this criteria exists in the database columns
            if ('MIN' + crit not in AIdb.getCriteria(
                files.database.getQueue(), onlyUsed=False, strip=False))\
            and ('MAX' + crit not in AIdb.getCriteria(
                files.database.getQueue(), onlyUsed=False,  strip=False)):
                raise SystemExit(_("Error:\tCriteria %s is not a " +
                                   "valid criteria!") % crit)
            db_criteria = AIdb.getSpecificCriteria(
                files.database.getQueue(), 'MIN' + crit, 'MAX' + crit,
                provideManNameAndInstance=True)

            # will iterate over a list of the form [manName, manInst, mincrit,
            # maxcrit]
            for row in db_criteria:
                # arbitrarily large number in case this Python does
                # not support IEEE754
                db_criterion = ["0", INFINITY]

                # now populate in valid database values (i.e. non-NULL values)
                if row[fields.MINCRIT]:
                    db_criterion[0] = row[fields.MINCRIT]
                if row[fields.MAXCRIT]:
                    db_criterion[1] = row[fields.MAXCRIT]
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
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] += "MIN" + crit + ","
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] += "MAX" + crit + ","
                    except KeyError:
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] = "MIN" + crit + ","
                        collisions[row[fields.MANNAME],
                                   row[fields.MANINST]] += "MAX" + crit + ","
    return collisions

def find_colliding_manifests(files, collisions):
    """
    For each manifest/instance pair in collisions check that the manifest
    criteria diverge (i.e. are not exactly the same) and that the ranges do not
    collide for ranges.
    Raises if: a range collides, or if the manifest has the same criteria as a
    manifest already in the database (SystemExit raised)
    Returns: Nothing
    Args: files - DataFiles object with vaild _criteria_root and database
                  object
          collisions - a dictionary with collisions, as produced by
                       find_colliding_criteria()
    """
    # check every manifest in collisions to see if manifest collides (either
    # identical criteria, or overlaping ranges)
    for man_inst in collisions:
        # get all criteria from this manifest/instance pair
        db_criteria = AIdb.getManifestCriteria(man_inst[0],
                                               man_inst[1],
                                               files.database.getQueue(),
                                               humanOutput=True,
                                               onlyUsed=False)

        # iterate over every criteria in the database
        for crit in AIdb.getCriteria(files.database.getQueue(),
                                     onlyUsed=False, strip=False):

            # Get the criteria name (i.e. no MIN or MAX)
            crit_name = crit.replace('MIN', '', 1).replace('MAX', '', 1)
            # Set man_criterion to the key of the DB criteria or None
            man_criterion = files.criteria[crit_name]
            if man_criterion and crit.startswith('MIN'):
                man_criterion = man_criterion[0]
            elif man_criterion and crit.startswith('MAX'):
                man_criterion = man_criterion[1]

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
                if (str(db_criterion).lower() != str(man_criterion).lower()):
                    raise SystemExit(_("Error:\tManifest has a range "
                                       "collision with manifest:%s/%i"
                                       "\n\tin criteria: %s!") %
                                     (man_inst[0], man_inst[1],
                                      crit.replace('MIN', '', 1).
                                      replace('MAX', '', 1)))

            # the range did not collide or this is a single value (if we
            # differ we can break out knowing we diverge for this
            # manifest/instance)
            elif(str(db_criterion).lower() != str(man_criterion).lower()):
                # manifests diverge (they don't collide)
                break

        # end of for loop and we never broke out (diverged)
        else:
            raise SystemExit(_("Error:\tManifest has same criteria as " +
                               "manifest:%s/%i!") %
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
    # check to see if manifest name is alreay in database (affects instance
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

        # if the values are a list this is a range
        if isinstance(values, list):
            for value in values:
                # translate "unbounded" to a database NULL
                if value == "unbounded":
                    query += "NULL,"
                # we need to deal with mac addresses specially being
                # hexadecimal
                elif crit.endswith("mac"):
                    # need to insert with hex operand x'<val>'
                    # use an upper case string for hex values
                    query += "x'" + AIdb.sanitizeSQL(str(value).upper())+"',"
                else:
                    query += AIdb.sanitizeSQL(str(value).upper()) + ","

        # this is a single criteria (not a range)
        elif isinstance(values, basestring):
            # translate "unbounded" to a database NULL
            if values == "unbounded":
                query += "NULL,"
            else:
                # use lower case for text strings
                query += "'" + AIdb.sanitizeSQL(str(values).lower()) + "',"

        # the critera manifest didn't specify this criteria so fill in NULLs
        else:
            # use the criteria name to determine if this is a range
            if crit.startswith('MAX'):
                query += "NULL,NULL,"
            # this is a single value
            else:
                query += "NULL,"

    # strip trailing comma and close parentheses
    query = query[:-1] + ")"

    # update the database
    query = AIdb.DBrequest(query, commit=True)
    files.database.getQueue().put(query)
    query.waitAns()
    # in case there's an error call the response function (which will print the
    # error)
    query.getResponse()

def do_default(files):
    """
    Removes old default.xml after ensuring proper format of new manifest
    (does not copy new manifest over -- see place_manifest)
    Args: None
    Returns: None
    Raises if: Manifest has criteria, old manifest can not be removed (exits
               with SystemExit)
    """
    # check to see if any criteria is present -- if so, it can not be a default
    # manifest (as they do not have criteria)
    if files.criteria:
        raise SystemExit(_("Error:\tCan not use AI criteria in a default " +
                           "manifest"))
    # remove old manifest
    try:
        os.remove(os.path.join(files.get_service(), 'AI_data', 'default.xml'))
    except IOError, e:
        raise SystemExit(_("Error:\tUnable to remove default.xml:\n\t%s") % e)

def place_manifest(files):
    """
    Compares src and dst manifests to ensure they are the same; if manifest
    does not yet exist, copies new manifest into place and sets correct
    permissions and ownership
    Args: None
    Returns: None
    Raises if: src and dst manifests differ (in MD5 sum), unable to write dst
               manifest (raises SystemExit -- no clean up of database performed)
    """
    manifest_path = os.path.join(files.get_service(), "AI_data",
                                files.manifest_name)

    # if the manifest already exists see if it is different from what was
    # passed in. If so, warn the user that we're using the existing manifest
    if os.path.exists(manifest_path):
        old_manifest = open(manifest_path, "r")
        existing_MD5 = hashlib.md5("".join(old_manifest.readlines())).digest()
        old_manifest.close()
        current_MD5 = hashlib.md5(lxml.etree.tostring(files._AI_root,
                                 pretty_print=True, encoding=unicode)).digest()
        if existing_MD5 != current_MD5:
            raise SystemExit(_("Error:\tNot copying manifest, source and " +
                               "current versions differ -- criteria in place."))

    # the manifest does not yet exist so write it out
    else:
        try:
            new_man = open(manifest_path, "w")
            new_man.writelines('<ai_criteria_manifest>\n')
            new_man.writelines('\t<ai_embedded_manifest>\n')
            new_man.writelines(lxml.etree.tostring(
                                   files._AI_root, pretty_print=True,
                                   encoding=unicode))
            new_man.writelines('\t</ai_embedded_manifest>\n')
            # write out each SMF SC manifest
            for key in files._smfDict:
                new_man.writelines('\t<sc_embedded_manifest name = "%s">\n'%
                                       key)
                new_man.writelines("\t\t<!-- ")
                new_man.writelines("<?xml version='1.0'?>\n")
                new_man.writelines(lxml.etree.tostring(files._smfDict[key],
                                       pretty_print=True, encoding=unicode))
                new_man.writelines('\t -->\n')
                new_man.writelines('\t</sc_embedded_manifest>\n')
            new_man.writelines('\t</ai_criteria_manifest>\n')
            new_man.close()
        except IOError, e:
            raise SystemExit(_("Error:\tUnable to write to dest. "
                               "manifest:\n\t%s") % e)

    # change read for all and write for owner
    os.chmod(manifest_path, 0644)
    # change to user/group root (uid/gid 0)
    os.chown(manifest_path, 0, 0)

class DataFiles(object):
    """
    Class to contain and work with data files necessary for program
    """
    # schema for validating an AI criteria manifest
    criteriaSchema = "/usr/share/auto_install/criteria_schema.rng"
    # DTD for validating an SMF SC manifest
    smfDtd = "/usr/share/lib/xml/dtd/service_bundle.dtd.1"


    def __init__(self, service_dir = None, image_path = None,
                 database_path = None, criteria_path = None):
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

        #
        # File system path variables
        ############################
        #

        # Check AI Criteria Schema exists
        if not os.path.exists(self.criteriaSchema):
            raise SystemExit(_("Error:\tUnable to find criteria_schema: " +
                               "%s") % self.criteriaSchema)

        # Check SC manifest SMF DTD exists
        if not os.path.exists(self.smfDtd):
            raise SystemExit(_("Error:\tUnable to find SMF system " +
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

        #
        # XML DOM variables
        ###################
        #

        #
        # Criteria manifest setup
        #

        # Holds DOM for criteria manifest
        self._criteria_root = None

        # Holds path for criteria manifest
        self.criteria_path = criteria_path
        # find SC manifests from the criteria manifest and validate according
        # to the SMF DTD (exit if errors)
        if criteria_path:
            # sets _criteria_root DOM
            self.verifyCriteria()

        #
        # SC manifest setup
        #

        # Holds DOMs for SC manifests
        self._smfDict = dict()

        # if we were provided a criteria manifest, look for a SC manifests
        # specified by the criteria manifest
        if self._criteria_root:
            # sets _smfDict DOMs
            self.find_SC_from_crit_man()

        #
        # AI manifest setup
        #

        # Holds DOM for AI manifest
        self._AI_root = None

        # Holds path to AI manifest being published (may not be set if an
        # embedded manifest)
        self._manifest = None

        # if we were provided a criteria manifest, look for an A/I manifest
        # specified by the criteria manifest
        if self._criteria_root:
            # this will set _manifest to be the AI manifest path (if a file),
            # set _AI_root to the correct location in the criteria DOM (if
            # embedded), or exit (if unable to find an AI manifest)
            self.find_AI_from_criteria()
            # this will verify the _AI_root DOM and exit on error
            self.verify_AI_manifest()

    # overload the _criteria class to be a list with a special get_item to act
    # like a dictionary
    class _criteria(list):
        """
        Wrap list class to provide lookups in the criteria file when
        requested
        """
        def __init__(self, criteria_root):
            # store the criteria manifest DOM root
            self._criteria_root = criteria_root
            # call the _init_() for the list class with a generator provided by
            # find_criteria() to populate this _criteria() instance.
            super(DataFiles._criteria, self).__init__(self.find_criteria())

        def __getitem__(self, key):
            """
            Look up a requested criteria (akin to dictionary access) but for an
            uninitialized key will not raise an exception but return None)
            """
            return self.get_criterion(key)

        def find_criteria(self):
            """
            Find criteria from the criteria manifest
            Returns: A generator providing all criteria name attributes from
                     <ai_criteria> tags
            """
            root = self._criteria_root.findall(".//ai_criteria")

            # actually find criteria
            for tag in root:
                for child in tag.getchildren():
                    if (child.tag == "range" or child.tag == "value") and \
                        child.text is not None:
                        # criteria names are lower case
                        yield tag.attrib['name'].lower()
                    # should not happen according to schema
                    else:
                        raise AssertionError(_(
                            "Criteria contains no values"))

        def get_criterion(self, criterion):
            """
            Return criterion out of the criteria manifest
            Returns: A list for range criterion with a min and max entry
                     A string for value criterion
            """
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
                            raise AssertionError(_(
                                "Criteria contains no values"))
            return None

        # disable trying to update criteria
        __setitem__ = None
        __delitem__ = None

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
            self._criteria_cache = self._criteria(self._criteria_root)
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
            return(self._db)
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
                               "directory") % db_file)
        elif self._service is None:
            self._service = os.path.abspath(serv)
        else:
            raise AssertionError('Setting service when already set!')

    service = property(get_service, set_service, None,
                       "Holds path to service directory (i.e. /var/ai/46501)")

    def find_SC_from_crit_man(self):
        """
        Find SC manifests as referenced in the criteria manifest
        Preconditions: self._criteria_root is a valid XML DOM
        Postconditions: self._smfDict will be a dictionary containing all
                        SC manifest DOMs
        Raises: SystemExit for XML processing errors
                           for two SC manifests named the same
                AssertionError if _critteria_root not set
        Args: None
        Returns: None
        """
        if self._criteria_root is None:
            raise AssertionError(_("Error:\t _criteria_root not set!"))
        try:
            root = self._criteria_root.iterfind(".//sc_manifest_file")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        # for each SC manifest file: get the URI and verify it, adding it to the
        # dictionary of SMF SC manifests (this means we can support a criteria
        # manifest with multiple SC manifests embedded or referenced)
        for SC_man in root:
            if SC_man.attrib['name'] in self._smfDict:
                raise SystemExit(_("Error:\tTwo SC manfiests with name %s") %
                                   SC_man.attrib['name'])
            # if this is an absolute path just hand it off
            if os.path.isabs(str(SC_man.attrib['URI'])):
                self._smfDict[SC_man.attrib['name']] = \
                    self.verify_SC_manifest(SC_man.attrib['URI'])
            # this is not an absolute path - make it one
            else:
                self._smfDict[SC_man.attrib['name']] = \
                    self.verify_SC_manifest(os.path.join(os.path.dirname(
                                          self.criteria_path),
                                          SC_man.attrib['URI']))
        try:
            root = self._criteria_root.iterfind(".//sc_embedded_manifest")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        # for each SC manifest embedded: verify it, adding it to the
        # dictionary of SMF SC manifests
        for SC_man in root:
            # strip the comments off the SC manifest
            xml_data = lxml.etree.tostring(SC_man.getchildren()[0])
            xml_data = xml_data.replace("<!-- ", "").replace(" -->", "")
            xml_data = StringIO.StringIO(xml_data)
            # parse and read in the SC manifest
            self._smfDict[SC_man.attrib['name']] = \
                self.verify_SC_manifest(xml_data, name=SC_man.attrib['name'])

    def find_AI_from_criteria(self):
        """
        Find A/I manifest as referenced or embedded in criteria manifest
        Preconditions: self._criteria_root is a valid XML DOM
        Postconditions: self.manifest_path will be set if using a free-standing
                        AI manifest otherwise self._AI_root will eb set to a
                        valid XML DOM for the AI manifest
        Raises: SystemExit for XML processing errors
                           for no ai_manifest_file specification
                AssertionError if _critteria_root not set
        """
        if self._criteria_root is None:
            raise AssertionError(_("Error:\t_criteria_root not set!"))
        try:
            root = self._criteria_root.find(".//ai_manifest_file")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        if not isinstance(root, lxml.etree._Element):
            try:
                root = self._criteria_root.find(".//ai_embedded_manifest")
            except lxml.etree.LxmlError, e:
                raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
            if not isinstance(root, lxml.etree._Element):
                raise SystemExit(_("Error:\tNo <ai_manifest_file> or " +
                                   "<ai_embedded_manifest> element in "
                                   "criteria manifest."))
        try:
            root.attrib['URI']
        except KeyError:
            self._AI_root = \
                lxml.etree.tostring(root.find(".//ai_manifest"))
            return
        if os.path.isabs(root.attrib['URI']):
            self.manifest_path = root.attrib['URI']
        else:
            # if we do not have an absolute path try using the criteria
            # manifest's location for a base
            self.manifest_path = \
                os.path.join(os.path.dirname(self.criteria_path),
                             root.attrib['URI'])
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
                                       IMG_AI_MANIFEST_SCHEMA)):
            self._AIschema = os.path.join(self.image_path,
                                          IMG_AI_MANIFEST_SCHEMA)
        else:
            if os.path.exists(SYS_AI_MANIFEST_SCHEMA):
                self._AIschema = SYS_AI_MANIFEST_SCHEMA
                print (_("Warning: Using A/I manifest schema <%s>\n") %
                        self._AIschema)
            else:
                raise SystemExit(_("Error:\tUnable to find an A/I schema!"))

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
        Returns: manifest name as defined in the A/I manifest (ensuring .xml is
                 applied to the string)
        Raises: SystemExit if <ai_manifest> tag can not be found
        """
        if self._AI_root.getroot().tag == "ai_manifest":
            name = self._AI_root.getroot().attrib['name']
        else:
            raise SystemExit(_("Error:\tCan not find <ai_manifest> tag!"))
        # everywhere we expect manifest names to be file names so ensure
        # the name matches
        if not name.endswith('.xml'):
            name += ".xml"
        return name

    def verify_AI_manifest(self):
        """
        Used for verifying and loading AI manifest as defined by
            DataFiles._AIschema.
        Args: None.
        Postconditions: Sets DataFiles._AI_root on success to a XML DOM
        Raises: SystemExit on file open error or validation error.
        """
        try:
            schema = file(self.AI_schema, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s ") %
                               self.AI_schema)
        try:
            xml_data = file(self.manifest_path, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s ") %
                               self.manifest_path)
        except AssertionError:
            # manifest path will be unset if we're not using a separate file for
            # A/I manifest so we must emulate a file
            xml_data = StringIO.StringIO(self._AI_root)
        self._AI_root = verifyXML.verifyRelaxNGManifest(schema, xml_data)
        if isinstance(self._AI_root, lxml.etree._LogEntry):
            # catch if we area not using a manifest we can name with
            # manifest_path
            try:
                raise SystemExit(_("Error:\tFile %s failed validation:\n\t%s") %
                                 (os.path.basename(self.manifest_path),
                                  self._AI_root.message))
            # manifest_path will throw an AssertionError if it does not have
            # a path use a different error message
            except AssertionError:
                raise SystemExit(_("Error:\tA/I manifest failed validation:"
                                   "\n\t%s") % self._AI_root.message)


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
        xml_root = verifyXML.verifyDTDManifest(data, self.smfDtd)
        if isinstance(xml_root, list):
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

    def verifyCriteria(self):
        """
        Used for verifying and loading criteria XML
        Raises SystemExit:
        *if the schema does not open
        *if the XML file does not open
        *if the XML is invalid according to the schema
        Postconditions: self._criteria_root is a valid XML DOM of the criteria
                        manifest and all MAC and IPv4 values are formatted
                        according to verifyXML.prepValuesAndRanges()
        """
        try:
            schema = file(self.criteriaSchema, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s") %
                             self.criteriaSchema)
        try:
            file(self.criteria_path, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s") % self.criteria_path)
        self._criteria_root = (verifyXML.verifyRelaxNGManifest(schema,
                              self.criteria_path))
        if isinstance(self._criteria_root, lxml.etree._LogEntry):
            raise SystemExit(_("Error:\tFile %s failed validation:\n\t%s") %
                             (self.criteria_path, self._criteria_root.message))
        verifyXML.prepValuesAndRanges(self._criteria_root,
                                      self.database)


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tNeed root privileges to run"))

    # load in all the options and file data
    data = parse_options()

    # if we have a default manifest do default manifest handling
    if data.manifest_name == "default.xml":
        do_default(data)

    # if we have a non-default manifest first ensure it is a unique criteria
    # set and then, if unique, add the manifest to the criteria database
    else:
        # if we have a None criteria from the criteria list then the manifest
        # has no criteria which is illegal for a non-default manifest
        if not data.criteria:
            raise SystemExit(_("Error:\tNo criteria found " +
                               "in non-default manifest -- "
                               "at least one criterion needed!"))
        find_colliding_manifests(data, find_colliding_criteria(data))
        insert_SQL(data)

    # move the manifest into place
    place_manifest(data)

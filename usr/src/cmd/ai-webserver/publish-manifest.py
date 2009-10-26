#!/usr/bin/python2.4
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

A/I Publish_Manifest Prototype

"""

import os.path
import sys
import StringIO
import gettext
import lxml.etree
import md5
from optparse import OptionParser
from pysqlite2 import dbapi2 as sqlite
from threading import Thread

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.verifyXML as verifyXML

INFINITY = str(0xFFFFFFFFFFFFFFFF)
IMG_AI_MANIFEST_SCHEMA = "/auto_install/ai_manifest.rng"
SYS_AI_MANIFEST_SCHEMA = "/usr/share/auto_install/ai_manifest.rng"

def parseOptions(files):
    """
    Parse and validate options
    Args: a dataFiles object
    Returns: nothing -- but the dataFiles object is populated  (with the
    manifest(s) A/I, SC, SMF and many error conditions are caught and flagged
    to the user via raising SystemExit exceptions.
    """

    usage = _("usage: %prog [options] service_directory")
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--criteria", dest="criteria",
                      metavar="criteria.xml", type="string", nargs=1,
                      help=_("provide criteria manifest file (not " +
                      "applicable to default manifests)"))
    parser.add_option("-a", "--aimanifest", dest="ai",
                      metavar="AImanifest.xml", type="string", nargs=1,
                      help=_("provide A/I manifest file"))
    parser.add_option("-s", "--sysconfig", dest="sysconfig",
                      metavar="SC.xml", type="string", nargs=1,
                      help=_("provide system configuration manifest file"))
    (options, args) = parser.parse_args()

    # check that we got the install service's data directory and
    # the install service's target imagepath passed in as arguments.
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    # we need at least an A/I manifest or a criteria manifest
    elif not options.ai and not options.criteria:
        parser.print_help()
        raise SystemExit(_("Error:\tNeed an A/I manifest or criteria " +
                           "manifest specifying one."))

    # set the service's data directory path and the imagepath
    files.setService(args[0])
    files.setImagePath(args[1])

    # Now that the imagepath is set, set the AIschema
    files.setAIschema()

    # check that the service's data and imagepath directories exist,
    # and the AI.db, criteria_schema.rng and ai_manifest.rng files
    # are present otherwise the service is misconfigured
    if not (os.path.isdir(files.getService()) and
            os.path.exists(os.path.join(files.getService(), "AI.db"))):
        raise SystemExit("Error:\tNeed a valid A/I service directory")
    if not (os.path.isdir(files.getImagePath())):
        raise SystemExit(_("Error:\tInvalid A/I imagepath " +
                           "directory: %s") % files.getImagePath())
    if not (os.path.exists(files.criteriaSchema)):
        raise SystemExit(_("Error:\tUnable to find criteria_schema: " +
                           "%s") % files.criteriaSchema)
    if not (os.path.exists(files.getAIschema())):
        raise SystemExit(_("Error:\tUnable to find A/I schema: " +
                           "%s") % files.getAIschema())

    # load the database (exits if there are errors)
    files.openDatabase(os.path.join(files.getService(), "AI.db"))

    # verify the database's table/column structure (or exit if errors)
    files.getDatabase().verifyDBStructure()
    if options.criteria:
        # validate the criteria manifest is valid according to the schema
        # (exit if errors)
        files.verifyCriteria(options.criteria)

    # if we have an A/I manifest (from the command line)
    if options.ai:
        # set the manifest path
        files.setManifestPath(options.ai)

        # validate the A/I manifest against its schema (exits if errors)
        files.verifyAImanifest()

    # we do not have an A/I manifest from the command line
    else:
        # look for an A/I manifest specified by the criteria manifest
        files.findAIfromCriteria()
        files.verifyAImanifest()

    # load the commandline SC manifest
    if options.sysconfig:
        # validate the SC manifest and add the LXML root to the dictionary of
        # SMF SC manifests (exits if there are errors)
        files._smfDict['commandLine'] = \
            files.verifySCmanifest(options.sysconfig)

    # load SC manifests refrenced by the criteria manifest (will validate too)
    if options.criteria:
        files.findSCfromCriteria()

def findCollidingCriteria(files):
    """
    Compare manifest criteria with criteria in database. Records collisions in
    a dictionary and returns the dictionary
    Exits if: a range is invalid, or if the manifest has a criteria not defined
    in the database
    """
    # collisions is a dictionary to hold keys of the form (manifest name,
    # instance) which will point to a comma-separated string of colliding
    # criteria
    collisions = dict()

    # verify each range criteria in the manifest is well formed and collect
    # collisions with database entries
    for crit in files.findCriteria():
        # gather this criteria's values from the manifest
        manifestCriteria = files.getCriteria(crit)

        # check "value" criteria here (check the criteria exists in DB, and
        # then find collisions)
        if not isinstance(manifestCriteria, list):
            # only check criteria in use in the DB
            if crit not in AIdb.getCriteria(files.getDatabase().getQueue(),
                                            onlyUsed=False, strip=False):
                raise SystemExit(_("Error:\tCriteria %s is not a " +
                                   "valid criteria!") % crit)

            # get all values in the database for this criteria (and
            # manifest/instance paris for each value)
            dbCriteria = AIdb.getSpecificCriteria(
                files.getDatabase().getQueue(), crit, None,
                provideManNameAndInstance=True)

            # will iterate over a list of the form [manName, manInst, crit,
            # None]
            for row in dbCriteria:
                # check if the database and manifest values differ
                if(str(row[2]).lower() == str(manifestCriteria).lower()):
                    # record manifest name, instance and criteria name
                    try:
                        collisions[row[0], row[1]] += crit + ","
                    except KeyError:
                        collisions[row[0], row[1]] = crit + ","

        # This is a range criteria.  (Check that ranges are valid, that
        # "unbounded" gets set to 0/+inf, ensure the criteria exists
        # in the DB, then look for collisions.)
        else:
            # check for a properly ordered range (with unbounded being 0 or
            # Inf.) but ensure both are not unbounded
            if(
               # Check for a range of -inf to inf -- not a valid range
               (manifestCriteria[0] == "unbounded" and
                manifestCriteria[1] == "unbounded"
               ) or
               # Check min > max -- range order reversed
               (
                (manifestCriteria[0] != "unbounded" and
                 manifestCriteria[1] != "unbounded"
                ) and
                (manifestCriteria[0] > manifestCriteria[1])
               )
              ):
                raise SystemExit(_("Error:\tCriteria %s "
                                   "is not a valid range (MIN > MAX) or "
                                   "(MIN and MAX unbounded).") % crit)

            # Clean-up NULL's and changed "unbounded"s to 0 and
            # really large numbers in case this Python does
            # not support IEEE754.  Note "unbounded"s are already
            # converted to lower case during manifest processing.
            if manifestCriteria[0] == "unbounded":
                manifestCriteria[0] = "0"
            if manifestCriteria[1] == "unbounded":
                manifestCriteria[1] = INFINITY
            if crit == "mac":
                # convert hex mac address (w/o colons) to a number
                try:
                    manifestCriteria[0] = \
                        long(str(manifestCriteria[0]).upper(), 16)
                    manifestCriteria[1] = \
                        long(str(manifestCriteria[1]).upper(), 16)
                except ValueError:
                    raise SystemExit(_("Error:\tCriteria %s "
                                       "is not a valid hexadecimal value") % crit)

            else:
                # this is a decimal value
                try:
                    manifestCriteria = [long(str(manifestCriteria[0]).upper()),
                                        long(str(manifestCriteria[1]).upper())]
                except ValueError:
                    raise SystemExit(_("Error:\tCriteria %s "
                                       "is not a valid integer value") % crit)

            # check to see that this criteria exists in the database columns
            if ('MIN' + crit not in AIdb.getCriteria(
                                                    files.getDatabase().getQueue(),
                                                    onlyUsed=False, strip=False)) \
            and ('MAX' + crit not in AIdb.getCriteria(
                                                    files.getDatabase().getQueue(),
                                                    onlyUsed=False,  strip=False)):
                raise SystemExit(_("Error:\tCriteria %s is not a " +
                                   "valid criteria!") % crit)
            dbCriteria = AIdb.getSpecificCriteria(
                files.getDatabase().getQueue(), 'MIN' + crit, 'MAX' + crit,
                provideManNameAndInstance=True)

            # will iterate over a list of the form [manName, manInst, mincrit,
            # maxcrit]
            for row in dbCriteria:
                # arbitrarily large number in case this Python does
                # not support IEEE754
                dbCrit = ["0", INFINITY]

                # now populate in valid database values (i.e. non-NULL values)
                if row[2]:
                    dbCrit[0] = row[2]
                if row[3]:
                    dbCrit[1] = row[3]
                if crit == "mac":
                    # use a hexadecimal conversion
                    dbCrit = [long(str(dbCrit[0]), 16),long(str(dbCrit[1]), 16)]
                else:
                    # these are decimal numbers
                    dbCrit = [long(str(dbCrit[0])), long(str(dbCrit[1]))]

                # these three criteria can determine if there's a range overlap
                if((manifestCriteria[1] >= dbCrit[0] and
                   dbCrit[1] >= manifestCriteria[0]) or
                   manifestCriteria[0] == dbCrit[1]):
                    # range overlap so record the collision
                    try:
                        collisions[row[0], row[1]] += "MIN" + crit + ","
                        collisions[row[0], row[1]] += "MAX" + crit + ","
                    except KeyError:
                        collisions[row[0], row[1]] = "MIN" + crit + ","
                        collisions[row[0], row[1]] += "MAX" + crit + ","
    return collisions

def findCollidingManifests(files, collisions):
    """
    For each manifest/instance pair in collisions check that the manifest
    criteria diverge (i.e. are not exactly the same) and that the ranges do not
    collide for ranges.
    Exits if: a range collides, or if the manifest has the same criteria as a
    manifest already in the database
    Returns: Nothing
    """
    # check every manifest in collisions to see if manifest collides (either
    # identical criteria, or overlaping ranges)
    for manifestInst in collisions:
        # get all criteria from this manifest/instance pair
        dbCriteria = AIdb.getManifestCriteria(manifestInst[0],
                                              manifestInst[1],
                                              files.getDatabase().getQueue(),
                                              humanOutput=True,
                                              onlyUsed=False)

        # iterate over every criteria in the database
        for crit in AIdb.getCriteria(files.getDatabase().getQueue(),
                                     onlyUsed=False, strip=False):

            # Get the criteria name (i.e. no MIN or MAX)
            crit_name = crit.replace('MIN', '', 1).replace('MAX', '', 1)
            # Set manCriteria to the key of the DB criteria or None
            manCriteria = files.getCriteria(crit_name)
            if manCriteria and crit.startswith('MIN'):
              manCriteria = manCriteria[0]
            elif manCriteria and crit.startswith('MAX'):
              manCriteria = manCriteria[1]

            # set the database criteria
            if dbCriteria[str(crit)] == '':
                # replace database NULL's with a Python None
                dbCrit = None
            else:
                dbCrit = dbCriteria[str(crit)]

            # Replace unbounded's in the criteria (i.e. 0/+inf)
            # with a Python None.
            if isinstance(manCriteria, basestring) and \
               manCriteria == "unbounded":
                manCriteria = None

            # check to determine if this is a range collision by using
            # collisions and if not are the manifests divergent

            if((crit.startswith('MIN') and
                collisions[manifestInst].find(crit + ",") != -1) or
               (crit.startswith('MAX') and
                collisions[manifestInst].find(crit + ",") != -1)
              ):
                if (str(dbCrit).lower() != str(manCriteria).lower()):
                    raise SystemExit(_("Error:\tManifest has a range "
                                       "collision with manifest:%s/%i"
                                       "\n\tin criteria: %s!") %
                                     (manifestInst[0], manifestInst[1],
                                      crit.replace('MIN', '', 1).
                                      replace('MAX', '', 1)))

            # the range did not collide or this is a single value (if we
            # differ we can break out knowing we diverge for this
            # manifest/instance)
            elif(str(dbCrit).lower() != str(manCriteria).lower()):
                # manifests diverge (they don't collide)
                break

        # end of for loop and we never broke out (diverged)
        else:
            raise SystemExit(_("Error:\tManifest has same criteria as " +
                               "manifest:%s/%i!") %
                             (manifestInst[0], manifestInst[1]))

def insertSQL(files):
    """
    Ensures all data is properly sanitized and formatted, then inserts it into
    the database
    """
    queryStr = "INSERT INTO manifests VALUES("

    # add the manifest name to the query string
    queryStr += "'" + AIdb.sanitizeSQL(files.manifestName()) + "',"
    # check to see if manifest name is alreay in database (affects instance
    # number)
    if AIdb.sanitizeSQL(files.manifestName()) in \
        AIdb.getManNames(files.getDatabase().getQueue()):
            # database already has this manifest name get the number of instances
            instance = AIdb.numInstances(AIdb.sanitizeSQL(files.manifestName()),
                                         files.getDatabase().getQueue())

    # this a new manifest
    else:
        instance = 0

    # actually add the instance to the query string
    queryStr += str(instance) + ","

    # we need to fill in the criteria or NULLs for each criteria the database
    # supports (so iterate over each criteria)
    for crit in AIdb.getCriteria(files.getDatabase().getQueue(),
                                 onlyUsed=False, strip=False):
        # for range values trigger on the MAX criteria (skip the MIN's
        # arbitrary as we handle rows in one pass)
        if crit.startswith('MIN'):
            continue

        # get the values from the manifest
        values = files.getCriteria(crit.replace('MAX', '', 1))

        # if the values are a list this is a range
        if isinstance(values, list):
            for value in values:
                # translate "unbounded" to a database NULL
                if value == "unbounded":
                    queryStr += "NULL,"
                # we need to deal with mac addresses specially being
                # hexadecimal
                elif crit.endswith("mac"):
                    # need to insert with hex operand x'<val>'
                    # use an upper case string for hex values
                    queryStr += "x'" + AIdb.sanitizeSQL(str(value).upper())+"',"
                else:
                    queryStr += AIdb.sanitizeSQL(str(value).upper()) + ","

        # this is a single criteria (not a range)
        elif isinstance(values, basestring):
            # translate "unbounded" to a database NULL
            if values == "unbounded":
                queryStr += "NULL,"
            else:
                # use lower case for text strings
                queryStr += "'" + AIdb.sanitizeSQL(str(values).lower()) + "',"

        # the critera manifest didn't specify this criteria so fill in NULLs
        else:
            # use the criteria name to determine if this is a range
            if crit.startswith('MAX'):
                queryStr += "NULL,NULL,"
            # this is a single value
            else:
                queryStr += "NULL,"

    # strip trailing comma and close parentheses
    queryStr = queryStr[:-1] + ")"

    # update the database
    query = AIdb.DBrequest(queryStr, commit=True)
    files.getDatabase().getQueue().put(query)
    query.waitAns()
    # in case there's an error call the response function (which will print the
    # error)
    query.getResponse()

def doDefault(files):
    """
    Removes old default.xml after ensuring proper format
    """
    if files.findCriteria().next() is not None:
        raise SystemExit(_("Error:\tCan not use AI criteria in a default " +
                           "manifest"))
    # remove old manifest
    try:
        os.remove(os.path.join(files.getService(), 'AI_data', 'default.xml'))
    except IOError, e:
        raise SystemExit(_("Error:\tUnable to remove default.xml:\n\t%s") % e)

def placeManifest(files):
    """
    Compares src and dst manifests to ensure they are the same; if manifest
    does not yet exist, copies new manifest into place and sets correct
    permissions and ownership
    """
    manifestPath = os.path.join(files.getService(), "AI_data",
                                files.manifestName())

    # if the manifest already exists see if it is different from what was
    # passed in. If so, warn the user that we're using the existing manifest
    if os.path.exists(manifestPath):
        oldManifest = open(manifestPath, "r")
        existingMD5 = md5.new("".join(oldManifest.readlines())).digest()
        oldManifest.close()
        currentMD5 = md5.new(lxml.etree.tostring(files._AIRoot,
                             pretty_print=True, encoding=unicode)).digest()
        if existingMD5 != currentMD5:
            raise SystemExit(_("Error:\tNot copying manifest, source and " +
                               "current versions differ -- criteria in place."))

    # the manifest does not yet exist so write it out
    else:
        try:
            newManifest = open(manifestPath, "w")
            newManifest.writelines('<ai_criteria_manifest>\n')
            newManifest.writelines('\t<ai_embedded_manifest>\n')
            newManifest.writelines(lxml.etree.tostring(
                                   files._AIRoot, pretty_print=True,
                                   encoding=unicode))
            newManifest.writelines('\t</ai_embedded_manifest>\n')
            # write out each SMF SC manifest
            for key in files._smfDict:
                newManifest.writelines(
                                       '\t<sc_embedded_manifest name = "%s">\n'%
                                       key)
                newManifest.writelines("\t\t<!-- ")
                newManifest.writelines("<?xml version='1.0'?>\n")
                newManifest.writelines(lxml.etree.tostring(files._smfDict[key],
                                           pretty_print=True, encoding=unicode))
                newManifest.writelines('\t -->\n')
                newManifest.writelines('\t</sc_embedded_manifest>\n')
            newManifest.writelines('\t</ai_criteria_manifest>\n')
            newManifest.close()
        except IOError, e:
            raise SystemExit(_("Error:\tUnable to write to dest. "
                               "manifest:\n\t%s") % e)

    # change read for all and write for owner
    os.chmod(manifestPath, 0644)
    # change to user/group root (uid/gid 0)
    os.chown(manifestPath, 0, 0)

class DataFiles:
    """
    Class to contain and work with data files necessary for program
    """


    def __init__(self):
        # Criteria Schmea
        self.criteriaSchema = "/usr/share/auto_install/criteria_schema.rng"
        # SMF DTD
        self.smfDtd = "/usr/share/lib/xml/dtd/service_bundle.dtd.1"
        # A/I Manifst Schema, set by setAIschema():
        self._AIschema = None
        # Set by setService():
        self._service = None
        # Set by setImagePath():
        self._imagepath = None
        # Set by setManifestPath():
        self._manifest = None
        # Set by verifyAImanifest():
        self._AIRoot = None
        # Set by verifySMFmanifest():
        self._smfDict = dict()
        # Set by verifyCriteria():
        self._criteriaRoot = None
        self._criteriaPath = None
        # Set by setDatabase():
        self._db = None

    def findCriteria(self, source=None):
        """
        Find criteria from either the A/I manifest or optionally supplied
        criteria manifest
        """
        # determine if we use the AI or Criteria manifest
        if not self._criteriaRoot or source == "AI":
          root = self._AIRoot.findall(".//ai_criteria")
        else:
          root = self._criteriaRoot.findall(".//ai_criteria")

        # actually find criteria
        for tag in root:
            for child in tag.getchildren():
                if __debug__:
                    # should not happen according to schema
                    if child.text is None:
                        raise AssertionError(_(
                            "Criteria contains no values"))
                if child.tag == "range":
                    # criteria names are lower case
                    yield tag.attrib['name'].lower()
                else:
                    # criteria names are lower case
                    yield tag.attrib['name'].lower()

    def getCriteria(self, criteria):
        """
        Return criteria out of the A/I manifest or optionally supplied criteria
        manifest
        """
        if self._criteriaRoot:
            source = self._criteriaRoot
        else:
            source = self._AIRoot
        for tag in source.getiterator('ai_criteria'):
            crit = tag.get('name')
            # compare criteria name case-insensitive
            if crit.lower() == criteria.lower():
                for child in tag.getchildren():
                    if __debug__:
                        # should not happen according to schema
                        if child.text is None:
                            raise AssertionError(_(
                                "Criteria contains no values"))
                    if child.tag == "range":
                        return child.text.split()
                    else:
                        # this is a value response
                        return child.text.strip()
        return None
                                                        
    def openDatabase(self, dbFile=None):
        """
        Sets self._db (opens database object) and errors if already set
        """
        if self._db is None:
            self._db = AIdb.DB(dbFile, commit=True)
        else:
            raise AssertionError('Opening database when already open!')

    def getDatabase(self):
        """
        Returns self._db (database object) and errors if not set
        """
        if isinstance(self._db, AIdb.DB):
            return(self._db)
        else:
            raise AssertionError('Database not yet open!')

    def getService(self):
        """
        Returns self._service and errors if not yet set
        """
        if self._service is not None:
            return(self._service)
        else:
            raise AssertionError('Manifest path not yet set!')

    def setService(self, serv=None):
        """
        Sets self._service and errors if already set
        """
        if self._service is None:
            self._service = os.path.abspath(serv)
        else:
            raise AssertionError('Setting service when already set!')

    def findSCfromCriteria(self):
        """
        Find SC manifests as referenced in the criteria manifest
        """
        if self._criteriaRoot is None:
            raise AssertionError(_("Error:\t _criteriaRoot not set!"))
        try:
            root = self._criteriaRoot.iterfind(".//sc_manifest_file")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        # for each SC manifest file: get the URI and verify it, adding it to the
        # dictionary of SMF SC manifests
        for SCman in root:
            if SCman.attrib['name'] in self._smfDict:
                raise SystemExit(_("Error:\tTwo SC manfiests with name %s") %
                                 SCman.attrib['name'])
            # if this is an absolute path just hand it off
            if os.path.isabs(str(SCman.attrib['URI'])):
                self._smfDict[SCman.attrib['name']] = \
                    self.verifySCmanifest(SCman.attrib['URI'])
            # this is not an absolute path - make it one
            else:
                self._smfDict[SCman.attrib['name']] = \
                    self.verifySCmanifest(os.path.join(os.path.dirname(
                                              self._criteriaPath),
                                              SCman.attrib['URI']))
        try:
            root = self._criteriaRoot.iterfind(".//sc_embedded_manifest")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        # for each SC manifest embedded: verify it, adding it to the
        # dictionary of SMF SC manifests
        for SCman in root:
            # strip the comments off the SC manifest
            xmlData = lxml.etree.tostring(SCman.getchildren()[0])
            xmlData = xmlData.replace("<!-- ", "").replace(" -->", "")
            xmlData = StringIO.StringIO(xmlData)
            # parse and read in the SC manifest
            self._smfDict[SCman.attrib['name']] = \
                self.verifySCmanifest(xmlData, name=SCman.attrib['name'])

    def findAIfromCriteria(self):
        """
        Find A/I manifest as referenced or embedded in criteria manifest
        """
        if self._criteriaRoot is None:
            raise AssertionError(_("Error:\t_criteriaRoot not set!"))
        try:
            root = self._criteriaRoot.find(".//ai_manifest_file")
        except lxml.etree.LxmlError, e:
            raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
        if not isinstance(root, lxml.etree._Element):
            try:
                root = self._criteriaRoot.find(".//ai_embedded_manifest")
            except lxml.etree.LxmlError, e:
                raise SystemExit(_("Error:\tCriteria manifest error:%s") % e)
            if not isinstance(root, lxml.etree._Element):
                raise SystemExit(_("Error:\tNo <ai_manifest_file> or " +
                                   "<ai_embedded_manifest> element in "
                                   "criteria manifest and no A/I manifest "
                                   "provided on command line."))
        try:
            root.attrib['URI']
        except KeyError:
            self._AIRoot = \
                lxml.etree.tostring(root.find(".//ai_manifest"))
            return
        if os.path.isabs(root.attrib['URI']):
            self.setManifestPath(root.attrib['URI'])
        else:
            # if we do not have an absolute path try using the criteria
            # manifest's location for a base
            self.setManifestPath(
                os.path.join(os.path.dirname(self._criteriaPath),
                root.attrib['URI']))

    def getAIschema(self):
        """
        Returns self._AIschema and errors if not set
        """
        if self._AIschema is not None:
            return (self._AIschema)
        else:
            raise AssertionError('AIschema not set')

    def setAIschema(self):
        """
        Sets self._AIschema and errors if imagepath not yet set.
        """
        if self._imagepath is None:
            raise AssertionError('Imagepath is not yet set')
        else:
            if (os.path.exists(self._imagepath + \
                IMG_AI_MANIFEST_SCHEMA)):
                self._AIschema = self._imagepath + \
                    IMG_AI_MANIFEST_SCHEMA
            else:
                self._AIschema = SYS_AI_MANIFEST_SCHEMA
                print(_("Warning: Using A/I manifest schema <%s>\n") %
                      self._AIschema)

    def getImagePath(self):
        """
        Returns self._imagepath and errors if not set
        """
        if self._imagepath is not None:
            return (self._imagepath)
        else:
            raise AssertionError('Imagepath not set')

    def setImagePath(self, imagepath=None):
        """
        Sets self._imagepath
        """
        self._imagepath = os.path.abspath(imagepath)

    def getManifestPath(self):
        """
        Returns self._manifest and errors if not set
        """
        if self._manifest is not None:
            return(self._manifest)
        else:
            raise AssertionError('Manifest path not yet set!')

    def setManifestPath(self, mani=None):
        """
        Sets self._manifest and errors if already set
        """
        if self._manifest is None:
            self._manifest = os.path.abspath(mani)
        else:
            raise AssertionError('Setting manifest when already set!')

    def manifestName(self):
        """
        Returns manifest name as defined in the A/I manifest
        """
        if self._AIRoot.getroot().tag == "ai_manifest":
            name = self._AIRoot.getroot().attrib['name']
        else:
            raise SystemExit(_("Error:\tCan not find <ai_manifest> tag!"))
        # everywhere we expect manifest names to be file names so ensure
        # the name matches
        if not name.endswith('.xml'):
            name += ".xml"
        return name

    def verifyAImanifest(self):
        """
        Used for verifying and loading AI manifest as defined by
            DataFiles._AIschema.
        Input: None.
        Output (Result): Sets DataFiles._AIRoot on success to a LXML XML Tree
            object or raise SystemExit on error.
        """
        try:
            schema = file(self.getAIschema(), 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s ") %
                             self.getAIschema())
        try:
            xmlData = file(self.getManifestPath(), 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s ") %
                             self.getManifestPath())
        except AssertionError:
            # manifest path will be unset if we're not using a separate file for
            # A/I manifest so we must emulate a file
            xmlData = StringIO.StringIO(self._AIRoot)
        self._AIRoot = verifyXML.verifyRelaxNGManifest(schema, xmlData)
        if isinstance(self._AIRoot, lxml.etree._LogEntry):
            # catch if we area not using a manifest we can name with
            # getManifestPath()
            try:
                raise SystemExit(_("Error:\tFile %s failed validation:\n\t%s") %
                                 (os.path.basename(self.getManifestPath()),
                                  self._AIRoot.message))
            # getManifestPath will throw an AssertionError if it does not have
            # a path use a different error message
            except AssertionError:
                raise SystemExit(_("Error:\tA/I manifest failed validation:"
                                   "\n\t%s") % self._AIRoot.message)


    def verifySCmanifest(self, data, name=None):
        """
        Used for verifying and loading SC manifest
        Input: File path, or StringIO object. Optionally, takes a name to
               provide in error output, as a StringIO object will not have a file
               path to provide.
        Output:Provide a LXML XML Tree object or raise a SystemExit on error.
        """
        if not isinstance(data, StringIO.StringIO):
            try:
                data = file(data, 'r')
            except IOError:
                if name is None:
                    raise SystemExit(_("Error:\tCan not open: %s") % data)
                else:
                    raise SystemExit(_("Error:\tCan not open: %s") % name)
        xmlRoot = verifyXML.verifyDTDManifest(data, self.smfDtd)
        if isinstance(xmlRoot, list):
            if not isinstance(data, StringIO.StringIO):
                print >> sys.stderr, (_("Error:\tFile %s failed validation:") %
                                      data.name)
            else:
                print >> sys.stderr, (_("Error:\tSC Manifest %s failed "
                                        "validation:") % name)
            for err in xmlRoot:
                print >> sys.stderr, err
            raise SystemExit()
        return(xmlRoot)

    def verifyCriteria(self, filePath):
        """
        Used for verifying and loading criteria XML
        This will exit:
        *if the schema does not open
        *if the XML file does not open
        *if the XML is invalid according to the schema
        """
        try:
            schema = file(self.criteriaSchema, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s") %
                             self.criteriaSchema)
        try:
            file(filePath, 'r')
        except IOError:
            raise SystemExit(_("Error:\tCan not open: %s") % filePath)
        self._criteriaPath = filePath
        self._criteriaRoot = (verifyXML.verifyRelaxNGManifest(schema,
                              self._criteriaPath))
        if isinstance(self._criteriaRoot, lxml.etree._LogEntry):
            raise SystemExit(_("Error:\tFile %s failed validation:\n\t%s") %
                             (self._criteriaPath, self._criteriaRoot.message))
        verifyXML.prepValuesAndRanges(self._criteriaRoot,
                                      self.getDatabase())


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    data = DataFiles()

    # check that we are root
    if os.geteuid() != 0:
        raise SystemExit(_("Error:\tNeed root privileges to run"))

    # load in all the options and file data
    parseOptions(data)

    # if we have a default manifest do default manifest handling
    if data.manifestName() == "default.xml":
        doDefault(data)

    # if we have a non-default manifest first ensure it is a unique criteria
    # set and then, if unique, add the manifest to the criteria database
    else:
        # if we have a None criteria from findCriteria then the manifest has
        # no criteria which is illegal for a non-default manifest
        if data.findCriteria() is None:
            raise SystemExit(_("Error:\tNo criteria found " +
                               "in non-default manifest -- "
                               "at least one criterion needed!"))
        findCollidingManifests(data, findCollidingCriteria(data))
        insertSQL(data)

    # move the manifest into place
    placeManifest(data)

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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
"""

A/I Publish_Manifest Prototype

"""

import os.path
import sys
from threading import Thread
import md5
import string
import StringIO

from optparse import OptionParser
from pysqlite2 import dbapi2 as sqlite
import lxml.etree

sys.path.append("/usr/lib/python2.4/vendor-packages/osol_install/auto_install")
import verifyXML
import AI_database as AIdb


def parseOptions(files):
	"""
	Parse and validate options
	Args: a dataFiles object
	Returns: nothing -- but the dataFiles object is populated  (with the
	manifest(s) A/I, SC, SMF and many error conditions are caught and flagged
	to the user via raising SystemExit exceptions.
	"""

	usage = "usage: %prog [options] service_directory"
	parser = OptionParser(usage=usage, version="%prog 0.5")
	parser.add_option("-c", "--criteria", dest="criteria",
	    metavar="criteria.xml", type="string", nargs=1,
		help="provide criteria manifest file (not " + \
		"applicable to default manifests)")
	parser.add_option("-a", "--aimanifest", dest="ai",
	    metavar="AImanifest.xml", type="string", nargs=1,
		help="provide A/I manifest file")
	parser.add_option("-s", "--sysconfig", dest="sysconfig",
	    metavar="SC.xml", type="string", nargs=1,
		help="provide system configuration manifest file")
	(options, args) = parser.parse_args()

	# check that we got the A/I service passed in as an argument
	if len(args) != 1:
		parser.print_help()
		sys.exit(1)

	# we need at least an A/I manifest or a criteria manifest
	elif not options.ai and not options.criteria:
		parser.print_help()
		raise SystemExit("Error:\tNeed an A/I manifest or criteria manifest" +
		    "specifying one.")

	# set the service path
	files.setService(args[0])

	# check the service directory exists, and the AI.db, criteria_schema.rng
	# and ai_schema.rng files are present otherwise the service is
	# misconfigured
	if not (os.path.isdir(files.getService()) and
		os.path.exists(os.path.join(files.getService(), "AI.db"))):
		raise SystemExit("Error:\tNeed a valid A/I service directory")
	if not (os.path.exists(files.criteriaSchema) and
	    os.path.exists(files.AIschema)):
		raise SystemExit("Error:\tUnable to find criteria_schema %s and " +
		    "A/I schema %s.", (files.criteriaSchema, files.AIschema))

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
		try:
			# see if we have another A/I manifest specified (and warn if so)
			if files.findAIfromCriteria():
				print "Warning: Using A/I manifest from command line.\n" + \
				    "\tIgnoring A/I manifest specified in criteria manifest."
		# findAIfromCriteria() will SystemExit if it can not find a manifest
		except SystemExit:
			pass

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
			    onlyUsed = False, strip = False):
				raise SystemExit('Error:\tCriteria "' + crit + '" is not a ' +
				    'valid criteria!')

			# get all values in the database for this criteria (and
			# manifest/instance paris for each value)
			dbCriteria = AIdb.getSpecificCriteria(
			    files.getDatabase().getQueue(), crit, None,
				provideManNameAndInstance = True)

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

		# this is a range criteria (check ranges are valid, "None" gets set to
		# -inf/+inf, ensure the criteria exists in the DB, then look for collisions)
		else:
			# check for a properly ordered range (with none being 0 or
			# Inf.) but ensure both are not None
			if(
			   (manifestCriteria[0] == "None" and
				manifestCriteria[1] == "None"
			   ) or 
			   ((manifestCriteria[0] != "None" and
				 manifestCriteria[1] != "None"
				) and 
				(manifestCriteria[0] > manifestCriteria[1])
			   )
			  ):
				raise SystemExit("Error:\tCriteria " + crit + 
				    " is not a valid range (min > max) or " +
				    "(min and max None).")

			# clean-up NULL's and None's (to 0 and really large) (MACs are hex)
			# arbitrarily large number in case this Python does
			# not support IEEE754
			if manifestCriteria[0] == "None":
				manifestCriteria[0] = "0"
			if manifestCriteria[1] == "None":
				manifestCriteria[1] = "99999999999999999999999999999"
			if crit == "MAC":
				# convert hex MAC address (w/o colons) to a number
				manifestCriteria[0] = long(str(
				    manifestCriteria[0]).upper(), 16)
				manifestCriteria[1] = long(str(
				    manifestCriteria[1]).upper(), 16)
			else:
				# this is a decimal value
				manifestCriteria = [long(str(manifestCriteria[0]).upper()),
				    long(str( manifestCriteria[1]).upper())]

			# check to see that this criteria exists in the database columns
			if 'min' + crit not in AIdb.getCriteria(files.getDatabase().getQueue(),
				onlyUsed = False, strip = False) and 'max' + crit not in AIdb.getCriteria(
				files.getDatabase().getQueue(), onlyUsed = False, strip = False):
				raise SystemExit('Error:\tCriteria "' + crit + '" is not a ' +
					'valid criteria!')
			dbCriteria = AIdb.getSpecificCriteria(
				files.getDatabase().getQueue(), 'min' + crit, 'max' + crit,
				provideManNameAndInstance = True)

			# will iterate over a list of the form [manName, manInst, mincrit,
			# maxcrit]
			for row in dbCriteria:
				# arbitrarily large number in case this Python does
				# not support IEEE754
				dbCrit = ["0", "999999999999999999999999999999"]

				# now populate in valid database values (i.e. non-NULL values)
				if row[2] != '' and row[2] != None:
					dbCrit[0] = row[2]
				if row[3] != '' and row[3] != None:
					dbCrit[1] = row[3]
				if crit == "MAC":
					# use a hexadecimal conversion
					dbCrit = [long(str(dbCrit[0]), 16),
						long(str(dbCrit[1]), 16)]
				else:
					# these are decimal numbers
					dbCrit = [long(str(dbCrit[0])), long(str(dbCrit[1]))]

				# these three criteria can determine if there's a range overlap
				if((manifestCriteria[1] >= dbCrit[0] and
					dbCrit[1] >= manifestCriteria[0]) or
					manifestCriteria[0] == dbCrit[1]):
					# range overlap so record the collision
					try:
						collisions[row[0], row[1]] += "min" + crit + ","
						collisions[row[0], row[1]] += "max" + crit + ","
					except KeyError:
						collisions[row[0], row[1]] = "min" + crit + ","
						collisions[row[0], row[1]] += "max" + crit + ","
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
	for manifestInst in collisions.keys():
		# get all criteria from this manifest/instance pair
		dbCriteria = AIdb.getManifestCriteria(manifestInst[0],
		    manifestInst[1], files.getDatabase().getQueue(), humanOutput = True,
		    onlyUsed = False)

		# iterate over every criteria in the database
		for crit in AIdb.getCriteria(files.getDatabase().getQueue(),
		    onlyUsed = False, strip = False):

			# if the manifest does not contain this criteria set manCriteria to
			# None
			if files.getCriteria(crit.replace('min', '', 1).
			    replace('max', '', 1)) == None:
				manCriteria = None
			# if the criteria is a min value use the first value returned from
			# getCriteria()
			elif crit.startswith('min'):
				manCriteria = \
				    files.getCriteria(crit.replace('min', ''))[0]
			# if the criteria is a max value use the second value returned from
			# getCriteria()
			elif crit.startswith('max'):
				manCriteria = \
				    files.getCriteria(crit.replace('max', ''))[1]
			# this must be a single valued criteria
			else:
				manCriteria = files.getCriteria(crit)

			# set the database criteria
			if dbCriteria[str(crit)] == '':
				# replace database NULL's with a Python None
				dbCrit = None
			else:
				dbCrit = dbCriteria[str(crit)]

			# replace None's in the criteria (i.e. -inf/+inf) with a Python
			# None
			if isinstance(manCriteria, basestring) and manCriteria == "None":
				manCriteria = None

			# check to determine if this is a range collision by using
			# collisions and if not are the manifests divergent

			if((crit.startswith('min') and
			    collisions[manifestInst].find(crit + ",") != -1) or
			    (crit.startswith('max') and
			    collisions[manifestInst].find(crit + ",") != -1)
			    ):
				if (str(dbCrit).lower() != str(manCriteria).lower()):
					raise SystemExit("Error:\tManifest has a range collision " + \
						"with manifest:%s/%i\n\tin criteria:%s!" % (manifestInst[0],
						manifestInst[1] + 1, crit.replace('min', '', 1).replace(
						'max', '', 1)))

			# the range did not collide or this is a single value (if we
			# differ we can break out knowing we diverge for this
			# manifest/instance)
			elif(str(dbCrit).lower() != str(manCriteria).lower()):
				# manifests diverge (they don't collide)
				break

		# end of for loop and we never broke out (diverged)
		else:
			raise SystemExit("Error:\tManifest has same criteria as " +
			    "manifest %s/%i!" % (manifestInst[0], manifestInst[1]))

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
	    onlyUsed = False, strip = False):
		# for range values trigger on the max criteria (skip the min's
		# arbitrary as we handle rows in one pass)
		if crit.startswith('min'): continue

		# get the values from the manifest
		values = files.getCriteria(crit.replace('max', '', 1))

		# if the values are a list this is a range
		if isinstance(values, list):
			for value in values:
				# translate "None" to a database NULL
				if value == "None":
					queryStr += "NULL,"
				# we need to deal with MAC addresses specially being
				# hexadecimal
				elif crit.endswith("MAC"):
					# need to insert with hex operand x'<val>'
					# use an upper case string for hex values
					queryStr += "x'" + AIdb.sanitizeSQL(str(
					    value).upper()) + "',"
				else:
					queryStr += AIdb.sanitizeSQL(str(value).upper()) + ","

		# this is a single criteria (not a range)
		elif isinstance(values, basestring):
			# translate "None" to a database NULL
			if values == "None":
				queryStr += "NULL,"
			else:
				# use lower case for text strings
				queryStr += "'" + AIdb.sanitizeSQL(str(values).lower()) + "',"

		# the critera manifest didn't specify this criteria so fill in NULLs
		else:
			# use the criteria name to determine if this is a range
			if crit.startswith('max'):
				queryStr += "NULL,NULL,"
			# this is a single value
			else:
				queryStr += "NULL,"

	# strip trailing comma and close parentheses
	queryStr = queryStr[:-1] + ")"

	# update the database
	query = AIdb.DBrequest(queryStr, commit = True)
	files.getDatabase().getQueue().put(query)
	query.waitAns()
	# in case there's an error call the response function (which will print the
	# error)
	query.getResponse()

def doDefault(files):
	"""
	Removes old default.xml after ensuring proper format
	"""
	if files.findCriteria().next() != None:
		raise SystemExit("Error:\tCan not use AI criteria in a default " +
		    "manifest")
	# remove old manifest
	try:
		os.remove(os.path.join(files.getService(), 'AI_data', 'default.xml'))
	except IOError, e:
		raise SystemExit("Error:\tUnable to remove default.xml:\n\t%s", e)

def placeManifest(files):
	"""
	Compares src and dst manifests to ensure they are the same; if manifest
	does not yet exist, copies new manifest into place and sets correct
	permissions and ownership
	"""
	manifestPath = os.path.join(files.getService(), "AI_data", files.manifestName())

	# if the manifest already exists see if it is different from what was
	# passed in. If so, warn the user that we're using the existing manifest
	if os.path.exists(manifestPath):
		oldManifest = open(manifestPath, "r")
		existingMD5 = md5.new(string.join(oldManifest.readlines())).digest()
		oldManifest.close()
		currentMD5 = md5.new(lxml.etree.tostring(files._AIRoot,
                             pretty_print=True, encoding=unicode)).digest()
		if existingMD5 != currentMD5:
			raise SystemExit("Error:\tNot copying manifest, source and " +
			    "current versions differ -- criteria in place.")

	# the manifest does not yet exist so write it out
	else:
		try:
			newManifest = open(manifestPath, "w")
			newManifest.writelines('<ai_criteria_manifest>\n')
			newManifest.writelines('\t<ai_embedded_manifest>\n')
			newManifest.writelines(lxml.etree.tostring(\
			    files._AIRoot, pretty_print=True, encoding=unicode))
			newManifest.writelines('\t</ai_embedded_manifest>\n')
			# write out each SMF SC manifest
			for key in files._smfDict.keys():
				newManifest.writelines('\t<sc_embedded_manifest name = "%s">\n' % \
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
			raise SystemExit(\
			    "Error:\tUnable to write to dest. manifest:\n\t%s" % e)

	# change read for all and write for owner
	os.chmod(manifestPath, 0644)
	# change to user/group root (uid/gid 0)
	os.chown(manifestPath, 0, 0)

class DataFiles:
	"""
	Class to contain and work with data files necessary for program
	"""


	def __init__(self):
		# A/I Manifst Schema
		self.AIschema = \
		    "/usr/share/lib/xml/rng/auto_install/ai_schema.rng"
		# Criteria Schmea
		self.criteriaSchma = \
		    "/usr/share/lib/xml/rng/auto_install/criteria_schema.rng"
		# SMF DTD
		self.smfDtd = "/usr/share/lib/xml/dtd/service_bundle.dtd.1"
		# Set by setService():
		self._service = None
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

	def findCriteria(self, source = None):
		"""
		Find criteria from either the A/I manifest or optionally supplied
		criteria manifest
		"""
		if source is "AI":
			root = self._AIRoot.findall(".//ai_criteria")
		else:
			if self._criteriaRoot:
				root = self._criteriaRoot.findall(".//ai_criteria")
			else:
				root = self._AIRoot.findall(".//ai_criteria")
		if len(root) > 0:
			for tag in root:
				yield tag.attrib['name']
		else:
			yield None
		return

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
			if crit == criteria:
				for child in tag.getchildren():
					if __debug__:
						if child.text is None:
							raise AssertionError("Criteria contains no values")
					if child.tag == "range":
						return child.text.split()
					else:
						# this is a value response
						return child.text
		return None
                                                        
	def openDatabase(self, dbFile = None):
		"""
		Sets self._db (opens database object) and errors if already set
		"""
		if self._db == None:
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
		if self._service != None:
			return(self._service)
		else:
			raise AssertionError('Manifest path not yet set!')

	def setService(self, serv = None):
		"""
		Sets self._service and errors if already set
		"""
		if self._service == None:
			self._service = os.path.abspath(serv)
		else:
			raise AssertionError('Setting service when already set!')

	def findSCfromCriteria(self):
		"""
		Find SC manifests as referenced in the criteria manifest
		"""
		if self._criteriaRoot == None:
			raise AssertionError("Error:\t _criteriaRoot not set!")
		try:
			root = self._criteriaRoot.iterfind(".//sc_manifest_file")
		except lxml.etree.LxmlError, e:
			raise SystemExit("Error:\tCriteria manifest error:%s" % e)
		# for each SC manifest file: get the URI and verify it, adding it to the
		# dictionary of SMF SC manifests
		for SCman in root:
			if SCman.attrib['name'] in self._smfDict.keys():
				raise SystemExit("Error:\tTwo SC manfiests with name %s" % \
				    SCman.attrib['name'])
			# if this is an absolute path just hand it off
			if os.path.isabs(str(SCman.attrib['URI'])):
				self._smfDict[SCman.attrib['name']] = \
					self.verifySCmanifest(self, SCman.attrib['URI'])
			# this is not an absolute path - make it one
			else:
				self._smfDict[SCman.attrib['name']] = \
				    self.verifySCmanifest(os.path.join(os.path.dirname(
				    self._criteriaPath), SCman.attrib['URI']))
		try:
			root = self._criteriaRoot.iterfind(".//sc_embedded_manifest")
		except lxml.etree.LxmlError, e:
			raise SystemExit("Error:\tCriteria manifest error:%s" % e)
		# for each SC manifest embedded: verify it, adding it to the
		# dictionary of SMF SC manifests
		for SCman in root:
			xmlData = \
				StringIO.StringIO(lxml.etree.tostring(SCman.getchildren()[0]).
				    replace("<!-- ", '').replace(" -->", ''))
			self._smfDict[SCman.attrib['name']] = \
				self.verifySCmanifest(xmlData, name = SCman.attrib['name'])

	def findAIfromCriteria(self):
		"""
		Find A/I manifest as referenced or embedded in criteria manifest
		"""
		if self._criteriaRoot == None:
			raise AssertionError("Error:\t _criteriaRoot not set!")
		try:
			root = self._criteriaRoot.find(".//ai_manifest_file")
		except lxml.etree.LxmlError, e:
			raise SystemExit("Error:\tCriteria manifest error:%s" % e)
		if not isinstance(root, lxml.etree._Element):
			try:
				root = self._criteriaRoot.find(".//ai_embedded_manifest")
			except lxml.etree.LxmlError, e:
				raise SystemExit("Error:\tCriteria manifest error:%s" % e)
			if not isinstance(root, lxml.etree._Element):
				raise SystemExit("Error:\tNo <ai_manifest_file> or " +
                    "<ai_embedded_manifest> element in criteria manifest " +
				    "and no A/I manifest provided on command line.")
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
			self.setManifestPath (os.path.join(os.path.dirname(self._criteriaPath),
			    root.attrib['URI']))

	def getManifestPath(self):
		"""
		Returns self._manifest and errors if not set
		"""
		if self._manifest != None:
			return(self._manifest)
		else:
			raise AssertionError('Manifest path not yet set!')

	def setManifestPath(self, mani = None):
		"""
		Sets self._manifest and errors if already set
		"""
		if self._manifest == None:
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
			raise SystemExit("Error:\tCan not find <ai_manifest> tag!")
		# everywhere we expect manifest names to be file names so ensure
		# the name matches
		if not name.endswith('.xml'):
			name += ".xml"
		return name

	def verifyAImanifest(self):
		"""
		Used for verifying and loading AI manifest
		"""
		try:
			schema = file(self.AIschema, 'r')
		except IOError:
			raise SystemExit("Error:\tCan not open: %s " % self.AIschema)
		try:
			xmlData = file(self.getManifestPath(), 'r')
		except IOError:
			raise SystemExit("Error:\tCan not open: %s " % self.getManifestPath())
		except AssertionError:
			# manifest path will be unset if we're not using a separate file for
			# A/I manifest so we must emulate a file
			xmlData = StringIO.StringIO(self._AIRoot)
		self._AIRoot = verifyXML.verifyRelaxNGManifest(schema, xmlData)
		if isinstance(self._AIRoot, lxml.etree._LogEntry):
			# catch if we area not using a manifest we can name with
			# getManifestPath()
			try:
				raise SystemExit("Error:\tFile %s failed validation:\n\t%s" % (
				    os.path.basename(self.getManifestPath()),
				    self._AIRoot.message))
			# getManifestPath will throw an AssertionError if it does not have
			# a path use a different error message
			except AssertionError:
				raise SystemExit("Error:\tA/I manifest failed validation:\n\t%s" %
				    self._AIRoot.message)


	def verifySCmanifest(self, data, name = None):
		"""
		Used for verifying and loading SC manifest
		"""
		if not isinstance(data, StringIO.StringIO):
			try:
				data = file(data, 'r')
			except IOError:
				raise SystemExit("Error:\tCan not open: %s" % data)
		xmlRoot = verifyXML.verifyDTDManifest(data,self.smfDtd)
		if isinstance(xmlRoot, list):
			if not isinstance(data, StringIO.StringIO):
				print >> sys.stderr, "Error:\tFile %s failed validation:" % \
				    data.name
			else:
				print >> sys.stderr, "Error:\tSC Manifest %s failed validation:"\
				    % name
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
			raise SystemExit("Error:\tCan not open: %s" % self.criteriaSchema)
		try:
			file(filePath, 'r')
		except IOError:
			raise SystemExit("Error:\tCan not open: %s" % filePath)
		self._criteriaPath = filePath
		self._criteriaRoot = (verifyXML.verifyRelaxNGManifest(schema,
		    self._criteriaPath))
		if isinstance(self._criteriaRoot, lxml.etree._LogEntry):
			raise SystemExit("Error:\tFile %s failed validation:\n\t%s" % (
			    self._criteriaPath, self._criteriaRoot.message))

if __name__ == '__main__':

	data = DataFiles()
	# check that we are root
	if os.geteuid() != 0:
		raise SystemExit("Error:\tNeed root privileges to run")
	parseOptions(data)
	if data.manifestName() == "default.xml":
		doDefault(data)
	else:
		findCollidingManifests(data, findCollidingCriteria(data))
		insertSQL(data)
	placeManifest(data)

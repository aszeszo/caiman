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

A/I List Manifests

"""

import os
import sys
import gettext
from optparse import OptionParser

from pysqlite2 import dbapi2 as sqlite

import osol_install.auto_install.AI_database as AIdb

def parseOptions():
	"""
	Parse and validate options
	"""

	usage = _("usage: %prog [options] manifest_name A/I_data_directory")
	parser = OptionParser(usage = usage, version = _("%prog 0.5"))
	parser.add_option("-i", "--instance", dest = "instance", default = None,
							help = _("provide manifest instance to remove"),
							type = "int", metavar = "manifest instance")
	(options, args) = parser.parse_args()
	# collect the manifest name and A/I data directory
	if len(args) != 2:
		parser.print_help()
		sys.exit(1)

	return (args[1], (args[0], options.instance))

def deleteManifestFromDB(DB, manifestInstance, dataLoc):
	"""
	Remove manifest from DB
	"""
	instance = manifestInstance[1]
	# check to see that the manifest is found in the database (as entered)
	if manifestInstance[0] not in AIdb.getManNames(DB.getQueue()):
		# since all manifest names have to have .xml appended try adding that
		if manifestInstance[0] + '.xml' in AIdb.getManNames(DB.getQueue()):
			manName = manifestInstance[0] + '.xml'
		else:
			raise SystemExit(_("Error:\tManifest %s not found in database!" %
			    manifestInstance[0]))
	else:
		manName = manifestInstance[0]

	# if we do not have an instance remove the entire manifest
	if instance == None:
		# remove manifest from database
		query = AIdb.DBrequest("DELETE FROM manifests WHERE name = '%s'" %
			AIdb.sanitizeSQL(manName), commit = True)
		DB.getQueue().put(query)
		query.waitAns()
		# run getResponse to handle and errors
		query.getResponse()

		# clean up file on file system
		try:
			os.remove(os.path.join(dataLoc, 'AI_data', manName))
		except:
			print >> sys.stderr, _("Warning:\tUnable to find file %s for " +
			    "removal!") % manName

	# we are removing a specific instance
	else:
		# check that the instance number is within bounds for that manifest
		# (0..numInstances)
		if instance > AIdb.numInstances(manName, DB.getQueue()) or \
		    instance < 0:
			raise SystemExit(_("Error:\tManifest %s has %i instances" % (manName,
			    AIdb.numInstances(manName, DB.getQueue()))))

		# remove instance from database
		qStr = "DELETE FROM manifests WHERE name = '%s' AND instance = '%i'" %\
		    (manName, instance)
		query = AIdb.DBrequest(qStr, commit = True)
		DB.getQueue().put(query)
		query.waitAns()
		# run getResponse to handle and errors
		query.getResponse()

		# We may need to reshuffle manifests to prevent gaps in instance
		# numbering as the DB routines expect instances to be contiguous and
		# increasing. We may have removed an instance with instances numbered
		# above thus leaving a gap.
		
		# get the number of instances with a larger instance
		for num in range(instance, AIdb.numInstances(
		    manName, DB.getQueue())+1):
			# now decrement the instance number
			qStr = "UPDATE manifests SET instance = '%i' WHERE name = '%s' " %\
			    (num-1, AIdb.sanitizeSQL(manName))
			qStr += "AND instance = '%i'" % num
			query = AIdb.DBrequest(qStr, commit = True)
			DB.getQueue().put(query)
			query.waitAns()
			# run getResponse to handle and errors
			query.getResponse()

		# remove file if manifest is no longer in database
		if manName not in AIdb.getManNames(DB.getQueue()):
			try:
				os.remove(os.path.join(dataLoc, 'AI_data',manName))
			except:
				print >> sys.stderr, _("Warning:\tUnable to find file %s for " +
					"removal!") % manName
			

if __name__ == '__main__':
	gettext.install("ai", "/usr/lib/locale") 
	# check that we are root
	if os.geteuid() != 0:
		raise SystemExit(_("Error:\tNeed root privileges to run"))
	(dataLoc, options) = parseOptions()
	if not os.path.exists(os.path.join(dataLoc, "AI.db")):
		raise SystemExit(_("Error:\tNeed a valid A/I service directory"))
	AISQL = AIdb.DB(os.path.join(dataLoc, 'AI.db'), commit = True)
	AISQL.verifyDBStructure()
	deleteManifestFromDB(AISQL, options, dataLoc)

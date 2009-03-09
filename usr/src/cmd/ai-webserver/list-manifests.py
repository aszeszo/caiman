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

import osol_install.auto_install.AI_database as AIdb

def parseOptions():
	"""
	Parse and validate options
	Return the options and service location (args[0])
	"""

	usage = _("usage: %prog [options] A/I_data_directory")
	parser = OptionParser(usage=usage, version=_("%prog 0.5"))
	parser.add_option("-c", "--criteria", dest="criteria", default=False,
							action="store_true",
							help=_("provide manifest criteria"))
	(options, args) = parser.parse_args()

	# we need the A/I service directory to be passed in
	if len(args) != 1:
		parser.print_help()
		sys.exit(1)

	return (options, args[0])

def printHeaders(DB, options):
	"""
	Prints out the headers for the rest of the command's output
	Returns the maximum lengths computed, to be used spacing the output of later
	functions
	"""
	headerL1 = ""
	maxManifestLen = 0
	maxCritLen = dict()

	# calculate the maximum manifest name length (and print the manifest
	# header)
	for name in AIdb.getManNames(DB.getQueue()):
		maxManifestLen = max(maxManifestLen, len(name))
	headerL1 += _("Manifest")

	# if we're printing out criteria calculate lengths and print criteria names
	if options.criteria:
		# add the necessary spacing to the header for the manifest
		# names and add a field for instances
		for i in range(len(_("Manifest")), maxManifestLen+1):
			headerL1 += " "
		headerL1 += _("Instance") + " "

		# first use un-stripped criteria to generate lengths of the criteria
		# values
		for crit in AIdb.getCriteria(DB.getQueue(), onlyUsed = False, strip = False):
			maxCritLen[crit] = 0
			# iterate through each value for this criteria getting the maximum
			# length
			for response in AIdb.getSpecificCriteria(DB.getQueue(),crit):
				maxCritLen[crit] = max(maxCritLen[crit], len(str(response[0])))

			# add a space between criteria
				maxCritLen[crit] += 1

			# set MIN and MAX criteria to have equal lenghts since they share a
			# column (but have to run on MAXcrit so MINcrit has been set)
			if crit.startswith('MAX'):
				# first set MAXcrit
				maxCritLen[crit] = max(maxCritLen[crit.replace('MIN','MAX')],
				    maxCritLen[crit.replace('MAX','MIN')])
				# now set MINcrit
				maxCritLen[crit.replace('MAX','MIN')] = maxCritLen[crit]

		# now print stripped criteria for human consumption as the headers
		for crit in AIdb.getCriteria(DB.getQueue(), onlyUsed = True, strip = True):
			headerL1 += crit
			# try the stripped criteria (if it doesn't match it's a range)
			try:
				if maxCritLen[crit]:
					for i in range(len(crit), int(str(maxCritLen[crit]))):
						headerL1 += " "
			# since the criteria didn't match stripped this must be a range
			except KeyError:
					# use MIN since
					# maxCritLen['MIN'+crit]=maxCritLen['MAX'+crit]
					for i in range(len(crit), int(str(maxCritLen['MIN' +
						crit]))):
						headerL1 += " "

	# print the final header
	print headerL1
	# print a line of hyphens to separate the data out
	headerL2 = ""
	for i in range(0, len(headerL1)):
		headerL2 += "-"
	print headerL2
	return (maxManifestLen + 1, maxCritLen)

def printManifests(DB,maxLengths = None):
	"""
	Prints out a list of manifests registered in the SQL database
	(If printing criteria call for the criteria of each manifest)
	"""
	for name in AIdb.getManNames(DB.getQueue()):
		# if we're handed maxLengths that means we need to print criteria too
		if maxLengths:
			print name + ":"
			printCriteria(DB, maxLengths, name)
		# we're simply printing manifest names
		else:
			print name

def printCriteria(DB, lengths, manifest):
	"""
	Prints out a list of criteria for each manifest instance
	registered in the SQL database
	"""
	# iterate over all instances of this manifest
	for instance in range(0, AIdb.numInstances(manifest, DB.getQueue())):

		# line one is used for single value and minimum values
		responseL1 = ""
		# line two is used for maximum values
		responseL2 = ""

		# deal with manifest and instance columns
		# print MAX manifest name length + 1 spaces for padding
		for i in range(0, lengths[0]):
			responseL1 += " "
			responseL2 += " "
		# add the instance number in
		responseL1 += str(instance)
		# space line two equally
		for i in range(0, len(str(instance))):
			responseL2 += " "
		# pad the column to the length of the instance header for the column
		for i in range(len(str(instance)), len(_("Instance"))):
			responseL1 += " "
			responseL2 += " "

		# now get the criteria to iterate over
		# need to iterate over all criteria not just used in case a MIN or MAX
		# is used but not its partner
		criteria = AIdb.getManifestCriteria(manifest, instance, DB.getQueue(),
		    humanOutput = True, onlyUsed = False)
		# now iterate for each criteria in the database
		for crit in criteria.keys():

			# this criteria is unused in this instance
			if criteria[crit] == None:
				# Ensure the criteria is used in the database - has a greater than
				# one length (due to space between criteria being added above)
				if lengths[1][crit] < 2:
					continue
				value = ""
				# print a centered hyphen if this criteria is unset
				for i in range(0, (lengths[1][crit]-1)/2):
					value += " "
				value += "-"
				for i in range((lengths[1][crit]-1)/2, lengths[1][crit]-1):
					value += " "
				
				# now put the value out to the correct line
				# MIN and single values on line one MAX values on line two
				if crit.startswith('MAX'):
					responseL2 += value
				elif crit.startswith('MIN'):
					responseL1 += value
				# else a single value space out line two
				else:
					responseL1 += value
					for i in range(0, len(str(value))):
						responseL2 += " "

			# this criteria is used in this instance
			else:
				value = criteria[crit]
				# if this is a range value print the MIN on line one
				if crit.startswith('MIN'):
					responseL1 += str(value)
					for i in range(len(str(value)), lengths[1][crit]):
						responseL1 += " "
				# if this is a range value print the MAX on line two
				elif crit.startswith('MAX'):
					responseL2 += str(value)
					for i in range(len(str(value)), lengths[1][crit]):
						responseL2 += " "
				# this is a single value (put it on line one and pad line two)
				else:
					responseL1 += str(value)
					for i in range(0, len(str(value))):
						responseL2 += " "
					for i in range(len(str(value)), lengths[1][crit]):
						responseL1 += " "
						responseL2 += " "

		print responseL1
		print responseL2


if __name__ == '__main__':
	gettext.install("ai", "/usr/lib/locale") 
	(options, dataLoc) = parseOptions()
	if not os.path.exists(os.path.join(dataLoc, "AI.db")):
		raise SystemExit("Error:\tNeed a valid A/I service directory")
	AISQL = AIdb.DB(os.path.join(dataLoc, 'AI.db'))
	AISQL.verifyDBStructure()
	maxLens = printHeaders(AISQL, options)
	if options.criteria:
		printManifests(AISQL, maxLengths = maxLens)
	else:
		printManifests(AISQL)

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

A/I Database Routines

"""

import Queue
import threading
from threading import Thread
import gettext

from pysqlite2 import dbapi2 as sqlite

class DB:
	"""
	Class to connect to, and look-up entries in the SQLite database
	"""


	def __init__(self, db, commit = False):
		"""
		Here we initialize the queue the DB thread will run, the DB
		thread itself (as well as daemonize it, and start it)
		"""
		self._requests = Queue.Queue()
		self._runner = DBthread(db, self._requests, commit)
		self._runner.setDaemon(True)
		self._runner.start()

	def getQueue(self):
		return self._requests

	def verifyDBStructure(self):
		"""
		Ensures reasonable DB schema and columns or else raises a SystemExit
		"""
		# get the names of each table in the database
		query = DBrequest("SELECT * FROM SQLITE_MASTER")
		self._requests.put(query)
		query.waitAns()

		# iterate over each table in the database
		for row in iter(query.getResponse()):
			if "manifests" == row['tbl_name']:
				break
		# if we do not break out we do not have a manifest table
		else:
			raise SystemExit(_("Error:\tNo manifests table"))
		# iterate over each column of the manifests table
		query = DBrequest("PRAGMA table_info(manifests)")
		self._requests.put(query)
		query.waitAns()

		# gather column names in a list
		columns = list()
		for col in iter(query.getResponse()):
			columns.append(col['name'])

		# ensure we have a name, instance and at least one criteria column
		if not "name" in columns or not "instance" in columns or \
		    len(columns) < 3:
			raise SystemExit(_("Error:\tDatabase columns appear malformed"))

class DBrequest(object):
	"""
	Class to hold SQL queries and their responses
	"""


	def __init__(self, query, commit = False):
		"""
		Set the private SQL query and create the event to flag when
		the query has returned.
		"""
		self._sql = str(query)
		self._e = threading.Event()
		self._ans = None
		self._committable = commit

	def needsCommit(self):
		""" Use needsCommit() to determine if the query needs to be committed. """
		return(self._committable)

	def getSql(self):
		""" Use getSql() to access the SQL query string. """
		return(self._sql)

	def setResponse(self, resp):
		"""
		Use setResponse() to set the DB response and update the event flag.
		(Will throw a RuntimeError if already set.)
		"""
		if self._e.isSet():
			raise RuntimeError('Setting already set value')
		self._ans = resp
		self._e.set()
	
	def getResponse(self):
		"""
		Use getResponse() to retrieve the DB response. (Will throw a
		NameError if not yet set.)
		"""
		# ensure the DBrequest's event is set and that _ans is a PySQLite list
		if self._e.isSet() and isinstance(self._ans, list):
			return(self._ans)
		# is _ans is a string we have an error so handle it
		elif self._e.isSet() and isinstance(self._ans, basestring):
			print self._ans
		else:
			print _("Value not yet set")

	def isFinished(self):
		"""
		finished() is similar to getResponse() allowing one to determine if the
		DBrequest has been handled
		"""
		return(self._e.isSet())

	def waitAns(self):
		"""
		Use waitAns() to wait for setResponse() to set the event
		"""
		# 15 second timeout is arbitrary to prevent possible deadlock
		self._e.wait(15)

class DBthread(Thread):
	"""
	Class to interface with SQLite as the provider is single threaded
	"""


	def __init__(self, db, queue, commit):
		"""
		Here we create a new thread object, create a DB connection object, keep
		track of the DB filename and track the request queue to run on.
		"""
		Thread.__init__(self)
		self._con = None
		self._dBfile = db
		self._requests = queue
		self._committable = commit
	
	def __del__(self):
		""" On destruction, close the DB connection if still open """
		if self._con is not None:
			self._con.close()

	def run(self):
		"""
		Here we simply iterate over the request queue executing queries and
		reporting responses, errors are set as strings for that DBrequest.
		"""
		if self._committable == True:
			# use SQLite IMMEDIATE isolation to prevent any writers changing
			# the DB while we are working on it (but don't use EXCLUSIVE since
			# there may be persistent readers)
			self._con = sqlite.connect(self._dBfile, isolation_level = "IMMEDIATE")
		else:
			self._con = sqlite.connect(self._dBfile)
		# allow access by both index and column name
		self._con.row_factory = sqlite.Row
		self._cursor = self._con.cursor()
		# iterate over each DBrequest object in the queue
		while True:
			request = self._requests.get()
			# skip already processed DBrequest's
			if request is not None and not request.isFinished():
				# if the connection and query are committable then execute the
				# query and commit it
				if request.needsCommit() == True and self._committable == True:
					try:
						self._cursor.execute(request.getSql())
						self._con.commit()
					except Exception, e:
						# save error string for caller to trigger
						request.setResponse(_("Database failure with SQL: %s") %
						    request.getSql() + "\n\t" + _("Error: %s") % str(e))
						# ensure we do not continue processing this request
						continue
				# the query does not need to commit
				elif request.needsCommit() == False:
					try:
						self._cursor.execute(request.getSql())
					except Exception, e:
						# save error string for caller to trigger
						request.setResponse(_("Database failure with SQL: %s") %
						    request.getSql() + "\n\t" + _("Error: %s") % str(e))
						# ensure we do not continue processing this request
						continue
				# the query needs commit access and the connection does not
				# support it
				else:
					# save error string for caller to trigger
					request.setResponse(_("Database failure with SQL: %s") %
						request.getSql() + "\n\t" + _("Error: Connection not" +
						"committable"))
					# ensure we do not continue processing this request
					continue
				request.setResponse(self._cursor.fetchall())
#
# Functions below here
#

def sanitizeSQL(s):
	"""
	Use to remove special SQL characters which could cause damage or
	unintended results if unexpectedly embedded in an SQL query.
	This shouldn't be expected to make a SQL injection attack somehow
	return valid data, but it should cause it to not be a threat to the DB.
	"""
	s = s.replace('%', '')
	s = s.replace('*', '')
	s = s.replace(',', '')
	s = s.replace(';', '')
	s = s.replace('(', '')
	s = s.replace(')', '')
	# note: "'" should not get stripped as x'<hex>' is how one flags a hex
	# value to SQLite3 so that it returns the string in a string not byte
	# format
	return str(s)

def numInstances(manifest, queue):
	""" Run to return the number of instances for manifest in the DB """
	query = DBrequest('SELECT COUNT(instance) FROM manifests WHERE ' +
	    'name = "' + manifest + '"')
	queue.put(query)
	query.waitAns()
	return(query.getResponse()[0][0])

def numManifests(queue):
	""" Run to return the number of manifests in the DB """
	query = DBrequest('SELECT COUNT(DISTINCT(name)) FROM manifests')
	queue.put(query)
	query.waitAns()
	return(query.getResponse()[0][0])

def getManNames(queue):
	"""
	Use to create a generator which provides the names of manifests
	in the DB
	"""
	# Whether the DBrequest should be in or out of the for loop depends on if doing
	# one large SQL query and iterating the responses (but holding the
	# response in memory) is better than requesting row by row, and
	# doing more DB transactions in less memory
	for i in range(numManifests(queue)):
		query = DBrequest('SELECT DISTINCT(name) FROM manifests LIMIT 1 ' +
		    'OFFSET %s' % i)
		queue.put(query)
		query.waitAns()
		yield(query.getResponse()[0][0])
	return

def findManifestsByCriteria(queue, criteria):
	"""
	Returns the manifest names and instance tuple as specified by a list of
	criteria tuples (crit, value)
	"""
	queryStr = "SELECT name, instance FROM manifests WHERE "
	for crit in criteria:
		queryStr += crit[0] + ' = "' + crit[1l] + '" AND '
	else:
		# cut off extraneous '" AND '
		queryStr = queryStr[:-5]
	query = DBrequest(queryStr)
	queue.put(query)
	query.waitAns()
	return(query.respnse())

def getSpecificCriteria(queue, criteria, criteria2 = None,
	provideManNameAndInstance = False):
	"""
	Returns the criteria specified as an iterable list (can provide a second
	criteria to return a range (i.e. MIN and MAX memory)
	"""
	if provideManNameAndInstance == True:
		queryStr = "SELECT name, instance, "
	else:
		queryStr = "SELECT "
	if criteria2 is not None:
		if criteria.endswith('mac'):
			# for hexadecimal values we need to use the SQL HEX() function to
			# properly return a hex value
			queryStr += "HEX(" + criteria + "), HEX(" + criteria2 + \
			    ") FROM manifests WHERE " + criteria + " IS NOT NULL OR " + \
			    criteria2 + " IS NOT NULL"
		else:
			# this is a noraml decimal range value
			queryStr += criteria + ", " + criteria2 + \
			    " FROM manifests WHERE " + criteria + " IS NOT NULL OR " + \
			    criteria2 + " IS NOT NULL"
	else:
		if criteria.endswith('mac'):
			# for hexadecimal values we need to use the SQL HEX() function to
			# properly return a hex value
			queryStr += "HEX(" + criteria + ") FROM manifests WHERE " + \
			    criteria + " IS NOT NULL"
		else:
			# this is a noraml decimal range value or string
			queryStr += criteria + " FROM manifests WHERE " + criteria + \
			    " IS NOT NULL"
	query = DBrequest(queryStr)
	queue.put(query)
	query.waitAns()
	return(query.getResponse())

def getCriteria(queue, onlyUsed = True, strip = True):
	"""
	Provides a list of criteria which are used in the DB (i.e. what
	needs to be queried on the client). If strip is False, return
	exact DB column names not (more) human names.
	"""
	# first get the names of the columns (criteria) by using the SQL PRAGMA
	# statement on the manifest table
	query = DBrequest("PRAGMA table_info(manifests)")
	queue.put(query)
	query.waitAns()

	columns = list()
	queryStr = "SELECT "
	# build a query so we can determine which columns (criteria) are in use
	# using the output from the PRAGMA statement
	for col in iter(query.getResponse()):
		colName = col['name']
		# skip the manifest name and instance column as they are not criteria
		if (colName == "name"): continue
		if (colName == "instance"): continue
		# use the SQL COUNT() aggregator to determine if the criteria is in use
		queryStr += "COUNT(" + colName + ") as " + colName + ", "
		# add the column name to the list of columns
		columns.append(colName)
	else:
		# strip extra ", " from the query
		queryStr = queryStr[:-2]
		queryStr += " FROM manifests"

	if onlyUsed == False and strip == False:
		# if we are not gleaning the unused columns and not stripping the
		# column names then yield them now
		for column in columns:
			yield str(column)
		return

	elif onlyUsed == False:
		# if we are only stripping the column names yield the result now
		for column in columns:
			if column.startswith('MAX'): continue
			else: yield str(column.replace('MIN',''))
		return

	else:
		# we need to run the query from above and determine which columns are
		# in use we will gather used criteria for the response from the above
		# query which is like:
		# "SELECT COUNT(memMIN), COUNT(memMAX), ... FROM manifests"
		query = DBrequest(queryStr)
		queue.put(query)
		query.waitAns()
		response = dict()
		# iterate over each column
		for colName in columns:
			# only take columns which have a positive count
			if query.getResponse()[0][str(colName)] > 0:
				if strip == True:
					# take only the criteria name, not a qualifier
					# (i.e. MIN, MAX) but use both MAX and MIN in case one is
					# unused we need ensure we still return the stripped result
					if colName.startswith('MAX') or colName.startswith('MIN'):
						try:
							# if the key lookup succeeds we have already
							# reported this criteria go to the next one
							if response[colName.replace('MIN', '', 1).replace(
							    'MAX', '', 1)]:
								continue
						except KeyError:	
							# we have not reported this criteria yet, do so
							colName = colName.replace('MIN', '',
							    1).replace('MAX', '', 1)
							response[colName] = 1
				yield str(colName)
		return

def getManifestCriteria(name, instance, queue, humanOutput = False,
						onlyUsed = True):
	"""
	Returns the criteria (as a subset of used criteria) for a particular
	manifest given (human output returns HEX() for mac opposed to byte output)
	"""
	queryStr = "SELECT "
	for crit in getCriteria(queue, onlyUsed = onlyUsed, strip = False):
		if str(crit).endswith('mac') and humanOutput == True:
			queryStr += "hex(" + str(crit) + ") as " + str(crit) + ", "
		else: 
			queryStr += str(crit) + ", "
	else:
		if getCriteria(queue, onlyUsed = onlyUsed, strip = False).next() != \
		    None:
			queryStr = queryStr[:-2]
		else:
			raise AssertionError(_("Database contains no criteria!")) 
	queryStr += ' FROM manifests WHERE name = "' + name + \
	    '" AND instance = "' + str(instance) + '"'
	query = DBrequest(queryStr)
	queue.put(query)
	query.waitAns()
	return query.getResponse()[0]

def findManifest(criteria, db):
	"""
	findManifest() returns a query response provided a criteria
	dictionary. (The response may contain 0 or more manifests depending on
	criteria.)
	"""
	# If we didn't get any criteria bail providing no manifest
	if len(criteria) == 0:
		return 0

	curCount = 0
	queryStr = "SELECT name FROM manifests WHERE "
	for crit in getCriteria(db.getQueue(), strip = False):
		prevCount = curCount
		queryStr1 = queryStr
		try:
			if crit.startswith("MIN"):
				if crit.endswith("mac"):
					# setup a clause like HEX(MINmac) <= HEX(x'F00')
					queryStr1 += "HEX(" + crit + ") <= HEX(x'" + \
					    sanitizeSQL( \
					    criteria[crit.replace('MIN', '')]) + "')"
				else:
					# setup a clause like crit <= value
					queryStr1 += crit + " " + "<= " + \
					    sanitizeSQL(criteria[crit.replace('MIN', '')])
			elif crit.startswith("MAX"):
				if crit.endswith("mac"):
					# setup a clause like HEX(MINmac) >= HEX(x'F00')
					queryStr1 += "HEX(" + crit + ") >= HEX(x'" + \
					    sanitizeSQL( \
					    criteria[crit.replace('MAX', '')]) + "')"
				else:
					# setup a clause like crit <= value
					queryStr1 += crit + " " + ">= " + \
					    sanitizeSQL(criteria[crit.replace('MAX', '')])
			else:
				# store single values in lower case
				# setup a clause like crit = lower(value)
				queryStr1 += crit + " " + '= lower("' + \
				    sanitizeSQL(criteria[crit]) + '")'
		except KeyError:
			print _("Missing criteria: %s;returning 0 - oft default.xml") % crit
			return 0
		query = DBrequest(queryStr1)
		db.getQueue().put(query)
		query.waitAns()

		try:
			curCount = len(query.getResponse())
		except Exception:
			# we'll not get a response if we were provided a criteria which
			# isn't in the DB (we'll generate a DB error); shouldn't happen
			# unless getCriteria() is really confused
			print _("Bad criteria: %s;returning 0 - oft default.xml") % crit
			return 0

		if len(query.getResponse()) >= 1:
			queryStr = queryStr1 + " AND "
		else:
			# criteria reduced effective set to zero (add a NULL criteria
			# instead)
			queryStr += crit + " IS NULL AND "
	else:
		# remove extraneous " AND "
		queryStr = queryStr[:-5]
	query = DBrequest(queryStr)
	db.getQueue().put(query)
	query.waitAns()

	# see if we got one, more or zero manifests back
	if len(query.getResponse()) == 1:
		return query.getResponse()[0]['name']
	elif len(query.getResponse()) > 1:
		return len(query.getResponse())
	# got zero manifests back
	else:
		return 0

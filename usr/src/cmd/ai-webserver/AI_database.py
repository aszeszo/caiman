#!/usr/bin/python
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
'''

AI Database Routines

'''

import Queue
from sqlite3 import dbapi2 as sqlite
import threading

class DB:
    ''' Class to connect to, and look-up entries in the SQLite database '''

    def __init__(self, db, commit=False):
        ''' Here we initialize the queue the DB thread will run, the
        DB thread itself (as well as daemonize it, and start it)
        '''
        self._requests = Queue.Queue()
        self._runner = DBthread(db, self._requests, commit)
        self._runner.setDaemon(True)
        self._runner.start()

    def getQueue(self):
        return self._requests

    def verifyDBStructure(self):
        ''' Ensures reasonable DB schema and columns or else 
        raises a SystemExit
        '''
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
        if "name" not in columns or "instance" not in columns or \
            len(columns) < 3:
            raise SystemExit(_("Error:\tDatabase columns appear malformed"))

class DBrequest(object):
    ''' Class to hold SQL queries and their responses '''

    def __init__(self, query, commit=False):
        ''' Set the private SQL query and create the event to flag when
        the query has returned.
        '''
        self._sql = str(query)
        self._e = threading.Event()
        self._ans = None
        self._committable = commit

    def needsCommit(self):
        ''' Use needsCommit() to determine if the query needs to 
        be committed.
        '''
        return(self._committable)

    def getSql(self):
        ''' Use getSql() to access the SQL query string. '''
        return(self._sql)

    def setResponse(self, resp):
        ''' Use setResponse() to set the DB response and update the event flag.
        (Will throw a RuntimeError if already set.)
        '''
        if self._e.isSet():
            raise RuntimeError('Setting already set value')
        self._ans = resp
        self._e.set()

    def getResponse(self):
        ''' Use getResponse() to retrieve the DB response. (Will throw a
        NameError if not yet set.)
        '''
        # ensure the DBrequest's event is set and that _ans is a PySQLite list
        if self._e.isSet() and isinstance(self._ans, list):
            return(self._ans)
        # is _ans is a string we have an error so handle it
        elif self._e.isSet() and isinstance(self._ans, basestring):
            print self._ans
        else:
            print _("Value not yet set")

    def isFinished(self):
        ''' isFinished() is similar to getResponse(), allowing one to 
        determine if the DBrequest has been handled
        '''
        return(self._e.isSet())

    def waitAns(self):
        ''' Use waitAns() to wait for setResponse() to set the event '''

        # 15 second timeout is arbitrary to prevent possible deadlock
        self._e.wait(15)

class DBthread(threading.Thread):
    ''' Class to interface with SQLite as the provider is single threaded '''


    def __init__(self, db, queue, commit):
        ''' Here we create a new thread object, create a DB connection object,
        keep track of the DB filename and track the request queue to run on.
        '''
        threading.Thread.__init__(self)
        self._con = None
        self._dBfile = db
        self._requests = queue
        self._committable = commit

    def __del__(self):
        ''' On destruction, close the DB connection if still open '''
        if self._con is not None:
            self._con.close()

    def run(self):
        ''' Here we simply iterate over the request queue executing queries 
        and reporting responses. Errors are set as strings for that DBrequest.
        '''
        if self._committable:
            # use SQLite IMMEDIATE isolation to prevent any writers changing
            # the DB while we are working on it (but don't use EXCLUSIVE since
            # there may be persistent readers)
            self._con = sqlite.connect(self._dBfile,
                                       isolation_level="IMMEDIATE")
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
                if request.needsCommit() and self._committable:
                    try:
                        self._cursor.execute(request.getSql())
                        self._con.commit()
                    except Exception, ex:
                        # save error string for caller to trigger
                        request.setResponse(_("Database failure with SQL: %s") %
                                            request.getSql() +
                                            "\n\t" +
                                            _("Error: %s") % str(ex))
                        # ensure we do not continue processing this request
                        continue
                # the query does not need to commit
                elif not request.needsCommit():
                    try:
                        self._cursor.execute(request.getSql())
                    except Exception, ex:
                        # save error string for caller to trigger
                        request.setResponse(_("Database failure with SQL: %s") %
                                            request.getSql() +
                                            "\n\t" +
                                            _("Error: %s") % str(ex))
                        # ensure we do not continue processing this request
                        continue
                # the query needs commit access and the connection does not
                # support it
                else:
                    # save error string for caller to trigger
                    request.setResponse(_("Database failure with SQL: %s") %
                                        request.getSql() +
                                        "\n\t" +
                                        _("Error: Connection not committable"))
                    # ensure we do not continue processing this request
                    continue
                request.setResponse(self._cursor.fetchall())
#
# Functions below here
#

def sanitizeSQL(text):
    ''' Use to remove special SQL characters which could cause damage or
    unintended results if unexpectedly embedded in an SQL query.
    This shouldn't be expected to make a SQL injection attack somehow
    return valid data, but it should cause it to not be a threat to the DB.
    '''
    text = text.replace('%', '')
    text = text.replace('*', '')
    text = text.replace(',', '')
    text = text.replace(';', '')
    text = text.replace('(', '')
    text = text.replace(')', '')
    # note: "'" should not get stripped as x'<hex>' is how one flags a hex
    # value to SQLite3 so that it returns the string in a string not byte
    # format
    return str(text)

def numInstances(manifest, queue):
    ''' Run to return the number of instances for manifest in the DB '''
    query = DBrequest('SELECT COUNT(instance) FROM manifests WHERE ' +
                      'name = "' + manifest + '"')
    queue.put(query)
    query.waitAns()
    return(query.getResponse()[0][0])

def numManifests(queue):
    ''' Run to return the number of manifests in the DB '''
    query = DBrequest('SELECT COUNT(DISTINCT(name)) FROM manifests')
    queue.put(query)
    query.waitAns()
    return(query.getResponse()[0][0])

def getManNames(queue):
    ''' Use to create a generator which provides the names of manifests
    in the DB
    '''
    # Whether the DBrequest should be in or out of the for loop depends on if
    # doing one large SQL query and iterating the responses (but holding the
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
    ''' Returns the manifest names and instance tuple as specified by a 
    list of criteria tuples (crit, value)
    '''
    query_str = "SELECT name, instance FROM manifests WHERE "
    # warning if there's a massive number of criteria this may pass the SQL
    # query length for the database in use
    for crit in criteria:
        query_str += crit[0] + ' = "' + crit[1l] + '" AND '
    else:
        # cut off extraneous '" AND '
        query_str = query_str[:-5]
    query = DBrequest(query_str)
    queue.put(query)
    query.waitAns()
    return(query.respnse())

def getSpecificCriteria(queue, criteria, criteria2=None,
                        provideManNameAndInstance=False,
			excludeManifests=None):
    ''' Returns the criteria specified as an iterable list (can provide a 
    second criteria to return a range (i.e. MIN and MAX memory).  The 
    excludeManifests argument filters out the rows with the manifest names 
    given in that list.
    '''
    if provideManNameAndInstance:
        query_str = "SELECT name, instance, "
    else:
        query_str = "SELECT "
    if criteria2 is not None:
        if criteria.endswith('mac'):
            # for hexadecimal values we need to use the SQL HEX() function to
            # properly return a hex value
            query_str += ("HEX(" + criteria + "), HEX(" + criteria2 +
                          ") FROM manifests WHERE (" + criteria +
                          " IS NOT NULL OR " + criteria2 + " IS NOT NULL)")
        else:
            # this is a decimal range value
            query_str += (criteria + ", " + criteria2 +
                          " FROM manifests WHERE (" + criteria +
                          " IS NOT NULL OR " + criteria2 + " IS NOT NULL)")
    else:
        if criteria.endswith('mac'):
            # for hexadecimal values we need to use the SQL HEX() function to
            # properly return a hex value
            query_str += ("HEX(" + criteria + ") FROM manifests WHERE " +
                          criteria + " IS NOT NULL")
        else:
            # this is a decimal range value or string
            query_str += (criteria + " FROM manifests WHERE " + criteria +
                          " IS NOT NULL")

    if excludeManifests is not None:
        for manifest in excludeManifests:
            query_str += " AND name IS NOT '" + manifest + "'"

    query = DBrequest(query_str)
    queue.put(query)
    query.waitAns()
    return(query.getResponse())

def getCriteria(queue, onlyUsed=True, strip=True):
    ''' Provides a list of criteria which are used in the DB (i.e. what
    needs to be queried on the client). If strip is False, return
    exact DB column names not (more) human names.
    '''
    # first get the names of the columns (criteria) by using the SQL PRAGMA
    # statement on the manifest table
    query = DBrequest("PRAGMA table_info(manifests)")
    queue.put(query)
    query.waitAns()

    columns = list()
    query_str = "SELECT "
    # build a query so we can determine which columns (criteria) are in use
    # using the output from the PRAGMA statement
    for col in iter(query.getResponse()):
        col_name = col['name']
        # skip the manifest name and instance column as they are not criteria
        if (col_name == "name"):
            continue
        if (col_name == "instance"):
            continue
        # use the SQL COUNT() aggregator to determine if the criteria is in use
        query_str += "COUNT(" + col_name + ") as " + col_name + ", "
        # add the column name to the list of columns
        columns.append(col_name)
    else:
        # strip extra ", " from the query
        query_str = query_str[:-2]
        query_str += " FROM manifests"

    if not (onlyUsed or strip):
        # if we are not gleaning the unused columns and not stripping the
        # column names then yield them now
        for column in columns:
            yield str(column)
        return

    elif not onlyUsed:
        # if we are only stripping the column names yield the result now
        for column in columns:
            if not column.startswith('MAX'):
                yield str(column.replace('MIN', ''))
        return

    else:
        # we need to run the query from above and determine which columns are
        # in use we will gather used criteria for the response from the above
        # query which is like:
        # "SELECT COUNT(memMIN), COUNT(memMAX), ... FROM manifests"
        query = DBrequest(query_str)
        queue.put(query)
        query.waitAns()
        response = dict()
        # iterate over each column
        for col_name in columns:
            # only take columns which have a positive count
            if query.getResponse()[0][str(col_name)] > 0:
                if strip:
                    # take only the criteria name, not a qualifier
                    # (i.e. MIN, MAX) but use both MAX and MIN in case one is
                    # unused we need ensure we still return the stripped result
                    if col_name.startswith('MAX') or \
                        col_name.startswith('MIN'):
                        # we have reported this criteria do not repeat it
                        if response.has_key(col_name.replace('MIN', '', 1).\
                                               replace('MAX', '', 1)):
                            continue
                        col_name = col_name.replace('MIN', '', 1)
                        col_name = col_name.replace('MAX', '', 1)
                        response[col_name] = 1
                yield str(col_name)
        return

def isRangeCriteria(queue, name):
    ''' Returns True if the criteria 'name' is a range criteria in the DB.
    Returns False otherwise.
    '''
    criteria = getCriteria(queue, onlyUsed=False, strip=False)
    for crit in criteria:
        if crit.startswith('MIN'):
            if name == crit.replace('MIN', ''):
                return True

    return False

def getManifestCriteria(name, instance, queue, humanOutput=False,
                        onlyUsed=True):
    ''' Returns the criteria (as a subset of used criteria) for a particular
    manifest given (human output returns HEX() for mac opposed to byte output)
    '''
    query_str = "SELECT "
    for crit in getCriteria(queue, onlyUsed=onlyUsed, strip=False):
        if str(crit).endswith('mac') and humanOutput:
            query_str += "HEX(" + str(crit) + ") AS " + str(crit) + ", "
        else:
            query_str += str(crit) + ", "
    else:
        if getCriteria(queue, onlyUsed=onlyUsed, 
                       strip=False).next() is not None:
            query_str = query_str[:-2]
        else:
            raise AssertionError(_("Database contains no criteria!"))
    query_str += ' FROM manifests WHERE name = "' + name + \
                 '" AND instance = "' + str(instance) + '"'
    query = DBrequest(query_str)
    queue.put(query)
    query.waitAns()
    return query.getResponse()[0]

def findManifest(criteria, db):
    ''' Provided a criteria dictionary, findManifest returns a query
    response containing a single manifest (or 0 if there are no matching
    manifests).
    '''
    # If we didn't get any criteria, bail providing no manifest
    if len(criteria) == 0:
        return 0

    # create list of criteria that are set in the db
    criteria_set_in_db = list(getCriteria(db.getQueue(), strip=False))

    # generate query string to obtain best match and
    # then make the db request
    query_str = build_query_str(criteria, criteria_set_in_db)
    if not query_str:
        return 0
    query = DBrequest(query_str)
    db.getQueue().put(query)
    query.waitAns()

    response = query.getResponse()

    if response and len(response) == 1:    # got a manifest
        return response[0]['name']
    else:                     # didn't get a manifest
        return 0
        
def build_query_str(criteria, criteria_set_in_db):
    '''  build a query to find out which manifest is the best
    match for the client, based on criteria set in the db.
    Args: 
        criteria: dictionary of client criteria
        criteria_set_in_db: list of unstripped criteria currently set in the db
    Returns: query string or 0 if there is an error
    '''

    # Save range values as either 1 or 0 for ORDERing purposes.
    # If either the MIN or MAX field in the db is non-NULL (if
    # unbounded, the MIN or MAX is NULL), then the "_val"
    # variable is set to 1. Otherwise, it is set to 0.
    # This allows for criteria that can be a range or an exact
    # value to be weighted equally during the ORDERing process
    # for manifests that have criteria set.
    # COALESCE returns a copy of its first non-NULL argument, or 
    # NULL if all arguments are NULL.
    query_str = ("SELECT name, "
                 "(COALESCE(MAXmac, MINmac) IS NOT NULL) as mac_val, "
                 "(COALESCE(MAXipv4, MINipv4) IS NOT NULL) as ipv4_val, "
                 "(COALESCE(MAXnetwork, MINnetwork) IS NOT NULL) as net_val, "
                 "(COALESCE(MAXmem, MINmem) IS NOT NULL) as mem_val "
                 "FROM manifests WHERE ")

    # Set up search for all manifest matches in the db and then add ORDER
    # clause to select the best match. 

    # For each criterion, add clause to match either on that criterion 
    # or NULL
    for crit in criteria_set_in_db:
        try:
            if crit.startswith("MIN"):
                critval = sanitizeSQL(criteria[crit.replace('MIN', '', 1)])
                if crit.endswith("mac"):
                    # setup a clause like (HEX(MINmac) <= HEX(x'F00')) OR
                    # MINMAC is NULL
                    query_str += "(HEX(" + crit + ") <= HEX(x'" + \
                                 critval + "') OR " + crit + " IS NULL) AND "
                else:
                    # setup a clause like crit <= value OR crit IS NULL AND
                    query_str += "(" + crit + " <= " + critval + \
                                 " OR " + crit + " IS NULL) AND "
                             
            elif crit.startswith("MAX"):
                critval = sanitizeSQL(criteria[crit.replace('MAX', '', 1)])
                if crit.endswith("mac"):
                    # setup a clause like (HEX(MAXmac) >= HEX(x'F00')) OR
                    # MAXmac is NULL
                    query_str += "(HEX(" + crit + ") >= HEX(x'" + critval + \
                                 "') OR " + crit + " IS NULL) AND "
                else:
                    # setup a clause like crit <= value
                    query_str += "(" + crit + " >= " + critval + \
                                 " OR " + crit + " IS NULL) AND "
    
            else:
                # store single values in lower case
                # setup a clause like crit = lower(value)
                query_str += "(" + crit + " " + "= LOWER('" + \
                             sanitizeSQL(criteria[crit]) + "') OR " + \
                             crit + " IS NULL) AND "
        except KeyError:
            print _("Missing criteria: %s; returning 0") % crit
            return 0

    # remove extraneous "AND "
    query_str = query_str[:-4]

    # ORDER so that the best match is first.  Use LIMIT to select 
    # that manifest, if multiple manifests match.
    # Precedence order is:
    #    mac_val, ipv4_val, platform, arch, cpu, net_val, mem_val

    query_str += ("ORDER BY "
                  "mac_val desc, ipv4_val desc, " 
                  "platform desc, arch desc, cpu desc, " 
                  "net_val desc, mem_val desc LIMIT 1")
    return query_str

def formatValue(key, value):
    ''' Format and stringify database values.

    Args:
      key: a database criterion key.  Starting "MIN" and "MAX" are stripped
            off to get the type of datum the key represents.
            The following user-friendly output formatting is done:
            - mac addresses have colons added.
            - IP addresses have dots added and leading 0's stripped.
            - memory sizes have "MB" added to the end.
            - All other criteria types are stringified only.

      value: The raw database value to format and stringify.

    Returns: a nicely-readable string representing the value. If value is none
             returns none

    Raises: N/A
    '''
    key = key.strip()
    key = key.replace("MIN", "", 1)
    key = key.replace("MAX", "", 1)
    if (key == "mac" and value):
        # Note: MAC addresses are already strings.
        ret = value[0:2] + ":" + value[2:4] + ":" + \
              value[4:6] + ":" + value[6:8] + ":" + \
              value[8:10] + ":" + value[10:12]
    elif (key == "ipv4" and value):
        svalue = "%12.12d" % long(value)
        ret = str(int(svalue[0:3])) + "." + \
              str(int(svalue[3:6])) + "." + \
              str(int(svalue[6:9])) + "." + \
              str(int(svalue[9:12]))
    elif (key == "mem" and value):
        ret = str(value) + " MB"
    else:
        ret = str(value)
    return ret

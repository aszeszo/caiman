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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# beadm - The Boot Environment Administration tool. Use this CLI to
# manage boot environments.
#

import getopt
import gettext
import string
import os
import sys
import shutil
import traceback
import datetime
import time
import random
import subprocess

from osol_install.beadm.BootEnvironment import *
import libbe as lb
import osol_install.beadm.messages as msg

#import dumper
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
	print >> sys.stderr, ("""
Usage:
	beadm subcommand cmd_options

	subcommands:
	
	beadm activate beName
	beadm create [-a] [-d description]
	    [-e non-activeBeName | beName@snapshot]
	    [-o property=value] ... [-p zpool] beName
	beadm create beName@snapshot
	beadm destroy [-fF] beName | beName@snapshot
	beadm list [[-a] | [-d] [-s]] [-H] [beName]
	beadm mount beName mountpoint
	beadm rename beName newBeName
	beadm unmount [-f] beName""")
	sys.exit(1)	


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Public Command Line functions described in beadm(1)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def activate(opts):

	""" Function:    activate 

		Description: Activate a Boot Environment.The following is the
		             subcommand, options and args that make up the
		             opts object passed in:

		Parameters:
		    opts - A string containing the active subcommand

		Returns:
		    0 - Success
		    1 - Failure
	"""

	if len(opts) != 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()
	
	be = BootEnvironment()
		
	rc = lb.beActivate(opts[0])
	if rc == 0:
		return 0

	be.msgBuf["0"] = opts[0]
	if rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST, opts[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_ACTIVATE, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_ACTIVATE, be.msgBuf, -1)
	return 1
	

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create(opts):

	""" Function:    create 

		Description: Create a Boot Environment. The following is the
		             subcommand, options and args that make up the
		             opts object passed in:

		             create [-a] [-d description]
		                [-e non-activeBeName | beName@Snapshot]
		                [-o property=value] ... [-p zpool] beName

		             create beName@Snapshot

		Parameters:
		    opts - A object containing the create subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""

	be = BootEnvironment()
	
	activate = False

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts,
		    "ad:e:o:p:")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	# Counters for detecting multiple options.
	# e.g. beadm create -p rpool -p rpool2 newbe
	numAOpts = 0; numEOpts = 0; numPOpts = 0; numDOpts = 0

	for opt, arg in optsArgs:
		if opt == "-a":
			activate = True
			numAOpts += 1
		elif opt == "-e":
			be.srcBeNameOrSnapshot = arg
			numEOpts += 1
		elif opt == "-o":
			key, value = arg.split("=")
			be.properties[key] = value
		elif opt == "-p":
			be.trgtRpool = arg
			numPOpts += 1
		elif opt == "-d":
			be.description = arg
			numDOpts += 1

	if numAOpts > 1 or numEOpts > 1 or numPOpts > 1 or numDOpts > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	# Check that all info provided from the user is legitimate.
	if (verifyCreateOptionsArgs(be) != 0):
		usage()
	
	if initBELog("create", be) != 0:
		return 1
	
	msg.printMsg(msg.Msgs.BEADM_MSG_BE_CREATE_START,
	    be.trgtBeNameOrSnapshot[0], be.logID)
	
	if be.trgtBeNameOrSnapshot[0].find("@") != -1:
		# Create a snapshot
		rc = createSnapshot(be)
	else:
		# Create a BE based on a snapshot
		if be.srcBeNameOrSnapshot != None and \
		    be.srcBeNameOrSnapshot.find("@") != -1:
			# Create a BE from a snapshot
			rc = createBEFromSnapshot(be)
		else:
			rc = createBE(be)

		# Activate the BE if the user chose to.
		if activate and rc == 0:
			rc = activateBE(be)
	cleanupBELog(be)
		
	return rc
		
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def destroy(opts):

	""" Function:    destroy 

		Description: Destroy a Boot Environment. The following is the
		             subcommand, options and args that make up the
		             opts object passed in:

		             destroy [-fF] beName | beName@snapshot

		Parameters:
		    opts - A object containing the destroy subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""

	force_unmount = 0
	suppress_prompt = False
	beActiveOnBoot = None
	be = BootEnvironment()

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts, "fF")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	# Counters for detecting multiple options.
	# e.g. beadm destroy -f -f newbe
	numFOpts = 0; numfOpts = 0;

	for opt, arg in optsArgs:
		if opt == "-f":
			force_unmount = 1
			numfOpts += 1
		elif opt == "-F":
			suppress_prompt = True
			numFOpts += 1

	if numfOpts > 1 or numFOpts > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	if len(be.trgtBeNameOrSnapshot) != 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	# Get the 'active' BE and the 'active on boot' BE.
	beActive, beActiveOnBoot = \
	    getActiveBEAndActiveOnBootBE(be.trgtBeNameOrSnapshot[0])
	
	# If the user is trying to destroy the 'active' BE then quit now.
	if beActive == be.trgtBeNameOrSnapshot[0] and \
	    be.trgtBeNameOrSnapshot[0].find("@") == -1:
		be.msgBuf["0"] = be.msgBuf["1"] = beActive
		msg.printMsg(msg.Msgs.BEADM_ERR_DESTROY_ACTIVE, be.msgBuf, -1)
		return 1

	if not suppress_prompt:

		# Display a destruction question and wait for user response.
		# Quit if negative user response.

		if not displayDestructionQuestion(be): return 0

	if be.trgtBeNameOrSnapshot[0].find("@") != -1:

		# Destroy a snapshot.

		beName, snapName = be.trgtBeNameOrSnapshot[0].split("@")
		rc = lb.beDestroySnapshot(beName, snapName)
	else:

		# Destroy a BE.  Passing in 1 for the second arg destroys
		# any snapshots the BE may have as well.

		rc = lb.beDestroy(be.trgtBeNameOrSnapshot[0], 1, force_unmount)

		# Check if the BE that was just destroyed was the
		# 'active on boot' BE. If it was, display a message letting
		# the user know that the 'active' BE is now also the
		# 'active on boot' BE.
		if beActiveOnBoot == be.trgtBeNameOrSnapshot[0] and rc == 0:
			msg.printMsg(msg.Msgs.BEADM_MSG_ACTIVE_ON_BOOT,
			    beActive, -1)

	if rc == 0:
		try:
			shutil.rmtree("/var/log/beadm/" + \
			    be.trgtBeNameOrSnapshot[0], True)
		except:
			msg.printMsg(msg.Msgs.BEADM_ERR_LOG_RM,
			    "/var/log/beadm/" + be.trgtBeNameOrSnapshot[0], -1)

		return 0

	be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
	if rc == msg.Msgs.BE_ERR_MOUNTED:
		be.msgBuf["1"] = be.msgBuf["2"] = be.trgtBeNameOrSnapshot[0]
		msg.printMsg(msg.Msgs.BEADM_ERR_MOUNTED, be.msgBuf, -1)
		return 1
	elif rc == msg.Msgs.BE_ERR_DESTROY_CURR_BE:
		msg.printMsg(msg.Msgs.BEADM_ERR_DESTROY_ACTIVE, \
		be.msgBuf["0"], -1)
		return 1
	elif rc == msg.Msgs.BE_ERR_ZONES_UNMOUNT:
		be.msgBuf["1"] = be.trgtBeNameOrSnapshot[0]
		msg.printMsg(msg.Msgs.BE_ERR_ZONES_UNMOUNT, be.msgBuf, -1)
		return 1
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_DESTROY, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)
			    
	msg.printMsg(msg.Msgs.BEADM_ERR_DESTROY, be.msgBuf, -1)
	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def list(opts):

	""" Function:    list 

		Description: List the attributes of a Boot Environment.
		             The following is the subcommand, options
		             and args that make up the opts object
		             passed in:

		             list [[-a] | [-d] [-s]] [-H] [beName]
		       
		             -a displays all info
		             -d displays BE info plus dataset info
		             -s displays BE info plus snapshot info
		             -H displays info parsable by a computer 

		Parameters:
		    opts - A object containing the list subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""

	be = BootEnvironment()
	
	listAllAttrs = ""
	listDatasets = ""
	listSnapshots = ""
	dontDisplayHeaders = False
	beName = None
	beList = None
	
	# Counters for detecting multiple options.
	# e.g. beadm list -a -a newbe
	numAOpts = 0; numDOpts = 0; numSOpts = 0; numHOpts = 0

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts, "adHs")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	for opt, arg in optsArgs:
		if opt == "-a":
			listAllAttrs = opt
			numAOpts += 1
		elif opt == "-d":
			listDatasets = opt
			numDOpts += 1
		elif opt == "-s":
			listSnapshots = opt
			numSOpts += 1
		elif opt == "-H":
			dontDisplayHeaders = True
			numHOpts += 1

	if numAOpts > 1 or numDOpts > 1 or numSOpts > 1 or numHOpts > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	if len(be.trgtBeNameOrSnapshot) > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	if len(be.trgtBeNameOrSnapshot) == 1:
		beName = be.trgtBeNameOrSnapshot[0]

	if (listAllAttrs == "-a" and (listDatasets == "-d" \
	    or listSnapshots == "-s")):
		msg.printMsg(msg.Msgs.BEADM_ERR_MUTUALLY_EXCL,
		    listAllAttrs + " " + listDatasets + " " +
		    listSnapshots, -1)
		usage()

	listOptions = ""

	# When zones are implemented add "listZones == "-z" below

	# Coelesce options to pass to displayBEs

	if (listDatasets == "-d" and listSnapshots == "-s" or \
	    listAllAttrs == "-a"):
		listOptions = "-a"
	elif listDatasets != "" or listSnapshots != "" or listAllAttrs != "":
		listOptions = listDatasets + " " + listSnapshots

	rc, beList = lb.beList()
	if rc != 0:
		if rc == msg.Msgs.BE_ERR_BE_NOENT:
			if beName == None:
				msg.printMsg(msg.Msgs.BEADM_ERR_NO_BES_EXIST,
				    None, -1);
				return 1

			str = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
			    beName)
		else:
			str = lb.beGetErrDesc(rc)
			if str == None:
				str = \
				    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

		msg.printMsg(msg.Msgs.BEADM_ERR_LIST, str, -1)
		return 1

	# classify according to command line options
	if listOptions.find("-a") != -1 or \
	    (listOptions.find("-d") != -1 and listOptions.find("-s") != -1):
		listObject = CompleteList(dontDisplayHeaders) #all
	elif listOptions.find("-d") != -1:
		listObject = DatasetList(dontDisplayHeaders) #dataset
	elif listOptions.find("-s") != -1:
		listObject = SnapshotList(dontDisplayHeaders) #snapshot
	else: listObject = BEList(dontDisplayHeaders) #only BE

	# use list method for object
	if listObject.list(beList, dontDisplayHeaders, beName) != 0:
		msg.printMsg(msg.Msgs.BEADM_ERR_LIST_DATA, None, -1)
		return 1
		
	return 0
			
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def mount(opts):

	""" Function:    mount 

		Description: Mount a Boot Environment on a directory.
		             The following is the subcommand, options
		             and args that make up the opts object
		             passed in:

		             mount beName [mountpoint]

		Parameters:
		    opts - A object containing the mount subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""
	
	be = BootEnvironment()

	mountpoint = None

	try:
		optlist, beName_mntPoint = getopt.getopt(opts, "")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	mountpointLen = len(beName_mntPoint)

	if mountpointLen != 2:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()
	else:
		# Check for leading / in mount point
		mountpoint = beName_mntPoint[1] 
		if mountpoint[0] != '/':
			msg.printMsg(msg.Msgs.BEADM_ERR_MOUNTPOINT,
			    mountpoint, -1)
			return 1

	rc = lb.beMount(beName_mntPoint[0], mountpoint)
	if rc == 0:
		return 0

	be.msgBuf["0"] = beName_mntPoint[0]
	if rc == msg.Msgs.BE_ERR_MOUNTED:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_MOUNT_EXISTS,
		    beName_mntPoint[0])
	elif rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
		    beName_mntPoint[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_MOUNT, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_MOUNT, be.msgBuf, -1)
	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def unmount(opts):
	
	""" Function:    unmount 

		Description: Unmount a Boot Environment.
		             The following is the subcommand, options
		             and args that make up the opts object
		             passed in:

		             unmount [-f] beName

		Parameters:
		    opts - A object containing the unmount subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""

	be = BootEnvironment()

	force_unmount = 0

	# Counter for detecting multiple options.
	# e.g. beadm unmount -f -f newbe
	numFOpts = 0

	try:
		optlist, args = getopt.getopt(opts, "f")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	for opt, arg in optlist:
		if opt == "-f":
			force_unmount = 1
			numFOpts += 1

	if numFOpts > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	if len(args) != 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	rc = lb.beUnmount(args[0], force_unmount)
	if rc == 0:
		return 0

	be.msgBuf["0"] = args[0]
	if rc == msg.Msgs.BE_ERR_UMOUNT_CURR_BE:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_UNMOUNT_ACTIVE,
		    args[0])
	elif rc == msg.Msgs.BE_ERR_UMOUNT_SHARED:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_SHARED_FS, args[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_UNMOUNT, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)
	
	msg.printMsg(msg.Msgs.BEADM_ERR_UNMOUNT, be.msgBuf, -1)
	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def rename(opts):
	
	""" Function:    rename

		Description: Rename the name of a Boot Environment.
		             The following is the subcommand, options
		             and args that make up the opts object
		             passed in:

		             rename beName newBeName

		Parameters:
		    opts - A object containing the mount subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""

	be = BootEnvironment()

	try:
		optlist, beNames = getopt.getopt(opts, "")
	except getopt.GetoptError:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	if len(beNames) != 2:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		usage()

	rc = lb.beRename(beNames[0], beNames[1])

	if rc == 0:
		return 0

	be.msgBuf["0"] = beNames[0]
	if rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
		    beNames[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_RENAME, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)	

	msg.printMsg(msg.Msgs.BEADM_ERR_RENAME, be.msgBuf, -1)
	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# End of CLI public functions
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Verify the options and arguments for the beadm create subcommand
          
def verifyCreateOptionsArgs(be):
	
	# Check valid BE names
		
	lenBEArgs = len(be.trgtBeNameOrSnapshot)
	if lenBEArgs < 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		return 1
	if lenBEArgs > 1:
		msg.printMsg(msg.Msgs.BEADM_ERR_OPT_ARGS, None, -1)
		idx = 0
		while lenBEArgs > idx:
			msg.printMsg(msg.Msgs.BEADM_MSG_FREE_FORMAT,
			    be.trgtBeNameOrSnapshot[idx], -1)
			idx += 1
		return 1
					
	return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parseCLI(CLIOptsArgs):

	gettext.install("beadm", "/usr/lib/locale")

 	if len(CLIOptsArgs) == 0:
		usage()
		
	subcommand = CLIOptsArgs[0]
	optsArgs = CLIOptsArgs[1:]
	
	if subcommand == "activate":
		rc = activate(optsArgs)
	elif subcommand == "create":
		rc = create(optsArgs)
	elif subcommand == "destroy":
		rc = destroy(optsArgs)
	elif subcommand == "list":
		rc = list(optsArgs)
	elif subcommand == "mount":
		rc = mount(optsArgs)
	elif subcommand == "rename":
		rc = rename(optsArgs)
	elif subcommand == "upgrade":
		rc = upgrade(optsArgs)
	elif subcommand == "unmount" or \
	    subcommand == "umount": #aliased for convenience
		rc = unmount(optsArgs)
	elif subcommand == "verify":
		rc = verify()
	else:
		msg.printMsg(msg.Msgs.BEADM_ERR_ILL_SUBCOMMAND,
		    subcommand, -1)
		usage()
		
	return(rc)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
	gettext.install("beadm", "/usr/lib/locale")

	if not isBeadmSupported():
		return(1)

	return(parseCLI(sys.argv[1:]))

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def initBELog(logId, be):
	# Format of the log
	# yyyymmdd_hhmmss - 20071130_140558
	# yy - year;   2007
	# mm - month;  11
	# dd - day;    30
	# hh - hour;   14
	# mm - minute; 05
	# ss - second; 58

	# /var/log/beadm/<beName>/<logId>.log.<yyyymmdd_hhmmss>

	date = time.strftime("%Y%m%d_%H%M%S", time.localtime())
	
	be.log = "/var/log/beadm/" + be.trgtBeNameOrSnapshot[0] + \
	    "/" + logId + ".log" + "." + date
		
	if not os.path.isfile(be.log) and not os.path.islink(be.log):
		if not os.path.isdir(os.path.dirname(be.log)):
			try:
				os.makedirs(os.path.dirname(be.log), 0644)
			except OSError, (errno, strerror):
				be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
				be.msgBuf["1"] = \
				    msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS,
				    0)
				msg.printMsg(msg.Msgs.BEADM_ERR_CREATE,
				    be.msgBuf, -1)
				return 1
		try:
			be.logID = open(be.log, "a")
		except IOError:
			msg.printMsg(msg.Msgs.BEADM_ERR_LOG_CREATE,
			    None, -1)
			return 1
	else:
		# Should never happen due to new time stamp each call
		msg.printMsg(msg.Msgs.BEADM_ERR_LOG_CREATE, None, -1)
		return 1
			
	return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanupBELog(be):

	be.logID.close()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def displayDestructionQuestion(be):

	# Display a destruction question and wait for user response.

	msg.printMsg(msg.Msgs.BEADM_MSG_DESTROY, be.trgtBeNameOrSnapshot[0], -1)
	while 1:
		try:
			value = raw_input().strip().upper()
		except KeyboardInterrupt:
			return False
		except:
			raise
		if len(value) > 0 and (value == 'Y' or value == 'YES'):
			return True
		elif len(value) == 0 or value == 'N' or value == 'NO':
			msg.printMsg(msg.Msgs.BEADM_MSG_DESTROY_NO,
			    be.trgtBeNameOrSnapshot[0], -1)
			return False
		else:
			msg.printMsg(msg.Msgs.BEADM_ERR_INVALID_RESPONSE,
			    -1)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def setMaxColumnWidths(beMW, dsMW, ssMW, beList):

	# Figure out max column widths for BE's, Datasets and Snapshots

	for idx in range(len(beList)):
		if beList[idx].get("orig_be_name") != None:
			determineMaxBEColWidth(beList[idx], beMW)
		if beList[idx].get("dataset") != None:
			determineMaxDSColWidth(beList[idx], dsMW)
		if beList[idx].get("snap_name") != None:
			determineMaxSSColWidth(beList[idx], ssMW)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Return the 'active on boot' BE, the 'active' BE or None.

def getActiveBEAndActiveOnBootBE(trgtBEName):

	activeBE = None
	activeBEOnBoot = None
	
	rc, beList = lb.beList()

	if rc != 0:
		if rc == msg.Msgs.BE_ERR_BE_NOENT:
			str = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
			    trgtBEName)
		else:
			str = lb.beGetErrDesc(rc)
			if str == None:
				str = \
				    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

		msg.printMsg(msg.Msgs.BEADM_ERR_LIST, str, -1)
		return None
		
	for i, beVals in enumerate(beList):
		srcBeName = beVals.get("orig_be_name")
		if beVals.get("active"):
			activeBE = srcBeName
		if beVals.get("active_boot"):
			activeBEOnBoot = srcBeName
		if activeBE != None and activeBEOnBoot != None:
			break
	
	return activeBE, activeBEOnBoot

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Create a snapshot

def createSnapshot(be):

	beName, snapName = be.trgtBeNameOrSnapshot[0].split("@")
			
	rc, snapNameNotUsed = lb.beCreateSnapshot(beName, snapName)
	
	if rc == 0:
		return 0
	
	be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
	if rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
		    beName)
	elif rc == msg.Msgs.BE_ERR_SS_EXISTS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_SNAP_EXISTS,
		    be.trgtBeNameOrSnapshot[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, -1)

	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Create a BE

def createBE(be):

	rc, trgtBENameNotUsed, snapshotNotUsed = \
	    lb.beCopy(be.trgtBeNameOrSnapshot[0], be.srcBeNameOrSnapshot,
	        None, be.trgtRpool, be.properties, be.description)	

	if rc == 0:
		msg.printMsg(msg.Msgs.BEADM_MSG_BE_CREATE_SUCCESS,
		    be.trgtBeNameOrSnapshot[0], be.logID)
		return 0

	be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
	if rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST,
		    be.srcBeNameOrSnapshot)
	elif rc == msg.Msgs.BE_ERR_BE_EXISTS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_BE_EXISTS,
		    be.trgtBeNameOrSnapshot[0])
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, be.logID)

	return 1
	
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Create a BE based off a snapshot

def createBEFromSnapshot(be):
	
	beName, snapName = be.srcBeNameOrSnapshot.split("@")

	rc, trgtBENameNotUsed, snapshotNotUsed = \
	    lb.beCopy(be.trgtBeNameOrSnapshot[0], \
	    beName, snapName, be.trgtRpool, be.properties, be.description)
	
	if rc == 0:
		msg.printMsg(msg.Msgs.BEADM_MSG_BE_CREATE_SUCCESS,
		    be.trgtBeNameOrSnapshot[0], be.logID)
		return 0

	be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
	if rc == msg.Msgs.BE_ERR_SS_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_SNAP_DOES_NOT_EXISTS,
		    be.srcBeNameOrSnapshot)
	elif rc == msg.Msgs.BE_ERR_BE_EXISTS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_BE_EXISTS, \
		    be.trgtBeNameOrSnapshot[0])
	elif rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST, \
		    beName)
	elif rc == msg.Msgs.BE_ERR_PERM or rc == msg.Msgs.BE_ERR_ACCESS:
		be.msgBuf["1"] = msg.getMsg(msg.Msgs.BEADM_ERR_PERMISSIONS, rc)
		msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, -1)
		return 1
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_CREATE, be.msgBuf, be.logID)

	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Activate a BE. Called from create() when -a is provided as a CLI option.

def activateBE(be):

	rc = lb.beActivate(be.trgtBeNameOrSnapshot[0])
	if rc == 0:
		return 0		
		
	be.msgBuf["0"] = be.trgtBeNameOrSnapshot[0]
	if rc == msg.Msgs.BE_ERR_BE_NOENT:
		be.msgBuf["1"] = \
		    msg.getMsg(msg.Msgs.BEADM_ERR_BE_DOES_NOT_EXIST, opts[0])
	else:
		be.msgBuf["1"] = lb.beGetErrDesc(rc)
		if be.msgBuf["1"] == None:
			be.msgBuf["1"] = \
			    msg.getMsg(msg.Msgs.BEADM_ERR_NO_MSG, rc)

	msg.printMsg(msg.Msgs.BEADM_ERR_ACTIVATE, be.msgBuf, -1)
	
	return 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def isBeadmSupported():
	# Currently the only environment that beadm is supported in is
	# a global zone. Check that beadm is executing in a
	# global zone and not in a non-global zone.

	try:
		proc = subprocess.Popen("/sbin/zonename",
		    stdout = subprocess.PIPE,
		    stderr = subprocess.STDOUT)
		# Grab stdout.
		zonename = proc.communicate()[0].rstrip('\n')
	except OSError, (errno, strerror):
		msg.printMsg(msg.Msgs.BEADM_ERR_OS, strerror, -1)
		# Ignore a failed attempt to retreive the zonename.
		return True

	if zonename != "global":
		msg.printMsg(msg.Msgs.BEADM_ERR_NOT_SUPPORTED_NGZ, None, -1)
		return False

	return True

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
	try:
		rc = main()
	except SystemExit, e:
		raise e
	except:
		traceback.print_exc()
		sys.exit(99)
	sys.exit(rc)

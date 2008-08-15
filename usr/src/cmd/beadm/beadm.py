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

from beadm.BootEnvironment import *
import libbe as lb
import beadm.messages as msg

#import dumper
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
	print >> sys.stderr, ("""
Usage:
	beadm subcommand cmd_options

	subcommands:
	
	beadm activate beName
	beadm create [-a] [-e non-activeBeName | beName@snapshot]
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

	if len(opts) > 1 or len(opts) == 0:
		msg.msgs("errActivateOpts", None)
		usage()
		
	if lb.beActivate(opts[0]) != 0:
		msg.msgs("errActivate", opts[0])
		return(1)
	
	return(0)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create(opts):

	""" Function:    create 

		Description: Create a Boot Environment. The following is the
		             subcommand, options and args that make up the
		             opts object passed in:

		             create [-a] [-e non-activeBeName | beName@Snapshot]
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
	force = False
	beNameSnapName = None

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts, "ae:o:p:")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	for opt, arg in optsArgs:
		if opt == "-a":
			activate = True
		elif opt == "-e":
			be.srcBeNameOrSnapshot = arg
		elif opt == "-o":
			key, value = arg.split("=")
			be.properties[key] = value
		elif opt == "-p":
			be.trgtRpool = arg
			
	# Check that all info provided from the user is legitimate.
	if (verifyCreateOptionsArgs(be) != 0):
		usage()
	
	if initBELog("create", be) != 0:
		msg.msgs("errLogCreate")
		return (1)
	
	msg.msgs("msgCreateBEStart", be.trgtBeNameOrSnapshot[0], be.logID)

	if be.trgtBeNameOrSnapshot[0].find("@") != -1:

		# Create a snapshot

		beNameSnapName = be.trgtBeNameOrSnapshot[0].split("@")

		retList = lb.beCreateSnapshot(beNameSnapName[0], beNameSnapName[1])

		if retList[0] != 0:
			msg.msgs("errCreate", be.trgtBeNameOrSnapshot[0])
			cleanupBELog(be)
			return(1);
	else:

		# Create a new BE.

		if be.srcBeNameOrSnapshot != None and \
		    be.srcBeNameOrSnapshot.find("@") != -1:
			beNameSnapName = be.srcBeNameOrSnapshot.split("@")

			# Based off of a snapshot.

			ret, trgtBename, snapshot = \
			    lb.beCopy(be.trgtBeNameOrSnapshot[0], \
			    beNameSnapName[0], beNameSnapName[1], \
			    be.trgtRpool, be.properties)
			if ret != 0:
				msg.msgs("errCreate", be.trgtBeNameOrSnapshot[0])
				cleanupBELog(be)
				return(1);
			else:
				msg.msgs("msgCreateBESuccess", be.trgtBeNameOrSnapshot[0], be.logID)
		else:

			# Based off another BE.

			ret, trgtBename, snapshot = \
			    lb.beCopy(be.trgtBeNameOrSnapshot[0], \
			    be.srcBeNameOrSnapshot, \
			    None, be.trgtRpool, be.properties)
			if ret != 0:
				msg.msgs("errCreate", be.trgtBeNameOrSnapshot[0])
				cleanupBELog(be)
				return(1);
			else:
				msg.msgs("msgCreateBESuccess", be.trgtBeNameOrSnapshot[0], be.logID)	

		# Activate the BE if the user wants to.

		if activate:
			if lb.beActivate(be.trgtBeNameOrSnapshot[0]) != 0:
				msg.msgs("errActivate", be.trgtBeNameOrSnapshot[0])
				return(1);

	cleanupBELog(be)
		
	return(0)
		
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
		msg.msgs("errInvalidOptsArgs")
		usage()

	for opt, arg in optsArgs:
		if opt == "-f":
			force_unmount = 1
		elif opt == "-F":
			suppress_prompt = True
				

	if len(be.trgtBeNameOrSnapshot) == 0:
		msg.msgs("errNoBeNameSnapshot")
		usage()

	if not suppress_prompt:

		# Display a destruction question and wait for user response.
		# Quit if negative user response.

		if not displayDestructionQuestion(be): return 0

	if be.trgtBeNameOrSnapshot[0].find("@") != -1:

		# Destroy a snapshot.

		beNameSnapName = be.trgtBeNameOrSnapshot[0].split("@")
		rc = lb.beDestroySnapshot(beNameSnapName[0], \
		    beNameSnapName[1])
	else:

		# Check if the BE being destroyed is the 'active on boot' BE.
		# If it is, display a message letting the user know that the
		# current BE is now also the 'active on boot' BE.
		
		beActiveOnBoot = activeOnBootBE(be.trgtBeNameOrSnapshot[0])

		# Destroy a BE.  Passing in 1 for the second arg destroys
		# any snapshots the BE may have as well.

		rc = lb.beDestroy(be.trgtBeNameOrSnapshot[0], 1, force_unmount)

		if beActiveOnBoot != None:
			msg.msgs("activeOnBootBE", beActiveOnBoot)
		
	if rc != 0:
		msg.msgs("errDestroy", be.trgtBeNameOrSnapshot[0])
		return(1)
	else:
		try:
			shutil.rmtree("/var/log/beadm/" + \
			    be.trgtBeNameOrSnapshot[0], True)
		except:
			msg.msgs("errLogRm", "/var/log/beadm/" + \
			    be.trgtBeNameOrSnapshot[0])

	return(0)

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

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts, "adHs")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	for opt, arg in optsArgs:
		if opt == "-a":
			listAllAttrs = opt
		elif opt == "-d":
			listDatasets = opt
		elif opt == "-s":
			listSnapshots = opt
		elif opt == "-H":
			dontDisplayHeaders = True

	if len(be.trgtBeNameOrSnapshot) > 1:
		msg.msgs("errInvalidOptsArgs")
		usage()

	if len(be.trgtBeNameOrSnapshot) == 1:
		beName = be.trgtBeNameOrSnapshot[0]

	if (listAllAttrs == "-a" and (listDatasets == "-d" \
	    or listSnapshots == "-s")):
		msg.msgs("errMutuallyExlusive", listAllAttrs + " " + \
			 listDatasets + " " + listSnapshots)
		usage()

	listOptions = ""

	# When zones are implemented add "listZones == "-z" below

	# Coelesce options to pass to displayBEs

	if (listDatasets == "-d" and listSnapshots == "-s" or \
	    listAllAttrs == "-a"):
		listOptions = "-a"
	elif listDatasets != "" or listSnapshots != "" or listAllAttrs != "":
		listOptions = listDatasets + " " + listSnapshots

	beList = lb.beList()

	if beList == None:
		msg.msgs("errList")
		return(1)

	# classify according to command line options
	if listOptions.find("-a") != -1 or \
	    (listOptions.find("-d") != -1 and listOptions.find("-s") != -1):
		listObject = CompleteList() #all
	elif listOptions.find("-d") != -1:
		listObject = DatasetList() #dataset
	elif listOptions.find("-s") != -1:
		listObject = SnapshotList() #snapshot
	else: listObject = BEList() #only BE

	# use list method for object
	if listObject.list(beList, dontDisplayHeaders, beName) != 0:
		msg.msgs("errList")
		return(1)
	return(0)
			
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
	
	mountpoint = None

	try:
		optlist, beName_mntPoint = getopt.getopt(opts, "")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	mountpointLen = len(beName_mntPoint)

	if mountpointLen == 0 or mountpointLen > 2:
		msg.msgs("errInvalidOptsArgs")
		usage()
		
	if mountpointLen == 2:
		# Check for leading / in mount point
		mountpoint = beName_mntPoint[1] 
		if mountpoint[0] != '/':
			msg.msgs("errMountpoint", mountpoint)
			return(1);

	if lb.beMount(beName_mntPoint[0], mountpoint) != 0:
	    msg.msgs("errMountFailed", beName_mntPoint[0])
	    return(1)

	return(0);

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

	force_unmount = 0

	try:
		optlist, args = getopt.getopt(opts, "f")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	for opt, arg in optlist:
		if opt == "-f":
			force_unmount = 1
			
	if len(args) != 1:
		msg.msgs("errInvalidOptsArgs")
		usage()

	if lb.beUnmount(args[0], force_unmount) != 0:
	    msg.msgs("errUnMountFailed", args[0])
	    return(1)
	
	return(0);

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
	
	try:
		optlist, beNames = getopt.getopt(opts, "")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	if len(beNames) != 2:
		msg.msgs("errInvalidOptsArgs")
		usage()

	if lb.beRename(beNames[0], beNames[1]) != 0:
		msg.msgs("errRenameFailed", beNames[0])
		return(1)
	
	return (0);

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# End of CLI public functions
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Verify the options and arguments for the beadm create subcommand
          
def verifyCreateOptionsArgs(be):
	
	# Check valid BE names
		
	lenBEArgs = len(be.trgtBeNameOrSnapshot)

	if lenBEArgs < 1:
		msg.msgs("errInvalidOptsArgs")
		return(1)

	if lenBEArgs > 1:
		msg.msgs("errInvalidOptsArgs")
		idx = 0
		while lenBEArgs > idx:
			msg.msgs("", be.trgtBeNameOrSnapshot[idx])
			idx += 1
		return(1)
					
	return(0)

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
		msg.msgs("errIllSubcommand", subcommand)
		usage()
		
	return(rc)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
	gettext.install("beadm", "/usr/lib/locale")

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
				msg.msgs("osErr", strerror)
				return(1)
		try:
			be.logID = open(be.log, "a")
		except IOError:
			msg.msgs("errLogCreate")
			return(1)
	else:
		# Should never happen due to new time stamp each call
		msg.msgs("errLogCreate")
		return(1)
			
	return(0)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanupBELog(be):

	be.logID.close()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def displayDestructionQuestion(be):

	# Display a destruction question and wait for user response.

	msg.msgs("destroyQuestion", be.trgtBeNameOrSnapshot[0])
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
			msg.msgs("destroyNo", be.trgtBeNameOrSnapshot[0])
			return False
		else:
			msg.msgs("errInvalidResponse")

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
# Determine if trgtBEName is 'active on boot'. If it is, return the
# name of currently active BE else return None

def activeOnBootBE(trgtBEName):

	activeBE = None
	beList = lb.beList()
	
	if beList == None:
		msg.msgs("errList")
		return(None)
		
	for i, beVals in enumerate(beList):
		srcBeName = beVals.get("orig_be_name")
		if beVals.get("active"):
			activeBE = srcBeName
		if srcBeName != trgtBEName:
			continue
		if beVals.get("active_boot"):
			return activeBE

	return None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
	try:
		ret = main()
	except SystemExit, e:
		raise e
	except:
		traceback.print_exc()
		sys.exit(99)
	sys.exit(ret)

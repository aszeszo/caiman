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
	beadm destroy [-f] beName | beName@snapshot
	beadm list [[-a] | [-d] [-s]] [-H] [beName]
	beadm mount beName mountpoint
	beadm rename beName newBeName
	beadm unmount beName""")
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

			try:
				lb.beCopy(be.trgtBeNameOrSnapshot[0], \
				    beNameSnapName[0], beNameSnapName[1], \
				    be.trgtRpool, be.properties)
			except:
				msg.msgs("errCreate", be.trgtBeNameOrSnapshot[0])
				cleanupBELog(be)
				return(1);
			else:
				msg.msgs("msgCreateBESuccess", be.trgtBeNameOrSnapshot[0], be.logID)
		else:

			# Based off another BE.

			try:
				lb.beCopy(be.trgtBeNameOrSnapshot[0], be.srcBeNameOrSnapshot, \
				None, be.trgtRpool, be.properties)
			except:
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

		             destroy [-f] beName | beName@snapshot

		Parameters:
		    opts - A object containing the destroy subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""
	
	force = False
	be = BootEnvironment()

	try:
		optsArgs, be.trgtBeNameOrSnapshot = getopt.getopt(opts, "f")
	except getopt.GetoptError:
		msg.msgs("errInvalidOptsArgs")
		usage()

	for opt, arg in optsArgs:
		if opt == "-f":
			force = True

	if len(be.trgtBeNameOrSnapshot) == 0:
		msg.msgs("errNoBeNameSnapshot")
		usage()

	if not force:

		# Display a destruction question and wait for user response.

		displayDestructionQuestion(be)

	if be.trgtBeNameOrSnapshot[0].find("@") != -1:

		# Destroy a snapshot.

		beNameSnapName = be.trgtBeNameOrSnapshot[0].split("@")
		rc = lb.beDestroySnapshot(beNameSnapName[0], \
		    beNameSnapName[1])
	else:

		# Destroy a BE.

		rc = lb.beDestroy(be.trgtBeNameOrSnapshot[0])

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

	if displayBEs(beList, dontDisplayHeaders, listOptions, beName) != 0:
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
		opts, beName_mntPoint = getopt.getopt(opts, "")
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

		             umount beName

		Parameters:
		    opts - A object containing the unmount subcommand
		           and all the options and arguments passed in
		           on the command line mentioned above.

		Returns:
		    0 - Success
		    1 - Failure
	"""
	
	if len(opts) != 1 or len(opts) == 0:
		msg.msgs("errInvalidOptsArgs")
		usage()
	
	if opts[0][0] == '/':
		msg.msgs("errUnmountArg", opts[0])
		usage()

	if lb.beUnmount(opts[0]) != 0:
	    msg.msgs("errUnMountFailed", opts[0])
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
		opts, beNames = getopt.getopt(opts, "")
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
	elif subcommand == "unmount":
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
# Determine the BE's to display. Call the formatting function that
# produces the output. The -H option produces the following:

# Display BE info in a condensed manner
#   BE1:yes:no:active:rpool/ROOT/BE1:5.4G;
#   BE1/opt:unmounted::55M;
#   BE1@test:static:2008-03-30 13:41:03;
#	BE2:no:no:mounted:rpool/ROOT/BE2:6.2G;;;

#   The ';' delimits BE's, Datasets and Snapshots. 
#   The ':' delimits attributes for BE's, Datasets and Snapshots.
#   The ',' delimits multiple Datasets and Snapshots.
#   Multiple BE's are delimited with a carriage return.

# A non -H option produces the following:

# BE       Active Active on Status  Dataset         Mountpoint  Space 
# Name            reboot                                        Used 
# ----     ------ --------- ------  --------        ----------  -----
# BE1      yes    no        active  rpool/ROOT/BE1  legacy      5.4G

#   Datasets Status    Mountpoint    Space Used 
#   -------- ------    ----------    ---------- 
#   BE1/opt  unmounted legacy        55M

#   Snapshots Policy    Date                  
#   --------  --------- ----                  
#   BE1@test  static    2008-03-30 13:41:03 
# 
# BE   Active Active on Status  Dataset        Mountpoint Space 
# Name        reboot                                      Used 
# ---- ------ --------- ------  --------       ---------- -----
# BE2  no     no        mounted rpool/ROOT/BE2 legacy     6.2G

def displayBEs(beList, ddh, listOptions, beName):

	# Initialize display objects.

	beMW = BEMaxWidths()
	dsMW = DatasetMaxWidths()
	ssMW = SnapshotMaxWidths()
	beDA = BEDisplayAttrs()

	pool = None
	found = False

	# See if BE name exists
	if beName != None:
		found = False
		for idx in range(len(beList)):
			if beList[idx].get("orig_be_name") == beName:
				found = True
				pool = beList[idx].get("orig_be_pool")
				break

		if not found:
			msg.msgs("errBEName", beName)
			return(1)

	setMaxColumnWidths(beMW, dsMW, ssMW, beList)
	
	# Determine how to display the output

	be = str(random.random())

	beHeader = True
	dsHeader = True
	ssHeader = True

	for idx in range(len(beList)):

		# Display info for a single BE

		if beName != None:
			if beList[idx].get("orig_be_name") == beName:
				be = beName
				dsHeader = True
				ssHeader = True
				if beHeader and not ddh : print
				formatBEOutput(beList[idx], beHeader, \
				    ddh, beMW, beDA)
				pool = beList[idx].get("orig_be_pool")
				if listOptions == "":
					beHeader = False	
	
			if beList[idx].has_key("dataset") and \
			    beList[idx].get("dataset").find(be) == 0:
				if listOptions.find("-a") != -1 or \
				    listOptions.find("-d") != -1 or ddh:
					if dsHeader and not ddh: print
					formatDatasetOutput(beList[idx], \
					    pool, dsHeader, ddh, dsMW, beDA)
					if beList[idx].get("dataset").find(be) == 0:
						dsHeader = False			

			if beList[idx].has_key("snap_name") and \
			    beList[idx].get("snap_name").find(be) == 0:
				if listOptions.find("-a") != -1 or \
				    listOptions.find("-s") != -1 or ddh:
					if ssHeader and not ddh: print
					formatSnapshotOutput(beList[idx], \
					    ssHeader, ddh, ssMW, beDA)
					if beList[idx].get("snap_name").find(be) == 0:
						ssHeader = False
		else:

			# Display info for a all BE's

			if beList[idx].has_key("orig_be_name"):
				be = beList[idx].get("orig_be_name")
				if ddh:
					beDA.outStr = beDA.outStr + "\n"
				dsHeader = True
				ssHeader = True
				if beHeader and not ddh: print
				formatBEOutput(beList[idx], beHeader, \
				    ddh, beMW, beDA)
				pool = beList[idx].get("orig_be_pool")
				if listOptions == "":
					beHeader = False

			if beList[idx].has_key("dataset"):
				if listOptions.find("-a") != -1 or \
				    listOptions.find("-d") != -1 or ddh:
					if dsHeader and not ddh: print
					formatDatasetOutput(beList[idx], \
					    pool, dsHeader, ddh, dsMW, beDA)
					if beList[idx].get("dataset").find(be) == 0:
						dsHeader = False			

			if beList[idx].has_key("snap_name"):
				if listOptions.find("-a") != -1 or \
				    listOptions.find("-s") != -1 or ddh:
					if ssHeader and not ddh: print
					formatSnapshotOutput(beList[idx], ssHeader, \
					    ddh, ssMW, beDA)
					if beList[idx].get("snap_name").find(be) == 0:
						ssHeader = False			

	if ddh:
		print beDA.outStr

	return(0)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Determine largest column widths for BE attributes

def determineMaxBEColWidth(belist, beWidth):

	beDA = BEDisplayAttrs()

	for idx in range(len(beDA.BEkeys)):
		if idx == BEMaxWidths.BENAME:
			# Calculate column width for the BE name

			beNameHeaderLen = \
			    len(beDA.BEheader2[BEMaxWidths.BENAME]) 
			origBeNameLen = \
			    len(belist.get(beDA.BEkeys[BEMaxWidths.BENAME]))

			if beNameHeaderLen > origBeNameLen \
			     and beNameHeaderLen > beWidth.beName:
				beWidth.beName = beNameHeaderLen
			elif beWidth.beName < origBeNameLen:
				beWidth.beName = origBeNameLen + 1

		elif idx == BEMaxWidths.ACTIVE:

			# Calculate column width for Active column

			beWidth.active = \
			    len(beDA.BEheader[BEMaxWidths.ACTIVE])

		elif idx == BEMaxWidths.ACTIVE_ON_REBOOT:

			# Calculate column width for Active on Reboot

			beWidth.activeOnBoot = \
			    len(beDA.BEheader[BEMaxWidths.ACTIVE_ON_REBOOT])

		elif idx == BEMaxWidths.STATUS:

			# Calculate column width for the status

			beWidth.status = len("mounted ")

		elif idx == BEMaxWidths.DATASET:

			# Calculate column width for the Dataset

			datasetHeaderLen = \
			    len(beDA.BEheader[BEMaxWidths.DATASET]) 
			datasetLen = \
			    len(belist.get(beDA.BEkeys[BEMaxWidths.DATASET]))

			if datasetHeaderLen > datasetLen \
			     and datasetHeaderLen > beWidth.dataset:
				beWidth.dataset = datasetHeaderLen
			elif beWidth.dataset < datasetLen:
				beWidth.dataset = datasetLen + 1

		elif idx == BEMaxWidths.MOUNTPOINT:

			# Calculate column width for the mountpoint 

			column = belist.get(beDA.BEkeys[BEMaxWidths.MOUNTPOINT])
			columnLen = len(column)
			columnHeaderLen = \
			    len(beDA.BEheader[BEMaxWidths.MOUNTPOINT])

			if column != "none":
				if columnHeaderLen > columnLen and \
					columnHeaderLen > beWidth.mountpoint:
					beWidth.mountpoint = columnHeaderLen
				elif beWidth.mountpoint < columnLen:
					beWidth.mountpoint = columnLen + 1
			else:
				beWidth.mountpoint = columnHeaderLen

		elif idx == BEMaxWidths.SPACE_USED:

			# Column width for the space used

			beWidth.spaceused = \
			    len(beDA.BEheader[BEMaxWidths.SPACE_USED])

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Display the BE's attributes.

def formatBEOutput(belist, headerFlag, ddh, beWidth, beDA):

	# Adjust the display by the widest column for each column and print
	# the results.

	outStr = ""
	tmpStr = ""
	headStr = ""
	headStr2 = ""
	headStr3 = ""
	
	delimMaj = ";"
	delimMin = ":"

	for idx in range(len(beDA.BEkeys)):

		if idx == BEMaxWidths.BENAME:

			# Construct BE name

			beName = belist.get(beDA.BEkeys[BEMaxWidths.BENAME])

			if ddh:
				outStr = beName + delimMin
			else:	
				outStr = beName.ljust(beWidth.beName)
				headStr = \
				    beDA.BEheader[BEMaxWidths.BENAME].ljust(beWidth.beName)
				headStr2 = \
				    beDA.BEheader2[BEMaxWidths.BENAME].ljust(beWidth.beName)
				headStr3 = \
				    beDA.BEheader3[BEMaxWidths.BENAME].ljust(beWidth.beName)
				
		elif idx == BEMaxWidths.ACTIVE:

			# Construct active value

			active = belist.get(beDA.BEkeys[BEMaxWidths.ACTIVE])

			if ddh:
				if active:
					outStr = outStr + "yes" + delimMin
				else:
					outStr = outStr + "no" + delimMin
			else:
				if active:
					outStr = outStr + "yes".ljust(beWidth.active)
				else:
					outStr = outStr + "no".ljust(beWidth.active)
	
				headStr = headStr + \
				    beDA.BEheader[BEMaxWidths.ACTIVE].ljust(beWidth.active)
				headStr2 = headStr2 + \
				    beDA.BEheader2[BEMaxWidths.ACTIVE].ljust(beWidth.active)
				headStr3 = headStr3 + \
				    beDA.BEheader3[BEMaxWidths.ACTIVE].ljust(beWidth.active)

		elif idx == BEMaxWidths.ACTIVE_ON_REBOOT:

			# Construct active on reboot value

			activeOnReboot = \
			    belist.get(beDA.BEkeys[BEMaxWidths.ACTIVE_ON_REBOOT])

			if ddh:
				if activeOnReboot:
					outStr = outStr + "yes" + delimMin
				else:
					outStr = outStr + "no" + delimMin
			else:
				if activeOnReboot:
					outStr = outStr + "yes".ljust(beWidth.activeOnBoot)
				else:
					outStr = outStr + "no".ljust(beWidth.activeOnBoot)
	
				headStr = headStr + \
				    beDA.BEheader[BEMaxWidths.ACTIVE_ON_REBOOT].ljust(beWidth.activeOnBoot)
				headStr2 = headStr2 + \
				    beDA.BEheader2[BEMaxWidths.ACTIVE_ON_REBOOT].ljust(beWidth.activeOnBoot)
				headStr3 = headStr3 + \
				    beDA.BEheader3[BEMaxWidths.ACTIVE_ON_REBOOT].ljust(beWidth.activeOnBoot)

		elif idx == BEMaxWidths.STATUS:

			# Construct status value

			activeRef = belist.get(beDA.BEkeys[BEMaxWidths.ACTIVE])
			mountRef = belist.get(beDA.BEkeys[BEMaxWidths.MOUNTED])

			if ddh:
				if activeRef:
					outStr = outStr + "active" + delimMin
				elif mountRef:
					outStr = outStr + "mounted" + delimMin
				else:
					outStr = outStr + '-' + delimMin
			else:
				if activeRef:
					outStr = outStr + "active".ljust(beWidth.status)
				elif mountRef:
					outStr = outStr + "mounted".ljust(beWidth.status)
				else:
					outStr = outStr + '-'.ljust(beWidth.status)
					
				headStr = headStr + \
				    beDA.BEheader[BEMaxWidths.STATUS].ljust(beWidth.status)
				headStr2 = headStr2 + \
				    beDA.BEheader2[BEMaxWidths.STATUS].ljust(beWidth.status)
				headStr3 = headStr3 + \
				    beDA.BEheader3[BEMaxWidths.STATUS].ljust(beWidth.status)

		elif idx == BEMaxWidths.DATASET:

			# Construct dataset value

			dataset = belist.get(beDA.BEkeys[BEMaxWidths.DATASET])

			if ddh:
				outStr = outStr + dataset + delimMin
			else:	
				outStr = outStr + dataset.ljust(beWidth.dataset)
				headStr = headStr + \
				    beDA.BEheader[BEMaxWidths.DATASET].ljust(beWidth.dataset)
				headStr2 = headStr2 + \
				    beDA.BEheader2[BEMaxWidths.DATASET].ljust(beWidth.dataset)
				headStr3 = headStr3 + \
				    beDA.BEheader3[BEMaxWidths.DATASET].ljust(beWidth.dataset)

		elif idx == BEMaxWidths.MOUNTPOINT:

			# Construct mountpoint value

			mountpoint = belist.get(beDA.BEkeys[BEMaxWidths.MOUNTPOINT])

			tmpStr = "-"
			if mountpoint != "none":
				tmpStr = mountpoint

			if ddh:
				outStr = outStr + tmpStr + delimMin
			else:
				outStr = outStr + tmpStr.ljust(beWidth.mountpoint)
					
				headStr = headStr + \
				    beDA.BEheader[BEMaxWidths.MOUNTPOINT].ljust(beWidth.mountpoint)
				headStr2 = headStr2 + \
				    beDA.BEheader2[BEMaxWidths.MOUNTPOINT].ljust(beWidth.mountpoint)
				headStr3 = headStr3 + \
				    beDA.BEheader3[BEMaxWidths.MOUNTPOINT].ljust(beWidth.mountpoint)

		elif idx == BEMaxWidths.SPACE_USED:

			# Construct space used  value

			spaceUsed = 0
			space = belist.get(beDA.BEkeys[BEMaxWidths.SPACE_USED])

			if space != "none":
				spaceUsed = getDisplayValue(space)
				if spaceUsed > beWidth.spaceused:
					width = len(spaceUsed)
				else:
					width = beWidth.spaceused

				if ddh:
					outStr = outStr + spaceUsed
				else:
					outStr = outStr + spaceUsed.ljust(width)
			else:
				if ddh:
					outStr = outStr + '-'
				else:
					width = beWidth.spaceused
					outStr = outStr + '-'.ljust(width)
				
			headStr = headStr + \
			    beDA.BEheader[BEMaxWidths.SPACE_USED].ljust(width)
			headStr2 = headStr2 + \
			    beDA.BEheader2[BEMaxWidths.SPACE_USED].ljust(width)
			headStr3 = headStr3 + \
			    beDA.BEheader3[BEMaxWidths.SPACE_USED].ljust(width)

	# Display headers

	if headerFlag and not ddh:
		print headStr
		print headStr2
		print headStr3

	# If headers are not to be displayed then append the output to
	# the BE object string. 

	if ddh:
		beDA.outStr += outStr
	else:
		print outStr

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Determine largest column widths for dataset attributes

def determineMaxDSColWidth(dsList, dsWidth):
	
	dsDA = DSDisplayAttrs()

	for idx in range(len(dsDA.DSkeys)):
		if idx == DatasetMaxWidths.DATASET:

			# Calculate column width for the Dataset name

			datasetHeaderLen = \
			    len(dsDA.DSheader[DatasetMaxWidths.DATASET])
			datasetLen = \
			    len(dsList.get(dsDA.DSkeys[DatasetMaxWidths.DATASET]))

			if datasetHeaderLen > datasetLen and \
			    datasetHeaderLen > dsWidth.dataset:
				dsWidth.dataset = datasetHeaderLen 
			elif dsWidth.dataset < datasetLen:
				dsWidth.dataset = datasetLen + 1

		elif idx == DatasetMaxWidths.STATUS:

			# Calculate column width for the Status
			
			dsWidth.status = len("unmounted ")
			
		elif idx == DatasetMaxWidths.MOUNTPOINT:

			# Calculate column width for the Mountpoint

			mountpointHeaderLen = \
			    len(dsDA.DSheader[DatasetMaxWidths.MOUNTPOINT])
			mountpointLen = \
			    len(dsList.get(dsDA.DSkeys[DatasetMaxWidths.MOUNTPOINT]))

			if mountpointHeaderLen > mountpointLen and \
			    mountpointHeaderLen > dsWidth.mountpoint:			
				dsWidth.mountpoint = mountpointHeaderLen 
			elif dsWidth.mountpoint < mountpointLen:
				dsWidth.mountpoint = mountpointLen + 1

		elif idx == DatasetMaxWidths.SPACE_USED:

			# Calculate column width for the Space Used

			spaceUsed = \
			    dsList.get(dsDA.DSkeys[DatasetMaxWidths.SPACE_USED])
			spaceUsedLen = \
			    len(getDisplayValue(spaceUsed))
			spaceUsedHeaderLen = \
			    len(dsDA.DSheader[DatasetMaxWidths.SPACE_USED])
			
			if spaceUsedHeaderLen > spaceUsedLen \
			   and spaceUsedHeaderLen > dsWidth.mountpoint:			
				dsWidth.spaceused = spaceUsedHeaderLen 
			elif dsWidth.spaceused < spaceUsedLen:
				dsWidth.spaceused = spaceUsedLen


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Display the dataset attributes.

def formatDatasetOutput(dsList, pool, headerFlag, ddh, dsWidth, beDA):

	outStr = ""
	tmpStr = ""
	headStr = ""
	headStr2 = ""

	delimMaj = ";"
	delimMin = ":"

	dsDA = DSDisplayAttrs()

	for idx in range(len(dsDA.DSkeys)):
		if idx == DatasetMaxWidths.DATASET:

			# Construct the dataset value

			dataset = dsList.get(dsDA.DSkeys[DatasetMaxWidths.DATASET])

			if ddh:
				if beDA.outStr[len(beDA.outStr) - 1] != '\n':
					beDA.outStr = beDA.outStr + delimMaj
				outStr = dataset + delimMin
			else:
				outStr = "   " + \
				    dataset.ljust(dsWidth.dataset)
				headStr = "   " + \
				    dsDA.DSheader[idx].ljust(dsWidth.dataset)
				headStr2 = "   " + \
				    dsDA.DSheader2[idx].ljust(dsWidth.dataset)

		elif idx == DatasetMaxWidths.STATUS:

			# Construct the status value

			status = dsList.get(dsDA.DSkeys[DatasetMaxWidths.MOUNTED])

			if ddh:
				if status:
					outStr = outStr + "mounted" + delimMin
				else:
					outStr = outStr + "unmounted" + delimMin
			else:
				if status:
					outStr = outStr + "mounted".ljust(dsWidth.status)
				else:
					outStr = outStr + "unmounted".ljust(dsWidth.status)
	
				headStr = headStr + \
				    dsDA.DSheader[DatasetMaxWidths.STATUS].ljust(dsWidth.status)
				headStr2 = headStr2 + \
				    dsDA.DSheader2[DatasetMaxWidths.STATUS].ljust(dsWidth.status)
	
		elif idx == DatasetMaxWidths.MOUNTPOINT:

			# Construct the mountpoint value

			mountpoint = dsList.get(dsDA.DSkeys[DatasetMaxWidths.MOUNTPOINT])

			if ddh:
				outStr = outStr + mountpoint + delimMin
			else:
				if mountpoint != "none":
					outStr = outStr + \
					    mountpoint.ljust(dsWidth.mountpoint)
				else:
					outStr = outStr + \
					    '-'.ljust(dsWidth.mountpoint)
					
				headStr = headStr + \
					dsDA.DSheader[idx].ljust(dsWidth.mountpoint)
				headStr2 = headStr2 + \
				    dsDA.DSheader2[idx].ljust(dsWidth.mountpoint)

		elif idx == DatasetMaxWidths.SPACE_USED:

			# Construct the space used value

			spaceUsed = 0
			space = dsList.get(dsDA.DSkeys[DatasetMaxWidths.SPACE_USED])

			if space != "none":
				spaceUsed = getDisplayValue(space)

				if len(spaceUsed) > dsWidth.spaceused:			
					width = len(spaceUsed) 
				else:
					width = dsWidth.spaceused

				outStr = outStr + spaceUsed.ljust(width)
			else:
				width = dsWidth.spaceused
				outStr = outStr + '-'.ljust(width)
				
			headStr = headStr + \
			    dsDA.DSheader[DatasetMaxWidths.SPACE_USED].ljust(width)
			headStr2 = headStr2 + \
			    dsDA.DSheader2[DatasetMaxWidths.SPACE_USED].ljust(width)

	# Display headers

	if headerFlag and not ddh:
		print headStr
		print headStr2

	# If headers are not to be displayed then append the output to
	# the datasets object string. 

	if ddh:
		beDA.outStr = beDA.outStr + outStr
	else:
		print outStr
	
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Determine largest column widths for snapshot attributes

def determineMaxSSColWidth(sslist, ssWidth):

	ssDA = SSDisplayAttrs()

	for idx in range(len(ssDA.SSkeys)):
		if idx == SnapshotMaxWidths.SNAPNAME:

			# Calculate column width for the snapshot name

			snapshotLen = \
			    len(sslist.get(ssDA.SSkeys[SnapshotMaxWidths.SNAPNAME]))
			snapshotHeaderLen = \
			    len(ssDA.SSheader[SnapshotMaxWidths.SNAPNAME])

			if snapshotHeaderLen > snapshotLen and \
			    snapshotHeaderLen > ssWidth.snapshot:			
				ssWidth.snapshot = snapshotHeaderLen 
			elif ssWidth.snapshot < snapshotLen:
				ssWidth.snapshot = snapshotLen + 1

		elif idx == SnapshotMaxWidths.POLICY:

			# Calculate column width for the policy

			policyLen = \
			    len(sslist.get(ssDA.SSkeys[SnapshotMaxWidths.POLICY]))
			policyHeaderLen = \
			    len(ssDA.SSheader[SnapshotMaxWidths.POLICY])

			if policyHeaderLen > policyLen and \
			    policyHeaderLen > ssWidth.policy:			
				ssWidth.policy = policyHeaderLen 
			elif ssWidth.policy < policyLen:
				ssWidth.policy = policyLen + 1

			ssWidth.policy = \
			    len(ssDA.SSheader[SnapshotMaxWidths.SNAPNAME + 1])

		elif idx == SnapshotMaxWidths.DATE:

			# Calculate column width for the Date

			dateLen = \
			    len(str(sslist.get(ssDA.SSkeys[SnapshotMaxWidths.SNAPNAME])))
			dateHeaderLen = \
			    len(ssDA.SSheader[SnapshotMaxWidths.SNAPNAME + 1])

			if dateHeaderLen > dateLen:			
				ssWidth.date = dateHeaderLen 
			elif ssWidth.date < dateLen:
				ssWidth.date = dateLen + 1

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Display the snapshot attributes.

def formatSnapshotOutput(sslist, headerFlag, ddh, ssWidth, beDA):

	outStr = ""
	headStr = ""
	headStr2 = ""

	delimMaj = ";"
	delimMin = ":"

	ssDA = SSDisplayAttrs()

	for idx in range(len(ssDA.SSkeys)):
		if idx == SnapshotMaxWidths.SNAPNAME:

			# Construct the snapshot value

			snapshot = sslist.get(ssDA.SSkeys[SnapshotMaxWidths.SNAPNAME])

			if ddh:
				if beDA.outStr[len(beDA.outStr) - 1] != '\n':
					beDA.outStr = beDA.outStr + delimMaj
				outStr = snapshot + delimMin
			else:
				outStr = "   " + snapshot.ljust(ssWidth.snapshot)
				headStr = "   " + \
				    ssDA.SSheader[SnapshotMaxWidths.SNAPNAME].ljust(ssWidth.snapshot)
				headStr2 = "   " + \
				    ssDA.SSheader2[SnapshotMaxWidths.SNAPNAME].ljust(ssWidth.snapshot)
				
		elif idx == SnapshotMaxWidths.POLICY:			

			# Construct the policy value

			policy = sslist.get(ssDA.SSkeys[SnapshotMaxWidths.POLICY])

			if ddh:
				outStr = outStr + policy + delimMin
			else:
				outStr = outStr + policy.ljust(ssWidth.policy)
				headStr = headStr + \
				    ssDA.SSheader[SnapshotMaxWidths.POLICY].ljust(ssWidth.policy)
				headStr2 = headStr2 + \
				    ssDA.SSheader2[SnapshotMaxWidths.POLICY].ljust(ssWidth.policy)

		elif idx == SnapshotMaxWidths.DATE:			

			# Construct the date value

			date = str(datetime.datetime.fromtimestamp(sslist.get(ssDA.SSkeys[SnapshotMaxWidths.DATE])))

			if ddh:
				outStr = outStr + date + delimMin
			else:							
				outStr = outStr + date
				headStr = headStr + ssDA.SSheader[SnapshotMaxWidths.DATE]
				headStr2 = headStr2 + ssDA.SSheader2[SnapshotMaxWidths.DATE]
						
	# Display headers

	if headerFlag and not ddh:
		print headStr
		print headStr2

	# If headers are not to be displayed then append the output to
	# the snapshot object string. 

	if ddh:
		beDA.outStr = beDA.outStr + outStr 
	else:
		print outStr

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Return the display value for the space used.

def getDisplayValue(num):

	K = 1024.0
	M = 1048576.0
	G = 1073741824.0
	T = 1099511627776.0

	if num == None:
		return("0")
	elif num < K:
		return (str(num) + "B")
	elif num >= K and num < M:
		return (str("%.1f" % (num / K)) + "K")
	elif num >= M and num < G:
		return (str("%.2f" % (num / M)) + "M")
	elif num >= G and num < T:
		return (str("%.2f" % (num / G)) + "G")

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
		
	if not os.path.isfile(be.log) and not \
		os.path.islink(be.log):
		if not os.path.isdir(os.path.dirname(be.log)):
			os.makedirs(os.path.dirname(be.log), 0644)
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
		answer = raw_input()
		value = string.upper(answer)
		if value[0] == 'Y' and len(value) == 1:
			break
		elif value[0] == 'N' and len(value) == 1:
			msg.msgs("destroyNo", be.trgtBeNameOrSnapshot[0])
			return(0)
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
if __name__ == "__main__":
	try:
		ret = main()
	except SystemExit, e:
		raise e
	except:
		traceback.print_exc()
		sys.exit(99)
	sys.exit(ret)

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
# beadm - The Boot Environment Administration tool.
#
# A file containing all of the messages output by beadm

import sys
        
def printStderr(str, logFd=0):

	print >> sys.stderr, "beadm:", str
	
	if logFd != 0:
		logFd.write(str)
		logFd.write("\n")
        
def printStdout(str, logFd=0):

	print >> sys.stdout, str

	if logFd != 0:
		logFd.write(str)
		logFd.write("\n")
       
def printLog(str, logFd=0):

	if logFd != 0:
		logFd.write(str)
		logFd.write("\n")
       
def msgs(msgType="", txt="", logFd=0):

    if msgType == "errIllSubcommand":
        msg = "Illegal subcommand: " + txt
        printStderr(msg, logFd)
    elif msgType == "errActivateOpts":
        msg = "Subcommand \"activate\" needs a beNme to activate"
        printStderr(msg, logFd)
    elif msgType == "errNoBeNameSnapshot":
        msg = "A <beName> or <snapshot> was not provided"
        printStderr(msg, logFd)
    elif msgType == "errActivate":
        msg = "Unable to activate " + txt
        printStderr(msg, logFd)
    elif msgType == "errCreate":
        msg = "Unable to create " + txt
        printStderr(msg, logFd)
    elif msgType == "errBEName":
        msg = txt + " does not exist"
        printStderr(msg, logFd)
    elif msgType == "errInvalidOptsArgs":
        msg = "Invalid options and arguments:"
        printStderr(msg, logFd)
    elif msgType == "errList":
        msg = "Failed to display Boot Environment(s)"
        printStderr(msg, logFd)
    elif msgType == "errMutuallyExlusive":
        msg = "Invalid options: " + \
            txt + " are mutually exclusive"
        printStderr(msg, logFd)
    elif msgType == "errUnmountArg":
        msg = "Invalid unmount argument: " + txt
        printStderr(msg, logFd)
    elif msgType == "errRenameFailed":
        msg = "rename of BE: " + txt + " failed"
        printStderr(msg, logFd)
    elif msgType == "errDestroy":
        msg = "Unable to destroy " + txt
        printStderr(msg, logFd)
    elif msgType == "errMountFailed":
        msg = "Unable to mount " + txt
        printStderr(msg, logFd)
    elif msgType == "errUnMountFailed":
        msg = "Unable to unmount " + txt
        printStderr(msg, logFd)
    elif msgType == "msgCreateBESuccess":
        msg = txt + "was createed successfully"
        printLog(msg, logFd)
    elif msgType == "msgCreateBEStart":
        msg = "Attempting to create" + txt
        printLog(msg, logFd)
    elif msgType == "msgLog":
        msg = "See log " + txt + " for details"
        printStdout(msg, logFd)
    elif msgType == "errMountpoint":
        msg = "Invalid mount point " + txt + " mount point must start with a /"
        printStderr(msg, logFd)
    elif msgType == "errLogCreate":
        msg = "Unable to create log file"
        printStderr(msg, logFd)
    elif msgType == "errLogRm":
        msg = "Unable to remove " + txt
        printStderr(msg, logFd)
    elif msgType == "errInvalidResponse":
        msg = "Invalid response. Please enter 'y' or 'n'"
        printStdout(msg, logFd)
    elif msgType == "quitting":
        msg = "Exiting. No changes have been made to the system"
        printStdout(msg, logFd)
    elif msgType == "dwnldSftwQuestion":
         msg = "New beadm software exists. Do you wish to download\nthe software before proceeding with the upgrade? (y/n): "
         printStdout(msg, logFd)
    elif msgType == "destroyQuestion":
         msg = "Are you sure you want to destroy " + txt + "? This action cannot be undone (y/[n]):"
         printStdout(msg, logFd)
    elif msgType == "destroyNo":
         msg = txt + " has not been destroyed"
         printStdout(msg, logFd)
    elif msgType == "":
        printStderr(txt)

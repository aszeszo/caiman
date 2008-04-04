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
# Boot Environment classes used by beadm.

import sys


class BootEnvironment:
	"""Boot Environment object that is used by beadm to manage command line 
	options, arguments and the log."""

	def __init__(self):
		self.trgtRpool = None
		self.trgtBeNameOrSnapshot = None
		self.srcBeNameOrSnapshot = None
		self.properties = {}
		self.logID = None
		self.log = None
	
class BEMaxWidths:
	"""An object to manage column widths for displaying
	Boot Environment information."""

	BENAME, ACTIVE, ACTIVE_ON_REBOOT, MOUNTPOINT, \
	    SPACE_USED, MOUNTED = range(6)

	def __init__(self):
		self.beName = 0
		self.active = 0
		self.activeOnBoot = 0
		self.status = 0
		self.dataset = 0
		self.mountpoint = 0
		self.mounted = 0
		self.spaceused = 0
            
class DatasetMaxWidths:
	"""An object to manage column widths for displaying
	Dataset information."""

	DATASET, MOUNTPOINT, SPACE_USED, MOUNTED = range(4)

	def __init__(self):
		self.dataset = 0
		self.status = 0
		self.mountpoint = 0
		self.spaceused = 0
            
class SnapshotMaxWidths:
	"""An object to manage column widths for displaying
	Snapshot information."""

	SNAPNAME, POLICY, DATE = range(3)

	def __init__(self):
		self.snapshot = 0
		self.policy = 0
		self.date = 0

class BEDisplayAttrs:
	"""An object to store the keys used to retrieve Boot Environment
	information exported by libbe. Also stores the static headers
	for displaying Boot Environment information."""

	def __init__(self):
		self.BEkeys = ("orig_be_name", "active", "active_boot", \
		    "mountpoint", "space_used", "mounted")
		self.BEheader = ("BE ", "Active ", "Active on ", \
		    "Mountpoint ", "Space ")
		self.BEheader2 = ("Name ", " ", "reboot ", " ", "Used")
		self.BEheader3 = ("---- ", "------ ", "--------- ", \
		    "---------- ", "-----")
		self.outStr = ""

class DSDisplayAttrs:
	"""An object to store the keys used to retrieve Dataset
	information exported by libbe. Also stores the static headers
	for displaying Dataset information."""

	def __init__(self):
		self.DSkeys = ("dataset", "mountpoint", "space_used", \
		    "mounted")
		self.DSheader =  ("Datasets ", "Mountpoint ", "Space Used")
		self.DSheader2 = ("-------- ", "---------- ", "----------")

class SSDisplayAttrs:
	"""An object to store the keys used to retrieve Snapshot
	information exported by libbe. Also stores the static headers
	for displaying snapshot information."""

	def __init__(self):
		self.SSkeys =    ("snap_name", "policy", "date")
		self.SSheader =  ("Snapshots ", "Policy ", "Date created")
		self.SSheader2 = ("--------- ", "------ ", "------------")

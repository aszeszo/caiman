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

# =============================================================================
# =============================================================================
# bootroot_initialize - Create and populate the bootroot area.
# =============================================================================
# =============================================================================

import os
import os.path
import sys
import errno
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.DC_ti import ti_create_target
from osol_install.distro_const.DC_ti import ti_release_target
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.transfer_mod import tm_perform_transfer
from osol_install.distro_const.DC_defs import \
    BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_DIR
from osol_install.distro_const.DC_defs import \
    BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_FILE
from osol_install.distro_const.DC_defs import \
    BOOT_ROOT_CONTENTS_BASE_EXCLUDE_TO_TYPE_DIR

execfile('/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py')
execfile('/usr/lib/python2.4/vendor-packages/osol_install/transfer_defs.py')

# A few commands
FIND = "/usr/bin/find"
CPIO = "/usr/bin/cpio"
GREP = "/usr/bin/grep"
RM = "/usr/bin/rm"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Create the bootroot area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_PATH: Package image area mountpoint

  TMP_DIR: Temporary directory

  BR_BUILD: Area where bootroot is put together.  Assumed to exist.

  MEDIA_DIR: Area where the media is put. (Not used)
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 6): # Don't forget sys.argv[0] is the script itself.
	raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
	    "    Reader socket, pkg_image area, temp dir,\n" +
	    "    bootroot build area, media area.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
PKG_IMG_PATH = sys.argv[2]	# package image area mountpoint
TMP_DIR = sys.argv[3]		# temporary directory to contain bootroot build
BR_BUILD = sys.argv[4]		# Bootroot build area

# Copy error string.
br_init_msg_copyerr = "bootroot_initialize: Error copying dir %s to %s"

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

print "Creating bootroot build area and adding files to it..."

os.chdir(BR_BUILD)	# Raises exception if build area doesn't exist
cmd = RM + " -rf *"
status = os.system(cmd)
if (status != 0):
	raise Exception, "Error purging old contents from bootroot build area"

FILELIST_NAME = TMP_DIR + "/filelist"

# create filelist for use in transfer module
filelist = open(FILELIST_NAME, 'w')

# get list of files in bootroot from contents file
BR_filelist = get_manifest_list(manifest_reader_obj,
    BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_FILE)

# TBD: Process list of file adjustments from manifest

# write the list of files to a file for use by the transfer module
try:
	for item in BR_filelist:
		filelist.write(item + '\n')
finally:
	filelist.close()

# use transfer module to copy files from pkg image area to bootroot staging area
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
	(TM_CPIO_ACTION, TM_CPIO_LIST),
	(TM_CPIO_LIST_FILE, FILELIST_NAME),
	(TM_CPIO_DST_MNTPT, BR_BUILD),
	(TM_CPIO_SRC_MNTPT, PKG_IMG_PATH)])

os.remove(FILELIST_NAME)

# verify that copy suceeded
if (status != 0):
	raise Exception, ("bootroot_initialize: copying files to " +
	    "bootroot failed: tm_perform_transfer returned %d" % status)

# use transfer module to copy directories from pkg image area to bootroot
# TBD: use os.system() and cpio to copy directories from pkg image area
# to bootroot until transfer module issues are addressed

# cd to mountpoint
os.chdir(PKG_IMG_PATH)

# get list of directories in bootroot from manifest file
BR_dirlist = get_manifest_list(manifest_reader_obj,
    BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_DIR)

# get list of directories to be excluded. These directories must
# be sub directories of a directory to be included
BR_direxcllist = get_manifest_list(manifest_reader_obj,
    BOOT_ROOT_CONTENTS_BASE_EXCLUDE_TO_TYPE_DIR)

# loop over BR_dirlist
for item in BR_dirlist:
	# check each item for exclusions
	excludes=""
	# loop over directories to be excluded
	for excitem in BR_direxcllist:
		# get the parent directory of the exclude item
		excwords = excitem.split('/')
		# if the parent dir of the exclude item matches the 
		# item, then we need to build the exclusion line
		if item == excwords[0]:
			excludes = excludes + " | " + GREP  + " -v " + excitem

	# cpio the directory 
	# build the line to grep -v the exclusions
	cmd = (FIND + " ./" + item + excludes + " | " +
	    CPIO + " -pdum " + BR_BUILD)
	status = os.system(cmd)
	if (status != 0):
		raise Exception, br_init_msg_copyerr % (item, BR_BUILD)

# HACK copy var and etc directory trees to bootroot
# this is needed or the symlinking step fails
find_no_excl_cmd = FIND + " %s ! -type f | " + CPIO + " -pdum " + BR_BUILD
item = "./var"
status = os.system(find_no_excl_cmd % (item))
if (status != 0):
	raise Exception, br_init_msg_copyerr % (item, BR_BUILD)

item = "./etc"
status = os.system(find_no_excl_cmd % (item))
if (status != 0):
	raise Exception, br_init_msg_copyerr % (item, BR_BUILD)

# cd to the bootroot
os.chdir(BR_BUILD)

# create ./tmp
# Do mkdir and chmod separately as os.mkdir('tmp', 01777) doesn't work right.
# The permissions value needs a leading 0 to make it octal too.
os.mkdir('tmp')
os.chmod('tmp', 01777)

# create ./proc
os.mkdir('proc', 0555)

# create ./mnt
os.mkdir('mnt', 0755)

sys.exit(0)

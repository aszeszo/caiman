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

execfile('/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py')
execfile('/usr/lib/python2.4/vendor-packages/osol_install/transfer_defs.py')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Create the bootroot area.  Name will come from the bootroot_root key in the
manifest, and will hang from TMP_DIR.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_MNT_PT: Package image area mountpoint

  TMP_DIR: Temporary directory to contain the bootroot file
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 4): # Don't forget sys.argv[0] is the script itself.
	raise Exception, ("bootroot_initialize: Requires 3 args: " +
	    "Reader socket, pkg_image mntpt and temp dir.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
PKG_IMG_MNT_PT = sys.argv[2]	# package image area mountpoint
TMP_DIR = sys.argv[3]		# temporary directory to contain bootroot file

# Second arg to get_manifest_value is a key, not a full nodepath
IS_KEY = True

# Name of file containing old undeleted bootroots
OLD_BRLIST_NAME = TMP_DIR + "/old_bootroots"

# Copy error string.
br_init_msg_copyerr = "bootroot_initialize: Error copying dir %s to %s"

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

# Where bootroot hangs from the pkg_image_area.
BR_ROOT = get_manifest_value(manifest_reader_obj, "bootroot_root", IS_KEY)
if (BR_ROOT == None):
	raise Exception, ("bootroot_initialize: bootroot_root not defined " +
	    "as a key in the manifest")
ABS_BR_ROOT = PKG_IMG_MNT_PT + "/" + BR_ROOT

# Name of the bootroot file
BR_NAME = get_manifest_value(manifest_reader_obj, "bootroot_name", IS_KEY)
if (BR_NAME == None):
	raise Exception, ("bootroot_initialize: bootroot_name not defined " +
	    "as a key in the manifest")

# Release any bootroot areas of the same name which were left mounted from a
# previous run.
status = os.system("lofiadm | grep /" + BR_NAME + " > " + OLD_BRLIST_NAME)
if (status == 0):
	old_bootroot_list = open(OLD_BRLIST_NAME,"r")
	for line in old_bootroot_list:
		if (line == ""):
			continue
		obr_name = line.split()[1].strip()

		print "Deleting old bootroot found at " + obr_name + " ..."
	
		# unmount the bootroot file and delete the lofi device
		status = ti_release_target({
		    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
		    TI_ATTR_DC_RAMDISK_DEST: ABS_BR_ROOT,
		    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
		    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: obr_name })
		if (status == errno.ENODEV):
			status = 0
 		if (status == 0):
			try:
				os.remove(obr_name)
			except Exception, err:
				status = 1
		if (status != 0):
			print >>sys.stderr, (
			    "Warning: Couldn't delete old bootroot " + obr_name)
			continue

	old_bootroot_list.close()
os.remove(OLD_BRLIST_NAME)

print "Creating bootroot file..."

# create the file for the bootroot and mount it
status = ti_create_target({
    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
    TI_ATTR_DC_RAMDISK_DEST: ABS_BR_ROOT,
    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
    TI_ATTR_DC_RAMDISK_SIZE: 215000,
    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: TMP_DIR + "/" + BR_NAME })
if (status != 0):
	raise Exception, ("bootroot_initialize: " +
	    "Unable to create boot archive: ti_create_target returned %d" %
	    status)

print "Adding files to bootroot..."

FILELIST_NAME = TMP_DIR + "/filelist"

# create filelist for use in transfer module
filelist = open(FILELIST_NAME, 'w')

# get list of files in bootroot from contents file
BR_filelist = get_manifest_list(manifest_reader_obj,
	'img_params/bootroot_contents/base_include[type="file"]')

# TBD: Process list of file adjustments from manifest

# write the list of files to a file for use by the transfer module
try:
	for item in BR_filelist:
		filelist.write(item + '\n')
finally:
	filelist.close()

# use transfer module to copy files from pkg image area to bootroot
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
	(TM_CPIO_ACTION, TM_CPIO_LIST),
	(TM_CPIO_LIST_FILE, FILELIST_NAME),
	(TM_CPIO_DST_MNTPT, ABS_BR_ROOT),
	(TM_CPIO_SRC_MNTPT, PKG_IMG_MNT_PT)])

os.remove(FILELIST_NAME)

# verify that copy suceeded
if (status != 0):
	raise Exception, ("bootroot_initialize: copying files to " +
	    "bootroot failed: tm_perform_transfer returned %d" % status)

# use transfer module to copy directories from pkg image area to bootroot
# TBD: use os.system() and cpio to copy directories from pkg image area
# to bootroot until transfer module issues are addressed

# cd to mountpoint
os.chdir(PKG_IMG_MNT_PT)

# get list of directories in bootroot from manifest file
BR_dirlist = get_manifest_list(manifest_reader_obj,
    'img_params/bootroot_contents/base_include[type="dir"]')

# get list of directories to be excluded. These directories must
# be sub directories of a directory to be included
BR_direxcllist = get_manifest_list(manifest_reader_obj,
    'img_params/bootroot_contents/base_exclude[type="dir"]')

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
			excludes = excludes + ' | grep -v ' + excitem

	# cpio the directory 
	# build the line to grep -v the exclusions
	status = os.system('find ./' + item + excludes +
		' | cpio -pdum ' + ABS_BR_ROOT)
	if (status != 0):
		raise Exception, br_init_msg_copyerr % (item, ABS_BR_ROOT)

# HACK copy var and etc directory trees to bootroot
# this is needed or the symlinking step fails
find_no_excl_cmd = (
    "/usr/bin/find %s ! -type f | /usr/bin/cpio -pdum " + ABS_BR_ROOT)
item = "./var"
status = os.system(find_no_excl_cmd % (item))
if (status != 0):
	raise Exception, br_init_msg_copyerr % (item, ABS_BR_ROOT)

item = "./etc"
status = os.system(find_no_excl_cmd % (item))
if (status != 0):
	raise Exception, br_init_msg_copyerr % (item, ABS_BR_ROOT)

# cd to the bootroot
os.chdir(ABS_BR_ROOT)

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

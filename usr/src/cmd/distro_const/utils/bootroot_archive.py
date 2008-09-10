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
# bootroot_archive - Release the bootroot mount and archive the bootroot area.
# =============================================================================
# =============================================================================

import os
import sys
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.DC_ti import ti_release_target
from osol_install.distro_const.dc_utils import get_manifest_value

execfile('/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Release the bootroot mount and archive the bootroot area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_MNT_PT: Package image area mountpoint

  TMP_DIR: Temporary directory to contain the bootroot file

Note:
	If this script is executed in a run independent of the run where
	bootroot_initialize was run, ti_release_target will not be able to
	find the proper devices/files to release and will give error 15
	"Block device required" If this happens, just rerun from the step
	which runs bootroot_initialize, as that script has code to check for
	old stale bootroots.
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 4): # Don't forget sys.argv[0] is the script itself.
	raise Exception, ("bootroot_archive: Requires 3 args: " +
	    "Reader socket, pkg_image mntpt and temp dir.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
PKG_IMG_MNT_PT = sys.argv[2]	# package image area mountpoint
TMP_DIR = sys.argv[3]		# temporary directory to contain bootroot file

# Second arg to get_manifest_value is a key, not a full nodepath
IS_KEY = True

print "Archiving bootroot..."

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

# Where bootroot hangs from the pkg_image_area.
BR_ROOT = get_manifest_value(manifest_reader_obj, "bootroot_root", IS_KEY)
if (BR_ROOT == None):
	raise Exception, ("bootroot_archive: bootroot_root not defined " +
	    "as a key in the manifest")
ABS_BR_ROOT = PKG_IMG_MNT_PT + "/" + BR_ROOT

# Name of the bootroot file
BR_NAME = get_manifest_value(manifest_reader_obj, "bootroot_name", IS_KEY)
if (BR_NAME == None):
	raise Exception, ("bootroot_archive: bootroot_name not defined " +
	    "as a key in the manifest")
TEMP_ARCHIVE = TMP_DIR + "/" + BR_NAME
BOOT_ARCHIVE = PKG_IMG_MNT_PT + "/boot/" + BR_NAME

# unmount the bootroot file and delete the lofi device
status = ti_release_target({
    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
    TI_ATTR_DC_RAMDISK_DEST: ABS_BR_ROOT,
    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: TEMP_ARCHIVE })
if status:
	raise Exception, ("bootroot_archive: " +
	    "Unable to release boot archive: ti_release_target returned %d" %
	    status)

# archive file using 7zip command and gzip compression
cmd = '/usr/bin/7za a -tgzip -mx=9 ' + TEMP_ARCHIVE + '.gz ' + TEMP_ARCHIVE
status = os.system(cmd)
if (status != 0):
	raise Exception, ("bootroot_archive: Error compressing bootroot: " +
	    "7za command returns %d" % status)

# move compressed file to proper location in pkg image area
mvcmd = '/usr/bin/mv ' + TEMP_ARCHIVE + '.gz ' + BOOT_ARCHIVE
status = os.system(mvcmd)
if (status != 0):
	raise Exception, ("bootroot_archive: Error moving " +
	    "bootroot from %s to %s: mv returns %d" %
	    (TEMP_ARCHIVE + '.gz', BOOT_ARCHIVE, status))
os.chmod(BOOT_ARCHIVE, 0644)

sys.exit(0)

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
from osol_install.distro_const.DC_defs import BR_ROOT
from osol_install.distro_const.DC_defs import BR_NAME
from osol_install.distro_const.DC_defs import BOOTROOT
from osol_install.distro_const.DC_defs import TMP
from osol_install.distro_const.DC_defs import PKG_IMAGE

execfile('/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Release the bootroot mount and archive the bootroot area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  BUILD_AREA: Build area mountpoint

Note:
	If this script is executed in a run independent of the run where
	bootroot_initialize was run, ti_release_target will not be able to
	find the proper devices/files to release and will give error 15
	"Block device required" If this happens, just rerun from the step
	which runs bootroot_initialize, as that script has code to check for
	old stale bootroots.
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 3): # Don't forget sys.argv[0] is the script itself.
	raise Exception, ("bootroot_archive: Requires 2 args: " +
	    "Reader socket, Build area mntpt.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
BUILD_AREA_MNT_PT = sys.argv[2]	# Build area
PKG_IMG_MNT_PT = BUILD_AREA_MNT_PT + PKG_IMAGE # package image area mountpoint
TMP_DIR = BUILD_AREA_MNT_PT + TMP # temporary directory to contain bootroot file

# Second arg to get_manifest_value is a key, not a full nodepath
IS_KEY = True

print "Archiving bootroot..."

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

ABS_BR_ROOT = PKG_IMG_MNT_PT + BR_ROOT

# Name of the bootroot file
BR_ARCHIVE = BUILD_AREA_MNT_PT + BOOTROOT + BR_NAME
BOOT_ARCHIVE = PKG_IMG_MNT_PT + "/boot" + BR_NAME

# unmount the bootroot file and delete the lofi device
status = ti_release_target({
    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
    TI_ATTR_DC_RAMDISK_DEST: ABS_BR_ROOT,
    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: BR_ARCHIVE })
if status:
	raise Exception, ("bootroot_archive: " +
	    "Unable to release boot archive: ti_release_target returned %d" %
	    status)

# archive file using 7zip command and gzip compression
cmd = '/usr/bin/7za a -tgzip -mx=9 ' + BR_ARCHIVE + '.gz ' + BR_ARCHIVE
status = os.system(cmd)
if (status != 0):
	raise Exception, ("bootroot_archive: Error compressing bootroot: " +
	    "7za command returns %d" % status)

# move compressed file to proper location in pkg image area
mvcmd = '/usr/bin/mv ' + BR_ARCHIVE + '.gz ' + BOOT_ARCHIVE
status = os.system(mvcmd)
if (status != 0):
	raise Exception, ("bootroot_archive: Error moving " +
	    "bootroot from %s to %s: mv returns %d" %
	    (BR_ARCHIVE + '.gz', BOOT_ARCHIVE, status))
os.chmod(BOOT_ARCHIVE, 0644)

sys.exit(0)

#!/usr/bin/python2.4
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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

# =============================================================================
# =============================================================================
# finalizer_checkpoint - Checkpoint state of a distro build
# =============================================================================
# =============================================================================

import sys
import osol_install.distro_const.DC_checkpoint as DC_checkpoint
import shutil
from osol_install.distro_const.dc_utils import setup_dc_logging


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Checkpoint state of a distro build

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object
	(not used)

  PKG_IMG_MNT_PT: Package image area mountpoint (not used)

  TMP_DIR: Temporary directory to contain the boot archive file (not used)

  BA_BUILD: Area where boot archive is put together (not used)

  MEDIA_DIR: Area where the media is put (not used)

  MANIFEST_FILE: Name of manifest file to save

  STATE_FILE: Name of state file to save

  ZFS_SNAPSHOTS (variable number): List of snapshots to take as part of this
	checkpoint operation

  MESSAGE: Message to print while checkpointing
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

length = len(sys.argv)
if length < 10:
    raise Exception, (sys.argv[0] + ": At least 11 args are required: \n" +
                                    "Reader socket, pkg_image area, " \
                                    "tmp area, \n" +
                                    "boot archive build area, media area, " \
                                    "manifest file, state file, \n" +
                                    "zfs dataset(s), message")

manifest_file = sys.argv[6]
state_file = sys.argv[7]
zfs_snapshots = sys.argv[8:length-1]
message = sys.argv[length-1]

dc_log = setup_dc_logging()

for snapshot in zfs_snapshots:
    DC_checkpoint.shell_cmd("/usr/sbin/zfs snapshot " + snapshot, dc_log)

shutil.copy(manifest_file, state_file)
dc_log.info(message)
sys.exit(0)

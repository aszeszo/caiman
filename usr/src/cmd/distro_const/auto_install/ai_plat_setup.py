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
# ai_plat_setup
#
# Platform specific customizations for sparc
#
# To be done before post_boot_archive_pkg_image_mod gets called.
# =============================================================================
# =============================================================================

import os
import sys
from osol_install.distro_const.DC_defs import BA_FILENAME_SUN4U
from osol_install.distro_const.DC_defs import BA_FILENAME_SUN4V
from osol_install.distro_const.DC_defs import BA_FILENAME_X86
from osol_install.distro_const.DC_defs import BA_FILENAME_AMD64

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Platform specific customizations for sparc.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_PATH: Package image area mountpoint

  TMP_DIR: Temporary directory (not used)

  BA_BUILD: Area where boot archive is put together.  (not used)

  MEDIA_DIR: Area where the media is put. (not used)

  KERNEL_ARCH: Machine type for archive

Note: This assumes a populated pkg_image area exists at the location
	${PKG_IMG_PATH}

"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 7): # Don't forget sys.argv[0] is the script itself.
    raise Exception, (sys.argv[0] + ": Requires 6 args:\n" +
                                    "    Reader socket, pkg_image area, " +
                                    "temp dir,\n" +
                                    "    boot archive build area, " +
                                    "media area, machine type.")

# collect input arguments from what this script sees as a commandline.
PKG_IMG_PATH = sys.argv[2]	# package image area mountpoint
KERNEL_ARCH = sys.argv[6]	# Machine type for this archive

if KERNEL_ARCH == "sparc":
    # Create the symlink from sun4v/boot_archive to sun4u/boot_archive
    # The sun4u/boot_archive is the real boot_archive. We're using
    # the same boot_archive for sun4v as sun4u.
    try:
        os.symlink("../.." + BA_FILENAME_SUN4U,
                   PKG_IMG_PATH + BA_FILENAME_SUN4V)
    except OSError, (errno, strerror):
        print >> sys.stderr, "Error creating symlink for sun4v boot_archive"
        raise



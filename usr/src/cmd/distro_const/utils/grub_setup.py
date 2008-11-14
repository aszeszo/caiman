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
# grub_setup
#
# Customizations to the grub menu.
#
# To be done before post_bootroot_pkg_image_mod gets called.
# =============================================================================
# =============================================================================

import os
import sys
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.DC_defs import *

DEFAULT_DEFAULT_ENTRY = "0"
DEFAULT_TIMEOUT = "30" # Seconds

RELEASE_FILE = "/etc/release"

FIND_EXTRACT_ERR_MSG = ("Error finding or extracting " +
    "non-empty release string from " + RELEASE_FILE)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Customizations to the grub menu.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_PATH: Package image area mountpoint

  TMP_DIR: Temporary directory (not used)

  BR_BUILD: Area where bootroot is put together.  (not used)

  MEDIA_DIR: Area where the media is put. (not used)

Note: This assumes a populated pkg_image area exists at the location
	${PKG_IMG_PATH}
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 6): # Don't forget sys.argv[0] is the script itself.
	raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
	    "    Reader socket, pkg_image area, temp dir,\n" +
	    "    bootroot build area, media area.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
PKG_IMG_PATH = sys.argv[2]	# package image area mountpoint

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

# Get the release from first line of /etc/release in PKG_IMG_PATH
release_fd = None
release = None
try:
	try:
		release_fd = open(PKG_IMG_PATH + RELEASE_FILE, "r")
		release = release_fd.readline().strip()
	except Exception, err:
		print >>sys.stderr, sys.argv[0] + ": " + FIND_EXTRACT_ERR_MSG
		raise err
finally:
	if (release_fd != None):
		release_fd.close()

if ((release == None) or (len(release.strip()) == 0)):
	print >>sys.stderr, sys.argv[0] + ": Empty or blank first line in file"
	raise Exception, sys.argv[0] + ": " + FIND_EXTRACT_ERR_MSG

# Open menu.lst file.
try:
	menu_lst_file = open(PKG_IMG_PATH + "/boot/grub/menu.lst", "w")
except IOError, err:
	print >>sys.stderr, "Error opening grub menu.lst for writing"
	raise

# Get default entry from manifest, if it exists.
DEFAULT_ENTRY = get_manifest_value(manifest_reader_obj, GRUB_DEFAULT_ENTRY_NUM)
if (DEFAULT_ENTRY == None):
	DEFAULT_ENTRY = DEFAULT_DEFAULT_ENTRY
menu_lst_file.write("default=" + DEFAULT_ENTRY + "\n")

# Get default timeout from manifest. if it exists.
TIMEOUT = get_manifest_value(manifest_reader_obj, GRUB_DEFAULT_TIMEOUT)
if (TIMEOUT == None):
	TIMEOUT = DEFAULT_TIMEOUT
menu_lst_file.write("timeout=" + TIMEOUT + "\n")

menu_lst_file.write("splashimage=/boot/grub/splash.xpm.gz\n")
menu_lst_file.write("foreground=ffffff\n")
menu_lst_file.write("background=215ECA\n")
menu_lst_file.write("min_mem64=1000\n")

# "entries" is an ordered list of grub entries.  Defaults will be:
#	<release>
#	<release> text console
#	Boot from hard disk
#
# Add new entries from the manifest, in the position requested.  Position will
# be relative to the existing entry list.  For example, if two entries are
# listed for position 1, the first one will be put at position 1, but then the
# second one will be put at position 1, bumping the first to position 2.

entries = []

# The following three entries are the standard "hardwired" entries.

entry = []
entry.append("title " + release)
entry.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix")
entry.append("\tmodule /boot/x86.microroot")
entries.append(entry)

entry = []
entry.append("title " + release + " text console")
entry.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B livemode=text")
entry.append("\tmodule /boot/x86.microroot")
entries.append(entry)

entry = []
entry.append("title Boot from Hard Disk")
entry.append("\trootnoverify (hd0)")
entry.append("\tchainloader +1")
entries.append(entry)

# This all assumes that data is returned from the manifest in the order it is
# provided.  Otherwise, lines within an entry could be out of order.

entry_names = get_manifest_list(manifest_reader_obj, GRUB_ENTRY_TITLE_SUFFIX)
for name in entry_names:
	entry = []
	entry.append("title " + release + " " + name)
	lines = get_manifest_list(manifest_reader_obj, GRUB_ENTRY_LINES % name)
	for line in lines:
		entry.append("\t" + line)

	position_str = get_manifest_value(manifest_reader_obj,
	    GRUB_ENTRY_POSITION % name)

	# Put at the end of the list if no position stated.
	if (position_str == None):
		entries.append(entry)
	else:
		try:
			position = int(position_str)
			entries.insert(position, entry)
		except ValueError:
			print >>sys.stderr, ("Position specified for the \"" +
			    release + " " + name + "\" entry")
			print >>sys.stderr, ("    is not a positive number.  " +
			    "Found: " + position_str)
			print >>sys.stderr, "    Placing at the end of the list"
			entries.append(entry)

for entry in entries:
	menu_lst_file.write("\n")
	for entry_line in entry:
		menu_lst_file.write(entry_line + "\n")

menu_lst_file.close()
sys.exit(0)

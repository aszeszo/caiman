#!/usr/bin/python2.6
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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""grub_setup
Customizations to the grub menu.

 To be done before post_bootroot_pkg_image_mod gets called.

"""

import os
import sys
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.dc_defs import IMAGE_INFO_FILE, \
    GRUB_DEFAULT_ENTRY_NUM, GRUB_DEFAULT_TIMEOUT, \
    IMAGE_INFO_GRUB_TITLE_KEYWORD, GRUB_ENTRY_TITLE_SUFFIX, \
    GRUB_ENTRY_LINES, GRUB_ENTRY_POSITION, GRUB_TITLE, GRUB_ENTRY_MIN_MEM64, \
    IMAGE_INFO_GRUB_MIN_MEM64_KEYWORD, IMAGE_INFO_GRUB_DO_SAFE_DEFAULT_KEYWORD

DEFAULT_DEFAULT_ENTRY = "0"
DEFAULT_TIMEOUT = "30" # Seconds

DEFAULT_GRUB_DO_SAFE_DEFAULT_VALUE = "true"

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

  BA_BUILD: Area where boot archive is put together.  (not used)

  MEDIA_DIR: Area where the media is put. (not used)

  GRUB_SETUP_TYPE: The type of image being created (ai or livecd)

Note: This assumes a populated pkg_image area exists at the location
        ${PKG_IMG_PATH}

"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 7): # Don't forget sys.argv[0] is the script itself.
    raise Exception, (sys.argv[0] + ": Requires 6 args:\n" +
    "    Reader socket, pkg_image area, temp dir,\n" +
    "    boot archive build area, media area, grub setup type.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]      # Manifest reader socket
PKG_IMG_PATH = sys.argv[2]      # package image area mountpoint
GRUB_SETUP_TYPE = sys.argv[6]	# Grub setup type

# get the manifest reader object from the socket
MANIFEST_READER_OBJ = ManifestRead(MFEST_SOCKET)

# if a string is specified in the manifest to be used as the title of the grub
# menu entries, that string will be used.  Otherwise, use the first
# line of /etc/release as the title

# Get grub title from manifest, if any
RELEASE = get_manifest_value(MANIFEST_READER_OBJ, GRUB_TITLE)
if RELEASE is not None:
    # User specified a special grub menu, record that in .image_info
    IMG_INFO_FD = None
    try:
        IMG_INFO_PATH = PKG_IMG_PATH + "/" + IMAGE_INFO_FILE
        try:
            IMG_INFO_FD = open(IMG_INFO_PATH, "a+")
            IMG_INFO_FD.write(IMAGE_INFO_GRUB_TITLE_KEYWORD +
                RELEASE + "\n")
        except Exception, err:
            print >> sys.stderr, sys.argv[0] +  \
                     "Unable to write to " + IMG_INFO_PATH 
            raise err
    finally:
        if (IMG_INFO_FD != None):
            IMG_INFO_FD.close()
else:
    # grub menu title is not defined in manifest, use the first
    # line of /etc/release in PKG_IMG_PATH
    RELEASE_FD = None
    try:
        try:
            RELEASE_FD = open(PKG_IMG_PATH + RELEASE_FILE, "r")
            RELEASE = RELEASE_FD.readline().strip()
        except Exception, err:
            print >> sys.stderr, sys.argv[0] + ": " \
                + FIND_EXTRACT_ERR_MSG
            raise err
    finally:
        if RELEASE_FD is not None:
            RELEASE_FD.close()

if (RELEASE is None or (len(RELEASE.strip()) == 0)):
    print >> sys.stderr, sys.argv[0] + ": Empty or blank first line in file"
    raise Exception, sys.argv[0] + ": " + FIND_EXTRACT_ERR_MSG

#
# For purposes of network automated installation (AI), pass (via .image_info
# file) minimum memory required for AI to be booted in 64 bit mode, and also
# a flag to indicate whether or not a safe default entry is to be created.
# That information is read by installadm(1M) tools on AI server - GRUB menu.lst
# 'min_mem64' option, and additional menu entry is populated accordingly.
#
# Get min_mem64 from manifest. If not specified there, 1000 is picked up
# as default.
#
if (GRUB_SETUP_TYPE == "ai"):
    min_mem64 = get_manifest_value(MANIFEST_READER_OBJ, GRUB_ENTRY_MIN_MEM64)

    do_safe_default = DEFAULT_GRUB_DO_SAFE_DEFAULT_VALUE

    IMG_INFO_PATH = os.path.join(PKG_IMG_PATH, IMAGE_INFO_FILE)
    try:
        with open(IMG_INFO_PATH, "a+") as image_info:
            image_info.write("%s%s\n" % (IMAGE_INFO_GRUB_MIN_MEM64_KEYWORD,
                             min_mem64))
	    image_info.write("%s%s\n" %
		(IMAGE_INFO_GRUB_DO_SAFE_DEFAULT_KEYWORD, do_safe_default))
    except Exception, err:
        print >> sys.stderr, sys.argv[0] + \
                 " : Unable to write to " + IMG_INFO_PATH
        raise err

# Open menu.lst file.
try:
    MENU_LST_FILE = open(PKG_IMG_PATH + "/boot/grub/menu.lst", "w")
except IOError, err:
    print >> sys.stderr, "Error opening grub menu.lst for writing"
    raise

# Get default entry from manifest, if it exists.
DEFAULT_ENTRY = get_manifest_value(MANIFEST_READER_OBJ, GRUB_DEFAULT_ENTRY_NUM)
if DEFAULT_ENTRY is None:
    DEFAULT_ENTRY = DEFAULT_DEFAULT_ENTRY
MENU_LST_FILE.write("default=" + DEFAULT_ENTRY + "\n")

# Get default timeout from manifest. if it exists.
TIMEOUT = get_manifest_value(MANIFEST_READER_OBJ, GRUB_DEFAULT_TIMEOUT)
if TIMEOUT is None:
    TIMEOUT = DEFAULT_TIMEOUT
MENU_LST_FILE.write("timeout=" + TIMEOUT + "\n")

MENU_LST_FILE.write("min_mem64=1000\n")

# "entries" is an ordered list of grub entries.  Defaults will be:
#       <release>
#       <release> text console
#       Boot from hard disk
#
# Add new entries from the manifest, in the position requested.  Position will
# be relative to the existing entry list.  For example, if two entries are
# listed for position 1, the first one will be put at position 1, but then the
# second one will be put at position 1, bumping the first to position 2.

ENTRIES = []

if (GRUB_SETUP_TYPE == "ai"):
    	# The following entries are the standard "hardwired" entries for AI
    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install custom")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true,aimanifest=prompt")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install custom ttya")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true,aimanifest=prompt,console=ttya")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install custom ttyb")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true,aimanifest=prompt,console=ttyb")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install ttya")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true,console=ttya")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " Automated Install ttyb")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B install=true,console=ttyb")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)
elif (GRUB_SETUP_TYPE == "livecd"):
    # The following entries are the standard "hardwired" entries for livecd.
    MENU_LST_FILE.write("splashimage=/boot/grub/splash.xpm.gz\n")
    MENU_LST_FILE.write("foreground=ffffff\n")
    MENU_LST_FILE.write("background=215ECA\n")

    ENTRY = []
    ENTRY.append("title " + RELEASE)
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " VESA driver")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B livemode=vesa")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

    ENTRY = []
    ENTRY.append("title " + RELEASE + " text console")
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix -B livemode=text")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)
elif (GRUB_SETUP_TYPE == "text-install"):
    # The following entries are the standard "hardwired" entries for 
    # the text-installer
    # The menu.lst is hidden by default. GRUB doesn't show the menu.lst
    # on the control terminal and automatically boots the default entry, 
    # unless interrupted by pressing <ESC> before the timeout expires.
    MENU_LST_FILE.write("hiddenmenu\n")

    ENTRY = []
    ENTRY.append("title " + RELEASE)
    ENTRY.append("\tkernel$ /platform/i86pc/kernel/$ISADIR/unix")
    ENTRY.append("\tmodule$ /platform/i86pc/$ISADIR/boot_archive")
    ENTRIES.append(ENTRY)

ENTRY = []
ENTRY.append("title Boot from Hard Disk")
ENTRY.append("\trootnoverify (hd0)")
ENTRY.append("\tchainloader +1")
ENTRIES.append(ENTRY)

# This all assumes that data is returned from the manifest in the order it is
# provided.  Otherwise, lines within an entry could be out of order.

ENTRY_NAMES = get_manifest_list(MANIFEST_READER_OBJ, GRUB_ENTRY_TITLE_SUFFIX)
for name in ENTRY_NAMES:
    ENTRY = []
    ENTRY.append("title " + RELEASE + " " + name)
    lines = get_manifest_list(MANIFEST_READER_OBJ, GRUB_ENTRY_LINES % name)
    for line in lines:
        ENTRY.append("\t" + line)

    position_str = get_manifest_value(MANIFEST_READER_OBJ,
                                      GRUB_ENTRY_POSITION % name)

    # Put at the end of the list if no position stated.
    if position_str is None:
        ENTRIES.append(ENTRY)
    else:
        try:
            position = int(position_str)
            ENTRIES.insert(position, ENTRY)
        except ValueError:
            print >> sys.stderr, ("Position specified for the \"" +
                                  RELEASE + " " + name + "\" entry")
            print >> sys.stderr, ("    is not a positive number.  " +
                "Found: " + position_str)
            print >> sys.stderr, "    Placing at the end of the list"
            ENTRIES.append(ENTRY)

for entry in ENTRIES:
    MENU_LST_FILE.write("\n")
    for entry_line in entry:
        MENU_LST_FILE.write(entry_line + "\n")

MENU_LST_FILE.close()
sys.exit(0)

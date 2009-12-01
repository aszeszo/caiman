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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""boot_archive_initialize - Create and populate the boot archive area."""

import os
import os.path
import shutil
import sys
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.transfer_mod import tm_perform_transfer
from osol_install.distro_const.dc_defs import \
    BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_TO_TYPE_DIR
from osol_install.distro_const.dc_defs import \
    BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_TO_TYPE_FILE
from osol_install.distro_const.dc_defs import \
    BOOT_ARCHIVE_CONTENTS_BASE_EXCLUDE_TO_TYPE_DIR
from osol_install.distro_const.dc_defs import \
    BOOT_ARCHIVE_CONTENTS_BASE_EXCLUDE_TO_TYPE_FILE
from osol_install.transfer_defs import TM_ATTR_MECHANISM, TM_PERFORM_CPIO, \
    TM_CPIO_ACTION, TM_CPIO_LIST, TM_CPIO_LIST_FILE, \
    TM_CPIO_DST_MNTPT, TM_CPIO_SRC_MNTPT


# A few commands
FIND = "/usr/bin/find"
CPIO = "/usr/bin/cpio"
GREP = "/usr/bin/grep"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Create the boot archive area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_PATH: Package image area mountpoint

  TMP_DIR: Temporary directory

  BA_BUILD: Area where boot archive is put together.  Assumed to exist.

  MEDIA_DIR: Area where the media is put. (Not used)

"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 6): # Don't forget sys.argv[0] is the script itself.
    raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
        "    Reader socket, pkg_image area, temp dir,\n" +
        "    boot archive build area, media area.")

# collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]      # Manifest reader socket
PKG_IMG_PATH = sys.argv[2]      # package image area mountpoint
TMP_DIR = sys.argv[3]           # temp directory to contain boot archive build
BA_BUILD = sys.argv[4]          # Boot archive build area

# Copy error string.
BA_INIT_MSG_COPYERR = "boot_archive_initialize: Error copying dir %s to %s"

# get the manifest reader object from the socket
MANIFEST_READER_OBJ = ManifestRead(MFEST_SOCKET)

print "Creating boot archive build area and adding files to it..."


# Clean out any old files which may exist.
try:
    shutil.rmtree(BA_BUILD)
except OSError:
    print >> sys.stderr, ("Error purging old contents from "
                         "boot archive build area")
    raise

try:
    os.mkdir(BA_BUILD)
except OSError:
    print >> sys.stderr, "Error creating boot archive build area"
    raise

FILELIST_NAME = TMP_DIR + "/filelist"

# create filelist for use in transfer module
FILELIST = open(FILELIST_NAME, 'w')

# get list of files in boot archive from contents file
BA_FILELIST = get_manifest_list(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_TO_TYPE_FILE)

# write the list of files to a file for use by the transfer module
try:
    for item in BA_FILELIST:
        FILELIST.write(item + '\n')
finally:
    FILELIST.close()

# use transfer module to copy files from pkg image area to the boot archive
# staging area
STATUS = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
                              (TM_CPIO_ACTION, TM_CPIO_LIST),
                              (TM_CPIO_LIST_FILE, FILELIST_NAME),
                              (TM_CPIO_DST_MNTPT, BA_BUILD),
                              (TM_CPIO_SRC_MNTPT, PKG_IMG_PATH)])

os.remove(FILELIST_NAME)

# verify that copy suceeded
if (STATUS != 0):
    raise Exception, ("boot_archive_initialize: copying files to " +
                      "boot_archive failed: tm_perform_transfer returned %d"
                      % STATUS)

# use transfer module to copy directories from pkg image area to boot archive
# TBD: use os.system() and cpio to copy directories from pkg image area
# to boot archive until transfer module issues are addressed

# cd to mountpoint
os.chdir(PKG_IMG_PATH)

# get list of directories in boot archive from manifest file
BA_DIRLIST = get_manifest_list(MANIFEST_READER_OBJ,
                               BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_TO_TYPE_DIR)

# get list of directories to be excluded. These directories must
# be sub directories of a directory to be included
BA_DIREXCLLIST = get_manifest_list(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_CONTENTS_BASE_EXCLUDE_TO_TYPE_DIR)

# loop over BA_DIRLIST
for item in BA_DIRLIST:
    # check each item for exclusions
    EXCLUDES = ""
    # loop over directories to be excluded
    for excitem in BA_DIREXCLLIST:
        # get the parent directory of the exclude item
        EXCWORDS = excitem.split('/')
        # if the parent dir of the exclude item matches the
        # item, then we need to build the exclusion line
        if item == EXCWORDS[0]:
            EXCLUDES = EXCLUDES + " | " + GREP  + " -v " + excitem

    # cpio the directory
    # build the line to grep -v the exclusions
    CMD = (FIND + " ./" + item + EXCLUDES + " | " +
           CPIO + " -pdum " + BA_BUILD)
    STATUS = os.system(CMD)
    if (STATUS != 0):
        raise Exception, BA_INIT_MSG_COPYERR % (item, BA_BUILD)

#
# Remove the list of files to be excluded from the boot archive
# This is done directly in the boot_archive directory
#
BA_FILEEXCLLIST = get_manifest_list(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_CONTENTS_BASE_EXCLUDE_TO_TYPE_FILE)

# cd to the boot_archive
os.chdir(BA_BUILD)

for item in BA_FILEEXCLLIST:
    try:
        os.remove(item)
    except OSError:
        #
        # Don't need to exit just for not being able to exclude
        # a file.  But want to print a warning so people know.
        # We will also get this error if people specified a directory
        # as a file.
        #
        print >> sys.stderr, "WARNING: Unable to exclude this file " + \
                "from boot_archive: " + item

# HACK copy var and etc directory trees to boot_archive
# this is needed or the symlinking step fails

# Going back to pkg image area
os.chdir(PKG_IMG_PATH)

FIND_NO_EXCL_CMD = FIND + " %s ! -type f | " + CPIO + " -pdum " + BA_BUILD
ITEM = "./var"
STATUS = os.system(FIND_NO_EXCL_CMD % (ITEM))
if (STATUS != 0):
    raise Exception, BA_INIT_MSG_COPYERR % (ITEM, BA_BUILD)

ITEM = "./etc"
STATUS = os.system(FIND_NO_EXCL_CMD % (ITEM))
if (STATUS != 0):
    raise Exception, BA_INIT_MSG_COPYERR % (ITEM, BA_BUILD)

# cd to the boot archive
os.chdir(BA_BUILD)

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

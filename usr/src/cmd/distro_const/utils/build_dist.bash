#!/usr/bin/bash
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

#
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# This script pulls in binaries from various locations and builds
# a complete bootable CD and memory based filesystem image of
# OpenSolaris. Finally it generates an iso image that can be burned
# onto the CDROM to get a bootable OpenSolaris Live DVD.
#
PATH=/usr/bin:/usr/sbin:
export PATH

source /usr/share/distro_const/build_dist.lib

SOCK_NAME=$1
DIST_PROTO=$2
TMPDIR=$3

OUTPUT_PATH=`/usr/bin/ManifestRead $SOCK_NAME "img_params/output_image/pathname"`
DISTRO_NAME=`/usr/bin/ManifestRead $SOCK_NAME "name"`
DIST_ISO=${OUTPUT_PATH}/${DISTRO_NAME}.iso

BOOT_FILENAME=x86.microroot
BOOT_ARCHIVE=$DIST_PROTO/boot/$BOOT_FILENAME
TEMP_ARCHIVE=$TMPDIR/$BOOT_FILENAME
MICROROOT=$DIST_PROTO/bootcd_microroot
RAMDISK_SIZE=200000


if [ ! -e /usr/bin/7za ] ; then
    echo "/usr/bin/7za is not available on your system. Please pkg install SUNWp7zip and rerun"
    exit 1
fi

echo "=== $0 started at `date`"

#
# Create the boot archive. This is a UFS filesystem image in a file
# that is loaded into RAM by Grub. A file is created using mkfile
# and is added as a block device using lofiadm. newfs is then used
# to create a UFS filesystem on the lofi device and then it is
# mounted and all the files required for a minimal root fs are
# copied.
#
initialize_root_archive

populate_root_archive

finalize_root_archive

#
# Unmount the lofi device and remove it. Then gzip the file
# containing the root fs image. Grub will decompress it while
# loading.
#
echo "Archiving Boot Archive"

/usr/sbin/umount $MICROROOT
if [ $? -ne 0 ] ; then
	echo "FAILURE: Unable to unmount $MICROROOT"
	fatal_exit
fi
 
/usr/sbin/lofiadm -d $TEMP_ARCHIVE;
if [ $? -ne 0 ] ; then
	echo "FAILURE: Failure to perform lofiadm -d $TEMP_ARCHIVE"
	fatal_exit
fi

/usr/bin/7za a -tgzip -mx=9 ${TEMP_ARCHIVE}.gz ${TEMP_ARCHIVE}
mv ${TEMP_ARCHIVE}.gz $BOOT_ARCHIVE
chmod a+r $BOOT_ARCHIVE

exit 0


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


# Path of the Distro Constructor kit.

D=`dirname $0`
TOOLS=`(cd $D; cd ../../tools; pwd)`
SRC=`(cd $D; pwd)`

source $SRC/build_dist.lib
SOCK_NAME=$1
DIST_PROTO=$2
TMPDIR=$3

OUTPUT_PATH=`/usr/bin/ManifestRead $SOCK_NAME "img_params/output_image/pathname"`
DISTRO_NAME=`/usr/bin/ManifestRead $SOCK_NAME "name"`

DIST_ISO=${OUTPUT_PATH}/${DISTRO_NAME}.iso

DIST_ISO_SORT=$SRC/slim_cd/iso.sort
ADMIN_FILE=$TMPDIR/admin
BOOT_FILENAME=x86.microroot
BOOT_ARCHIVE=$DIST_PROTO/boot/$BOOT_FILENAME
TEMP_ARCHIVE=$TMPDIR/$BOOT_FILENAME
MICROROOT=$DIST_PROTO/bootcd_microroot
RAMDISK_SIZE=200000


if [ ! -e /usr/bin/7za ] ; then
    echo "/usr/bin/7za is not available on your system. Please pkg install SUNWp7zip and rerun"
    exit 1
fi

(
echo "=== $0 started at `date`"


#
# Pre-configure Gnome databases
#

echo "Configuring Gnome in PROTO area"

#
#Create a temporary /dev/null since many GNOME scripts
#redirect their output to /dev/null.  The /dev/null here will
#not have the same link structure as the one in a regular system,
#it is just a character type special file. 
#

echo "dev/null" | (cd / ; cpio -Lp $DIST_PROTO)

#
# The GNOME scripts decide whether to regenerate its caches
# by looking at the timestamps of certain files delivered by GNOME packages.
# When IPS installs packages, there's no guarantee that
# they are installed in a certain order.  So, looking
# at the timestamp is not a valid method.  Since we
# want to make sure that all the caches are regenerated,
# all 4 caches that have to be regenerated will be removed.
# Note that this is just a workaround until we figure out how
# to solve the problem of forcing the cache to regenerate.
#
# With this workaround, also make sure that the icon-cache SMF service
# comes after the pixbuf-loaders-installer SMF service, because the
# icon-cache service depends on the existence of the gdk-pixbuf.loaders cache.
#
/bin/rm -f $DIST_PROTO/usr/share/applications/mimeinfo.cache \
	$DIST_PROTO/etc/gtk-2.0/gtk.immodules \
	$DIST_PROTO/etc/amd64/gtk-2.0/gtk.immodules \
	$DIST_PROTO/etc/gtk-2.0/gdk-pixbuf.loaders \
	$DIST_PROTO/etc/amd64/gtk-2.0/gdk-pixbuf.loaders \
	$DIST_PROTO/usr/share/mime/mimeinfo.cache

chroot $DIST_PROTO /bin/sh /lib/svc/method/desktop-mime-cache start
chroot $DIST_PROTO /bin/sh /lib/svc/method/gconf-cache start
chroot $DIST_PROTO /bin/sh /lib/svc/method/input-method-cache start
chroot $DIST_PROTO /bin/sh /lib/svc/method/mime-types-cache start
chroot $DIST_PROTO /bin/sh /lib/svc/method/pixbuf-loaders-installer start
chroot $DIST_PROTO /bin/sh /lib/svc/method/icon-cache start

#Remove the temp /dev/null
/bin/rm $DIST_PROTO/dev/null

echo "Creating font cache"
[ -x ${DIST_PROTO}/usr/bin/fc-cache ] && chroot $DIST_PROTO /usr/bin/fc-cache --force

#
# Remove the indices, from the IPS data directory, if any,
# since they are taking up a lot of space, and
# pkg search will work without them.
#
/bin/rm -rf $DIST_PROTO/var/pkg/index


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

# Perform special processing to create Live CD
livemedia_processing $DIST_PROTO $TMPDIR

# If additonal special processing is provided in the tar file
# by the user, execute it.
if [ "$DIST_ADDITIONAL_MOD" != "" ] ; then
	# Extract the post processing archive into the temp dir
	# Assuming the archive is a tar file.

	cd $TMPDIR
	/bin/tar -xf $DIST_ADDITIONAL_MOD
	if [ $? -ne 0 ] ; then
		echo "FAILURE: Error in untarring $DIST_ADDITIONAL_MOD"
		fatal_exit	
	fi
	# This needs to be changed so it's not hardcoded.
	POST_PROCESS_SCRIPT=post_process
	#Make sure the post-process script is there
	if [ -f $POST_PROCESS_SCRIPT  -a -x $POST_PROCESS_SCRIPT ] ; then 
		./$POST_PROCESS_SCRIPT $DIST_PROTO $MICROROOT $TMPDIR
		if [ $? -ne 0 ] ; then
			echo "FAILURE: Fatal error running $POST_PROCESS_SCRIPT"
			fatal_exit	
		fi
	else
		echo "Post process script not found in archive"
		echo "Modification is not done"
	fi
fi

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

create_iso

cleanup

exit 0

) 2>&1 | tee $SRC/$0.log

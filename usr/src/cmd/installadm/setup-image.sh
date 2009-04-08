#!/bin/sh
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

# Description:
#       This script contain functions to create and delete net images
#	The create_image function creates a netimage from an iso or
#	another directory that contain netimage. The target directory is
#	validated and the system checked for space availability.
#	The contents is copied to the target directory and a link is created
#	to the webserver running on a standard port.
#	The document root is assumed to be /var/ai/image_server/images
#	The delete_image removes the directory and the link under the
#	document root.

APACHE2=/usr/apache2/2.2/bin/apachectl
AI_HTTPD_CONF=/var/installadm/ai-webserver/ai-httpd.conf
MOUNT_DIR=/tmp/installadm.$$
DOCROOT=/var/ai/image-server/images
AI_NETIMAGE_REQUIRED_FILE="solaris.zlib"
DF="/usr/sbin/df"
diskavail=0
lofi_dev=""
image_source=""

#
# cleanup_and_exit
#
# Purpose : Cleanup and exit with the passed parameter
#
# Arguments : 
#	exit code
#
cleanup_and_exit()
{
	if [ -f "$image_source" ]; then
		unmount_iso_image $image_source
	fi

	exit $1
}

#
# usage
#
# Purpose : Print the usage message in the event the user
#           has input illegal command line parameters and
#           then exit
#
# Arguments : 
#	none
#
usage()
{
	echo "setup_image <create> <source> <destination>"
	echo "setup_image <delete> <directory>"
	cleanup_and_exit 1
}

#
# validate_uid
#
# Purpose : Make sure script is being run by root
#
# Arguments :
#	none
#
validate_uid()
{
	uid=`/usr/bin/id | /usr/bin/sed 's/uid=\([0-9]*\)(.*/\1/'`
	if [ $uid != 0 ] ; then
		print_err "You must be root to execute this script"
		exit 1
	fi
}

print_err() {
	echo "$@" >&2
}

#
# check_target
#
# Purpose : Create the directory that will contain the net image
#           If the target is not on the local system then print an
#	    error message if it is not local.
#
# Arguments : 
#	$1 - pathname to the directory 
#
# Side Effects :
#	diskavail - the amount of space available for the the install
#               server is set
#
check_target()
{
	echo $1 | grep '^/.*' >/dev/null 2>&1
	status=$?
	if [ "$status" != "0" ] ; then
	    print_err "ERROR: A full pathname is required for the <destination directory>"
	    cleanup_and_exit 1
	fi
	if [ ! -d $1 ]; then
		mkdir -p $1
		if [ $? -ne 0 ]; then
			print_err "ERROR: unable to create $1"
			cleanup_and_exit 1
		fi
	fi
	# check to see if target is a local filesystem
	# because we cannot export it otherwise.
	${DF} -l $1 >/dev/null 2>&1
	if [ $? -ne 0 ] ; then
		print_err "ERROR: $1 is not located in a local filesystem"
		cleanup_and_exit 1
	fi
	diskavail=`${DF} -k $1 | \
			( read junk; read j1 j2 j3 size j5; echo $size )`
}

#
# mount_iso_image
#
# Purpose : If the source is an iso image, lofimount the source
#
# Arguments : 
#	$1 - source pathname
#
mount_iso_image()
{
	file=$1
	lofi_dev=`lofiadm -a $file` > /dev/null 2>&1
	status=$?
	if [ $status -ne 0 ] ; then
	    print_err "ERROR: Cannot mount $file as a lofi device"
	    cleanup_and_exit 1
	fi
	mkdir -p $MOUNT_DIR
	mount -F hsfs -o ro $lofi_dev $MOUNT_DIR > /dev/null 2>&1
	status=$?
	if [ $status -ne 0 ] ; then
	    print_err "ERROR: Cannot mount $file as a lofi device"
	    cleanup_and_exit 1
	fi
}

#
# unmount_iso_image
#
# Purpose : unmount the lofimounted image and remove lofi device
#
# Arguments :  None
#
unmount_iso_image()
{
	umount $MOUNT_DIR > /dev/null 2>&1
	lofiadm -d $lofi_dev > /dev/null 2>&1
	rmdir $MOUNT_DIR
}

#
# create_image
#
# purpose : Copy the image from source to destination and create links to
# the webserver so that it can be accessed using http
#
# Arguments: 
#	$1 - Path to image source (iso or directory)
#	$2 - Destination directory
#
create_image()
{
	image_source=$1
	target=$2

	# Make sure source exists
	if [ ! -e "$image_source" ]; then
		print_err "ERROR: The source image does not exist: ${image_source}"
		cleanup_and_exit 1
	fi

	# Mount if it is iso
	if [ -f "$image_source" ]; then
		mount_iso_image $image_source
		src_dir=$MOUNT_DIR
	else
		src_dir=$image_source
	fi	

	#
	# Check whether source image is a net image
	#
	if [ ! -f ${src_dir}/${AI_NETIMAGE_REQUIRED_FILE} ]; then
		print_err "ERROR: The source image is not a AI net image"
		cleanup_and_exit 1
	fi

	# Remove consecutive and trailing slashes in the specified target
	dirname_target=`dirname "${target}"`
	basename_target=`basename "${target}"`

	# If basename returns / target was one or more slashes.
	if [ "${basename_target}" == "/" ]; then
		target="/"
	# Else if dirname returns / append basename to dirname
	elif [ "${dirname_target}" == "/" ]; then
		target="${dirname_target}${basename_target}"
	# Else insert a / between dirname and basename
	# The inserted slash is necessary because dirname strips it.
	else
		target="${dirname_target}/${basename_target}"
	fi

	# create target directory, if needed
	check_target $target

	#
	# Check for space to create image and in /tftpboot
	#
	space_reqd=`du -ks ${src_dir} | ( read size name; echo $size )`
	# copy the whole CD to disk except Boot image
	if [ $space_reqd -gt $diskavail ]; then
		print_err "ERROR: Insufficient space to copy CD image"
		print_err "       ${space_reqd} necessary - ${diskavail} available"
		cleanup_and_exit 1
	fi

	current_dir=`pwd`
	echo "Setting up the target image at ${target} ..."
	cd ${src_dir}
	find . -depth -print | cpio -pdmu ${target} >/dev/null 2>&1
	copy_ret=$?
	cd $current_dir

	if [ $copy_ret -ne 0 ]; then
		print_err "ERROR: Setting up AI image failed"
		cleanup_and_exit 1
	fi

	# Check whether the AI imageserving webserver is running. If not
	# start the webserver
	pgrep -f ai-httpd.conf > /dev/null 2>&1
	if [ $? -ne 0 ]; then
		${APACHE2} -f ${AI_HTTPD_CONF} -k start
	fi

	# Create a link from the AI webserver so that it can accessed by the client
	target_path=`dirname $target`

	mkdir -p ${DOCROOT}/$target_path
	ln -s $target ${DOCROOT}/$target
	return 0
}

#
# delete_image
#
# purpose : Delete image and remove the links in the webserver
#
# Arguments: 
#	$1 - Full path of the image directory
#
delete_image()
{
	dir=$1

	if [ -d $dir ] ; then
		rm -rf $dir
	fi
	rm -f ${DOCROOT}/target
}

#################################################################
# MAIN
#
#################################################################

#
# Check whether enough arguments are passed

if [ $# -lt 2 ]; then
	usage
fi

# Make sure script is being run by root
validate_uid

action=$1

if [ "$action" = "create" ]; then
	# Need 3 args for create including action=create
	if [ $# -ne 3 ]; then
		usage
	fi
	src=$2
	dest=$3
	create_image $src $dest
	status=$?
elif [ "$action" = "delete" ]; then
	directory=$2
	delete_image $directory
	status=$?
else 
	echo " $1 - unsupported image action"
	exit 1
fi

cleanup_and_exit $status

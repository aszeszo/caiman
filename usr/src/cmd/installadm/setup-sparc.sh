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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.

# Description:
#	This script sets up the wanboot.conf file which is used
#	to boot the sparc netimage.
#
# Files potentially changed on server:
# /etc/netboot - directory created
# /etc/netboot/wanboot.conf - file created
# /etc/netboot/<MACID>/wanboot.conf - file created 
# <image>/install.conf - file created 

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

. /usr/lib/installadm/installadm-common


WANBOOTCGI="/usr/lib/inet/wanboot/wanboot-cgi"
CGIBIN_WANBOOTCGI="cgi-bin/wanboot-cgi"


#
# Create the install.conf file (replace if it already exists)
#
# Arguments:
#	$1 - Name of service
#       $2 - Location of service
#	$3 - Absolute path to image (where file will be placed)
#
create_installconf()
{
	svcname=$1
	svc_address=$2
	image_path=$3

	installconf="${image_path}/${SPARC_INSTALL_CONF}"
	tmpconf=${installconf}.$$

	# Store service name
	printf "install_service=" > ${tmpconf}
	printf "${svcname}\n" >> ${tmpconf}

	#
	# add service location
	# it can be either provided by the caller or set to "unknown"
	#
	# If set to "unknown", try to look up this information
	# in service configuration database right now
	#
	[ "$svc_address" = "$SERVICE_ADDRESS_UNKNOWN" ] &&
	    svc_address=$(get_service_address ${svc_name})

	if [ "$svc_address" != "$SERVICE_ADDRESS_UNKNOWN" ] ; then
		print "Service discovery fallback mechanism set up"

		printf "install_svc_address=" >> ${tmpconf}
		printf "$svc_address\n" >> ${tmpconf}
	else
		print "Could not determine service location, fallback " \
		    "mechanism will not be available"
	fi

	# Rename the tmp file to the real thing
	$MV ${tmpconf} ${installconf}

	return 0
}

#
# determine install service which is used by default by inspecting
# service-specific wanboot.conf file referenced by /etc/netboot/wanboot.conf
# symbolic link.
#
# [1] obtain value of 'root_file' option - it points to boot_archive
#     within AI image. It is located at <ai_image>/boot/platform/sun4v/boot_archive.
#     For backwards compatibility, we also look in <ai_image>/boot/boot_archive.
# [2] get service name from <ai_image>/install.conf file
#
get_service_with_global_scope()
{
	root_file_location=$($GREP "^root_file" \
	    "${WANBOOT_CONF_SPEC}" | $CUT -d '=' -f 2)

	srv_dfl=""

	if [ -f "$root_file_location" ] ; then
		image_directory=$($DIRNAME "$root_file_location")
		image_directory=$($DIRNAME "$image_directory")

		# For backward compatibility we check to see if the
		# boot_archive is in /boot or /boot/platform/sun4v
		# and calculate the image_directory accordingly.
		$GREP "/boot/platform/sun4v/boot_archive" ${WANBOOT_CONF_SPEC} > /dev/null
		if [ $? -eq 0 ]; then
			#
			# Invoking dirname twice to move up two directory levels
			#
			image_directory=$($DIRNAME "$image_directory")
			image_directory=$($DIRNAME "$image_directory")
		fi
		install_conf="$image_directory/$SPARC_INSTALL_CONF"
		srv_dfl=$($GREP "^install_service" \
		    $install_conf | $CUT -d '=' -f 2)

	else
		print "root file from ${WANBOOT_CONF_SPEC} does not exist"
	fi

	print "$srv_dfl"
}

#
# Create the wanboot.conf file (replace if it already exists)
#
# Arguments:
#	$1 - directory in which to place the wanboot.conf file
#	$2 - ip address of server
#	$3 - Absolute path to image
#
create_wanbootconf()
{
	confdir=$1
	svr_ip=$2
	image_path=$3

	get_http_port
	if [ $? -ne 0 ] ; then
		print "Warning: Unable to determine the service's default port"
		print "         Using 5555 as the service's port"
		HTTP_PORT=5555
	fi

	wanbootconf="${confdir}/${WANBOOT_CONF_FILE}"

	# Create target directory if it does not already exist
	[ ! -d "$confdir" ] && $MKDIR -p -m 755 "$confdir"

	tmpconf=${wanbootconf}.$$
	pgrp="sun4v"	# hardcoded for now

	printf "root_server=" > ${tmpconf}
	printf "http://${svr_ip}:${HTTP_PORT}/" >> ${tmpconf}
	printf "${CGIBIN_WANBOOTCGI}\n" >> ${tmpconf}

	if [ -f ${image_path}/boot/boot_archive ] ; then
		# for backwards compatibility
		printf "root_file=" >> ${tmpconf}
		printf "${image_path}/boot/boot_archive\n" >> ${tmpconf}
	else
		printf "root_file=" >> ${tmpconf}
		printf "${image_path}/boot/platform/${pgrp}/boot_archive\n" >> ${tmpconf}
	fi

	printf "boot_file=" >> ${tmpconf}
	printf "${image_path}/platform/${pgrp}/wanboot\n" >> ${tmpconf}

	printf "encryption_type=\n" >> ${tmpconf}
	printf "signature_type=\n" >> ${tmpconf}
	printf "server_authentication=no\n" >> ${tmpconf}
	printf "client_authentication=no\n" >> ${tmpconf}

	# rename the tmp file to the real thing
	print "Creating SPARC configuration file"
	$MV ${tmpconf} ${wanbootconf}

	return 0
}

		
#
# This is an internal function
# So we expect only limited use

if [ $# -lt 3 ]; then
	print "Internal function to manage SPARC setup does not have enough data"
	exit 1
fi

# see if we are multi-homed
if (( $(valid_networks | $WC -l) != "1" )); then
	# for multi-homed AI servers use the host's nodename
	srv_ip=$(uname -n)
else # we are single-homed
	# get server ip address
	srv_ip=$(get_ip_for_net $(valid_networks))
	if [[ -z $srv_ip ]]; then
		print "Failed to get server's IP address."
		exit 1
	fi
fi

if [ "$1" = "server" ]; then
	img_path=$2
	svc_name=$3
	svc_address=$4

	if [ ! -f "${WANBOOTCGI}" ]; then
		print "${WANBOOTCGI} does not exist"
		exit 1
	fi

	# create install.conf file at top of image.
	# it contains the service name and service location
	#
	create_installconf $svc_name $svc_address $img_path

	# ensure we have the /etc/netboot directory
	#
	$MKDIR -p ${NETBOOTDIR}

	#
	# Populate service-specific wanboot.conf file in
	# /etc/netboot/<service_name>/ directory. /etc/netboot/wanboot.conf
	# can be created by user as symbolic link to that file in order
	# to change the service with global scope (serving clients which
	# don't have per-client binding explicitly created by
	# 'create-client' command).
	#
	create_wanbootconf "${NETBOOTDIR}/${svc_name}" $srv_ip "$img_path"

	#
	# If there is no service with global scope set yet, select this one
	# by creating /etc/netboot/wanboot.conf as a link to it.
	#
	# Otherwise, preserve existing configuration and inform user
	# how to change the service manually.
	#

	if [ -f "${WANBOOT_CONF_SPEC}" ] ; then
		srv_dfl=$(get_service_with_global_scope)

		if [[ "XX${srv_dfl}" == "XX" ]]; then
			exit 1
		fi

		print "Service $srv_dfl is currently being used by SPARC" \
		    "clients which have not explicitly been associated" \
		    "with another service via the 'create-client' subcommand."

		print "To select service $svc_name for those SPARC clients," \
		    "use the following commands:"

		print "$RM -f $WANBOOT_CONF_SPEC"
		print "$LN -s ${svc_name}/${WANBOOT_CONF_FILE} $NETBOOTDIR"
	else
		$RM -f "$WANBOOT_CONF_SPEC"
		$LN -s "${svc_name}/${WANBOOT_CONF_FILE}" "$NETBOOTDIR"
	fi

	status=$?

elif [ "$1" = "client" ]; then
	macid=$2
	img_path=$3

	# create /etc/netboot sub-directories
	#
	wbootdir="${NETBOOTDIR}/${macid}"
	$MKDIR -p ${wbootdir}

	create_wanbootconf $wbootdir $srv_ip $img_path
	status=$?
else 
	print " $1 - unsupported SPARC setup service action"
	exit 1
fi


if [ $status -eq 0 ]; then
	exit 0
else
	exit 1
fi

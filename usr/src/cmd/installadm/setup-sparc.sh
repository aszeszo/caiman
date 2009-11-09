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
#	This script sets up the wanboot.conf file which is used
#	to boot the sparc netimage.
#
# Files potentially changed on server:
# /etc/netboot - directory created
# /etc/netboot/<network number> - directory created
# /etc/netboot/wanboot.conf - file created
# /etc/netboot/<network number>/<MACID>/wanboot.conf - file created 
# <image>/install.conf - file created 

. /usr/lib/installadm/installadm-common


WANBOOTCGI="/usr/lib/inet/wanboot/wanboot-cgi"
CGIBINDIR="/var/ai/image-server/cgi-bin"


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
	    svc_address=`get_service_address ${svc_name}`

	if [ "$svc_address" != "$SERVICE_ADDRESS_UNKNOWN" ] ; then
		echo "Service discovery fallback mechanism set up"

		printf "install_svc_address=" >> ${tmpconf}
		printf "$svc_address\n" >> ${tmpconf}
	else
		echo "Couldn't determine service location, fallback " \
		    "mechanism will not be available"
	fi

	# Rename the tmp file to the real thing
	mv ${tmpconf} ${installconf}

	return 0
}

#
# determine install service which is used by default by inspecting
# service-specific wanboot.conf file referenced by /etc/netboot/wanboot.conf
# symbolic link.
#
# [1] obtain value of 'root_file' option - it points to boot_archive
#     within AI image. It is located at <ai_image>/boot/platform/sun4v/boot_archive.
# [2] get service name from <ai_image>/install.conf file
#
get_service_with_global_scope()
{
	root_file_location=`/usr/bin/grep "^root_file" \
	    "${WANBOOT_CONF_SPEC}" | cut -d '=' -f 2`

	srv_dfl=""

	if [ -f "$root_file_location" ] ; then
		image_directory=`/usr/bin/dirname "$root_file_location"`
		image_directory=`/usr/bin/dirname "$image_directory"`
		install_conf="$image_directory/$SPARC_INSTALL_CONF"
		srv_dfl=`/usr/bin/grep "^install_service" \
		    $install_conf | cut -d '=' -f 2`
	fi

	echo "$srv_dfl"
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

	wanbootconf="${confdir}/${WANBOOT_CONF_FILE}"

	# Create target directory if it doesn't already exist
	[ ! -d "$confdir" ] && /usr/bin/mkdir -p -m 755 "$confdir"

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
	echo "Creating SPARC configuration file"
	mv ${tmpconf} ${wanbootconf}

	return 0
}

		
#
# This is an internal function
# So we expect only limited use

if [ $# -lt 3 ]; then
	echo "Internal function to manage SPARC setup doesn't have enough data"
	exit 1
fi

# get server ip address
srv_ip=`get_server_ip`
if [ -z $srv_ip ] ; then
	echo "Failed to get server's IP address."
	exit 1
fi

# get server netmask
srv_netmask=`get_ip_netmask $srv_ip`
if [ -z $srv_netmask ]; then
	echo "Failed to get server's netmask."
	exit 1
fi

# determine network
net=`get_network $srv_ip $srv_netmask`
if [ -z $net ]; then
	echo "Failed to get network for $srv_ip"
	exit 1
fi

if [ "$1" = "server" ]; then
	img_path=$2
	svc_name=$3
	svc_address=$4

	if [ ! -f "${WANBOOTCGI}" ]; then
		echo "${WANBOOTCGI} does not exist"
		exit 1
	fi

	if [ ! -d "${CGIBINDIR}" ]; then
		echo "${CGIBINDIR} does not exist"
		exit 1
	fi

	# copy over wanboot-cgi
	cp ${WANBOOTCGI} ${CGIBINDIR}

	# create install.conf file at top of image.
	# it contains the service name and service location
	#
	create_installconf $svc_name $svc_address $img_path

	# create /etc/netboot directories
	#
	mkdir -p ${NETBOOTDIR}/${net}

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
		srv_dfl=`get_service_with_global_scope`

		echo "Service $srv_dfl is currently being used by SPARC" \
		    "clients which have not explicitly been associated" \
		    "with another service via the 'create-client' subcommand."

		echo "To select service $svc_name for those SPARC clients," \
		    "use the following commands:"

		echo "/usr/bin/rm -f $WANBOOT_CONF_SPEC"
		echo "/usr/bin/ln -s ${svc_name}/${WANBOOT_CONF_FILE} $NETBOOTDIR"
	else
		/usr/bin/rm -f "$WANBOOT_CONF_SPEC"
		/usr/bin/ln -s "${svc_name}/${WANBOOT_CONF_FILE}" "$NETBOOTDIR"
	fi

	status=$?

elif [ "$1" = "client" ]; then
	macid=$2
	img_path=$3

	# create /etc/netboot sub-directories
	#
	wbootdir="${NETBOOTDIR}/${net}/${macid}"
	mkdir -p ${wbootdir}

	create_wanbootconf $wbootdir $srv_ip $img_path
	status=$?
else 
	echo " $1 - unsupported SPARC setup service action"
	exit 1
fi


if [ $status -eq 0 ]; then
	exit 0
else
	exit 1
fi

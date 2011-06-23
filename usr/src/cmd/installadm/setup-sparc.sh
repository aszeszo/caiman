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
# <image>/system.conf - file created 

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

. /usr/lib/installadm/installadm-common


WANBOOTCGI="/usr/lib/inet/wanboot/wanboot-cgi"
CGIBIN_WANBOOTCGI="cgi-bin/wanboot-cgi"
SPARC_SYSTEM_CONF="system.conf"


#
# Create the system.conf file (replace if it already exists)
#
# Arguments:
#	$1 - Name of service
#       $2 - Location of service
#	$3 - Absolute path to image (where file will be placed)
#
create_systemconf()
{
	svcname=$1
	svc_address=$2
	sysconf_path=$3

	systemconf="${sysconf_path}/${SPARC_SYSTEM_CONF}"
	tmpconf=${systemconf}.$$

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
	$MV ${tmpconf} ${systemconf}

	return 0
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

	printf "system_conf=system.conf\n" >> ${tmpconf}
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
	sysconf_path=$5

	if [ ! -f "${WANBOOTCGI}" ]; then
		print "${WANBOOTCGI} does not exist"
		exit 1
	fi

	# Create system.conf file in /var/ai/service/<svcname>. It will
	# eventually be lofi mounted at the top of the image.
	# It contains the service name and service location.
	#
	create_systemconf $svc_name $svc_address $sysconf_path

	# ensure we have the /etc/netboot directory
	#
	$MKDIR -p ${NETBOOTDIR}

	#
	# Populate service-specific wanboot.conf file in the service's image,
	# which is later mounted to /etc/netboot/<service_name>/.
	#
	create_wanbootconf "$img_path" $srv_ip "$img_path"

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

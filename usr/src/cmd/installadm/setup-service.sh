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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.

# Description:
#       This script contains interfaces that allow look for a service,
#	register a new service and remove a running service.
#	The service typeis assumed to be _OSInstall_.tcp and the
#	service domain is assumed to be local.
#	Lookup interface searches for the specified service name.
#	Register starts the service and checks the output to make sure that
#	the service is running before returning
#	Remove service first lookup for the service before terminating
#

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

. /usr/lib/installadm/installadm-common

IMG_AI_DEFAULT_MANIFEST="/auto_install/default.xml"
SYS_AI_DEFAULT_MANIFEST="/usr/share/auto_install/default.xml"
AI_SETUP_WS=/var/installadm/ai-webserver
VARAI=/var/ai
AIWEBSERVER="aiwebserver"
AIWEBSERVER_PROGRAM="/usr/lib/installadm/webserver"
ret=0

#
# Find whether the service is running;
# as determined by if the AI webserver is running
#
# Arguments:
#	$1 - Service Name (for example my_install)
#
# Returns:
#	0 - If the service is running 
#	1 - If the service is not running
#
lookup_service()
{
	name=$1

	# check webserver port and that webserver is running on said port
	webserver_port=$($SVCPROP -cp AI${name}/txt_record ${SMF_INST_SERVER} \
	    2>/dev/null | $CUT -f 2 -d':')
	if (( $webserver_port <= 0 )); then
		return 1
	fi
	if [[ $($PGREP -f "installadm/webserver -p $webserver_port") ]]; then
		return 0
	fi

	# we did not find a webserver PID and process
	return 1
}

#
# Refresh the SMF service and verify the given service is advertised
# via mDNS, assuming the service to be properly enabled
# for the aimdns(1) command
#
# Arguments:
#	$1 - Service Name (for example my_install)
#
# Returns:
#	0 - If the service is successfully registered
#	1 - If the service is not registered
#
refresh_smf_and_verify_service()
{
	name=$1

	# check webserver port and that the service is enabled
	port=$($SVCPROP -cp AI${name}/txt_record ${SMF_INST_SERVER} \
	    2>/dev/null | $CUT -f 2 -d':')
	if (( $port <= 0 )); then
		print "The service ${name} does not have a valid websever" \
		    "port set"
		return 1
	fi

	if [[ "$($SVCPROP -cp AI${name}/status ${SMF_INST_SERVER} \
	    2>/dev/null)" != "on" ]]; then
		print "The service ${name} is not enabled"
		return 1
	fi

	print "Refreshing install services"

	# refresh the service to re-register all enabled services
	$SVCADM refresh ${SMF_INST_SERVER}

	# sleep 5 seconds waiting for registrations to happen
	sleep 5

	# verify service registration (with a 1 second investigation time out
	# since the record should be local)
	if $AIMDNS -t 1 -f $name >/dev/null 2>&1; then
		return 0
	else
		print "The service ${name} could not be registered"
		return 1
	fi
}

#
# Disable a running service by name
#
# Arguments:
#	$1 - Service Name (for example my_install)
#
# Returns:
#	0 - If the service is successfully removed
#	1 - If the service cannot be removed
#
disable_service()
{
	name=$1

	# Check whether the service is running now

	lookup_service $name
	if (( $? == 0 )); then
		# Service is running
		# We will be terminating the process
		print "Stopping the service ${name}"

		# Stop the webserver corresponding to this service
		port=$($SVCPROP -cp AI${name}/txt_record ${SMF_INST_SERVER} \
		    2>/dev/null | $CUT -f 2 -d':')
		if (( $port != 0 )); then
			stop_ai_webserver $port
		fi

		# refresh the service to de-register all disabled services
		$SVCADM refresh ${SMF_INST_SERVER}

		ret=0
	else
		ret=1
	fi
	return $ret
}

#
# Populate the data directory used by the AI webserver associated
# with the service being set up.
#
# Arguments:
#	$1 - The data directory used by the AI webserver associated with
#	     the service.
#	$2 - The target imagepath directory for the service being set up.
#
setup_data_dir()
{
	data_dir=$1
	imagepath=$2

	$MKDIR -p $data_dir
	current_dir=$(pwd)
	cd ${AI_SETUP_WS}
	$FIND . -depth -print | $CPIO -pdmu ${data_dir} >/dev/null 2>&1
	cd $current_dir

	#
	# Set up the default manifest for this service.
	#
	setup_default_manifest $data_dir $imagepath
	if (( $? != 0 )); then
		return 1
	fi

	return 0
}

#
# Set up the default manifest for a service by using the default.xml
# file from the service's image.  A service's manifests are internally
# kept as files in the service's webserver ${data_dir}/AI_data directory,
# so we simply copy the file to that directory.
#
# If a default.xml doesn't exist in the service's image, fall back to
# using the default.xml on the running system.
#
# Arguments:
#	$1 - The data directory for the AI webserver associated with
#	     the service.
#	$2 - The target imagepath directory for the service being set up.
#
setup_default_manifest()
{
	data_dir=$1
	imagepath=$2

	if [[ -f ${imagepath}${IMG_AI_DEFAULT_MANIFEST} ]]; then
		$CP ${imagepath}${IMG_AI_DEFAULT_MANIFEST} \
		    ${data_dir}/AI_data/default.xml
	elif [[ -f ${SYS_AI_DEFAULT_MANIFEST} ]]; then
		print "Warning: Using default manifest <${SYS_AI_DEFAULT_MANIFEST}>"
		$CP ${SYS_AI_DEFAULT_MANIFEST} \
		    ${data_dir}/AI_data/default.xml
	else
		print "Failed to find a default manifest."
		return 1
	fi

	return 0
}

#
# Start the webserver for the service
#
# Arguments:
#	$1 - The DNS text record contains the host and port information for the
#	     webserver
#
# Returns:
#	0 - If the web service is successfully started
#	1 - If the web service cannot be started successfully
#
start_ai_webserver()
{
	ret=0
	txt=$1
	imagepath=$2
	# Extract the port from txt record
	port=$(print $txt | $GREP $AIWEBSERVER | $CUT -f2 -d'=' | $CUT -f2 -d':')

	#
	# Get the port and start the webserver using the data directory
	# <VARAI>/<port>
	#
	data_dir=$VARAI/$port
	log=$data_dir/webserver.log

	if [[ ! -d $data_dir ]]; then
		setup_data_dir $data_dir $imagepath
		if (( $? != 0 )); then
			ret=1
		fi
	fi

	if (( $ret == 0 )); then
		# Start the webserver
		$AIWEBSERVER_PROGRAM -p $port $data_dir > $log 2>&1 &
		if (( $? != 0 )); then
			ret=1
		fi
	fi

	return $ret
}

#
# stop the webserver for a given service
#
# Arguments:
#	$1 - The port number of the running AI webserver 
#
stop_ai_webserver()
{
	port=$1

	# Search the processes to find the webserver that is using $port
	# and kill the process

	webpid=$($PGREP -f "installadm/webserver -p $port")

	if [[ -n "${webpid}"  ]]; then
		kill $webpid > /dev/null 2>&1
	fi
}

#
# MAIN
# This is an internal function
# So we expect only limited use

if (( $# < 2 )); then
	print "Internal function to manage DNS services does not" \ 
	    "have enough data"
	exit 1
fi

if [[ "$1" == "register" ]]; then
	if (( $# < 4 )); then
		print "Install Service Registration requires four arguments"
		exit 1
	fi

	service_name=$2
	service_txt=$3
	service_imagepath=$4

	lookup_service $service_name
	status=$?
	if (( status == 1 )); then
		# Start the AI webserver using the port from txt record
		start_ai_webserver $service_txt $service_imagepath
		status=$?
		if [ $status -eq 0 ]; then
			refresh_smf_and_verify_service $service_name
			status=$?
		fi
	else
		print "The service ${name} is running."
	fi
elif [[ "$1" == "disable" ]]; then
	if (( $# < 2 )); then
		print "Install Service Disabling requires two arguments"
		exit 1
	fi

	service_action=$1
	service_name=$2

	disable_service $service_name
	status=$?
else 
	print " $1 - unsupported DNS service action"
	exit 1
fi
if (( status == 0 )); then
	exit 0
else
	exit 1
fi

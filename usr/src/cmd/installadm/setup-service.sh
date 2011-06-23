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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

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

AI_SETUP_WS=/var/installadm/ai-webserver
AI_WS_CONF=$AI_SETUP_WS/ai-httpd.conf
AI_SERVICE_DIR_PATH=/var/ai/service
AIWEBSERVER="aiwebserver"
ret=0

#
# Find whether the service is running;
# as determined by if the mDNS record is registered
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

	# check to see if the service has an mDNS record registered
	status=$($AIMDNS -f ${name} -t 2 2>/dev/null)
	if [ $? -eq 1 -o "X$status" == "X" ]; then
		return 1
	fi

	if [ "${status%%:*}" == "+" ]; then
		return 0
	fi

	# we did not find the named service's status
	return 1
}

#
# Refresh the SMF service and verify if the given service is advertised
# via mDNS.  Failure to verify that the service is registered with mDNS is
# not a fatal error, as mDNS is not required for an installation service
# to function.
#
# This method expects the service to be properly enabled/configured;
# improperly configured services will cause this function to return an error.
#
# Arguments:
#	$1 - Service Name (for example my_install)
#
# Returns:
#	0 - If the service is properly configured.
#	1 - If the service is improperly configured or not enabled.
#
refresh_smf_and_verify_service()
{
	name=$1


	# check webserver port and that the service is enabled
	port=$($PYTHON $SVC_CFG_MODULE listprop ${name} txt_record | $CUT -f 2 -d':')
	if (( port <= 0 )); then
		print "The service ${name} does not have a valid webserver" \
		    "port set"
		return 1
	fi

	if [[ "$($PYTHON $SVC_CFG_MODULE listprop ${name} status)" != "on" ]]; then
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
	if ! $AIMDNS -t 1 -f $name >/dev/null 2>&1; then
                print "Warning: mDNS registry of service ${name} could not be" \
                        "verified."
	fi

	return 0
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
	ret=0

	# Check whether the service is running now
	lookup_service $name
	if (( $? == 0 )); then
		# Service is running
		# We will be terminating the process
		print "Stopping the service ${name}"

		# The status of the install service property should already
		# be off. Refresh the service to de-register all disabled
		# services.
		$SVCADM refresh ${SMF_INST_SERVER}
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
#	$1 - The service name used by the AI webserver associated with the
#	     service
#	$2 - The DNS text record contains the host and port information for the
#	     webserver
#	$3 - The target imagepath directory for the service being set up.
#
setup_data_dir()
{
	svcname=$1
	txt=$2
	imagepath=$3

	# Extract the port from txt record
	port=$(print $txt | $GREP $AIWEBSERVER | $CUT -f2 -d'=' | $CUT -f2 -d':')

	# Get the configured service port
	http_port=$($SVCPROP -cp all_services/port $SMF_INST_SERVER)

	data_dir=$AI_SERVICE_DIR_PATH/$svcname

	$MKDIR -p $data_dir

	current_dir=$(pwd)
	cd ${AI_SETUP_WS}
	$FIND . -depth -print | $CPIO -pdmu ${data_dir} >/dev/null 2>&1
	cd $current_dir

	# make compatibility symlink
	if (( port != http_port )); then
		$LN -s $data_dir $AI_SERVICE_DIR_PATH/$port 2>/dev/null
	fi

	if (( $? != 0 )); then
		return 1
	fi

	return 0
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

if [[ "$1" == "create" ]]; then
	if (( $# < 4 )); then
		print "Install service creation requires four arguments"
		exit 1
	fi

	service_name=$2
	service_record=$3
	service_imagepath=$4

	status=0
	# Setup the AI webserver using the servicename and image path
	setup_data_dir $service_name $service_record $service_imagepath
	status=$?
elif [[ "$1" == "register" ]]; then
	if (( $# < 3 )); then
		print "Install service registration requires three arguments"
		exit 1
	fi

	service_name=$2
	service_record=$3
	port=$(print $service_record | $GREP $AIWEBSERVER | $CUT -f2 -d'=' | $CUT -f2 -d':')

	status=0
	if [[ ! -e $AI_SERVICE_DIR_PATH/$service_name && ! -e $AI_SERVICE_DIR_PATH/$port ]] ; then
		# Should already be created, give error if not found
		print "Install Service register expects existing /var/ai/service directory"
		exit 1
	fi
	if (( status == 0 )); then
		refresh_smf_and_verify_service $service_name
		status=$?
	fi
elif [[ "$1" == "disable" ]]; then
	if (( $# < 2 )); then
		print "Install service disabling requires two arguments"
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

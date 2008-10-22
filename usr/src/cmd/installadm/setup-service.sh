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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.

# Description:
#       This script contains interfaces that allow look for a service,
#	register a new service and remove a running service.
#	All the service functions uses the test tool called dns-sd.
#	dns-sd is meant for dynamic services and so it never returns once
#	the it is invoked. So it is invoked in the background and terminated
#	once we get the necessary data.
#	The service typeis assumed to be _OSInstall_.tcp and the
#	service domain is assumed to be local.
#	Lookup interface searches for the specified service name.
#	Register starts the service and checks the output to make sure that
#	the service is running before returning
#	Remove service first lookup for the service before terminating
#

SVCS=/usr/bin/svcs
SVCADM=/usr/sbin/svcadm
TMP_FILE=/tmp/dns-sd.out.$$
AI_SETUP_WS=/var/installadm/ai-webserver
DOCROOT=/var/ai
AIWEBSERVER="aiwebserver"
AIWEBSERVER_PROGRAM="/usr/lib/installadm/webserver"
PHRASE1="registered"
PHRASE2="active"
ret=0

#
# Find whether the service is running
#
# Arguments:
#	$1 - Service Name (for example my_install)
#	$2 - Service Type (_OSInstall._tcp)
#	$3 - domain (local)
#
# Returns:
#	0 - If the service is running 
#	1 - If the service is not running
#
lookup_service()
{
	name=$1
	type=$2
	domain=$3
	# dns-sd doesn't time out and return. It keeps on running
	# even for a small lookup. We have to kill the process
	# once we got the information
	/usr/bin/dns-sd -L ${name} ${type} ${domain} > $TMP_FILE &
	pid=$!
	#
	# Sleep for 2 seconds for the lookup to find our service
	#
	sleep 2
	grep "$name" $TMP_FILE > /dev/null 2>&1
	if [ $? -eq 0 ]; then
		txt=`grep $AIWEBSERVER $TMP_FILE | cut -f2 -d'='`
		ret=0
	else
		ret=1
	fi
	kill $pid  > /dev/null 2>&1
	rm -f $TMP_FILE
	return $ret
}

#
# List the running services
#
# Arguments:
#	$1 - Service Type (_OSInstall._tcp)
#	$2 - domain (local)
#
# Returns:
#	0 - If the browse is successful
#	1 - If the browse fails
#
list_service()
{
	type=$1
	domain=$2
	# dns-sd doesn't time out and return. It keeps on running
	# even for a small lookup. We have to kill the process
	# once we got the information
	/usr/bin/dns-sd -B ${type} ${domain} > $TMP_FILE &
	pid=$!
	#
	# Sleep for 5 seconds and display the available services
	#
	sleep 5

	grep "${type}" $TMP_FILE > /dev/null 2>&1
	if [ $? -eq 0 ]; then
		echo "The install services running on the system are:"
		while read line; do
			echo $line | grep $type > /dev/null 2>&1
			if [ $? -eq 0 ]; then
				echo ${line} | nawk '{ print $7 }'
			fi
		done < $TMP_FILE
		ret=0
	else
		grep "failed" $TMP_FILE > /dev/null 2>&1
		if [ $? -eq 0 ]; then
			echo "List services failed"
			ret=1
		else
			echo "No install services running on the system"
			ret=0
		fi
	fi
	kill ${pid}  > /dev/null 2>&1
	rm -f $TMP_FILE
	return $ret
}

#
# Register the given service in DNS
# First check whether the service is running
# Register the service only if it is not running already.
#
# Arguments:
#	$1 - Service Name (for example my_install)
#	$2 - Service Type (_OSInstall._tcp)
#	$3 - domain (local)
#	$4 - port
#	$5 - DNS text record (aiwebserver=<host>:<port>)
#
# Returns:
#	0 - If the service is successfully started
#	1 - If the service cannot be started successfully
#
register_service()
{
	name=$1
	type=$2
	domain=$3
	port=$4
	txt=$5

	#
	# If the host name instead of host address is given, create a 
	# new text record with host address
	#
	host=`echo $txt | cut -f2 -d'=' | cut -f1 -d':'`
	aiport=`echo $txt | cut -f2 -d'=' | cut -f2 -d':'`
	ip=`getent hosts $host | nawk '{ print $1 }'`

	new_txt="${AIWEBSERVER}=$ip:$aiport"

	echo "Registering the service ${name}.${type}.${domain}"
	/usr/bin/dns-sd -R ${name} ${type} ${domain} ${port} ${new_txt} > $TMP_FILE 2>&1 &

	pid=$!
	# Wait for few seconds for the registration to complete
	sleep 5
	# Now check whether the service is registered by parsing the output
	# It is ugly and should be rewritten using the service discovery
	# library
	grep "$name" $TMP_FILE | grep "$PHRASE1" | grep "$PHRASE2" > /dev/null 2>&1
	if [ $? -eq 0 ]; then
		ret=0
	else
		echo "The service ${name}.${type}.${domain} is not registered"
		kill $pid > /dev/null 2>&1
		ret=1
	fi
	
	rm -f $TMP_FILE
	return $ret
}

#
# Remove a running service by name
#
# Arguments:
#	$1 - Service Name (for example my_install)
#	$2 - Service Type (_OSInstall._tcp)
#	$3 - domain (local)
#
# Returns:
#	0 - If the service is successfully removed
#	1 - If the service cannot be removed
#
remove_service()
{
	name=$1
	type=$2
	domain=$3

	# Check whether the service is running now
	/usr/bin/dns-sd -L ${name} ${type} ${domain} > $TMP_FILE &
	pid=$!
	#
	# Sleep for 2 seconds for the lookup to find our service
	#
	sleep 2
	grep "$name" $TMP_FILE > /dev/null 2>&1
	if [ $? -eq 0 ]; then
		# Service is running
		# There is no stop service command
		# We will be terminating the process
		echo "Stopping the service ${name}.${type}.${domain}"
		pid2=`ps -ef | grep "\-R" | grep "${name}" | grep "${type}" | nawk '{ print $2 }'`
		if [ -n "${pid2}" ]; then
			kill $pid2 > /dev/null 2>&1
		fi
		#
		# Remove the service entry from the file that keep track
		# of currently running services
		txt=`grep $AIWEBSERVER $TMP_FILE | cut -f2 -d'='`
		# Stop the webserver correspond to this service
		port=`echo $txt | cut -f2 -d':'`
		if [ $port -ne 0 ]; then
			stop_ai_webserver $port
		fi
		ret=0
	else
		ret=1
	fi
	kill $pid > /dev/null 2>&1
	rm -f $TMP_FILE
	return $ret
}

#
# Populate the data directory for the AI webserver to run
#
# Arguments:
#	$1 - Setup the document root for the webserver associated with
#	     the service.
#
setup_docroot()
{
	target=$1

	mkdir -p $target
	current_dir=`pwd`
	cd ${AI_SETUP_WS}
	find . -depth -print | cpio -pdmu ${target} >/dev/null 2>&1
	cd $current_dir

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
	txt=$1
	# Extract the port from txt record
	port=`echo $txt | grep $AIWEBSERVER | cut -f2 -d'=' | cut -f2 -d':'`

	#
	# Get the port and start the webserver using the data directory
	# <DOCROOT>/<port>
	docroot=$DOCROOT/$port
	log=$docroot/webserver.log

	setup_docroot $docroot

	# Start the webserver
	$AIWEBSERVER_PROGRAM -p $port $docroot > $log 2>&1 &
	if [ $? -eq 0 ]; then
		ret=0
	else
		ret=1
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

	pid=`ps -ef | grep "$AIWEBSERVER_PROGRAM" | grep "$port" |  nawk '{ print $2 }'`
	if [ $? -ne 0 ]; then
		kill $pid > /dev/null 2>&1
	fi
}

#
# MAIN
# This is an internal function
# So we expect only limited use

if [ $# -lt 3 ]; then
	echo "Internal function to manage DNS services doesn't have enough data"
	exit 1
fi

state=`$SVCS -H -o STATE network/dns/multicast:default`
if [ "$state" != "online" ]; then
	echo "enabling network/dns/multicast service"
	$SVCADM enable network/dns/multicast
	if [ $? != 0 ]; then
		echo "unable to start multicast DNS service, exiting"
		exit 1
	fi
fi

if [ "$1" = "lookup" ]; then
	if [ $# -lt 4 ]; then
		echo "Service Discovery lookup requires four arguments"
		exit 1
	fi

	service_name=$2
	service_type=$3
	service_domain=$4

	lookup_service $service_name $service_type $service_domain
	status=$?
elif [ "$1" = "register" ]; then
	if [ $# -lt 6 ]; then
		echo "Install Service Registration requires six arguments"
		exit 1
	fi

	service_name=$2
	service_type=$3
	service_domain=$4
	service_port=$5
	service_txt=$6

	lookup_service $service_name $service_type $service_domain
	status=$?
	if [ $status -eq 1 ]; then
		# Start the AI webserver using the port from txt record
		start_ai_webserver $service_txt
		status=$?
		if [ $status -eq 0 ]; then
			register_service $service_name $service_type $service_domain $service_port $service_txt
		fi
		status=$?
	fi
elif [ "$1" = "remove" ]; then
	if [ $# -lt 4 ]; then
		echo "Install Service Removal requires four arguments"
		exit 1
	fi

	service_name=$2
	service_type=$3
	service_domain=$4

	remove_service $service_name $service_type $service_domain
	status=$?
elif [ "$1" = "list" ]; then
	service_type=$2
	service_domain=$3

	list_service $service_type $service_domain
	status=$?
else 
	echo " $1 - unsupported DNS service action"
	exit 1
fi
if [ $status -eq 0 ]; then
	exit 0
else
	exit 1
fi

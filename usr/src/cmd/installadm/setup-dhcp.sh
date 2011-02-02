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
#       This script sets up DHCP server, DHCP network, DHCP macro and
#	assign DHCP macro to set of IP addresses.
#	If the DHCP server is remote or the user doesn't have permission
#	to modify DHCP server, then the user is advised to insert the
#	DHCP macro manually.
#	Currently the support for handling remote DHCP server is not implemented
#
# Files potentially changed on server:
# /etc/inet/dhcpsvc.conf - SMF service information for DHCP
# /var/dhcp - DHCP information is kept in files under /var/ai

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

. /usr/lib/installadm/installadm-common

DHTADM="/usr/sbin/dhtadm -g"
PNTADM=/usr/sbin/pntadm
DHCPCONFIG=/usr/sbin/dhcpconfig
NETSTAT=/usr/bin/netstat
DHCP_SVC="svc:/network/dhcp-server:default"
BOOTSRVA="BootSrvA"
BOOTFILE="BootFile"
INCLUDE="Include"

#
# DHCP options should be built and given to dhtadm in a single command
# This function adds the new "name:value" pair to the existing macro
# value passed in as the third argument or constructs a new macro value 
# if there are only two arguments.
#
function update_macro_value
{
	typeset key=$1
	typeset val=$2
	typeset macro_value=""
	if (( $# == 3 )); then
		macro_value=$3
	fi

	if [[ -z "$macro_value" ]]; then
		new_macro_value=":${key}=${val}:"
	else
		# Already there is a : at the end of previous key-value pair
		new_macro_value="${macro_value}${key}=${val}:"
	fi
	print ${new_macro_value}
}

#
# Create a macro with the value
#
function add_macro
{
	typeset name=$1
	typeset value=$2
	# overwrite is true if unset; otherwise, pass in false to append the
	# options to macro (if it already exists)
	typeset overwrite=${3:-true}

	# create a variable in which to store colliding options
	typeset collision_opts=""
	ENTRY=$($DHTADM -P | \
	    $AWK '$1 == name && $2 ~ /Macro/ { print $3 }' name="$name")
	# macro does not already exists
	if [[ -z "$ENTRY" ]]; then
		$DHTADM -A -m $name -d $value
	# macro already exists -- overwrite or modify it
	elif [[ "$ENTRY" != "$value" ]]; then
		# overwrite the macro
		if ${overwrite}; then
			$DHTADM -M -m $name -d $value
		# modify only those options provided
		else
			# The colon in URLs (like for a BootFile due to
			# http[s]://) will catch our field separator
			# so replace BootFiles with a keyword \$boot_file for
			# the moment

			# see if we have a BootFile option
			# this is necessary as colon's embedded in a macro
			# value will cause the for loop below to split on
			# the value instead of on the DHCP option
			typeset boot_file=""
			if [[ "${value/:BootFile=//}" != "$value" ]]; then
				# strip value to BootFile
				boot_file=${value#*:BootFile=\"}
				boot_file=${boot_file%%\":*}

				# substitute out the BootFile value for
				# $boot_file as a token
				value=${value/$boot_file/\$boot_file}
			fi
			oifs="$IFS"
			IFS=":"
			# iteratively change or add the options desired
			for optstr in $value; do
				IFS="$oifs"
				# ignore blank matches (the leading colon
				# in the macro string)
				if [[ -z "$optstr" ]]; then
					continue
				fi

				# replace the $boot_file token with the value
				# in variable $boot_file
				optstr=${optstr/\$boot_file/$boot_file}

				# next, check to see if this option is set and
				# if set differently, then save instructions
				# for the user
				match_macro_and_option $name ${optstr%%=*} \
				    ${optstr#*=}
				if (( $? == 1 )); then
					# add a space and option name to
					# $collision_opts 
					collision_opts+=" ${optstr%%=*}"
					# add a space and option value to
					# $collision_opts 
					collision_opts+=" ${optstr#*=}"
					continue
				fi
				$DHTADM -M -m $name -e $optstr
				IFS=":"
			done
			IFS="$oifs"
			# print colliding options if any were found
			[[ -n $collision_opts ]] && print_macro_opt_collision \
			    $name "$collision_opts"
		fi
	fi
}

#
# Function to determine if a macro option is set to value
# Returns: 0 on exact match
#	   1 on option set but no-match
#	  -1 on option not set
#
function match_macro_and_option
{
	# arguments to be passed in
	typeset macro=$1
	typeset option=$2
	typeset value=$3

	typeset status=-1

	# skip the first two lines of dhtadm -P
	macros=$($DHTADM -P | $TAIL +3)
	oifs="$IFS"
	# set field separator to newline to read each macro in one at a time
	IFS="$(print "")"
	for data in $macros; do
		IFS="$oifs"
		# example lines from dhtadm(1) should be of the form:
		# 192.168.0.0 Macro :Include=hoover:BootFile="http://1.1.1.1:80/wanboot-cgi":
		# macro_foo Macro :Include=fluffy:BootFile=install_test_ai_x86:
		# 01000AE429C1EF Macro :BootSrvA=172.20.25.12:BootFile="01000AE429C1EF":

		# split each line on whitespace so we should have
		# [1]: macro name, [2]: Macro or Symbol, [3]: macro or symbol options
		typeset -a line=( $data )

		# skip to the next line if we do not have a match
		if [[ "${line[0]}" != "$macro" || "${line[1]}" != "Macro" ]]; then
			continue
		fi

		# see if the option and value are present
		if [[ "${line[2]}" == ~(E).*:${option}=${value}:.* ]]; then
			status=0
			break
		# see if the option and some other value are present
		elif [[ "${line[2]}" == ~(E).*:${option}=.*:.* ]]; then
			status=1
			break
		fi
	done
	IFS="$oifs"
	return $status
}

#
# Function to print warnings on macro option collisions
# Arguments: Macro name	- a macro name string
#	     Options	- a space delimited set of option names and values
#			  (e.g. "BootSrvA 128.138.243.136 BootSrvN tlaloc")
#
function print_macro_opt_collision
{
	typeset macro=$1
	# accept a space separated string of option names and values
	typeset options=$2
	print "The macro named $macro is already configured with the" \
	    "following options."
	print "If you are running the Oracle Solaris DHCP Server, use the following"
	print "dhtadm(1) commands to update the DHCP macro, ${macro}:"

	# name is a state variable for holding the option name
	typeset name=""
	for option in $options; do
		# first populate the option name
		if [[ -z $name ]]; then
			name=$option
			continue
		fi
		print "   ($name) : ${option}"
		print "   $DHTADM -M -m ${macro} -e ${name}=${option}"
		name=""
	done
}

#
# Function to show the user how to manually setup the
# service dhcp macro.
#
function print_service_macro_info
{
	typeset caller=$1
	typeset macro=$2
	typeset bootfile=$3
	typeset mvalue=$4

	print "If not already configured, please create a DHCP macro"
	print "named ${macro} with:"
	print "   Boot file      ($BOOTFILE) : ${bootfile}"

	print "If you are running the Oracle Solaris DHCP Server, use the following"
	print "command to add the DHCP macro, ${macro}:"
	print "   $DHTADM -A -m ${macro} -d ${mvalue}"
	print ""
	print "Note: Be sure to assign client IP address(es) if needed"
	print "(e.g., if running the Oracle Solaris DHCP Server, run pntadm(1M))."

}
#
# Function to show the user how to manually setup the
# network dhcp macro.
#
function print_network_macro_info
{
	typeset caller=$1
	typeset macro=$2
	typeset svr_ipaddr=$3
	typeset bootfile=$4
	typeset mvalue=$5
	typeset sparc=$6

	print "If not already configured, please create a DHCP macro"
	print "named ${macro} with:"
	# only SPARC needs a network wide BootFile (URL to wanboot)
	if ${sparc}; then
		print "   Boot file      ($BOOTFILE) : ${bootfile}"
	# only X86 needs a network wide BootSrvA (IP to tftp server)
	else
		print "   Boot server IP ($BOOTSRVA) : ${svr_ipaddr}"
	fi

	print "If you are running the Oracle Solaris DHCP Server, use the following"
	print "command to add the DHCP macro, ${macro}:"
	print "   $DHTADM -A -m ${macro} -d ${mvalue}"
	print ""
	print "Note: Be sure to assign client IP address(es) if needed"
	print "(e.g., if running the Oracle Solaris DHCP Server, run pntadm(1M))."

}

#
# Set up the network dhcp macro
#    X86:   Uses BootSrvA
#    SPARC: Uses BootFile to store the URL to wanboot-cgi
#
function setup_network_macro
{
	typeset caller=$1
	typeset name=$2
	typeset svr_ipaddr=$3
	typeset bootfile=$4
	typeset sparc=$5

	server_name=$(uname -n)

	# see if DHCP is configured
	if [[ "$($SVCS -Ho STATE $DHCP_SVC 2>/dev/null)" == "online" ]]; then
		$DHTADM -P >/dev/null 2>&1
		dhtstatus=$?
	else
		dhtstatus=1
	fi

	# Construct the value of the macro that will either be passed to
	# add_macro or will be printed out for the user
	#
	mvalue=""
	if (( dhtstatus == 0 )); then
		mvalue=$(update_macro_value ${INCLUDE} ${server_name})
	fi

	if ${sparc}; then
		if (( dhtstatus == 0 )); then
			# If we are adding the macro, bootfile is url and
			# contains an embedded colon. Enclose bootfile in
			# quotes so that the colon doesn't terminate the
			# macro string.
			#
			bootfile="\"${bootfile}\""
		else
			# If the macro is going to be printed for the user
			# to enter on the command line, use escaped version
			# of quoted string (backslash gets the quote past
			# the shell).
			#
			bootfile="\\\"${bootfile}\\\""
		fi
		# set Bootfile option
		mvalue=$(update_macro_value "${BOOTFILE}" "${bootfile}" \
		   "${mvalue}")
	else
		# set BootSrvA option
		mvalue=$(update_macro_value "${BOOTSRVA}" "${svr_ipaddr}" \
		    "${mvalue}")
	fi

	if (( dhtstatus != 0 )); then
		# Tell user how to setup dhcp macro
		#
		print "\nDetected that DHCP is not set up on this server."
		print_network_macro_info ${caller} ${name} ${svr_ipaddr} \
		    ${bootfile} ${mvalue} ${sparc}
		return 1
	else
		add_macro $name $mvalue false
	fi
	return 0
}


#
# Set up the service specific dhcp macro
#    X86: Uses BootFile for file to tftp download (file name only) which is
#         service dependent
#    SPARC: Does not need a service macro -- simply return success
#
function setup_service_macro
{
	typeset caller=$1
	typeset name=$2
	typeset bootfile=$3

	server_name=$(uname -n)

	# see if DHCP is configured
	if [[ "$($SVCS -Ho STATE $DHCP_SVC 2>/dev/null)" == "online" ]]; then
		$DHTADM -P >/dev/null 2>&1
		dhtstatus=$?
	else
		dhtstatus=1
	fi

	# Construct the value of the macro that will either be passed to
	# add_macro or will be printed out for the user
	#
	mvalue=""
	if (( dhtstatus == 0 )); then
		mvalue=$(update_macro_value ${INCLUDE} ${server_name})
	fi
	# set Bootfile option
	mvalue=$(update_macro_value ${BOOTFILE} ${bootfile} ${mvalue})

	if (( dhtstatus != 0 )); then
		# Tell user how to setup dhcp macro
		#
		print "\nDetected that DHCP is not set up on this server."
		print_service_macro_info ${caller} ${name} ${bootfile} \
		    ${mvalue}
		return 1
	else
		add_macro $name $mvalue
	fi
	return 0
}

#
# create_dhcp_server
# Purpose:
# 	Create the DHCP server if it doesn't exist
# 	Add the network corresponding the ip addresses to be added
#
# Parameters:
#	$1 - starting address of dhcp client ip address to
#	     set up on the dhcp server.
#
# Return:
#	0 - Success
#	1 - Failure
#
function create_dhcp_server
{
	typeset ip_start=$1

	# Figure out which network the given starting dhcp client
	# ip address belongs to.   
	#
	net=$(strip_ip_address $(find_network $ip_start))

	if [[ -z "$net" ]] ; then
		print "Failed to find network for $ip_start"
		return 1
	fi

	# Create the DHCP table if DHCP is not set-up
	$DHTADM -P >/dev/null 2>&1
	if (( $? != 0 )); then
		$MKDIR -p /var/dhcp >/dev/null 2>&1
		print "Creating DHCP Server"

		$DHCPCONFIG -D -r SUNWfiles -p /var/dhcp
		if (( $? != 0 )); then
			print "Failed to setup DHCP server"
			return 1
		fi
	fi

	# At this point, either a DHCP server previously existed, or
	# one has been successfully created.

	# If the router found is for the network being configured,
	# configure the network in DHCP with that router.  Otherwise
	# don't use it.
	use_router=0

	# Get the router from netstat. There may be more than one default
	# router listed for multiple subnets. Check them against the network
	# we're looking for to see if we can use any of them.
	#
	$NETSTAT -rn | $AWK '/default/ { print $2 }' | \
	    while read router ; do
		router_network=$(strip_ip_address $(find_network $router))
		if [[ -n $router_network && "$router_network" == "$net" ]]; then
			use_router=1
			break;
		fi
	done

	if (( use_router == 1 )); then
		$DHCPCONFIG -N ${net} -t ${router}
	else
		# We couldn't find the correct router for the address in
		# $net so we have no good way to determine the network
		# topology here. The user will have to do any remaining
		# dhcp setup manually.

		print "Unable to determine the proper default router "
		print "or gateway for the $net subnet. The default "
		print "router or gateway for this subnet will need to "
		print "be provided later using the following command:"
		print "   /usr/sbin/dhtadm -M -m $net -e  Router=<address> -g"

		$DHCPCONFIG -N ${net} 
	fi

	# If the network already exists, ignore the error
	ret=$?
	if (( ret == 255 )); then
		return 0
	elif (( ret != 0 )); then
		print "Failed to add network (${net}) to dhcp server"
		return 1
	fi

	return 0
}

#
# Add the given ip addresses to the DHCP table
#
function add_ip_addresses
{
	typeset ip_start=$1
	typeset ip_count=$2

	n1=$(print $ip_start | $CUT -d'.' -f1-3)
	last_octet=$(print $ip_start | $CUT -d'.' -f4)

	# Figure out which network the given starting dhcp client
	# ip address belong to.
	#
	net=$(strip_ip_address $(find_network $ip_start))
	if [[ -z "$net" ]]; then
		print "Failed to find network for $ip_start"
		return 1
	fi

	index=0
	while (( index < ip_count )); do
		next_addr_octet=$(expr $last_octet + $index)
		ip=$(print $n1.$next_addr_octet)
		addr=$($PNTADM -P ${net} | $NAWK '{ print $3 }' \
		    2>/dev/null | $GREP "^${ip}\$")
		if [[ -z "$addr" ]]; then
			if [[ "$ip" != "$addr" ]]; then
				$PNTADM -A ${ip} ${net}
			fi
		fi
		index=$((index + 1))
	done

	return 0
}

#
# Assign the dhcp macro to the IP addresses we have added to the DHCP table
#
function assign_dhcp_macro
{
	typeset macro_name=$1
	typeset ip_start=$2
	typeset ip_count=$3

	n1=$(print $ip_start | $CUT -d'.' -f1-3)
	last_octet=$(print $ip_start | $CUT -d'.' -f4)
 
	# Figure out which network the given starting dhcp client
	# ip address belong to.
	#
	net=$(strip_ip_address $(find_network $ip_start))
	if [[ -z "$net" ]]; then
		print "Failed to find network for $ip_start"
		return 1
	fi

	index=0
	while (( index < ip_count )); do
		next_addr_octet=$(expr $last_octet + $index)
		ip=$(print $n1.$next_addr_octet)
		addr=$($PNTADM -P ${net} | $NAWK '{ print $3 }' \
		    2>/dev/null | $GREP "^${ip}\$")
		if [[ -n "$addr" ]]; then
			if [[ "$ip" == "$addr" ]]; then
				$PNTADM -D ${ip} ${net} # remove the entry
			fi
		fi
		$PNTADM -A ${ip} -m ${macro_name} ${net}
		index=$(expr $index + 1)
	done

	return 0
}

#
# Run setup_network_macro() for necessary networks on server
#
function run_setup_dhcp
{
	typeset caller=$1
	typeset bootfile=$2
	typeset sparc=$3

	# by default we return non-zero until at least one successful
	# setup_network_macro is run
	success=1
	for network in $(valid_networks); do
		# skip blank lines from valid_networks
		if [[ -z $network ]]; then
			continue
		fi
		# get the host IP address for this network
		server_ip=$(get_ip_for_net $network)
		if [[ -z "$server_ip" ]]; then
			print -u2 "Warning: unable to find IP address"\
				  "for network $network."
			continue
		fi

		# change bootfile if necessary to have proper server IP
		net_boot_file=${bootfile//\$serverIP/$server_ip}

		# actually call setup_network_macro for this network
		setup_network_macro $caller $network $server_ip $net_boot_file $sparc
		if (( $? == 0 )); then
			# record if we got at least one successful DHCP run
			# we want to return 0 if we did (ignore failures as
			# long as one worked)
			success=0
		fi
	done
	return $success
}

#
# This is an internal script
# So we expect only limited use

if (( $# < 3 )); then
	print "Internal function to manage DHCP services does not have enough data"
	exit 1
fi

if [[ "$1" == "server" ]]; then
	client_ip_start=$2
	ip_count=$3

	create_dhcp_server $client_ip_start
	status=$?
	if (( status == 0 )); then
		add_ip_addresses $client_ip_start $ip_count
		status=$?
	fi
elif [[ "$1" == "macro" ]]; then
	imgtype=$2	# x86 or sparc
	macro=$3	# macro name
	boot_file=$4	# boot file for TFTP or WAN Boot

	sparc=false # leave $sparc false if we are X86
	if [[ "${imgtype}" == "sparc" ]]; then
		sparc=true
	fi

	# setup network macros
	run_setup_dhcp $1 $boot_file $sparc
	status=$?
	if ! ${sparc}; then
		# only X86 needs a service macro
		setup_service_macro $1 $macro $boot_file
	fi
	# sum the statuses (an error >=2 indicates a failure in setup_service,
	# an odd error indicates a failure in setting up network macros)
	status=$((status+2*$?))
elif [[ "$1" == "assign" ]]; then
	client_ip_start=$2
	ip_count=$3
	macro=$4

	assign_dhcp_macro $macro $client_ip_start $ip_count
	status=$?
elif [[ "$1" == "client" ]]; then
	imgtype=$2	# x86 or sparc
	macro=$3	# macro name
	boot_file=$4	# boot file to use
	
	sparc=false # leave sparc false if we are X86
	if [[ "$imgtype" == "sparc" ]]; then
		sparc="true"
	fi

	# no need to setup network macros -- they already should be setup
	# simply create a client macro if running for an X86
	if ! ${sparc}; then
		# only X86 needs a service macro
		setup_service_macro $1 $macro $boot_file
	fi
	status=$?
else 
	print " $1 - unsupported DHCP service action"
	exit 1
fi

exit $status

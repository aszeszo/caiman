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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#
# Description:
#	This script checks for basic network setup necessary for an AI server
#	to function.  Specifically it does the following:
#
#	- Check that svc:/network/physical services are set up properly:
#	  ----------------------------------------------------------------------
#	  | NWAM  /  default    | not online         | online                  |
#	  ----------------------------------------------------------------------
#	  | online              | WARNING (allowed)  | ERROR: too many net svcs|
#	  ----------------------------------------------------------------------
#	  | !online & !disabled | ERROR: no net svcs | ERROR: too many net svcs|
#	  ----------------------------------------------------------------------
#	  | disabled            | ERROR: no net svcs | OK                      |
#	  ----------------------------------------------------------------------
#
#	 Check that svc:/network/dns/multicast:default is online
#
#	- Get IP address via getent host hostname
#	- Get IP address via ifconfig
#	- IP addresses have to match and not be a loopback address
#
# Additionally, if the server is being set up to be a dhcp server:
#
#	- Get netmask for IP address using getent netmasks IP
#	- Get netmask for IP address via ifconfig
#	- Netmasks have to match
#
#	- Verify /etc/resolv.conf exists
#	  and has at least one uncommented nameserver entry.
#	  (Prints a warning and continues if either of these tests fail.)
#
#	- Verify that the client being setup is on a configured network path.
#
# If anything is found to be incorrect, the script displays a message and
# returns 1.
# If all is found to be OK, the script returns 0 silently.

. /usr/lib/installadm/installadm-common

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

# Commands
GETENT="/usr/bin/getent"

# Files
RESOLV_CONF_FILE="/etc/resolv.conf"

LOOPBACK_IP_A=127
NAMESERVER_STRING="^nameserver"

MDNS_SVC="svc:/network/dns/multicast:default"
NWAM_SVC="svc:/network/physical:nwam"
NDEF_SVC="svc:/network/physical:default"

. /usr/lib/installadm/installadm-common

#
# Print to stderr
#
print_err() {
	echo "$@" >&2
}

#
# Perform the checks done for all servers, whether designated as dhcp or not.
# See module header for description of the checks.
#
# Args:
#   $1 - valid: Global: used to flag a failing check.  Assumed preinitialized
#		to "True", but this function may set it to "False"
#   $2 - ipaddr: Global: This function will initialize to an IP address which
#		correlates to the system's hostname.
#   $3 - netmask: Global: This function will initialize to the netmask which
#		correlates to the returned ipaddr.
#
# Returns:
#   valid: global is modified.
#   ipaddr: global is modified.
#   netmask: global is modified.
#	
do_all_service_create_check()
{
	# These are actually globals modified by this routine.
	# Declared here to document them.
	valid=$1	# Assumed to be "True" upon entry.
	ipaddr=$2
	netmask=$3

	# Get hostname.
	# "unknown" is valid if that's how this system knows itself.
	THISHOST=`$HOSTNAME`
	if [ "X$THISHOST" == "X" ] ; then
		print_err "Hostname is not set. " \
		    "It is needed to get IP information."
		valid="False"
	else
		# Check network/physical SMF service configuration.
		NWAM_STATE=`$SVCS -H -o STATE $NWAM_SVC`
		NDEF_STATE=`$SVCS -H -o STATE $NDEF_SVC`
		if [ "$NDEF_STATE" != "online" ] ; then
			if [ "$NWAM_STATE" == "online" ] ; then
				print_err "Warning: NWAM is enabled. " \
				    "Please be sure that the IP address for" \
				    "$THISHOST is static."
			else
				print_err "No networking SMF service is online."
				valid="False"
			fi
		elif [ "$NWAM_STATE" != "disabled" ] ; then
			print_err "More than one SMF network/physical service" \
			    "is enabled."
			valid="False"
		fi

		# Ensure svc:/network/dns/multicast:default is enabled
		MDNS_STATE=`$SVCS -H -o STATE $MDNS_SVC`
		if [ "$MDNS_STATE" != "online" ]; then
			print_err "Service $MDNS_SVC is disabled."
			print_err "Please enable the service via:" \
			    "svcadm enable $MDNS_SVC."
			valid="False"
		fi

		# Get IP address
		host_ip=$($GETENT hosts $THISHOST)
		GETENT_IP=$(get_ip_for_net ${host_ip%%[^0-9.]*})
		if [ $? -ne 0 -o "X$GETENT_IP" == "X" ] ; then
			print_err "Could not find the IP address for" \
			    "host $THISHOST"
			valid="False"
		fi
	fi

	# Extract the first number, and compare to loopback value.
	if [ "$valid" == "True" ] ; then
		GETENT_IP_A=`echo $GETENT_IP | $NAWK -F "." '{ print $1 }'`
		if [ "$GETENT_IP_A" == "$LOOPBACK_IP_A" ] ; then
			print_err "Server hostname $THISHOST resolved as a" \
			    "loopback IP address."
			valid="False"
		fi
	fi

	if [ "$valid" == "True" ] ; then
		# Validate IP address and get its ifconfig netmask.
		netmask=`get_ip_netmask $GETENT_IP`
		if [ "X$netmask" == "X" ] ; then
			print_err "The IP address $GETENT_IP is not assigned" \
			    "to any of the system's network interfaces."
			ipaddr=
			valid="False"
		else
			ipaddr=$GETENT_IP
		fi
	fi

	# If valid = "True" at this point, the system has a non-loopback IP
	# address assigned to its hostname, and the IP address shows up via
	# ifconfig as well.

	return
}

#
# Check that the SMF all_services property group is properly configured
#	* Check that property group all_services exists
#	* Check that property all_services/networks exists
#	* Check that property all_services/exclude_networks exists
#	* Check that all networks specified by all_services/networks match at
#	  least one network served by an actual interface
#
# Args:
#   $1 - valid: Global: used to flag a failing check.  This function may set it
#		to "False".
#
# Post-condition:
#   valid: global is modified.
do_all_services_check()
{
	# This is actually a global modified by this routine.
	# Declared here to document it.
	valid=$1

	# Check svc:/system/install/server:default property
	# group all_services exists
	if ! $SVCPROP -cp all_services $SMF_INST_SERVER \
	    > /dev/null 2>&1; then
		print_err "Please add the property group" \
		    "all_services:\n" \
		    "'svccfg -s $SMF_INST_SERVER addpg" \
		    "all_services application'."
		valid="False"
	fi

	# Check svc:/system/install/server:default property
	# exclude_networks exists and is only set to true or false
	exclude=$($SVCPROP -cp all_services/exclude_networks \
	    $SMF_INST_SERVER 2>&1)
	if (( $? != 0 )); then
		print_err "Please add the property" \
		    "all_services/exclude_networks:\n" \
		    "'svccfg -s $SMF_INST_SERVER setprop" \
		    "all_services/exclude_networks = "\
		    "boolean: false'."
		valid="False"
	elif [[ "$exclude" != "true" && "$exclude" != "false" ]]; then
		print_err "Please set the property" \
		    "all_services/exclude_networks" \
		    "to either 'true' or 'false'."
		valid="False"
	fi

	# Check svc:/system/install/server:default property
	# networks exists
	if ! $SVCPROP -cp all_services/networks \
	    $SMF_INST_SERVER >/dev/null 2>&1; then
		print_err "Please add the property" \
		    "all_services/networks:\n" \
		    "'svccfg -s $SMF_INST_SERVER setprop" \
		    "all_services/networks = "\
		    "net_address_v4: 0.0.0.0/0'."
		valid="False"
	fi

	# if we have failed any of the basic SMF tests; do not look further yet
	[[ "$valid" == "False" ]] && return

	# get interfaces which the server provides
	typeset nets=""

	for net in $(get_system_networks); do
		# strip the network bits
		nets="${nets}${net%/*}\n"
	done

	# get the SMF networks to be included or excluded
	typeset smf_nets=$(get_SMF_masked_networks)

	# try to apply the SMF mask to the system's networks and record any
	# failures (ignore the network output from file descriptor 3)
	typeset bad_masks=$(apply_mask_to_networks \
	    $(print "${nets}\n${smf_nets}") 4>&1 3>/dev/null)

	# see if apply_mask_to_networks() failed
	if [[ -n "$bad_masks" ]]; then
		valid="False"
		for mask in $bad_masks; do
			print_err "The SMF all_services/networks property" \
			    "($mask) does not match a network interface on" \
			    "this server."
		done
	fi
}

#
# Check that ifconfig returns same netmask as getent does, for given IP address
# 
# Args:
#   $1 - valid: Global: used to flag a failing check.  This function may set it
#		to "False".
#   $2 - ipaddr: Local: IP address to check.
#   $3 - ifconfig_netmask: Local: Netmask from ifconfig which correlates
#		to ipaddr.
#
# Post-condition:
#   valid: global is modified.
# 
do_netmask_check()
{
	# These are actually globals modified by this routine.
	# Declared here to document them.
	valid=$1

	# Local variables
	typeset nc_ipaddr=$2
	typeset nc_ifconfig_nm=$3
	typeset nc_decval=
	typeset hex_getent_nm=

	# Get netmask for IP address using getent
	getent_nm=`$GETENT netmasks $nc_ipaddr | $NAWK '{ print $2 }'`
	if [ $? -ne 0 ] ; then
		print_err "The netmask for network $nc_ipaddr is not" \
		    "configured in the netmasks(4) table."
		valid="False"
	else

		nc_decval=`echo $getent_nm | $NAWK -F "." '{ print $1 }'`
		eval nc_ip_A=`printf %2.2x nc_decval`
		nc_decval=`echo $getent_nm | $NAWK -F "." '{ print $2 }'`
		eval nc_ip_B=`printf %2.2x nc_decval`
		nc_decval=`echo $getent_nm | $NAWK -F "." '{ print $3 }'`
		eval nc_ip_C=`printf %2.2x nc_decval`
		nc_decval=`echo $getent_nm | $NAWK -F "." '{ print $4 }'`
		eval nc_ip_D=`printf %2.2x nc_decval`

		hex_getent_nm="${nc_ip_A}${nc_ip_B}${nc_ip_C}${nc_ip_D}"

		if [ "$nc_ifconfig_nm" != "$hex_getent_nm" ] ; then
			print_err "The netmask obtained from netmasks(4)" \
			    "for network $nc_ipaddr does not equal"
			print_err "that network interface's configured netmask."
			valid="False"
		fi
	fi
}

#
# Perform the extra checks done for dhcp servers.
# See module header for description of the checks.
#
# Args:
#   $1 - valid: Global: used to flag a failing check.  This function may set it
#		to "False".
#   $2 - ipaddr: Local: System's IP address
#   $3 - netmask: Local: Netmask which correlates to ipaddr.
#   $4 - client_ipaddr: Local: IP address given to the client being setup.
#
# Returns:
#   valid: global is modified.
# 
do_dhcp_service_create_check()
{
	# These are actually globals modified by this routine.
	# Declared here to document them.
	valid=$1

	# Local variables.
	typeset ds_ifc_ipaddr=$2
	typeset ds_ifc_netmask=$3
	typeset ds_client_ipaddr=$4

	# Check hostname-bound network's netmask from ifconfig vs getent.
	do_netmask_check $valid $ds_ifc_ipaddr  $ds_ifc_netmask

	# Check that the client being setup is on a configured network path,
	# and get its network's netmask from ifconfig.
	ds_client_ifc_ipaddr=`find_network_baseIP $ds_client_ipaddr`
	ds_client_ifc_netmask=`find_network_nmask $ds_client_ipaddr`
	if [ "X${ds_client_ifc_netmask}" == "X" -o \
	    "X${ds_client_ifc_ipaddr}" == "X" ] ; then
		print_err "No configured network path to the client" \
		    "at $ds_client_ipaddr exists."
		valid="False"
	else
		# Check client network's netmask from ifconfig vs getent.
		do_netmask_check $valid $ds_client_ifc_ipaddr \
		    $ds_client_ifc_netmask
	fi


	# Verify /etc/resolv.conf exists and has at least one nameserver entry.
	# Docs show that a ; or a # in column 1 is a comment.
	# Other code tests that "nameserver" starts in column 1.  We'll do that.
	if [ ! -r $RESOLV_CONF_FILE ] ; then
		print_err "Warning: $RESOLV_CONF_FILE is missing or" \
		    "inaccessible."
	else
		$GREP $NAMESERVER_STRING $RESOLV_CONF_FILE 2>&1 >>/dev/null
		if [ $? -ne 0 ] ; then
			print_err "Warning: $RESOLV_CONF_FILE is missing" \
			    "nameserver entries"
		fi
	fi
}

#
# Main
#

valid="True"
ipaddr=
netmask=
client_ipaddr=

if [ $# -gt 1 ] ; then
	print_err "Usage: $0: [ <client_ip_address> ]"
	print_err "  where dhcp-server checks are made when" \
	    "<client_ip_address> is provided"
	exit 1

elif [ $# -eq 1 ] ; then	# DHCP server check.
	client_ipaddr=$1
fi

# Do checks common to all servers.
# Returns with $ipaddr and $netmask set, and $valid updated.
do_all_service_create_check $valid $ipaddr $netmask

# Do checks for all_services SMF property group
do_all_services_check $valid

# If hostname problem above, ipaddr won't be set.  Don't continue.
# Also, installadm specifies dhcp server checks by setting client_ipaddr
if [ "X$ipaddr" != "X" -a "X$client_ipaddr" != "X" ] ; then
	# Do dhcp server specific checks.  Updates $valid
	do_dhcp_service_create_check $valid $ipaddr $netmask \
	    $client_ipaddr
fi

if [ "$valid" != "True" ] ; then
	print_err "Automated Installations will not work with the" \
	    "current server network setup."
	exit 1
fi
exit 0

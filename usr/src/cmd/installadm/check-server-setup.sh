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
#	- Warn if the svc:/network/dns/multicast:default is not online
#
# If anything is found to be incorrect, the script displays a message and
# returns 1.
# If all is found to be OK, the script returns 0 silently.

. /usr/lib/installadm/installadm-common

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

# Commands
GETENT="/usr/bin/getent"

MDNS_SVC="svc:/network/dns/multicast:default"
NWAM_SVC="svc:/network/physical:nwam"
NDEF_SVC="svc:/network/physical:default"

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
	THISHOST=$($HOSTNAME)
	if [ "X$THISHOST" == "X" ] ; then
		print_err "Hostname is not set. " \
		    "It is needed to get IP information."
		valid="False"
	else
		# Check network/physical SMF service configuration.
		NWAM_STATE=$($SVCS -H -o STATE $NWAM_SVC)
		NDEF_STATE=$($SVCS -H -o STATE $NDEF_SVC)
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

		# Check if svc:/network/dns/multicast:default is online
		MDNS_STATE=$($SVCS -H -o STATE $MDNS_SVC)
		if [ "$MDNS_STATE" != "online" ]; then
			print_err "Warning: Service $MDNS_SVC is not online."
			print_err "   Installation services will not be" \
			    "advertised via multicast DNS."
		fi
	fi
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
		    "all_services/exclude_networks = " \
		    "boolean: false'."
		valid="False"
	elif [[ "$exclude" != "true" && "$exclude" != "false" ]]; then
		print_err "Please set the property" \
		    "all_services/exclude_networks" \
		    "to either 'true' or 'false'."
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

if [ "$valid" != "True" ] ; then
	print_err "Automated Installations will not work with the" \
	    "current server network setup."
	exit 1
fi
exit 0

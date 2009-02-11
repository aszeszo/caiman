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
#       This script sets up DHCP server, DHCP network, DHCP macro and
#	assign DHCP macro to set of IP addresses.
#	If the DHCP server is remote or the user doesn't have permission
#	top modify DHCP server, then the user is advised to insert the
#	DHCP macro manually.
#	Currently the support for handling remote DHCP server is not implemented
#
# Files potentially changed on server:
# /etc/inet/dhcpsvc.conf - SMF service information for DHCP
# /var/dhcp - DHCP information is kept in files under /var/ai

DHTADM="/usr/sbin/dhtadm -g"
PNTADM=/usr/sbin/pntadm
DHCPCONFIG=/usr/sbin/dhcpconfig
TMP_DHCP=/tmp/installadm.dhtadm-P.$$
BOOTSRVA="BootSrvA"
BOOTFILE="BootFile"
ROOTPATH="Rootpath"
INCLUDE="Include"
GRUBMENU="GrubMenu"
macro_value=""


#
# DHCP options should be built and given to dhtadm in a single command
# This function adds the new "name:value" pair to the existing option
#
update_macro_value()
{
	key=$1
	val=$2

	if [ X"${macro_value}" = X ]; then
		macro_value=":${key}=${val}:"
	else
		# Already there is a : at the end of previous key-value pair
		macro_value="${macro_value}${key}=${val}:"
	fi
}

#
# Create a macro with the value
#
add_macro()
{
	name=$1
	value=$2

	$DHTADM -P > ${TMP_DHCP} 2>&1
	ENTRY=`cat ${TMP_DHCP} | awk '$1 == name && $2 ~ /Macro/ { print $3 }' name="$name"`
	if [ -z "${ENTRY}" ]; then
		$DHTADM -A -m $name -d ${value}
	elif [ "${ENTRY}" != "${value}" ]; then
		$DHTADM -M -m $name -d ${value}
	fi
}

print_dhcp_macro_info()
{
	macro=$1
	svr_ipaddr=$2
	bootfile=$3
	rootpath=$4
	sparc=$5
	menu_lst_file="menu.lst.${bootfile}"
	
	echo "  Please create a DHCP macro named ${macro} with:"
	echo "  Boot server IP (BootSrvA) : ${svr_ipaddr}"
	echo "  Boot file      (BootFile) : ${bootfile}"
	if [  "$sparc" ]; then
		echo "  Root path      (Rootpath) : ${rootpath}"
	else
		echo "  GRUB Menu      (GrubMenu) : ${menu_lst_file}"
		echo ""
		echo "  Additionally, if the site specific symbol GrubMenu"
		echo "  is not present, please add it as follows:"
		echo "  $DHTADM -A -s GrubMenu -d Site,150,ASCII,1,0"
		echo ""
	fi
}

#
# Set up the dhcp macro
#    Both sparc/x86 use boot server address and boot file, but contents of
#    boot file differ between sparc/x86. In addition, sparc uses the dhcp
#    macro symbol, Rootpath,  and x86 uses dhcp macro symbol, GrubMenu,
#    which are defined by ROOTPATH and GRUBMENU, respectively.
# 
setup_dhcp_macro()
{
	caller=$1
	name=$2
	svr_ipaddr=$3
	bootfile=$4
	rootpath=$5
	sparc=$6

	server_name=`uname -n`

	bootfilesave="${bootfile}"
	rootpathsave="${rootpath}"
	if [ "$sparc" ]; then
		# For sparc, bootfile and rootpath are urls, and contain
		# an embedded colon. Enclose bootpath and rootpath
		# in quotes so that the colon doesn't terminate the
		# macro string.
		bootfile="\"${bootfile}\""
		rootpath="\"${rootpath}\""
	else
		# set menu.lst for x86
		menu_lst_file="menu.lst.${bootfile}"
	fi


	$DHTADM -P > ${TMP_DHCP} 2>&1
	if [ $? -ne 0 ]; then
		#
		# Do not print dhcp macro info if called from create-client
		# because create-client prints it
		#
		if [ "${caller}" = "client" ]; then
			return 1
		fi
		echo "Could not retrieve DHCP information from dhcp server"
		print_dhcp_macro_info $name $svr_ipaddr $bootfilesave $rootpathsave $sparc
		return 1
	fi
	update_macro_value ${INCLUDE} ${server_name}
	update_macro_value ${BOOTSRVA} ${svr_ipaddr}
	update_macro_value ${BOOTFILE} ${bootfile}
	if [ "$sparc" ]; then
		update_macro_value ${ROOTPATH} ${rootpath}
	else
		update_macro_value ${GRUBMENU} ${menu_lst_file}
	fi
	add_macro $name $macro_value
}

#
# Create the DHCP server if it doesn't exist
# Add the network corresponding the ip addresses to be added
# Finding the network from the ip address need to be improved
# It work only for class c addresses
#
create_dhcp_server()
{
	ip_start=$1

	n1=`echo $ip_start | cut -d'.' -f1-3`
	net=$n1.0

	# Create the DHCP table if it the DHCP is not enabled
	$DHTADM -P > /dev/null 2>&1
	if [ $? -ne 0 ]; then
		mkdir -p /var/dhcp
		echo "Creating DHCP Server"
		$DHCPCONFIG -D -r SUNWfiles -p /var/dhcp
		# Add the site specific option 150 to specify a 
		# menu.lst other than default one based on
		# MAC adddress
		$DHTADM -A -s GrubMenu -d Site,150,ASCII,1,0
	fi

	# Only create network if the DHCP server is created
	if [ $? -eq 0 ]; then
		#
		# Get the router from netstat
		#
		router=`netstat -rn | awk '/default/ { print $2 }'`
		if [ X${router} != X ]; then
			$DHCPCONFIG -N ${net} -t ${router}
		else
			echo "Cannot get the default router"
			echo "Please check whether default route is configured"
			$DHCPCONFIG -N ${net}
		fi
		# If the network already exists, ignore the error
		if [ $? -eq 255 ]; then
			return 0
		fi
	fi
	return 0
}

#
# Add the given ip addresses to the DHCP table
#
add_ip_addresses()
{
	ip_start=$1
	ip_count=$2

	n1=`echo $ip_start | cut -d'.' -f1-3`
	net=`echo $n1.0`
	last_octet=`echo $ip_start | cut -d'.' -f4`
	index=0
	while [ $index -lt $ip_count ]; do
		next_addr_octet=`expr $last_octet + $index`
		ip=`echo $n1.$next_addr_octet`
		addr=`$PNTADM -P ${net} | /usr/bin/nawk '{ print $3 }' 2> /dev/null | /usr/bin/grep "^${ip}\$"`
		if [ X"${addr}" != X ]; then
			if [ "$ip" != "$addr" ]; then
				$PNTADM -A ${ip} ${net}
			fi
		fi
		index=`expr $index + 1`
	done
}

#
# Assign the dhcp macro to the IP addresses we have added to the DHCP table
#
assign_dhcp_macro()
{
	macro_name=$1
	ip_start=$2
	ip_count=$3

	n1=`echo $ip_start | cut -d'.' -f1-3`
	net=`echo $n1.0`
	last_octet=`echo $ip_start | cut -d'.' -f4`
	index=0
	while [ $index -lt $ip_count ]; do
		next_addr_octet=`expr $last_octet + $index`
		ip=`echo $n1.$next_addr_octet`
		addr=`$PNTADM -P ${net} | /usr/bin/nawk '{ print $3 }' 2> /dev/null | /usr/bin/grep "^${ip}\$"`
		if [ X"${addr}" != X ]; then
			if [ "$ip" = "$addr" ]; then
				$PNTADM -D ${ip} ${net}
			fi
		fi
		$PNTADM -A ${ip} -m ${macro_name} ${net}
		index=`expr $index + 1`
	done
}
		
#
# This is an internal function
# So we expect only limited use

if [ $# -lt 3 ]; then
	echo "Internal function to manage DHCP services doesn't have enough data"
	exit 1
fi

if [ "$1" = "server" ]; then
	client_ip_start=$2
	ip_count=$3

	create_dhcp_server $client_ip_start
	status=$?
	if [ $status -eq 0 ]; then
		add_ip_addresses $client_ip_start $ip_count	
		status=$?
	fi
elif [ "$1" = "macro" ]; then
	imgtype=$2	# x86 or sparc
	srv_ip=$3
	macro=$4
	boot_file=$5
	rpath=$6

	sparc=
	if [ "${imgtype}" = "sparc" ]; then
		sparc="true"
	fi
	setup_dhcp_macro $1 $macro $srv_ip $boot_file $rpath $sparc
	status=$?
elif [ "$1" = "assign" ]; then
	client_ip_start=$2
	ip_count=$3
	macro=$4

	assign_dhcp_macro $macro $client_ip_start $ip_count	
	status=$?
elif [ "$1" = "client" ]; then
	imgtype=$2	# x86 or sparc
	srv_ip=$3
	macro=$4
	boot_file=$5
	rpath=$6
	client_ip=$7
	
	sparc=
	if [ "${imgtype}" = "sparc" ]; then
		sparc="true"
	fi
	setup_dhcp_macro $1 $macro $srv_ip $boot_file $rpath $sparc
	status=$?
	if [ $status -eq 0 -a "X${client_ip}" != "X" ]; then
		assign_dhcp_macro $macro $client_ip 1	
		status=$?
	fi
else 
	echo " $1 - unsupported DHCP service action"
	exit 1
fi

/bin/rm -f $TMP_DHCP

if [ $status -eq 0 ]; then
	exit 0
else
	exit 1
fi

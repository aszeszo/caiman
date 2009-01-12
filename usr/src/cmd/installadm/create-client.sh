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

#
# Description:
#       Sets up client data specific for a particular client, in the
#       non-default case. In general, client setup is not required and all
#       clients will boot the default service as tagged in create-service.
#       If it is desired to have a client boot and utilize specific services
#       and manifests, this command is used to do so. The following
#       functionality is provided:
#
#       1. Allow for specification of installation service for client to use.
#          This will bypass the service discovery mechanism and use a specific
#          service. The administrator can set up manifiests with that service
#          to serve the clients.
#
#       2. For x86, creates a bootfile and /tftpboot entries. The bootfile
#	   name is derived from the MAC address.
#	   For sparc, setup wanboot files and create wanboot.conf
#
#       3. Setup the dhcp macro with the server and bootfile (and rootpath
#	   for sparc) information if it doesn't exist.
#
# Files potentially changed on server:
# /tftpboot/ - directory created/populated with pxegrub files and links.
# /etc/inetd.conf - to turn on tftpboot daemon
# /etc/netboot/<network number>/<MACID>/wanboot.conf

# make sure path is ok
PATH=/usr/bin:/usr/sbin:/sbin:${PATH}; export PATH

# tr may fail in some locales. Hence set the env LANG=C and LC_ALL=C
TR='env LC_ALL=C LANG=C /bin/tr'

# Constants
#
SIGHUP=1
SIGINT=2
SIGQUIT=3
SIGTERM=15

# Variables 
#
DHCP_CLIENT_ID=""
PROTOCOL="HTTP"
DIRNAME="/usr/lib/installadm"
INSTALL_TYPE="_OSInstall._tcp"
Bootdir="/tftpboot"

# Settings for client specific properties, to be passed via grub menu
#
BARGLIST=""

# import common functions
#
. ${DIRNAME}/installadm-common


# usage
#
# Purpose : Print the usage message in the event the user
#           has input illegal command line parameters and
#           then exit
#
# Arguments : 
#   none
#
usage () {
	echo "Usage: $0 [-P <protocol>]"
	echo "\t\t[-b \"<property>=<value>\"]"
        echo "\t\t-e <macaddr> -t <imagepath> -n <svcname>"
	
	exit 1
}

abort()
{
	echo "${myname}: Aborted"
	exit 1
}


#
# MAIN - Program
#

myname=`basename $0`
ID=`id`
USER=`expr "${ID}" : 'uid=\([^(]*\).*'`

unset BOOT_FILE IMAGE_PATH IMAGE_SERVER MAC_ADDR
unset SERVER SERVICE_NAME

trap abort $SIGHUP $SIGINT $SIGQUIT $SIGTERM

# Verify user ID before proceeding - must be root
#
if [ "${USER}" != "0" ]; then
	echo "You must be root to run $0"
	exit 1
fi


# Set the umask.
#
umask 022

# Get SERVER info
#
SERVER_IP=`get_server_ip`

# Parse the command line options.
#
while [ "$1"x != "x" ]; do
    case $1 in
    -e)	MAC_ADDR="$2";
        if [ "X$MAC_ADDR" = "X" ]; then
            usage ;
        fi

	fnum=`echo "${MAC_ADDR}" | awk 'BEGIN { FS = ":" } { print NF } ' `
	if [ $fnum != 6 ]; then
		echo "${myname}: malformed MAC address: $MAC_ADDR"
		exit 1
	fi

        MAC_ADDR=`expr $MAC_ADDR : '\([0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\)'`

        if [ ! "${MAC_ADDR}" ] ; then
                echo "${myname}: malformed MAC address:  $2"
                exit 1
        fi
        shift 2;;
    -n)	SERVICE_NAME=$2
        if [ ! "$SERVICE_NAME" ]; then
            usage ;
	fi
	shift 2;;

    # Accept value for -t as either <server:/path> or </path>.
    #
    -t)	if [ ! "$2" ]; then
		usage;
	fi
    	IMAGE_SERVER=`expr $2 : '\(.*\):.*'`
	if [ -n "${IMAGE_SERVER}" ]; then
		IMAGE_PATH=`expr $2 : '.*:\(.*\)'`
	else
		# no server provided, just get path
		IMAGE_PATH=$2
		IMAGE_SERVER=${SERVER_IP}
	fi
        if [ ! "$IMAGE_PATH" ]; then
		echo "${myname}: Invalid image pathname"
            usage ;
	fi
	shift 2;;
    -f) BOOT_FILE=$2
	if [ ! "$BOOT_FILE" ] ; then
	    usage ;
	fi
	shift 2;;
    -P) PROTOCOL=$2
	if [ ! "$PROTOCOL" ] ; then
	    usage ;
	fi
	PROTOCOL=`echo ${PROTOCOL} | ${TR} "[a-z]" "[A-Z]"`
	shift 2;;

    # -b option is used to introduce changes in a client,
    # e.g. console=ttya
    #
    -b) BARGLIST="$BARGLIST"$2","
	shift 2;;

    -*)	# -anything else is an unknown argument
        usage ;
        ;;
    *)	# all else is spurious
        usage ;
        ;;
    esac
done

if [ -z "${MAC_ADDR}" -o -z "${IMAGE_PATH}" -o -z "${SERVICE_NAME}" ]; then
	echo "${myname}: Missing one or more required options."
	usage
fi 

if [ "${PROTOCOL}" != "HTTP" ]; then
	echo "${myname}: Valid protocols are HTTP and NFS."
	if [ "${PROTOCOL}" = "NFS" ]; then
		echo "${myname}: NFS protocol is not supported at this time,"
		echo "\tdefaulting to HTTP."
		PROTOCOL="HTTP"
	fi
	exit 1
fi 

# Check that IMAGE_SERVER is the same as SERVER
#
IMAGE_IP=`get_host_ip ${IMAGE_SERVER}`

if [ "${IMAGE_IP}" != "${SERVER_IP}" ]; then
    echo "${myname}: Remote image server is not supported at this time."
    exit 1
fi


# Verify that IMAGE_PATH is a valid directory
#
if [ ! -d ${IMAGE_PATH} ]; then
    echo "${myname}: Install image directory ${IMAGE_PATH} does not exist."
    exit 1
fi

# Verify valid image
#
if [ ! -f ${IMAGE_PATH}/solaris.zlib ]; then
	echo "${myname}: ${IMAGE_PATH}/solaris.zlib does not exist. " \
	    "The specified image is not an OpenSolaris image."
	exit 1
fi


# Determine if image is sparc or x86
#
IMAGE_TYPE=`get_image_type ${IMAGE_PATH}`

# For sparc, make sure the user hasn't specified a boot file via
# the "-f" option. If they have, the BOOT_FILE variable will be set.
#
if [ "${IMAGE_TYPE}" = "${SPARC_IMAGE}" ]; then
	if [ "X$BOOT_FILE" != "X" ] ; then
	    echo "${myname}: \"-f\" is an invalid option for SPARC"
	    exit 1
	fi
fi

# Verify that service corresponding to SERVICE_NAME exists
#
${DIRNAME}/setup-service lookup ${SERVICE_NAME} ${INSTALL_TYPE} local
if [ $? -ne 0 ] ; then
	echo "${myname}: Service does not exist: ${SERVICE_NAME}"
	exit 1
fi


# Convert the Ethernet address to DHCP "default client-ID" form:
#    uppercase hex, preceded by the hardware
#    address type ("01" for ethernet)
#
DHCP_CLIENT_ID=01`echo "${MAC_ADDR}" | ${TR} '[a-z]' '[A-Z]' |
    awk -F: '
	{
	    for (i = 1; i <= 6 ; i++)
		if (length($i) == 1) {
		    printf("0%s", $i)
		} else {
		    printf("%s", $i);
		}
	}'`


# Perform x86/sparc specific setup activities
#
if [ "${IMAGE_TYPE}" = "${X86_IMAGE}" ]; then
	echo "Setting up X86 client..." 
	${DIRNAME}/setup-tftp-links client ${SERVICE_NAME} ${IMAGE_PATH} \
				${DHCP_CLIENT_ID} ${BOOT_FILE}
	status=$?
	if [ $status -ne 0 ]; then
		echo "${myname}: Unable to setup x86 client"
		exit 1
	fi

	# Set value of DHCP_BOOT_FILE.
	DHCP_BOOT_FILE=${DHCP_CLIENT_ID}
	if [ "X${BOOT_FILE}" != "X" ] ; then
	    DHCP_BOOT_FILE=${BOOT_FILE}
	fi
	dhcptype="x86"
	dhcprootpath="x86"
else
	echo "Setting up SPARC client..." 
	# For sparc, set value of DHCP_BOOT_FILE and setup wanboot.conf file.
	#
	DHCP_BOOT_FILE="http://${SERVER_IP}:${HTTP_PORT}/${CGIBIN_WANBOOTCGI}"
	${DIRNAME}/setup-sparc client ${DHCP_CLIENT_ID} ${IMAGE_PATH}
	status=$?
	if [ $status -ne 0 ]; then
		echo "${myname}: Unable to setup SPARC client"
		exit 1
	fi
	dhcptype="sparc"
	dhcprootpath="http://${SERVER_IP}:${HTTP_PORT}${IMAGE_PATH}"
fi


# Try to update the DHCP server automatically. If not possible,
# then tell the user how to define the DHCP macro.
#
${DIRNAME}/setup-dhcp client ${dhcptype} ${SERVER_IP} ${DHCP_CLIENT_ID} \
				${DHCP_BOOT_FILE} ${dhcprootpath}
status=$?

if [ $status -eq 0 ]; then
	echo "Enabled network boot by adding a macro named ${DHCP_CLIENT_ID}"
	echo "to DHCP server with:"
	echo "  Boot server IP     (BootSrvA) : ${SERVER_IP}"
	echo "  Boot file          (BootFile) : ${DHCP_BOOT_FILE}"
	if [ "${IMAGE_TYPE}" = "${SPARC_IMAGE}" ]; then
		echo "  Root path          (Rootpath) : ${dhcprootpath}"
	fi
else
	echo "If not already configured, enable network boot by creating"
	echo "a macro named ${DHCP_CLIENT_ID} with:"
	echo "  Boot server IP     (BootSrvA) : ${SERVER_IP}"
	echo "  Boot file          (BootFile) : ${DHCP_BOOT_FILE}"
	if [ "${IMAGE_TYPE}" = "${SPARC_IMAGE}" ]; then
		echo "  Root path          (Rootpath) : ${dhcprootpath}"
	fi
fi

exit 0

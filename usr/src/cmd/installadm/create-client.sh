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
#       2. Creates a bootfile and /tftpboot entries. The bootfile name is
#          derived from the MAC address.
#
#       3. Setup the dhcp macro with the bootfile information if it doesn't
#          exist.
#
# Files potentially changed on server:
# /tftpboot/ - directory created/populated with pxegrub files and links.
# /etc/inetd.conf - to turn on tftpboot daemon


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

        MAC_ADDR=`expr $MAC_ADDR : '\([0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\)'`

        if [ ! "${MAC_ADDR}" ] ; then
                echo "${myname}: mal-formed MAC address: $2"
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


# Set BUILD for menu.lst file in /tftpboot (create_menu_lst_file)
#
BUILD=`basename ${IMAGE_PATH}`


# Verify that IMAGE_PATH is a valid directory
#
if [ ! -d ${IMAGE_PATH} ]; then
    echo "${myname}: Install image ${IMAGE_PATH} does not exist."
    exit 1
fi


# Append "boot" to IMAGE_PATH provided by user
#
IMAGE_PATH=${IMAGE_PATH}/boot

# Verify valid image
#
if [ ! -f ${IMAGE_PATH}/grub/pxegrub ]; then
	echo "${myname}: ${IMAGE_PATH}/grub/pxegrub does not exist," \
	    "invalid boot image"
	exit 1
fi

# Verify that service corresponding to SERVICE_NAME exists
#
${DIRNAME}/setup-service lookup ${SERVICE_NAME} ${INSTALL_TYPE} local
if [ $? -ne 0 ] ; then
	echo "${myname}: Service does not exist: ${SERVICE_NAME}"
	exit 1
fi


# lofs mount /boot directory under /tftpboot
#
mount_lofs_boot


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

# CLEAN file is used so delete-client can undo the setup
#
CLEAN="${Bootdir}/rm.${DHCP_CLIENT_ID}"
CLEANUP_FOR="${MAC_ADDR}"

# if config file already exists, run the cleanup - before checking tftpboot
#
if [ -f "${CLEAN}" ] ; then
    # do the cleanup (of old stuff)
    if [ ! -x ${DIRNAME}/delete-client ] ; then
        echo "WARNING: could not execute: ${DIRNAME}/delete-client"
        echo "  cannot clean up preexisting install client \"${CLEANUP_FOR}\""
        echo "  continuing anyway"
    else
        echo "Cleaning up preexisting install client \"${CLEANUP_FOR}\""
        ${DIRNAME}/delete-client -q ${CLEANUP_FOR}
    fi
fi

# Obtain a unique name for file in tftpboot dir.
#
aBootfile=${IMAGE_PATH}/grub/pxegrub
Bootfile=`tftp_file_name $aBootfile pxegrub`

# If the caller has specified a boot file name, we're going to eventually
# create a symlink from the pxegrub file to the caller specified name.  If
# that link already exists, make sure it points to the boot file we're
# going to use.
#
if [ "X$BOOT_FILE" != "X" ] ; then
	if [ -h "${Bootdir}/$BOOT_FILE" -a ! -f "${Bootdir}/$BOOT_FILE" ] ; then
		echo "ERROR: Specified boot file ${BOOT_FILE} already exists, "
		echo "       but does not point to anything."
		exit 1
	fi

	if [ -f "${Bootdir}/$BOOT_FILE" ] ; then
		cmp -s "${Bootdir}/${Bootfile}" "${Bootdir}/${BOOT_FILE}"
		if [ $? != 0 ] ; then
			echo "ERROR: Specified boot file ${BOOT_FILE} already ,"
			echo "       exists and is of a different version than" 
			echo "       the one needed for this client."
			exit 1
		fi
	fi
fi

# Create the boot file area, if not already created
#
if [ ! -d "${Bootdir}" ]; then
	echo "making ${Bootdir}"
	mkdir ${Bootdir}
	chmod 775 ${Bootdir}
fi

# start tftpd if needed
#
start_tftpd


# start creating clean up file
#
echo "#!/sbin/sh" > ${CLEAN}			# (re)create it
echo "# cleanup file for ${CLEANUP_FOR} - sourced by installadm delete-client" \
	>> ${CLEAN}

# install boot program (pxegrub)
if [ ! -f ${Bootdir}/${Bootfile} ]; then
	echo "copying boot file to ${Bootdir}/${Bootfile}"
	cp ${aBootfile} ${Bootdir}/${Bootfile}
	chmod 755 ${Bootdir}/${Bootfile}
fi

# create tftp symlink to bootfile
#
Menufile=${Bootdir}/menu.lst.${DHCP_CLIENT_ID}
setup_tftp "${DHCP_CLIENT_ID}" "${Bootfile}"


# create the menu.lst.<macaddr> file
#
create_menu_lst_file


# prepare for cleanup action
#
if [ "X${DHCP_CLIENT_ID}" != "X" ]; then
	printf "rm -f ${Menufile}\n" >> ${CLEAN}
fi


# Make tftpboot symlink if caller specified boot file
#
if [ "X$BOOT_FILE" != "X" ] ; then
	# Link from the pxegrub file to the user-specified name
	# We don't want to use setup_tftp because we don't want
	# to save removal commands in the cleanup file
	#
	ln -s ${Bootfile} ${Bootdir}/$BOOT_FILE

	cat <<-EOF >>${CLEAN}
		if [ -h "${Bootdir}/${BOOT_FILE}" -o -f "${Bootdir}/${BOOT_FILE}" ] ; then
		    echo "Not removing manually specified boot file \"${BOOT_FILE}\""
		    echo "because other clients may be using it."
		else
		    echo "The pxegrub file corresponding to the boot file \"${BOOT_FILE}\""
		    echo "does not exist.  Deleting \"${BOOT_FILE}\"."
		    rm -f ${Bootdir}/${BOOT_FILE}
		fi
	EOF
fi


# Try to update the DHCP server automatically. If not possible,
# then tell the user how to define the DHCP macro.
#
DHCP_BOOT_FILE=${DHCP_CLIENT_ID}
if [ "X${BOOT_FILE}" != "X" ] ; then
	DHCP_BOOT_FILE=${BOOT_FILE}
fi

status=0
if [ ! -x ${DIRNAME}/setup-dhcp ]; then
	status=1
else
	${DIRNAME}/setup-dhcp client ${SERVER_IP} ${DHCP_CLIENT_ID} \
							 ${DHCP_BOOT_FILE}
	status=$?
fi

if [ $status -eq 0 ]; then
	echo "Enabled PXE boot by adding a macro named ${DHCP_CLIENT_ID}"
	echo "to DHCP server with:"
	echo "  Boot server IP (BootSrvA) : ${SERVER_IP}"
	echo "  Boot file      (BootFile) : ${DHCP_BOOT_FILE}"
else
	echo "If not already configured, enable PXE boot by creating"
	echo "a macro named ${DHCP_CLIENT_ID} with:"
	echo "  Boot server IP (BootSrvA) : ${SERVER_IP}"
	echo "  Boot file      (BootFile) : ${DHCP_BOOT_FILE}"
fi

exit 0

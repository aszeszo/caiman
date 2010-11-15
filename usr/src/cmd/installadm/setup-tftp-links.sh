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
#       The script sets up the necessary files in the /tftpboot
#	directory so that client can boot from the netimage setup
#	by installadm create-service.
#
# Files potentially changed on server:
# /etc/inetd.conf - to turn on tftpboot daemon
# /etc/vfstab - Entry added to mount the image as a lofs device
# /tftpboot/menu.lst - menu.lst file corresponding to the service

PATH=/usr/bin:/usr/sbin:/sbin:/usr/lib/installadm; export PATH

. /usr/lib/installadm/installadm-common

# Main
#


TYPE=$1
SERVICE_NAME=$2

if [[ "$TYPE" == "client" ]]; then
	if (( $# < 4 )); then
		exit 1
	fi
	IMAGE_PATH=$3
	DHCP_CLIENT_ID=$4
	BARGLIST=$5
	BOOT_FILE=$6
	if [[ ${BARGLIST} == "null" ]]; then
		BARGLIST=""
	fi
elif [[ "$TYPE" == "server" ]]; then
	if (( $# < 5 )); then
		exit 1
	fi
	IMAGE_PATH=$3
	DHCP_CLIENT_ID=$4
	BARGLIST=$5
	if [[ ${BARGLIST} == "null" ]]; then
		BARGLIST=""
	else
		BARGLIST="${BARGLIST},"
	fi
else
	print " $TYPE - unsupported TFTP service action"
	exit 1
fi

Bootdir=/tftpboot

CLEAN="${Bootdir}/rm.${DHCP_CLIENT_ID}"
CLEANUP_FOR="${DHCP_CLIENT_ID}"

number_of_nets=$(valid_networks | $WC -l)

# see if we are multihomed
if (( number_of_nets == 1 )); then
	IMAGE_IP=$(get_ip_for_net $(valid_networks))
else
	IMAGE_IP='$serverIP'
fi

# lofs mount /boot directory under /tftpboot
#
mount_lofs_boot

# Clean the entry in /tftpboot if there is one already
clean_entry $TYPE $DHCP_CLIENT_ID

# Obtain a unique name for file in tftpboot dir.
#
aBootfile=${IMAGE_PATH}/boot/grub/pxegrub
Bootfile=$(tftp_file_name $aBootfile pxegrub)

# If the caller has specified a boot file name, we're going to eventually
# create a symlink from the pxegrub file to the caller specified name.  If
# that link already exists, make sure it points to the boot file we're
# going to use.
#

if [[ -n "$BOOT_FILE" ]]; then
	if [[ -L "${Bootdir}/$BOOT_FILE" && \
	    ! -f "${Bootdir}/$BOOT_FILE" ]]; then
		print "ERROR: Specified boot file ${BOOT_FILE} already exists, "
		print "       but does not point to anything."
		exit 1
	fi

	if [[ -f "${Bootdir}/$BOOT_FILE" ]]; then
		/usr/bin/cmp -s "${Bootdir}/${Bootfile}" "${Bootdir}/${BOOT_FILE}"
		if (( $? != 0 )); then
			print "ERROR: Specified boot file ${BOOT_FILE} already ,"
			print "       exists and is of a different version than" 
			print "       the one needed for this client."
			exit 1
		fi
	fi
fi

# Create the boot file area, if not already created
#
if [[ ! -d "${Bootdir}" ]]; then
	print "making ${Bootdir}"
	$MKDIR ${Bootdir}
	$CHMOD 775 ${Bootdir}
fi

start_tftpd

#
# start creating clean up file
#
print "#!/sbin/sh" > ${CLEAN}			# (re)create it
print "# cleanup file for ${CLEANUP_FOR} - sourced by"\
	  "installadm delete-client" >> ${CLEAN}

# install boot program (pxegrub)
if [[ ! -f ${Bootdir}/${Bootfile} ]]; then
	print "copying boot file to ${Bootdir}/${Bootfile}"
	$CP ${aBootfile} ${Bootdir}/${Bootfile}
	$CHMOD 755 ${Bootdir}/${Bootfile}
fi

# install pxegrub menu file
Menufile=${Bootdir}/menu.lst.${DHCP_CLIENT_ID}
setup_tftp "${DHCP_CLIENT_ID}" "${Bootfile}"

create_menu_lst_file

# prepare for cleanup action
printf "rm -f ${Menufile}\n" >> ${CLEAN}

# if called from create-client and the user specified a boot file,
# then make tftpboot symlink
#
if [[ "${TYPE}" == "client" && -n "$BOOT_FILE" ]]; then
	# Link from the pxegrub file to the user-specified name
	# We don't want to use setup_tftp because we don't want
	# to save removal commands in the cleanup file
	#
	$LN -s ${Bootfile} ${Bootdir}/$BOOT_FILE

	$CAT <<-EOF >>${CLEAN}
	if [[ -L "${Bootdir}/${BOOT_FILE}" ]]; then
	        $RM -f ${Bootdir}/${BOOT_FILE}
	
	fi
	EOF
fi

exit 0

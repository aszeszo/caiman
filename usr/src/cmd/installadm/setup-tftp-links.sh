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
#       The script sets up the necessary files in the /tftpboot
#	directory so that client can boot from the netimage setup
#	by installadm create-service.
#
# Files potentially changed on server:
# /etc/inetd.conf - to turn on tftpboot daemon
# /etc/vfstab - Entry added to mount the image as a lofs device
# /tftpboot/menu.lst - menu.lst file corresponding to the service

. /usr/lib/installadm/installadm-common

# Main
#

if [ $# -lt 4 ]; then
	exit 1
fi

TYPE=$1 		# "client" or "server"
SERVICE_NAME=$2
IMAGE_PATH=$3
DHCP_CLIENT_ID=$4

if [ "$TYPE" = "client" ]; then
	BARGLIST=$5
	BOOT_FILE=$6
	if [ ${BARGLIST} = "null" ]; then
		BARGLIST=""
	fi
elif [ "$TYPE" != "server" ]; then
	echo " $TYPE - unsupported TFTP service action"
	exit 1
fi

Bootdir=/tftpboot

CLEAN="${Bootdir}/rm.${DHCP_CLIENT_ID}"
CLEANUP_FOR="${DHCP_CLIENT_ID}"
IMAGE_IP=`get_server_ip`

# lofs mount /boot directory under /tftpboot
#
mount_lofs_boot

# Clean the entry in /tftpboot if there is one already
clean_entry $TYPE $DHCP_CLIENT_ID

# Obtain a unique name for file in tftpboot dir.
#
aBootfile=${IMAGE_PATH}/boot/grub/pxegrub
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

start_tftpd

#
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

# install pxegrub menu file
Menufile=${Bootdir}/menu.lst.${DHCP_CLIENT_ID}
setup_tftp "${DHCP_CLIENT_ID}" "${Bootfile}"

create_menu_lst_file

# prepare for cleanup action
printf "rm -f ${Menufile}\n" >> ${CLEAN}

# if called from create-client and the user specified a boot file,
# then make tftpboot symlink
#
if [ "${TYPE}" = "client" -a "X$BOOT_FILE" != "X" ]; then
	# Link from the pxegrub file to the user-specified name
	# We don't want to use setup_tftp because we don't want
	# to save removal commands in the cleanup file
	#
	ln -s ${Bootfile} ${Bootdir}/$BOOT_FILE

	cat <<-EOF >>${CLEAN}
	if [ -h "${Bootdir}/${BOOT_FILE}" ] ; then
	        rm -f ${Bootdir}/${BOOT_FILE}
	
	fi
	EOF
fi

exit 0

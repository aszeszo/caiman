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
#       It contains common functions used by create-client and
#	setup-tftp-links, which is used by when the user issues
#	installadm create-service.
#
# Files potentially changed on server:
# /etc/inetd.conf - to turn on tftpboot daemon
# /etc/vfstab - Entry added to mount the image as a lofs device
# /tftpboot/menu.lst - menu.lst file corresponding to the service/client

SVCS=/usr/bin/svcs
SVCADM=/usr/sbin/svcadm
VERSION=OpenSolaris
HTTP_PORT=5555

#
# get_host_ip
#
# Purpose : Get the IP address from the host name 
#
# Arguments : 
#	$1 - Host Name
#
# Returns IP address
#
get_host_ip()
{
	hname=$1
	HOST_IP=`getent hosts ${hname} | nawk '{ print $1 }`
	echo "$HOST_IP"
}

#
# get_server_ip
#
# Purpose : Get the IP address of the machine where this program is running.
#
# Arguments : 
#	None
#
# Returns IP address of the current host.
#
get_server_ip()
{
	SERVER=`uname -n`
	SERVER_IP=`get_host_ip $SERVER`
	echo "$SERVER_IP"
}

#
# clean_entry
#
# Purpose : Cleanup the /tftpboot files corresponding the entry
#	    we are trying to create for this service/ethernet address
#
# Arguments : 
#	$1 - Boot File Name
#
clean_entry()
{
	bname=$1
	# See if there's a cleanup file corresponding to the passed 
	# boot file 
	#
	if [ "X${bname}" != "X" -a \
	    -f "${Bootdir}/rm.${bname}" ] ; then
        	CLEAN=${Bootdir}/rm.${bname}
	fi

	# If a cleanup file exists, source it
	#
	if [ -f ${CLEAN} ]; then
		. ${CLEAN}
	fi

	rm -f ${CLEAN}
}

#
# create_menu_lst_file
#
# Purpose : Create the menu.lst file so that the client can get the information
#	    about the netimage and dwonload the necessary files.
#	    It also adds location of the kernel, microroot and other options.
#
# Arguments : 
#	None. But expected $Menufile is set to correct file.
#
#
create_menu_lst_file()
{
	# create the menu.lst.<bootfile> file
	#
	touch ${Menufile}
	grep "kernel /${BootLofs}/x86.microroot" ${Menufile} > /dev/null 2>&1
	if [ $? != 0 ]; then
		printf "default=0\n" > $Menufile
		printf "timeout=30\n" >> $Menufile
		printf "title ${VERSION} ${BUILD}\n" >> $Menufile

		printf "\tkernel /${BootLofs}/platform/i86pc/kernel/unix -B ${BARGLIST}" >> $Menufile

		# add install media path, install boot archive,
		# and service name
		#
		printf "install_media=" >> $Menufile
		printf "http://${IMAGE_IP}:${HTTP_PORT}" >> $Menufile
		dir=`dirname "${IMAGE_PATH}"`
		printf "${dir}" >> $Menufile	
		printf ",install_boot=" >> $Menufile
		printf "http://${IMAGE_IP}:${HTTP_PORT}" >> $Menufile
		printf "${IMAGE_PATH}" >> $Menufile

		printf ",install_service=" >> $Menufile
		printf "${SERVICE_NAME}"  >> $Menufile

		printf ",livemode=text\n" >> $Menufile
		printf "\tmodule /${BootLofs}/x86.microroot\n" >> $Menufile
	fi
}

#
# mount_lofs_boot
#
# Purpose : Create the loopback mount of the boot directory of the netimage
#	    under /tftpboot. Also updates /etc/vfstab so that they are always
#	    mounted.
#
# Arguments : 
#	None. But expected $IMAGE_PATH is set to the netimage and
#	$Bootdir is set to /tftpboot
#
#
mount_lofs_boot()
{
	# lofs mount /boot directory under /tftpboot
	# First, check if it is already mounted
	#
	line=`grep "^${IMAGE_PATH}[ 	]" /etc/vfstab`
	if [ $? = 0 ]; then
		# already mounted
		mountpt=`echo $line | cut -d ' ' -f3`
		BootLofs=`basename "${mountpt}"`
		BootLofsdir=`dirname "${mountpt}"`
		if [ ${BootLofsdir} != ${Bootdir} ]; then
			printf "${myname}: ${IMAGE_PATH} mounted at"
			printf " ${mountpt}\n"
			printf "${myname}: retry after unmounting and deleting"
			printf " entry form /etc/vfstab\n"
			exit 1
		fi

		# Check to see if the mount is sane, if not, kick it.
		#
		# Note: One might think that the case when kicking the
		#       mounpoint won't work should then be handled, but
		#	if that were the case, the code path for no existing
		#	mount would have been taken resulting in a new
		#	mountpoint being created.
		#
		if [ ! -f $mountpt/multiboot  ]; then
			umount $mountpt
			mount $mountpt
		fi
	else
		# Not mounted. Get a new directory name and mount IMAGE_PATH
		max=0
		for i in ${Bootdir}/I86PC.${VERSION}* ; do
			max_num=`expr $i : ".*boot.I86PC.${VERSION}-\(.*\)"`
			if [ "$max_num" -gt $max ]; then
				max=$max_num
			fi
		done
		max=`expr $max + 1`

		BootLofs=I86PC.${VERSION}-${max}
		mkdir -p ${Bootdir}/${BootLofs}
		mount -F lofs -o ro ${IMAGE_PATH} ${Bootdir}/${BootLofs}
		if [ $? != 0 ]; then
			echo "${myname}: failed to mount ${IMAGE_PATH} on" \
			   "${Bootdir}/${BootLofs}"
			exit 1
		fi
		printf "${IMAGE_PATH} - ${Bootdir}/${BootLofs} " >> /etc/vfstab
		printf "lofs - yes ro\n" >> /etc/vfstab
	fi
}

#
# start tftpd if needed
#
start_tftpd()
{
	
	INETD_CONF="/etc/inetd.conf"
	TMP_INETD_CONF="/tmp/inetd.conf.$$"

	# see if tftp is in the /etc/inetd.conf file. If it is there
	# and commented out, need to uncomment it. If it isn't there
	# at all, need to add it.
	#
	convert=0
	if grep '^#tftp[ 	]' ${INETD_CONF} > /dev/null ; then
		# Found it commented out, so it must be disabled. Use 
		# sed to uncomment.
		#
		convert=1
		echo "enabling tftp in /etc/inetd.conf"
		sed '/^#tftp/ s/#//' ${INETD_CONF} > ${TMP_INETD_CONF}
	else
		cp ${INETD_CONF} ${TMP_INETD_CONF}
		grep -s '^tftp[ 	]' ${TMP_INETD_CONF} > /dev/null
		if [ $? -eq 1 ] ; then
			# No entry, so add it. 
			#
			convert=1
			echo "adding tftp to /etc/inetd.conf"
			cat >> ${TMP_INETD_CONF} <<-EOF
			# TFTPD - tftp server (primarily used for booting)
			tftp	dgram	udp6	wait	root	/usr/sbin/in.tftpd	in.tftpd -s /tftpboot
			EOF
                fi
	fi

	if [ $convert -eq 1 ]; then
		# Copy the modified tmp file to the real thing
		#
		cp ${TMP_INETD_CONF} ${INETD_CONF}

		# If the "network/tftp/udp6" service doesn't
		# already exist, convert it.
		/usr/bin/svcprop -q network/tftp/udp6 > /dev/null 2>&1
		if [ $? != 0 ]; then
			echo "Converting /etc/inetd.conf"
			/usr/sbin/inetconv >/dev/null 2>&1
		fi
	fi

	rm -f ${TMP_INETD_CONF}

	# Enable the network/tftp/udp6 service if not already enabled.
	#
	state=`$SVCS -H -o STATE network/tftp/udp6:default`
	if [ "$state" != "online" ]; then
		echo "enabling network/tftp/udp6 service"
		$SVCADM enable network/tftp/udp6
		if [ $? != 0 ]; then
			echo "unable to start tftp service, exiting"
			exit 1
		fi
	fi
}

#
# tftp_file_name
#
# Purpose : Determine the name to use for installing a file in ${Bootdir}.
#	    Use an existing file if there is one that matches, otherwise
#	    make up a new name with a version number suffix.
#
# Arguments :
#   $1 - the file to be installed
#   $2 - the prefix to use for forming a name
#
# Results :
#   Filename written to standard output.
#
tftp_file_name()
{
	SRC=$1
	BASE=$2
	file_to_use=

	I86PC="I86PC"

	# Determine the name to use for the file in bootdir.
	# Either use an existing file or make up a new name with a version
	# number appended.
	for i in ${Bootdir}/${BASE}.${I86PC}.${VERSION}* ; do
		#
		# avoid symbolic links, or we can end up with
		# inconsistent references
		#
		if [ -h $i ]; then
			continue
		fi

		if cmp -s $SRC $i; then
			file_to_use=$i
			break
		fi
	done

	if [ "$file_to_use" ]; then
		file_to_use=`basename $file_to_use`
	else
		# Make this name not a subset of the old style names, so old style
		# cleanup will work.

		max=0
		for i in ${Bootdir}/${BASE}.${I86PC}.${VERSION}* ; do
			max_num=`expr $i : ".*${BASE}.${I86PC}.${VERSION}-\(.*\)"`

			if [ "$max_num" -gt $max ]; then
				max=$max_num
			fi
		done

		max=`expr $max + 1`

		file_to_use=${BASE}.${I86PC}.${VERSION}-${max}
	fi
	echo $file_to_use
}

#
# setup_tftp
#
# Purpose : Create a link from one filename to another.  Also store a
#	    command in the cleanup file to remove the created link.
#
# Arguments :
#   $1 - the link target
#   $2 - the link source
#
setup_tftp()
{
	target=$1
	source=$2

	echo "rm /tftpboot/${target}" >> ${CLEAN}

	if [ -h /tftpboot/${target} ]; then
    	    # save it, and append the cleanup command
    	    mv /tftpboot/${target} /tftpboot/${target}-
	    echo "mv /tftpboot/${target}- /tftpboot/${target}" >> ${CLEAN}
	fi

	ln -s ${source} /tftpboot/${target}
}


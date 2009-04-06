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
#       It contains common functions used by create-client and
#	setup-tftp-links, which is used by when the user issues
#	installadm create-service.
#
# Files potentially changed on server:
# /etc/inetd.conf - to turn on tftpboot daemon
# /etc/vfstab - Entry added to mount the image as a lofs device
# /tftpboot/menu.lst - menu.lst file corresponding to the service/client

SED=/usr/bin/sed
VERSION=OpenSolaris
HTTP_PORT=5555

SPARC_IMAGE="sparc_image"
X86_IMAGE="x86_image"
DOT_RELEASE=".release"
CGIBIN_WANBOOTCGI="cgi-bin/wanboot-cgi"
SERVICE_CONFIG_DIR="/var/installadm/services"
AIWEBSERVER="aiwebserver"
SERVICE_ADDRESS_UNKNOWN="unknown"

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
	HOST_IP=`getent hosts ${hname} | nawk '{ print $1 }'`
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
# get_image_type
#
# Purpose : Determine if image is sparc or x86
#
# Arguments : 
#	$1 - path to image
#
# Returns: "sparc_image" or "x86_image"
#
get_image_type()
{
	image_path=$1
	if [ -d ${image_path}/platform/sun4v ]; then
		image_type="${SPARC_IMAGE}"
	elif [ -d ${image_path}/platform/i86pc ]; then
		image_type="${X86_IMAGE}"
	else 
		echo "Unable to determine OpenSolaris install image type"
		exit 1
	fi
	echo "$image_type"
}

#
# clean_entry
#
# Purpose : Cleanup the /tftpboot files corresponding the entry
#	    we are trying to create for this service/ethernet address
#
# Arguments : 
#	$1 - client or server
#	$2 - Boot File Name
#
clean_entry()
{
	type=$1
	bname=$2
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
		if [ "${type}" = "client" ]; then
		    echo "Cleaning up preexisting install client \"${bname}\""
		fi
		. ${CLEAN}
	fi

	rm -f ${CLEAN}
}

#
# get_relinfo
#
# Purpose: Get the release info from the <image>/.release file. If the file does not
#	   exist, return the value of $VERSION. 
#
# Arguments: 
#	$1 - path to image
#
# Returns: release info from <image>/.release file or value of $VERSION.
#

#
get_relinfo()
{
	releasepath=$1/${DOT_RELEASE}
	if [ -f ${releasepath} ]; then
		releaseinfo=`head -1 ${releasepath}`
	else
		releaseinfo=$VERSION
	fi
	echo "$releaseinfo"
}

#
# get_service_address
#
# Purpose: Get the service location (machine ip and port nuber)
#          for given service name. Common service database is
#          looked up for this information.
#          
#
# Arguments: 
#	$1 - service name
#
# Returns: service address in format <machine_ip>:<port_number>
#          if service not found in database, "unknown" is returned
#
#
get_service_address()
{
	srv_config_file="$SERVICE_CONFIG_DIR/$1"

	# if configuration file for particular file doesn't exist, exit
	if [ ! -f "$srv_config_file" ] ; then
		echo "$SERVICE_ADDRESS_UNKNOWN"
		return 0
	fi

	#
	# search for txt record in service configuration file
	# data are stored as name-value pairs - one pair per line
	#
	# ...
	# txt_record=aiwebserver=<machine_hostname>:<machine_port>
	# ...
	#
	srv_location=`cat "$srv_config_file" | grep "txt_record" |
	    cut -f 3 -d '='`

	# if location of service can't be obtained, return with "unknown"
	if [ -z "$srv_location" ] ; then
		echo "$SERVICE_ADDRESS_UNKNOWN"
		return 0
	fi

	srv_address_hostname=`echo "$srv_location" | cut -f 1 -d ":"`
	srv_address_ip=`get_host_ip "$srv_address_hostname"`
	srv_address_port=`echo "$srv_location" | cut -f 2 -d ":"`

	# if port or IP can't be determined, return with "unknown"
	if [ -n "$srv_address_ip" -a -n "$srv_address_port" ] ; then
		echo "$srv_address_ip:$srv_address_port"
	else
		echo "$SERVICE_ADDRESS_UNKNOWN"
	fi

	return 0
}

#
# create_menu_lst_file
#
# Purpose : Create the menu.lst file so that the x86 client can get the
#	    information about the netimage and download the necessary files.
#	    It also adds location of the kernel, boot_archive and other options.
#
# Arguments : 
#	None, but it is expected that:
#		$Menufile is set to the correct file.
#		$IMAGE_PATH is set to the absolute path of the image.
#		$SERVICE_NAME is set to the service name.
#		$SERVICE_ADDRESS is set to the location of given service.
#		$IMAGE_IP is set to the IP of the server hosting the image.
#
create_menu_lst_file()
{

	# create the menu.lst.<bootfile> file
	#
	tmpmenu=${Menufile}.$$

	printf "default=0\n" > ${tmpmenu}
	printf "timeout=30\n" >> ${tmpmenu}
	printf "min_mem64=1536\n" >> ${tmpmenu}

	# get release info and strip leading spaces
	relinfo=`get_relinfo ${IMAGE_PATH}`
	title=`echo title ${relinfo} | $SED -e 's/  //g'`
	printf "${title} \n" >> ${tmpmenu}

	printf "\tkernel\$ /${BootLofs}/platform/i86pc/kernel/\$ISADIR/unix -B ${BARGLIST}" >> ${tmpmenu}

	# add install media path and service name
	#
	printf "install_media=" >> ${tmpmenu}
	printf "http://${IMAGE_IP}:${HTTP_PORT}" >> ${tmpmenu}
	printf "${IMAGE_PATH}" >> ${tmpmenu}	

	printf ",install_service=" >> ${tmpmenu}
	printf "${SERVICE_NAME}"  >> ${tmpmenu}

	#
	# add service location
	# it can be either provided by the caller or set to "unknown"
	#
	# If set to "unknown", try to look up this information
	# in service configuration database right now
	#
	[ "$SERVICE_ADDRESS" = "$SERVICE_ADDRESS_UNKNOWN" ] &&
	    SERVICE_ADDRESS=`get_service_address ${SERVICE_NAME}`

	if [ "$SERVICE_ADDRESS" != "$SERVICE_ADDRESS_UNKNOWN" ] ; then
		echo "Service discovery fallback mechanism set up"

		printf ",install_svc_address=" >> ${tmpmenu}
		printf "$SERVICE_ADDRESS"  >> ${tmpmenu}
	else
		echo "Couldn't determine service location, fallback " \
		    "mechanism will not be available"
	fi

	printf ",livemode=text\n" >> ${tmpmenu}
	if [ -f ${IMAGE_PATH}/boot/x86.microroot ]; then
		# for backwards compatibility, check for x86.microroot
		printf "\tmodule /${BootLofs}/x86.microroot\n" >> ${tmpmenu}
	else
		printf "\tmodule /${BootLofs}/boot_archive\n" >> ${tmpmenu}
	fi
        mv ${tmpmenu} ${Menufile}

        return 0

}

#
# mount_lofs_boot
#
# Purpose : Create the loopback mount of the boot directory of the netimage
#	    under /tftpboot. Also updates /etc/vfstab so that they are always
#	    mounted.
#
# Arguments : 
#	None. But it is expected that $IMAGE_PATH is set to the netimage
#	and $Bootdir is set to /tftpboot
#
#
mount_lofs_boot()
{
	# lofs mount /boot directory under /tftpboot
	# First, check if it is already mounted
	#
	IMAGE_BOOTDIR=${IMAGE_PATH}/boot
	line=`grep "^${IMAGE_BOOTDIR}[ 	]" /etc/vfstab`
	if [ $? = 0 ]; then
		# already mounted
		mountpt=`echo $line | cut -d ' ' -f3`
		BootLofs=`basename "${mountpt}"`
		BootLofsdir=`dirname "${mountpt}"`
		if [ ${BootLofsdir} != ${Bootdir} ]; then printf "${myname}: ${IMAGE_BOOTDIR} mounted at"
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
		# Not mounted. Get a new directory name and mount IMAGE_BOOTDIR
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
		mount -F lofs -o ro ${IMAGE_BOOTDIR} ${Bootdir}/${BootLofs}
		if [ $? != 0 ]; then
			echo "${myname}: failed to mount ${IMAGE_BOOTDIR} on" \
			   "${Bootdir}/${BootLofs}"
			exit 1
		fi
		printf "${IMAGE_BOOTDIR} - ${Bootdir}/${BootLofs} " >> /etc/vfstab
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
		$SED '/^#tftp/ s/#//' ${INETD_CONF} > ${TMP_INETD_CONF}
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

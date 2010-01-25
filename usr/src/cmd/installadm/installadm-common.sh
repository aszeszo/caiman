#!/bin/ksh
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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
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

AWK=/bin/awk
GREP=/bin/grep
IFCONFIG=/usr/sbin/ifconfig
MV=/bin/mv
SED=/usr/bin/sed
SVCCFG=/usr/sbin/svccfg

VERSION=OpenSolaris
HTTP_PORT=5555

SPARC_IMAGE="sparc_image"
X86_IMAGE="x86_image"
DOT_RELEASE=".release"
DOT_IMAGE_INFO=".image_info"
GRUB_TITLE_KEYWORD="GRUB_TITLE"
GRUB_MIN_MEM64="GRUB_MIN_MEM64"
CGIBIN_WANBOOTCGI="cgi-bin/wanboot-cgi"
NETBOOTDIR="/etc/netboot"
WANBOOT_CONF_FILE="wanboot.conf"
SPARC_INSTALL_CONF="install.conf"
WANBOOT_CONF_SPEC="${NETBOOTDIR}/${WANBOOT_CONF_FILE}"
SMF_INST_SERVER="svc:/system/install/server:default"
AIWEBSERVER="aiwebserver"
SERVICE_ADDRESS_UNKNOWN="unknown"

#
# get_host_ip
#
# Purpose : Use getent(1M) to get the IP address for the given host name 
#	    or IP.  NOTE: this function will return the first entry
#	    returned from getent(1M) in cases were multiple entries
#	    are yielded.
#
# Arguments : 
#	$1 - Hostname or IP address.
#
# Returns IP address
#
get_host_ip()
{
	hname=$1
	if [ -z "$hname" ]; then
		return
	fi

	HOST_IP=`getent hosts ${hname} | head -1 | nawk '{ print $1 }'`
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
# get_ip_netmask
#
# Purpose : Get the netmask set for the given IP address on the current host.
#           Assumes IP address is currently set on an interface.
#
# Arguments :
#	$1 - IP address
#
# Returns netmask in hexidecimal notation (e.g. ffffff00)
#
get_ip_netmask()
{
	ipaddr=$1

	if [ -z "$ipaddr" ]; then
		return
	fi

	$IFCONFIG -a | grep broadcast | awk '{print $2, $4}' | \
		while read t_ipaddr t_netmask ; do
			if [ "$t_ipaddr" = "$ipaddr" ]; then
				echo "$t_netmask"
				break
			fi
		done
}

#
# get_network
#
# Purpose : Determine the network number given an IP addres and the netmask.
#
# Arguments :
#	$1 - IP address
#	$2 - netmask in hexidecimal notation (e.g. ffffff00)
#
# Returns network number
#
get_network()
{
	if [ $# -ne 2 ]; then
		return
	fi

NETWORK=`echo | nawk -v ipaddr=$1 -v netmask=$2 '
function bitwise_and(x, y) {

	# This function ands together the lower four bits of the two decimal
	# values passed in, and returns the result as a decimal value.

        a[4] = x % 2;
        x -= a[4];
        a[3] = x % 4;
        x -= a[3]
        a[2] = x % 8;
        x -= a[2];
        a[1] = x;

        b[4] = y % 2;
        y -= b[4];
        b[3] = y % 4;
        y -= b[3]
        b[2] = y % 8;
        y -= b[2];
        b[1] = y;

        for (j = 1; j <= 4; j++)
                if (a[j] != 0 && b[j] != 0)
                        ans[j] = 1;
                else
                        ans[j] = 0;

        return(8*ans[1] + 4*ans[2] + 2*ans[3] + ans[4]);
}

BEGIN {
        ip=ipaddr
        netm=netmask

        # set up the associative array for mapping hexidecimal numbers
        # to decimal fields.

        hex_to_dec["0"]=0
        hex_to_dec["1"]=1
        hex_to_dec["2"]=2
        hex_to_dec["3"]=3
        hex_to_dec["4"]=4
        hex_to_dec["5"]=5
        hex_to_dec["6"]=6
        hex_to_dec["7"]=7
        hex_to_dec["8"]=8
        hex_to_dec["9"]=9
        hex_to_dec["a"]=10
        hex_to_dec["b"]=11
        hex_to_dec["c"]=12
        hex_to_dec["d"]=13
        hex_to_dec["e"]=14
        hex_to_dec["f"]=15
        hex_to_dec["A"]=10
        hex_to_dec["B"]=11
        hex_to_dec["C"]=12
        hex_to_dec["D"]=13
        hex_to_dec["E"]=14
        hex_to_dec["F"]=15

        # split the netmask into an array of 8 4-bit numbers
        for (i = 1; i <= 8; i++)
                nm[i]=hex_to_dec[substr(netm, i, 1)]

        # split the ipaddr into its four decimal fields
        split(ip, df, ".")

        # now, for each decimal field, split the 8-bit number into its
        # high and low 4-bit fields, and do a bit-wise AND of those
        # fields with the corresponding fields from the netmask.

        for (i = 1; i <= 4; i++) {
                lo=df[i] % 16;
                hi=(df[i] - lo)/16;

                res_hi[i] = bitwise_and(hi, nm[2*i - 1])
                res_lo[i] = bitwise_and(lo, nm[2*i])
        }

        printf("%d.%d.%d.%d",
            res_hi[1]*16 + res_lo[1],
            res_hi[2]*16 + res_lo[2],
            res_hi[3]*16 + res_lo[3],
            res_hi[4]*16 + res_lo[4]);
}'`

echo "$NETWORK"
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
# get_grub_title
#
# Purpose: Get the line used in the title line of the grub menu.
#	   If the <image>/.image_info file contains the GRUB_TITLE line
#	   specifying the grub title to be used, the string will be returned.
#	   Otherwise, use the first line of the <image>/.release file as the 
#	   title of the grub menu. If the <image>/.release file does not
#	   exist, return the value of $VERSION. 
#
# Arguments: 
#	$1 - path to image
#
# Returns: String specified with the GRUB_TITLE keyward in <image>/.image_info
#	file.  If no GRUB_TITLE is specified or if <image>/.image_info
#	does not exist, the first line of the <image>/.release file will
#	be returned.  If <image>/.release file is not found, the value of
#	$VERSION will be returned.
#
get_grub_title()
{

	grub_title=""

	image_info_path=$1/${DOT_IMAGE_INFO}
	if [ -f ${image_info_path} ] ; then
		while read line ; do
			if [[ "${line}" == ~(E)^${GRUB_TITLE_KEYWORD}=.* ]]
			then
				grub_title="${line#*=}" 
			fi
		done < ${image_info_path}
	fi

	if [ "X${grub_title}" == "X" ] ; then
		releasepath=$1/${DOT_RELEASE}
		if [ -f ${releasepath} ]; then
			grub_title=`head -1 ${releasepath}`
		else
			grub_title=$VERSION
		fi
	fi
	echo "$grub_title"
}

#
# get_grub_min_mem64
#
# Purpose: Get minimum memory required to boot network AI in 64 bit mode.
#	   GRUB menu.lst is then populated with 'min_mem64' option accordingly.
#	   If that parameter can't be obtained, return 1536 (1,5GB) for backward
#	   compatibility.
#
# Arguments: 
#	$1 - path to image
#
# Returns: String specified with the GRUB_MIN_MEM64 keyword
#	in <image>/.image_info file. If no GRUB_MIN_MEM64 is specified or if
#	<image>/.image_info does not exist, return 1536 (1,5GB).
#
get_grub_min_mem64()
{

	grub_min_mem64=""

	image_info_path=$1/${DOT_IMAGE_INFO}
	if [ -f ${image_info_path} ] ; then
		while read line ; do
			if [[ "${line}" == ~(E)^${GRUB_MIN_MEM64}=.* ]]
			then
				grub_min_mem64="${line#*=}"
			fi
		done < ${image_info_path}
	fi

	if [ -z "$grub_min_mem64" ] ; then
		grub_min_mem64="1536"
	fi

	echo "$grub_min_mem64"
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
	#
	# Search for the txt_record in the AI service's SMF properties.
	# The data is stored as a property of the AI service's property group.
	#
	# ...
	# txt_record=aiwebserver=<machine_hostname>:<machine_port>
	# ...
	#
	srv_location=`$SVCCFG -s $SMF_INST_SERVER listprop \
	    AI$1/txt_record`
	srv_location="${srv_location#*=}"

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

	# get min_mem64 entry
	min_mem64=`get_grub_min_mem64 "$IMAGE_PATH"`
	printf "min_mem64=$min_mem64\n" >> ${tmpmenu}

	# get release info and strip leading spaces
	grub_title_string=`get_grub_title ${IMAGE_PATH}`
	title=`echo title ${grub_title_string} | $SED -e 's/  //g'`
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

	printf "\n" >> ${tmpmenu}

	#
	# for backwards compatibility, inspect layout of boot archive and
	# generate GRUB 'module' entry accordingly. Two scenarios are covered:
	#
	# [1] combined boot archive (contains both 32 and 64 bit stuff)
	#     <ai_image>/boot/x86.microroot
	# [2] separate 32 and 64 bit boot archives
	#     <ai_image>/platform/i86pc/$ISADIR/boot_archive
	#
	if [ -f ${IMAGE_PATH}/boot/x86.microroot ]; then
		printf "\tmodule /${BootLofs}/x86.microroot\n" >> ${tmpmenu}
	else
		printf "\tmodule$ /${BootLofs}/platform/i86pc/\$ISADIR/boot_archive\n" >> ${tmpmenu}
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
# Remove the entry for the service mountpoint from vfstab
#
# Arguments:
#       $1 - Service name
#
# Returns:
#       None
#
remove_vfstab_entry()
{
	name=$1

	# Read the image_path from the smf database
	IMAGE_PATH=`${SVCCFG} -s svc:/system/install/server:default listprop \
	    AI${name} | ${GREP} image_path | ${AWK} '{print $3}'`
	if [ "X${IMAGE_PATH}" == "X" ] ; then
		# Didn't exist so there is nothing to remove
		return
	fi
	IMAGE_BOOTDIR=${IMAGE_PATH}/boot

	# Check to see if the entry is in /etc/vfstab.
	# If it's not, there's nothing to do so just return
	${GREP} "^${IMAGE_BOOTDIR}[ 	]" /etc/vfstab
	if [ $? -ne 0 ]; then
		return
	fi
	while read line ; do
		# grab the device field
		device=`echo ${line} | ${AWK} '{print $1}'`
		# If the device is our image boot dir don't write it out
		if [ "${device}" != "${IMAGE_BOOTDIR}" ] ; then
			printf "${line}\n" >> /tmp/vfstab.$$
		fi
	done < /etc/vfstab
	${MV} /tmp/vfstab.$$ /etc/vfstab
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

#
# find_network_attr
#
# Purpose : Given an IP address, figure out which network on this
#	    server it belongs to, or its netmask, depending on $2.
#	    Workhorse function for find_network(), find_network_nmask() and
#	    find_network_baseIP()
#
# Parameters :
#	$1 - IP address
#	$2 - what gets returned: one of "network", "netmask" or "netIPaddr"
#		- "network" specifies that this function returns the network
#			corresponding to the IP address (IP addr & netmask)
#		- "netmask" specifies that this function returns the netmask
#			of the network corresponding to the IP address
#		- "netIPaddr" specifies that this function returns the base IP
#			address of the network corresponding to the IP address
# Returns :
#	Network for IP address passed in.
#
find_network_attr()
{
	typeset ipaddr=$1
	typeset attr=$2

	if [ -z "$ipaddr" ] ; then
		return
	fi

	# Iterate through the interfaces to figure what the possible
	# networks are (in case this is a multi-homed server).
	# For each network, use its netmask with the given IP address 
	# to see if resulting network matches.
	$IFCONFIG -a | grep broadcast | awk '{print $2, $4}' | \
		while read t_ipaddr t_netmask ; do

			# get network of this interface
			if_network=`get_network $t_ipaddr $t_netmask`
			if [ -z $if_network ]; then
				continue
			fi

			# get network for passed in ipaddr based
			# on this interfaces's netmask
			ip_network=`get_network $ipaddr $t_netmask`
			if [ -z $ip_network ]; then
				continue
			fi

			# if networks match, this is the network that
			# the passed in ipaddr belongs to.
			if [ "$if_network" = "$ip_network" ] ; then
				case $attr in
					"network" )
						echo "$if_network"
						;;
					"netmask" )
						echo "$t_netmask"
						;;
					"netIPaddr" )
						echo "$t_ipaddr"
						;;
				esac
				break
			fi
		done
}

#
# find_network
#
# Purpose : Given an IP address, figure out which network on this
#	    server it belongs to.
#
# Parameters :
#	$1 - IP address
#
# Returns :
#	Network for IP address passed in.
#
find_network()
{
	echo `find_network_attr $1 "network"`
}

#
# find_network_nmask()
#
# Purpose : Given an IP address, figure out which network on this server it
#	belongs to, and return that network's netmask.
#
# Parameters :
#	$1 - IP address
#
# Returns :
#	Netmask for IP address passed in.
#
find_network_nmask()
{
	echo `find_network_attr $1 "netmask"`
}

#
# find_network_baseIP()
#
# Purpose : Given an IP address, figure out which network on this server it
#	belongs to, and return that network's base IP address.
#
# Parameters :
#	$1 - IP address
#
# Returns :
#	Netmask for IP address passed in.
#
find_network_baseIP()
{
	echo `find_network_attr $1 "netIPaddr"`
}

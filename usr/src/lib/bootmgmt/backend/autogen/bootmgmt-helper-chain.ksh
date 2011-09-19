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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

#
# DO NOT CHANGE THE FORMAT OF THIS SCRIPT'S OUTPUT WITHOUT ALSO CHANGING
# bootmgmt.backend.autogen.chain'S PARSING CODE!
#
# This script attempts to detect legacy OS's installed on the system and
# outputs lines that the pybootmgmt package uses to create chain loading
# directives in boot loader menus.
# Currently this is know to work for NT derived Windows systems (ntfs or
# FAT fs on IFS partitions) as well as DOS/Win9x systems (FAT on FAT
# partitions). It is likely to work for OS/2 on IFS partitions. Linux,
# particularly on extended partitions is not supported at this point. For
# every non-understood partition type that is potentially bootable a
# comment is generated that identifies its Solaris device name, the
# partition type as well as the GRUB device name to give an educated user
# as much information as possible to generate their own entry.


# generate a chainload entry for a specific OS entry
# of the form:
# <title>:<grub root>:<active>
#
entry()
{
	root=$1
        _partition=$2
	title=$3
	active=$4

	printf "\n$title:$root:$_partition:$active"
}

# process a FAT partition
#
handle_fat()
{
	root=$3
        part=$4

	entry $root $part Windows False
}

# process an IFS partition
#
handle_ifs()
{
	dev=$1
	rdev=$2
	root=$3
        part=$4

	sig=`dd if=${rdev} bs=512 count=1 2>/dev/null |strings 2>/dev/null | head -1 | awk '{ print $1 }'`
	if [ "$sig" = "NTFS" ] ; then
		entry $root $part "Windows" False
	else
		entry $root $part OS/2 False
	fi
}

# process a Solaris partition - this only deals with DCA based Solaris
# instances as GRUB based Solaris instances are handled directly by bootadm
#
handle_solaris()
{
	dev=$1
	rdev=$2
	root=$3
        part=$4

	tmp=/tmp/mnt$$
	mkdir $tmp

	for i in 0 1 3 4 5 6 7 ; do
		fs=`fstyp ${dev}s$i 2> /dev/null`
		if [ "$fs" = "ufs" ] ; then
			mount -o ro ${dev}s$i $tmp 2> /dev/null
			if [ $? != 0 ] ; then
				continue
			fi

			if [ -f $tmp/etc/release ] ; then
				if [ ! -f $tmp/platform/i86pc/multiboot ] &&
				    [ -f $tmp/boot/solaris/boot.bin ] ; then
					release=`head -1 $tmp/etc/release | \
					    sed "s/^[	 ]*//"`
					entry $root $part "$release" True
				fi
			fi
			umount $tmp > /dev/null 2>&1
		fi
	done

	rmdir $tmp
}

# process a Solaris x86-boot partition
#
handle_x86boot()
{
	dev=$1
	rdev=$2
	root=$3
	part=$4

	tmp=/tmp/mnt$$
	mkdir $tmp
	
	fs=`fstyp $rdev 2> /dev/null`
	device=""
	if [ "$fs" = "pcfs" ] ; then
		mount -o ro -F pcfs ${dev}p$partition $tmp 2> /dev/null
		device=`grep "^setprop bootpath " $tmp/solaris/bootenv.rc \
		    2> /dev/null | awk '{ print $3 }' | sed s/\'//`
		umount $tmp 2> /dev/null 2>&1
	fi

	if [ -z "$device" ] ; then
		rmdir $tmp
		return
	fi

	fs=`fstyp /devices/$device 2> /dev/null`
	if [ "$fs" = "ufs" ] ; then
		mount -o ro /devices/$device $tmp 2> /dev/null
		if [ $? != 0 ] ; then
			continue
		fi

		if [ -f $tmp/etc/release ] ; then
			if [ ! -f $tmp/platform/i86pc/multiboot ] &&
			    [ -f $tmp/boot/solaris/boot.bin ] ; then
				release=`head -1 $tmp/etc/release | \
				    sed "s/^[	 ]*//"`
				entry $root $part "$release" False
			fi
		fi
		umount $tmp > /dev/null 2>&1
	fi

	rmdir $tmp
}

# process a diag (usually DOS based) partition
#
handle_diag()
{
	root=$3
	part=$4
	entry $root $part "Diagnostic Partition" False
}

# generate a comment for an unsupported partition
#
unhandled()
{
	disk=$1
	partition=$2
	root=$3
	part=$4
	id=$5

	printf "\n# Unknown partition of type $id found "
	printf "on $disk partition: ${partition}. It "
	printf "maps to (0-based) bootable disk ${root}, "
        printf "(0-based) partition ${part}."
}


# begin main
#

if [ ! -f /var/run/solaris_grubdisk.map ] && 
    [ -x /boot/solaris/bin/create_diskmap ] ; then
	/boot/solaris/bin/create_diskmap
fi

for disk in /dev/rdsk/*p0 ; do
	typeset -i partition=1
	typeset -i gpart
	typeset -i gdisk

	for id in `fdisk -W - $disk 2> /dev/null | grep -v "^*" | \
	    awk '{ print $1 }'` ; do
		dev=`echo $disk | sed s#/rdsk/#/dsk/# | sed s/p0$//`
		rdev=`echo $disk | sed s/p0$/p$partition/`
		(( gpart=partition-1 ))
		ctd=`basename $disk | sed s/p0$//`
		grep $ctd /var/run/solaris_grubdisk.map > /dev/null 2> /dev/null
		if [ $? = 0 ] ; then
			gdisk=`grep $ctd /var/run/solaris_grubdisk.map | \
			    awk '{ print $1 }'`
		else
			gdisk=0
		fi
		# presence of /.cdrom/.liveusb indicates install from USB disk
		# for USB installation the GRUB map will list the USB disk
		# as the first device, which is very likely not the normal order
		# reset the normal order by decrementing the disk index
		if [[ -e "/.cdrom/.liveusb" ]] && (( gdisk > 0 )); then
			# identify windows partitions and decrement
			# disk index for USB installations
			case $id in
				7|11|12|18|23|222)
					root="$((gdisk-1))"
					;;
				*) root="${gdisk}"
				   ;;
			esac
		else
			root="${gdisk}"
		fi

		case $id in
			0)	;; # unused
			7)	handle_ifs $dev $rdev $root $gpart ;;
			11)	handle_fat $dev $rdev $root $gpart ;;
			12)	handle_fat $dev $rdev $root $gpart ;;
			18)	handle_diag $dev $rdev $root $gpart ;;
			23)	handle_ifs $dev $rdev $root $gpart ;;
			28)	;; # hidden FAT32 must ignore
			130)	handle_solaris $dev $rdev $root $gpart ;;
			190)	handle_x86boot $dev $rdev $root $gpart ;;
			191)	handle_solaris $dev $rdev $root $gpart ;;
			222)	handle_diag $dev $rdev $root $gpart ;;
			238)	;; # Protective GPT - ignore
			*)	unhandled $disk $partition $root $gpart $id ;;
		esac

		partition=$partition+1
	done
done
exit 0

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
# Common functions and definitions used by installation media services

# compressed archives
SOLARIS_ZLIB="solaris.zlib"
SOLARISMISC_ZLIB="solarismisc.zlib"

MOUNT=/sbin/mount

#
# is_livecd - true if this is a live CD environment
#
is_livecd() {
	[ -f /.livecd ]
}

# is_liveusb - true if this is a live USB environment
#
is_liveusb() {
	[ -f /.cdrom/.liveusb ]
}

# is_autoinstall - true if this is an autoinstall environment
#
is_autoinstall() {
	[ -f /.autoinstall ]
}

# is_textinstall - true if this is a textinstall environment
#
is_textinstall() {
	[ -f /.textinstall ]
}

# Set up the builtin commands.
builtin cd

#
# The platform profile must be created and applied at boot time, based
# on the architecture of the machine
#
apply_platform_profile()
{
	if [ -f /lib/svc/manifest/system/early-manifest-import.xml ]; then
		SMF_PROF_DIR=/etc/svc/profile
	else
		SMF_PROF_DIR=/var/svc/profile
	fi
	if [ ! -f ${SMF_PROF_DIR}/platform.xml ]; then
		this_karch=`uname -m`
		this_plat=`uname -i`

		if [ -f ${SMF_PROF_DIR}/platform_$this_plat.xml ]; then
			platform_profile=platform_$this_plat.xml
		elif [ -f ${SMF_PROF_DIR}/platform_$this_karch.xml ]; then
			platform_profile=platform_$this_karch.xml
		else
			platform_profile=platform_none.xml
		fi
	fi

        (cd ${SMF_PROF_DIR}; ln -s $platform_profile platform.xml)

	/usr/sbin/svccfg apply ${SMF_PROF_DIR}/platform.xml
	if [ $? -ne 0 ]; then
		echo "Failed to apply ${SMF_PROF_DIR}/platform.xml" > /dev/msglog
	fi

}

# Make user home directories writable by mounting on tmpfs and copying initial
# contents from media directory
setup_user_dirs()
{
	# Mount /root home directory onto swap
	mountfs -O /root tmpfs - swap || exit $SMF_EXIT_ERR_FATAL
	cd /.cdrom/root
	find . -print | cpio -pmud /root

	# Mount /jack home directory onto swap
	mountfs -O /jack tmpfs - swap || exit $SMF_EXIT_ERR_FATAL
	cd /.cdrom/jack
	find . -print | cpio -pmud /jack
}

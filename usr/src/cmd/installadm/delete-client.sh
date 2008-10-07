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

# Description:
#       Deletes an existing client's information, which was set up using
#       the installadm create-client command, in the non-default case.


# make sure path is ok
PATH=/usr/bin:/usr/etc:/usr/sbin:${PATH}

# tr may fail in some locales. Hence set the env LANG=C and LC_ALL=C
TR='env LC_ALL=C LANG=C /bin/tr'

# Constants
#
SIGHUP=1
SIGINT=2
SIGQUIT=3
SIGTERM=15

DHCP_CLIENT_ID=""
Bootdir=/tftpboot

#
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
	echo "Usage: $0 <macaddr>"
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
myname=$0
ID=`id`
USER=`expr "${ID}" : 'uid=\([^(]*\).*'`

unset MAC_ADDR

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


if [ $# -gt 2 ]; then
	usage ;
fi

QUIET=0

#
# Parse the command line options.
#
while [ "$1"x != "x" ]; do
    case $1 in

	# The -q option is passed if called from create-client. This
	# is so that the user is not told to remove entries from the 
	# dhcp server, since create-client attempts to add them again.

	-q) QUIET=1
	shift 1
	;;

  [a-zA-Z0-9]*) # one trailing argument
        MAC_ADDR="$1";

        if [ "X$MAC_ADDR" = "X" ]; then
            usage ;
        fi

        MAC_ADDR=`expr $MAC_ADDR : '\([0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\:[0-9a-fA-F][0-9a-fA-F]*\)'`

        if [ ! "${MAC_ADDR}" ] ; then
                echo "mal-formed MAC address: $2"
                exit 1
        fi
        shift 1
        ;;
    *)	# all else is spurious
        usage ;
        ;;
    esac
done


if [ -z "${MAC_ADDR}" ]; then
	echo "${myname}: Missing one or more required options."
	usage
fi 


# Convert the Ethernet address to DHCP "default client-ID" form:
#    uppercase hex, preceded by the hardware
#    address type ("01" for ethernet)
#
if [ "X${MAC_ADDR}" != "X" ] ; then
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
fi


# See if there's a cleanup file corresponding to the passed 
# ethernet address
#
if [ "X${DHCP_CLIENT_ID}" != "X" -a \
     -f "${Bootdir}/rm.${DHCP_CLIENT_ID}" ] ; then
        CLEAN=${Bootdir}/rm.${DHCP_CLIENT_ID}
fi

# If a cleanup file exists, source it
#
if [ -n "${CLEAN}" -a -f "${CLEAN}" ]; then
	. ${CLEAN}
fi

rm -f ${CLEAN}


if [ $QUIET -eq 0 ] ; then
	echo "To disable ${MAC_ADDR} in the DHCP server,"
	echo "  remove the entry with Client ID ${DHCP_CLIENT_ID}"
fi

exit 0

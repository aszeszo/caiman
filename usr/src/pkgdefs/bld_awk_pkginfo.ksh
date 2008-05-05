#!/usr/bin/ksh -p
#
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
#
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#

#
# Simple script which builds the awk_pkginfo awk script.  This awk script
# is used to convert the pkginfo.tmpl files into pkginfo files
# for the build.
#


usage()
{
   echo "usage: bld_awk_pkginfo -p <prodver> -m <mach> -v <pkgver> -o <awk_script>"
}
#
# Awk strings
#
VERSION="VERSION\="
PRODVERS="^SUNW_PRODVERS\="
ARCH='ARCH=\"ISA\"'
COMMON_VERSION="COMMON_VERSION"


#
# parse command line
#
mach=""
prodver=""
awk_script=""
common_version=""

while getopts o:p:m:v: c
do
   case $c in
   o)
      awk_script=$OPTARG
      ;;
   m)
      mach=$OPTARG
      ;;
   p)
      prodver=$OPTARG
      ;;
   v)
      common_version=$OPTARG
      ;;
   \?)
      usage
      exit 1
      ;;
   esac
done

if [[ ( -z $prodver ) || ( -z $mach ) || ( -z $awk_script ) || ( -z $common_version ) ]]
then
   usage
   exit 1
fi

if [[ -f $awk_script ]]
then
	rm -f $awk_script
fi

#
# Build REV= field based on date
#
rev=$(date "+%Y.%m.%d.%H.%M")

#
# Build awk script which will process all the
# pkginfo.tmpl files.
#
rm -f $awk_script
cat << EOF > $awk_script
/$VERSION/ {
      sub(/COMMON_VERSION/,"$common_version")
      sub(/\=[^=]*$/,"=$rev\"")
      print
      next
   }
/$PRODVERS/ { 
      printf "SUNW_PRODVERS=\"%s\"\n", "$prodver" 
      next
   }
/$ARCH/ {
      printf "ARCH=\"%s\"\n", "$mach"
      next
   }
{ print }
EOF


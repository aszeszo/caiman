#!/bin/ksh -p
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
#ident	"@(#)opensolaris_build_slim.sh	1.1	07/11/13 SMI"
#
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

#

#
# OpenSolaris build script to make it easier for the OpenSolaris
# external community to build the tools w/o the rest of the Admin/Install
# gate
#

if [ -z $ROOT ]; then
	echo "You must first source your environment file before building."
	exit 1
fi

# setup the proto area, creating the necessary directory tree
rm -rf $ROOT
$SPRO_ROOT/bin/dmake -k -m serial proto

# create links to snadm libraries in proto area
ln -s /usr/snadm/lib/libadmutil.so $ROOT/usr/snadm/lib 
ln -s /usr/snadm/lib/libadmldb.so $ROOT/usr/snadm/lib 

# Build and install the individual components
$SPRO_ROOT/bin/dmake -e -k -m parallel install


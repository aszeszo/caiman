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

#
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)opensolaris_build.sh	1.4	07/08/15 SMI"
#

#
# OpenSolaris build script to make it easier for the OpenSolaris
# external community to build the tools w/o the rest of the Admin/Install
# gate
#

if [ -z $ROOT ]; then
	echo "You must first setup and source ENV before building."
	exit 1
fi

# setup the proto area, creating the necessary directory tree
dmake -k -m serial proto >/dev/null 2>&1

# remove any existing links for libraries which we don't
# deliver to opensolaris but need to link against which will
# be recreated to point to the proper locations.
rm $ROOT/usr/snadm/lib/libspmi*.so

# create links to snadm libspmi* libraries in proto area
ln -s /usr/snadm/lib/libspmi*.so $ROOT/usr/snadm/lib 

# then go build and install the individual components
(cd tools && dmake -m serial all && dmake -m serial install)
(cd lib/libgendb && dmake -m serial all && dmake -m serial install)
(cd lib/libpkg && dmake -m serial all && dmake -m serial install)
(cd lib/libpkgdb && dmake -m serial all && dmake -m serial install)
(cd lib/libinst && dmake -m serial all && dmake -m serial install)
(cd cmd/makeuuid && dmake -m serial all && dmake -m serial install)
(cd cmd/pkgcmds && dmake -m serial all && dmake -m serial install)
(cd cmd/webstart/wsreg && dmake -m serial all && dmake -m serial install)

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
dmake -k -m serial proto >/dev/null 2>&1

# remove any existing links for libraries which we don't
# deliver to opensolaris but need to link against which will
# be recreated to point to the proper locations.
rm $ROOT/usr/snadm/lib/libspmi*.so
rm $ROOT/usr/snadm/lib/libadmutil.so
rm $ROOT/usr/snadm/lib/libadmldb.so

# create links to snadm libspmi* libraries in proto area
ln -s /usr/snadm/lib/libspmi*.so $ROOT/usr/snadm/lib 
ln -s /usr/snadm/lib/libadmutil.so $ROOT/usr/snadm/lib 
ln -s /usr/snadm/lib/libadmldb.so $ROOT/usr/snadm/lib 

# Beware of changing the order of the directories below.
# There are inter-dependancies between the libraries.

# Build and install the individual components
(cd tools && dmake -m serial all && dmake -m serial install)
(cd lib/libpkgdb && dmake -m serial all && dmake -m serial install)
(cd lib/libgendb && dmake -m serial all && dmake -m serial install)
(cd lib/libpkg && dmake -m serial all && dmake -m serial install)
(cd lib/libspmiapp && dmake -m serial all && dmake -m serial install)
(cd lib/libspmicommon && dmake -m serial all && dmake -m serial install)
(cd lib/libspmitty && dmake -m serial all && dmake -m serial install)
(cd lib/libspmixm && dmake -m serial all && dmake -m serial install)
(cd lib/libspmizones && dmake -m serial all && dmake -m serial install)
(cd lib/libspmisoft && dmake -m serial all && dmake -m serial install)
(cd lib/libspmistore && dmake -m serial all && dmake -m serial install)
(cd lib/libspmisvc && dmake -m serial all && dmake -m serial install)
(cd lib/liblogsvc && dmake -m serial all && dmake -m serial install)
(cd lib/libtd && dmake -m serial all && dmake -m serial install)
(cd lib/libti && dmake -m serial all && dmake -m serial install)
(cd lib/libtransfer && dmake -m serial all && dmake -m serial install)
(cd lib/liborchestrator && dmake -m serial all && dmake -m serial install)
(cd lib/libinst && dmake -m serial all && dmake -m serial install)
(cd cmd/makeuuid && dmake -m serial all && dmake -m serial install)
(cd cmd/pkgcmds && dmake -m serial all && dmake -m serial install)
(cd cmd/webstart/wsreg && dmake -m serial all && dmake -m serial install)
(cd cmd/inst/gui-install && dmake -m serial all && dmake -m serial install)

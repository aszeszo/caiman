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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include $(SRC)/Makefile.master

SUBDIRS=	libbe \
		libbe_pymod \
		libgendb \
		liblogsvc \
		liblogsvc_pymod \
		liborchestrator	\
		libict	\
		libpkg \
		libpkgdb \
		libspmiapp \
		libspmicommon \
		libspmisoft \
		libspmistore \
		libspmisvc \
		libspmitty \
		libinstzones \
		libtd \
		libti \
		libti_pymod \
		libtransfer \
		libtransfer_pymod \
		libict_pymod \
		install_utils

HDRSUBDIRS=	libadmldb libadmutil

ADMINLIBRARIES=	libadmldb.so libadmutil.so
ROOTADMINLIBLINKS=	$(ADMINLIBRARIES:%=$(ROOTADMINLIB)/%)

.PARALLEL:	$(SUBDIRS)

ROOTINC=	$(ROOT)/usr/include
ROOTINCADMIN=	$(ROOTINC)/admin

all:=		TARGET= all
check:=		TARGET= check
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install
install_h:=	TARGET= install_h
lint:=		TARGET= lint

.KEEP_STATE:

all check clean clobber lint: $(SUBDIRS)

install: $(ROOTADMINLIBLINKS) .WAIT $(SUBDIRS)

headers: install_h

install_h:	$(ROOTINCADMIN) $(HDRSUBDIRS) $(SUBDIRS)

# library dependencies
libbe:			libinstzones
libbe_pymod:		libbe
liblogsvc_pymod:	liblogsvc
libtransfer_pymod:	libtransfer liblogsvc
libti_pymod:		libti
libgendb:		libpkgdb
liborchestrator:	libtd liblogsvc libti libtransfer_pymod libbe libict
libict:			liblogsvc libti libtransfer_pymod libbe
libpkg:			libgendb
libtd:			libinstzones liblogsvc libbe
libti:			liblogsvc libbe
libtransfer:		liblogsvc
libict_pymod:		liblogsvc


$(ROOTADMINLIBLINKS):
	$(RM) $@; $(SYMLINK) $(ADMINLIB)/$(@F) $@

$(ROOTINCADMIN):
	$(INS.dir)

$(SUBDIRS) $(HDRSUBDIRS): FRC
	cd $@; pwd; $(MAKE) $(TARGET)

FRC:

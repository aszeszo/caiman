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
include $(SRC)/cmd/slim-install/Targetdirs
include $(SRC)/cmd/slim-install/Makefile.slim

INSTALL_FINISH=	install-finish

ROOTSBININSTALL_FINISH=	$(INSTALL_FINISH:%=$(ROOTSBIN)/%)

SUBDIRS=	svc listusb listcd user/jack

.PARALLEL:

all:=           TARGET= all
check:=         TARGET= check
clean:=         TARGET= clean
clobber:=       TARGET= clobber
cstyle:=        TARGET= cstyle
install:=       TARGET= install
install_h:=     TARGET= install_h
lint:=          TARGET= lint
lintlib:=       TARGET= lintlib
patch:=         TARGET= install

.KEEP_STATE:

all install: headers .WAIT $(ROOTSBININSTALL_FINISH) .WAIT $(SUBDIRS)

check clean clobber cstyle lint lintlib patch: $(SUBDIRS)

headers: $(ROOTDIRS) .WAIT $(ROOTSBIN) .WAIT $(SUBDIRS)

install_h:

$(ROOTSBIN)/%: %
	$(INS.exec)

$(SUBDIRS): FRC
	cd $@; pwd; $(MAKE) $(TARGET)

$(ROOTDIRS):
	$(INS.dir)

clobber clean:

FRC:

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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.cmd

HELPFILES= \
	FINISH_PANEL.txt \
	INSTALL_DISK_PANEL.txt \
	INSTALL_FAILURE_PANEL.txt \
	INSTALL_LANGUAGE_PANEL.txt \
	INSTALL_PROGRESS_PANEL.txt \
	INSTALL_REVIEW_PANEL.txt \
	INSTALL_TIMEZONE_PANEL.txt \
	INSTALL_USERS_PANEL.txt \
	WELCOME_PANEL.txt

SUBDIRS=	C \
	de_DE.UTF-8 \
	es_ES.UTF-8 \
	fr_FR.UTF-8 \
	it_IT.UTF-8 \
	ja_JP.UTF-8 \
	ko_KR.UTF-8 \
	pt_BR.UTF-8 \
	zh_CN.UTF-8 \
	zh_TW.UTF-8


SCHEMAFILES= solaris-gui-install.schemas

ROOTHELPFILES= $(HELPFILES:%=$(ROOTGUIINST)/help/C/%)

ROOTIMGURLMAP= $(IMGURLMAP:%=$(ROOTGUIINST)/installmessages/%)
ROOTPNGFILES= $(PNGFILES:%=$(ROOTGUIINST)/installmessages/%)

ROOTSCHEMAFILES= $(SCHEMAFILES:%=$(ROOT)/etc/gconf/schemas/%)

all: $(SUBDIRS)

install: all $(ROOTHELPFILES) $(SUBDIRS) $(ROOTSCHEMAFILES)

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

install_h: 

$(ROOTUSRSHARE)/gui-install/help/C/%: %
	$(INS.file)

$(ROOTUSRSHARE)/gui-install/installmessages/%: %
	$(INS.file)

$(ROOT)/etc/gconf/schemas/%: %
	$(INS.file)

clobber clean:

include ../../Makefile.targ

#
##
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

include ../../Makefile.lib

all:=          TARGET= all
clean:=        TARGET= clean
clobber:=      TARGET= clobber
install:=      TARGET= install


DTD_FILES_SRC =	ai.dtd.src \
	dc.dtd.src 	\
	media-transfer.dtd.src

DTD_FILES_GEN =	ai.dtd \
	dc.dtd 	\
	media-transfer.dtd

DTD_FILES =	$(DTD_FILES_GEN) \
	boot_mods.dtd \
	configuration.dtd \
	execution.dtd \
	software.dtd \
	target.dtd

DTD_FILES_VER =	ai.dtd.$(DTD_VERSION_AI) \
	boot_mods.dtd.$(DTD_VERSION_BOOT_MODS) \
	dc.dtd.$(DTD_VERSION_DC) \
	configuration.dtd.$(DTD_VERSION_CONFIGURATION) \
	execution.dtd.$(DTD_VERSION_EXECUTION) \
	software.dtd.$(DTD_VERSION_SOFTWARE) \
	target.dtd.$(DTD_VERSION_TARGET) \
	media-transfer.dtd.$(DTD_VERSION_MEDIA_TRANSFER)

CLOBBERFILES = $(DTD_FILES_GEN) $(DTD_FILES_VER)
CLEANFILES = $(CLOBBERFILES)

ROOT_DTD_FILES=	$(DTD_FILES_VER:%=$(ROOTUSRSHAREINSTALL)/%)

all: $(DTD_FILES_VER)

install_h:

install: .WAIT \
    $(ROOTUSRSHAREINSTALL) \
	$(ROOT_DTD_FILES)

ai.dtd.$(DTD_VERSION_AI): ai.dtd
	$(RM) -f $@; $(CP) -p $? $@

boot_mods.dtd.$(DTD_VERSION_BOOT_MODS):  boot_mods.dtd
	$(RM) -f $@; $(CP) -p $? $@

dc.dtd.$(DTD_VERSION_DC):  dc.dtd
	$(RM) -f $@; $(CP) -p $? $@

configuration.dtd.$(DTD_VERSION_CONFIGURATION): configuration.dtd
	$(RM) -f $@; $(CP) -p $? $@

execution.dtd.$(DTD_VERSION_EXECUTION):  execution.dtd
	$(RM) -f $@; $(CP) -p $? $@

software.dtd.$(DTD_VERSION_SOFTWARE):  software.dtd
	$(RM) -f $@; $(CP) -p $? $@

target.dtd.$(DTD_VERSION_TARGET):  target.dtd
	$(RM) -f $@; $(CP) -p $? $@

media-transfer.dtd.$(DTD_VERSION_MEDIA_TRANSFER): media-transfer.dtd
	$(RM) -f $@; $(CP) -p $? $@

include ../../Makefile.targ

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.cmd

all:=          TARGET= all
clean:=        TARGET= clean
clobber:=      TARGET= clobber
install:=      TARGET= install

MANIFEST_FILES_SRC=	dc_ai_sparc.xml.src \
	dc_ai_x86.xml.src \
	dc_livecd.xml.src \
	dc_text_sparc.xml.src \
	dc_text_x86.xml.src

MANIFEST_FILES_GEN=	dc_ai_sparc.xml \
	dc_ai_x86.xml \
	dc_livecd.xml \
	dc_text_sparc.xml \
	dc_text_x86.xml

MANIFEST_FILES=	$(MANIFEST_FILES_GEN) \
	boot_archive_contents_x86.xml \
	boot_archive_contents_sparc.xml \
	lang_facets.xml

ROOT_MANIFEST_FILES=	$(MANIFEST_FILES:%=$(ROOTDC)/%)

CLEANFILES= $(MANIFEST_FILES_GEN)
CLOBBERFILES= $(CLEANFILES)

all: $(MANIFEST_FILES_GEN)

install: all .WAIT $(ROOTDC) \
	$(ROOT_MANIFEST_FILES)

$(MANIFEST_FILES_GEN):

clean:
	$(RM) $(CLEANFILES)

include ../../Makefile.targ

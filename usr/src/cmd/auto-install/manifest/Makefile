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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
include $(SRC)/cmd/Makefile.cmd

MANIFEST_FILES_SRC =	ai_manifest.xml.src \
			default.xml.src \
			zone_default.xml.src

MANIFEST_FILES_GEN =	ai_manifest.xml \
			default.xml \
			zone_default.xml

MANIFEST_FILES =	$(MANIFEST_FILES_GEN)

ROOTMANIFESTS= $(MANIFEST_FILES:%=$(ROOTAUTOINSTMANIFEST)/%)

CLEANFILES = $(MANIFEST_FILES_GEN)
CLOBERFILES = $(CLEANFILES)

all: $(MANIFEST_FILES_GEN)

install: all .WAIT \
	$(ROOTMANIFESTS)

$(MANIFEST_FILES_GEN):

clean:
	$(RM) $(CLEANFILES)


include $(SRC)/cmd/Makefile.targ

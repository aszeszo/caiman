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

MANIFEST_FILES_SRC = \
		manifest_auto_reboot_false.xml.src \
		manifest_auto_reboot_invalid.xml.src \
		manifest_auto_reboot_not_set.xml.src \
		manifest_auto_reboot_true.xml.src

MANIFEST_FILES_GEN = \
		manifest_auto_reboot_false.xml \
		manifest_auto_reboot_invalid.xml \
		manifest_auto_reboot_not_set.xml \
		manifest_auto_reboot_true.xml

MANIFEST_FILES =	$(MANIFEST_FILES_GEN)

CLEANFILES = $(MANIFEST_FILES_GEN)
CLOBERFILES = $(CLEANFILES)

all: $(MANIFEST_FILES_GEN)

install: all

$(MANIFEST_FILES_GEN):

clean:
	$(RM) $(CLEANFILES)


include $(SRC)/cmd/Makefile.targ

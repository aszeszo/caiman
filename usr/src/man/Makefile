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

# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

include $(SRC)/Makefile.master

MANPAGES1M = aimanifest.1m distro_const.1m installadm.1m js2ai.1m
MANPAGES4 = dc_manifest.4

FILEMODE = 0444

ROOTMANPAGES1M = $(MANPAGES1M:%=$(ROOTMAN1M)/%)
ROOTMANPAGES4 = $(MANPAGES4:%=$(ROOTMAN4)/%)

all :=		TARGET = all
clean :=	TARGET = clean
clobber :=	TARGET = clobber
install :=	TARGET = install

all:	$(MANPAGES1M) $(MANPAGES4)

headers:

clean:
	$(RM) $(ROOTMANPAGES1M) $(ROOTMANPAGES4)

clobber: clean

install: all $(ROOTMANPAGES1M) $(ROOTMANPAGES4)

$(ROOTMAN1M)/%: %
	$(INS.file)

$(ROOTMAN4)/%: %
	$(INS.file)

$(ROOTMAN1M):
	$(INS.dir)

$(ROOTMAN4):
	$(INS.dir)

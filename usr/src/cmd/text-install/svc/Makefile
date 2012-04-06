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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

MSG_DOMAIN=     solaris_install_text_menu

include $(SRC)/cmd/Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

PROG_KSH=	text-mode-menu.ksh
PROG=		$(PROG_KSH:%.ksh=%)

ROOTPROGS=      $(PROG:%=$(ROOTUSRSBIN)/%)
ROOTMSGS=	$(POFILE:%=$(ROOTUSRSHAREMSGS)/%)

SYSMANIFESTSRC= text-mode-menu.xml
SYSMANIFESTS= $(SYSMANIFESTSRC:%=$(ROOTMANSYS)/%)

.KEEP_STATE:

all:	$(PROG) $(POFILE)

clean:
	rm -f $(ROOTPROGS) $(ROOTMSGS) $(SYSMANIFESTS) $(POFILE)

clobber: clean

install: all .WAIT $(ROOTPROGS) $(ROOTMSGS) \
	 $(ROOTMANSYS) $(ROOTLIBSVCMETHOD) $(SYSMANIFESTS)

$(PROG):	$(PROG_KSH)
	cp $(PROG_KSH) $(PROG)

msgs:	$(POFILE)

MSGFILES =	text-mode-menu.ksh

FRC:

include $(SRC)/cmd/Makefile.targ

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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#

include $(SRC)/cmd/Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

PROG_KSH=	text-mode-menu.ksh
PROG=		$(PROG_KSH:%.ksh=%)

MSG_DOMAIN=	SUNW_INSTALL_TEXT_MENU
POFILE=		$(MSG_DOMAIN).po

ROOTPROGS=      $(PROG:%=$(ROOTUSRSBIN)/%)
ROOTMSGS=	$(POFILE:%=$(ROOTUSRLIBMSGS)/%)

SYSMANIFESTSRC= text-mode-menu.xml
SYSMANIFESTS= $(SYSMANIFESTSRC:%=$(ROOTMANSYS)/%)

.KEEP_STATE:

all:	$(PROG) $(POFILE)

clean:
	rm -f $(ROOTPROGS) $(ROOTMSGS) $(SYSMANIFESTS)

clobber: clean

install: all .WAIT $(ROOTPROGS) $(ROOTMSGS) \
	 $(ROOTMANSYS) $(ROOTLIBSVCMETHOD) $(SYSMANIFESTS)

$(PROG):	$(PROG_KSH)
	cp $(PROG_KSH) $(PROG)

msgs:	$(POFILE)

$(POFILE):	$(PROG_KSH)
	@echo "Making messages file $(POFILE)"
	@$(ROOTADMINBIN)/xgetsh -d $(MSG_DOMAIN) $(PROG_KSH)

FRC:

include $(SRC)/cmd/Makefile.targ
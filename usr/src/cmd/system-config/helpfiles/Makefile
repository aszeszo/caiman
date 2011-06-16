
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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

HELP_FILES=	date_time.txt \
		dns_server.txt \
		dns_search.txt \
		domain.txt \
		ldap_profile.txt \
		ldap_proxy.txt \
		name_service.txt \
		network_manual.txt \
		network.txt \
		nis.txt \
		summary.txt \
		timezone.txt \
		users.txt \
		welcome.txt

ROOTHELP_FILES=	$(HELP_FILES:%=$(ROOTUSRSHARESCHELPC)/%)

$(ROOTUSRSHARESCHELPC):
	$(INS.dir)

all: $(ROOTUSRSHARESCHELPC)

clean:	
	rm -rf $(ROOTUSRSHARESCHELPC)

clobber: clean

install: all .WAIT $(ROOTHELP_FILES)

include ../../Makefile.targ

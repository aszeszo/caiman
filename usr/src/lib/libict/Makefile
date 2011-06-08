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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

LIBRARY	= libict.a
VERS	= .1

OBJECTS	= ict.o
PRIVHDRS = ict_private.h
EXPHDRS = ict_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. \
		   -I../liblogsvc \
		   -I../libti \
		   -I../liborchestrator \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) \
		-lnvpair \
		-llogsvc -ltransfer -lti -lzfs

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -uaxm ${CPPFLAGS}

TEST_PROGS	= ict_test
ROOT_TEST_PROGS	= $(TEST_PROGS:%=$(ROOTOPTINSTALLTESTBIN)/%)
CLEANFILES	= $(TEST_PROGS) ict_test.o

.KEEP_STATE:

all: $(HDRS) .WAIT dynamic $(TEST_PROGS)
	@true

#Install Completion Tasks test program
ict_test:	.WAIT dynamic ict_test.o
	${LINK.c} -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-o ict_test ict_test.o -Lpics/${ARCH} -L$(ROOTADMINLIB) \
		-L$(ROOTUSRLIB) -lict -llogsvc -lnvpair

dynamic: $(DYNLIB) .WAIT $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK) $(ROOT_TEST_PROGS)

install_test:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK)

install_h:	$(ROOTUSRINCLEXP)

lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	$(CSTYLE) $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

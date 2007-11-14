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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.1	07/10/03 SMI"
#
# Target Instantiation software library makefile
#

LIBRARY	= libti.a
VERS	= .1

OBJECTS	= \
	ti_mg.o \
	ti_dm.o \
	ti_zfm.o

PRIVHDRS = \
	ti_dm.h
#	ti_lib.h

EXPHDRS = \
	ti_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. \
		   -I../liblogsvc \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-ladm -lnvpair -llogsvc

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -uaxm ${CPPFLAGS}

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic
	@true

# Target Instantiation test program
titst:	.WAIT dynamic test_ti.o
	${LINK.c} -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-o test_ti test_ti.o -L$(ROOTADMINLIB) \
		-Lpics/${ARCH} -lti -llogsvc -lnvpair

static: $(LIBS)

dynamic: $(DYNLIB) .WAIT $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK)

install_test:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK)

install_h:	$(ROOTUSRINCLEXP)

lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	$(CSTYLE) $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

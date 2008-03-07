#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.1	07/08/03 SMI"
#
# Target Discovery software library makefile
#

LIBRARY	= libtd.a
VERS	= .1

OBJECTS	= \
	td_mg.o \
	td_version.o \
	td_mountall.o \
	td_util.o \
	td_dd.o \
	td_dd_svm.o \
	test_td.o

#	td_misc.o \
#	td_boolean.o \

PRIVHDRS = \
	td_lib.h \
	td_version.h \
	td_dd.h
EXPHDRS = \
	td_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. -I../libspmizones \
		   -I../libspmisvc \
		   -I../liborchestrator \
		   -I../liblogsvc \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lwanboot -lcontract -ldiskmgt -lnvpair -lspmizones -lzonecfg \
		-lspmicommon -llogsvc

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -uaxm ${CPPFLAGS}

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic
	@true

#Target Discovery Manager test program
mgtst:	.WAIT static tdmgtst.o
	${LINK.c} -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-o tdmgtst tdmgtst.o \
		-Lobjs/${ARCH} -ldiskmgt -lnvpair -ldevinfo \
		-L${ROOT}/usr/snadm/lib \
		-ladm -lzonecfg -lcontract -lwanboot \
		-lspmiapp -lspmisvc -lspmistore \
		-lspmisoft -lspmicommon -lpkg \
		-lorchestrator \
		-llogsvc -lspmizones \
		-Bstatic \
		-ltd \
		-Bdynamic

#		-L../liborchestrator/objs/${ARCH} -lorchestrator \
#
#Target Discovery test program
tdtst:	.WAIT dynamic test_td.o
	${LINK.c} -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-o test_td test_td.o -L$(ROOTADMINLIB) \
		-Lpics/${ARCH} -ltd -llogsvc -lnvpair -lspmicommon

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

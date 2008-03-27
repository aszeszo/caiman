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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# Transfer module Makefile
#

LIBRARY	= libtransfer.a
VERS	= .1

OBJECTS	= \
	transfermod.o

PYMODS = \
	transfer_mod.py

TEST_SRCS = \
	transfermod.c

TEST_BIN = \
	transfertest

PRIVHDRS =

EXPHDRS = \
	transfermod.h

CLEANFILES = $(TEST_BIN)

HDRS		= $(EXPHDRS) $(PRIVHDRS)


PYCMODS = $(PYMODS:%.py=%.pyc)

%.pyc: %.py
	python -m compileall -l $(@D)

include ../Makefile.lib

INCLUDE		 = \
		   -I$(ROOTINCADMIN) -I/usr/include/python2.4 -I$(SRC)/lib/liblogsvc

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}S
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lnvpair -lpython2.4 -llogsvc
TEST_CFLAGS	= -D__TM_TEST__ $(INCLUDE)

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -uaxm ${CPPFLAGS}

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic
	@true

# Target Instantiation test program
$(TEST_BIN):	.WAIT dynamic 
	${LINK.c} -o $(TEST_BIN) $(TEST_CFLAGS) $(TEST_SRCS) \
		-L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lnvpair -lpython2.4 -llogsvc

test: $(TEST_BIN)

static: $(LIBS)

dynamic: $(DYNLIB) $(PYCMODS) .WAIT $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK) $(ROOTPYTHONVENDORMODS)

install_test:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK)

install_h:	$(ROOTUSRINCLEXP)

lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	$(CSTYLE) $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

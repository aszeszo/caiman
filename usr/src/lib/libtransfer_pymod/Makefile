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

#
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

LIBRARY		= libtransfer.a
VERS	= .1

OBJECTS		= libtransfer.o

TEST_SRCS = \
	libtransfer.c

TEST_BIN = transfertest

CLEANFILE = $(TEST_BIN)

include ../Makefile.lib

INCLUDE		= -I/usr/include/python2.4 -I../libtransfer -I$(SRC)/lib/liblogsvc

CPPFLAGS	+= ${INCLUDE} $(CPPFLAGS.master) -D_FILE_OFFSET_BITS=64
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS} 
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lnvpair -lpython2.4 -llogsvc
TEST_CFLAGS     = -D__TM_TEST__ $(INCLUDE)

static:	

dynamic:	$(CPYTHONLIB)

all:		dynamic

install_h:

install:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK)

lint:		lint_SRCS

$(TEST_BIN): 	.WAIT dynamic
	${LINK.c} -o $(TEST_BIN) $(TEST_CFLAGS) $(TEST_SRCS) \
		-L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lnvpair -lpython2.4 -llogsvc

test: $(TEST_BIN)
include ../Makefile.targ

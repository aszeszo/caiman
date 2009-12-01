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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# Target Instantiation software library makefile
#

LIBRARY	= libti.a
VERS	= .1

TEST_PROGS	= test_ti test_ti_static

OBJECTS	= \
	ti_mg.o \
	ti_bem.o \
	ti_dm.o \
	ti_zfm.o \
	ti_dcm.o

PRIVHDRS = \
	ti_dm.h \
	ti_zfm.h \
	ti_dcm.h

EXPHDRS = \
	ti_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. \
		   -I../liblogsvc \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= $(INCLUDE) -D$(ARCH)
CFLAGS		+= $(DEBUG_CFLAGS) -Xa $(CPPFLAGS)
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) \
		-ladm -lnvpair -llogsvc -lbe

ROOT_TEST_PROGS	= $(TEST_PROGS:%=$(ROOTOPTINSTALLTESTBIN)/%)
CLEANFILES	= $(TEST_PROGS)

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic $(TEST_PROGS)
	@true

# Target Instantiation test program
test_ti:	dynamic test_ti.o
	$(LINK.c) -o test_ti test_ti.o \
		-R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTADMINLIB) -L$(ROOTUSRLIB) -Lpics/$(ARCH) \
		-lti -llogsvc -lnvpair

# statically-built Target Instantiation test program
test_ti_static:	static test_ti.o
	$(LINK.c) -o test_ti_static test_ti.o \
		-L$(ROOTADMINLIB) -L$(ROOTUSRLIB) -Lobjs/$(ARCH) \
		-Bstatic \
		-lti -lbe -llogsvc -linstzones \
		-Bdynamic \
		-ladm -lnvpair -lgen -lzfs -lpython2.6 -luuid \
		-lzonecfg -lcontract

static: $(LIBS)

dynamic: $(DYNLIB) .WAIT $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOT_TEST_PROGS) $(ROOTADMINLIBDYNLIBLINK)

install_h:	$(ROOTUSRINCLEXP)

lint:  $(SRCS) $(HDRS)
	$(LINT.c) $(SRCS)

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	$(CSTYLE) $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

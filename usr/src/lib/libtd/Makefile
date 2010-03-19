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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# Target Discovery software library makefile
#

LIBRARY	= libtd.a
VERS	= .1

TEST_PROGS	= test_td test_td_static tdmgtst tdmgtst_static

OBJECTS	= \
	td_mg.o \
	td_be.o \
	td_version.o \
	td_mountall.o \
	td_util.o \
	td_dd.o \
	td_dd_svm.o \
	td_iscsi.o \
	test_td.o

PRIVHDRS = \
	td_lib.h \
	td_version.h \
	td_dd.h
EXPHDRS = \
	td_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. \
		   -I../liborchestrator \
		   -I../liblogsvc \
		   -I../libbe \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= $(INCLUDE) -D$(ARCH)
CFLAGS		+= $(DEBUG_CFLAGS) -Xa $(CPPFLAGS)
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) \
		-ldiskmgt -lfstyp -lnvpair -llogsvc -linstzones -lima

ROOT_TEST_PROGS	= $(TEST_PROGS:%=$(ROOTOPTINSTALLTESTBIN)/%)
CLEANFILES	= $(TEST_PROGS)

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic
	@true

# Target Discovery Manager test program
tdmgtst:	dynamic tdmgtst.o
	$(LINK.c) -o tdmgtst tdmgtst.o \
		-R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTADMINLIB) -Lpics/$(ARCH) \
		-ltd -lfstyp -llogsvc -lnvpair

# statically built Target Discovery Manager test program
tdmgtst_static:	static tdmgtst.o
	$(LINK.c) -o tdmgtst_static tdmgtst.o \
		-L$(ROOTADMINLIB) -Lobjs/$(ARCH) \
		-Bstatic \
		-ltd -llogsvc \
		-Bdynamic \
		-ldiskmgt -lfstyp -lnvpair -ldevinfo -ladm \
		-linstzones -lzonecfg -lcontract -lgen -lima

# Target Discovery test program
test_td:	dynamic test_td.o
	$(LINK.c) -o test_td test_td.o \
		-R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTADMINLIB) -Lpics/$(ARCH) \
		-ltd -lfstyp -llogsvc -lnvpair

# statically built Target Discovery test program
test_td_static:	static test_td.o
	$(LINK.c) -o test_td_static test_td.o \
		-L$(ROOTADMINLIB) -Lobjs/$(ARCH) \
		-Bstatic \
		-ltd -llogsvc \
		-Bdynamic \
		-ldiskmgt -lfstyp -lnvpair -ldevinfo -ladm \
		-linstzones -lzonecfg -lcontract -lgen -lima

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

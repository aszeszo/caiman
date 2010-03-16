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
# Target Instantiation software library makefile
#

LIBRARY	= tgt

OBJECTS	= \
	discover.o \
	disk.o \
	geometry.o \
	instantiate.o \
	partition.o \
	slice.o \
	tgt.o \
	zpool.o

CPYTHONLIBS = tgt.so

PRIVHDRS = tgt.h

EXPHDRS =

HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

PYVERSION=python2.6
PYINCLUDE=-I/usr/include/$(PYVERSION) -I../libtd -I../libti

INCLUDE		 = -I. \
		   -I../libtd \
		   -I../libti \
		   $(PYINCLUDE) \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= $(INCLUDE) -D$(ARCH)
CFLAGS		+= $(DEBUG_CFLAGS) -Xa $(CPPFLAGS) -xc99
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) -ltd -lti \
		-Mmapfile-vers

PYMODULES=	tgt_utils.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)
ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALL)/%)
ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALL)/%)

# Can't include libdiskmgmt.h if it thinks we are 64-bit
#pics/$(ARCH)/disk.o:=CFLAGS += -D_FILE_OFFSET_BITS=32

static: $(OBJECTS)

dynamic: $(CPYTHONLIB)

all: $(HDRS) dynamic python

install_h:

install:	all .WAIT \
		$(ROOTPYTHONVENDOR) \
		$(ROOTPYTHONVENDORINSTALL) \
		$(ROOTPYTHONVENDORINSTALLLIBS) \
		$(ROOTPYTHONVENDORINSTALLMODS) \
		$(ROOTPYTHONVENDORINSTALLCMODS) \
		$(ROOTPYMODULES) \
		$(ROOTPYCMODULES)


lint:  $(SRCS) $(HDRS)
	$(LINT.c) $(SRCS)

python:
	$(PYTHON) -m compileall -l $(@D)

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	$(CSTYLE) $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

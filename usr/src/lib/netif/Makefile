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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
# Internet Protocol network interface names and interface indexes 
# software library makefile (if_nametoindex, if_indextoname, if_nameindex)
#

LIBRARY	= netif

OBJECTS	= netif.o

CPYTHONLIBS = netif.so

PRIVHDRS = netif.h

EXPHDRS =

HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

PYVERSION=python2.6
PYINCLUDE=-I/usr/include/$(PYVERSION)

INCLUDE		 = $(PYINCLUDE) \
		   -I$(ROOTINCADMIN)

CPPFLAGS	+= $(INCLUDE) -D$(ARCH)
CFLAGS		+= $(DEBUG_CFLAGS) -Xa $(CPPFLAGS) -xc99
LDFLAGS		+=
SOFLAGS		+= -L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-L$(ROOTUSRLIB) -R$(ROOTUSRLIB:$(ROOT)%=%) -lsocket -l$(PYVERSION) \
		-Mmapfile-vers

PYMODULES=	

PYCMODULES=	$(PYMODULES:%.py=%.pyc)
ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)
ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

static: $(OBJECTS)

dynamic: $(CPYTHONLIB)

all: dynamic

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

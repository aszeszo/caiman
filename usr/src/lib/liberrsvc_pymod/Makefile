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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

LIBRARY		= _liberrsvc

OBJECTS		= liberrsvc.o \
		  liberrsvc_wrap.o

CPYTHONLIBS	= _liberrsvc.so

PYMODS		= errsvc.py \
		liberrsvc.py

PYCMODS		= $(PYMODS:%.py=%.pyc)

CLOBBERFILES	= $(PYCMODS) liberrsvc_wrap.c liberrsvc.py
CLEANFILES	= $(CLOBBERFILES)

include ../Makefile.lib

PRIVHDRS	=
EXPHDRS		=
HDRS		= $(EXPHDRS) $(PRIVHDRS)

INCLUDE		= -I/usr/include/python2.6 -I../liberrsvc

CPPFLAGS	+= ${INCLUDE} $(CPPFLAGS.master) -D_FILE_OFFSET_BITS=64
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS} 
SOFLAGS		+= -L$(ROOTUSRLIB) -L$(ROOTADMINLIB) \
		-R$(ROOTUSRLIB:$(ROOT)%=%)  \
		-R$(ROOTADMINLIB:$(ROOT)%=%) -L/lib \
		-lpython2.6 -lm -lc -zdefs

static:

dynamic:	$(CPYTHONLIB)

python:
	$(PYTHON) -m compileall -l $(@D)

all:		$(HDRS) dynamic .WAIT python $(SUBDIRS)

install_h:

install:	all .WAIT \
		$(ROOTPYTHONVENDOR) \
		$(ROOTPYTHONVENDORINSTALL) \
		$(ROOTPYTHONVENDORINSTALLLIBS) \
		$(ROOTPYTHONVENDORINSTALLMODS) \
		$(ROOTPYTHONVENDORINSTALLCMODS)

lint:		lint_SRCS

liberrsvc_wrap.c liberrsvc.py:
	swig -python liberrsvc.i

$(SUBDIRS):	FRC
	cd $@; pwd; $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

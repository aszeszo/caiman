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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

PROGS=		beadm

PYMODULES=	__init__.py \
		BootEnvironment.py \
		messages.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS=	$(PROGS:%=$(ROOTSBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORBEADM)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORBEADM)/%)

all:		python $(PROGS)

clean:
	rm -f $(PROGS) $(PYCMODULES)

clobber: clean

install: all $(ROOTPROGS) $(ROOTPYMODULES) $(ROOTPYCMODULES)

python:
	python -m compileall -l $(@D)

beadm: beadm.py
	cp beadm.py beadm

include ../Makefile.targ

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

SUBDIRS=	modules

PROGS=		js2ai

PROG=	$(PROGS)

ROOTPROGS=	$(PROGS:%=$(ROOTUSRSBIN)/%)

all:		python $(PROGS)

clean:	 $(SUBDIRS)
	$(RM) $(PROGS) js2ai.pyc

clobber: clean

install: all .WAIT $(ROOTPROGS) \
	$(SUBDIRS)

js2ai: js2ai.py
	$(CP) js2ai.py js2ai
	$(CHMOD) 755 js2ai

python:
	$(PYTHON) -m compileall -l $(@D)

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

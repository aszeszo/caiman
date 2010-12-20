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

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

MSG_DOMAIN =	../js2ai

PYMODULES=	__init__.py \
			common.py \
			conv.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS=	$(PROGS:%=$(ROOTSBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLJS2AI)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLJS2AI)/%)

MSGFILES =  $(PYMODULES)

all:		python

clean:
	rm -f $(PYCMODULES)

clobber: clean

install: all .WAIT $(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORSOLINSTALLJS2AI) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES) \
	.WAIT msgs

python:
	$(PYTHON) -m compileall -l $(@D)

msgs:	$(MSG_DOMAIN).po

$(MSG_DOMAIN).po: $(PYMODULES)
	@echo "Making messages file $(MSG_DOMAIN).po"
		$(GNUXGETTEXT) $(GNUXGETFLAGS) -d $(MSG_DOMAIN) \
		$(MSGFILES)

include ../../Makefile.targ

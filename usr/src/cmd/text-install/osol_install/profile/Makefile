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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../../../Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

PYMODULES=	__init__.py \
		disk_info.py \
		disk_space.py \
		install_profile.py \
		partition_info.py \
		slice_info.py

PYCMODULES=     $(PYMODULES:%.py=%.pyc)

ROOTPROGS=      $(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLPROF)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLPROF)/%)

MSGFILES =	$(PYMODULES)

.KEEP_STATE:

all:		python

clean:
	rm -f $(PROGS) *.pyc

clobber: clean


install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLPROF) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES)

python:
	$(PYTHON) -m compileall -l $(@D)


FRC:

include ../../../Makefile.targ


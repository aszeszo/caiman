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

PROGS=		ai_get_manifest

PYMODULES=

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS=	$(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

all:		python $(PROGS)

clean:
	rm -f $(PROGS) $(PYCMODULES)

clobber: clean

install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLAI) \
	$(ROOTPYMODULES) $(ROOTPYCMODULES)

python:
	$(PYTHON) -m compileall -l $(@D)

ai_get_manifest: ai_get_manifest.py
	$(CP) ai_get_manifest.py ai_get_manifest
	$(CHMOD) 755 ai_get_manifest

install_h:

include ../Makefile.targ

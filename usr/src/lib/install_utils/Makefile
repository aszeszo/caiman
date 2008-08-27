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

include ../Makefile.lib

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

PYMODS =	__init__.py \
		DefValProc.py \
		ENParser.py \
		TreeAcc.py \
		finalizer.py \
		install_utils.py \
		ManifestServ.py \
		ManifestRead.py \
		SocketServProtocol.py

PYCMODS=	$(PYMODS:%.py=%.pyc)

ROOTRNGSCHEMA   = $(ROOT)/usr/share/lib/xml/rng
RNG_SCHEMA=	defval-manifest.rng
ROOTRNGSCHEMAFILE= $(RNG_SCHEMA:%=$(ROOTRNGSCHEMA)/%)

CLOBBERFILES = $(PYCMODS)
CLEANFILES = $(CLOBBERFILES)

all:		python

install: all .WAIT \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLMODS) \
	$(ROOTPYTHONVENDORINSTALLCMODS) \
	$(ROOTRNGSCHEMAFILE)

install_h:

python:
	$(PYTHON) -m compileall -l $(@D)

include ../Makefile.targ

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

PY_PROGS=	ManifestServ \
		ManifestRead

SCRIPTS=	usbgen \
		usbcopy \
		proc_tracedata \
		proc_slist

PROGS=		$(PY_PROGS) $(SCRIPTS)

ROOTPROGS=	$(PROGS:%=$(ROOTUSRBIN)/%)

all:		python $(PY_PROGS)

clean:
	$(RM) $(PY_PROGS) *.pyc

clobber: clean

install: all .WAIT $(ROOTPROGS) 

ManifestRead: ManifestRead.py
	$(CP) ManifestRead.py ManifestRead
	$(CHMOD) 755 ManifestRead

ManifestServ: ManifestServ.py
	$(CP) ManifestServ.py ManifestServ
	$(CHMOD) 755 ManifestServ

#Compile the python files, we are not shipping the .pyc files,
#but compiling it can help catch syntax errors.
python:
	$(PYTHON) -m compileall -l $(@D)

include ../Makefile.targ

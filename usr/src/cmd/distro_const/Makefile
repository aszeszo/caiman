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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

SUBDIRS=	checkpoints manifest profile sort

PROGS=		distro_const

PYMODULES=	cli.py \
		__init__.py \
		distro_spec.py \
		execution_checkpoint.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS= 	$(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLDC)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLDC)/%)

all:		python $(PROGS)

clean:	$(SUBDIRS)
	$(RM) $(PROGS) $(PYCMODULES)

clobber: clean

install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORINSTALLDC) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES) \
	$(SUBDIRS)

python:
	$(PYTHON) -m compileall -l $(@D)

distro_const: distro_const.py
	$(CP) distro_const.py distro_const
	$(CHMOD) 755 distro_const

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

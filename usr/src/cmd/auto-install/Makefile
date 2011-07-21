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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#
include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

SUBDIRS=	svc config checkpoints manifest profile

PROGS=		ai_get_manifest ai_sd auto-install

PYMODULES=	\
	__init__.py \
	ai_get_manifest.py \
	ai_instance.py \
	ai_parse_manifest.py \
	ai_sd.py \
	auto-install.py \
	auto_install.py \
	utmpx.py

PYCMODULES =	$(PYMODULES:%.py=%.pyc)

AIFILES=	version derived_manifest_test_env.sh

ROOTPROGS=	$(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLAI)/%)

ROOTAIFILES=	$(AIFILES:%=$(ROOTAUTOINST)/%)

all: python $(PROGS)

install: all .WAIT $(ROOTPROGS) \
	$(ROOTUSRBIN) \
	$(ROOTUSRBINPROG) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORSOLINSTALLAI) \
	$(ROOTAIFILES) \
	$(ROOTPYMODULES) $(ROOTPYCMODULES) \
	$(SUBDIRS)

python:
	$(PYTHON) -m compileall -l $(@D)

auto-install: auto-install.py
	$(CP) auto-install.py auto-install
	$(CHMOD) 755 auto-install

ai_get_manifest: ai_get_manifest.py
	$(CP) ai_get_manifest.py ai_get_manifest

ai_sd: ai_sd.py
	$(CP) ai_sd.py ai_sd

clean: $(SUBDIRS)
	$(RM) $(PROGS) $(PYCMODULES)

clobber: clean 

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

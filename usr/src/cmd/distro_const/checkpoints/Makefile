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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

SUBDIRS=	defaultfiles

PYMODULES=	__init__.py \
		ai_publish_pkg.py \
		boot_archive_archive.py \
		boot_archive_configure.py \
		create_iso.py \
		create_usb.py \
		custom_script.py \
		grub_setup.py \
		pkg_img_mod.py \
		pre_pkg_img_mod.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLDCCHKPT)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLDCCHKPT)/%)

all:		python

clean:  $(SUBDIRS)
	$(RM) $(PYCMODULES)

clobber: clean

install: all .WAIT $(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORINSTALLDC) \
	$(ROOTPYTHONVENDORINSTALLDCCHKPT) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES) \
	$(SUBDIRS)

python:
		$(PYTHON) -m compileall -l $(@D)

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../../Makefile.targ

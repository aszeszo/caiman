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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#

MSG_DOMAIN =	solaris_install_textinstall

include ../Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

SUBDIRS=        svc helpfiles

ROOTMSGS=       $(POFILE:%=$(ROOTUSRSHAREMSGS)/%)

PROGS=		text-install

PYMODULES=	__init__.py \
		discovery_selection.py \
		disk_selection.py \
		disk_window.py \
		fdisk_partitions.py \
		gpt_partitions.py \
		install_progress.py \
		install_status.py \
		iscsi.py \
		log_viewer.py \
		partition_edit_screen.py \
                progress.py \
		summary.py \
		ti_install.py \
		ti_install_utils.py \
                ti_target_utils.py \
		welcome.py

PYCMODULES=     $(PYMODULES:%.py=%.pyc)

ROOTPROGS=      $(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLTI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLTI)/%)

MSGFILES =	$(PYMODULES)

.PARALLEL:	$(SUBDIRS)

.KEEP_STATE:

all:	python $(PROGS) $(SUBDIRS) $(POFILE)

clean: $(SUBDIRS)
	rm -f *.pyc  $(POFILE)

clobber: clean

install: all .WAIT $(SUBDIRS) .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORSOLINSTALLTI) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES) \
	$(ROOTMSGS)

python:
	$(PYTHON) -m compileall -l $(@D)

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

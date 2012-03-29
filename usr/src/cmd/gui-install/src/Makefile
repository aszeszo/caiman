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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

include ../../Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

PROGS=		gui-install

PYMODULES=	__init__.py \
	base_screen.py \
	confirm_screen.py \
	disk_panel.py \
	disk_screen.py \
	failure_screen.py \
	fdisk_panel.py \
	finish_screen.py \
	gpt_panel.py \
	gui_install_common.py \
	help_dialog.py \
	install_profile.py \
	libzoneinfo_ctypes.py \
	map.py \
	progress_screen.py \
	screen_manager.py \
	support_screen.py \
	textview_dialog.py \
	timezone.py \
	timezone_screen.py \
	user_screen.py \
	welcome_screen.py

PYCMODULES=     $(PYMODULES:%.py=%.pyc)

ROOTPROGS=      $(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLGUI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORSOLINSTALLGUI)/%)

.KEEP_STATE:

all:	python $(PROGS)

clean:
	$(RM) $(PROGS) $(PYCMODULES)

clobber: clean

install: all \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORSOLINSTALLGUI) \
	.WAIT \
	$(ROOTPROGS) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES)

python:
	$(PYTHON) -m compileall -l $(@D)

gui-install: gui-install.py
	$(CP) gui-install.py gui-install
	$(CHMOD) 755 gui-install

include ../../Makefile.targ

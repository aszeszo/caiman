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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include ../../../Makefile.cmd

all:=		TARGET= all
clean:=		TARGET= clean
clobber:=	TARGET= clobber
install:=	TARGET= install

MSG_DOMAIN =	textinstall

PROGS=		text-install

PYMODULES=	__init__.py \
		action.py \
		base_screen.py \
		color_theme.py \
		date_time.py \
		disk_selection.py \
		disk_window.py \
		edit_field.py \
		error_window.py \
		fdisk_partitions.py \
		help_screen.py \
		inner_window.py \
		install_progress.py \
		install_status.py \
		list_item.py \
		log_viewer.py \
		main_window.py \
		network_nic_configure.py \
		network_nic_select.py \
		network_type.py \
		partition_edit_screen.py \
		screen_list.py \
		scroll_window.py \
		summary.py \
		ti_install.py \
		ti_install_utils.py \
		timezone.py \
		users.py \
		welcome.py \
		window_area.py

PYCMODULES=     $(PYMODULES:%.py=%.pyc)

ROOTPROGS=      $(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=  $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLTI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLTI)/%)

MSGFILES =	$(PYMODULES) text_install.py

.KEEP_STATE:

all:		python $(PROGS)

clean:
	rm -f $(PROGS) *.pyc  $(MSG_DOMAIN).po

clobber: clean


install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLTI) \
	$(ROOTPYMODULES) \
	$(ROOTPYCMODULES) \
	.WAIT msgs

python:
	$(PYTHON) -m compileall -l $(@D)

text-install:	text_install.py
		cp text_install.py text-install

msgs:	$(MSG_DOMAIN).po

$(MSG_DOMAIN).po: text_install.py $(PYMODULES)
	@echo "Making messages file $(MSG_DOMAIN).po"
	$(GNUXGETTEXT) $(GNUXGETFLAGS) -d $(MSG_DOMAIN) \
		$(MSGFILES)

FRC:

include ../../../Makefile.targ

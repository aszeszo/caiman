
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

PYMODS		= __init__.py \
		  apply_sysconfig.py \
		  boot_archive.py \
		  cleanup_cpio_install.py \
		  create_snapshot.py \
		  device_config.py \
		  generate_sc_profile.py \
		  initialize_smf.py \
		  ips.py \
		  setup_swap.py \
                  transfer_files.py \
		  update_dumpadm.py

PROFILESRC=	sc_template.xml

PYCMODS		= $(PYMODS:%.py=%.pyc)

ROOTPYMODS=     $(PYMODS:%=$(ROOTPYTHONVENDORSOLINSTALLICT)/%)

ROOTPYCMODS=    $(PYCMODS:%=$(ROOTPYTHONVENDORSOLINSTALLICT)/%)

PROFILES= $(PROFILESRC:%=$(ROOTUSRSHAREINSTALL)/%)

CLOBBERFILES	= $(PYCMODS)
CLEANFILES	= $(CLOBBERFILES)

include ../Makefile.lib

all:=           TARGET= all
check:=         TARGET= check
clean:=         TARGET= clean
clobber:=       TARGET= clobber
install:=       TARGET= install
install_h:=     TARGET= install_h
lint:=          TARGET= lint

.KEEP_STATE:

python:
	$(PYTHON) -m compileall -l $(@D)

all:		python

install_h:

install:	all .WAIT \
		$(ROOTPYTHONVENDOR) \
                $(ROOTPYTHONVENDORSOLINSTALL) \
		$(ROOTPYTHONVENDORSOLINSTALLICT) \
		$(ROOTPYMODS) \
		$(ROOTPYCMODS) \
		$(ROOTUSRSHAREINSTALL) $(PROFILES)

lint:		lint_SRCS

FRC:

include ../Makefile.targ

#
##
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


PYMODS		= parser.py

PYCMODS		= $(PYMODS:%.py=%.pyc)

ROOTPYMODS=	$(PYMODS:%=$(ROOTPYTHONVENDORSOLINSTALLMANIFEST)/%)

ROOTPYCMODS=	$(PYCMODS:%=$(ROOTPYTHONVENDORSOLINSTALLMANIFEST)/%)


CLOBBERFILES	= $(PYCMODS) 
CLEANFILES	= $(CLOBBERFILES)

include ../../Makefile.lib

static:

dynamic:

python:
	$(PYTHON) -m compileall -l $(@D)

all:		python

install_h:

install:	all .WAIT \
		$(ROOTPYTHONVENDOR) \
		$(ROOTPYTHONVENDORSOLINSTALL) \
		$(ROOTPYTHONVENDORSOLINSTALLMANIFEST) \
		$(ROOTPYMODS) $(ROOTPYCMODS)

lint:		lint_SRCS

FRC:

include ../../Makefile.targ

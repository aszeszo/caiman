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

PROGS=		distro_const

PYMODULES=	DC_checkpoint.py \
		__init__.py \
		DC_defs.py \
		DC_ti.py \
		DC_tm.py \
		ValidatorModule.py \
		DefaultsModule.py \
		dc_utils.py \
		finalizer_checkpoint.py \
		finalizer_rollback.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS=	$(PROGS:%=$(ROOTSBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLDC)/%)

ROOTPYCMODULES=	$(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLDC)/%)

all:		python $(PROGS)

clean:
	$(RM) $(PROGS) $(PROGS).pyc $(PYCMODULES)

clobber: clean

install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLDC) \
	$(ROOTPYMODULES) $(ROOTPYCMODULES) manifest_files

python:
	$(PYTHON) -m compileall -l $(@D)

distro_const: distro_const.py
	$(CP) distro_const.py distro_const
	$(CHMOD) 755 distro_const

#
# The manifest_files target is a hack right now.  It is used
# for getting around the problem of the DefValProc.py module
# having hard coded values for the xml and schema files for DC.
# This target should be removed once that is fixed.
#
manifest_files:
	$(CP) DC-manifest.defval.xml \
		$(ROOTPYTHONVENDORINSTALLDC)/DC-manifest.defval.xml
	$(CP) DC-manifest.rng $(ROOTPYTHONVENDORINSTALLDC)/DC-manifest.rng

include ../Makefile.targ

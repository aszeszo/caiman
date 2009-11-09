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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include ../../Makefile.cmd

all:=           TARGET= all
clean:=         TARGET= clean
clobber:=       TARGET= clobber
install:=       TARGET= install

PYMODULES=	ai_plat_setup.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

AUTOINSTALL_FILES=	ai_generic_live.xml \
			ai_x86_image.xml \
			ai_sparc_image.xml \
			ai_boot_archive_configure \
			ai_post_boot_archive_pkg_image_mod \
			ai_pre_boot_archive_pkg_image_mod \
			$(PYMODULES)

ROOT_AUTOINSTALL_FILES=	$(AUTOINSTALL_FILES:%=$(ROOTDC_AI)/%)

all:		python	

clean:
		$(RM) $(PYCMODULES)

clobber: 	clean

install:	$(ROOTDC) \
		$(ROOTDC_AI) \
		$(ROOT_AUTOINSTALL_FILES)

python:	
		$(PYTHON) -m compileall -l $(@D)

include ../../Makefile.targ

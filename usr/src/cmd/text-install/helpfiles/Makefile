
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

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

HELP_FILES=	discovery_selection.txt \
                disks.txt \
		gpt_partitions.txt \
                iscsi.txt \
		sparc_solaris_slices_select.txt \
		sparc_solaris_slices.txt \
		summary.txt \
		welcome.txt \
		x86_fdisk_partitions_select.txt \
		x86_fdisk_partitions.txt \
		x86_fdisk_slices_select.txt \
		x86_fdisk_slices.txt

ROOTHELP_FILES=	$(HELP_FILES:%=$(ROOTUSRSHARETIHELPC)/%)

$(ROOTUSRSHARETI):
	$(INS.dir)

all: $(ROOTUSRSHARETIHELPC)

clean:	
	rm -rf $(ROOTUSRSHARETI)

clobber: clean

install: all .WAIT $(ROOTHELP_FILES)

include ../../Makefile.targ

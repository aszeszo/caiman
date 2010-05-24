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
# Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
#

#
# Top-level Makefile
#
# include global definitions
include Makefile.master
#
# the Targetdirs file is the AT&T target.dirs file in a makefile format.
# it defines TARGETDIRS and ROOTDIRS.
include Targetdirs

SUBDIRS=	tools man lib cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
headers:=	TARGET= headers
install:=	TARGET=	install
lint:=		TARGET= lint
pkgs:=		TARGET= pkgs

.KEEP_STATE:

all install:	headers .WAIT man .WAIT lib .WAIT cmd .WAIT pkgs

clean clobber lint: $(SUBDIRS) pkg pkgdefs

proto: headers

headers: rootdirs .WAIT build-tools .WAIT $(SUBDIRS)

rootdirs: $(ROOTDIRS)

# We use our own local tools when creating the header files.  These
# should eventually be packaged separately and delivered onto build
# machines, rather than rebuilt with every nightly run.
build-tools:
	@cd tools; pwd; $(MAKE) install

$(SUBDIRS) pkg pkgdefs: FRC
	@cd $@; pwd; $(MAKE) $(TARGET)

$(SRC)/pkgdefs/awk_pkginfo:
	@cd $(SRC)/pkgdefs; pwd; $(MAKE) awk_pkginfo

$(XGETSH): $(ROOTDIRS)
	@cd $(SRC)/tools/xgetsh; pwd; $(MAKE) install

FRC:

$(ROOTDIRS):
	$(INS.dir)

pkgs:
	@cd $(SRC)/pkgdefs; pwd; $(MAKE) install
	@cd $(SRC)/pkg; pwd; $(MAKE) install

# Build the TAGS file for etags, the Emacs cross-referencer
ETAGS=etags

etags:
	@-rm TAGS
	find . \( -type d \( -name Codemgr_wsdata -o -name SCCS -o -name .del\* \) \) -prune -o \
	       \( -name '*.[Ccshlxy]' -o -name \*.java -o -name \*.cc \) -print | $(ETAGS) -

CTAGS=ctags

ctags:
	@-rm tags
	find . \( -type d \( -name Codemgr_wsdata -o -name SCCS -o -name .del\* \) \) -prune -o \
	       \( -name '*.[Ccshlxy]' -o -name \*.java -o -name \*.cc \) -print | xargs $(CTAGS) -a

#
# The cscope.out file is made in the current directory and spans the
# entire source tree.
#
# Things to note:
#   1. We use relative names for cscope
#   2. Unlike ON, our workspace is small enough that we can easily rebuild
#      the database each time, so we do blow it away first.
#
CSDIR=.
CSCOPE=cscope

cscope:
	@-rm cscope.files cscope.out
	find . \( -type d \( -name Codemgr_wsdata -o -name SCCS -o -name .del\* \) \) -prune -o \
	       \( -name '*.[Ccshlxy]' -o -name \*.cc -o -name Makefile\* \) -print > cscope.files
	$(CSCOPE) -b

.NO_PARALLEL: cc-version cc64-version java-version

# Compiler version reporting; used by nightly.
cc-version:
	@if $(CC) -flags >/dev/null 2>/dev/null; then	\
		$(ECHO) 32-bit compiler;		\
		which $(CC);				\
		$(CC) -V 2>&1 | head -1;		\
	else						\
		$(ECHO) No 32-bit compiler found;	\
		exit 1;					\
	fi

cc64-version:
	@__VERSION=`$(CC) -m64 -E /dev/null 2>&1 >/dev/null`; \
	if [ -z "$$__VERSION" ]; then			\
		$(ECHO) 64-bit compiler;		\
		which $(CC);				\
		$(CC) -V 2>&1 | head -1;		\
	else						\
		$(ECHO) No 64-bit compiler found;	\
		exit 1;					\
	fi

java-version:
	@$(ECHO) Java compiler;				\
	$(ECHO) Java not used in this build

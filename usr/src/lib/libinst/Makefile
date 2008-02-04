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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

#
# ident	"@(#)Makefile	1.34	07/11/06 SMI"
#

LIBRARY=	libinst.a

OBJECTS=copyf.o		dockdeps.o	echo.o		eptstat.o	\
	finalck.o	findscripts.o	fixpath.o	flex_dev.o	\
	isreloc.o	lockinst.o	mntinfo.o	nblk.o		\
	ocfile.o	pathdup.o	pkgdbmerg.o	procmap.o	\
	pkgobjmap.o	psvr4ck.o	ptext.o		putparam.o	\
	qreason.o	qstrdup.o	setadmin.o	setlist.o	\
	srcpath.o	scriptvfy.o	stub.o		doulimit.o	\
	dryrun.o	listmgr.o	is_local_host.o cvtpath.o	\
	depchk.o	pkgops.o	sml.o		log.o		\
	setup_temporary_directory.o	open_package_datastream.o	\
	unpack_package_from_stream.o

EXPHDRS	=	dryrun.h install.h libinst.h

# include library definitions
include ../Makefile.lib

TEXT_DOMAIN= SUNW_PKG_CMDS

#
# messaging catalog
#
POFILE = libinst.po
POFILES= $(OBJECTS:%.o=%.po)
# making a po file requires making .c from lex
scriptvfy.c:	scriptvfy.l

GENERAL=	$(SRC)/cmd/pkgcmds/hdrs
LIBPKGDIR=	$(SRC)/lib/libpkg
CPPFLAGS=	-I. -I$(GENERAL) -I$(LIBPKGDIR) \
		-I$(SFWINCDIR) $(CPPFLAGS.master) \
		-I$(ROOTINCADMIN) \
		-DTEXT_DOMAIN=\"${TEXT_DOMAIN}\"

LB=         objs/$(ARCH)/libinst.a

LINTOUT=	lint.out
CLEANFILES=	$(LINTOUT) $(LINTLIB)

.KEEP_STATE:

all: 		$(LIBS) .WAIT link

static:		all

dynamic:	all

_msg:   $(POFILE)

$(LIBRARY):	all

$(POFILE): $(POFILES)
	$(RM)	$@
	cat $(POFILES)  > $@

install:	all _msg

install_h:	$(ROOTUSRINCLEXP)

link:
	rm -f $(LIBRARY); $(LN) objs/$(ARCH)/libinst.a $(LIBRARY);

CLOBBERFILES +=	$(LB) $(LIBRARY) scriptvfy.c

lint:		$(LINTLIB)

# include library targets
include ../Makefile.targ

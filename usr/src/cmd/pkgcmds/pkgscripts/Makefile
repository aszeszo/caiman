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
# ident	"@(#)Makefile	1.32	07/11/06 SMI"
#
PROG=		cmdexec
SHELLS=		r.build i.build i.sed i.awk r.sed r.awk i.CompCpio
ADMINFILE=	default
PRODUCT=	$(PROG) $(SHELLS)

SRCS=		$(PROG:%=%.c)

include ../../Makefile.cmd
TEXT_DOMAIN= SUNW_PKG_CMDS
#
# for messagin catalog file
#
POFILE= pkgscripts.po
POFILES= $(SRCS:%.c=%.po)

GENLIBS=     -L$(SFWLIBDIR) -R$(SFWLIBRDIR) -L$(ROOTADMINLIB)

LIBPKG=		-lpkg
LIBPKGDIR=  $(SRC)/lib/libpkg
LAZYLIB=	-z lazyload -lzonecfg -lcontract -z nolazyload
LDLIBS=     $(LDLIBS.cmd) $(GENLIBS) $(LIBPKG) -lelf -ladm -lnsl -lsocket \
		-lcrypto -lmd5 -lwanboot -lssl -lcrypto -lmd5 $(LAZYLIB)

CPPFLAGS=	-I$(LIBPKGDIR) -I$(SFWINCDIR) $(CPPFLAGS.master) \
		-DTEXT_DOMAIN=\"${TEXT_DOMAIN}\"

FILEMODE=	0555
OWNER=		root
GROUP=		sys

ROOTPKG= 	$(ROOT)/var/sadm/install
ROOTPKGADM=	$(ROOTPKG)/admin
ROOTPKGSCR=	$(ROOT)/usr/sadm/install/scripts
ROOTPKGSCRPROG=	$(PROG:%=$(ROOTPKGSCR)/%)
ROOTPKGSCRSHELL=$(SHELLS:%=$(ROOTPKGSCR)/%)
ROOTPKGADMFILE= $(ADMINFILE:%=$(ROOTPKGADM)/%)


$(ROOTPKGADMFILE) := FILEMODE = 0444

.KEEP_STATE:

all: 		$(PRODUCT) $(ADMINFILE) 

static:     all

dynamic:    all

catalog: $(POFILE)

$(POFILE):      $(POFILES)
	$(RM) 	$@
	cat     $(POFILES)      > $@

install:	all .WAIT $(ROOTPKGSCRPROG) $(ROOTPKGSCRSHELL) \
		$(ROOTPKGADMFILE)

$(ROOTPKGSCR)/%: %
	$(INS.file)

$(ROOTPKGADM)/%: %
	$(INS.file)

$(ROOTPKG)/%: %
	$(INS.file)

lint:		lint_SRCS

clean:
	$(RM) $(OBJECTS)

include ../../Makefile.targ

#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at src/OPENSOLARIS.LICENSE.
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
#ident	"@(#)Makefile	1.3	07/03/08 SMI"

#
# lib/libgendb/Makefile
#

MSG_DOMAIN=	SUNW_INSTALL_GENDB

GDBSRC=		genericdb.c
GDBHDR=		genericdb.h genericdb_private.h

LIBRARY= libgendb.a
VERS=   .1

OBJECTS= genericdb.o

# include library definitions
include ../Makefile.lib

CFLAGS +=	-Xt -xspace -W0,-Lt $(DEBUG_CFLAGS)

SOFLAGS=      -h $(SOLIBNAME) -L$(ROOTUSRLIB) -lpkgdb
CPPFLAGS=     -I. -I../libpkgdb $(CPPFLAGS.master) \
		-DTEXT_DOMAIN=\"${MSG_DOMAIN}\"

CPPFLAGS +=	-DNDEBUG

CLOBBERFILES    = *.po *.mo

TEXT_DOMAIN =  SUNW_PKG_LIBGENDB
MSG_DOMAIN =  SUNW_PKG_LIBGENDB

POFILES= $(OBJECTS:%.o=%.po)

.KEEP_STATE:

all:    static dynamic

install_h:

static: $(LIBS)

$(LINTLIB) :=	SRCS=$(LINTSRC)

dynamic:    $(DYNLIB) $(LINTLIB)

messages:	${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: 	${GDBSRC} ${GDBHDR}
	@echo "Making message file $(MSG_DOMAIN).po"
	cc -C -E ${GDBSRC} ${GDBHDR} 2>/dev/null | \
		xgettext -d $(MSG_DOMAIN) -c "i18n:" - > /dev/null 2>&1

install: all .WAIT \
	$(ROOTUSRLIBS) $(ROOTUSRLIBDYNLIB) $(ROOTUSRLIBDYNLIBLINK) \
	$(ROOTUSRLINT) .WAIT messages .WAIT  $(INSTMSGS)

lint:	lint_SRCS

# include library targets
include ../Makefile.targ

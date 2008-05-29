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
#

#
# lib/libpkg/Makefile
#
LIBRARY= libpkg.a
VERS=	.1


OBJECTS= \
canonize.o   ckparam.o    ckvolseq.o   devtype.o    dstream.o    gpkglist.o \
gpkgmap.o    isdir.o      logerr.o     mappath.o    ncgrpw.o     nhash.o \
pkgexecl.o   pkgexecv.o   pkgmount.o   pkgtrans.o   pkgxpand.o   ppkgmap.o \
progerr.o    putcfile.o   rrmdir.o     runcmd.o     srchcfile.o  tputcfent.o \
verify.o     security.o   pkgweb.o     pkgerr.o     keystore.o   p12lib.o \
dbsql.o      vfpops.o     fmkdir.o     pkgstr.o     handlelocalfs.o

# include library definitions
include ../Makefile.lib

CFLAGS +=	-Xt -xspace -W0,-Lt $(DEBUG_CFLAGS)

LIBINCS=-I../libgendb -I$(SFWINCDIR)

SOFLAGS=      -h $(SOLIBNAME) -L$(ROOTUSRLIB) -lgendb -ldl -lwanboot
CPPFLAGS=     -I. $(LIBINCS) $(CPPFLAGS.master) -DNDEBUG -D_FILE_OFFSET_BITS=64

# openssl forces us to ignore dubious pointer casts, thanks to its clever
# use of macros for stack management.
LINTFLAGS=	-umx -errtags \
		-erroff=E_BAD_PTR_CAST_ALIGN,E_BAD_PTR_CAST

CLOBBERFILES	= *.po *.mo *.ln

TEXT_DOMAIN =  SUNW_PKG_LIBPKG
MSG_DOMAIN =  SUNW_PKG_LIBPKG

POFILES= $(OBJECTS:%.o=%.po)

# Add TEXT_DOMAIN for building of .po files only
$(MSG_DOMAIN).po:=	CPPFLAGS += -DTEXT_DOMAIN=$(TEXT_DOMAIN)

.KEEP_STATE:

all:	$(LIBS) $(DYNLIB) $(LINTLIB)

install_h:

static: $(LIBS)

$(LINTLIB) :=	SRCS=$(LINTSRC)

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po:      $(POFILES)
	$(RM)	$@
	cat $(POFILES) > $@

install: all .WAIT $(ROOTUSRLIBS) $(ROOTUSRLIBDYNLIB) $(ROOTUSRLIBDYNLIBLINK) \
	$(ROOTUSRLINT) .WAIT msgs .WAIT  $(INSTMSGS)

lint:	lint_SRCS

# include library targets
include ../Makefile.targ

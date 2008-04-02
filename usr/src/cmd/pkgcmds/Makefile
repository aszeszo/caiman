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

TEXT_DOMAIN= SUNW_PKG_CMDS

SUBDIRS=	pkgadd    pkginstall   pkgrm    pkgremove   pkginfo  \
		pkgproto  pkgchk       pkgmk   pkgscripts   installf \
		pkgtrans  pkgname      pkgparam    pkgadm	pkgcond

.PARALLEL=	$(SUBDIRS)

ROOTPKGADM=	$(ROOT)/var/sadm/install
ROOTPKGADMIN=	$(ROOTPKGADM)/admin
ROOTPKGINS=	$(ROOT)/usr/sadm/install
ROOTPKGBIN=	$(ROOTPKGINS)/bin
ROOTPKGSCR=	$(ROOTPKGINS)/scripts

INSDIRS=	$(ROOTBIN)	$(ROOTUSRSBIN)	$(ROOTPKGADM) \
		$(ROOTPKGADMIN)	$(ROOTPKGINS)	$(ROOTPKGBIN) \
		$(ROOTPKGSCR) $(ROOTUSRBIN)

$(CH)$(ROOTPKGADM)   := DIRMODE = 555
$(CH)$(ROOTPKGSCR)   := DIRMODE = 755
$(CH)$(ROOTPKGADMIN)	:= DIRMODE = 555

all:=		TARGET= all
install:=	TARGET= install
clean:=		TARGET= clean
clobber:=	TARGET= clobber
lint:=		TARGET= lint
static:=	TARGET= static
dynamic:=		TARGET= dynamic

#
# for message catalog files
#
_msg:=          TARGET= catalog
POFILE= pkgcmds.po
POFILES= $(SUBDIRS:%=%/%.po)
LIBINSTPOFILE= $(SRC)/lib/libinst/libinst.po

.KEEP_STATE:

all:		$(SUBDIRS) .WAIT _msg

clean dynamic lint static: $(SUBDIRS)

clobber:	$(SUBDIRS) local_clobber

local_clobber:
	$(RM) $(CLOBBERFILES)

install_h:

install: $(INSDIRS) .WAIT $(SUBDIRS) .WAIT _msg

_msg:   $(SUBDIRS)
	$(RM) $(POFILE)
	$(CAT) $(POFILES) $(LIBINSTPOFILE) > $(POFILE)
	$(RM) $(ROOTUSRLIBMSGS)/$(TEXT_DOMAIN).po
	cp $(POFILE) $(ROOTUSRLIBMSGS)/$(TEXT_DOMAIN).po

$(INSDIRS):
	$(INS.dir)

$(SUBDIRS): FRC
	@cd $@; pwd; $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

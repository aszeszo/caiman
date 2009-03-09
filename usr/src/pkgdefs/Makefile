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
#

# include global definitions
include ./Makefile.com

# COMMON_VERSION becomes VERSION field in pkginfo file, which is used to 
# determine upgradability.

COMMON_VERSION="11.11"

COMMON_SUBDIRS	= \
	SUNWauto-install \
	SUNWauto-install-common \
	SUNWbeadm \
	SUNWdistro-const \
	SUNWgui-install \
	SUNWinstall \
	SUNWinstall-libs \
	SUNWinstall-test \
	SUNWinstalladm-tools \
	SUNWslim-utils \
	SUNWstosreg \

SUBDIRS		= $(COMMON_SUBDIRS)

.PARALLEL:	$(SUBDIRS)

all:=		TARGET= all
install:=	TARGET= install
clean:=		TARGET= clean
clobber:=	TARGET= clobber
lint:=		TARGET= lint

.KEEP_STATE:

all install: awk_pkginfo .WAIT $(SUBDIRS)

%: %.ksh
	$(RM) $@
	cp $< $@
	chmod +x $@

awk_pkginfo: bld_awk_pkginfo
	./bld_awk_pkginfo -m $(ARCH) -p "$(VERSION)" -v "$(COMMON_VERSION)" \
		-o $@

lint install_h:

clobber clean:	$(SUBDIRS)
	rm -f bld_awk_pkginfo awk_pkginfo

$(SUBDIRS): FRC
	cd $@; pwd; $(MAKE) $(TARGET)

FRC:

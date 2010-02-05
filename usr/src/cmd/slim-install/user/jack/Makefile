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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#

JACKCONFIGAUTOFILESRC = iotrace.desktop
JACKFILESRC644 = xscreensaver xorg.conf.vesa
JACKFILESRC755 = Xclients local.bashrc local.profile
JACKDESKTOPFILESRC = 	install_opensolaris.desktop ddu.desktop \
			getting_started.desktop .os-icons-installed


include $(SRC)/cmd/slim-install/Makefile.slim

JACKFILES644= $(JACKFILESRC644:%=$(ROOTJACK)/%)
$(JACKFILES644) :=	FILEMODE= 0644

JACKFILES755= $(JACKFILESRC755:%=$(ROOTJACK)/%)
$(JACKFILES755) :=      FILEMODE= 0755

JACKCONFIGAUTOFILES= $(JACKCONFIGAUTOFILESRC:%=$(ROOTJACKCONFIGAUTO)/%)
$(JACKCONFIGAUTOFILES) :=      FILEMODE= 0644

JACKDESKTOPFILES= $(JACKDESKTOPFILESRC:%=$(ROOTJACKDESKTOP)/%)
$(JACKDESKTOPFILES) :=      FILEMODE= 0644

all: 

install: all $(ROOTJACK) $(ROOTJACKCONFIGAUTO) $(ROOTJACKDESKTOP) \
	$(JACKFILES644) $(JACKFILES755) $(JACKCONFIGAUTOFILES) \
	$(JACKDESKTOPFILES)

$(ROOTJACK) $(ROOTJACKCONFIGAUTO) $(ROOTJACKDESKTOP):
	$(INS.dir)

$(ROOTJACK)/%: % $(ROOTJACK)
	$(INS.file)

$(ROOTJACKCONFIGAUTO)/%: % $(ROOTJACKCONFIGAUTO)
	$(INS.file)

$(ROOTJACKDESKTOP)/%: % $(ROOTJACKDESKTOP)
	$(INS.file)

clobber clean:
       
.os-icons-installed:
	$(TOUCH) $@

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

JACKCONFIGAUTOFILESRC = license.desktop
JACKFILESRC644 = xscreensaver install-icon.png 
JACKFILESRC755 = Xclients local.bashrc
JACKDESKTOPFILESRC = install_opensolaris.desktop


include $(SRC)/cmd/slim-install/Makefile.slim

JACKFILES644= $(JACKFILESRC644:%=$(ROOTJACK)/%)
$(JACKFILES644) :=	FILEMODE= 0644

JACKFILES755= $(JACKFILESRC755:%=$(ROOTJACK)/%)
$(JACKFILES755) :=      FILEMODE= 0755

JACKCONFIGAUTOFILES= $(JACKCONFIGAUTOFILESRC:%=$(ROOTJACKCONFIGAUTO)/%)
$(JACKCONFIGAUTOFILES) :=      FILEMODE= 0644

JACKDESKTOPFILES= $(JACKDESKTOPFILESRC:%=$(ROOTJACKDESKTOP)/%)
$(JACKDESKTOPFILES) :=      FILEMODE= 0644




all: $(JACKFILES644) $(JACKFILES755) $(JACKCONFIGAUTOFILES) $(JACKDESKTOPFILES)

install: all $(ROOTJACK) $(ROOTJACKCONFIGAUTO) $(ROOTJACKDESKTOP)

$(ROOTJACK)/%: %
	$(INS.file)

$(ROOTJACKCONFIGAUTO)/%: %
	$(INS.file)

$(ROOTJACKDESKTOP)/%: %
	$(INS.file)

clobber clean:
       

$(ROOTMANSYS)/% $(ROOTMANSYSDEV)/% $(ROOTMANSYSFIL)/%  \
$(ROOTVARSVCPROFILE)/% $(ROOTLIBSVCMETHOD)/%: %
	$(INS.file)

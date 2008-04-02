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

SYSMANIFESTSRC=	live-sysidtool.xml live-io-tracing.xml

SYSDEVICEMANIFESTSRC=	live-devices-local.xml

SYSFSMANIFESTSRC=	live-root-fs.xml live-usr-fs.xml 
                
SVCMETHODSRC=	live-devices-local live-fs-root live-fs-usr \
		live-sysidtool-system  live-io-tracing

PROFILESRC=	network_nwam.xml


include $(SRC)/cmd/Makefile.cmd


FILEMODE= 444

SYSMANIFESTS= $(SYSMANIFESTSRC:%=$(ROOTMANSYS)/%)
SYSDEVICEMANIFESTS= $(SYSDEVICEMANIFESTSRC:%=$(ROOTMANSYSDEV)/%)
SYSFSMANIFESTS= $(SYSFSMANIFESTSRC:%=$(ROOTMANSYSFIL)/%)
PROFILES= $(PROFILESRC:%=$(ROOTVARSVCPROFILE)/%)


SVCMETHODS= $(SVCMETHODSRC:%=$(ROOTLIBSVCMETHOD)/%)
$(SVCMETHODS) :=	FILEMODE= 0555


all: $(SYSMANIFESTS) $(SYSDEVICEMANIFESTS) $(SYSFSMANIFESTS) \
	$(PROFILES) $(SVCMETHODS)

install: all $(ROOTMANSYS) $(ROOTMANSYSDEV) $(ROOTMANSYSFIL) \
	$(ROOTVARSVCPROFILE) $(ROOTLIBSVCMETHOD)
	

clobber clean:
       

$(ROOTMANSYS)/% $(ROOTMANSYSDEV)/% $(ROOTMANSYSFIL)/%  \
$(ROOTVARSVCPROFILE)/% $(ROOTLIBSVCMETHOD)/%: %
	$(INS.file)

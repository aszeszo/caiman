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
include $(SRC)/Makefile.master

FILEMODE = 0755

# Definitions of common installation directories
ROOTLIBSVCMETHOD	= $(ROOT)/lib/svc/method
ROOTLIBSVCSHARE	= $(ROOT)/lib/svc/share
ROOTMANIFEST	= $(ROOT)/var/svc/manifest
ROOTMANAPP	= $(ROOTMANIFEST)/application
ROOTMANSYS	= $(ROOTMANIFEST)/system
ROOTMANSYSFIL	= $(ROOTMANSYS)/filesystem
ROOTMANSYSSVC	= $(ROOTMANSYS)/svc
ROOTMANSYSINS	= $(ROOTMANSYS)/install
ROOTSBIN	= $(ROOT)/sbin
ROOTUSRLIB	= $(ROOT)/usr/lib
ROOTUSRLIBINSTALLADM	= $(ROOT)/usr/lib/installadm
ROOTUSRBIN	= $(ROOT)/usr/bin
ROOTUSRSBIN	= $(ROOT)/usr/sbin
ROOTVARSADM	= $(ROOT)/var/sadm
ROOTVARINSTADM	= $(ROOT)/var/installadm
ROOTVARAIWEB	= $(ROOT)/var/installadm/ai-webserver
ROOTVARSVCPROFILE	= $(ROOT)/var/svc/profile

# Derived installation rules
ROOTUSRBINPROG	= $(PROG:%=$(ROOTUSRBIN)/%)

ROOTUSRSBINPROG	= $(PROG:%=$(ROOTUSRSBIN)/%)
ROOTUSRSBINFILES = $(FILES:%=$(ROOTUSRSBIN)/%)

ROOTSBINPROG	= $(PROG:%=$(ROOTSBIN)/%)
ROOTSBINFILES	= $(FILES:%=$(ROOTSBIN)/%)

# Basic linkage macro
LDLIBS.cmd	= -L$(ROOTUSRLIB) -L$(ONLIBDIR) -L$(ONUSRLIBDIR)


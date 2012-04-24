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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#
#

EXECATTRFILES = exec_attr.SUNWgui-install exec_attr.distribution-constructor \
                exec_attr.system%2Finstall%2Fmedia%2Finternal \
                exec_attr.install%2Finstalladm

PROFATTRFILES = prof_attr.distribution-constructor \
                prof_attr.install%2Finstalladm

USERATTRFILES = user_attr.system%2Finstall%2Fauto-install \
                user_attr.SUNWgui-install

AUTHATTRFILES = auth_attr.install%2Finstalladm

include $(SRC)/cmd/Makefile.cmd

FILEMODE= 444

all:

install: all $(ROOTEXECATTR) $(ROOTPROFATTR) $(ROOTUSERATTR) $(ROOTAUTHATTR) .WAIT \
	$(ROOTEXECATTRFILES) $(ROOTPROFATTRFILES) $(ROOTUSERATTRFILES) \
	$(ROOTAUTHATTRFILES)

install_h:

clobber clean:

include $(SRC)/cmd/Makefile.targ

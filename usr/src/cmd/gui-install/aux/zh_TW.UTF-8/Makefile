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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../../../Makefile.cmd

IMGURLMAP= \
	imageurl.txt

PNGFILES= \
	install-01.png \
	install-02.png \
	install-03.png \
	install-04.png \
	install-05.png \
	install-06.png

ROOTIMGURLMAP= $(IMGURLMAP:%=$(ROOTGUIINST)/installmessages/zh_TW.UTF-8/%)
ROOTPNGFILES= $(PNGFILES:%=$(ROOTGUIINST)/installmessages/zh_TW.UTF-8/%)


all: $(ROOTPNGFILES) $(ROOTIMGURLMAP)

install: all $(ROOTPNGFILES) $(ROOTIMGURLMAP)

install_h: 

$(ROOTUSRSHARE)/gui-install/installmessages/zh_TW.UTF-8/%: %
	$(INS.file)

clobber clean:

include ../../../Makefile.targ

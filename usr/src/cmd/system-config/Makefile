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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
MSG_DOMAIN = solaris_install_systemconfig

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

SUBDIRS=	helpfiles profile tools xslt

PROGS=		sysconfig

PYMODULES=	__init__.py \
		date_time.py \
		nameservice.py \
		network_nic_configure.py \
		network_nic_select.py \
		network_type.py \
		summary.py \
                support.py \
		timezone.py \
		users.py \
		welcome.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPROGS=	$(PROGS:%=$(ROOTUSRSBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORSCI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORSCI)/%)

ROOTMSGS=       $(POFILE:%=$(ROOTUSRSHAREMSGS)/%)

MSGFILES =	$(PYMODULES) profile/*.py

.KEEP_STATE:

all:	python $(PROGS) $(POFILE)

install: all .WAIT $(ROOTPROGS) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORSOLINSTALL) \
	$(ROOTPYTHONVENDORSCI) \
	$(ROOTPYMODULES) $(ROOTPYCMODULES) \
	$(SUBDIRS) \
	$(ROOTMSGS)


python:
	$(PYTHON) -m compileall -l $(@D)

install_h:

clean: $(SUBDIRS)
	rm -f *.pyc $(POFILE)

clobber: clean

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

sysconfig:

FRC:

include ../Makefile.targ


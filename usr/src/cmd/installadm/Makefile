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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install


SCRIPTS	=	check-server-setup \
		installadm-common \
		setup-image \
		setup-dhcp \
		setup-service \
		setup-sparc \
		setup-tftp-links

CONF	=	ai-httpd.conf

MANIFESTSRC =	server.xml

SVCMETHODSRC =	svc-install-server

PYMODULES=	ai_smf_service.py \
		aimdns_mod.py \
		create_client.py \
		create_service.py \
		delete_client.py \
		delete_service.py \
		installadm_common.py \
		list.py \
                properties.py \
                set_service.py

PYTHON_MODULES=	aimdns.py aimdnsd.py

PYTHON_EXECS =	installadm

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPYMODULES= $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYPROGS=	$(PYTHON_EXECS:%=$(ROOTUSRSBIN)/%)

ROOTSCRIPTS=	$(SCRIPTS:%=$(ROOTUSRLIBINSTALLADM)/%)

ROOTPYSCRIPTS=  $(PYTHON_MODULES:%=$(ROOTUSRLIBINSTALLADM)/%)

VARWEB=		$(CONF:%=$(ROOTVARAIWEB)/%)

SYSMANIFESTS=	$(MANIFESTSRC:%=$(ROOTMANSYSINS)/%)
SVCMETHODS=	$(SVCMETHODSRC:%=$(ROOTLIBSVCMETHOD)/%)
$(SVCMETHODS) :=	FILEMODE= 0555

MSG_DOMAIN = SUNW_INSTALL_INSTALLADM

.KEEP_STATE: 


all: python $(PYTHON_EXECS) \
	$(SCRIPTS) $(CONF) 
	@true

python:
	$(PYTHON) -m compileall -l $(@D)

installadm:	installadm.py
		cp installadm.py installadm

msgs: ${MSG_DOMAIN}.po

clean:
	rm -f $(SCRIPTS) *.pyc $(PYTHON_EXECS)

clobber: clean


install: all .WAIT $(ROOTPYPROGS) $(ROOTPYMODULES) \
	$(ROOTPYCMODULES) $(ROOTPYSCRIPTS) $(SYSMANIFESTS) \
        $(ROOTSCRIPTS) $(ROOTMANSYS) $(ROOTLIBSVCMETHOD) \
	$(SVCMETHODS) $(ROOTPYTHONVENDORINSTALLAI) \
	$(SYSMANIFESTS) $(VARWEB)

include ../Makefile.targ


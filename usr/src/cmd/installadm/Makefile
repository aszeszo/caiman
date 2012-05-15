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
# Copyright (c) 2008, 2012, Oracle and/or its affiliates. All rights reserved.
#

MSG_DOMAIN =	solaris_install_installadm

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

ROOTMSGS=	$(POFILE:%=$(ROOTUSRSHAREMSGS)/%)

SCRIPTS	=	check-server-setup \
		installadm-common \
		setup-image \
		setup-service \
		setup-sparc

CONF	=	ai-httpd-templ.conf

MANIFESTSRC =	server.xml

SVCMETHODSRC =	svc-install-server

PYMODULES=	__init__.py \
		ai_smf_service.py \
		aimdns_mod.py \
		client_control.py \
		create_client.py \
		create_service.py \
		delete_client.py \
		delete_service.py \
		dhcp.py \
		grub.py \
		image.py \
		installadm_common.py \
		list.py \
		rename_service.py \
		service.py \
		service_config.py \
		set_service.py \
		update_service.py

PYTHON_MODULES=	aimdns.py aimdnsd.py

MSGFILES =      $(PYMODULES) $(PYTHON_MODULES) $(PYTHON_EXECS:%=%.py) 

PYTHON_EXECS =	installadm installadm-convert

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

.KEEP_STATE: 


all: python $(PYTHON_EXECS) \
	$(SCRIPTS) $(CONF) $(POFILE)
	@true

python:
	$(PYTHON) -m compileall -l $(@D)

installadm:	installadm.py
		cp installadm.py installadm

installadm-convert:	installadm-convert.py
		cp installadm-convert.py installadm-convert

clean:
	rm -f $(SCRIPTS) *.pyc $(PYTHON_EXECS) $(POFILE)

clobber: clean


install: all .WAIT $(ROOTPYPROGS) $(ROOTPYMODULES) \
	$(ROOTPYCMODULES) $(ROOTPYSCRIPTS) $(SYSMANIFESTS) \
        $(ROOTSCRIPTS) $(ROOTMANSYS) $(ROOTLIBSVCMETHOD) \
	$(SVCMETHODS) $(ROOTPYTHONVENDORINSTALLAI) \
	$(SYSMANIFESTS) $(VARWEB) \
	$(ROOTMSGS)

include ../Makefile.targ


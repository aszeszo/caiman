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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install_h:=	TARGET=	install_h
install:=	TARGET=	install

SRCS	=	installadm.c \
		installadm_util.c

OBJS	=	${SRCS:%.c=${ARCH}/%.o}

SCRIPTS	=	check-server-setup \
		installadm-common \
		setup-image \
		setup-dhcp \
		setup-service \
		setup-sparc \
		setup-tftp-links

HDRS	=	installadm.h

PROGS	=	installadm

CONF	=	ai-httpd.conf

MANIFESTSRC =	server.xml

SVCMETHODSRC =	svc-install-server

PYMODULES= installadm_common.py

PYTHON_MODULES= delete_service.py delete_client.py create_client.py list.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

ROOTPYMODULES= $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPROGS=	$(PROGS:%=$(ROOTUSRSBIN)/%) 

ROOTSCRIPTS=	$(SCRIPTS:%=$(ROOTUSRLIBINSTALLADM)/%)

ROOTPYSCRIPTS=  $(PYTHON_MODULES:%=$(ROOTUSRLIBINSTALLADM)/%)

VARWEB=		$(CONF:%=$(ROOTVARAIWEB)/%)

SYSMANIFESTS=	$(MANIFESTSRC:%=$(ROOTMANSYSINS)/%)
SVCMETHODS=	$(SVCMETHODSRC:%=$(ROOTLIBSVCMETHOD)/%)
$(SVCMETHODS) :=	FILEMODE= 0555

LIBDIR  = $(ROOTADMINLIB)
LIBDIRS = -L${LIBDIR} -L$(SFWLIBDIR) -R$(SFWLIBRDIR) -L$(ROOTUSRLIB)

CFLAGS	  += $(DEBUG_CFLAGS) -Xa
LINTFLAGS  = -umx ${CPPFLAGS}

LDFLAGS  +=	$(DEBUG_CFLAGS) \
		-R$(ROOTADMINLIB:$(ROOT)%=%) $(LIBDIRS)
APPLIBS  +=	-Bdynamic -lsocket -lnsl -lelf

LDLIBS   =	-lscf -laiscf ${APPLIBS}

MSG_DOMAIN = SUNW_INSTALL_INSTALLADM

${ARCH}/%.o: %.c
	${COMPILE.c} -o $@ $<

.KEEP_STATE: 

all: ${ARCH} .WAIT python $(PROGS) \
	$(SCRIPTS) $(CONF)
	@true

${ARCH}:
	@[ -d ${@} ] || (${RM} ${@} ;mkdir -p ${@})

python:
	$(PYTHON) -m compileall -l $(@D)

$(PROGS):  $(OBJS) $(HDRS) .WAIT $(LIBDEP)
	$(LINK.c) -o $@ $(OBJS) $(LDLIBS)
	cp $@ ${ARCH}
	$(POST_PROCESS)

lint: ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

msgs: ${MSG_DOMAIN}.po

clean:
	rm -f $(PROGS) $(SCRIPTS) *.pyc $(PYTHON_EXECS)

clobber: clean

install_h: 

install: all .WAIT $(ROOTPYMODULES) $(ROOTPYCMODULES) $(ROOTPYSCRIPTS) \
	$(SYSMANIFESTS) $(PROGS) $(ROOTPROGS) $(ROOTSCRIPTS) $(ROOTMANSYS) \
	$(ROOTLIBSVCMETHOD) $(SVCMETHODS) $(ROOTPYTHONVENDORINSTALLAI) \
	$(SYSMANIFESTS) $(VARWEB)

include ../Makefile.targ


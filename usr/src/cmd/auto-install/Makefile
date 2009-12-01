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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

PROG	   = auto-install
SUBDIRS=	svc

SRCS =	auto_install.c \
	auto_td.c \
	auto_parse.c \
	auto_parse_manifest.c

PROGS=		ai_get_manifest ai_sd

PYMODULES=	__init__.py ai_parse_manifest.py

HDRS =	auto_install.h

PYCMODULES =	$(PYMODULES:%.py=%.pyc)

OBJS =	${SRCS:%.c=${ARCH}/%.o}

MANIFEST_FILES = ai_manifest.xml \
		 ai_manifest.defval.xml \
		 ai_manifest.rng \
		 default.xml

ROOTPROGS=	$(PROGS:%=$(ROOTUSRBIN)/%)

ROOTPYMODULES=	$(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTMANIFESTS= $(MANIFEST_FILES:%=$(ROOTAUTOINST)/%)  

LIBDIR  = $(ROOTADMINLIB)
LIBDIRS = -L${LIBDIR} -L$(SFWLIBDIR) -R$(SFWLIBRDIR) -L$(ROOTUSRLIB)

INCLUDEDIR = -I. -I${SRC}/lib/liborchestrator -I${SRC}/lib/libtd -I${SRC}/lib/libti -I${SRC}/lib/liblogsvc -I${SRC}/lib/libtransfer -I$(ROOTINCADMIN) -I/usr/include/python2.6

CPPFLAGS  += $(INCLUDEDIR)
CFLAGS	  += $(DEBUG_CFLAGS) -Xa
LINTFLAGS  = -umx ${CPPFLAGS}

LDFLAGS  +=	$(DEBUG_CFLAGS) \
		-R$(ROOTADMINLIB:$(ROOT)%=%) $(LIBDIRS)
LDLIBS  +=	-Bdynamic -ltd -ltransfer -lti -lorchestrator \
		 -lbe -lspmicommon -lnvpair -llogsvc -lelf -lpython2.6

MSG_DOMAIN = SUNW_INSTALL_AUTOINSTALL

${ARCH}/%.o: %.c
	${COMPILE.c} -o $@ $<

FILEMODE= 555
OWNER= root
GROUP= sys

.KEEP_STATE: 

all: ${ARCH} .WAIT $(PROG) python $(PROGS)
	@true

${ARCH}:
	@[ -d ${@} ] || (${RM} ${@} ;mkdir -p ${@})

$(PROG):  $(OBJS) $(HDRS) .WAIT $(LIBDEP)
	$(LINK.c) -o $@ $(OBJS) $(LDLIBS)
	cp $@ ${ARCH}
	$(POST_PROCESS)

${OBJS}: $(HDRS)

install: all .WAIT $(ROOTPROGS) \
	$(ROOTUSRBIN) \
	$(ROOTUSRBINPROG) \
	$(ROOTPYTHONVENDOR) \
	$(ROOTPYTHONVENDORINSTALL) \
	$(ROOTPYTHONVENDORINSTALLAI) \
	$(ROOTMANIFESTS) \
	$(ROOTPYMODULES) $(ROOTPYCMODULES) \
	$(SUBDIRS) \
	.WAIT msgs

python:
	$(PYTHON) -m compileall -l $(@D)

headers:

install_h:

lint: ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

ai_get_manifest: ai_get_manifest.py
	$(CP) ai_get_manifest.py ai_get_manifest

ai_sd: ai_sd.py
	$(CP) ai_sd.py ai_sd

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
	    xgettext -d ${MSG_DOMAIN} -s \
	    	-c "i18n:" - > /dev/null 2>&1

clean: $(SUBDIRS)
	rm -f $(PROGS) $(PYCMODULES) ${PROG} ${PYCMODS} ${ARCH}/* ${MSG_DOMAIN}.po

clobber: clean 

$(SUBDIRS): FRC
	cd $@; pwd; echo $(TARGET); $(MAKE) $(TARGET)

FRC:

include ../Makefile.targ

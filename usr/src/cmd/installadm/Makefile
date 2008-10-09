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

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install_h:=	TARGET=	install_h
install:=	TARGET=	install

SRCS	=	installadm.c

OBJS	=	${SRCS:%.c=${ARCH}/%.o}

SCRIPTS	=	create-client \
		delete-client \
		installadm-common \
		setup-image \
		setup-dhcp \
		setup-service \
		setup-tftp-links

HDRS	=	installadm.h

PROGS	=	installadm

CONF	=	ai-httpd.conf

ROOTPROGS=	$(PROGS:%=$(ROOTUSRSBININSTALLADM)/%)

ROOTSCRIPTS=	$(SCRIPTS:%=$(ROOTUSRSBININSTALLADM)/%)

VARWEB=		$(CONF:%=$(ROOTVARAIWEB)/%)

LIBDIR  = $(ROOTADMINLIB)
LIBDIRS = -L${LIBDIR} -L$(SFWLIBDIR) -R$(SFWLIBRDIR) -L$(ROOTUSRLIB)

CPPFLAGS  += $(INCLUDEDIR)
CFLAGS	  += $(DEBUG_CFLAGS) -Xa
LINTFLAGS  = -umx ${CPPFLAGS}

LDFLAGS  +=	$(DEBUG_CFLAGS) \
		-R$(ROOTADMINLIB:$(ROOT)%=%) $(LIBDIRS)
APPLIBS  +=	-Bdynamic -lsocket -lnsl -lelf

LDLIBS   =	${APPLIBS}

MSG_DOMAIN = SUNW_INSTALL_INSTALLADM

${ARCH}/%.o: %.c
	${COMPILE.c} -o $@ $<

.KEEP_STATE: 

all: ${ARCH} .WAIT $(OBJS) $(SCRIPTS) $(CONF)
	@true

${ARCH}:
	@[ -d ${@} ] || (${RM} ${@} ;mkdir -p ${@})

$(PROG):  $(OBJS) $(HDRS) .WAIT $(LIBDEP)
	$(LINK.c) -o $@ $(OBJS) $(LDLIBS)
	cp $@ ${ARCH}
	$(POST_PROCESS)

lint: ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

msgs: ${MSG_DOMAIN}.po

clean:
	rm -f $(PROGS) $(SCRIPTS)

clobber: clean

install_h: 

install: all .WAIT $(PROGS) $(ROOTPROGS) $(ROOTSCRIPTS) $(VARWEB)

include ../Makefile.targ

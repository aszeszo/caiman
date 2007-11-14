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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.6	07/11/09 SMI"
#
# SPMI Xm library makefile
#

LIBRARY	= libspmixm.a
VERS	= .1

OBJECTS	= \
	xm_adminhelp.o \
	xm_msg.o \
	xm_utils.o

SRCS =	$(OBJECTS:.o=.c)

PRIVHDRS	= xm_utils.h xm_adminhelp.h
EXPHDRS		= spmixm_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

# Set up X information...
MOTIFHOME	:sh= echo "${MOTIFHOME:-/usr/dt}"
OPENWINHOME	:sh= echo "${OPENWINHOME:-/usr/openwin}"
XINCLUDEDIR	= -I${MOTIFHOME}/include -I$(OPENWINHOME)/include

INCLUDE		= -I. \
		  -I${ROOTINCADMIN} \
		  ${XINCLUDEDIR}
CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBXM

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic

static: $(LIBS)

dynamic: $(DYNLIB) $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) .WAIT $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK) .WAIT msgs .WAIT $(INSTMSGS)

install_test:	all .WAIT \
		$(ROOTADMINLIB) .WAIT $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK) .WAIT $(INSTMSGS)

install_h:	$(ROOTUSRINCLEXP)

#
# Since the library may use strings exported from the libraries,
# we could actually end up generating 'extraneous' .po files here
# (e.g. SUNW_INSTALL_LIBAPP.po).
# We delete all but the library's .po here.
#
msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file ${MSG_DOMAIN}.po"
	${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" - >/dev/null 2>&1
	@for i in *.po; do \
		if test $${i} != ${MSG_DOMAIN}.po; then \
			echo "deleting $${i}"; \
			rm -f $${i}; \
		fi; \
	done;

# Create a message file with "translated" test strings.
# Turn the po file into an mo file ready for testing.
msgs_test: ${SRCS} ${HDRS}
	@echo "Making test messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" -m "öýê!" - >/dev/null 2>&1
	@for i in *.po; do \
		if test $${i} != ${MSG_DOMAIN}.po; then \
			echo "deleting $${i}"; \
			rm -f $${i}; \
		fi; \
	done;
	@msgfmt -o ${MSG_DOMAIN}.mo ${MSG_DOMAIN}.po

lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	cstyle $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

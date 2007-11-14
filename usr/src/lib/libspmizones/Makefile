#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END

#
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.2	07/03/08 SMI"
#
# SPMI zones library makefile
#

LIBRARY	= libspmizones.a
VERS	= .1

OBJECTS	= \
	zones_args.o \
	zones_exec.o \
	zones_locks.o \
	zones_paths.o \
	zones_states.o \
	zones_str.o \
	zones_utils.o \
	zones_lofs.o \
	zones.o

SRCS =	$(OBJECTS:.o=.c)

PRIVHDRS	= \
	spmizones_lib.h \
	zones_strings.h

EXPHDRS		= spmizones_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I../libspmicommon
CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=
SOFLAGS		+= -ldl

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBZONES

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

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" - >/dev/null 2>&1
 
# Create a message file with "translated" test strings.
# Turn the po file into an mo file ready for testing.
msgs_test: ${SRCS} ${HDRS}
	@echo "Making test messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" -m "öýê!" - >/dev/null 2>&1
	@msgfmt -o ${MSG_DOMAIN}.mo ${MSG_DOMAIN}.po

lint:  ${SRCS} ${HDRS}
	${LINT.c} ${SRCS}

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	cstyle $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

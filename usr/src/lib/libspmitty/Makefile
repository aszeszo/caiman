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
#
# SPMI Xm library makefile
#

LIBRARY	= libspmitty.a
VERS	= .1

OBJECTS	= \
	tty_color.o \
	tty_help.o \
	tty_init.o \
	tty_list.o \
	tty_menu.o \
	tty_msg.o \
	tty_utils.o \
	tty_wins.o

SRCS =	$(OBJECTS:.o=.c)

PRIVHDRS	= \
	tty_strings.h \
	tty_utils.h
EXPHDRS		= spmitty_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I. -I${ROOTINCADMIN}
CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBTTY

.KEEP_STATE:

all: $(HDRS) .WAIT static dynamic

static: $(LIBS)

dynamic: $(DYNLIB) $(DYNLIBLINK)

install:	all .WAIT \
		$(ROOTADMINLIB) .WAIT $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
		$(ROOTADMINLIBDYNLIBLINK) .WAIT msgs .WAIT $(INSTMSGS)

install_test:	all .WAIT \
		$(ROOTADMINLIB) $(ROOTADMINLIBS) $(ROOTADMINLIBDYNLIB) \
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
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
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

cstyle:	$(SRCS) $(HDRS)
	cstyle $(SRCS) $(HDRS)

depend:
	makedepend -- ${CPPFLAGS} ${CFLAGS} -- ${SRCS}

include ../Makefile.targ
# DO NOT DELETE THIS LINE -- make depend depends on it.
# makedepend dependencies modified using:
# /usr/rmtc/misc/spmi/bin/deps.pl, Version: 1.2
# on Tue Apr  9 14:45:21 US/Mountain 1996

${ARCH}/tty_color.o: spmitty_api.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_color.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_color.o: tty_utils.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_help.o: spmitty_api.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_help.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_help.o: tty_utils.h tty_strings.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_init.o: spmitty_api.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_init.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_init.o: tty_utils.h tty_strings.h
${ARCH}/tty_intro.o: spmitty_api.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_intro.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_intro.o: tty_utils.h tty_strings.h
${ARCH}/tty_menu.o: spmitty_api.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_menu.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_menu.o: tty_utils.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_msg.o: spmitty_api.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_msg.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_msg.o: tty_utils.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_utils.o: spmitty_api.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_utils.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_utils.o: tty_utils.h tty_strings.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmicommon_api.h
${ARCH}/tty_wins.o: spmitty_api.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmiapp_api.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmistore_api.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmisoft_api.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/soft_hash_table.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmiapp_strings.h
${ARCH}/tty_wins.o: ${ROOTINCADMIN}/spmiapp_ui_msg.h
${ARCH}/tty_wins.o: tty_utils.h tty_strings.h

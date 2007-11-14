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
#ident	"@(#)Makefile	1.14	07/11/08 SMI"
#
# SPMI software library makefile
#

LIBRARY	= libspmisoft.a
VERS	= .1

OBJECTS	= \
	soft_admin.o \
	soft_arch.o \
	soft_choosemedia.o \
	soft_depend.o \
	soft_do_upgrade.o \
	soft_dump.o \
	soft_find_modified.o \
	soft_free.o \
	soft_geo.o \
	soft_hash_table.o \
	soft_install.o \
	soft_launcher.o \
	soft_locale.o \
	soft_locale_lookup.o \
	soft_media.o \
	soft_module.o \
	soft_pipe.o \
	soft_pkghist.o \
	soft_platform.o \
	soft_prod.o \
	soft_prodsel.o \
	soft_progress.o \
	soft_service.o \
	soft_sp_calc.o \
	soft_sp_load.o \
	soft_sp_space.o \
	soft_sp_spacetab.o \
	soft_sp_util.o \
	soft_webstart_tables.o \
	soft_webstart_util.o \
	soft_swi_admin.o \
	soft_swi_arch.o \
	soft_swi_choosemedia.o \
	soft_swi_depend.o \
	soft_swi_dump.o \
	soft_swi_geo.o \
	soft_swi_install.o \
	soft_swi_launcher.o \
	soft_swi_locale.o \
	soft_swi_media.o \
	soft_swi_module.o \
	soft_swi_platform.o \
	soft_swi_prod.o \
	soft_swi_prodsel.o \
	soft_swi_sp_space.o \
	soft_swi_sp_util.o \
	soft_swi_update_actions.o \
	soft_swi_util.o \
	soft_swi_webstart_tables.o \
	soft_swi_webstart_util.o \
	soft_swi_v_version.o \
	soft_templates.o \
	soft_update_actions.o \
	soft_util.o \
	soft_version.o \
	soft_view.o \
	soft_walktree.o

SRCS = $(OBJECTS:.o=.c)

PRIVHDRS = \
	soft_templates.h \
	soft_version.h \
	spmisoft_lib.h \
	sw_pipe.h \
	sw_space.h \
	sw_swi.h \
	sw_swi_defines.h
EXPHDRS = \
	spmisoft_api.h \
	soft_hash_table.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I../libspmicommon -I../libspmizones -I../libpkg \
			-I../libgendb -I$(SFWINCDIR) -I.
CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBSOFT

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

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file ${MSG_DOMAIN}.po"
	@${COMPILE.c} -C -E ${SRCS} 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -s \
			-c "i18n:" - >/dev/null 2>&1
	@#
	@# Add metacluster names to .po file so they can be localized.
	@# These strings are supplied by RE via the .clustertoc file.
	@# If those strings change, then these strings must also change.
	@#
	@echo msgid \"Entire Distribution plus OEM support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Entire Distribution\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Developer System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"End User System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Core System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Reduced Networking Core System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po

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

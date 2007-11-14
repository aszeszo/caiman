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
#ident	"@(#)Makefile	1.31	07/10/09 SMI"
#
# SPMI service library makefile
#

LIBRARY	= libspmisvc.a
VERS	= .1

OBJECTS	= \
	svc_capability.o \
	svc_checkpoint.o \
	svc_default_swap.o \
	svc_dfltmnt.o \
	svc_do_upgrade.o \
	svc_dsr_archive_list.o \
	svc_extra_pkg.o \
	svc_fdiskconfig.o \
	svc_flash.o \
	svc_flash_http.o \
	svc_flash_http_old.o \
	svc_flash_lf.o \
	svc_flash_ld.o \
	svc_flash_nfs.o \
	svc_flash_tape.o \
	svc_flash_ftp.o \
	svc_fs_space.o \
	svc_global.o \
	svc_kernel.o \
	svc_mountall.o \
	svc_oslist.o \
	svc_patch.o \
	svc_resource.o \
	svc_resourceobj.o \
	svc_sdiskconfig.o \
	svc_sdiskfreespace.o \
	svc_service_free.o \
	svc_services.o \
	svc_setaction.o \
	svc_slice_list.o \
	svc_sp_free_results.o \
	svc_sp_print_results.o \
	svc_templates.o \
	svc_updateconfig.o \
	svc_updatedisk.o \
	svc_updateserial.o \
	svc_updatesoft.o \
	svc_updatesys.o \
	svc_upg_recover.o \
	svc_upgradeable.o \
	svc_vfstab.o \
	svc_be.o \
	svc_write_script.o

SRCS =	$(OBJECTS:.o=.c)

PRIVHDRS	= spmisvc_lib.h \
		  svc_dsr_archive_list_in.h \
		  svc_strings.h \
		  svc_templates.h
EXPHDRS		= spmisvc_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I../libspmisoft \
		   -I../libspmistore \
		   -I../libspmicommon \
		   -I../libspmiapp \
		   -I../libspmizones \
		   -I.

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}


NEEDEDLIBS	= 	-lspmiapp -lspmisvc -lspmistore -lspmisoft \
			-lspmicommon -ldl -ldevinfo -lsocket -lnsl -ladm \
			-lgen

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBSVC

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


driver: objs/$(ARCH)/driver.o objs/$(ARCH)/$(LIBRARY)
		$(CC) -o objs/$(ARCH)/$@ objs/$(ARCH)/$@.o\
		-u print_disk \
		$(NEEDEDLIBS)

svc_upgradeable: objs/$(ARCH)/$(LIBRARY)
		$(CC) -o objs/$(ARCH)/$@ -DMODULE_TEST $@.c $(INCLUDE) \
		-R$(ROOTADMINLIB:$(ROOT)%=%) -u print_disk \
		$(NEEDEDLIBS)
LDFLAGS		+= $(DEBUG_CFLAGS) -R$(ROOTADMINLIB:$(ROOT)%=%) ${LIBDIRS}

msgs: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${SRCS} ${HDRS}
	@echo "Making messages file $(MSG_DOMAIN)"
	@if [ -f $(MSG_DOMAIN).po ] ; then rm $(MSG_DOMAIN).po ; fi
	@#
	@# svc_templates.c is essentially a shell script, so get messages
	@# from it as if it were one.
	@#
	@sed 's/\\\\n/\\n/g' svc_templates.c > svc_templatesTMP.c
	@$(ROOTADMIN)/bin/xgetsh -d $(MSG_DOMAIN) svc_templatesTMP.c
	@#
	@# Get messages from the other C files
	@#
	@TOCPP=`echo ${SRCS} |sed -e 's/\<svc_templates.c\>//g'` ; \
	${COMPILE.c} -C -E $$TOCPP 2>/dev/null | \
		xgettext -d ${MSG_DOMAIN} -j \
			-c "i18n:" - >/dev/null 2>&1
	@#
	@# Add cluster names to .po file so that they are localized.
	@#
	@echo msgid \"Entire Distribution plus OEM support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Server Distribution\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Developer System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"End User System Support\" >> ${MSG_DOMAIN}.po
	@echo msgstr >> ${MSG_DOMAIN}.po
	@echo msgid \"Core System Support\" >> ${MSG_DOMAIN}.po
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

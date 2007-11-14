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
#ident	"@(#)Makefile	1.14	07/10/09 SMI"
#
# SPMI storage library makefile
#

LIBRARY	= libspmistore.a
VERS	= .1

OBJECTS	= \
	store_boot.o \
	store_bootobj.o \
	store_check.o \
	store_common.o \
	store_debug.o \
	store_disk.o \
	store_fdisk.o \
	store_initdisk.o \
	store_rwdisklist.o \
	store_sdisk.o \
	store_svm.o

SRCS =	$(OBJECTS:.o=.c)

PRIVHDRS	= spmistore_lib.h store_strings.h
EXPHDRS		= spmistore_api.h
HDRS		= $(EXPHDRS) $(PRIVHDRS)

include ../Makefile.lib

INCLUDE		 = -I../libspmicommon -I../libspmizones

CPPFLAGS	+= ${INCLUDE} -D${ARCH}
CFLAGS		+= $(DEBUG_CFLAGS) -Xa ${CPPFLAGS}
LDFLAGS		+=

# Need a runtime search path so we can find libsvm.so (see store_svm.c)
SOFLAGS		+= -R$(ROOTADMINLIB:$(ROOT)%=%)

LINTERR		= lint_errors
LINTFILES	= ${SRCS:%.c=${ARCH}/%.ln}
LINTFLAGS	= -umx ${CPPFLAGS}

CLOBBERFILES	= *.po *.mo

MSG_DOMAIN	= SUNW_INSTALL_LIBSTORE

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

driver:	objs/$(ARCH)/driver.o objs/$(ARCH)/$(LIBRARY)
		$(CC) -o objs/$(ARCH)/$@ -DMODULE_TEST $@.c $(INCLUDE) \
			-u print_disk \
			objs/$(ARCH)/$(LIBRARY) \
			-ldl -ldevinfo -lnsl -ladm \
			-Bstatic -lspmicommon

store_initdisk:	objs/$(ARCH)/$(LIBRARY)
		$(CC) -o objs/$(ARCH)/$@ -DMODULE_TEST $@.c $(INCLUDE) \
			-u print_disk \
			objs/$(ARCH)/store_initdisk.o \
			objs/$(ARCH)/$(LIBRARY) \
			-ldl -ldevinfo -lnsl -ladm \
			-Bstatic -lspmicommon

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

lint:	lint_SRCS

cstyle:	$(SRCS) $(PRIVHDRS) $(PUBHDRS)
	cstyle $(SRCS) $(PRIVHDRS) $(PUBHDRS)

include ../Makefile.targ

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
#ident	"@(#)Makefile	1.11	07/05/10 SMI"
#

OBJECTS	=	\
		flock.o \
		etheraddr.o \
		sysdep.o \
		uuid.o \
		main.o

SRCS	=	$(OBJECTS:.o=.c)

HDRS	=	uuid_strings.h

PROG	=	makeuuid

ROOTUSRBINPROGS=$(PROG:%=$(ROOTUSRBIN)/%)

# Global definitions
include ../Makefile.cmd

MSG_DOMAIN	=	SUNW_INSTALL_UUID
MSG_DIR		=	.

# Where to find header files
LOCAL	=
RELATED	=
GENERAL	=

LDLIBS	+=	-lsocket
CFLAGS	+=	$(DEBUG_CFLAGS)

CPPFLAGS	=	$(LOCAL:%=-I%) $(RELATED:%=-I%) $(GENERAL:%=-I%) \
			-DTEXT_DOMAIN=\"${MSG_DOMAIN}\" \
			-DPROG_NAME=\"${PROG}\" \
			$(CPPFLAGS.master)

all:		$(ARCH) $(PROG)

$(PROG):	$(ARCH) $(OBJECTS)
		$(PURIFY) $(LINK.c) -o $@ $(OBJECTS) $(LDFLAGS) $(LDLIBS)
		cp $@ $(ARCH)

${ARCH}:
	[ -d ${ARCH} ] || (rm -f ${ARCH} ;mkdir -p ${ARCH})

${ARCH}/%.o: %.c
	${COMPILE.c} -o $@ $<


install:	all .WAIT $(ROOTUSRBINPROGS) .WAIT messages .WAIT $(INSTMSGS)

install_h:

CLOBBERFILES+=	$(MSG_DOMAIN).po

clean:
		$(RM) $(PICS) $(OBJECTS) *.o *~

messages: $$(SRCS)
	@echo "Making messages file $(MSG_DIR)/$(MSG_DOMAIN)"
	@${COMPILE.c} -C -E $(SRCS) $(HDRS) 2>/dev/null | \
		xgettext -d $(MSG_DOMAIN) -c "i18n:" \
			-p $(MSG_DIR) - >/dev/null 2>&1
	cp ${MSG_DOMAIN}.po ${ROOTUSRMENU}

lint:	lint_SRCS

include ../Makefile.targ


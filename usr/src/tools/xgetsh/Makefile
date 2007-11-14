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
#ident	"@(#)Makefile	1.17	07/05/10 SMI"
#

PROG = xgetsh

SRCS= xgetsh.c nhash.c ncmsg.c

HDRS= nhash.h xgetsh.h

CFLAGS += $(DEBUG_CFLAGS) -Xa

OBJS=${SRCS:%.c=%.o}

include ../Makefile.cmd

LIBS=-lintl

.KEEP_STATE:

all: ${PROG} 

install: all $(ROOTADMINBINPROG)

${PROG}: ${OBJS} ${HDRS}
	$(LINK.c) -o $@ $(OBJS) $(LIBS)

${OBJS}:	${HDRS}

lint:	lint_SRCS

clean:
	-rm -f $(OBJS)

include ../Makefile.targ

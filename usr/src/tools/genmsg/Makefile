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

#
# Copyright 1995 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.5	06/02/27 SMI"
#

PROG = genmsg

SRCS= 

HDRS=

CFLAGS=

LINTERR=lint_errors

OBJS=${SRCS:%.c=%.o}

include ../Makefile.cmd

LIBS=-lintl

.KEEP_STATE:

all: ${PROG} 
	@true

install: all $(ROOTADMINBINPROG)

${PROG}: docp

${OBJS}:	${HDRS}

lint:

cleanlint:
	-rm ${LINTERR}

clean:
	-rm -f core errs *.o *.BAK ${LINTERR} ${OBJS}

docp:
	@if [ "`uname -p`" = "sparc" ]; then \
		${RM} ${PROG}; ${CP} ${PROG}.sparc ${PROG};  \
         elif [ "`uname -p`" = "i386" ]; then \
                 ${RM} ${PROG}; ${CP} ${PROG}.i386 ${PROG}; \
         elif [ "`uname -p`" = "ppc" ]; then \
                 ${RM} ${PROG}; ${CP} ${PROG}.ppc ${PROG}; \
	 elif [ 1 ]; then \
		echo "error building genmsg"; exit 1; \
         fi

include ../Makefile.targ

.WAIT:

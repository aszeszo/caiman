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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

ARCH =		$(TARGET_ARCH:-%=%)

PROG =		tbeadm


OBJS =		tbeadm.o
SRCS =		$(OBJS:%.o=../%.c)

INCLUDE =	-I. -I../

STATICDEPLIBS	= ../objs/$(ARCH)/libbe.a
STATICLDLIBS	+= -L/lib -L../objs/$(ARCH) -lzfs -lnvpair -lbe\
		-Bstatic -lbe -Bdynamic

DEPLIBS		= ../objs/$(ARCH)/libbe.so.1
LDLIBS +=	-L/lib -L../pics/$(ARCH) -lzfs -lnvpair -lbe

CPPFLAGS +=	-D_LARGEFILE64_SOURCE=1 -D_REENTRANT ${INCLUDE}
CFLAGS +=	-g -DDEBUG


$(PROG):	$(OBJS) $(STATICDEPLIBS)
		$(LINK.c) -o $@ $(OBJS) $(STATICLDLIBS)
		$(POST_PROCESS)

all:		$(PROG)

install_h:

install:	all $(ROOTPROG)

lint:
	$(LINT.c) $(SRCS) $(LDLIBS)

clobber: clean
	$(RM) tbeadm.o

clean:
	$(RM) tbeadm 


#
#CDDL HEADER START
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

ARCH =		$(TARGET_ARCH:-%=%)

PROG =		tlogger

include ../../Makefile.lib

OBJS =		tlogger.o\
		test_setup.o \
		test_set_logger_class.o\
		test_get_logger.o \
		test_set_log_level.o \
		test_addhandler.o \
		test_addhandler_fail.o\
		test_add_progress_handler.o \
		test_addstrmhandler.o \
		test_report_progress.o \
                test_report_progress_fail.o \
		test_log_message.o \
		test_transfer_destonly.o \
		test_transfer_srclog.o \
		test_close_logging.o

SRCS =		$(OBJS:%.o=%.c)

INCLUDE =	-I. -I../ -I/usr/include/python2.6


DEPLIBS		= ../pics/$(ARCH)/logger.so.1
LDLIBS +=	-L/lib -L../pics/$(ARCH) -R ../pics/$(ARCH) -llogger \
		-L$(ROOTADMINLIB) -R$(ROOTADMINLIB:$(ROOT)%=%) \
		-lerrsvc -lpython2.6 -lnvpair -Bdynamic

CPPFLAGS +=	-D_LARGEFILE64_SOURCE=1 -D_REENTRANT ${INCLUDE}
CFLAGS +=	-g -DNDEBUG


$(PROG):	$(OBJS)
		$(LINK.c) -o $@ $(OBJS) $(LDLIBS)
		$(POST_PROCESS)

all:		$(PROG)

install_h:

install:	all $(ROOTPROG)

lint:
	$(LINT.c) $(SRCS) $(LDLIBS)

clobber: clean

clean:
	$(RM) $(OBJS) $(PROG)


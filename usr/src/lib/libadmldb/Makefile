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
#ident	"@(#)Makefile	1.19	07/11/09 SMI"
#

LIBRARY   =	libadmldb.a
VERS	  =	.2
MSGMASTER =	msg_master
MSG	=	admldb_msgs
MSG_DOMAIN =	SUNW_ADM_LIBLDB
MSGPO	=	$(MSG_DOMAIN).po

EXPHDRS   =	cl_database_parms.h admldb.h admldb_impl.h $(MSG).h

OBJECTS =	$(MSG).o admldb_impl.o admdb_tbl.o admldb_nis.o admldb_ufs.o \
		tbl_defs.o admldb.o nis_plus_ufs_policy.o

SRCS      =	$(OBJECTS:.o=.c)

MSGSRCS	=	$(MSG).c $(MSG).h

include ../Makefile.lib

CLEANFILES=	$(MSGSRCS)

CLOBBERFILES=	$(MSGPO) $(DYNLIB) $(DYNLIBLINK)

TXTS =

# Following variables define where to find header files
LOCAL    =	.
RELATED  =
GENERAL  =	$(ROOTINCADMIN)
CPPFLAGS =	$(LOCAL:%=-I%) $(RELATED:%=-I%) $(GENERAL:%=-I%) \
		$(CPPFLAGS.master)
# CFLAGS +=	$(DEBUG_CFLAGS) -DNIS_DEBUG
CFLAGS +=	$(DEBUG_CFLAGS)

.KEEP_STATE:

# $(MSGSRCS) are generated from $(MSGMASTER) so they musn't be processed
# in parallel.
.NO_PARALLEL:	$(MSGSRCS)

all: 		static dynamic $(TXTS)

static:		$(LIBS)

dynamic:	$(DYNLIB) $(DYNLIBLINK)


install:	all .WAIT $(ROOTADMINLIB) .WAIT $(ROOTADMINLIBS) \
		$(ROOTADMINLIBDYNLIB) $(ROOTADMINLIBDYNLIBLINK) .WAIT \
		$(INSTMSGS)

# build xxx_message.c and xxx_message.h files
#	also build the xxx_message.po file that will be used as input to the
#	localization process -- not sure where to put it or how to distribute it
$(MSGSRCS):	$(MSGMASTER)
		$(MKMSGS) -d $(MSG_DOMAIN) < $(MSGMASTER)

install_h:	$(ROOTUSRINCLEXP)

lint:		$(LINTLIB)

include ../Makefile.targ


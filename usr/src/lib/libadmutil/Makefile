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
# classes/lib/libadmutil/Makefile
#

LIBRARY   =	libadmutil.a
VERS	  =	.2

MSGMASTER =	
MSG	  =	
TEXTDOMAIN =    $(MSG)
MSGPO	  =	$(TEXTDOMAIN).po
MSGOBJ	=	pics/$(MSG).o
MSGLIB	=	lib$(MSG).so.1

EXPHDRS   =	admutil.h

IMPLHDRS  =	admutil_priv.h

OBJECTS =	\
		config_nsswitch.o \
		config_nsprofile.o \
		config_resolv.o \
		config_krb.o \
		config_nfs4.o \
		db_entry.o \
		get_domain.o \
		get_net_if_ip_netmask.o \
		get_net_if_ip_addr.o \
		get_net_if_names.o \
		get_nodename.o \
		is_local_host.o \
		modify.o \
		set_domain.o \
		set_net_if_ip_netmask.o \
		set_net_if_status.o \
		set_nodename.o \
		set_run_level.o \
		set_timezone.o \
		string_op.o \
		util.o \
		valid.o

SRCS      =	$(OBJECTS:.o=.c)
SRCMSGS	=	$(MSG).c $(MSG).h

include ../Makefile.lib

CLEANFILES=	valid_test.o $(SRCMSGS)

CLOBBERFILES=	$(DYNLIB) $(DYNLIBLINK) valid_test *% $(MSGPO)

# Following variables define where to find header files
LOCAL    =	.
RELATED  =
GENERAL  =	$(ROOTINCADMIN)
CPPFLAGS =	$(LOCAL:%=-I%) $(RELATED:%=-I%) $(GENERAL:%=-I%) \
		$(CPPFLAGS.master)

CFLAGS +=	$(DEBUG_CFLAGS)

.KEEP_STATE:

# $(SRCMSGS) are generated from $(MSGMASTER) so they musn't be processed
# in parallel.
.NO_PARALLEL:	$(SRCMSGS)

all: 		static dynamic

static:		$(LIBS)

dynamic:	$(DYNLIB) $(DYNLIBLINK)

install:	all .WAIT $(ROOTADMINLIB) $(ROOTADMINLIBS) \
		$(ROOTADMINLIBDYNLIB) $(ROOTADMINLIBDYNLIBLINK)

valid_test:= LDFLAGS =
valid_test:	dynamic valid_test.o
		$(LINK.c) -o $@ valid_test.o  -R. -L. -ladmutil -lsocket -lgen

# build xxx_message.o file for inclusion in links of individual methods
$(MSGOBJ):	$(SRCMSGS)

# build xxx_message.c and xxx_message.h files
#       also build the xxx_message.po file that will be used as input to the
#       localization process -- not sure where to put it or how to distribute it
$(SRCMSGS):	$(MSGMASTER)
		$(MKMSGS) -d $(TEXTDOMAIN) < $(MSGMASTER)

install_h:	$(ROOTUSRINCLEXP)

lint:		$(LINTLIB)

# EXPORT DELETE START
# Special target to clean up the source tree for export distribution
# Warning: This target changes the source tree
EXPORT_SRC:
	sed -e "/^# EXPORT DELETE START/,/^# EXPORT DELETE END/d" \
		< Makefile > Makefile+
	$(MV) Makefile+ Makefile
	$(CHMOD) 444 Makefile

# EXPORT DELETE END

include ../Makefile.targ


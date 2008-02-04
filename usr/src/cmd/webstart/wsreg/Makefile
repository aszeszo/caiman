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
#ident	"@(#)Makefile	1.35	07/05/10 SMI"
#

LIBRARY =	libwsreg.so
VERS	=	.1

MSG_DOMAIN=     SUNW_INSTALL_WSREG

HDRS =		article.h \
		article_id.h \
		boolean.h \
		cluster_file_io.h \
		conversion.h \
		ds_article_input_stream.h \
		file_reader.h \
		file_token.h \
		file_util.h \
		hashtable.h \
		list.h \
		localized_strings.h \
		pkg_db.h \
		pkg_db_io.h \
		prodreg_cli.h \
		progress.h \
		reg_comp.h \
		reg_query.h \
		revision.h \
		simple_registry.h \
		stack.h \
		string_map.h \
		string_util.h \
		unz_article_input_stream.h \
		wsreg.h \
		wsreg_private.h \
		xml_file_context.h \
		xml_file_io.h \
		xml_reg.h \
		xml_reg_io.h \
		xml_tag.h \
		zlib_article_input_stream.h

OBJECTS	=	\
		article.o \
		article_id.o \
		cluster_file_io.o \
		conversion.o \
		file_reader.o \
		file_token.o \
		file_util.o \
		hashtable.o \
		list.o \
		pkg_db_io.o \
		progress.o \
		reg_comp.o \
		reg_query.o \
		revision.o \
		simple_registry.o \
		stack.o \
		string_map.o \
		string_util.o \
		unz_article_input_stream.o \
		wsreg.o \
		xml_file_context.o \
		xml_file_io.o \
		xml_reg.o \
		xml_reg_io.o \
		xml_tag.o

${OBJECTS}:	$(HDRS)

REGOBJS	=	\
		Regconvert.o 

PRDOBJS		= \
		prodreg.o \
		prodreg_browse.o \
		prodreg_browse_num.o \
		prodreg_info.o \
		prodreg_list.o \
		prodreg_uninst.o \
		prodreg_unreg.o \
		prodreg_util.o \
		prodreg_reg.o

SRCS  =		$(OBJECTS:.o=.c)
REGSRC =	Regconvert.c 
PRODSRC =	prodreg.c

PROG	=	prodreg

ROOTUSRBINPROG=$(PROG:%=$(ROOTUSRBIN)/%)

INSTALLPROG =	regconvert

ROOTINSTALLPROG=$(INSTALLPROG:%=$(ROOTINSTALLBIN)/%)

PRODREGHDRS	=	wsreg.h wsreg_private.h list.h boolean.h

WBEMINCLUDEHDRS= $(PRODREGHDRS:%=$(ROOTWBEMINCLUDE)/%)

EXPHDRS		=	wsreg.h

# Global definitions
include $(SRC)/cmd/webstart/Makefile.lib

#
# To build a debug version, remove -DNDEBUG from CPPFLAGS
# and add -g and -xs to the DEBUGFLAGS.  The line adding
# debug symbols has been commented out for the release
# version.
#

# Where to find header files
LOCAL	=
RELATED	=
GENERAL	=
CPPFLAGS=	$(LOCAL:%=-I%) $(RELATED:%=-I%) $(GENERAL:%=-I%) \
		-DTEXT_DOMAIN=\"${MSG_DOMAIN}\" \
		-DNDEBUG \
		$(CPPFLAGS.master)

LDFLAGS +=	-R/usr/lib -lm -lsecdb -ladm
LDLIBS	+=	-L$(ROOTUSRLIB) -L$(ROOTADMINLIB)
INCLUDES=	-I$(ROOTINCADMIN)
CPPFLAGS +=	$(INCLUDES) -O
CLOBBERFILES +=	$(DYNLIB) $(DYNLIBLINK) $(PROG) $(INSTALLPROG) $(MSG_DOMAIN).po

regconvert:	$(REGOBJS) $(HDRS)
		$(PURIFY) $(LINK.c) -o $@ $(REGOBJS) $(LDFLAGS) $(LDLIBS) -lwsreg -lc

prodreg:	$(PRDOBJS) $(HDRS)
		$(PURIFY) $(LINK.c) -o $@ $(PRDOBJS) $(LDFLAGS) $(LDLIBS) -lwsreg

all:		dynamic $(PROG) $(INSTALLPROG)

messages: ${MSG_DOMAIN}.po

${MSG_DOMAIN}.po: ${REGSRC} ${PRODSRC} ${HDRS} $$(SRCS)
	@echo "Making messages file $(MSG_DOMAIN).po"
	@${COMPILE.c} -C -E ${REGSRC} ${PRODSRC} $(SRCS) 2>/dev/null | \
		xgettext -d $(MSG_DOMAIN) -c "i18n:" - >/dev/null 2>&1
	cp ${MSG_DOMAIN}.po ${ROOTUSRMENU}

install:	all $(ROOTUSRBINPROG) $(ROOTINSTALLPROG) $(ROOTUSRINCHDRS) \
		$(WBEMINCLUDEHDRS) messages

install_h:	$(ROOTUSRINCHDRS) $(WBEMINCLUDEHDRS)

dynamic:	$(DYNLIB) $(DYNLIBLINK) $(ROOTUSRLIBDYNLIBS) $(ROOTUSRLIBDYNLIBLINK)

clean:
		$(RM) $(PICS) $(PRDOBJS) $(REGOBJS)

include ../Makefile.targ

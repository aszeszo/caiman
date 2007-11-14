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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
#ident	"@(#)Makefile	1.5	07/08/13 SMI"
#

#
# lib/libpkgdb/Makefile
#
LIBRARY= libpkgdb.a
VERS=    .1

OBJECTS=attach.o \
	auth.o \
	btree.o \
	btree_rb.o \
	build.o \
	copy.o \
	delete.o \
	encode.o \
	expr.o \
	func.o \
	hash.o \
	insert.o \
	main.o \
	opcodes.o \
	os.o \
	pager.o \
	parse.o \
	pragma.o \
	printf.o \
	random.o \
	select.o \
	shell.o \
	table.o \
	tokenize.o \
	trigger.o \
	update.o \
	util.o \
	vacuum.o \
	vdbe.o \
	where.o \

include ../Makefile.lib

CFLAGS +=	-Xt -xspace -W0,-Lt
SOFLAGS=      -h $(SOLIBNAME)
CPPFLAGS=     -DNDEBUG=1 -I. $(CPPFLAGS.master) -D_FILE_OFFSET_BITS=64
DYNFILES=     config.h parse.c parse.h opcodes.c opcodes.h
CLEANFILES=   lempar.c parse.out y.tab.c yacc.acts yacc.debug yacc.tmp
CLOBBERFILES= $(DYNFILES) lemon
TEXT_DOMAIN=  SUNW_PKG_LIBPKG

POFILE = libdbpkg.po
POFILES= $(OBJECTS:%.o=%.po)

.KEEP_STATE:

# Build dynamically generated files
config.h:
	$(CC) -o def_ptr_sz tool/def_ptr_sz.c
	./def_ptr_sz > config.h
	echo >> config.h
	rm -f def_ptr_sz

lemon:		tool/lemon.c tool/lempar.c
	$(CC) -o lemon tool/lemon.c
	cp -f tool/lempar.c .

parse.h:	parse.c

parse.c:	parse.y lemon
	./lemon parse.y
	$(RM) -f parse.out y.tab.c yacc.acts yacc.debug yacc.tmp

opcodes.c:	vdbe.c
	echo '/* Automatically generated file.	Do not edit */' >opcodes.c
	echo 'char *sqliteOpcodeNames[] = { "???", ' >>opcodes.c
	grep '^case OP_' vdbe.c | \
	  sed -e 's/^.*OP_/  "/' -e 's/:.*$$/", /' >>opcodes.c
	echo '};' >>opcodes.c

opcodes.h:	vdbe.h
	echo '/* Automatically generated file.	Do not edit */' >opcodes.h
	grep '^case OP_' vdbe.c | \
	  sed -e 's/://' | \
	  awk '{printf "#define %-30s %3d\n", $$2, ++cnt}' >>opcodes.h


all:    $(DYNFILES) .WAIT static dynamic

install_h:

static: $(LIBS)

$(LINTLIB) :=	SRCS=$(LINTSRC)

dynamic:	$(DYNLIB) $(LINTLIB)

_msg:   $(MSGDOMAIN) $(POFILE)
	$(RM) $(ROOTUSRLIBMSGS)/$(TEXT_DOMAIN).po
	cp $(POFILE) $(ROOTUSRLIBMSGS)

$(POFILE):      $(POFILES)
	$(RM)    $@
	cat $(POFILES) > $@

install: all .WAIT \
	$(ROOTUSRLIBS) $(ROOTUSRLIBDYNLIB) $(ROOTUSRLIBDYNLIBLINK) \
	$(ROOTUSRLINT)

lint:	lint_SRCS

$(MSGDOMAIN):
	$(INS.dir)

# include library targets
include ../Makefile.targ

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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

PYMODULES=	AI_database.py \
			verifyXML.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

WEBSERVER_FILES= \
			AI.db

SCHEMAS=	criteria_schema.rng

PYTHON_EXECS= delete-manifest \
			  list-manifests \
			  publish-manifest \
			  webserver

ROOTPYMODULES= $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTWEBSERVER_FILES= $(WEBSERVER_FILES:%=$(ROOTVARAIWEB)/%)

ROOTPROGS= $(PYTHON_EXECS:%=$(ROOTUSRLIBINSTALLADM)/%)

ROOTSCHEMAS= $(SCHEMAS:%=$(ROOTAUTOINST)/%)

all: python $(PYTHON_EXECS)

clean:
	$(RM) $(PYTHON_EXECS) *.pyc
	$(RM) AI.db

clobber: clean

install: all .WAIT $(ROOTPROGS) \
			$(ROOTPYTHONVENDORINSTALLAI) \
			$(ROOTPYMODULES) \
			$(ROOTPYCMODULES) \
			$(ROOTVARINSTADM) \
			$(ROOTWEBSERVER_FILES) \
			$(ROOTSCHEMAS)

python:
	$(PYTHON) -m compileall -l $(@D)

$(PYTHON_EXECS):
	$(CP) $(@).py $(@)

#
# Note that the names of the database items below must be in lower-case letters
# except for the MIN or MAX prefixes used in range names.
#
AI.db:
	$(ECHO) 'CREATE TABLE manifests (name TEXT, instance INTEGER, arch TEXT, MINmac INTEGER, MAXmac INTEGER, MINipv4 INTEGER, MAXipv4 INTEGER, cpu TEXT, platform TEXT, MINnetwork INTEGER, MAXnetwork INTEGER, MINmem INTEGER, MAXmem INTEGER);' | /usr/bin/sqlite3 ./AI.db

include ../Makefile.targ

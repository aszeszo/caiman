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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

include ../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

PYMODULES=	AI_database.py \
		common_profile.py \
		create_profile.py \
		delete_manifest.py \
		delete_profile.py \
                export.py \
		publish_manifest.py \
		set_criteria.py \
		validate_profile.py \
		verifyXML.py

PYCMODULES=	$(PYMODULES:%.py=%.pyc)

WEBSERVER_FILES= AI.db

SCHEMAS=	criteria_schema.rng

PYTHON_CGI=	cgi_get_manifest.py

ROOTPYMODULES= $(PYMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTPYCMODULES= $(PYCMODULES:%=$(ROOTPYTHONVENDORINSTALLAI)/%)

ROOTWEBSERVER_FILES= $(WEBSERVER_FILES:%=$(ROOTVARAIWEB)/%)

ROOTCGI_FILES= $(PYTHON_CGI:%=$(ROOTVARAICGI)/%)

ROOTSCHEMAS= $(SCHEMAS:%=$(ROOTAUTOINST)/%)

all: python

clean:
	$(RM) *.pyc
	$(RM) AI.db

clobber: clean

install: all .WAIT $(ROOTPYTHONVENDORINSTALLAI) \
			$(ROOTPYMODULES) \
			$(ROOTPYCMODULES) \
			$(ROOTVARINSTADM) \
			$(ROOTCGI_FILES) \
			$(ROOTWEBSERVER_FILES) \
			$(ROOTSCHEMAS)

python:
	$(PYTHON) -m compileall -l $(@D)

#
# Note that the names of the database items below must be in lower-case letters
# except for the MIN or MAX prefixes used in range names.
#
AI.db:
	$(ECHO) 'CREATE TABLE manifests (name TEXT, instance INTEGER, arch TEXT, MINmac INTEGER, MAXmac INTEGER, MINipv4 INTEGER, MAXipv4 INTEGER, cpu TEXT, platform TEXT, MINnetwork INTEGER, MAXnetwork INTEGER, MINmem INTEGER, MAXmem INTEGER, zonename TEXT);' | /usr/bin/sqlite3 ./AI.db
	$(ECHO) 'CREATE TABLE profiles (name TEXT, file TEXT, arch TEXT, hostname TEXT, MINmac INTEGER, MAXmac INTEGER, MINipv4 INTEGER, MAXipv4 INTEGER, cpu TEXT, platform TEXT, MINnetwork INTEGER, MAXnetwork INTEGER, MINmem INTEGER, MAXmem INTEGER, zonename TEXT);' | /usr/bin/sqlite3 ./AI.db

include ../Makefile.targ

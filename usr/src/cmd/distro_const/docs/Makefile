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

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

HTML_FILES=	appendix.html \
		command.html \
		distro_const.html \
		distroconst.html \
		docinfo.html \
		gentextid-176.html \
		gentextid-875.html \
		how.html \
		index.html \
		manifest.html \
		manifestfile.html \
		overview.html \
		scripts.html \
		setup.html \
		sysreq.html \
		using.html

CSS_FILES=	css/advanced.css \
		css/elements.css \
		css/opensol.css

GRAPHICS_FILES=	graphics/header_gradientpart.png \
		graphics/opensolaris_logo_trans.png

ROOTDC_DOC_CSS=$(ROOTDC_DOC)/css
ROOTDC_DOC_GRAPHICS=$(ROOTDC_DOC)/graphics

ROOTHTML_FILES=	$(HTML_FILES:%=$(ROOTDC_DOC)/%)
ROOTCSS_FILES=	$(CSS_FILES:%=$(ROOTDC_DOC)/%)
ROOTGRAHICS_FILES=	$(GRAPHICS_FILES:%=$(ROOTDC_DOC)/%)

$(ROOTDC_DOC):
	$(INS.dir)

$(ROOTDC_DOC_CSS):
	$(INS.dir)

$(ROOTDC_DOC_GRAPHICS):
	$(INS.dir)

$(ROOTDC_DOC)/%: %
	$(INS.file)

all:		

clean:	

clobber: clean

install: $(ROOTDC_DOC) \
	$(ROOTDC_DOC_CSS)\
	$(ROOTDC_DOC_GRAPHICS) \
	$(ROOTHTML_FILES) \
	$(ROOTCSS_FILES) \
	$(ROOTGRAHICS_FILES)

include ../../Makefile.targ

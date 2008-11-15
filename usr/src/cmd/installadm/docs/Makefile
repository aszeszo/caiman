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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

include ../../Makefile.cmd

all:=		TARGET=	all
clean:=		TARGET=	clean
clobber:=	TARGET=	clobber
install:=	TARGET=	install

HTML_FILES=	aimanifest.html \
		appendix.html \
		docinfo.html \
		gentextid-1114.html \
		gentextid-140.html \
		gentextid-199.html \
		gentextid-261.html \
		gentextid-62.html \
		index.html \
		installadm.html \
		manifest.html \
		overview.html \
		scenario.html \
		solarisinstall.html

CSS_FILES=	css/advanced.css \
		css/elements.css \
		css/opensol.css

GRAPHICS_FILES=	graphics/header_gradientpart.png \
		graphics/opensolaris_logo_trans.png

ROOTAI_DOC_CSS=$(ROOTAI_DOC)/css
ROOTAI_DOC_GRAPHICS=$(ROOTAI_DOC)/graphics

ROOTHTML_FILES=	$(HTML_FILES:%=$(ROOTAI_DOC)/%)
ROOTCSS_FILES=	$(CSS_FILES:%=$(ROOTAI_DOC)/%)
ROOTGRAHICS_FILES=	$(GRAPHICS_FILES:%=$(ROOTAI_DOC)/%)

$(ROOTAI_DOC):
	$(INS.dir)

$(ROOTAI_DOC_CSS):
	$(INS.dir)

$(ROOTAI_DOC_GRAPHICS):
	$(INS.dir)

$(ROOTAI_DOC)/%: %
	$(INS.file)

all:

clean:	

clobber: clean

install: $(ROOTAI_DOC) \
	$(ROOTAI_DOC_CSS)\
	$(ROOTAI_DOC_GRAPHICS) \
	$(ROOTHTML_FILES) \
	$(ROOTCSS_FILES) \
	$(ROOTGRAHICS_FILES)

include ../../Makefile.targ

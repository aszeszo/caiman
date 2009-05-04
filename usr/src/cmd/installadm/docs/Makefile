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

HTML_FILES=	add.html \
		administer.html \
		advancedsetup.html \
		aimanifest.html \
		appendix.html \
		associate.html \
		basic.html \
		benefits.html \
		bothclient.html \
		cclient.html \
		client.html \
		clientinstall.html \
		clientreq.html \
		clients.html \
		criteria.html \
		customai.html \
		customsc.html \
		delclient.html \
		delete.html \
		docinfo.html \
		enable.html \
		faq.html \
		help.html \
		index.html \
		initial.html \
		installadm.html \
		list.html \
		manifest.html \
		manifest1.html \
		scenario.html \
		setup.html \
		setupfaq.html \
		simple.html \
		smf.html \
		solarisinstall.html \
		sparcclient.html \
		tasks.html \
		tasks1.html \
		trouble.html \
		use.html \
		whatis.html \
		x86client.html

CSS_FILES=	css/advanced.css \
		css/elements.css \
		css/opensol.css

FIGURES_FILES=	figures/aiflow.gif

GRAPHICS_FILES=	graphics/header_gradientpart.png \
		graphics/opensolaris_logo_trans.png

ROOTAI_DOC_CSS=$(ROOTAI_DOC)/css
ROOTAI_DOC_FIGURES=$(ROOTAI_DOC)/figures
ROOTAI_DOC_GRAPHICS=$(ROOTAI_DOC)/graphics

ROOTHTML_FILES=	$(HTML_FILES:%=$(ROOTAI_DOC)/%)
ROOTCSS_FILES=	$(CSS_FILES:%=$(ROOTAI_DOC)/%)
ROOTFIGURES_FILES=	$(FIGURES_FILES:%=$(ROOTAI_DOC)/%)
ROOTGRAPHICS_FILES=	$(GRAPHICS_FILES:%=$(ROOTAI_DOC)/%)

$(ROOTAI_DOC):
	$(INS.dir)

$(ROOTAI_DOC_CSS):
	$(INS.dir)

$(ROOTAI_DOC_FIGURES):
	$(INS.dir)

$(ROOTAI_DOC_GRAPHICS):
	$(INS.dir)

$(ROOTAI_DOC)/%: %
	$(INS.file)

all:

clean:	
	rm -rf $(ROOTAI_DOC)

clobber: clean

install: $(ROOTAI_DOC) \
	$(ROOTAI_DOC_CSS)\
	$(ROOTAI_DOC_FIGURES) \
	$(ROOTAI_DOC_GRAPHICS) \
	$(ROOTHTML_FILES) \
	$(ROOTCSS_FILES) \
	$(ROOTFIGURES_FILES) \
	$(ROOTGRAPHICS_FILES)

include ../../Makefile.targ

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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
"""

A/I Verify Manifest Prototype

"""

import os.path
import gettext
import lxml.etree

def verifyDTDManifest(data, xml_dtd):
	"""
	Use this for verifying a generic DTD based XML whose DOCTYPE points to its available DTD
	(absolute path needed). Will return the etree to walk the XML tree or the validation error
	"""
	result = list()
	parser = lxml.etree.XMLParser(load_dtd = False, no_network=True,
	    dtd_validation=False)
	dtd = lxml.etree.DTD(os.path.abspath(xml_dtd))
	try:
		root = lxml.etree.parse(data, parser)
	except IOError:
		raise SystemExit(_("Error:\tCan not open: %s" % data))
	except lxml.etree.XMLSyntaxError, e:
		for err in e.error_log:
			result.append(err.message)
		return result
	if dtd.validate(root):
		return root
	else:
		for err in dtd.error_log.filter_from_errors():
			result.append(err.message)
		return result


def verifyRelaxNGManifest(schema_f, data):
	"""
	Use this to verify a RelaxNG based document using the pointed to RelaxNG schema
	and receive the validation error or the etree to walk the XML tree
	"""
	try:
		relaxng_schema_doc = lxml.etree.parse(schema_f)
	except IOError:
		raise SystemExit(_("Error:\tCan not open:" % schema_f))
	relaxng = lxml.etree.RelaxNG(relaxng_schema_doc)
	try:
		root = lxml.etree.parse(data)
	except IOError:
		raise SystemExit(_("Error:\tCan not open:" % data))
	except lxml.etree.XMLSyntaxError, e:
		return e.error_log.last_error
	if relaxng.validate(root):
		return root
	return relaxng.error_log.last_error

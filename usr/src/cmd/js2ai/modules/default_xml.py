#!/usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
Class to handle activies associated with reading and modifying default xml
used by the installer

"""

import common
import lxml
import os
import shutil
import sys
import tempfile

from common import _
from common import DEFAULT_XML_FILENAME
from common import pretty_print as pretty_print
from common import write_xml_data as write_xml_data
from lxml import etree
from StringIO import StringIO

DEFAULT_XML_EMPTY = \
"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE auto_install SYSTEM "file:///usr/share/auto_install/ai.dtd">
<auto_install>
    <ai_instance name="default">
        <sc_embedded_manifest name="AI"/>
    </ai_instance>
</auto_install>
"""

SVC_BUNDLE_XML_DEFAULT = \
"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE service_bundle SYSTEM "/usr/share/lib/xml/dtd/service_bundle.dtd.1">
<service_bundle type="profile" name="system configuration"/>
"""


class XMLDefaultData(object):
    """The default xml data object that all work on the rules, profiles, and
    sysidcfg will work against.

    """
    _sc_embedded_manifest = None
    _service_bundle_tree = None
    _ai_instance = None
    _tree = None
    _root = None

    def __init__(self, default_xml_filename):
        parser = etree.XMLParser()
        if default_xml_filename is None:
            self._tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
            default_xml_filename = "DEFAULT_XML"
        else:
            self._tree = etree.parse(default_xml_filename)

        if len(parser.error_log) != 0:
            # We got parsing errors
            for err in parser.error_log:
                sys.stderr.write(err)

        self._root = self._tree.getroot()
        if self._root is None or self._root.tag != "auto_install":
            tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
            expected_layout = etree.tostring(tree, pretty_print=True)
            raise ValueError(_("%(filename)s does not conform to the expected "
                               "layout of:\n\n%(layout)s") %
                               {"filename": default_xml_filename, \
                                "layout": expected_layout})

        # Ensure that the tree has the minimum layout we expect
        nodes = \
            self._root.xpath("/auto_install/ai_instance[@name='default']")
        if len(nodes) != 0:
            self._ai_instance = nodes[0]

        nodes = self._ai_instance.xpath("./sc_embedded_manifest")
        if len(nodes) != 0:
            self._sc_embedded_manifest = nodes[0]

        if self._ai_instance is None or self._sc_embedded_manifest is None:
            tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
            expected_layout = etree.tostring(tree, pretty_print=True)
            raise ValueError(_("%(filename)s does not conform to the expected "
                               "layout of:\n\n%(layout)s") %
                               {"filename": default_xml_filename, \
                                "layout": expected_layout})

    @property
    def tree(self):
        """The xml tree that represents this object"""
        return self._tree

    def fetch_service_bundle_tree(self):
        """Return the comment node containing the service bundle tree"""
        if self._service_bundle_tree is not None:
            return self._service_bundle_tree

        manifest = self._sc_embedded_manifest
        #
        # Using type seems to be the only available way of detecting
        # that an entry is comment that works
        #
        if len(manifest) == 1 and type(manifest[0]) == lxml.etree._Comment:
            # The tree follows the required hierachy
            xml_text = manifest[0].text.strip()
            if xml_text:
                parser = etree.XMLParser()
                self._service_bundle_tree = etree.parse(StringIO(xml_text))
                if len(parser.error_log) != 0:
                    # We got non fatal parsing errors
                    for err in parser.error_log:
                        sys.stderr.write(err)
        return self._service_bundle_tree

    def replace_service_bundle_tree(self, service_bundle_tree):
        """Replace the existing service bunlde tree entry with the specified
        service bundle tree

        """
        manifest = self._sc_embedded_manifest
        manifest.clear()
        manifest.set(common.ATTRIBUTE_NAME, "AI")
        self._service_bundle_tree = service_bundle_tree
        tree_text = pretty_print(service_bundle_tree.getroot())
        # Since we are inserting a XML tree into the tree as a comment
        # we want to continue to maintain the base indentation level
        # that is being used by the rest of the tree. Since the indentation
        # level we need is known we just add some extra spaces to the
        # beginning of every line in the xml tree comment.
        tree_format = "          %s"
        tree_text = os.linesep.join(
            [tree_format % line for line in tree_text.splitlines()])
        tree_text = "\n" + tree_text + "\n        "
        comment = etree.Comment(text=tree_text)
        manifest.append(comment)

    def tree_copy(self):
        """Return a copy of this xml tree"""
        #
        # Ideally we'd use deepcopy() and make a copy of the tree.
        # deepcopy however, does not preserve the DOCTYPE entry
        tree_copy = pretty_print(self._tree)
        return etree.parse(StringIO(tree_copy))

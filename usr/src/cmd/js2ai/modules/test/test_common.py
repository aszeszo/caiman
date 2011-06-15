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

import os
import shutil
import tempfile
import unittest

import lxml.etree as etree

from StringIO import StringIO
from solaris_install.js2ai.common import write_xml_data
from solaris_install.js2ai.default_xml import DEFAULT_XML_EMPTY


class Test_XML_Corner_Cases(unittest.TestCase):
    """Test corner cases that are not picked up via code coverage on
    other routines

    """

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_xml_output_to_non_exist_dir(self):
        """Outputs the xml data to a file and then performs a validation test
        on the resulting file

        """
        tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
        dir = os.path.join(self.working_dir, "somedir")
        # The directory that this file will be written to doesn't exist
        # so this test passes by not getting any exceptions during the
        # run
        write_xml_data(tree, dir, "abc")

if __name__ == '__main__':
    unittest.main()

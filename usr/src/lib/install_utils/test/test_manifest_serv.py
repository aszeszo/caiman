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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
Note: the XML and DTD files are picked up from usr/src/cmd/auto-install
and not the proto area.
'''

import gettext
import unittest

from osol_install.ManifestServ import ManifestServ
from osol_install.DefValProc import ManifestProcError


# This is the path for the Manifest and Schema files.
# It is relative to usr/src in the current workspace.
XML_DIR="cmd/auto-install"


class DTDManifest(unittest.TestCase):
    '''Tests for DTD Manifests'''

    def setUp(self):
        # Create a ManifestServ for the default Manifest, default.xml.
        self.man_serv = ManifestServ("%s/default" % XML_DIR,
            full_init=False)

    def test_create(self):
        '''ManifestServ: can be instantiated with manifest default.xml'''

        instance_names = self.man_serv.get_values("auto_install/ai_instance/name")
        print "instance_names = [%s]" % instance_names
        self.assertEquals(len(instance_names), 1)
        self.assertEquals(instance_names[0], "default")

    def test_validate_fails_if_dtd_schema_is_false(self):
        '''ManifestServ: validate fails if dtd_schema is False'''

        self.assertRaises(ManifestProcError,
            self.man_serv.schema_validate,
            schema_name="%s/ai.dtd" % XML_DIR,
            dtd_schema=False)

    def test_validate_succeeds_if_dtd_schema_is_true(self):
        '''ManifestServ: validate succeeds if dtd_schema is True'''

        try:
            self.man_serv.schema_validate(
                schema_name="%s/ai.dtd" % XML_DIR,
                dtd_schema=True)
        except ManifestProcError, err:
            self.fail("schema_validate unexpectedly failed: [%s]" % str(err))


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/python
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''test_create_snapshot
   Test program for create_snapshot
'''

import os
import tempfile
import unittest

from common_create_simple_doc import CreateSimpleDataObjectCache
from solaris_install.ict.create_snapshot import CreateSnapshot
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestCreateSnapshot(unittest.TestCase):
    '''test the functionality for the CreateSnapshot Class'''

    def setUp(self):
        # Set up the Target directory
        self.test_target = tempfile.mkdtemp(dir="/tmp",
                                            prefix="ict_test_")
        os.chmod(self.test_target, 0777)

        # Create a data object to hold the required data
        self.simple = CreateSimpleDataObjectCache(self.test_target)

        # Instantiate the checkpoint
        self.create_snap = CreateSnapshot("CS")

    def tearDown(self):
        reset_engine()
        self.simple.doc = None

    def test_default_snapshot_name(self):
        '''Test that the default snapshot name is install'''

        # Instantiate the checkpoint
        try:
            self.create_snap.execute(dry_run=True)
        except Exception as e:
            self.fail(str(e))

        self.assertEquals(self.create_snap.snapshot_name, 'install')

    def test_get_progress_estimate(self):
        '''Test get progress estimate return value'''

        # Check the return value for the progress estimate
        self.assertEquals(self.create_snap.get_progress_estimate(), 5)

if __name__ == '__main__':
    unittest.main()

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

'''test_setup_swap
   Test program for setup_swap checkpoint
'''

import os
import shutil
import tempfile
import unittest

from lxml import etree
from solaris_install.ict.setup_swap import SetupSwap
from solaris_install.engine.test.engine_test_utils import reset_engine, \
    get_new_engine_instance
from solaris_install.target.logical import BE


class TestSetupSwap(unittest.TestCase):
    '''test the functionality for SetupSwap Class'''

    def populate_doc(self):
        DESIRED_XML = '''
        <root>
          <target name="desired">
            <logical noswap="false" nodump="false">
              <zpool name="myrpool" action="create" is_root="true">
                <filesystem name="export" action="create" in_be="false"/>
                <filesystem name="export/home" action="create" in_be="false"/>
                <be name="solaris"/>
                <vdev name="vdev" redundancy="none"/>
                <zvol name="myswap" action="create" use="swap">
                  <size val="512m"/>
                </zvol>
                <zvol name="mydump" action="create" use="dump">
                  <size val="512m"/>
                </zvol>
              </zpool>
            </logical>
            <disk whole_disk="false">
              <disk_name name="c7d0" name_type="ctd"/>
              <partition action="create" name="1" part_type="191">
                <size val="30Gb" start_sector="512"/>
                <slice name="0" action="create" force="true" is_swap="false"
                 in_zpool="myrpool" in_vdev="vdev">
                  <size val="20Gb" start_sector="512"/>
                </slice>
                <slice name="1" action="create" force="true" is_swap="true">
                  <size val="1Gb"/>
                </slice>
              </partition>
            </disk>
          </target>
        </root>
        '''
        desired_dom = etree.fromstring(DESIRED_XML)

        self.doc.import_from_manifest_xml(desired_dom, volatile=False)

        # Set BE mounpoints
        be_list = self.doc.get_descendants(class_type=BE)
        for be in be_list:
            be.mountpoint = self.test_target

    def setUp(self):
        # Set up the Target directory
        self.test_target = tempfile.mkdtemp(dir="/tmp",
                                            prefix="ict_test_")
        os.chmod(self.test_target, 0777)
        os.mkdir(os.path.join(self.test_target, "etc"))

        self.engine = get_new_engine_instance()
        self.doc = self.engine.data_object_cache

        self.populate_doc()

        # Instantiate the checkpoint
        self.setup_swap = SetupSwap("setup_swap")

        # Create a test file name
        self.test_file = os.path.join(self.test_target, 'etc/vfstab')

    def tearDown(self):
        reset_engine()
        self.doc = None

        if os.path.isfile(self.test_file):
            os.unlink(self.test_file)

        if os.path.exists(self.test_target):
            shutil.rmtree(self.test_target)

    def test_update_vfstab(self):
        '''Test update setup_swap'''

        # Call the execute command for the checkpoint
        self.setup_swap.execute()

        # Check to see if the test dumpadm.conf file exists
        self.assertTrue(os.path.isfile(self.test_file))

        # Read in the contents of the test file
        with open(self.test_file, "r") as fh:
            vfstab_data = fh.readlines()

        expected_lines = [
            '/dev/dsk/c7d0s1\t-\t\t-\t\tswap\t-\tno\t-\n',
            '/dev/zvol/dsk/myrpool/myswap\t-\t\t-\t\tswap\t-\tno\t-\n']
        self.assertEqual(vfstab_data, expected_lines)

    def test_update_setup_swap_dry(self):
        '''Test update setup_swap dry run'''

        # Call the execute command for the checkpoint
        # with dry_run set to true.
        try:
            self.setup_swap.execute(dry_run=True)
        except Exception as e:
            self.fail(str(e))

        # Check to see if the test vfstab file exists
        self.assertFalse(os.path.isfile(self.test_file))

    def test_get_progress_estimate(self):
        '''Test get progress estimate return value'''

        # Check the return value for the progress estimate
        self.assertEquals(self.setup_swap.get_progress_estimate(), 1)


if __name__ == '__main__':
    unittest.main()

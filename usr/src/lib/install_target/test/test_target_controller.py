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

import platform
import unittest
from lxml import etree
from nose.plugins.skip import SkipTest
from StringIO import StringIO

from solaris_install.engine.test import engine_test_utils
from solaris_install.target import Target
from solaris_install.target.logical import Vdev
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size
from solaris_install.target.controller import TargetController, BadDiskError


class TestTargetController(unittest.TestCase):
    def setUp(self):
        self.engine = engine_test_utils.get_new_engine_instance()
        self.doc = self.engine.data_object_cache

        # Poulate "discovered targets" with some made-up disks
        xml_str = '<root>\
  <target name="discovered">\
    <disk>\
      <disk_name name="c2t0d0" name_type="ctd"/>\
      <disk_prop dev_type="FIXED" dev_vendor="HITACHI" dev_size="100GB"/>\
      <disk_keyword key="boot_disk"/>\
      <partition action="create" name="1" part_type="191">\
        <size val="100GB" start_sector="0"/>\
        <slice name="0" action="create" force="false" is_swap="false">\
          <size val="50GB" start_sector="1024"/>\
        </slice>\
        <slice name="1" action="create" force="false" is_swap="false">\
          <size val="50GB" start_sector="2098176"/>\
        </slice>\
      </partition>\
    </disk>\
    <disk>\
      <disk_name name="c2t1d0" name_type="ctd"/>\
      <disk_prop dev_type="FIXED" dev_vendor="HITACHI" dev_size="50GB"/>\
      <partition action="create" name="1" part_type="7">\
        <size val="50GB" start_sector="0"/>\
        <slice name="0" action="create" force="false" is_swap="false">\
          <size val="25GB" start_sector="1024"/>\
        </slice>\
        <slice name="1" action="create" force="false" is_swap="false">\
          <size val="25GB" start_sector="2098176"/>\
        </slice>\
      </partition>\
    </disk>\
    <disk>\
      <disk_name name="c2t2d0" name_type="ctd"/>\
      <disk_prop dev_type="FIXED" dev_vendor="HITACHI" dev_size="150GB"/>\
      <partition action="create" name="1" part_type="7">\
        <size val="150GB" start_sector="0"/>\
        <slice name="0" action="create" force="false" is_swap="false">\
          <size val="10GB" start_sector="1024"/>\
        </slice>\
        <slice name="1" action="create" force="false" is_swap="false">\
          <size val="140GB" start_sector="2098176"/>\
        </slice>\
      </partition>\
    </disk>\
    <disk>\
      <disk_name name="c3t0d0" name_type="ctd"/>\
      <disk_prop dev_type="FIXED" dev_vendor="HITACHI" dev_size="150GB"/>\
      <partition action="preserve" name="1" part_type="191">\
        <size val="149GB" start_sector="0"/>\
        <slice name="0" action="preserve" force="false" is_swap="false">\
          <size val="75GB" start_sector="1024"/>\
        </slice>\
      </partition>\
      <partition action="preserve" name="2" part_type="190">\
        <size val="1GB" start_sector="0"/>\
        <slice name="0" action="preserve" force="false" is_swap="false">\
          <size val="1GB" start_sector="0"/>\
        </slice>\
      </partition>\
    </disk>\
  </target>\
</root>'

        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(StringIO(xml_str), parser)
        self.doc.import_from_manifest_xml(tree.getroot())

    def tearDown(self):
        engine_test_utils.reset_engine()

    def _get_discovered_disks(self):
        discovered_root = self.doc.get_descendants(name=Target.DISCOVERED,
            class_type=Target,
            max_depth=2,
            max_count=1,
            not_found_is_err=True)[0]
        return discovered_root.get_children(class_type=Disk)

    def _get_desired_disks(self):
        desired_root = self.doc.get_descendants(class_type=Target,
            name=Target.DESIRED,
            max_depth=2,
            not_found_is_err=True)[0]
        return desired_root.get_children(class_type=Disk)

    def test_error_if_no_discovered(self):
        '''Validate error raised if "discovered targets" doesn't exist'''
        self.doc.persistent.delete_children(class_type=Target,
            name=Target.DISCOVERED,
            not_found_is_err=True)
        tc = TargetController(self.doc)
        self.assertRaises(BadDiskError, tc.initialize)

    def test_error_if_no_suitable_disk(self):
        '''Validate error raised if "discovered targets" are too small'''
        tc = TargetController(self.doc)
        self.assertRaises(BadDiskError, tc.initialize,
            image_size=Size("1TB"))

    def test_no_initial_disk_works(self):
        '''Validate no_initial_disk=True works'''
        tc = TargetController(self.doc)
        returned_disks = tc.initialize(no_initial_disk=True)

        self.assertEqual(len(returned_disks), 0,
            "initialize() should have returned empty list")
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 0,
            "desired targets should not contain any disks")

    def test_initial_disk_selected(self):
        '''Validate that an initial disk is returned and selected.'''
        tc = TargetController(self.doc)
        returned_disks = tc.initialize()

        self.assertEqual(returned_disks[0].ctd, "c2t0d0",
            "initial disk not correctly returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(desired_disks[0].ctd, "c2t0d0",
            "initial disk not correctly selected")

    def test_initial_disk_selected_by_size(self):
        '''Validate that initial disk matches size criteria'''
        tc = TargetController(self.doc)
        returned_disks = tc.initialize(image_size=Size("110GB"))

        self.assertEqual(returned_disks[0].ctd, "c2t2d0",
            "incorrect initial disk returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(desired_disks[0].ctd, "c2t2d0",
            "incorrect initial disk selected")

    def test_selecting_specific_disk(self):
        '''Validate that a specific disk can be selected.'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[1])

        self.assertEqual(len(selected_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(selected_disks[0].ctd, discovered_disks[1].ctd,
            "incorrect disk returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 1,
            "there should be 1 Disk selected")
        self.assertEqual(desired_disks[0].ctd, discovered_disks[1].ctd,
            "incorrect disk selected")

    def test_existing_partitions(self):
        '''Validate that existing partitions can be presevered.'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[3])
        tc.apply_default_layout(selected_disks[0], False, False)

        self.assertEqual(len(selected_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(selected_disks[0].ctd, discovered_disks[3].ctd,
            "incorrect disk returned")
        self.assertEqual(
            len(selected_disks[0].get_children(class_type=Partition)),
            2,
            "disk should still have 2 partitions")


    def test_clears_existing_partitions(self):
        '''Validate that existing partitions are removed with wipe_disk set.'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[3])
        tc.apply_default_layout(selected_disks[0], False, True)

        self.assertEqual(len(selected_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(selected_disks[0].ctd, discovered_disks[3].ctd,
            "incorrect disk returned")
        self.assertEqual(
            len(selected_disks[0].get_children(class_type=Partition)),
            1,
            "disk should only have 1 partition now")


    def test_reset_layout(self):
        '''Validate that existing partitions are restored with reset_layout.'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc, debug=True)
        selected_disks = tc.select_disk(discovered_disks[3])
        self.assertEqual(len(selected_disks), 1,
            "there should be 1 Disk returned")
        tc.apply_default_layout(selected_disks[0], use_whole_disk=False, \
                                wipe_disk=True)
        self.assertEqual(
            len(selected_disks[0].get_children(class_type=Partition)),
            1, "disk should have 1 partition now")
        copy_disks = tc.reset_layout(selected_disks[0], use_whole_disk=False)

        self.assertEqual(len(copy_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(copy_disks[0].ctd, discovered_disks[3].ctd,
            "incorrect disk returned")
        self.assertEqual(
            len(copy_disks[0].get_children(class_type=Partition)),
            2, "disk should have 2 partitions again")


    def test_selecting_specific_disks(self):
        '''Validate that 2 specific disks can be selected.'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(
            [discovered_disks[1], discovered_disks[2]])

        self.assertEqual(len(selected_disks), 2,
            "there should be 2 Disks returned")
        self.assertEqual(selected_disks[0].ctd, discovered_disks[1].ctd,
            "incorrect disk returned")
        self.assertEqual(selected_disks[1].ctd, discovered_disks[2].ctd,
            "incorrect disk returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 2,
            "there should be 2 Disks selected")
        self.assertEqual(desired_disks[0].ctd, discovered_disks[1].ctd,
            "incorrect disk selected")
        self.assertEqual(desired_disks[1].ctd, discovered_disks[2].ctd,
            "incorrect disk selected")

    def test_previous_disk_unselected(self):
        '''Validate that selecting a new disk un-selects the previous disk'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[1])
        selected_disks = tc.select_disk(discovered_disks[2])

        self.assertEqual(len(selected_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(selected_disks[0].ctd, discovered_disks[2].ctd,
            "incorrect disk returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 1,
            "there should be 1 Disk selected")
        self.assertEqual(desired_disks[0].ctd, discovered_disks[2].ctd,
            "incorrect disk selected")

    def test_add_disk(self):
        '''Validate that adding a disk works'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[1])
        added_disks = tc.add_disk(discovered_disks[2])

        self.assertEqual(len(added_disks), 1,
            "there should be 1 Disk returned")
        self.assertEqual(added_disks[0].ctd, discovered_disks[2].ctd,
            "incorrect disk returned")
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 2,
            "there should be 2 Disks selected")
        self.assertEqual(desired_disks[0].ctd, discovered_disks[1].ctd,
            "incorrect disk selected")
        self.assertEqual(desired_disks[1].ctd, discovered_disks[2].ctd,
            "incorrect disk selected")

    def test_resetting_specific_disk(self):
        '''Validate that selected disks can be reset separately'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(
            [discovered_disks[1], discovered_disks[2]])

        selected_disks[0].delete_children(class_type=Partition)
        selected_disks[1].delete_children(class_type=Partition)

        tc.reset_layout(discovered_disks[2])

        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 2,
            "there should be 2 Disks selected")
        self.assertEqual(
            len(desired_disks[0].get_children(class_type=Partition)),
            0,
            "1st disk should have 0 partitions")
        self.assertEqual(
            len(desired_disks[1].get_children(class_type=Partition)),
            1,
            "2nd disk should have 1 partition")

    def test_resetting_all_disks(self):
        '''Validate that all selected disks can be reset'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(
            [discovered_disks[1], discovered_disks[2]])

        selected_disks[0].delete_children(class_type=Partition)
        selected_disks[1].delete_children(class_type=Partition)

        tc.reset_layout()

        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 2,
            "there should be 2 Disks selected")
        self.assertEqual(
            len(desired_disks[0].get_children(class_type=Partition)),
            1,
            "1st disk should have 1 partition")
        self.assertEqual(
            len(desired_disks[1].get_children(class_type=Partition)),
            1,
            "2nd disk should have 1 partition")

    def test_restoring_from_backup(self):
        '''Validate restoring previously edited disk from backup'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        # select, edit, de-select and re-select a disk
        selected_disks = tc.select_disk(discovered_disks[1])
        selected_disks[0].delete_children(class_type=Partition)
        selected_disks = tc.select_disk(discovered_disks[2])
        selected_disks = tc.select_disk(discovered_disks[1])

        desired_disks = self._get_desired_disks()
        self.assertEqual(
            len(desired_disks[0].get_children(class_type=Partition)),
            0,
            "selected disk should have 0 partitions")

    def test_use_whole_disk(self):
        '''Validate that partitions deleted if use_whole_disk specified'''
        if platform.processor() != "i386":
            raise SkipTest("test not supported on sparc")

        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(discovered_disks[1],
            use_whole_disk=True)

        desired_disks = self._get_desired_disks()
        # There should be at least one partition since we create this in
        # _fixup_disk().
        self.assertEqual(
            len(desired_disks[0].get_children(class_type=Partition)), 1,
            "selected disk should have 1 partitions")

    def test_disks_associated_with_vdev(self):
        '''Validate selected disks are associated with a Vdev'''
        discovered_disks = self._get_discovered_disks()
        tc = TargetController(self.doc)
        selected_disks = tc.select_disk(
            [discovered_disks[1], discovered_disks[2]])

        desired_root = self.doc.get_descendants(name=Target.DESIRED,
            class_type=Target,
            max_depth=2,
            max_count=1,
            not_found_is_err=True)[0]
        vdev = desired_root.get_descendants(class_type=Vdev,
            max_depth=3,
            max_count=1,
            not_found_is_err=True)[0]
        desired_disks = self._get_desired_disks()
        self.assertEqual(len(desired_disks), 2, "should be 2 seleted disks")
        self.assertEqual(vdev.name, "vdev", "Vdev's name should be 'vdev'")

        for desired_disk in desired_disks:
            slices = desired_disk.get_descendants(class_type=Slice)
            if not slices:
                self.assertEqual(desired_disk.in_vdev, vdev.name,
                    "Selected disk should be associated with vdev")
            else:
                bootslices = desired_disk.get_descendants(class_type=Slice,
                    name="0", not_found_is_err=True)
                bootslice = bootslices[0]
                if bootslice:
                    self.assertEqual(bootslice.in_vdev, vdev.name,
                        "Selected slice should be associated with vdev")
                else:
                    self.assertTrue(not bootslice,
                        "No root slice associated with vdev")




if __name__ == '__main__':
    unittest.main()

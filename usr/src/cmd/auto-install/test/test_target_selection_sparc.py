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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

import difflib
import os
import platform
import re
import unittest

import osol_install.errsvc as errsvc
from lxml import etree
from solaris_install.auto_install.checkpoints.target_selection \
    import TargetSelection
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine
from solaris_install.target import Target, logical
from solaris_install.target.physical import Disk, Slice


class TestTargetSelectionTestCase(unittest.TestCase):
    DISCOVERED_TARGETS_XML = '''
    <root>
      <target name="discovered">

        <disk whole_disk="false">
          <disk_name name="c99t2d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
          dev_size="625141760secs"/>
          <slice name="1" action="preserve" force="false" is_swap="false"
             in_zpool="rpool_test" in_vdev="rpool_test-none">
            <size val="1060290secs" start_sector="512"/>
          </slice>
        </disk>

        <disk whole_disk="false">
          <disk_name name="c99t0d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="HITACHI"
           dev_size="143349312secs"/>
          <disk_keyword key="boot_disk"/>
          <slice name="0" action="preserve" force="false" is_swap="false"
           in_zpool="rpool_test" in_vdev="rpool_test-none">
            <size val="16770048secs" start_sector="10176"/>
          </slice>
          <slice name="2" action="preserve" force="false" tag="5"
           is_swap="false">
            <size val="143349312secs" start_sector="0"/>
          </slice>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c99t1d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="HITACHI"
           dev_size="143349312secs"/>
          <slice name="0" action="preserve" force="false" is_swap="false">
            <size val="41945472secs" start_sector="0"/>
          </slice>
          <slice name="1" action="preserve" force="false" is_swap="false">
            <size val="4202688secs" start_sector="41945472"/>
          </slice>
          <slice name="2" action="preserve" force="false" tag="5"
           is_swap="false">
            <size val="143349312secs" start_sector="0"/>
          </slice>
        </disk>
        <disk whole_disk="false">
          <disk_name name="206000c0ff0080c4" name_type="wwn"/>
          <disk_prop dev_type="scsi" dev_vendor="HITACHI"
           dev_size="143349312secs"/>
          <slice name="0" action="preserve" force="false" is_swap="false">
            <size val="41945472secs" start_sector="0"/>
          </slice>
          <slice name="1" action="preserve" force="false" is_swap="false">
            <size val="4202688secs" start_sector="41945472"/>
          </slice>
          <slice name="2" action="preserve" force="false" tag="5"
           is_swap="false">
            <size val="143349312secs" start_sector="0"/>
          </slice>
        </disk>
        <logical noswap="false" nodump="false">
          <zpool name="rpool_test" action="preserve" is_root="false"
           mountpoint="/rpool_test">
            <vdev name="rpool_test-none" redundancy="none"/>
            <filesystem name="ROOT" action="preserve" mountpoint="legacy"
             in_be="false"/>
            <filesystem name="ROOT/solaris" action="preserve" mountpoint="/"
             in_be="false"/>
            <filesystem name="ROOT/solaris/testing" action="preserve"
             mountpoint="/testing" in_be="false"/>
            <zvol name="dump" action="preserve" use="dump">
              <size val="1.03gb"/>
            </zvol>
            <zvol name="swap" action="preserve" use="swap">
              <size val="2.06gb"/>
            </zvol>
            <be name="solaris"/>
          </zpool>
        </logical>
      </target>
    </root>
    '''

    def __gendiff_str(self, a, b):
        a_lines = a.splitlines()
        b_lines = b.splitlines()
        return "\n".join(list(difflib.ndiff(a_lines, b_lines)))

    def __run_simple_test(self, input_xml, expected_xml, fail_ex_str=None,
        dry_run=True):
        '''Run a simple test where given specific xml in the manifest, we
        validate that the generated DESIRED tree is as expected.

        'expected_xml' should have the values indented using '.' instead of
        spaces to ensure that perfect match is made.
        '''
        errsvc.clear_error_list()

        # Different processor to what these tests were written for.
        if platform.processor() != 'sparc':
            print "Skipping test on wrong arch"
            return

        if input_xml is not None:
            manifest_dom = etree.fromstring(input_xml)
            self.doc.import_from_manifest_xml(manifest_dom, volatile=True)
            self.doc.logger.debug("DOC AFTER IMPORT TEST XML:\n%s\n\n" %
                                  (str(self.doc)))
            if len(errsvc._ERRORS) > 0:
                self.fail(errsvc._ERRORS[0])

        # Define expected string, compensate for indent. Using '.' in expected
        # string to remove conflict with indent replacement.
        indentation = '''\
        '''
        expected_xml = expected_xml.replace(indentation, "").replace(".", " ")

        try:
            self.target_selection.select_targets(
                self.doc.volatile.get_descendants(class_type=Target,
                                                  max_depth=2),
                self.doc.persistent.get_first_child(Target.DISCOVERED),
                dry_run=dry_run)
            if (fail_ex_str is not None):
                self.fail("Expected failure but test succeeded.")
        except Exception, ex:
            if (fail_ex_str is not None):
                self.assertEquals(str(ex), fail_ex_str)
            else:
                import traceback
                traceback.print_exc()
                raise ex

        try:
            desired = \
                self.doc.get_descendants(
                    name=Target.DESIRED, class_type=Target, max_depth=2,
                    not_found_is_err=True)[0]

            xml_str = desired.get_xml_tree_str()

            expected_re = re.compile(expected_xml)
            if not expected_re.match(xml_str):
                self.fail("Resulting XML doesn't match "
                          "expected:\nDIFF:\n%s\n" %
                          self.__gendiff_str(expected_xml, xml_str))

            desired.final_validation()
        except ObjectNotFoundError:
            self.fail("Unable to find DESIRED tree!")
        except Exception, e:
            import traceback
            traceback.print_exc()
            self.fail(e)

        if len(errsvc._ERRORS) > 0:
            self.fail(errsvc._ERRORS[0])

    def setUp(self):
        logical.DEFAULT_BE_NAME = "ai_test_solaris"
        self.engine = get_new_engine_instance()
        self.target_selection = TargetSelection("Test Checkpoint")
        self.doc = InstallEngine.get_instance().data_object_cache
        discovered_dom = etree.fromstring(self.DISCOVERED_TARGETS_XML)
        self.doc.import_from_manifest_xml(discovered_dom, volatile=False)

        # Ensure backup slices have tag = 5 (V_BACKUP)
        slices = self.doc.get_descendants("2", Slice)
        for s in slices:
            s.tag = 5

        # As we are not really discovering disks, label will be set to "None"
        # Ensure they set to VTOC
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "VTOC"

            # to test a different identification types (devid, wwn, etc.), set
            # a ctd string for any disk without one.  Target Discovery will
            # always set as many attributes (ctd, volid, devpath, devid,
            # receptacle, wwn) as libdiskmgt returns but the XML only allows a
            # single identification type.
            if disk.ctd is None:
                disk.ctd = "c89t0d0"

    def tearDown(self):
        if self.engine is not None:
            reset_engine(self.engine)

        self.doc = None
        self.target_selection = None

    def test_target_selection_no_target(self):
        '''Test Success if no target in manifest'''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="false" nodump="false">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(None, expected_xml)

    def test_target_selection_no_disk_target_with_logical(self):
        '''Test Success if no disk targets, but with a logical section'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
             <target>
               <logical>
                 <zpool name="ai_test_rpool" is_root="true">
                   <filesystem name="/export"/>
                   <filesystem name="/export/home"/>
                   <be name="ai_test_solaris"/>
                 </zpool>
               </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''
        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<filesystem name="/export" action="create" in_be="false"/>
        ......<filesystem name="/export/home" action="create" in_be="false"/>
        ......<be name="ai_test_solaris"/>
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_single_whole_disk_target(self):
        '''Test Success if single whole target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_boot_disk_target(self):
        '''Test Success if boot_disk target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool" in_vdev="vdev">
                <disk_keyword key="boot_disk" />
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <vdev name="vdev" redundancy="none" />
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_multiple_whole_disk_targets(self):
        '''Test Success if multiple disk targets, no zpool, in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="True">
                <disk_name name="c99t1d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_multiple_whole_disk_false_no_slices(self):
        '''Test Success if whole disk false, no slices, in manifest.
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c99t1d0" name_type="ctd"/>
                <size val="390714880secs" start_sector="512"/>
                <slice name="0" action="create" force="false"
                 is_swap="false">
                  <size val="390714880secs" start_sector="512"/>
                </slice>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml,
            fail_ex_str="If whole_disk is False, you need to "
                        "provide information for"
                        " gpt_partitions or slices")

    def test_target_selection_multiple_whole_disk_mixed_no_logicals(self):
        '''Test Success if 1 whole & 1 partitioned disk, no logicals'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c99t1d0" name_type="ctd"/>
                <slice name="1" action="delete"/>
                <slice name="0" action="create" force="false"
                 is_swap="false">
                  <size val="143348736secs" start_sector="512"/>
                </slice>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="1" action="delete" force="false" is_swap="false">
        ......<size val="4202688secs" start_sector="41945472"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_whole_disk_true_and_rpool(self):
        '''Test Success if 2 disks, whole_disk=True & root pool'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd" />
              </disk>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t1d0" name_type="ctd" />
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_whole_disk_false_and_rpool(self):
        '''Test Success If 2 Disks w/Whole-Disks = False & Root Pool Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
                  <slice name="1" action="delete"/>
                  <slice name="0" action="create" force="false"
                      is_swap="false" in_zpool="ai_test_rpool">
                    <size val="143349312secs" start_sector="512"/>
                  </slice>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c99t1d0" name_type="ctd"/>
                  <slice name="1" action="delete"/>
                  <slice name="0" action="create" force="false"
                    is_swap="false" in_zpool="ai_test_rpool">
                    <size val="143349312secs" start_sector="512"/>
                  </slice>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143349248secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="1" action="delete" force="false" is_swap="false">
        ......<size val="4202688secs" start_sector="41945472"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143349248secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_mixed_whole_disk_and_rpool(self):
        '''Test Success If 2 Disks, Mixed Whole-Disk Values & Root Pool
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c99t1d0" name_type="ctd"/>
                <slice name="1" action="delete"/>
                <slice name="0" action="create" force="false" is_swap="false"
                 in_zpool="ai_test_rpool">
                  <size val="143349312secs" start_sector="512"/>
                </slice>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <zvol name="swap" action="create" use="swap">
                    <size val="747m"/>
                  </zvol>
                  <zvol name="dump" action="create" use="dump">
                    <size val="747m"/>
                  </zvol>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="747m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="747m"/>
        ......</zvol>
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="1" action="delete" force="false" is_swap="false">
        ......<size val="4202688secs" start_sector="41945472"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143349248secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_whole_disk_true_and_rpool_w_vdev(self):
        '''Test Success If 2 Disks w/Whole-Disk = True & Root Vdev Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_vdev="ai_test_vdev">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="true" in_vdev="ai_test_vdev">
                <disk_name name="c99t1d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <vdev name="ai_test_vdev" redundancy="mirror"/>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="ai_test_vdev" redundancy="mirror"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_root_pool_non_be_datasets(self):
        '''Test Success If Root Pool Non-BE Datasets Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <filesystem name="to_share" mountpoint="/share"/>
                  <filesystem name="export2"/>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<filesystem name="to_share" action="create" mountpoint="/share" \
        in_be="false"/>
        ......<filesystem name="export2" action="create" in_be="false"/>
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_root_pool_with_be_datasets(self):
        '''Test Success If Root Pool with BE Datasets Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <filesystem name="to_share" mountpoint="/share"/>
                  <filesystem name="export2"/>
                  <filesystem name="opt" in_be="true"/>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<filesystem name="to_share" action="create" mountpoint="/share" \
        in_be="false"/>
        ......<filesystem name="export2" action="create" in_be="false"/>
        ......<filesystem name="opt" action="create" in_be="true"/>
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_pool_and_datasets_options(self):
        '''Test Success If Pool and Datasets Options Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <pool_options>
                    <option name="listsnaps" value="on"/>
                  </pool_options>
                  <dataset_options>
                    <option name="compression" value="on"/>
                  </dataset_options>
                  <filesystem name="to_share" mountpoint="/share">
                    <options>
                      <option name="compression" value="off"/>
                    </options>
                  </filesystem>
                  <filesystem name="export2"/>
                  <be name="ai_test_solaris_be">
                    <options>
                      <option name="test:ai_test_option" value="1"/>
                    </options>
                  </be>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<pool_options>
        ........<option name="listsnaps" value="on"/>
        ......</pool_options>
        ......<dataset_options>
        ........<option name="compression" value="on"/>
        ......</dataset_options>
        ......<filesystem name="to_share" action="create" mountpoint="/share" \
        in_be="false">
        ........<options>
        ..........<option name="compression" value="off"/>
        ........</options>
        ......</filesystem>
        ......<filesystem name="export2" action="create" in_be="false"/>
        ......<be name="ai_test_solaris_be">
        ........<options>
        ..........<option name="test:ai_test_option" value="1"/>
        ........</options>
        ......</be>
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_root_pool_with_be_specified(self):
        '''Test Success If Root Pool With BE Specified
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <be name="ai_test_solaris_be"/>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<be name="ai_test_solaris_be"/>
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_slice_no_size(self):
        '''Test Success If Have a Disk, containing 1 slice without size
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
                <slice name="0" action="create" force="false"
                 is_swap="false"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_slice_no_start_sector(self):
        '''Test Success If Have a Disk, containing 1 slice without start_sector
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
                <slice name="0" action="create" force="false"
                 is_swap="false">
                  <size val="30G"/>
                </slice>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="62914560secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_slice_too_large(self):
        '''Test Fail if slice is specified with a value too large'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
            <target>
             <disk>
                <disk_name name_type="ctd" name="c99t0d0"/>
                <slice name="0" action="create" is_swap="false"
                 in_zpool="rpool" in_vdev="vdev">
                  <size val="20000001mb"/>
                </slice>
              </disk>
              <logical>
                <zpool name="rpool" is_root="true">
                  <vdev name="vdev" redundancy="none"/>
                </zpool>
              </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''
        expected_xml = ""

        self.__run_simple_test(test_manifest_xml, expected_xml,
            fail_ex_str="Slice 0 has a size larger than the disk c99t0d0")

    def test_target_selection_swap_and_dump_size(self):
        '''Test Success In Calc of Swap and Dump Size'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name_type="ctd" name="c99t0d0"/>
                <slice name="0" action="create" is_swap="false"
                 in_zpool="ai_test_rpool" in_vdev="vdev">
                  <size val="10GB"/>
                </slice>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <vdev name="vdev" redundancy="none"/>
                </zpool>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="2" action="preserve" force="false" is_swap="false">
        ......<size val="143349312secs" start_sector="0"/>
        ....</slice>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="20971520secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_use_slice_on_existing_zpool(self):
        '''Test Success using slices on existing zpools'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
            <disk whole_disk="false">
              <disk_name name="c99t2d0" name_type="ctd"/>
              <slice name="1" action="create" is_swap="false"
                 in_zpool="ai_test_rpool" in_vdev="rpool-none">
                 <size val="276976665secs"/>
              </slice>
            </disk>

            <logical noswap="true" nodump="true">
              <zpool name="ai_test_rpool" action="create" is_root="true">
                <vdev name="rpool-none" redundancy="none"/>
              </zpool>
            </logical>
          </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="rpool-none" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="rpool-none">
        ......<size val="276976128secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_create_swap_and_ufs_slices(self):
        '''Test Success using creating swap and ufs slices'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
            <disk whole_disk="false">
              <disk_name name="c99t2d0" name_type="ctd"/>
              <slice name="1" action="create" is_swap="false"
                 in_zpool="ai_test_rpool" in_vdev="rpool-none">
                 <size val="276976665secs"/>
              </slice>
              <slice name="3" action="create" is_swap="true">
                 <size val="1gb"/>
              </slice>
              <slice name="5" action="create" is_swap="false">
                 <size val="1gb"/>
              </slice>
              <slice name="7" action="create" is_swap="true">
                 <size val="1gb"/>
              </slice>
            </disk>

            <logical noswap="true" nodump="true">
              <zpool name="ai_test_rpool" action="create" is_root="true">
                <vdev name="rpool-none" redundancy="none"/>
              </zpool>
            </logical>
          </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="rpool-none" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="rpool-none">
        ......<size val="276976640secs" start_sector="512"/>
        ....</slice>
        ....<slice name="3" action="create" force="false" is_swap="true">
        ......<size val="2097152secs" start_sector="276977152"/>
        ....</slice>
        ....<slice name="5" action="create" force="false" is_swap="false">
        ......<size val="2097152secs" start_sector="279074304"/>
        ....</slice>
        ....<slice name="7" action="create" force="false" is_swap="true">
        ......<size val="2097152secs" start_sector="281171456"/>
        ....</slice>
        ..</disk>
        </target>
        '''

    def test_target_selection_whole_disk_true_with_kids_and_rpool(self):
        '''Test Success if whole_disk=True, one disk with kids & root pool'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t2d0" name_type="ctd"/>
                  <slice name="1" action="create" is_swap="false"
                  in_zpool="ai_test_rpool"/>
              </disk>
              <logical noswap="true" nodump="true">
                <zpool name="ai_test_rpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="625141248secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_whole_disk_true_partition_create(self):
        '''Test Success if whole_disk=True, partition with create'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t1d0" name_type="ctd"/>
                <slice action="create" name="1" in_zpool="ai_test_rpool"/>
              </disk>
              <logical noswap="true" nodump="true">
                <zpool name="ai_test_rpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_default_small_slice_size(self):
        '''Test Success if creating a default small sized slice'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t1d0" name_type="ctd"/>
                <slice name="0" action="create"
                  is_swap="false" in_zpool="ai_test_rpool">
                  <size val="68gb"/>
                </slice>
                <slice name="1" action="create"
                  is_swap="false"/>
              </disk>
              <logical noswap="true" nodump="true">
                <zpool name="ai_test_rpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="142605824secs" start_sector="512"/>
        ....</slice>
        ....<slice name="1" action="create" force="false" is_swap="false">
        ......<size val="742400secs" start_sector="142606848"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_wwn(self):
        ''' Test success if user specifies wwn as the disk_name'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="206000c0ff0080c4" name_type="wwn"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c89t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_1(self):
        ''' Test success if user specifies a disk property'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_prop dev_type="FIXED"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_2_1(self):
        ''' Test success if user specifies a disk property and a disk name'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="c99t1d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_vendor="Lenovo"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_2_1_err(self):
        ''' Test Fail if a disk property and disk name point to same disk'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="c99t2d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_type="FIXED"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml, 
            fail_ex_str="Unable to locate the disk '[dev_type='FIXED']'" + 
                        " on the system.")

    def test_target_selection_props_2_2(self):
        ''' Test success if user specifies 2 disk properties'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_prop dev_size="143349312secs"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_vendor="Lenovo"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_2_with_pools(self):
        ''' Test success if user specifies 2 disk props and pools specified'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk in_zpool="rpool" whole_disk="True">
                <disk_prop dev_size="143349312secs"/>
              </disk>
              <disk in_zpool="data" whole_disk="True">
                <disk_prop dev_vendor="Lenovo"/>
              </disk>
              <logical noswap="true" nodump="true">
                <zpool name="rpool" is_root="true">
                    <filesystem name="export" mountpoint="/export"/>
                    <filesystem name="export/home"/>
                    <be name="solaris"/>
                </zpool>
                <zpool name="data"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<filesystem name="export" action="create" \
        mountpoint="/export" in_be="false"/>
        ......<filesystem name="export/home" action="create" \
        mountpoint="/export/home/" in_be="false"/>
        ......<be name="solaris"/>
        ......<vdev name="vdev" redundancy="none"/>
        ....</zpool>
        ....<zpool name="data" action="create" is_root="false">
        ......<vdev name="vdev" redundancy="none"/>
        ....</zpool>
        ..</logical>
        ..<disk in_zpool="data" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_3_2(self):
        ''' Test success if user specifies 2 disk properties and 1 disk name'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_prop dev_size="143349312secs"/>
              </disk>
              <disk whole_disk="True">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_vendor="Lenovo"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_props_3_3(self):
        ''' Test success if user specifies 3 disk properties'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_prop dev_size="143349312secs"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_vendor="Hitachi"/>
              </disk>
              <disk whole_disk="True">
                <disk_prop dev_type="scsi"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="143349312secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="143348736secs" start_sector="512"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="HITACHI" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c99t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</slice>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)


if __name__ == '__main__':
    unittest.main()

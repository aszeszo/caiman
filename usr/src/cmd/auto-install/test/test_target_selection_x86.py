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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
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
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine
from solaris_install.target import Target, logical
from solaris_install.target.physical import Disk


class  TestTargetSelectionTestCase(unittest.TestCase):
    DISCOVERED_TARGETS_XML = '''
    <root>
      <target name="discovered">
        <disk whole_disk="false">
          <disk_name name="c10t4d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
          dev_size="625141760secs"/>
          <partition action="preserve" name="1" part_type="191">
            <size val="276976665secs" start_sector="512"/>
            <slice name="1" action="preserve" force="false" is_swap="false"
               in_zpool="rpool" in_vdev="rpool-none">
              <size val="1060290secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c10t3d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
           dev_size="625141760secs"/>
          <partition action="preserve" name="1" part_type="11">
            <size val="3341520secs" start_sector="0"/>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c10t2d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
           dev_size="625141760secs"/>
          <partition action="preserve" name="1" part_type="191">
            <size val="348144615secs" start_sector="0"/>
            <slice name="1" action="preserve" force="false" is_swap="false"
               in_zpool="rpool" in_vdev="rpool-none">
              <size val="1060290secs" start_sector="48195"/>
            </slice>
            <slice name="3" action="preserve" force="false" is_swap="false"
             in_zpool="ai_test_rpool" in_vdev="rpool-mirror-0">
              <size val="43022070secs" start_sector="1108485"/>
            </slice>
            <slice name="7" action="preserve" force="false" is_swap="false">
              <size val="190257795secs" start_sector="44130555"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c10t1d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
           dev_size="625141760secs"/>
          <partition action="preserve" name="1" part_type="191">
            <size val="348144615secs" start_sector="0"/>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c10t0d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
           dev_size="625141760secs"/>
          <partition action="preserve" name="1" part_type="131">
            <size val="348144615secs" start_sector="0"/>
          </partition>
          <partition action="preserve" name="2" part_type="130">
            <size val="276976665secs" start_sector="348160680"/>
            <slice name="1" action="preserve" force="false" is_swap="false"
               in_zpool="rpool" in_vdev="rpool-none">
              <size val="1060290secs" start_sector="48195"/>
            </slice>
            <slice name="2" action="preserve" force="false" is_swap="false">
              <size val="276944535secs" start_sector="0"/>
            </slice>
            <slice name="3" action="preserve" force="false" is_swap="false"
             in_zpool="ai_test_rpool" in_vdev="rpool-mirror-0">
              <size val="43022070secs" start_sector="1108485"/>
            </slice>
            <slice name="7" action="preserve" force="false" is_swap="false">
              <size val="190257795secs" start_sector="44130555"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
            <slice name="9" action="preserve" force="false" is_swap="false">
              <size val="32129secs" start_sector="16066"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c7d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
          <disk_keyword key="boot_disk"/>
          <partition action="preserve" name="1" part_type="175">
            <size val="401625secs" start_sector="0"/>
          </partition>
          <partition action="preserve" name="2" part_type="175">
            <size val="133949970secs" start_sector="401625"/>
          </partition>
          <partition action="preserve" name="3" part_type="130">
            <size val="234420480secs" start_sector="134367660"/>
            <slice name="1" action="preserve" force="false" is_swap="false">
              <size val="1060290secs" start_sector="48195"/>
            </slice>
            <slice name="2" action="preserve" force="false" is_swap="false">
              <size val="234388350secs" start_sector="0"/>
            </slice>
            <slice name="3" action="preserve" force="false" is_swap="false">
              <size val="43022070secs" start_sector="1108485"/>
            </slice>
            <slice name="7" action="preserve" force="false" is_swap="false">
              <size val="190257795secs" start_sector="44130555"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
            <slice name="9" action="preserve" force="false" is_swap="false">
              <size val="32130secs" start_sector="16065"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c7d1" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
            <partition action="create" name="1" part_type="191">
            <size val="390714880secs" start_sector="512"/>
            <slice name="0" action="create" force="false" is_swap="false">
              <size val="390713344secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c8d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
            <partition action="create" name="1" part_type="191">
            <size val="390714880secs" start_sector="512"/>
            <slice name="0" action="create" force="false" is_swap="false">
              <size val="390713344secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c8d1" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
            <partition action="create" name="1" part_type="191">
            <size val="390714880secs" start_sector="512"/>
            <slice name="0" action="create" force="false" is_swap="false">
              <size val="390713344secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c9d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
            <partition action="create" name="1" part_type="191">
            <size val="390714880secs" start_sector="512"/>
            <slice name="0" action="create" force="false" is_swap="false">
              <size val="390713344secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c9d1" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="390715392secs"/>
            <partition action="create" name="1" part_type="191">
            <size val="390714880secs" start_sector="512"/>
            <slice name="0" action="create" force="false" is_swap="false">
              <size val="390713344secs" start_sector="512"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c3d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="29.98gb"/>
            <partition action="preserve" name="1" part_type="12">
              <size val="2.99Gb" start_sector="16065"/>
            </partition>
            <partition action="preserve" name="2" part_type="131">
              <size val="2.99Gb" start_sector="6286550"/>
            </partition>
            <partition action="preserve" name="3" part_type="12">
              <size val="2.99Gb" start_sector="12557035"/>
            </partition>
            <partition action="preserve" name="4" part_type="5">
              <size val="14.99Gb" start_sector="18827520"/>
            </partition>
            <partition action="preserve" name="5" part_type="12">
              <size val="1.5Gb" start_sector="18827520"/>
            </partition>
            <partition action="preserve" name="6" part_type="191">
              <size val="5.5Gb" start_sector="21973248"/>
            </partition>
        </disk>
        <logical noswap="true" nodump="true">
          <zpool name="export" action="preserve" is_root="false"
           mountpoint="/export">
            <vdev name="export-mirror-0" redundancy="mirror-0"/>
            <filesystem name="home" action="preserve"
             mountpoint="/export/home"/>
            <filesystem name="synchronized" action="preserve"
             mountpoint="/export/synchronized"/>
            <filesystem name="test_install" action="preserve"
             mountpoint="/a"/>
          </zpool>
          <zpool name="ai_test_rpool" action="preserve" is_root="true"
           mountpoint="/rpool">
            <vdev name="rpool-none" redundancy="none"/>
            <vdev name="rpool-mirror-0" redundancy="mirror-0"/>
            <filesystem name="ROOT" action="preserve" mountpoint="none"/>
            <filesystem name="ROOT/os153" action="preserve" mountpoint="/"/>
            <filesystem name="ROOT/os158" action="preserve" mountpoint="/"/>
            <filesystem name="ROOT/os159" action="preserve" mountpoint="/"/>
            <filesystem name="ROOT/os161" action="preserve" mountpoint="/"/>
            <zvol name="dump" action="preserve" use="none">
              <size val="1.50gb"/>
            </zvol>
            <zvol name="swap" action="preserve" use="none">
              <size val="1.00gb"/>
            </zvol>
            <be name="os153"/>
            <be name="os158"/>
            <be name="os159"/>
            <be name="os161"/>
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
        if platform.processor() != 'i386':
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

        desired = \
            self.doc.get_descendants(
                name=Target.DESIRED, class_type=Target, max_depth=2)[0]

        xml_str = desired.get_xml_tree_str()

        expected_re = re.compile(expected_xml)
        if not expected_re.match(xml_str):
            self.fail("Resulting XML doesn't match expected:\nDIFF:\n%s\n" %
                      self.__gendiff_str(expected_xml, xml_str))

        desired.final_validation()
        if len(errsvc._ERRORS) > 0:
            self.fail(errsvc._ERRORS[0])

    def setUp(self):
        logical.DEFAULT_BE_NAME="ai_test_solaris"
        self.engine = get_new_engine_instance()

        self.target_selection = TargetSelection("Test Checkpoint")
        self.doc = InstallEngine.get_instance().data_object_cache
        discovered_dom = etree.fromstring(self.DISCOVERED_TARGETS_XML)
        self.doc.import_from_manifest_xml(discovered_dom, volatile=False)

        # As we are not really discovering disks, label  will be set to "None"
        # Ensure they set to VTOC
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "VTOC"

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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
              <disk whole_disk="true">
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
              <disk whole_disk="true">
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="true">
                <disk_name name="c7d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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

    def test_target_selection_multiple_whole_disk_false_no_logicals(self):
        '''Test Success if multiple partitioned disks, no logical, in manifest.
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c10t0d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="create" name="1" part_type="191">
                  <size val="625141248secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="625139712secs" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="390714880secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="390713344secs" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        . <logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="delete" name="2" part_type="130">
        ......<size val="276976665secs" start_sector="348160680"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        . </disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_multiple_whole_disk_mixed_no_logicals(self):
        '''Test Success if 1 whole & 1 partitioned disk, no logicals'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="390714880secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="390713344secs" start_sector="512"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd" />
              </disk>
              <disk whole_disk="true" in_zpool="ai_test_rpool">
                <disk_name name="c7d0" name_type="ctd"/>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="create" name="1" part_type="191">
                  <size val="625141248secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                      is_swap="false" in_zpool="ai_test_rpool">
                    <size val="625139712secs" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="390714880secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                    is_swap="false" in_zpool="ai_test_rpool">
                    <size val="390713344secs" start_sector="512"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="delete" name="2" part_type="130">
        ......<size val="276976665secs" start_sector="348160680"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
            <disk_name name="c7d0" name_type="ctd"/>
            <partition action="delete" name="2"/>
            <partition action="delete" name="3"/>
            <partition action="create" name="1" part_type="191">
              <size val="390714880secs" start_sector="512"/>
              <slice name="0" action="create" force="false" is_swap="false"
               in_zpool="ai_test_rpool">
                <size val="390713344secs" start_sector="512"/>
              </slice>
            </partition>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="true" in_vdev="ai_test_vdev">
                <disk_name name="c7d0" name_type="ctd"/>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_whole_disk_false_and_rpool_w_vdev(self):
        '''Test Success If 2 Disks w/Whole-Disk = False & Root Pool w/Vdev
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c10t0d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="create" name="1" part_type="191">
                  <size val="625141248secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false" in_vdev="ai_test_vdev">
                    <size val="625139712secs" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="390714880secs" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false" in_vdev="ai_test_vdev">
                    <size val="390713344secs" start_sector="512"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="delete" name="2" part_type="130">
        ......<size val="276976665secs" start_sector="348160680"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_mixed_whole_disk__and_rpool_w_vdev(self):
        '''Test Success If 2 Disks, Mixed Whole-Disk Values & Root w/Vdev
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_vdev="ai_test_vdev">
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="390714880secs" start_sector="512"/>
                  <slice name="0" action="create" force="false" is_swap="false"
                   in_vdev="ai_test_vdev">
                    <size val="390713344secs" start_sector="512"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="ai_test_vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c10t0d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="ai_test_rpool" is_root="true">
                  <be name="ai_test__solaris_be"/>
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
        ......<be name="ai_test__solaris_be"/>
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
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_partition_no_size(self):
        '''Test Success If Have a Disk, containing 1 partition without size
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="390714367secs" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <logical nodump="true" noswap="true"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714368secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <slice name="0" action="create" force="false"
                   is_swap="false"/>
                </partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714368secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_partition_no_start_sector(self):
        '''Test Success If Have a Disk, with 1 partition w/out start_sector
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="30G"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="25G" start_sector="512"/>
                  </slice>
                </partition>
              </disk>
              <logical nodump="true" noswap="true"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="62914560secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="52428800secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="30G" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="30G"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="62914560secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="62914048secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_2_partition_no_start_sector(self):
        '''Test Success If Have a Disk, with 2 partition w/out start_sector
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="25G"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="20G" start_sector="512"/>
                  </slice>
                </partition>
                <partition action="create" name="2" part_type="11">
                  <size val="4G"/>
                </partition>
              </disk>
              <logical nodump="true" noswap="true"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="52428800secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="41943040secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ....<partition action="create" name="2" part_type="11">
        ......<size val="8388608secs" start_sector="52429824"/>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_if_disk_with_2_slice_no_start_sector(self):
        '''Test Success If Have a Disk, containing 2 slice without start_sector
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c7d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="1" part_type="191">
                  <size val="30G" start_sector="512"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false">
                    <size val="20G"/>
                  </slice>
                  <slice name="1" action="create" force="false"
                   is_swap="false">
                    <size val="9G"/>
                  </slice>
                </partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="62914560secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="41942528secs" start_sector="512"/>
        ......</slice>
        ......<slice name="1" action="create" force="false" is_swap="false">
        ........<size val="18873856secs" start_sector="41943552"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_rpool_1_disk_and_data_2_disk(self):
        '''Test Success If Have 1 Disk in the Root Pool, Data Pool with 2 Disks
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create">
                  </zpool>
                  <zpool name="ai_test_data"/>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ....<zpool name="ai_test_data" action="create" is_root="false">
        ......<vdev name="vdev" redundancy="mirror"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="vdev">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_rpool_2_disk_mirror_and_2_disk_spare(self):
        '''Test Success If Have 2 Disks in the Root Pool and 2 Disks spare
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="mirrored">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="mirrored">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="spared">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="spared">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create">
                    <vdev name="mirrored" redundancy="mirror"/>
                    <vdev name="spared" redundancy="spare"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="mirrored" redundancy="mirror"/>
        ......<vdev name="spared" redundancy="spare"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="mirrored">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="mirrored">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="spared">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="spared">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_data_pool_2_disk_mirror_and_2_logmirror(self):
        '''Test Success If Have 2 Disks in a Data Pool and 2 Disks log-mirror
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root">
                  <disk_name name="c10t0d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="mirrored">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="mirrored">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="mirrored-log">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="mirrored-log">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create"/>
                  <zpool name="ai_test_data" is_root="false" action="create">
                    <vdev name="mirrored" redundancy="mirror"/>
                    <vdev name="mirrored-log" redundancy="logmirror"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ....<zpool name="ai_test_data" action="create" is_root="false">
        ......<vdev name="mirrored" redundancy="mirror"/>
        ......<vdev name="mirrored-log" redundancy="logmirror"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="mirrored" whole_disk="true">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="mirrored" whole_disk="true">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="mirrored-log" \
        whole_disk="true">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="mirrored-log" \
        whole_disk="true">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_data_pool_3_disk_raid2(self):
        '''Test Success If Have 3 Disks in a Data Pool with RAIDZ2
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root">
                  <disk_name name="c10t0d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data" in_vdev="raid">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data" in_vdev="raid">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data" in_vdev="raid">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create"/>
                  <zpool name="ai_test_data" is_root="false" action="create">
                    <vdev name="raid" redundancy="raidz2"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ....<zpool name="ai_test_data" action="create" is_root="false">
        ......<vdev name="raid" redundancy="raidz2"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="raid" whole_disk="true">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="raid" whole_disk="true">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="raid" whole_disk="true">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_data_pool_2_disk_mirror_1_hot_spare_1_log(self):
        '''Test Success If Have 2 Disks in a Data Pool with hot-spare and log
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root">
                  <disk_name name="c10t0d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="ai_test_spare">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_data"
                 in_vdev="ai_test_log">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create"/>
                  <zpool name="ai_test_data" is_root="false" action="create">
                    <vdev name="ai_test_mirrored" redundancy="mirror"/>
                    <vdev name="ai_test_spare" redundancy="spare"/>
                    <vdev name="ai_test_log" redundancy="log"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ....<zpool name="ai_test_data" action="create" is_root="false">
        ......<vdev name="ai_test_mirrored" redundancy="mirror"/>
        ......<vdev name="ai_test_spare" redundancy="spare"/>
        ......<vdev name="ai_test_log" redundancy="log"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c10t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="vdev">
        ........<size val="625139712secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="ai_test_mirrored" \
        whole_disk="true">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="ai_test_mirrored" \
        whole_disk="true">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="ai_test_spare" \
        whole_disk="true">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        ..<disk in_zpool="ai_test_data" in_vdev="ai_test_log" \
        whole_disk="true">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_rpool_2_disk_mirror_1_hot_spare_1_cache(self):
        '''Test Success If Have 2 Disks in a Root Pool with hot-spare and cache
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_spare">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_cache">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create">
                    <vdev name="ai_test_mirrored" redundancy="mirror"/>
                    <vdev name="ai_test_spare" redundancy="spare"/>
                    <vdev name="ai_test_cache" redundancy="cache"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="ai_test_mirrored" redundancy="mirror"/>
        ......<vdev name="ai_test_spare" redundancy="spare"/>
        ......<vdev name="ai_test_cache" redundancy="cache"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_mirrored">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_mirrored">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_spare">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_cache">
        ........<size val="390713344secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_use_existing_solaris2_target(self):
        '''Test Success if use_existing_solaris2 target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c10t1d0" name_type="ctd"/>
                <partition action="use_existing_solaris2"/>
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
        ....<disk_name name="c10t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="use_existing_solaris2" name="1" part_type="191">
        ......<size val="348144615secs" start_sector="0"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="348143616secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_use_existing_solaris2_target_with_slices(self):
        '''Test Success if use_existing_solaris2 target with slices in manifest
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c10t2d0" name_type="ctd"/>
                <partition action="use_existing_solaris2">
                  <slice name="0" action="create" force="true"
                   is_swap="false">
                    <size val="9Gb" start_sector="48000"/>
                  </slice>
                  <slice name="1" action="delete" force="false"
                   is_swap="false"/>
                  <slice name="3" action="delete" force="false"
                   is_swap="false"/>
                  <slice name="7" action="delete" force="false"
                   is_swap="false"/>
                  <slice name="8" action="delete" force="false"
                   is_swap="false"/>
                </partition>
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
        ....<disk_name name="c10t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="use_existing_solaris2" name="1" part_type="191">
        ......<size val="348144615secs" start_sector="0"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="18873856secs" start_sector="48128"/>
        ......</slice>
        ......<slice name="1" action="delete" force="false" is_swap="false">
        ........<size val="1060290secs" start_sector="48195"/>
        ......</slice>
        ......<slice name="3" action="delete" force="false" is_swap="false">
        ........<size val="43022070secs" start_sector="1108485"/>
        ......</slice>
        ......<slice name="7" action="delete" force="false" is_swap="false">
        ........<size val="190257795secs" start_sector="44130555"/>
        ......</slice>
        ......<slice name="8" action="delete" force="false" is_swap="false">
        ........<size val="16065secs" start_sector="0"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_gpt_rpool_2_disk_mirror_1_spare_1_cache(self):
        '''Test Success If Disks w/GPT labels, 2 Disks in rpool w/spare & cache
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
              <target>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_mirrored">
                  <disk_name name="c7d1" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_spare">
                  <disk_name name="c8d0" name_type="ctd"/>
                </disk>
                <disk whole_disk="true" in_zpool="ai_test_root"
                 in_vdev="ai_test_cache">
                  <disk_name name="c8d1" name_type="ctd"/>
                </disk>
                <logical>
                  <zpool name="ai_test_root" is_root="true" action="create">
                    <vdev name="ai_test_mirrored" redundancy="mirror"/>
                    <vdev name="ai_test_spare" redundancy="spare"/>
                    <vdev name="ai_test_cache" redundancy="cache"/>
                  </zpool>
                </logical>
             </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_root" action="create" is_root="true">
        ......<vdev name="ai_test_mirrored" redundancy="mirror"/>
        ......<vdev name="ai_test_spare" redundancy="spare"/>
        ......<vdev name="ai_test_cache" redundancy="cache"/>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_mirrored">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_mirrored">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_spare">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c8d1" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_root" in_vdev="ai_test_cache">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        for disk in self.disks:
            disk.label = "GPT"

        # When GPT support gets added and bug : 7037884 gets fixed we
        # can re-enable this test
        #self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_no_target_all_gpt_disks(self):
        '''Test Success if no target in manifest with all GPT disks'''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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

        for disk in self.disks:
            disk.label = "GPT"

        # When GPT support gets added and bug : 7037884 gets fixed we
        # can re-enable this test
        #self.__run_simple_test(None, expected_xml)

    def test_target_selection_no_disk_target_with_logical_all_gpt_disks(self):
        '''Test Success if no disks, but with logical section and all GPT
        '''

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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714880secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="390714880secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        for disk in self.disks:
            disk.label = "GPT"

        # When GPT support gets added and bug : 7037884 gets fixed we
        # can re-enable this test
        #self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_slice_too_large(self):
        '''Test Fail if slice is specified with a value too large'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
            <target>
             <disk>
                <disk_name name_type="ctd" name="c7d0"/>
                <partition action="delete" name="1"/>
                <partition action="delete" name="3"/>
                <partition name="2" action="create" part_type="191">
                  <size val="20gb" start_sector="100000"/>
                  <slice name="0" action="create" is_swap="false"
                   in_zpool="rpool" in_vdev="vdev">
                    <size val="20000001mb"/>
                  </slice>
                </partition>
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
            fail_ex_str="Slice 0 has a size larger than the "
                        "containing partition 2")

    def test_target_selection_partition_too_large(self):
        '''Test Fail if partition is specified with a value too large'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
            <target>
             <disk>
                <disk_name name_type="ctd" name="c7d0"/>
                <partition action="delete" name="1"/>
                <partition action="delete" name="3"/>
                <partition name="2" action="create" part_type="191">
                  <size val="200000000mb" start_sector="100000"/>
                  <slice name="0" action="create" is_swap="false"
                   in_zpool="rpool" in_vdev="vdev">
                    <size val="200000001mb"/>
                  </slice>
                </partition>
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
            fail_ex_str="Partition 2 has a size larger than the disk c7d0")

    def test_target_selection_multiple_partitions_and_existing_partition(self):
        '''Test Success if multiple partitions and existing partition'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
            <target>
             <disk>
                <disk_name name_type="ctd" name="c7d0"/>
                <partition name="3" action="delete"/>
                <partition name="2" action="create" part_type="191">
                  <size val="20000mb"/>
                  <slice name="0" action="create" is_swap="false"
                   in_zpool="ai_test_rpool" in_vdev="vdev">
                    <size val="19999mb"/>
                  </slice>
                </partition>
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
        expected_xml = ""

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_swap_and_dump_size(self):
        '''Test Success In Calc of Swap and Dump Size'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name_type="ctd" name="c7d0"/>
                  <partition name="2" action="delete"/>
                  <partition name="3" action="delete"/>
                  <partition name="1" action="create" part_type="191">
                    <slice name="0" action="create" is_swap="false"
                     in_zpool="ai_test_rpool" in_vdev="vdev">
                    <size val="6GB"/>
                    </slice>
                  </partition>
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
        ........<size val="682m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="341m"/>
        ......</zvol>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="390714368secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="12582400secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_create_logical_partition(self):
        '''Test Success Creating a logical partition'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk>
                <disk_name name_type="ctd" name="c7d0"/>
                <partition action="delete" name="1"/>
                <partition action="delete" name="2"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="4" part_type="5">
                  <size val="15000mb"/>
                </partition>
                <partition action="create" name="6" part_type="191">
                  <size val="10240mb"/>
                </partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="delete" name="1" part_type="175">
        ......<size val="401625secs" start_sector="0"/>
        ....</partition>
        ....<partition action="delete" name="2" part_type="175">
        ......<size val="133949970secs" start_sector="401625"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="4" part_type="5">
        ......<size val="30720000secs" start_sector="512"/>
        ....</partition>
        ....<partition action="create" name="6" part_type="191">
        ......<size val="20971457secs" start_sector="575"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="20970496secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_too_many_extended_partitions(self):
        '''Test Fail with too many extended partitions'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance name="ai_test_manifest" auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name_type="ctd" name="c3d0"/>
                <partition action="delete" name="7" part_type="191">
                  <size val="0mb"/>
                </partition>
                <partition action="create" name="3" part_type="12">
                  <size val="2.99gb"/>
                </partition>
                <partition action="create" name="4" part_type="5">
                  <size val="9000mb"/>
                </partition>
                <partition action="create" name="5" part_type="191">
                  <size val="8000mb"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false"/>
                </partition>
              </disk>
              <logical noswap="false" nodump="false">
                <zpool name="ai_test_rpool" is_root="true" action="create">
                  <vdev name="vdev" redundancy="none"/>
                  <filesystem name="/testing" in_be="true" action="create"/>
                </zpool>
              </logical>
            </target>
         </ai_instance>
        </auto_install>
        '''

        expected_xml = ""

        self.__run_simple_test(test_manifest_xml, expected_xml,
            fail_ex_str="It is only possible to have at most 1 "
                        "extended partition defined")

    def test_target_selection_delete_non_existant(self):
        '''Test Success deleting a non-existant partition'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk>
                <disk_name name_type="ctd" name="c7d0"/>
                <partition action="delete" name="3"/>
                <partition action="delete" name="4"/>
                <partition action="create" name="2">
                    <size val="10G"/>
                </partition>
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
        ....<disk_name name="c7d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="390715392secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="preserve" name="1" part_type="175">
        ......<size val="401625secs" start_sector="0"/>
        ....</partition>
        ....<partition action="delete" name="3" part_type="130">
        ......<size val="234420480secs" start_sector="134367660"/>
        ....</partition>
        ....<partition action="create" name="2" part_type="191">
        ......<size val="20971520secs" start_sector="401920"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="20971008secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_delete_extended_includes_logical(self):
        '''Test Success deleting an extended, deletes logicals'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance name="ai_test_manifest" auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name_type="ctd" name="c3d0"/>
                <partition action="delete" name="1"/>
                <partition action="delete" name="3"/>
                <partition action="create" name="4" part_type="5">
                  <size val="9000mb"/>
                </partition>
                <partition action="create" name="5" part_type="191">
                  <size val="8000mb"/>
                  <slice name="0" action="create" force="false"
                   is_swap="false"/>
                </partition>
              </disk>
              <logical noswap="false" nodump="false">
                <zpool name="ai_test_rpool" is_root="true" action="create">
                  <vdev name="vdev" redundancy="none"/>
                  <filesystem name="/testing" in_be="true" action="create"/>
                </zpool>
              </logical>
            </target>
         </ai_instance>
        </auto_install>
        '''

        expected_xml = ""

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_create_different_partition(self):
        '''Test Success creating solaris partition beside existing partition'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk>
                <disk_name name="c10t3d0" name_type="ctd"/>
                <partition action="create" name="2" part_type="191">
                    <size val="10240mb"/>
                    <slice name="0" action="create"/>
                </partition>
            </disk>
            <logical noswap="true" nodump="true">
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
        ..<logical noswap="true" nodump="true">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c10t3d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="preserve" name="1" part_type="11">
        ......<size val="3341520secs" start_sector="0"/>
        ....</partition>
        ....<partition action="create" name="2" part_type="191">
        ......<size val="20971520secs" start_sector="3341824"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="vdev">
        ........<size val="20971008secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
              <disk_name name="c10t4d0" name_type="ctd"/>
              <partition action="create" name="1" part_type="191">
                <slice name="1" action="create" is_swap="false"
                   in_zpool="ai_test_rpool" in_vdev="rpool-none">
                   <size val="276976665secs"/>
                </slice>
              </partition>
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
        ....<disk_name name="c10t4d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="rpool-none">
        ........<size val="276976128secs" start_sector="512"/>
        ......</slice>
        ....</partition>
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
              <disk_name name="c10t4d0" name_type="ctd"/>
              <partition action="create" name="1" part_type="191">
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
              </partition>
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
        ....<disk_name name="c10t4d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="625141760secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="625141248secs" start_sector="512"/>
        ......<slice name="1" action="create" force="false" is_swap="false" \
        in_zpool="ai_test_rpool" in_vdev="rpool-none">
        ........<size val="276976128secs" start_sector="512"/>
        ......</slice>
        ......<slice name="3" action="create" force="false" is_swap="true">
        ........<size val="2096640secs" start_sector="276977152"/>
        ......</slice>
        ......<slice name="5" action="create" force="false" is_swap="false">
        ........<size val="2096640secs" start_sector="279074304"/>
        ......</slice>
        ......<slice name="7" action="create" force="false" is_swap="true">
        ........<size val="2096640secs" start_sector="281171456"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

if __name__ == '__main__':
    unittest.main()

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

import difflib
import os
import platform
import re
import unittest

import osol_install.errsvc as errsvc
from lxml import etree
from solaris_install.auto_install.checkpoints.target_selection \
    import TargetSelection
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine
from solaris_install.target import Target, CRO_LABEL, logical
from solaris_install.target.physical import Disk


class TestTargetSelectionTestCase(unittest.TestCase):
    DISCOVERED_TARGETS_XML = '''
    <root>
      <target name="discovered">
        <disk whole_disk="false">
          <disk_name name="c18t0d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" dev_size="286728120secs"/>
          <partition action="preserve" name="1" part_type="191">
            <size val="286712055secs" start_sector="16065"/>
            <slice name="0" action="preserve" force="false" is_swap="false" in_zpool="myrpool" in_vdev="myrpool-none">
              <size val="286663860secs" start_sector="16065"/>
            </slice>
            <slice name="2" action="preserve" force="false" is_swap="false">
              <size val="286679925secs" start_sector="0"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c18t1d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" dev_size="286728120secs"/>
          <partition action="preserve" name="1" part_type="15">
            <size val="286712055secs" start_sector="16065"/>
          </partition>
          <partition action="preserve" name="5" part_type="191">
            <size val="819137secs" start_sector="16128"/>
            <slice name="0" action="preserve" force="false" is_swap="false">
              <size val="610470secs" start_sector="16065"/>
            </slice>
            <slice name="2" action="preserve" force="false" is_swap="false">
              <size val="286679925secs" start_sector="0"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
          </partition>
          <partition action="preserve" name="6" part_type="191">
            <size val="1638400secs" start_sector="835428"/>
            <slice name="0" action="preserve" force="false" is_swap="false">
              <size val="610470secs" start_sector="16065"/>
            </slice>
            <slice name="2" action="preserve" force="false" is_swap="false">
              <size val="286679925secs" start_sector="0"/>
            </slice>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16065secs" start_sector="0"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c18t2d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" dev_size="143358286secs"/>
          <partition action="preserve" name="1" part_type="238">
            <size val="143374737secs" start_sector="1"/>
            <slice name="8" action="preserve" force="false" is_swap="false">
              <size val="16384secs" start_sector="143358321"/>
            </slice>
          </partition>
        </disk>
        <disk whole_disk="false">
          <disk_name name="c18t3d0" name_type="ctd"/>
          <disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" dev_size="143364060secs"/>
          <disk_keyword key="boot_disk"/>
          <partition action="preserve" name="1" part_type="15">
            <size val="114688035secs" start_sector="16065"/>
          </partition>
          <partition action="preserve" name="5" part_type="11">
            <size val="32129937secs" start_sector="16128"/>
          </partition>
          <partition action="preserve" name="6" part_type="11">
            <size val="32129937secs" start_sector="32146128"/>
          </partition>
        </disk>
        <logical noswap="false" nodump="false">
          <zpool name="myrpool" action="preserve" is_root="true" mountpoint="/myrpool">
            <vdev name="myrpool-none" redundancy="none"/>
            <filesystem name="export" action="preserve" mountpoint="/export" in_be="false"/>
            <filesystem name="export/home" action="preserve" mountpoint="/export/home" in_be="false"/>
            <zvol name="swap" action="preserve" use="swap">
              <size val="8.50gb"/>
            </zvol>
            <zvol name="dump" action="preserve" use="dump">
              <size val="8.00gb"/>
            </zvol>
            <be name="solaris"/>
            <be name="sol164"/>
            <be name="sol165"/>
            <be name="sol166"/>
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
        logical.DEFAULT_BE_NAME = "ai_test_solaris"
        self.engine = get_new_engine_instance()

        self.target_selection = TargetSelection("Test Checkpoint")
        self.doc = InstallEngine.get_instance().data_object_cache
        discovered_dom = etree.fromstring(self.DISCOVERED_TARGETS_XML)
        self.doc.import_from_manifest_xml(discovered_dom, volatile=False)

        # Register the CRO Information
        cro_dict = {'c18t0d0': (3, 'SYS', 'SYS/HD2'),
                    'c18t1d0': (1, 'SYS', 'SYS/HD0'),
                    'c18t2d0': (4, 'SYS', 'SYS/HD3'),
                    'c18t3d0': (2, 'SYS', 'SYS/HD1')}
        self.doc.persistent.insert_children(
            DataObjectDict(CRO_LABEL, cro_dict, generate_xml=True))

        # As we are not really discovering disks, label  will be set to "None"
        # Ensure they set to VTOC
        # Also ensure that the CRO details are correctly set since can't be
        # set in the XML.
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "VTOC"
            if disk.ctd in cro_dict:
                (index, chassis, receptacle) = cro_dict[disk.ctd]
                disk.receptacle = receptacle

    def tearDown(self):
        if self.engine is not None:
            reset_engine(self.engine)

        self.doc = None
        self.target_selection = None

    def test_cro_target_selection_no_target(self):
        '''Test CRO Success if no target in manifest'''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c18t3d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143364060secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143363072secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="143361536secs" start_sector="512"/>
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

    def test_cro_target_selection_no_disk_target_with_logical(self):
        '''Test CRO Success if no disk targets, but with a logical section'''

        test_manifest_xml = '''
        <auto_install>
           <ai_instance name="orig_default">
             <target>
               <logical>
                 <zpool name="myrpool" is_root="true">
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
        ....<zpool name="myrpool" action="create" is_root="true">
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
        ....<disk_name name="c18t3d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143364060secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143363072secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="myrpool" in_vdev="vdev">
        ........<size val="143361536secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_cro_target_selection_single_whole_disk_target(self):
        '''Test CRO Success if single whole target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="SYS/HD3" name_type="receptacle"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c18t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143358286secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143357440secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="143355904secs" start_sector="512"/>
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

    def test_cro_target_selection_boot_disk_target(self):
        '''Test CRO Success if boot_disk target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="myrpool" in_vdev="vdev">
                <disk_keyword key="boot_disk" />
              </disk>
              <logical>
                <zpool name="myrpool" is_root="true">
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
        ....<zpool name="myrpool" action="create" is_root="true">
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
        ....<disk_name name="c18t3d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143364060secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143363072secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="myrpool" in_vdev="vdev">
        ........<size val="143361536secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_cro_target_selection_multiple_whole_disk_targets(self):
        '''Test CRO Success if multiple disk targets, no zpool, in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="True">
                <disk_name name="c18t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="True">
                <disk_name name="c18t2d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk whole_disk="false">
        ....<disk_name name="c18t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" \
        dev_size="286728120secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="286727168secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="286725632secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143358286secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143357440secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="143355904secs" start_sector="512"/>
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

    def test_cro_target_selection_multiple_whole_disk_false_no_logicals(self):
        '''Test CRO Success if multiple partitioned disks, no logical, in manifest.
        '''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c18t0d0" name_type="ctd"/>
                <partition action="delete" name="2"/>
                <partition action="create" name="1" part_type="191">
                  <slice name="0" action="create" force="false"
                   is_swap="false"/>
                </partition>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c18t2d0" name_type="ctd"/>
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
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" \
        dev_size="286728120secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="286727168secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="286725632secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143358286secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143357440secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="143355904secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_cro_target_selection_multiple_whole_disk_mixed_no_logicals(self):
        '''Test CRO Success if 1 whole & 1 partitioned disk, no logicals'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c18t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c18t2d0" name_type="ctd"/>
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
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" \
        dev_size="286728120secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="286727168secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="286725632secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143358286secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143357440secs" start_sector="512"/>
        ......<slice name="0" action="create" force="false" is_swap="false" \
        in_zpool="rpool" in_vdev="vdev">
        ........<size val="143355904secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_cro_target_selection_2_disks_whole_disk_true_and_rpool(self):
        '''Test CRO Success if 2 disks, whole_disk=True & root pool'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true" in_zpool="myrpool">
                <disk_name name="c18t0d0" name_type="ctd" />
              </disk>
              <disk whole_disk="true" in_zpool="myrpool">
                <disk_name name="c18t2d0" name_type="ctd"/>
              </disk>
              <logical>
                <zpool name="myrpool" is_root="true"/>
              </logical>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="myrpool" action="create" is_root="true">
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
        ....<disk_name name="c18t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" \
        dev_size="286728120secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="286727168secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="myrpool" in_vdev="vdev">
        ........<size val="286725632secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c18t2d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="FUJITSU" dev_chassis="SYS" \
        dev_size="143358286secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="143357440secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="myrpool" in_vdev="vdev">
        ........<size val="143355904secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

    def test_cro_target_selection_dev_chassis(self):
        '''Test CRO Success if dev_chassis attribute specified'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_prop dev_chassis="SYS"/>
              </disk>
              <logical>
                <zpool name="myrpool" is_root="true">
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
        ....<zpool name="myrpool" action="create" is_root="true">
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
        ....<disk_name name="c18t1d0" name_type="ctd"/>
        ....<disk_prop dev_type="scsi" dev_vendor="SEAGATE" dev_chassis="SYS" \
        dev_size="286728120secs"/>
        ....<partition action="create" name="1" part_type="191">
        ......<size val="286727168secs" start_sector="512"/>
        ......<slice name="0" action="create" force="true" is_swap="false" \
        in_zpool="myrpool" in_vdev="vdev">
        ........<size val="286725632secs" start_sector="512"/>
        ......</slice>
        ....</partition>
        ..</disk>
        </target>
        '''

        self.__run_simple_test(test_manifest_xml, expected_xml)

if __name__ == '__main__':
    unittest.main()

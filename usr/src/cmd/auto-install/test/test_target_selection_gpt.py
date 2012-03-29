#! /usr/bin/python
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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
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
from solaris_install.target.physical import Disk, GPTPartition
from solaris_install.target.libefi.const import EFI_BIOS_BOOT, EFI_SYSTEM


class TargetSelectionBase(object):
    # Useful when trying to understand XML:
    #
    #   dev_size="625141760secs" probably using 512 byte sectors
    #   Therefore 625141760secs ~ 298GB
    #             525141760secs ~ 250GB
    #
    # Common GUIDs (these all have p_tag for libefi):
    #   ZFS_USR = {6a898cc3-1dd2-11b2-99a6-080020736631} = "solaris"
    #   EFI_SYSTEM = {c12a7328-f81f-11d2-ba4b-00a0c93ec93b} = "esp"
    #   EFI_BIOS_BOOT = {21686148-6449-6E6F-744E-656564454649} = "bbp"
    #   EFI_RESERVED = {6a945a3b-1dd2-11b2-99a6-080020736631} = "reserved"
    #
    #   EFI_MSFT_BASIC_DATA = {ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}
    #   EFI_LINUX_LVM = {e6d6d379-f507-44c2-a23c-238f2a3df928}
    #
    # Can be only 1 boot disk
    DISCOVERED_TARGETS_XML = '''
    <root>
      <target name="discovered">
        <disk whole_disk="false">
          <disk_name name="c99t0d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_vendor="Lenovo"
          dev_size="625141760secs"/>
          <gpt_partition name="1" action="preserve" force="false"
                         part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}">
            <size val="524288secs" start_sector="256"/>
          </gpt_partition>
          <gpt_partition name="2" action="preserve" force="false"
                         part_type="{6a898cc3-1dd2-11b2-99a6-080020736631}">
            <size val="524617728secs" start_sector="524288"/>
          </gpt_partition>
        </disk>

        <disk whole_disk="false">
          <disk_name name="c97d0" name_type="ctd"/>
          <disk_prop dev_type="FIXED" dev_size="625141760secs"/>
          <disk_keyword key="boot_disk"/>
          <gpt_partition name="0" action="preserve" force="false"
                         part_type="%s">
            <size val="524288secs" start_sector="256"/>
          </gpt_partition>
          <gpt_partition name="1" action="preserve" force="false"
                         part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}">
            <size val="31457280secs" start_sector="524544"/>
          </gpt_partition>
          <gpt_partition name="2" action="preserve" force="false"
                         part_type="{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}">
            <size val="31457280secs" start_sector="31982080"/>
          </gpt_partition>
          <gpt_partition name="3" action="preserve" force="false"
                         part_type="solaris">
            <size val="41943040secs" start_sector="63439616"/>
          </gpt_partition>
          <gpt_partition name="4" action="preserve" force="false"
                         part_type="solaris">
            <size val="519741701secs" start_sector="105382912"/>
          </gpt_partition>
          <gpt_partition name="8" action="preserve" force="false" \
                         part_type="reserved">
            <size val="16640secs" start_sector="625124864"/>
          </gpt_partition>
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

    def _run_simple_test(self, input_xml, expected_xml, fail_ex_str=None,
        dry_run=True):
        '''Run a simple test where given specific xml in the manifest, we
        validate that the generated DESIRED tree is as expected.

        'expected_xml' should have the values indented using '.' instead of
        spaces to ensure that perfect match is made.
        '''
        errsvc.clear_error_list()

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
            desired = self.doc.get_descendants(name=Target.DESIRED,
                class_type=Target, max_depth=2, not_found_is_err=True)[0]

            xml_str = desired.get_xml_tree_str()

            expected_re = re.compile(expected_xml)
            if not expected_re.match(xml_str):
                #self.fail("Resulting XML doesn't match "
                #          "expected:\nDIFF:\n%s\n" %
                #          self.__gendiff_str(expected_xml, xml_str))
                self.fail("Resulting XML doesn't match "
                          "expected:\nDIFF:\n%s\n\n\n%s" %
                          (self.__gendiff_str(expected_xml, xml_str),
                          xml_str))

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

        # As we are not really discovering disks, label will be set to "None"
        # Ensure they set to GPT
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "GPT"

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
        ..<disk in_zpool="rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
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

        self._run_simple_test(None, expected_xml)

    def test_target_selection_one_solaris_gpt(self):
        ''' XXX Test Success if it does the right thing....'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
                <gpt_partition name="1" action="create" part_type="solaris"/>
              </disk>
            </target>
          </ai_instance>
        </auto_install>
        '''

        # Shadow list tests sizing, don't do that here.
        # All size and start_sector should be \d+

        expected_xml = '''\
        <target name="desired">
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
        ..<disk whole_disk="false">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<gpt_partition name="0" action="create" force="true" \
        part_type="%s">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="1" action="create" force="false" \
        part_type="solaris" in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="8" action="create" force="true" \
        part_type="reserved">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ..</disk>
        </target>
        ''' % ((self.SYSTEM,) * 1)
        self._run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_no_disk_target_with_logical(self):
        '''Test Success if no disk targets, but with a logical section'''

        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
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
        ..<disk in_zpool="ai_test_rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        </target>
        '''
        self._run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_single_whole_disk_target(self):
        '''Test Success if single whole target in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk in_zpool="rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="none"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''
        self._run_simple_test(test_manifest_xml, expected_xml)

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
        ..<disk in_zpool="ai_test_rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="625141760secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        </target>
        '''
        self._run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_multiple_whole_disk_targets(self):
        '''Test Success if multiple disk targets, no zpool, in manifest'''
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="true">
                <disk_name name="c99t0d0" name_type="ctd"/>
              </disk>
              <disk whole_disk="true">
                <disk_name name="c97d0" name_type="ctd"/>
              </disk>
              <logical noswap="true" nodump="true"/>
            </target>
          </ai_instance>
        </auto_install>
        '''

        expected_xml = '''\
        <target name="desired">
        ..<disk in_zpool="rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ..</disk>
        ..<disk in_zpool="rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ..</disk>
        ..<logical noswap="true" nodump="true">
        ....<zpool name="rpool" action="create" is_root="true">
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        </target>
        '''
        self._run_simple_test(test_manifest_xml, expected_xml)

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
                <disk_name name="c97d0" name_type="ctd"/>
                <gpt_partition action="delete" name="3"
                  part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}"/>
                <gpt_partition action="delete" name="2"
                  part_type="{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}"/>
                <gpt_partition action="create" name="1" part_type="solaris">
                  <size val="41943040secs" start_sector="524544"/>
                </gpt_partition>
                <gpt_partition action="preserve" name="4" part_type="solaris"/>
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
        ..<disk in_zpool="rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<gpt_partition name="0" action="%s" force="false" \
        part_type="%s">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="1" action="create" force="false" \
        part_type="solaris" in_zpool="rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="2" action="delete" force="false" \
        part_type="{\w+-\w+-\w+-\w+-\w+}">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="3" action="delete" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="4" action="preserve" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="8" action="preserve" force="false" \
        part_type="reserved">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ..</disk>
        </target>
        ''' % (self.SYS_ACTION, self.SYSTEM)
        self._run_simple_test(test_manifest_xml, expected_xml)

    def test_target_selection_2_disks_whole_disk_false_and_rpool(self):
        '''Test Success If 2 Disks w/Whole-Disks = False & Root Pool Specified
        '''
        # Notice c99t0d0 gpt_partition 2 will be a donor for system/reserve
        # which will be created for us...
        test_manifest_xml = '''
        <auto_install>
          <ai_instance auto_reboot="false">
            <target>
              <disk whole_disk="false">
                <disk_name name="c99t0d0" name_type="ctd"/>
                <gpt_partition action="delete" name="1"
                  part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}"/>
                <gpt_partition action="create" name="2"
                  part_type="solaris" in_zpool="ai_test_rpool"/>
              </disk>
              <disk whole_disk="false">
                <disk_name name="c97d0" name_type="ctd"/>
                <gpt_partition action="delete" name="3"
                  part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}"/>
                <gpt_partition action="delete" name="2"
                  part_type="{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}"/>
                <gpt_partition action="create" name="1"
                  part_type="solaris" in_zpool="ai_test_rpool">
                  <size val="41943040secs" start_sector="524544"/>
                </gpt_partition>
                <gpt_partition action="preserve" name="4"
                  part_type="solaris"/>
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
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ....<gpt_partition name="0" action="create" force="true" \
        part_type="%s">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="1" action="delete" force="false" \
        part_type="{\w+-\w+-\w+-\w+-\w+}">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="2" action="create" force="false" \
        part_type="solaris" in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="8" action="create" force="true" \
        part_type="reserved">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<gpt_partition name="0" action="%s" force="false" \
        part_type="%s">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="1" action="create" force="false" \
        part_type="solaris" in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="2" action="delete" force="false" \
        part_type="{\w+-\w+-\w+-\w+-\w+}">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="3" action="delete" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="4" action="preserve" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="8" action="preserve" force="false" \
        part_type="reserved">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ..</disk>
        </target>
        ''' % (self.SYSTEM, self.SYS_ACTION, self.SYSTEM)
        self._run_simple_test(test_manifest_xml, expected_xml)

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
                <disk_name name="c97d0" name_type="ctd"/>
                <gpt_partition action="delete" name="3"
                  part_type="{e6d6d379-f507-44c2-a23c-238f2a3df928}"/>
                <gpt_partition action="delete" name="2"
                  part_type="{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}"/>
                <gpt_partition action="create" name="1"
                  part_type="solaris" in_zpool="ai_test_rpool">
                  <size val="41943040secs" start_sector="524544"/>
                </gpt_partition>
                <gpt_partition action="preserve" name="4"
                  part_type="solaris"/>
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

        # Because in_zool is set c99t0d0 gets carved up instead of letting
        # ZFS do it.
        expected_xml = '''\
        <target name="desired">
        ..<logical noswap="false" nodump="false">
        ....<zpool name="ai_test_rpool" action="create" is_root="true">
        ......<zvol name="swap" action="create" use="swap">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<zvol name="dump" action="create" use="dump">
        ........<size val="\d+m"/>
        ......</zvol>
        ......<vdev name="vdev" redundancy="mirror"/>
        ......<be name="ai_test_solaris"/>
        ....</zpool>
        ..</logical>
        ..<disk in_zpool="ai_test_rpool" in_vdev="vdev" whole_disk="true">
        ....<disk_name name="c99t0d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_vendor="Lenovo" \
        dev_size="\d+secs"/>
        ..</disk>
        ..<disk whole_disk="false">
        ....<disk_name name="c97d0" name_type="ctd"/>
        ....<disk_prop dev_type="FIXED" dev_size="\d+secs"/>
        ....<disk_keyword key="boot_disk"/>
        ....<gpt_partition name="0" action="%s" force="false" \
        part_type="%s">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="1" action="create" force="false" \
        part_type="solaris" in_zpool="ai_test_rpool" in_vdev="vdev">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="2" action="delete" force="false" \
        part_type="{\w+-\w+-\w+-\w+-\w+}">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="3" action="delete" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="4" action="preserve" force="false" \
        part_type="solaris">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ....<gpt_partition name="8" action="preserve" force="false" \
        part_type="reserved">
        ......<size val="\d+secs" start_sector="\d+"/>
        ....</gpt_partition>
        ..</disk>
        </target>
        ''' % (self.SYS_ACTION, self.SYSTEM)
        self._run_simple_test(test_manifest_xml, expected_xml)


class TestTargetSelectionTestCaseESP(TargetSelectionBase, unittest.TestCase):

    SYSTEM = "esp"
    SYS_ACTION = "create" # because it will need to be formatted

    DISCOVERED_TARGETS_XML = TargetSelectionBase.DISCOVERED_TARGETS_XML % \
        ("esp")

    def setUp(self):
        super(TestTargetSelectionTestCaseESP, self).setUp()

        # As we are not really discovering disks,
        # bootmgmt.bootinfo.SystemFirmware
        # could report this system as "uefi64" or "bios".
        # Force all disks into "uefi64" mode
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "GPT"

            disk._sysboot_guid = EFI_SYSTEM
            required = list(Disk.reserved_guids)
            required.append(disk.sysboot_guid)
            disk._required_guids = tuple(required)


class TestTargetSelectionTestCaseBBP(TargetSelectionBase, unittest.TestCase):

    SYSTEM = "bbp"
    SYS_ACTION = "preserve" # because it will need to be formatted

    DISCOVERED_TARGETS_XML = TargetSelectionBase.DISCOVERED_TARGETS_XML % \
        ("bbp")

    def setUp(self):
        super(TestTargetSelectionTestCaseBBP, self).setUp()

        # As we are not really discovering disks,
        # bootmgmt.bootinfo.SystemFirmware
        # could report this system as "uefi64" or "bios".
        # Force all disks into "uefi64" mode
        discovered = self.doc.persistent.get_first_child(Target.DISCOVERED)
        self.disks = discovered.get_descendants(class_type=Disk)
        for disk in self.disks:
            if disk.label is None:
                disk.label = "GPT"

            disk._sysboot_guid = EFI_BIOS_BOOT
            required = list(Disk.reserved_guids)
            required.append(disk.sysboot_guid)
            disk._required_guids = tuple(required)

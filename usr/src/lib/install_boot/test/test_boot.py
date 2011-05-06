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

""" Boot checkpoint Unit Tests
"""

import os
import abc
import tempfile
import unittest
import platform
import pwd
import grp

from shutil import rmtree, copyfile
from lxml import etree

from bootmgmt.bootconfig import BootConfig
from solaris_install.boot.boot import SystemBootMenu, AIISOImageBootMenu, \
    TextISOImageBootMenu, LiveCDISOImageBootMenu, BOOT_ENV, DEVS
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine
from solaris_install.target.logical import be_list, BE, Filesystem

TMP_TEST_DIR = "/tmp/boot-test"

BOOT_MODS_XML = '''
<root>
  <boot_mods timeout="20" title="Boot Testing:">
    <boot_entry default_entry="false" insert_at="end">
      <title_suffix>2nd last Boot Entry</title_suffix>
      <kernel_args>test_kernel_args=true</kernel_args>
    </boot_entry>
    <boot_entry default_entry="true" insert_at="start">
      <title_suffix>1st (default) Boot Entry</title_suffix>
      <kernel_args>test_kernel_args=true</kernel_args>
    </boot_entry>
    <boot_entry>
      <title_suffix>Last Boot Entry</title_suffix>
    </boot_entry>
    <boot_entry>
    </boot_entry>
  </boot_mods>
</root>'''

# Physical target representation for X86 tests
PHYS_X86_XML = \
'''<disk whole_disk="false">
    <disk_name name="c600d600" name_type="ctd"/>
    <disk_prop dev_type="FIXED" dev_size="666666666"/>
    <disk_keyword key="boot_disk"/>
    <partition action="preserve" name="1" part_type="191">
      <size val="66666666secs" start_sector="16065"/>
      <slice name="0" action="preserve" force="false" in_zpool="rpool">
        <size val="33479459secs" start_sector="16065"/>
      </slice>
    </partition>
  </disk>
  <disk whole_disk="false">
    <disk_name name="c700d700" name_type="ctd"/>
    <disk_prop dev_type="FIXED" dev_size="777777777"/>
    <partition action="preserve" name="1" part_type="191">
      <size val="33527655secs" start_sector="16065"/>
      <slice name="0" action="preserve" force="false" in_zpool="rpool">
        <size val="33479459secs" start_sector="16065"/>
      </slice>
    </partition>
  </disk>'''

# Physical target representation for SPARC tests
PHYS_SPARC_XML = '''
<root>
  <disk whole_disk="false">
    <disk_name name="c600d600" name_type="ctd"/>
    <disk_prop dev_type="FIXED" dev_size="666666666"/>
    <disk_keyword key="boot_disk"/>
    <slice name="0" action="preserve" force="false" in_zpool="rpool">
      <size val="33479459secs" start_sector="16065"/>
    </slice>
  </disk>
  <disk whole_disk="false">
    <disk_name name="c700d700" name_type="ctd"/>
    <disk_prop dev_type="FIXED" dev_size="777777777"/>
      <slice name="0" action="preserve" force="false" in_zpool="rpool">
        <size val="33479459secs" start_sector="16065"/>
      </slice>
  </disk>
</root>'''

# This is a template logical target specification. The physical part is
# populated with the appropriate architecture specific physical specification
# above. The logical part is populated based on a run time inspection of the
# live system's active BE and pool(s).
DYNAMIC_DESIRED_XML = '''
<root>
<target name="desired">
  %(phys_xml)s
  <logical noswap="true" nodump="true">
    <zpool name="%(rpoolname)s" action="preserve" is_root="true">
      <be name="%(bename)s" mountpoint="%(bemount)s"/>
    </zpool>
  </logical>
</target>
</root>'''


class BootMenuTestCaseBase(unittest.TestCase):
    """ Abstracy base class for unit tests that doesn't run any tests of
        its own, but sets up an environment for boot unit tests
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, test_case_name):
        """ Constructor for class so that architecture can be overriden if
            necessary
        """
        super(BootMenuTestCaseBase, self).__init__(test_case_name)
        self.arch = platform.processor()

    def setUp(self):
        """ Common unit test setup method for all subclasses
        """
        self.engine = get_new_engine_instance()
        self.doc = InstallEngine.get_instance().data_object_cache
        if not os.path.exists(TMP_TEST_DIR):
            os.makedirs(TMP_TEST_DIR)

    def tearDown(self):
        """ Common unit test tear down method for all subclasses
        """
        if self.engine:
            reset_engine(self.engine)
        self.doc = None
        self.boot_mods = None
        self.boot_menu = None
        self.arch = None


class SystemBootMenuTestCase(BootMenuTestCaseBase):
    """ Class for unit testing of SystemBootMenu class
    """

    def setUp(self):
        """ Initialises a runtime environment for execution of
            SystemBootMenu unit tests.
        """
        super(SystemBootMenuTestCase, self).setUp()

        desired_dict = {}
        # For the purposes of having a sane environment for the
        # test case, use the active BE. This allows pybootmgt
        # initialisation to locate all the bits it expects.
        for self.be_name, be_pool, be_root_ds in be_list():
            be_fs = Filesystem(be_root_ds)
            if be_fs.get('mounted') == 'yes' and \
               be_fs.get('mountpoint') == '/':
                desired_dict["rpoolname"] = be_pool
                desired_dict["rpoolmount"] = \
                    Filesystem(be_pool).get('mountpoint')
                desired_dict["bename"] = self.be_name
                desired_dict["bemount"] = '/'
                break
        if self.arch == "sparc":
            desired_dict["phys_xml"] = PHYS_SPARC_XML
        else:
            desired_dict["phys_xml"] = PHYS_X86_XML
        # Make sure the active BE was found before proceeding with the test
        try:
            desired_dict["bemount"]
        except KeyError:
            raise RuntimeError("Couldn't find active BE to use in unit test")
        boot_mods_dom = etree.fromstring(BOOT_MODS_XML)
        self.doc.import_from_manifest_xml(boot_mods_dom, volatile=True)
        target_desired_dom = etree.fromstring(DYNAMIC_DESIRED_XML \
                                              % desired_dict)
        self.doc.import_from_manifest_xml(target_desired_dom, volatile=True)

        # logical BE:from_xml() method ignores the mountpoint property in the
        # XML so manually override its None value.
        boot_env = self.doc.volatile.get_descendants(class_type=BE)[0]
        boot_env.mountpoint = '/'
        self.boot_menu = SystemBootMenu("Test SystemBootMenu Checkpoint")
        # Force the arch in SystemBootMenu to match self.arch in case we
        # are trying to override it.
        self.boot_menu.arch = self.arch

    def test_parse_doc_target(self):
        """ Tests parsing of Target.Desired in the Data Object Cache
        """
        for arch in ['sparc', 'i386']:
            self.tearDown()
            self.arch = arch
            self.setUp()

            # Invoke target parsing method and verify it matches
            # expected values
            self.boot_menu._parse_doc_target(dry_run=True)
            boot_targets = self.boot_menu.boot_target

            # Check that the vtoc slice object was identified as a boot device
            # Slice should be slice 0 belonging to disk c600d600
            # ie. c600d700s0

            boot_slice = boot_targets[DEVS][0]
            self.failUnlessEqual(boot_slice, 'c600d600s0',
                "%s target boot device slice object doesn't match "\
                "manifest entry:\n" \
                "(Manifest slice device: c600d600s0, SystemBootMenu slice " \
                "slice device: %s)\n" % (arch, boot_slice))

            # UEFI Further checks for gpt_partitions should be included here.

            # Check the BE sub element of the logical node of target too
            boot_env = boot_targets[BOOT_ENV]
            self.failUnlessEqual(boot_env.name, self.be_name,
                "Target boot environment object doesn't match " \
                "manifest entry:\n" \
                "(Manifest boot environment: \'foobar\', "
                "SystemBootMenu boot " \
                "environment: %s)\n" % (boot_env.name))

    def test_get_progress_estimate(self):
        """ Tests return value of the boot checkpoint's
            get_progress_estimate() method
        """
        estimate = self.boot_menu.get_progress_estimate()
        self.failUnlessEqual(estimate, 5,
            "BootMenu:get_progress_estimate() returned unexpected " \
            "estimate:\n(Expected estimate: \'5\', Actual estimate '%d'\n" \
            % (estimate))

    def test_build_custom_entries(self):
        """ Unit tests custom boot menu entry creation from manifest XML
        """
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        self.boot_menu.build_custom_entries()

    def test_build_default_entries(self):
        """ Unit tests default boot menu entry creation (autogenerated)
        """
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        # Force method to construct a boot title
        self.boot_menu.boot_title = None
        self.boot_menu.build_default_entries()

    def test_install_boot_loader(self):
        """ Unit tests boot loader installation method
        """
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        self.boot_menu.build_default_entries()
        self.boot_menu.install_boot_loader(dry_run=True)

    def test_copy_sparc_bootlst(self):
        """ Unit tests copying of the SPARC bootlst binary.
            Can only be partially tested on X86.
        """
        if self.arch == 'sparc':
            self.boot_menu._parse_doc()
            self.boot_menu._copy_sparc_bootlst(dry_run=True)

    def test_create_sparc_boot_menu(self):
        """ Test creation of the SPARC menu.lst file
        """
        self.tearDown()
        self.arch = 'sparc'
        self.setUp()
        self.boot_menu._parse_doc_target()
        self.boot_menu._create_sparc_boot_menu(dry_run=True)
        self.tearDown()

    def test_install_sparc_bootblk(self):
        """ Test installation of the SPARC bootblk binary via installboot(1M)
        """
        # Make sure the method thinks it's runnning on SPARC
        self.tearDown()
        self.arch = 'sparc'
        self.setUp()
        self.boot_menu._parse_doc_target()
        self.boot_menu._install_sparc_bootblk(dry_run=True)
        # Make sure it raises a RuntimeError on X86
        self.boot_menu.arch = 'i386'
        self.assertRaises(RuntimeError,
                          self.boot_menu._install_sparc_bootblk,
                          dry_run=True)

    def test_set_sparc_prom_boot_device(self):
        """ Tests setting of the prom boot-device variable on SPARC
            This test is limited because reading from /dev/openprom
            requires root priviliges which causes a non-fatal exception
            in the called method.
        """
        # Make sure the method thinks it's runnning on SPARC
        self.tearDown()
        self.arch = 'sparc'
        self.setUp()
        self.boot_menu._parse_doc_target()
        self.boot_menu._set_sparc_prom_boot_device(dry_run=True)

    def test_execute(self):
        """ Test that runs the entire checkpoint as an install application
            would. Essentially an aggregation of the above tests.
        """
        self.boot_menu.execute(dry_run=True)


class ISOBootMenuTestCase(BootMenuTestCaseBase):
    """ Abstract unit test base class for ISO image derived classes such as
        AI, Text and LiveCD ISO BootMenu classes.
        Doesn't directly perform any unit tests
    """
    __metaclass__ = abc.ABCMeta

    def setUp(self):
        """ Initialises a runtime environment for execution of
            ISOImageBootMenu subclassed unit tests. Currently needs
            an X86 legacy GRUB environment.
        """
        super(ISOBootMenuTestCase, self).setUp()
        temp_dir = tempfile.mkdtemp(dir=TMP_TEST_DIR,
                                    prefix="install_boot_test_")
        rel_file_dir = os.path.join(temp_dir, "etc")
        os.makedirs(rel_file_dir)
        rel_file = os.path.join(rel_file_dir, 'release')
        with open(rel_file, 'w') as file_handle:
            file_handle.write('Solaris Boot Test')
        doc_dict = {"pkg_img_path": temp_dir}
        self.temp_dir = temp_dir
        self.doc.volatile.insert_children(DataObjectDict("DC specific",
                                          doc_dict,
                                          generate_xml=True))
        # Create a dummy boot and grub menu.ls environment
        # so that pybootmgmt can instantiate a legacyGrub
        # boot loader under the bootconfig object
        # UEFI - this needs updating for SPARC, GRUB2 & UEFI
        # when support gets added to pybootmgmt
        if platform.processor() == 'i386':
            os.makedirs(os.path.join(temp_dir, 'boot/grub'))
            copyfile('/boot/grub/menu.lst',
                     os.path.join(temp_dir, 'boot/grub/menu.lst'))
            copyfile('/boot/grub/stage2_eltorito',
                     os.path.join(temp_dir, 'boot/grub/stage2_eltorito'))
            os.makedirs(os.path.join(temp_dir, 'boot/solaris'))
            copyfile('/boot/solaris/bootenv.rc',
                     os.path.join(temp_dir, 'boot/solaris/bootenv.rc'))

    def tearDown(self):
        """ Cleans up after each unit test is executed
        """
        super(ISOBootMenuTestCase, self).tearDown()
        rmtree(self.temp_dir)

    def _test_build_custom_entries(self):
        """ Implements a custom boot menu entry listtest for derived classes
        """
        boot_mods_dom = etree.fromstring(BOOT_MODS_XML)
        self.doc.import_from_manifest_xml(boot_mods_dom, volatile=True)
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        self.boot_menu.build_default_entries()
        self.boot_menu.build_custom_entries()
        config = self.boot_menu.config

        sorted_entry_list = []
        for entry in self.boot_menu.boot_entry_list:
            if entry.insert_at == "start":
                sorted_entry_list.insert(0, entry)
            else:
                sorted_entry_list.append(entry)

        # Map manifest defined custom entries to their expected positions in
        # the bootConfig objects boot_instances list and compare.
        num_entries = len(config.boot_instances)
        j = 0
        for i in [0, num_entries - 2, num_entries - 1]:
            full_title = self.boot_menu.boot_title + \
                        " " + \
                        sorted_entry_list[j].title_suffix
            self.failUnlessEqual(full_title, config.boot_instances[i].title,
                "Resulting BootConfig doesn't match manifest.\n\
                Mismatched boot entry titles at entry: %d\n\
                BootConfig Title: %s\n\
                Manifest Title: %s\n"\
                % (i, config.boot_instances[i].title, full_title))
            j += 1

    def _test_build_default_entries(self, titles, kargs, chainloader=True):
        """ Implements a default menu entry unit test for sub-classes
        """
        # How many boot entries the TextCD ISO defines by default. Needs to
        # be adjusted along with expected entry contents if the defaults
        # change.
        exp_len = len(titles)
        if chainloader:
            exp_len += 1
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        self.boot_menu.build_default_entries()

        instances = self.boot_menu.config.boot_instances
        self.assertEqual(len(titles), len(kargs),
            "Arguments mismatch. titles and kargs arguments must be the " \
            "same length")
        self.assertEqual(len(instances), exp_len,
            "Unexpected number of boot entries in default menu:"
            "\n\tACTUAL: %d\tExpected: %d" % (len(instances), exp_len))

        # Only one element for now, but making it a list makes it easier to
        # expand later, even if it looks silly.
        self.boot_title = self.boot_menu.boot_title

        for i, exp_title in enumerate(titles):
            actual_title = self.boot_menu.config.boot_instances[i].title
            self.assertEqual(actual_title,
                             exp_title,
                             "Unexpected boot entry title at index %d:" \
                             "\nACTUAL:\t%s\nEXPECTED:\t%s" \
                             % (i, actual_title, exp_title))
            actual_kargs = self.boot_menu.config.boot_instances[i].kargs
            exp_kargs = kargs[i]
            self.assertEqual(actual_kargs,
                             exp_kargs,
                             "Unexpected boot entry kernel args at index %d:" \
                             "\nACTUAL:\t%s\nEXPECTED:\t%s" \
                             % (i, actual_kargs, exp_kargs))
        # Finally, check the chainloader entry
        if chainloader:
            i += 1
            actual_title = self.boot_menu.config.boot_instances[i].title
            exp_title = "Boot from Hard Disk"
            self.assertEqual(actual_title,
                             exp_title,
                             "Unexpected chainloader title at index %d:" \
                             "\nACTUAL:\t%s\nEXPECTED:\t%s" \
                             % (i, actual_title, exp_title))
            actual_cinfo = self.boot_menu.config.boot_instances[i].chaininfo
            exp_cinfo = (0, 0)
            self.assertEqual(actual_cinfo,
                             exp_cinfo,
                             "Unexpected chainloader chaininfo at index %d:" \
                             "\nACTUAL:\t%s\nEXPECTED:\t%s" \
                             % (i, str(actual_cinfo), str(exp_cinfo)))

    def _test_install_boot_loader(self):
        """ Implements a boot loader installation unit test for sub-classes
        """
        boot_mods_dom = etree.fromstring(BOOT_MODS_XML)
        self.doc.import_from_manifest_xml(boot_mods_dom, volatile=True)
        self.boot_menu.parse_doc()
        self.boot_menu.init_boot_config()
        self.boot_menu.build_default_entries()
        self.boot_menu.build_custom_entries()
        self.boot_menu.install_boot_loader(dry_run=True)

    def _test_handle_boot_config_list(self):
        """ Implemnts a unit test to validate that returned boot config data
            from bootmgmt is handled correctly. Used by sub-classes
            Checks file and bios eltorito boot images for now.
        """
        self.boot_menu.parse_doc()
        self.boot_menu.boot_tokens[BootConfig.TOKEN_SYSTEMROOT] = self.temp_dir
        dst_file = "%(" + BootConfig.TOKEN_SYSTEMROOT + ")s" + "/dst-file"
        dst_blt = "%(" + BootConfig.TOKEN_SYSTEMROOT + ")s" + \
                  "/dst-bios-eltorito-img"

        # Assign matching user and group names so file ownership can be
        # processed.
        user = pwd.getpwuid(os.getuid())[0]
        group = grp.getgrgid(os.getgid())[0]

        # Test standard file handle type first
        src_dir = tempfile.mkdtemp(dir=TMP_TEST_DIR, prefix="boot_config_src_")
        src_file = os.path.join(src_dir, "src-file")
        with open(src_file, 'w') as file_handle:
            file_handle.write("Rhubarb")
        boot_files = [[(BootConfig.OUTPUT_TYPE_FILE,
                       src_file, None,
                       dst_file,
                       user,
                       group,
                       420)]]
        self.boot_menu._handle_boot_config_list(boot_files, dry_run=False)
        os.unlink(os.path.join(self.temp_dir, "dst-file"))

        # Test BIOS eltorito image type. mkisofs(1M) requires that the
        # eltorito image file be underneath the top level folder of the
        # ISO filesystem tree.
        src_blt = os.path.join(self.temp_dir, "src-bios-eltorito-img")
        with open(src_blt, 'w') as file_handle:
            file_handle.write("BLT")
        boot_files = [[(BootConfig.OUTPUT_TYPE_BIOS_ELTORITO,
                       src_blt, None,
                       dst_blt,
                       user,
                       group,
                       420)]]
        self.boot_menu._handle_boot_config_list(boot_files, dry_run=False)
        os.unlink(src_blt)

        # Test BIOS eltorito image type with a bad src directory
        bad_blt_dir = tempfile.mkdtemp(dir=TMP_TEST_DIR, prefix="bad_blt_")
        src_blt = os.path.join(bad_blt_dir, "src-bios-eltorito-img")
        with open(src_blt, 'w') as file_handle:
            file_handle.write("BLT")
        boot_blt = [[(BootConfig.OUTPUT_TYPE_BIOS_ELTORITO,
                     src_blt, None,
                     dst_blt,
                     user,
                     group,
                     420)]]
        self.assertRaises(RuntimeError,
                          self.boot_menu._handle_boot_config_list,
                          boot_config_list=boot_blt, dry_run=False)
        # Test with an invalid file type.
        boot_unsup = [[("DEADBEEF",
                     src_blt, None,
                     dst_blt,
                     user,
                     group,
                     420)]]
        self.assertRaises(RuntimeError,
                          self.boot_menu._handle_boot_config_list,
                          boot_config_list=boot_unsup, dry_run=False)
        os.unlink(src_blt)
        rmtree(bad_blt_dir)
        rmtree(src_dir)


class AIISOBootMenuTestCase(ISOBootMenuTestCase):
    """ Unit test class for AIIsoBootMenu class
    """

    def test_build_custom_entries(self):
        self.boot_menu = AIISOImageBootMenu("Test AI Boot Checkpoint")
        self._test_build_custom_entries()

    def test_update_img_info_path(self):
        self.boot_menu = AIISOImageBootMenu("Test AI Boot Checkpoint")
        boot_mods_dom = etree.fromstring(BOOT_MODS_XML)
        self.doc.import_from_manifest_xml(boot_mods_dom, volatile=True)
        self.boot_menu.parse_doc()
        self.boot_menu.img_info_path = tempfile.mktemp(dir=TMP_TEST_DIR,
                                                        prefix="img_info_")
        self.boot_menu.update_img_info_path()
        os.unlink(self.boot_menu.img_info_path)

    def test_install_boot_loader(self):
        self.boot_menu = AIISOImageBootMenu("Test AIISOBootMenu Checkpoint")
        self._test_install_boot_loader()

    def test_handle_boot_config_list(self):
        self.boot_menu = AIISOImageBootMenu("Test AIISOBootMenu Checkpoint")
        self._test_handle_boot_config_list()

    def test_build_default_entries(self):
        """ Default menu entry unit test for AI ISO
        """
        self.boot_menu = AIISOImageBootMenu("Test AIISOBootMenu Checkpoint")
        self.boot_menu.parse_doc()

        # This assignment permits convenient copy and paste from the
        # AIISOImageBootMenu checkpoint codes ai_titles and ai_kargs values
        self.boot_title = self.boot_menu.boot_title
        ai_titles = [self.boot_title + " Automated Install custom",
                     self.boot_title + " Automated Install",
                     self.boot_title + " Automated Install custom ttya",
                     self.boot_title + " Automated Install custom ttyb",
                     self.boot_title + " Automated Install ttya",
                     self.boot_title + " Automated Install ttyb"]
        ai_kargs = ["-B aimanifest=prompt",
                    None,
                    "-B install=true,aimanifest=prompt,console=ttya",
                    "-B install=true,aimanifest=prompt,console=ttyb",
                    "-B install=true,console=ttya",
                    "-B install=true,console=ttyb"]

        self._test_build_default_entries(ai_titles, ai_kargs)


class LiveCDISOBootMenuTestCase(ISOBootMenuTestCase):

    def test_install_boot_loader(self):
        self.boot_menu = LiveCDISOImageBootMenu("Test LiveCD Boot Checkpoint")
        self.boot_menu.execute(dry_run=True)

    def test_build_default_entries(self):
        """ Default menu entry unit test for LiveCD ISO
        """
        self.boot_menu = LiveCDISOImageBootMenu("Test LiveCD Boot Checkpoint")
        self.boot_menu.parse_doc()

        # This assignment permits convenient copy and paste from the
        # LiveCDISOImageBootMenu checkpoint codes ai_titles and ai_kargs values
        self.boot_title = self.boot_menu.boot_title
        lcd_titles = [self.boot_title,
                      self.boot_title + " VESA driver",
                      self.boot_title + " text console"]
        lcd_kargs = [None,
                     "-B livemode=vesa",
                     "-B livemode=text"]
        self._test_build_default_entries(lcd_titles, lcd_kargs)


class TextISOBootMenuTestCase(ISOBootMenuTestCase):
    def test_build_default_entries(self):
        """ Default menu entry unit test for Text ISO
        """
        # How many boot entries the TextCD ISO defines by default. Needs to
        # be adjusted along with expected entry contents if the defaults
        # change.
        self.boot_menu = TextISOImageBootMenu("Test Text Boot Checkpoint")
        self.boot_menu.parse_doc()

        titles = [self.boot_menu.boot_title]
        kargs = [None]
        self._test_build_default_entries(titles, kargs)

if __name__ == '__main__':
    unittest.main()

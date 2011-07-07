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
'''
   test_gen_sc_profile
   Test program for testing GenerateSCProfile
'''

import os
import shutil
import tempfile
import unittest

from common_create_simple_doc import CreateSimpleDataObjectCache
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.ict import SC_TEMPLATE
from solaris_install.ict.generate_sc_profile import GenerateSCProfile
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestGenerateSCProfile(unittest.TestCase):
    '''test the functionality for GenerateSCProfile Class'''

    def setUp(self):

        # Set up the Target directory
        self.test_target = tempfile.mkdtemp(dir="/tmp",
                                            prefix="ict_test_")
        os.chmod(self.test_target, 0777)

        self.sc_test_template = ['<!DOCTYPE service_bundle SYSTEM  \
                      "/usr/share/lib/xml/dtd/service_bundle.dts.1">',
                           ' ',
                           '<!--',
                           'Parameter: keyboard layout',
                           'SMF service: svc:/system/keymap:default',
                           'SMF property: keymap/layout',
                           '-->',
                           '<service_bundle type="profile" \
                             name="sc_install_interactive">',
                           '    <service name="system/keymap" version="1"\
                                 type="system">',
                           '        <instance name="default">',
                           '            <property_group name="keymap" \
                                         type="system">',
                           '                <propval name="layout" \
                                             type="astring" \
                                             value="US-English" />',
                           '            </property_group>',
                           '        </instance>',
                           '    </service>',
                           '</service_bundle>']

        self.sc_test_template_it = ['<!DOCTYPE service_bundle SYSTEM  \
                      "/usr/share/lib/xml/dtd/service_bundle.dts.1">',
                           ' ',
                           '<!--',
                           'Parameter: keyboard layout',
                           'SMF service: svc:/system/keymap:default',
                           'SMF property: keymap/layout',
                           '-->',
                           '<service_bundle type="profile" \
                             name="sc_install_interactive">',
                           '    <service name="system/keymap" version="1"\
                                 type="system">',
                           '        <instance name="default">',
                           '            <property_group name="keymap" \
                                         type="system">',
                           '                <propval name="layout" \
                                             type="astring" \
                                             value="Italian" />',
                           '            </property_group>',
                           '        </instance>',
                           '    </service>',
                           '</service_bundle>']

        # Create a data object to hold the required data
        self.simple = CreateSimpleDataObjectCache(test_target=self.test_target)
        self.sc_dict = {}

    def tearDown(self):
        reset_engine()
        self.simple.doc = None

        if os.path.exists(self.test_target):
            shutil.rmtree(self.test_target)
        self.sc_dict = {}

    def test_sc_profile_config_default(self):
        '''Test the default parameters of GenerateSCProfile'''

        # Create the test source directory
        test_source = os.path.join(self.test_target,
                                  'usr/share/install/sc_template.xml')
        if not os.path.exists(os.path.dirname(test_source)):
            os.makedirs(os.path.dirname(test_source))

        # Create the test sc_template.xml file
        sc_tmp_string = ''
        for sc_tmplt in self.sc_test_template:
            sc_tmp_string += sc_tmplt + '\n'
        with open(test_source, "w") as fh:
            fh.writelines(sc_tmp_string)
        fh.close()

        # Instantiate the checkpoint
        gen_sc = GenerateSCProfile("generate_sc_profile")

        try:
            gen_sc.execute()
        except Exception as e:
            self.fail(str(e))

    def test_sc_profile_config_dif(self):
        '''Test different kb parameters of GenerateSCProfile'''

        # Create the test source directory
        test_source = os.path.join(self.test_target,
                                  'usr/share/install/sc_template.xml')
        if not os.path.exists(os.path.dirname(test_source)):
            os.makedirs(os.path.dirname(test_source))

        # Create the test sc_template.xml file
        sc_tmp_string = ''
        for sc_tmplt in self.sc_test_template_it:
            sc_tmp_string += sc_tmplt + '\n'
        with open(test_source, "w") as fh:
            fh.writelines(sc_tmp_string)
        fh.close()

        # Instantiate the checkpoint
        gen_sc = GenerateSCProfile("generate_sc_profile")

        try:
            gen_sc.execute()
        except Exception as e:
            self.fail(str(e))

    def test_sc_profile_different_dest(self):
        '''Test different sc_profile destination succeeds'''

        self.sc_dict[SC_TEMPLATE] = 'test_dir/my_sc_template.xml'

        sc_dod = DataObjectDict("generate_sc_profile", self.sc_dict,
                                generate_xml=True)
        self.simple.doc.persistent.insert_children([sc_dod])

        # Create the test source directory
        test_source = os.path.join(self.test_target,
                                  'usr/share/install/sc_template.xml')
        if not os.path.exists(os.path.dirname(test_source)):
            os.makedirs(os.path.dirname(test_source))

        # Create the test sc_template.xml file
        sc_tmp_string = ''
        for sc_tmplt in self.sc_test_template:
            sc_tmp_string += sc_tmplt + '\n'
        with open(test_source, "w") as fh:
            fh.writelines(sc_tmp_string)
        fh.close()

        # Instantiate the checkpoint
        gen_sc = GenerateSCProfile("generate_sc_profile")

        try:
            gen_sc.execute()
        except Exception as e:
            self.fail(str(e))

    def test_more_than_one_profile_node(self):
        '''Test having multiple configurations fails'''
        sc_dict2 = {}

        sc_dict2[SC_TEMPLATE] = 'test_dir/my_sc_template.xml'
        sc_dod = DataObjectDict("generate_sc_profile", sc_dict2,
                                generate_xml=True)
        self.simple.doc.persistent.insert_children([sc_dod])

        self.sc_dict[SC_TEMPLATE] = 'test_dir/my_sc_template.xml'
        sc_dod_2 = DataObjectDict("generate_sc_profile", self.sc_dict,
                                  generate_xml=True)
        self.simple.doc.persistent.insert_children([sc_dod_2])

        # Instantiate the checkpoint
        gen_sc = GenerateSCProfile("generate_sc_profile")
        self.assertRaises(ValueError, gen_sc.execute, dry_run=True)

    def test_gen_sc_profile_dry(self):
        '''Test GenerateSCProfile dry run'''

        gen_sc = GenerateSCProfile("generate_sc_profile")
        # Call the execute command for the checkpoint
        # with dry_run set to true.
        try:
            gen_sc.execute(dry_run=True)
        except Exception as e:
            self.fail(str(e))

    def test_gen_sc_profile_src_dest(self):
        '''Test passing in a source and a destination'''
        alt_source = 'usr/share/install/sc2_template.xml'
        test_source = os.path.join(self.test_target, alt_source)
        if not os.path.exists(os.path.dirname(test_source)):
            os.makedirs(os.path.dirname(test_source))

        # Create the test sc_template.xml file
        sc_tmp_string = ''
        for sc_tmplt in self.sc_test_template:
            sc_tmp_string += sc_tmplt + '\n'
        with open(test_source, "w") as fh:
            fh.writelines(sc_tmp_string)
        fh.close()

        self.sc_dict[alt_source] = 'test_dir/my_sc_template.xml'
        sc_dod = DataObjectDict("generate_sc_profile", self.sc_dict,
                                generate_xml=True)
        self.simple.doc.persistent.insert_children([sc_dod])

        gen_sc = GenerateSCProfile("generate_sc_profile")
        try:
            gen_sc.execute()
        except Exception as e:
            self.fail(str(e))

    def test_gen_sc_profile_default_src(self):
        '''Use the default source and a user defined destination'''

        # Create the test source directory
        test_source = os.path.join(self.test_target, SC_TEMPLATE)
        if not os.path.exists(os.path.dirname(test_source)):
            os.makedirs(os.path.dirname(test_source))

        # Create the test sc_template.xml file
        sc_tmp_string = ''
        for sc_tmplt in self.sc_test_template:
            sc_tmp_string += sc_tmplt + '\n'
        with open(test_source, "w") as fh:
            fh.writelines(sc_tmp_string)
        fh.close()

        self.sc_dict[SC_TEMPLATE] = 'test_dir/mysc_template.xml'
        sc_dod = DataObjectDict("generate_sc_profile", self.sc_dict,
                                generate_xml=True)
        self.simple.doc.persistent.insert_children([sc_dod])

        gen_sc = GenerateSCProfile("generate_sc_profile")
        try:
            gen_sc.execute()
        except Exception as e:
            self.fail(str(e))

    def test_get_progress_estimate(self):
        '''Test get progress estimate return value'''

        gen_sc = GenerateSCProfile("generate_sc_profile")
        # Check the return value for the progress estimate
        self.assertEquals(gen_sc.get_progress_estimate(), 1)

if __name__ == '__main__':
    unittest.main()

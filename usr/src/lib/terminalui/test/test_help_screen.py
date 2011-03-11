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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''


import os
import shutil
import tempfile
import unittest

import terminalui
from terminalui.help_screen import HelpScreen


terminalui.init_logging("test")


HELP_FILE_CONTENTS = '''Test line 1
Test line 2
'''


class MockAll(object):
    '''Generic Mock object that 'never' raises an AttributeError'''
    
    def __getattr__(self, name):
        return self
    
    def __call__(self, *args, **kwargs):
        return self


class TestHelpScreen(unittest.TestCase):
    
    def setUp(self):
        self.HelpScreen__init__ = HelpScreen.__init__
        HelpScreen.__init__ = lambda x, y: None
        self.help = HelpScreen(None)
        self.help.locale = "C"
        self.temp_dir = None
    
    def tearDown(self):
        HelpScreen.__init__ = self.HelpScreen__init__
        self.help = None
        if self.temp_dir:
            shutil.rmtree(self.temp_dir)
    
    def test_setup_help_data_normal(self):
        '''HelpScreen.setup_help_data() correctly generates help_dict
           and help_info for screens with help_data'''
        screen = MockAll()
        screen.instance = ".test"
        screen.help_data = ("help data", "tuple")
        screen.help_format = "%s"
        
        self.help.setup_help_data([screen])
        self.assertEquals(screen.help_data,
                          self.help.help_dict["MockAll.test"])
        self.assertEquals(("MockAll.test", " %s"), self.help.help_info[0])
    
    def test_setup_help_data_no_data(self):
        '''HelpScreen.setup_help_data() generates empty help_dict/help_info
           for screens with no help_data'''
        screen = MockAll()
        screen.instance = ".test"
        screen.help_data = (None, None)
        screen.help_format = "%s"
        
        self.help.setup_help_data([screen])
        self.assertFalse(self.help.help_dict,
                         "HelpScreen.help_dict should be empty")
        self.assertFalse(self.help.help_info,
                         "HelpScreen.help_info should be empty")
    
    def test_get_locids_locale_has_encoding(self):
        '''HelpScreen._get_locids() includes correct possibilities
           if the current locale has an encoding.
           This includes: The current locale, the locale (without encoding),
           and the default ("C") locale.
        
        '''
        self.help.locale = "ab_CD.EFG-1"
        locids = self.help._get_locids()
        self.assertEquals(["ab_CD.EFG-1", "ab_CD", "ab", "C"], locids)
    
    def test_get_locids_locale_has_dialect(self):
        '''HelpScreen._get_locids() includes correct possibilities if current
           locales has dialect.
           This includes: The current locale, the language (locale without
           dialect), and the default ("C") locale.
        
        '''
        self.help.locale = "ab_CD"
        locids = self.help._get_locids()
        self.assertEquals(["ab_CD", "ab", "C"], locids)
    
    def test_get_help_text_file_exists(self):
        '''HelpScreen.get_help_text() loads help text from existent file'''
        temp_dir = tempfile.mkdtemp()
        self.temp_dir = temp_dir # tearDown will clean up self.temp_dir
        os.makedirs(os.path.join(temp_dir, "C"))
        filename = os.path.join(temp_dir, "%s", "help.txt")
        temp_file = filename % "C"
        with open(temp_file, "w") as help_file:
            help_file.write(HELP_FILE_CONTENTS)
        
        help_text = self.help.get_help_text(filename=filename)
        self.assertEquals(HELP_FILE_CONTENTS, help_text)
    
    def test_get_help_text_file_does_not_exist(self):
        '''HelpScreen.get_help_text() falls back gracefully when
           no help text file is found'''
        badfile = os.tempnam() + "/%s/help.txt"
        help_text = self.help.get_help_text(filename=badfile)
        self.assertEquals("Help for this screen is not available", help_text)

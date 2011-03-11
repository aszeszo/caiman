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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests:

1) nightly -n developer.sh # build the gate
2) export PYTHONPATH=${WS}/proto/root_i386/usr/snadm/lib:${WS}/proto/root_i386/usr/lib/python2.6/vendor-packages
3) pfexec python2.6 test_disk_select.py

A single test may be run by specifying the test as an argument to step 3, e.g.:
pfexec python2.6 test_disk_select.py OnActivateTest.test_on_activate_default

Since the proto area is used for the PYTHONPATH, the gate must be rebuilt for
these tests to pick up any changes in the tested code.

'''

import numbers
import unittest

import osol_install.text_install.disk_selection as disk_selection
from osol_install.profile.disk_info import DiskInfo
import terminalui
from terminalui.base_screen import BaseScreen


terminalui.init_logging("test")
BaseScreen.set_default_quit_text("test", "test", "test", "test")

class MockCenterWin(object):
    '''Mocks an InnerWindow as used by a MainWindow'''
    
    def add_paragraph(self, *args, **kwargs):
        pass

class MockDiskInfo(object):
    '''Mocks a DiskInfo object'''
    do_copy = False
    label = []
    was_blank = False
    use_whole_segment = False
    
    def create_default_layout(self):
        pass

class MockDiskDetail(object):
    '''Mocks a DiskWindow object'''
    
    def set_disk_info(self, *args):
        pass

class MockDiskScreen(object):
    '''Mocks the DiskScreen'''
    win_size_x = 0
    proposed_text = ""
    found_text = ""

class MockInstallProfile(object):
    '''Mocks an InstallProfile'''
    
    disk = None
    original_disk = None

class MockAll(object):
    '''Generic Mock object that 'never' raises an AttributeError'''
    
    def __getattr__(self, name):
        return self
    
    def __call__(self, *args, **kwargs):
        return None

class OnActivateTest(unittest.TestCase):
    '''Test disk_selection.on_activate'''
    
    def setUp(self):
        self.screen = MockDiskScreen()
        self.disk = MockDiskInfo()
        self.screen.center_win = MockCenterWin()
        self.screen.disk_detail = MockDiskDetail()
    
    def tearDown(self):
        self.screen = None
        self.disk = None
    
    def test_on_activate_default(self):
        '''Ensure that do_copy flag is set after calls to on_activate'''
        disk_selection.on_activate(disk_info=self.disk,
                                   disk_select=self.screen)
        self.assertFalse(self.disk.use_whole_segment)
        self.assertTrue(self.screen.do_copy)
    
    def test_on_activate_GPT(self):
        '''Ensure use_whole_segment is set if the disk was GPT labeled'''
        
        self.disk.label = [DiskInfo.GPT]
        
        disk_selection.on_activate(disk_info=self.disk,
                                   disk_select=self.screen)
        self.assertTrue(self.disk.use_whole_segment)
    
    def test_on_activate_was_blank(self):
        '''Ensure use_whole_segment is set when the disk was initially blank'''
        self.disk.was_blank = True
        
        disk_selection.on_activate(disk_info=self.disk,
                                   disk_select=self.screen)
        self.assertTrue(self.disk.use_whole_segment)


class DiskSelectTest(unittest.TestCase):
    '''Test the DiskScreen'''
    
    def setUp(self):
        self.screen = disk_selection.DiskScreen(MockAll())
        self.screen.disk_win = MockAll()
    
    def test_on_change_screen_disk_detail_none(self):
        '''Ensure selected_disk is set properly by on_change_screen'''
        self.screen.disk_detail = None
        obj = object()
        self.screen.selected_disk = obj
        
        self.screen.on_change_screen()
        self.assertTrue(self.screen.selected_disk is obj)
    
    def test_on_change_screen_do_copy(self):
        '''Ensure disk is copied when do_copy flag is set'''
        self.screen.install_profile = MockInstallProfile()
        self.screen.install_profile.disk = True
        
        obj = object()
        self.screen.disk_win.active_object = obj
        self.screen.selected_disk = None
        
        disk = MockDiskInfo()
        self.screen.disk_detail = MockAll()
        self.screen.disk_detail.disk_info = disk
        self.screen.do_copy = True
        
        self.screen.on_change_screen()
        
        self.assertTrue(self.screen.selected_disk is obj)
        self.assertTrue(self.screen.install_profile.original_disk is disk)
    
    def test_on_change_screen_disk_is_none(self):
        '''Check DiskScreen.on_change_screen when disk is None'''
        self.screen.install_profile = MockInstallProfile()
        
        disk = MockDiskInfo()
        self.screen.disk_detail = MockAll()
        self.screen.disk_detail.disk_info = disk
        
        self.screen.on_change_screen()
        
        self.assertTrue(self.screen.install_profile.original_disk is disk)
    
    def test_size_line(self):
        '''Ensure that DiskScreen._size_line is created and is a string after
        calling get_size_line. Also verify that subsequent calls do not modify
        the _size_line
        
        '''
        self.assertTrue(self.screen._size_line is None)
        self.screen.get_size_line()
        self.assertTrue(isinstance(self.screen._size_line, basestring))
        
        obj = object()
        self.screen._size_line = obj
        self.screen.get_size_line()
        self.assertTrue(obj is self.screen._size_line)
    
    def test_determine_size_data(self):
        '''Ensure that recommended_size and minimum_size are accessible after
        a call to determine_size_data(), and that they are numbers'''
        
        self.assertTrue(self.screen._recommended_size is None)
        self.assertTrue(self.screen._minimum_size is None)
        self.screen.determine_size_data()
        self.assertTrue(isinstance(self.screen.minimum_size, numbers.Real))
        self.assertTrue(isinstance(self.screen.recommended_size, numbers.Real))


if __name__ == '__main__':
    unittest.main()

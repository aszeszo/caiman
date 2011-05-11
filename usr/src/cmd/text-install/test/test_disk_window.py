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
2) export PYTHONPATH=${WS}/proto/root_i386/usr/snadm/lib:\
${WS}/proto/root_i386/usr/lib/python2.6/vendor-packages
3) python2.6 test_disk_window.py

A single test may be run by specifying the test as an argument to step 3:
python2.6 test_disk_window.py UpdateEditField.test_part_info_not_editable

Since the proto area is used for the PYTHONPATH, the gate must be rebuilt for
these tests to pick up any changes in the tested code.

'''

import unittest

from solaris_install.target.physical import Disk
from solaris_install.text_install.disk_window import DiskWindow
import terminalui
from terminalui.color_theme import ColorTheme
from terminalui.window_area import WindowArea
from terminalui.inner_window import InnerWindow


terminalui.init_logging("test")


class MockAll(object):
    '''Generic Mock object that 'never' raises an AttributeError'''
    
    def __getattr__(self, name):
        return self
    
    def __call__(self, *args, **kwargs):
        return self


class MockInnerWin(object):
    '''Class for mock inner win'''
    def __init__(self):
        self.active_object = None
        self.objects = []
        self.text = None
        self.scrollable_lines = 10

    def activate_object(self):
        '''Set active_object to 0'''
        self.active_object = 0

    def get_active_object(self):
        '''Get active_object'''
        if self.active_object is not None:
            return self.objects[self.active_object]
        else:
            return None

    def add_text(self, text=None, y_loc=0, x_loc=0):
        '''Append passed in text to self.text'''
        if self.text is None:
            self.text = str(y_loc) + text
        else:
            self.text = self.text + str(y_loc) + text

    def get_text(self):
        '''Get the current value of self.text'''
        return self.text


class MockPartInfo(object):
    '''Class for mock part info field'''
    def __init__(self):
        self.is_editable = True

    def set_editable(self, editable=True):
        '''Set editable property'''
        self.is_editable = editable

    def editable(self):
        ''' get editable setting'''
        return self.is_editable


class MockEditField(object):
    '''Class for mock edit field'''
    def __init__(self):
        self.active = False

    def make_inactive(self, inactive=True):
        ''' Set active property'''
        self.active = not inactive


class MockPartField(object):
    '''Class for mock part field'''
    def __init__(self):
        self.edit_field = None
        self.active_object = None
        self.objects = []

    def activate_object(self, tobject):
        '''activate object'''
        self.active_object = 0
        self.edit_field = tobject
        self.edit_field.make_inactive(False)

    def get_active_object(self):
        '''Get active_object'''
        if self.active_object is not None:
            return self.objects[self.active_object]
        else:
            return None


def do_nothing(*args, **kwargs):
    '''does nothing'''
    pass


class TestDiskWindow(unittest.TestCase):
    '''Class to test DiskWindow'''
    
    def setUp(self):
        '''unit test set up
         Sets several functions to call do_nothing to allow
         test execution in non-curses environment. Original
         functions are saved so they can be later restored in
         tearDown.

        '''
        self.inner_window_init_win = InnerWindow._init_win
        self.disk_window_init_win = DiskWindow._init_win
        self.inner_window_set_color = InnerWindow.set_color
        InnerWindow._init_win = do_nothing
        InnerWindow.set_color = do_nothing
        DiskWindow._init_win = do_nothing
        self.disk_win = DiskWindow(WindowArea(70, 70, 0, 0), Disk("MockDisk"),
                                   color_theme=ColorTheme(force_bw=True),
                                   window=MockAll())
        self.edit_field = MockEditField()
        self.part_field = MockPartField()
        self.part_info = MockPartInfo()
        self.inner_win = MockInnerWin()
        self.disk_win.objects = []
        self.part_field.objects = []

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values. 
        '''
        InnerWindow._init_win = self.inner_window_init_win
        InnerWindow.set_color = self.inner_window_set_color
        DiskWindow._init_win = self.disk_window_init_win
        self.disk_win = None
        self.edit_field = None
        self.part_field = None
        self.part_info = None
        self.inner_win = None
    

class UpdateEditField(TestDiskWindow):
    '''Tests for _update_edit_field'''

    def test_part_info_not_editable(self):
        '''Ensure edit field updated correctly if part_info not editable'''
        self.part_info.set_editable(False)
        self.edit_field.make_inactive(False)
        self.part_field.activate_object(self.edit_field)
        self.part_field.objects.append(self.edit_field)
        
        self.disk_win._update_edit_field(self.part_info, self.part_field,
                                         self.edit_field)
        self.assertFalse(self.edit_field.active)
        self.assertEquals(len(self.part_field.objects), 0)
        self.assertTrue(self.part_field.active_object is None)

    def test_part_info_editable_no_active_win(self):
        '''Ensure edit field not updated if no active right/left win'''
        self.part_info.set_editable(True)
        self.edit_field.make_inactive(True)
        self.assertTrue(self.part_field.active_object is None)
        self.disk_win._update_edit_field(self.part_info, self.part_field,
                                         self.edit_field)
        self.assertTrue(self.part_field.active_object is None)
        self.assertFalse(self.edit_field.active)

    def test_part_info_editable_active_win_no_active_obj(self):
        '''Ensure edit field updated correctly if active obj not part_field'''
        self.part_info.set_editable(True)
        self.edit_field.make_inactive(True)
        self.disk_win.objects.append(self.inner_win)
        self.disk_win.active_object = 0
        my_part_field = MockPartField()
        self.inner_win.objects.append(my_part_field)
        self.inner_win.active_object = 0

        self.assertTrue(self.inner_win.get_active_object() is my_part_field)
        self.assertTrue(self.part_field.active_object is None)

        self.disk_win._update_edit_field(self.part_info, self.part_field,
                                         self.edit_field)
        self.assertTrue(self.part_field.active_object is None)
        self.assertFalse(self.edit_field.active)

    def test_part_info_editable_active_win(self):
        '''Ensure edit field updated correctly if part_info is editable'''
        self.part_info.set_editable(True)
        self.edit_field.make_inactive(True)
        self.disk_win.objects.append(self.inner_win)
        self.disk_win.active_object = 0
        self.inner_win.objects.append(self.part_field)
        self.inner_win.active_object = 0

        self.assertEquals(self.disk_win.active_object, 0)
        self.assertTrue(self.part_field.active_object is None)

        self.disk_win._update_edit_field(self.part_info, self.part_field,
                                         self.edit_field)
        self.assertEquals(self.part_field.active_object, 0)
        self.assertTrue(self.edit_field.active)
        

if __name__ == '__main__':
    unittest.main()

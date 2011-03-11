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


import unittest

import terminalui
from terminalui.color_theme import ColorTheme
from terminalui.inner_window import InnerWindow
from terminalui.window_area import WindowArea


terminalui.init_logging("test")


def do_nothing(*args, **kwargs):
    '''does nothing'''
    pass


class MockWin(object):
    
    def __init__(self):
        self.active = False
    
    def make_active(self):
        self.active = True
    
    def make_inactive(self):
        self.active = False
    
    def noutrefresh(self):
        pass


class TestInnerWindow(unittest.TestCase):
    
    def setUp(self):
        '''unit test set up
         Sets several functions to call do_nothing to allow
         test execution in non-curses environment. 
        '''
        self.inner_window_init_win = InnerWindow._init_win
        self.inner_window_set_color = InnerWindow.set_color
        InnerWindow._init_win = do_nothing
        InnerWindow.set_color = do_nothing
        self.win = InnerWindow(WindowArea(60, 70, 0, 0),
                               color_theme=ColorTheme(force_bw=True))
        self.win.window = MockWin()
        for x in range(5):
            self.win.add_object(MockWin())
    
    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        InnerWindow._init_win = self.inner_window_init_win
        InnerWindow.set_color = self.inner_window_set_color
    
    def test_activate_jump_idx_less_than_zero(self):
        '''InnerWindow.activate_object(idx, jump=True) for negative idx
           activates the first object'''
        self.assertEquals(self.win.active_object, None)
        
        self.win.activate_object(-5, jump=True)
        self.assertEquals(0, self.win.active_object)
        self.assertTrue(self.win.objects[0].active)
    
    def test_activate_jump_idx_gt_length(self):
        '''InnerWindow.activate_object(idx, jump=True)
           for idx > len(InnerWindow.objects) activates last object'''
        self.assertEquals(self.win.active_object, None)
        
        self.win.activate_object(len(self.win.objects) + 10, jump=True)
        self.assertEquals(len(self.win.objects) - 1, self.win.active_object)
        self.assertTrue(self.win.objects[-1].active)
    
    def test_on_page(self):
        '''InnerWindow.on_page() activates correct object and returns None'''
        self.win.activate_object(0)
        ret = self.win.on_page(1, 12345)
        self.assertEquals(None, ret)
        self.assertTrue(self.win.objects[-1].active)
    
    def test_on_page_no_change(self):
        '''InnerWindow.on_page() returns input_key when active
           object is unchanged'''
        self.win.activate_object(0)
        ret = self.win.on_page(-1, 12345)
        self.assertEquals(ret, 12345)
        self.assertTrue(self.win.objects[0].active)
    
    def test_on_page_no_active(self):
        '''InnerWindow.on_page() returns input_key when
           there is no active_object'''
        self.assertEquals(self.win.active_object, None)
        
        ret = self.win.on_page(1, 12345)
        self.assertEquals(ret, 12345)
        self.assertEquals(self.win.active_object, None)

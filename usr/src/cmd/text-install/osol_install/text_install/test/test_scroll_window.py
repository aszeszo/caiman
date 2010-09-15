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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import curses
import unittest

from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea
from osol_install.text_install.inner_window import InnerWindow
from osol_install.text_install.color_theme import ColorTheme

class MockInnerWin(object):
    '''Class for mock inner win'''

    def noutrefresh(self, *args):
        return

class MockEditField(object):
    '''Class for mock edit field'''
    def __init__(self):
        self.active = False

    def make_active(self, active=True):
        ''' Set active property'''
        self.active = active

    def make_inactive(self, inactive=True):
        ''' Set active property'''
        self.active = not inactive

def do_nothing(*args, **kwargs):
    '''does nothing'''
    pass


class TestScrollWindow(unittest.TestCase):
    '''Class to test ScrollWindow'''

    def setUp(self):
        '''unit test set up
         Sets several functions to call do_nothing to allow
         test execution in non-curses environment. 
        '''
        self.inner_window_init_win = InnerWindow._init_win
        self.inner_window_set_color = InnerWindow.set_color
        self.scroll_window_init_win = ScrollWindow._init_win
        self.scroll_window_no_ut_refresh = ScrollWindow.no_ut_refresh
        self.scroll_window_update_scroll_bar = ScrollWindow._update_scroll_bar
        InnerWindow._init_win = do_nothing
        InnerWindow.set_color = do_nothing
        ScrollWindow._init_win = do_nothing
        ScrollWindow.no_ut_refresh = do_nothing
        ScrollWindow._update_scroll_bar = do_nothing

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        InnerWindow._init_win = self.inner_window_init_win
        InnerWindow.set_color = self.inner_window_set_color
        ScrollWindow._init_win = self.scroll_window_init_win
        ScrollWindow.no_ut_refresh = self.scroll_window_no_ut_refresh
        ScrollWindow._update_scroll_bar = self.scroll_window_update_scroll_bar

class TestNoUtRefresh(unittest.TestCase):
    '''Class to test no_ut_refresh method'''

    def setUp(self):
        '''unit test set up
        '''
        self.inner_window_set_color = InnerWindow.set_color
        self.scroll_window_init_win = ScrollWindow._init_win
        self.scroll_window_update_scroll_bar = ScrollWindow._update_scroll_bar
        InnerWindow.set_color = do_nothing
        ScrollWindow._init_win = do_nothing
        ScrollWindow._update_scroll_bar = do_nothing

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        InnerWindow.set_color = self.inner_window_set_color
        ScrollWindow._init_win = self.scroll_window_init_win
        ScrollWindow._update_scroll_bar = self.scroll_window_update_scroll_bar

    def test_no_ut_refresh(self):
        '''Ensure deep_refresh is updating nested window screen location '''

        scroll_win = ScrollWindow(WindowArea(60, 70, 0, 0, 
                                  scrollable_columns=75),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.window = MockInnerWin()
        scroll_win.area.lower_right_y = 20
        scroll_win.area.lower_right_x = 20
        myscroll = ScrollWindow(WindowArea(10, 10, 0, 0,
                                scrollable_columns=15),
                                color_theme=ColorTheme(force_bw=True))
        myscroll.window = MockInnerWin()
        myscroll.area.lower_right_y = 16
        myscroll.area.lower_right_x = 18
        scroll_win.objects.append(myscroll)
        scroll_win.area.y_loc = 3
        scroll_win.area.x_loc = 5
        abs_y = 12
        abs_x = 15
        scroll_win.latest_yx = (abs_y, abs_x)
        scroll_win.no_ut_refresh()
        self.assertEquals(myscroll.latest_yx[0], scroll_win.area.y_loc + abs_y)
        self.assertEquals(myscroll.latest_yx[1], scroll_win.area.x_loc + abs_x)

class TestScrollCreated(TestScrollWindow):
    '''Class to test Scrollbar created or not appropriately'''

    def test_vert_scrollbar_created(self):
        '''Ensure vertical scrollbar is created or not appropriately'''
        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0, 
                                  scrollable_lines=75),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.get_use_vert_scroll_bar())

        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0, 
                                  scrollable_lines=70),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertFalse(scroll_win.get_use_vert_scroll_bar())

    def test_horiz_scrollbar_created(self):
        '''Ensure horizontal scrollbar is created or not appropriately'''
        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0, 
                                  scrollable_columns=75),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.get_use_horiz_scroll_bar())

        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0, 
                                  scrollable_columns=69),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertFalse(scroll_win.get_use_horiz_scroll_bar())

class TestScroll(TestScrollWindow):
    '''Class to test scroll method'''

    def test_scroll_no_args(self):
        '''Test that scroll called with no args throws ValueError'''
        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0,
                                  scrollable_lines=75),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.get_use_vert_scroll_bar())
        self.assertEquals(scroll_win.current_line[0], 0)
        self.assertRaises(ValueError, scroll_win.scroll)

    def test_scroll_one_line(self):
        '''Test to scroll one line '''
        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0,
                                  scrollable_lines=75),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.get_use_vert_scroll_bar())
        self.assertEquals(scroll_win.current_line[0], 0)
        scroll_win.scroll(lines=1)
        self.assertEquals(scroll_win.current_line[0], 1)

    def test_scroll_to_bottom(self):
        '''Test to scroll multiple lines to bottom of scrollarea'''
        lines = 70
        extra_lines = 5
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.scroll(scroll_to_line=5)
        self.assertTrue(scroll_win.at_bottom())

    def test_scroll_one_col(self):
        '''Test to scroll one column '''
        scroll_win = ScrollWindow(WindowArea(70, 70, 0, 0, 
                                  scrollable_columns=75),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.get_use_horiz_scroll_bar())
        self.assertEquals(scroll_win.current_line[1], 0)
        scroll_win.scroll(columns=1)
        self.assertEquals(scroll_win.current_line[1], 1)

    def test_scroll_to_right(self):
        '''Test to scroll multiple columns to right of scrollarea'''
        cols = 70
        extra_cols = 5
        scroll_win = ScrollWindow(WindowArea(70, cols, 0, 0, 
                                  scrollable_columns=cols+extra_cols),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.scroll(scroll_to_column=5)
        self.assertTrue(scroll_win.at_right())
        
    def test_scroll_past_top(self):
        '''Test to scroll past top, should end up at top '''
        lines = 70
        extra_lines = 5
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.at_top())
        scroll_win.scroll(lines=-3)
        self.assertTrue(scroll_win.at_top())

    def test_scroll_past_bottom(self):
        '''Test to scroll past bottom, should end up at bottom '''
        lines = 70
        extra_lines = 5
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.at_top())
        self.assertFalse(scroll_win.at_bottom())
        scroll_win.scroll(lines=10)
        self.assertFalse(scroll_win.at_top())
        self.assertTrue(scroll_win.at_bottom())

    def test_scroll_past_right(self):
        '''Test to scroll past right, should end up at right '''
        cols = 70
        extra_cols = 5
        scroll_win = ScrollWindow(WindowArea(70, cols, 0, 0, 
                                  scrollable_columns=cols+extra_cols),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.at_left())
        self.assertFalse(scroll_win.at_right())
        scroll_win.scroll(columns=10)
        self.assertFalse(scroll_win.at_left())
        self.assertTrue(scroll_win.at_right())

    def test_scroll_past_left(self):
        '''Test to scroll past left, should end up at left '''
        cols = 70
        extra_cols = 5
        scroll_win = ScrollWindow(WindowArea(70, cols, 0, 0, 
                                  scrollable_columns=cols+extra_cols),
                                  color_theme=ColorTheme(force_bw=True))
        self.assertTrue(scroll_win.at_left())
        scroll_win.scroll(columns=-3)
        self.assertTrue(scroll_win.at_left())
        

class TestOnArrowKey(TestScrollWindow):
    '''Class to test on_arrow_key method'''

    def test_scroll_right_left_arrow(self):
        '''Test to scroll right and left with arrow key '''
        cols = 3
        extra_cols = 5
        scroll_win = ScrollWindow(WindowArea(10, cols, 0, 0, 
                                  scrollable_columns=cols+extra_cols),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.active_object = None

        self.assertTrue(scroll_win.at_left())
        key = scroll_win.on_arrow_key(curses.KEY_RIGHT)
        self.assertEqual(key, None)
        self.assertFalse(scroll_win.at_left())

        key = scroll_win.on_arrow_key(curses.KEY_LEFT)
        self.assertEqual(key, None)
        self.assertTrue(scroll_win.at_left())

        key = scroll_win.on_arrow_key(curses.KEY_LEFT)
        self.assertEqual(key, curses.KEY_LEFT)
        self.assertTrue(scroll_win.at_left())

        scroll_win.scroll(columns=extra_cols-2)
        self.assertFalse(scroll_win.at_left())
        self.assertFalse(scroll_win.at_right())
        scroll_win.on_arrow_key(curses.KEY_RIGHT)
        self.assertTrue(scroll_win.at_right())
            
        scroll_win.scroll(columns=-(extra_cols-2))
        self.assertFalse(scroll_win.at_left())
        self.assertFalse(scroll_win.at_right())
        scroll_win.on_arrow_key(curses.KEY_LEFT)
        self.assertTrue(scroll_win.at_left())

    def test_scroll_down_up_arrow(self):
        '''Test to scroll down and up with arrow key '''
        lines = 4
        extra_lines = 9
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.active_object = None

        self.assertTrue(scroll_win.at_top())
        key = scroll_win.on_arrow_key(curses.KEY_DOWN)
        self.assertEqual(key, None)
        self.assertFalse(scroll_win.at_top())

        key = scroll_win.on_arrow_key(curses.KEY_UP)
        self.assertEqual(key, None)
        self.assertTrue(scroll_win.at_top())

        key = scroll_win.on_arrow_key(curses.KEY_UP)
        self.assertEqual(key, curses.KEY_UP)
        self.assertTrue(scroll_win.at_top())

        scroll_win.scroll(extra_lines-2)
        self.assertFalse(scroll_win.at_bottom())
        scroll_win.on_arrow_key(curses.KEY_DOWN)
        self.assertTrue(scroll_win.at_bottom())
            
        scroll_win.scroll(-(extra_lines-2))
        self.assertFalse(scroll_win.at_top())
        scroll_win.on_arrow_key(curses.KEY_UP)
        self.assertTrue(scroll_win.at_top())

    def test_act_obj_indexerr_edge(self):
        '''Test arrow key, active object, IndexError, at edge'''
        lines = 4
        extra_lines = 9
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.active_object = 0
        scroll_win.objects.append(object())
        key = scroll_win.on_arrow_key(curses.KEY_UP)
        self.assertEquals(scroll_win.current_line[0], 0)
        self.assertEquals(key, curses.KEY_UP)

    def test_act_obj_indexerr_not_edge(self):
        '''Test arrow key, active object, IndexError, not at edge'''
        lines = 4
        extra_lines = 9
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.active_object = 0
        scroll_win.objects.append(object())
        key = scroll_win.on_arrow_key(curses.KEY_DOWN)
        self.assertEquals(scroll_win.current_line[0], 1)
        self.assertEquals(key, None)

    def test_active_object(self):
        '''Test that arrow key changes active object'''
        lines = 4
        extra_lines = 9
        scroll_win = ScrollWindow(WindowArea(lines, 70, 0, 0, 
                                  scrollable_lines=lines + extra_lines),
                                  color_theme=ColorTheme(force_bw=True))
        scroll_win.active_object = 0
        myobj0 = MockEditField()
        myobj0.area = MockInnerWin()
        myobj0.area.y_loc = 1
        myobj0.active = True
        myobj1 = MockEditField()
        myobj1.area = MockInnerWin()
        myobj1.area.y_loc = 3
        myobj1.active = False
        scroll_win.objects.append(myobj0)
        scroll_win.objects.append(myobj1)

        key = scroll_win.on_arrow_key(curses.KEY_DOWN)
        self.assertEquals(key, None)
        self.assertEquals(scroll_win.active_object, 1)


if __name__ == '__main__':
    unittest.main()

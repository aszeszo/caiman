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
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''


import unittest

import terminalui
from terminalui.color_theme import ColorTheme
import terminalui.edit_field as edit_field
from terminalui.edit_field import EditField, PasswordField
from terminalui.window_area import WindowArea

from test_scroll_window import TestScrollWindow


terminalui.init_logging("test")


class MockTextbox(object):
    '''Replacement textbox to allow for testing of EditFields'''
    
    def __init__(self, *args, **kwargs):
        pass
    
    def __getattr__(self, name):
        return self
    
    def __call__(self, *args, **kwargs):
        return self


def Edit__init__(self, *args, **kwargs):
    '''Replacement __init__ function for testing EditField
    (Avoids curses calls)
    
    '''
    
    self.textbox = MockTextbox()
    self._modified = False
    self.text = None


class TestEditFieldBase(TestScrollWindow):
    
    # pylint: disable-msg=E1002
    def setUp(self):
        super(TestEditFieldBase, self).setUp()
        
        self.edit_field_textbox = edit_field.Textbox
        edit_field.Textbox = MockTextbox
    
    def tearDown(self):
        super(TestEditFieldBase, self).tearDown()
        
        edit_field.Textbox = self.edit_field_textbox


class TestEditField(TestEditFieldBase):

    # pylint: disable-msg=E1002
    def setUp(self):
        super(TestEditField, self).setUp()
        self.edit = EditField(WindowArea(1, 70, 0, 0),
                              color_theme=ColorTheme(force_bw=True))
    
    # pylint: disable-msg=E1002
    def tearDown(self):
        super(TestEditField, self).tearDown()
        self.edit = None
    
    def test_private_set_text_unmodified(self):
        '''Ensure that the private _set_text function does NOT flip
           the "modified" flag.'''
        # pylint: disable-msg=E1101
        self.assertFalse(self.edit._modified)
        self.edit._set_text("foo")
        self.assertFalse(self.edit._modified)
    
    def test_clear_text_modified(self):
        '''Ensure that clear_text() sets the modified flag,
           and clears the text'''
        # pylint: disable-msg=E1101
        self.assertFalse(self.edit._modified)
        self.edit.clear_text()
        self.assertTrue(self.edit._modified)
        self.assertFalse(self.edit.text)

class TestPasswordField(TestEditFieldBase):
    
    # pylint: disable-msg=E1002
    def setUp(self):
        super(TestPasswordField, self).setUp()
        self.pw_field = PasswordField(WindowArea(1, 70, 0, 0),
                                      color_theme=ColorTheme(force_bw=True),
                                      fill=True)
        self.pw_field_two = PasswordField(WindowArea(1, 70, 0, 0),
                                         color_theme=ColorTheme(force_bw=True),
                                         fill=True)
    
    def tearDown(self):
        super(TestPasswordField, self).tearDown()
        self.pw_field = None
        self.pw_field_two = None
    
    def test_compare_unmodified(self):
        # pylint: disable-msg=E1101
        self.assertTrue(self.pw_field.compare(self.pw_field_two))
        # pylint: disable-msg=E1101
        self.assertTrue(self.pw_field_two.compare(self.pw_field))
    
    def test_compare_one_modified(self):
        self.pw_field_two._modified = True
        # pylint: disable-msg=E1101
        self.assertFalse(self.pw_field.compare(self.pw_field_two))
        # pylint: disable-msg=E1101
        self.assertFalse(self.pw_field_two.compare(self.pw_field))
    
    def test_compare_modified_text_equal(self):
        self.pw_field._modified = True
        self.pw_field_two._modified = True
        self.pw_field.text = list("one")
        self.pw_field_two.text = list("one")
        # pylint: disable-msg=E1101
        self.assertTrue(self.pw_field.compare(self.pw_field_two))
        # pylint: disable-msg=E1101
        self.assertTrue(self.pw_field_two.compare(self.pw_field))
    
    def test_compare_modified_text_different(self):
        self.pw_field._modified = True
        self.pw_field_two._modified = True
        self.pw_field.text = list("one")
        self.pw_field_two.text = list("two")
        # pylint: disable-msg=E1101
        self.assertFalse(self.pw_field.compare(self.pw_field_two))
        # pylint: disable-msg=E1101
        self.assertFalse(self.pw_field_two.compare(self.pw_field))

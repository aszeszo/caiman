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

from solaris_install.sysconfig.users import UserScreen
import terminalui


terminalui.init_logging("test")


class MockUser(object):
    
    ENCRYPTED = "<ENCRYPTED>"
    
    def __init__(self):
        self.password = None
        self.login_name = "name"
        self.real_name = "name"
        self.is_role = False
        self.blank = True
    
    def get_password(self):
        return self._password
    
    def set_password(self, password, encrypted=False):
        
        if not password and not encrypted:
            self.blank = True
            self.actual_password = password
            self._password = password
            return
        else:
            self.blank = False
        
        self.actual_password = password
        if not encrypted:
            password = MockUser.ENCRYPTED
        self._password = password
    
    password = property(get_password, set_password)


class MockPWField(object):
    
    def __init__(self, text):
        self.modified = False
        self.text = text
    
    def get_text(self):
        return self.text
    
    def clear_text(self):
        self.modified = True
        self.text = ""
    
    def compare(self, other):
        if self.modified:
            if other.modified and self.get_text() == other.get_text():
                # Both fields modified, text is equal
                return True
        elif not other.modified:
            # Both fields not modified
            return True
        
        return False


class TestUserScreen(unittest.TestCase):
    
    def setUp(self):
        self.UserScreen__init__ = UserScreen.__init__
        UserScreen.__init__ = lambda x, y: None
        self.user_screen = UserScreen(None)
    
    def tearDown(self):
        UserScreen.__init__ = self.UserScreen__init__
        
        self.user_screen = None


class TestOnChangeScreen(TestUserScreen):
    
    def setUp(self):
        super(TestOnChangeScreen, self).setUp()
        
        for field in ("root_pass_edit", "root_confirm_edit", "user_pass_edit",
                      "user_confirm_edit", "real_name_edit", "username_edit"):
            setattr(self.user_screen, field, MockPWField(field))
        self.user_screen.root = MockUser()
        self.user_screen.user = MockUser()
    
    def test_root_pass_not_match(self):
        '''If root passwords don't match, password is cleared'''
        self.user_screen.root_pass_edit.text = "foo"
        self.user_screen.root_confirm_edit.text = "bar"
        self.user_screen.root_pass_edit.modified = True
        self.user_screen.root_confirm_edit.modified = True
        self.user_screen.on_change_screen()
        self.assertEquals(self.user_screen.root.actual_password, "")
    
    def test_root_pass_blank(self):
        '''When root password is blank, password is set correctly'''
        self.user_screen.root_pass_edit.text = ""
        self.user_screen.root_confirm_edit.text = ""
        self.user_screen.on_change_screen()
        self.assertTrue(self.user_screen.root.blank)
    
    def test_root_pass_non_blank(self):
        '''Ensure non-blank root password is set properly'''
        self.user_screen.root_pass_edit.text = "foo"
        self.user_screen.root_confirm_edit.text = "foo"
        self.user_screen.root_pass_edit.modified = True
        self.user_screen.root_confirm_edit.modified = True
        self.user_screen.on_change_screen()
        self.assertEquals(self.user_screen.root.actual_password, "foo")
    
    def test_user_pass_not_match(self):
        '''If user passwords don't match, password is cleared'''
        self.user_screen.user_pass_edit.text = "foo"
        self.user_screen.user_confirm_edit.text = "bar"
        self.user_screen.user_pass_edit.modified = True
        self.user_screen.user_confirm_edit.modified = True
        self.user_screen.on_change_screen()
        self.assertEquals(self.user_screen.user.actual_password, "")
    
    def test_user_pass_blank(self):
        '''When user password is blank, password is set correctly'''
        self.user_screen.user_pass_edit.text = ""
        self.user_screen.user_confirm_edit.text = ""
        self.user_screen.on_change_screen()
        self.assertTrue(self.user_screen.user.blank)
    
    def test_user_pass_non_blank(self):
        '''Ensure non-blank user password is set properly'''
        self.user_screen.user_pass_edit.text = "foo"
        self.user_screen.user_confirm_edit.text = "foo"
        self.user_screen.user_pass_edit.modified = True
        self.user_screen.user_confirm_edit.modified = True
        self.user_screen.on_change_screen()
        self.assertEquals(self.user_screen.user.actual_password, "foo")

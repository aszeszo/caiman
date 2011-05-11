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
3) pfexec python2.6 test_disk_select.py

A single test may be run by specifying the test as an argument to
step 3, e.g.:

pfexec python2.6 test_disk_select.py OnActivateTest.test_on_activate_default

Since the proto area is used for the PYTHONPATH, the gate must be rebuilt for
these tests to pick up any changes in the tested code.

'''

import numbers
import unittest

import solaris_install.text_install.disk_selection as disk_selection
import terminalui
from terminalui.base_screen import BaseScreen
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance
from solaris_install.target.size import Size

terminalui.init_logging("test")
BaseScreen.set_default_quit_text("test", "test", "test", "test")


class MockCenterWin(object):
    '''Mocks an InnerWindow as used by a MainWindow'''
    
    def add_paragraph(self, *args, **kwargs):
        pass


class MockAll(object):
    '''Generic Mock object that 'never' raises an AttributeError'''
    
    def __getattr__(self, name):
        return self
    
    def __call__(self, *args, **kwargs):
        return None


class MockTC(object):
    ''' Mocks the target controller '''

    minimum_target_size = Size("3gb")
    recommended_target_size = Size("6gb")


class DiskSelectTest(unittest.TestCase):
    '''Test the DiskScreen'''
    
    def setUp(self):
        self.engine = get_new_engine_instance()
        self.screen = disk_selection.DiskScreen(MockAll(), MockTC())
        self.screen.disk_win = MockAll()
    
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
        self.assertTrue(isinstance(self.screen.minimum_size, Size))
        self.assertTrue(isinstance(self.screen.recommended_size, Size))


if __name__ == '__main__':
    unittest.main()

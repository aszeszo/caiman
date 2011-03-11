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
from terminalui.main_window import MainWindow


terminalui.init_logging("test")


class MockAction(object):
    
    def __init__(self, key, reference):
        self.key = key
        self.reference = reference


class TestMainWindow(unittest.TestCase):
    
    def setUp(self):
        self.MainWindow__init__ = MainWindow.__init__
        MainWindow.__init__ = lambda x: None
        self.main = MainWindow()
    
    def test_reset_actions(self):
        '''MainWindow.reset_actions() resets MainWindow.default_actions
           while preserving the Action's method reference'''
        old_reference = object()
        old_actions = [MockAction(x, old_reference) for x in range(5)]
        default_reference = object()
        default_actions = [MockAction(x, default_reference) for x in range(5)]
        
        self.main.default_actions = old_actions
        self.main._default_actions = default_actions
        
        self.main.reset_actions()
        
        self.assertTrue(self.main.default_actions)
        for action in self.main.default_actions:
            self.assertFalse(action in old_actions)
            self.assertFalse(action in default_actions)
            self.assertFalse(action.reference is old_reference)
            self.assertTrue(action.reference is default_reference)

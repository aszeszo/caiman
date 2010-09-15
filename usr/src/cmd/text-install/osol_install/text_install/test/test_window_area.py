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

import unittest

from osol_install.text_install.window_area import WindowArea

class TestScrollProperties(unittest.TestCase):
    '''Class to test properties'''

    def test_scrollable_lines(self):
        '''Test scrollable_lines getter and setter '''
        print "\nhello"
        num_lines = 70
        my_win = WindowArea(num_lines, 60, 0, 0)
        self.assertEqual(my_win.scrollable_lines, num_lines)
        my_win.scrollable_lines = 80
        self.assertEqual(my_win.scrollable_lines, 80)

    def test_scrollable_columns(self):
        '''Test scrollable_columns getter and setter '''
        num_cols = 75
        my_win = WindowArea(50, num_cols, 0, 0)
        self.assertEqual(my_win.scrollable_columns, 75)
        my_win.scrollable_columns = 80
        self.assertEqual(my_win.scrollable_columns, 80)

if __name__ == '__main__':
    unittest.main()

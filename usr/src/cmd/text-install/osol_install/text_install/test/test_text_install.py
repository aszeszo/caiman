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

import osol_install.text_install as text_install


class TestTextInstall(unittest.TestCase):
    
    def test_reboot_cmds(self):
        '''_reboot_cmds(x86) returns expected list of potential reboot commands
        * /usr/sbin/reboot -f -- rpool/ROOT/<BE>
        * /usr/sbin/reboot
        
        '''
        cmds = text_install._reboot_cmds(True)
        
        # First command should be: /usr/sbin/reboot -f -- rpool/ROOT/<BE>
        self.assertEqual(cmds[0][0], text_install.REBOOT)
        self.assertEqual(cmds[0][1], "-f")
        self.assertEqual(cmds[0][2], "--")
        # Last item will be something like: 'rpool/ROOT/active-on-reboot-BE'
        # Ensure that it's enclosed in the single-quotes
        self.assertTrue(cmds[0][3].startswith("'"))
        self.assertTrue(cmds[0][3].endswith("'"))
        self.assertEqual(len(cmds[0]), 4)
        
        # Second command should be just: /usr/sbin/reboot
        self.assertEqual(cmds[1][0], text_install.REBOOT)
        self.assertEqual(len(cmds[1]), 1)
        
        self.assertEqual(len(cmds), 2)
    
    def test_reboot_cmds_sparc(self):
        '''_reboot_cmds(sparc) returns expected list of reboot commands
        (SPARC requires the additional "-Z")
        * /usr/sbin/reboot -f -- -Z rpool/ROOT/<BE>
        * /usr/sbin/reboot
        
        '''
        cmds = text_install._reboot_cmds(False)
        
        # First command should be: /usr/sbin/reboot -f -- -Z rpool/ROOT/<BE>
        self.assertEqual(cmds[0][0], text_install.REBOOT)
        self.assertEqual(cmds[0][1], "-f")
        self.assertEqual(cmds[0][2], "--")
        self.assertEqual(cmds[0][3], "-Z")
        # Last item will be something like: rpool/ROOT/active-on-reboot-BE
        # Just ensure that there's something there
        self.assertTrue(cmds[0][4])
        self.assertEqual(len(cmds[0]), 5)
        
        # Second command should be just: /usr/sbin/reboot
        self.assertEqual(cmds[1][0], text_install.REBOOT)
        self.assertEqual(len(cmds[1]), 1)
        
        self.assertEqual(len(cmds), 2)

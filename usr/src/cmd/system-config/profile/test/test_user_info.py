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

from solaris_install.sysconfig.profile.user_info import UserInfo


class TestUserInfoToXML(unittest.TestCase):
    
    def test_invalid(self):
        user = UserInfo(login_name="root")
        self.assertEqual(None, user.to_xml())
    
    def test_root(self):
        root = UserInfo(login_name="root")
        root.password = "test"
        root_xml = root.to_xml()
        found = set()
        expected = set(["login", "password"])
        for child in root.get_children():
            if child.propname == "login":
                self.assertEqual("root", child.propval)
            elif child.propname == "password":
                self.assertTrue(child.propval)
            found.add(child.propname)
        
        missing = expected - found
        self.assertFalse(missing, "Root is missing properties: %s" % missing)
    
    def test_non_root(self):
        user = UserInfo(login_name="user", real_name="test user", gid=10,
                        shell="/usr/bin/bash", roles="root",
                        profiles="System Administrator",
                        sudoers="ALL=(ALL) ALL",
                        autohome="localhost:/export/home/&")

        user.password = "test"
        user_xml = user.to_xml()
        found = set()
        expected = set(["login", "password", "roles", "profiles", "shell",
                        "sudoers", "autohome", "gid", "type", "description"])
        for child in user.get_children():
            if child.propname == "login":
                self.assertEqual("user", child.propval)
            elif child.propname == "password":
                self.assertTrue(child.propval)
            found.add(child.propname)
        
        missing = expected - found
        self.assertFalse(missing, "User is missing properties: %s" % missing)

#!/usr/bin/python
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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''Tests for the Transfer Info interface'''

import unittest
from solaris_install.engine import InstallEngine
from solaris_install.transfer.info import Software
import solaris_install.transfer as Transfer


class TestCreateCheckpoint(unittest.TestCase):
    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile

    def tearDown(self):
        InstallEngine._instance = None
        self.engine.data_object_cache.clear()
        self.engine = None
        self.doc = None

    def test_create_cpio_chkpt(self):
        '''Test create_checkpoint correctly returns cpio values'''

        soft_node = Software("CPIO_Transfer", "CPIO")
        self.doc.insert_children([soft_node])
        soft_class = self.doc.get_first_child(class_type=Software)

        chkpt, mod, cls = Transfer.create_checkpoint(soft_class)
        self.assertEqual(chkpt, 'CPIO_Transfer')
        self.assertEqual(mod, 'solaris_install.transfer.cpio')
        self.assertEqual(cls, 'TransferCPIO')

    def test_create_ips_chkpt(self):
        '''Test create_checkpoint correctly returns ips values'''

        soft_node = Software("IPS_Transfer", "IPS")
        self.doc.insert_children([soft_node])
        soft_class = self.doc.get_first_child(class_type=Software)

        chkpt, mod, cls = Transfer.create_checkpoint(soft_class)
        self.assertEqual(chkpt, 'IPS_Transfer')
        self.assertEqual(mod, 'solaris_install.transfer.ips')
        self.assertEqual(cls, 'TransferIPS')

    def test_create_p5i_chkpt(self):
        '''Test create_checkpoint correctly returns P5I values'''

        soft_node = Software("P5I_Transfer", "P5I")
        self.doc.insert_children([soft_node])
        soft_class = self.doc.get_first_child(class_type=Software)

        chkpt, mod, cls = Transfer.create_checkpoint(soft_class)
        self.assertEqual(chkpt, 'P5I_Transfer')
        self.assertEqual(mod, 'solaris_install.transfer.p5i')
        self.assertEqual(cls, 'TransferP5I')

    def test_bad_chkpt(self):
        '''Test create_checkpoint correctly fails with invalid type '''

        soft_node = Software("P5I_Transfer", "BAD")
        self.doc.insert_children([soft_node])
        soft_class = self.doc.get_first_child(class_type=Software)

        self.assertRaises(TypeError, Transfer.create_checkpoint(soft_class))

    def test_no_chkpt(self):
        '''Test create_checkpoint correctly returns ips values'''

        soft_class = None
        self.assertRaises(TypeError, Transfer.create_checkpoint(soft_class))


if __name__ == '__main__':
    unittest.main()

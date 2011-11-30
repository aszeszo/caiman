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
import os
import tempfile
import osol_install.auto_install.grub as grub


class TestGrub(unittest.TestCase):
    '''Tests for grub'''

    def setUp(self):
        '''unit test set up'''
        self.path = '/foo/auto_install/x86iso'
        self.svcname = 'myservice'
        self.bootargs = 'console=ttya'

        # create original menu.lst file
        self.menulst_txt = (
            "default=0\n"
            "timeout=30\n"
            "min_mem64=0\n\n"

            "title Oracle Solaris 11 11/11 Text Installer and command line\n"
            "\tkernel$ /%(name)s/platform/i86pc/kernel/$ISADIR/unix -B "
            "%(args)s,install_media=http://$serverIP:5555/%(path)s,"
            "install_service=%(name)s,install_svc_address=$serverIP:5555\n"
            "\tmodule$ /%(name)s/platform/i86pc/$ISADIR/boot_archive\n\n"

            "title Oracle Solaris 11 11/11 Automated Install\n"
            "\tkernel$ /%(name)s/platform/i86pc/kernel/$ISADIR/unix -B "
            "%(args)s,install=true,"
            "install_media=http://$serverIP:5555/%(path)s,"
            "install_service=%(name)s,install_svc_address=$serverIP:5555\n"
            "\tmodule$ /%(name)s/platform/i86pc/$ISADIR/boot_archive\n") % \
            {'args': self.bootargs, 'path': self.path, 'name': self.svcname}

        (tfp, self.mymenulst) = tempfile.mkstemp()
        os.write(tfp, self.menulst_txt)
        os.close(tfp)

    def tearDown(self):
        '''unit test tear down'''
        os.remove(self.mymenulst)

    def test_update_imagepath(self):
        '''verify update_imagepath updates imagepath correctly'''

        # update path in menu.lst file, read file back in
        # and ensure file updated properly
        newpath = '/export/mydir/myimage'
        grub.update_imagepath(self.mymenulst, self.path, newpath)
        with open(self.mymenulst, 'r') as menulst_file:
            newmenulst = menulst_file.read()
        expected_text = self.menulst_txt.replace(self.path, newpath)
        self.assertEqual(newmenulst, expected_text)

    def test_update_svcname(self):
        '''verify update_svcname updates svcname correctly'''

        # update svcname in menu.lst file, read file back in
        # and ensure file updated properly
        newsvcname = 'new_service'
        grub.update_svcname(self.mymenulst, newsvcname, newsvcname)
        with open(self.mymenulst, 'r') as menulst_file:
            newmenulst = menulst_file.read()
        expected_text = self.menulst_txt.replace('/' + self.svcname + '/',
                                                 '/' + newsvcname + '/')
        expected_text = expected_text.replace(
            'install_service=' + self.svcname,
            'install_service=' + newsvcname)
        self.assertEqual(newmenulst, expected_text)

    def test_update_bootargs(self):
        '''verify update_bootargs updates bootargs correctly'''

        # update bootargs in menu.lst file, read file back in
        # and ensure file updated properly
        newbootargs = 'console=ttyb'
        grub.update_bootargs(self.mymenulst, self.bootargs, newbootargs)
        with open(self.mymenulst, 'r') as menulst_file:
            newmenulst = menulst_file.read()
        expected_text = self.menulst_txt.replace(self.bootargs, newbootargs)
        self.assertEqual(newmenulst, expected_text)


if __name__ == '__main__':
    unittest.main()

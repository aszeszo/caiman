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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''


import grp
import os
import pwd
import tempfile
import unittest
import osol_install.auto_install.grub as grub


class BootInstance(object):
    '''Class for fake BootInstance (instead of SolarisNetBootInstance)'''
    def __init__(self, name='mysvc', path='/export/myimage', bootargs=''):
        self.svcname = name
        self.path = path
        self.bootargs = bootargs
        self.kargs = ("-B %(args)s,install=true,"
            "install_media=http://$serverIP:5555/%(path)s,"
            "install_service=%(name)s,install_svc_address=$serverIP:5555\n" %
             {'args': self.bootargs, 'path': self.path, 'name': self.svcname})

        self.kernel = ("\tkernel$ /%(name)s/platform/i86pc/kernel/$ISADIR/unix"
                        % {'name': self.svcname})

        self.boot_archive = ("\tmodule$ /%(name)s/platform/i86pc/$ISADIR/"
                             "boot_archive\n" % {'name': self.svcname})


class TestGrub(unittest.TestCase):
    '''Tests for grub'''

    def setUp(self):
        '''unit test set up'''
        self.path = '/foo/auto_install/x86path'
        self.svcname = 'myservice'
        self.bootargs = 'console=ttya'

        # create original boot instance strings
        self.kargs = ("-B %(args)s,install=true,"
            "install_media=http://$serverIP:5555/%(path)s,"
            "install_service=%(name)s,install_svc_address=$serverIP:5555\n" %
             {'args': self.bootargs, 'path': self.path, 'name': self.svcname})
        self.kernel = ("\tkernel$ /%(name)s/platform/i86pc/kernel/$ISADIR/unix"
                        % {'name': self.svcname})
        self.boot_archive = ("\tmodule$ /%(name)s/platform/i86pc/$ISADIR/"
                             "boot_archive\n" % {'name': self.svcname})

    def test_update_imagepath(self):
        '''verify update_kargs_imagepath updates imagepath correctly'''

        newpath = '/export/mydir/myimage'
        new_kargs = grub.update_kargs_imagepath(self.kargs, self.path, newpath)
        expected_text = self.kargs.replace(self.path, newpath)
        self.assertEqual(new_kargs, expected_text)

    def test_update_boot_instance_svcname(self):
        '''verify update_boot_instance_svcname updates svcname correctly'''
        newname = 'newsvcname'
        boot_inst = BootInstance(name=self.svcname, path=self.path,
                                 bootargs=self.bootargs)
        boot_inst = grub.update_boot_instance_svcname(boot_inst,
            self.svcname, 'newsvcname')
        boot_inst2 = BootInstance(name=newname, path=self.path,
                                     bootargs=self.bootargs)
        self.assertEqual(boot_inst.kargs, boot_inst2.kargs)
        self.assertEqual(boot_inst.kernel, boot_inst2.kernel)
        self.assertEqual(boot_inst.boot_archive, boot_inst2.boot_archive)

    def test_update_svcname_functions(self):
        '''verify individual update_svcname functions work correctly'''

        newsvcname = 'new_service'

        # test using kernel string
        new_kernel = grub.update_kernel_ba_svcname(self.kernel, self.svcname,
                                                   newsvcname)
        expected_text = self.kernel.replace('/' + self.svcname + '/',
                                           '/' + newsvcname + '/')
        self.assertEqual(new_kernel, expected_text)

        # test using module string
        new_boot_archive = grub.update_kernel_ba_svcname(self.boot_archive,
            self.svcname, newsvcname)
        expected_text = self.boot_archive.replace('/' + self.svcname + '/',
                                                  '/' + newsvcname + '/')
        self.assertEqual(new_boot_archive, expected_text)

        new_kargs = grub.update_kargs_install_service(self.kargs,
            self.svcname, newsvcname)
        expected_text = self.kargs.replace('install_service=' + self.svcname,
                                           'install_service=' + newsvcname)
        self.assertEqual(new_kargs, expected_text)

    def test_update_bootargs(self):
        '''verify update_kargs_bootargs updates bootargs correctly'''

        # update bootargs in menu.lst file, read file back in
        # and ensure file updated properly
        newbootargs = 'console=ttyb'
        new_kargs = grub.update_kargs_bootargs(self.kargs, self.bootargs,
                                               newbootargs)
        expected_text = self.kargs.replace(self.bootargs, newbootargs)
        self.assertEqual(new_kargs, expected_text)

    def test_set_perms(self):
        '''Ensure that set_perms sets permissions properly'''

        # save original umask
        orig_umask = os.umask(0022)
        # set too restrictive and too open umask
        for mask in (0066, 0000):
            tmpfile = tempfile.mktemp()
            with open(tmpfile, 'w'):
                pass
            os.umask(mask)
            grub.set_perms(tmpfile, pwd.getpwuid(os.getuid()).pw_name,
                           grp.getgrgid(os.getgid()).gr_name, 420)
            mode = os.stat(tmpfile).st_mode
            self.assertEqual(mode, 0100644)
            os.remove(tmpfile)
        # return umask to the original value
        os.umask(orig_umask)


if __name__ == '__main__':
    unittest.main()

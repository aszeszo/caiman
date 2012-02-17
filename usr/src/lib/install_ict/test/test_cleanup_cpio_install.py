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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''
   test_cleanup_live_cd
   Test program for testing CleanupLiveCD
'''

import os
import tempfile
import unittest

from common_create_simple_doc import CreateSimpleDataObjectCache
from solaris_install.ict.cleanup_cpio_install import CleanupCPIOInstall
from solaris_install.engine.test.engine_test_utils import reset_engine
from solaris_install.transfer.info import IPSSpec
from solaris_install.transfer.info import CPIOSpec
from solaris_install.transfer.info import Software


def create_filesystem(*args):
    """ create_filesystem - function to create a dummy filesystem in
    /var/tmp

    *args - a list of specific files to create inside the filesystem

    create_filesystem(*["/etc/foo", "/etc/bar/fleeb"]) will create a
    filesystem with those two files in it.  if empty directories are
    wanted, append a slash to the end of the specific path:  /etc/,
    /lib/amd64/, etc
    """
    # get a temporary directory
    tdir = tempfile.mkdtemp(dir="/tmp", prefix="ict_test_")

    # walk each entry in args and create the files and directories as
    # needed
    for arg in args:
        # strip the leading slash
        arg = arg.lstrip("/")

        # check for a directory entry
        if arg.endswith("/"):
            if not os.path.exists(os.path.join(tdir, arg)):
                os.makedirs(os.path.join(tdir, arg))
            continue

        # create the directory if needed
        if not os.path.exists(os.path.join(tdir, os.path.dirname(arg))):
            os.makedirs(os.path.join(tdir, os.path.dirname(arg)))

        # touch the file
        with open(os.path.join(tdir, arg), "w+") as fh:
            pass

    os.chmod(tdir, 0777)
    return tdir


class TestCleanupCPIOInstall(unittest.TestCase):
    '''test the functionality for CleanupCPIOInstall Class'''

    def setUp(self):
        '''Setup for tests'''

        # Test Packages
        self.TEXT_PKG_REMOVE_LIST = ['pkg:/system/install/media/internal',
                                     'pkg:/system/install/text-install']

        # packages added to the cleanup list
        self.add_files = ['file1', 'file2', 'file3']

        self.filesys_files = ['/var/tmp/test_dir/',
            '/var/tmp/file1', '/var/tmp/file2',
            '/mnt/test_dir/file1', '/mnt/file2', '/mnt/file3',
            '/save/etc/gconf/schemas/panel-default-setup.entries',
            '/save/etc/X11/gdm/custom.conf',
            '/save/etc/xdg/autostart/updatemanagernotifier.desktop',
            '/save/usr/share/dbus-1/services/gnome-power-manager.service',
            '/save/usr/share/gnome/autostart/gnome-keyring-daemon-wrapper.desktop',
            '.livecd', '.volsetid', '.textinstall', 'etc/sysconfig/language',
            '.liveusb', 'a', 'bootcd_microroot', 'var/user/jack',
            'var/cache/gdm/jack/dmrc', 'var/cache/gdm/jack/', '/save/bogus']

        self.test_target = create_filesystem(*self.filesys_files)

        # Create a data object to hold the required data
        self.simple = CreateSimpleDataObjectCache(test_target=self.test_target)

    def tearDown(self):
        '''Tear down for the tests'''
        reset_engine()
        self.simple.doc = None

        if os.path.exists(self.test_target):
            os.unlink(self.test_target)

    def test_live_cd_cleanup_dry(self):
        '''Test the dry run functionality for cleanup_livecd'''

        # Create an IPS node for packages to be removed
        self.soft_node = Software("cleanup_cpio_install")
        self.pkg_rm_node = IPSSpec()
        self.pkg_rm_node.action = "uninstall"
        self.pkg_rm_node.contents = self.TEXT_PKG_REMOVE_LIST
        self.soft_node.insert_children([self.pkg_rm_node])
        self.simple.doc.persistent.insert_children([self.soft_node])

        # Create a CPIO node for files to be removed
        self.add_cleanup_node = CPIOSpec()
        self.add_cleanup_node.action = "uninstall"
        self.add_cleanup_node.contents = self.add_files
        self.soft_node.insert_children([self.add_cleanup_node])

        cleanup_list = ['.livecd', '.volsetid', '.textinstall',
                        'etc/sysconfig/language', '.liveusb', 'a',
                        'bootcd_microroot', 'var/user/jack',
                        'var/cache/gdm/jack/dmrc', 'var/cache/gdm/jack/',
                        'file1', 'file2', 'file3']

        # Instantiate the checkpoint
        self.clean_lcd = CleanupCPIOInstall("cleanup_cpio_install")

        # Call the execute command for the checkpoint
        # with dry_run set to true.
        try:
            self.clean_lcd.execute(dry_run=True)
        except Exception as e:
            self.fail(str(e))

        self.assertEquals(cleanup_list, self.clean_lcd.cleanup_list)

    def test_get_progress_estimate(self):
        '''Test get progress estimate return value'''

        self.clean_lcd = CleanupCPIOInstall("cleanup_cpio_install")

        # Check the return value for the progress estimate
        self.assertEquals(self.clean_lcd.get_progress_estimate(), 60)

if __name__ == '__main__':
    unittest.main()

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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

import logging
import os
import shutil
import unittest

from solaris_install.engine import InstallEngine
from solaris_install.logger import InstallLogger
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import SVR4Spec
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.svr4 import TransferSVR4
from solaris_install.transfer.svr4 import TransferSVR4Attr
from solaris_install.transfer.svr4 import AbstractSVR4

ROOT = os.environ.get("ROOT")


class TestTransferSVR4Functions(unittest.TestCase):
    '''Tests for the  TransferSVR4 class'''
    TEST_SRC_DIR = ROOT + "/var/tmp"
    TEST_DST_DIR = ROOT + "/tmp"

    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile
        self.soft_node = Software("SVR4Transfer", "SVR4")
        self.tr_node = SVR4Spec()
        self.soft_node.insert_children([self.tr_node])
        self.doc.insert_children([self.soft_node])
        self.tr_svr4 = TransferSVR4("SVR4Transfer")
        self.make_dummy_pkg(self.TEST_SRC_DIR + "/SUNWpkg1")
        self.make_dummy_pkg(self.TEST_SRC_DIR + "/SUNWpkg2")
        self.make_dummy_pkg(self.TEST_SRC_DIR + "/SUNWpkg3")
        if not os.path.isdir(AbstractSVR4.ADMIN_FILE_DIR):
            os.makedirs(AbstractSVR4.ADMIN_FILE_DIR, 0755)

    def tearDown(self):
        self.engine.data_object_cache.clear()
        self.doc = None
        self.engine = None
        self.soft_node = None
        self.tr_node = None
        self.tr_svr4 = None
        InstallEngine._instance = None
        shutil.rmtree(self.TEST_SRC_DIR + "/SUNWpkg1")
        shutil.rmtree(self.TEST_SRC_DIR + "/SUNWpkg2")
        shutil.rmtree(self.TEST_SRC_DIR + "/SUNWpkg3")
        if os.path.isdir(AbstractSVR4.ADMIN_FILE_DIR):
            os.removedirs(AbstractSVR4.ADMIN_FILE_DIR)

    def make_dummy_pkg(self, where):
        os.makedirs(where)
        fd = open(where + "/pkgmap", "w")
        fd.close()
        fd = open(where + "/pkginfo", "w")
        fd.close()

    def test_software_type(self):
        self.assertTrue(self.soft_node.tran_type == "SVR4")

    def test_cancel(self):
        '''Test the cancel method'''
        try:
            self.tr_svr4.cancel()
        except Exception as err:
            self.fail(str(err))

    def test_check_cancel_event(self):
        self.tr_svr4._cancel_event = True
        try:
            self.tr_svr4.check_cancel_event()
        except Exception as err:
            self.fail(str(err))

    def test_validate_dst(self):
        '''Test error is raised when no destination is registered'''
        self.tr_svr4.dst = None
        self.assertRaises(Exception, self.tr_svr4._validate_input)

    def test_validate_src(self):
        '''Test error is raised when no source is registered'''
        self.tr_svr4.dst = "/mydest"
        self.tr_svr4.src = None
        self.assertRaises(Exception, self.tr_svr4._validate_input)

    def test_validate_no_transfer_list(self):
        '''Test error is raised when transfer list is empty'''
        self.tr_svr4.dst = "/mydest"
        self.tr_svr4._transfer_list = []
        self.assertRaises(Exception, self.tr_svr4._validate_input)

    def test_validate_no_args(self):
        ''''Test error is raised when no args are provided'''
        self.tr_svr4.dst = "/mydest"
        self.tr_svr4.src = "/mysrc"
        self.tr_svr4._transfer_list = [{'action': 'install',
                                   'contents': ['mypkg']},
                                  {'action': 'uninstall',
                                   'contents': ["myuninstallpkg"]}]
        self.assertRaises(Exception, self.tr_svr4._validate_input)

    def test_src_not_exist(self):
        '''Test that an error is raised when the source doesn't exist'''
        src = Source()
        pub = Publisher()
        origin = Origin("/doesnt_exist")
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_src_not_specified(self):
        '''Test error when src is not specified
        '''
        dst = Destination()
        dst_path = self.TEST_DST_DIR
        path = Dir(dst_path)
        dst.insert_children([path])

        self.soft_node.insert_children([dst])
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_more_than_one_src(self):
        '''Test error when more than one src directory is added.
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        dst_path = self.TEST_DST_DIR
        path = Dir(dst_path)
        dst.insert_children([path])

        src2 = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src2.insert_children([pub])

        self.soft_node.insert_children([dst, src, src2])
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_dst_not_specified(self):
        '''Test error when dst is not specified
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        self.soft_node.insert_children([src])
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_more_than_one_dst(self):
        '''Test error with more than one dst directory
        '''
        dst = Destination()
        path = Dir("/hello")
        dst.insert_children([path])

        dst2 = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst2.insert_children([path])

        self.soft_node.insert_children([dst, dst2])
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_more_than_one_same_soft_node(self):
        '''Test error when multiple software nodes with same name
        '''
        soft_node2 = Software("SVR4Transfer")
        self.doc.insert_children([soft_node2])
        tr_node2 = SVR4Spec()
        soft_node2.insert_children([tr_node2])
        self.doc.insert_children([soft_node2])

        self.assertRaises(Exception, TransferSVR4, "SVR4Transfer")

    def test_more_than_one_soft_node(self):
        '''Test checkpoint and software node match correctly
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1"]

        soft_node2 = Software("SVR4Transfer2")
        self.doc.insert_children([soft_node2])

        try:
            self.tr_svr4.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_checkpoint_soft_node_mismatch(self):
        '''Test fail when checkpoint and software node don't match
        '''
        self.assertRaises(Exception, TransferSVR4, "SVR4_Transfer")

    def test_multiple_args_declared(self):
        '''Test having multiple args fails'''
        args = Args({"svr4_args": "-n -d"})
        self.tr_node.insert_children([args])
        args2 = Args({"svr4_args": "-n -d, mi"})
        self.tr_node.insert_children([args2])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_bad_args_name(self):
        '''Test having invalid args key fails'''
        args = Args({"svr44444_args": "-n -d"})
        self.tr_node.insert_children([args])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_single_args_instance(self):
        '''Test pass when single instance of args provided
        '''
        mysrc = "srcdir"
        mydest = "destfile"
        args = Args({"svr4_args": "-n -d %s -R %s" % (mysrc, mydest)})
        self.tr_node.insert_children([args])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1"]

        try:
            self.tr_svr4.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_install_uninstall_dry_run(self):
        '''Test an install followed by an uninstall'''
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1", "SUNWpkg2", "SUNWpkg3"]
        args = Args({"svr4_args": "-n -R %s" % (self.TEST_DST_DIR)})
        self.tr_node.insert_children([args])
        self.tr_node2 = SVR4Spec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = ["SUNWpkg2"]
        self.soft_node.insert_children([self.tr_node2])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])

        try:
            self.tr_svr4.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_dry_run_transfer(self):
        '''Test with accurate input dry run succeeds
        '''
        self.tr_node2 = SVR4Spec()
        self.tr_node2.action = "install"
        self.tr_node2.contents = ["SUNWpkg1", "SUNWpkg2"]
        self.soft_node.insert_children([self.tr_node2])
        args2 = Args({"svr4_args": "-n -R %s" % (self.TEST_DST_DIR)})
        self.tr_node2.insert_children([args2])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])

        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1", "SUNWpkg2"]

        try:
            self.tr_svr4.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_valid_transfer_action(self):
        '''Test valid input with dry run.
        '''
        self.tr_node2 = SVR4Spec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = ["SUNWpkg1", "SUNWpkg2"]
        self.soft_node.insert_children([self.tr_node2])
        args2 = Args({"svr4_args": "-n -R %s" % (self.TEST_DST_DIR)})
        self.tr_node2.insert_children([args2])

        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])

        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1", "SUNWpkg2"]

        self.tr_node3 = SVR4Spec()
        self.tr_node3.action = "transform"
        self.tr_node3.contents = ["SUNWpkg1", "SUNWpkg2"]
        self.soft_node.insert_children([self.tr_node3])

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_transfer_fail_install(self):
        '''Test that the transfer mechanism to install
           fails with a non-existent package
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg0"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_transfer_fail_uninstall(self):
        '''Test that the transfer mechanism to uninstall
           fails with a non-existent package
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        self.tr_node.action = 'uninstall'
        self.tr_node.contents = ["SUNWpkg0"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_install_bad_args(self):
        '''Test that the transfer install
           fails with bad SVR4 package args
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        args = Args({"svr4_args": "-q -r -s -t"})
        self.tr_node.insert_children([args])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWpkg1"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_uninstall_bad_args(self):
        '''Test transfer uninstall fails with bad args
        '''
        src = Source()
        pub = Publisher()
        origin = Origin(self.TEST_SRC_DIR)
        pub.insert_children([origin])
        src.insert_children([pub])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([src, dst])
        args = Args({"svr4_args": "-q -r -s -t"})
        self.tr_node.insert_children([args])
        self.tr_node.action = "uninstall"
        self.tr_node.contents = ["SUNWpkg1"]
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)


class TestTransferSVR4AttrFunctions(unittest.TestCase):
    '''Tests for the TransferSVR4Attr class'''
    TEST_SRC_DIR = ROOT + "/var/tmp"
    TEST_DST_DIR = ROOT + "/tmp"

    def setUp(self):
        logging.setLoggerClass(InstallLogger)
        logging.getLogger("InstallationLogger")
        self.tr_svr4 = TransferSVR4Attr("SVR4Transfer")

    def tearDown(self):
        self.tr_svr4 = None
        InstallLogger.DEFAULTFILEHANDLER = None

    def test_src_not_exist(self):
        '''Test fail when src directory doesn't exist.
        '''
        self.tr_svr4.src = "/mysrc"
        self.tr_svr4.dst = self.TEST_DST_DIR

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_src_not_specified(self):
        '''Test fail when src  is not specified
        '''
        self.tr_svr4.dst = "/tmp"

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_dst_not_specified(self):
        '''Test fail when dst is not specified
        '''
        self.tr_svr4.src = "/tmp"
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=True)

    def test_install_bad_args(self):
        '''Test install fail with bad args
        '''
        self.tr_svr4.src = self.TEST_SRC_DIR
        self.tr_svr4.dst = self.TEST_DST_DIR
        self.tr_svr4.svr4_args = "-q -r -s -t"
        self.tr_svr4.action = "install"
        self.tr_svr4.contents = ["SUNWpkg1"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_uninstall_bad_args(self):
        '''Test uninstall fails with bad args
        '''
        self.tr_svr4.src = self.TEST_SRC_DIR
        self.tr_svr4.dst = self.TEST_DST_DIR
        self.tr_svr4.svr4_args = "-q -r -s -t"
        self.tr_svr4.action = "uninstall"
        self.tr_svr4.contents = ["SUNWpkg1"]
        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_transfer_fail_install(self):
        '''Test that the transfer mechanism to install
           fails with a non-existent package
        '''
        self.tr_svr4.src = self.TEST_SRC_DIR
        self.tr_svr4.dst = self.TEST_DST_DIR
        self.tr_svr4.action = "install"
        self.tr_svr4.contents = ["SUNWpkg0"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

    def test_transfer_fail_uninstall(self):
        '''Test that the transfer fails with a bad package
        '''
        self.tr_svr4.src = self.TEST_SRC_DIR
        self.tr_svr4.dst = self.TEST_DST_DIR
        self.tr_svr4.action = "uninstall"
        self.tr_svr4.contents = ["SUNWpkg0"]

        self.assertRaises(Exception, self.tr_svr4.execute, dry_run=False)

if  __name__ == '__main__':
    unittest.main()

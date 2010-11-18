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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''Tests for the Transfer Info interface'''

import unittest
from pkg.client.api import IMG_TYPE_PARTIAL
from solaris_install.engine import InstallEngine
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import CPIOSpec
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Image
from solaris_install.transfer.info import ImType
from solaris_install.transfer.info import IPSSpec
from solaris_install.transfer.info import Mirror
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import SVR4Spec


class TestCPIOInfoFunctions(unittest.TestCase):
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

    def test_info(self):
        '''Test that all the arguments get into the node correctly'''
        soft_node = Software("CPIO transfer test 1")
        cpio_node = CPIOSpec()

        dst = Destination()
        path = Dir("/a")
        dst.insert_children([path])

        src = Source()
        path = Dir("/bin")
        src.insert_children([path])

        # first check src and dst
        soft_node.insert_children([dst, src, cpio_node])
        self.doc.insert_children([soft_node])
        soft_list = self.doc.get_children("CPIO transfer test 1", Software)
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                try:
                    args = tr.get_children("args", Args)[0]
                except:
                    self.assertTrue(True)
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(tr.action, None)
                self.assertEqual(tr.type, None)
                self.assertEqual(tr.contents, None)

        # set cpio args
        args = Args({"cpio_args": "-pdm"})
        cpio_node.insert_children([args])

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, None)
                self.assertEqual(tr.type, None)
                self.assertEqual(tr.contents, None)

        # set file_list content
        cpio_node.action = "install"
        cpio_node.type = "FILE"
        cpio_node.contents = "/usr/share/tr_file_list"

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, "install")
                self.assertEqual(tr.type, "FILE")
                self.assertEqual(tr.contents, "/usr/share/tr_file_list")

        # set dir_list
        cpio_node.action = "install"
        cpio_node.type = "DIR"
        cpio_node.contents = "/usr/share/tr_dir_list"

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, "install")
                self.assertEqual(tr.type, "DIR")
                self.assertEqual(tr.contents, "/usr/share/tr_dir_list")

        # set skip_file_list
        cpio_node.action = "uninstall"
        cpio_node.type = "FILE"
        cpio_node.contents = "/usr/share/tr_skip_file_list"

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.type, "FILE")
                self.assertEqual(tr.contents, "/usr/share/tr_skip_file_list")

        # set dir_excl_list
        cpio_node.action = "uninstall"
        cpio_node.type = "DIR"
        cpio_node.contents = "/usr/share/tr_dir_excl_list"

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.type, "DIR")
                self.assertEqual(tr.contents, "/usr/share/tr_dir_excl_list")

        # set media transform
        cpio_node.action = "transform"
        cpio_node.type = "None"
        cpio_node.contents = "/usr/share/media_transform"

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", CPIOSpec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["cpio_args"], "-pdm")
                self.assertEqual(tr.action, "transform")
                self.assertEqual(tr.type, "None")
                self.assertEqual(tr.contents, "/usr/share/media_transform")


class TestIPSInfoFunctions(unittest.TestCase):
    '''Tests that validate the IPS info functionality'''

    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile

    def tearDown(self):
        self.engine.data_object_cache.clear()
        InstallEngine._instance = None
        self.engine = None
        self.doc = None

    def test_name(self):
        '''Test that names are populated correctly in the Software node'''
        ips_node = Software("transfer 1")
        ips_node2 = Software("transfer 2")
        self.doc.insert_children([ips_node, ips_node2])
        soft_list = self.doc.get_children("transfer 1", Software)
        for soft in soft_list:
            self.assertEqual(soft._name, "transfer 1")

        soft_list = self.doc.get_children("transfer 2", Software)
        for soft in soft_list:
            self.assertEqual(soft._name, "transfer 2")

    def test_info(self):
        '''Test that the arguments get into the node correctly'''

        # just dst, need to check default repo
        soft_node = Software("transfer test 1")
        tr_node = IPSSpec()
        soft_node.insert_children([tr_node])
        self.doc.insert_children([soft_node])

        dst = Destination()
        ips_image = Image("/rpool/dc", "create") 
        self.img_type = ImType("full")
        ips_image.insert_children([self.img_type])
        dst.insert_children([ips_image])

        src = Source()
        pub = Publisher()
        origin = Origin("http://pkg.oracle.com/solaris/release")
        pub.insert_children([origin])
        src.insert_children([pub])

        # first check src and dst
        soft_node.insert_children([dst, src, soft_node])
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)

                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, "full")
                self.assertEqual(img_type[0].zone, False)
                self.assertEqual(tr.action, None)
                self.assertEqual(tr.contents, None)
                self.assertEqual(tr.app_callback, None)
                self.assertEqual(tr.purge_history, False)

        # pkg install list is set
        tr_node.action = "install"
        tr_node.contents = ["SUNWcs", "SUNWcsr"]
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)
                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, "full")
                self.assertEqual(img_type[0].zone, False)
                self.assertEqual(tr.contents, ["SUNWcs", "SUNWcsr"])
                self.assertEqual(tr.action, "install")
                self.assertEqual(tr.purge_history, False)
                self.assertEqual(tr.app_callback, None)

        # pkg uninstall list is set
        tr_node.action = "uninstall"
        tr_node.contents = ["SUNWcs"]
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)

                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, "full")
                self.assertEqual(img_type[0].zone, False)
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.contents, ["SUNWcs"])
                self.assertEqual(tr.purge_history, False)
                self.assertEqual(tr.app_callback, None)

        # purge history is set to true
        tr_node.purge_history = True
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)

                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, "full")
                self.assertEqual(img_type[0].zone, False)
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.contents, ["SUNWcs"])
                self.assertEqual(tr.purge_history, True)

        # is zone is set to True
        self.img_type.zone = True
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)

                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, "full")
                self.assertEqual(img_type[0].zone, True)
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.contents, ["SUNWcs"])
                self.assertEqual(tr.purge_history, True)

        # completeness is set to IMG_TYPE_PARTIAL
        self.img_type.completeness = IMG_TYPE_PARTIAL
        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                src_list = soft.get_children("source", Source)
                self.assertEqual(len(src_list), 1)

                pub = src_list[0].get_children("publisher", Publisher)
                origin = pub[0].get_children("origin", Origin)
                self.assertEqual(origin[0].origin, "http://pkg.oracle.com/solaris/release")

                dst_list = soft.get_children("destination", Destination)
                self.assertEqual(len(dst_list), 1)

                image = dst_list[0].get_children("image", Image)
                self.assertEqual(len(image), 1)

                img_type = image[0].get_children("img_type", ImType)
                self.assertEqual(len(img_type), 1)

                self.assertEqual(image[0].img_root, "/rpool/dc")
                self.assertEqual(image[0].action, "create")
                self.assertEqual(img_type[0].completeness, IMG_TYPE_PARTIAL)
                self.assertEqual(img_type[0].zone, True)
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.contents, ["SUNWcs"])
                self.assertEqual(tr.purge_history, True)

    def test_multiple_source_info(self):
        '''Test that specifying multiple sources succeeds.'''
        soft_node = Software("transfer test 2")
        src1 = Source()
        pub1 = Publisher("test1.org")
        origin1 = Origin("http://test1/dev")
        pub1.insert_children([origin1])
        src1.insert_children([pub1])

        src2 = Source()
        pub2 = Publisher("test2.org")
        origin2 = Origin("http://test2/dev")
        pub2.insert_children([origin2])
        src2.insert_children([pub2])

        tr_node = IPSSpec()
        soft_node.insert_children([src1, src2, tr_node])
        self.doc.insert_children([soft_node])
        soft_list = self.doc.get_children("transfer test 2", Software)
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            pub = src_list[0].get_children("publisher", Publisher)
            origin = pub[0].get_children("origin", Origin)
            self.assertEqual(pub[0].publisher, "test1.org")
            self.assertEqual(origin[0].origin, "http://test1/dev")
            pub = src_list[1].get_children("publisher", Publisher)
            origin = pub[0].get_children("origin", Origin)
            self.assertEqual(pub[0].publisher, "test2.org")
            self.assertEqual(origin[0].origin, "http://test2/dev")

    def test_mirror_info(self):
        '''Test that writting to the mirror object works'''
        soft_node = Software("transfer test 1")
        src = Source()
        pub = Publisher("test.org")
        origin = Origin("http://test/dev")
        mirror = Mirror("http://mirror")
        pub.insert_children([origin, mirror])
        src.insert_children([pub])
        tr_node = IPSSpec()
        soft_node.insert_children([src, tr_node])
        self.doc.insert_children([soft_node])

        soft_list = self.doc.get_children("transfer test 1", Software)
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            pub = src_list[0].get_children("publisher", Publisher)
            origin = pub[0].get_children("origin", Origin)
            mirror = pub[0].get_children("mirror", Mirror)
            self.assertEqual(pub[0].publisher, "test.org")
            self.assertEqual(origin[0].origin, "http://test/dev")
            self.assertEqual(mirror[0].mirror, "http://mirror")

    def test_args(self):
        '''Test that setting the ips arguments works'''
        soft_node = Software("transfer test 4")
        tr_node = IPSSpec()
        ips_args_node = Args({"force": True, "set-something": 12})
        tr_node.insert_children([ips_args_node])
        soft_node.insert_children([tr_node])
        self.doc.insert_children([soft_node])
        soft_list = self.doc.get_children("transfer test 4", Software)
        for soft in soft_list:
            tr_list = soft.get_children(class_type=IPSSpec)
            for tr in tr_list:
                ips_args = tr.get_children("args", Args)
                for args in ips_args:
                    for key in args.arg_dict:
                        if key is not "force" or key is not "set-something":
                            self.assertTrue(True)
                        if key is "force":
                            self.assertEqual(args.arg_dict[key], True)
                        if key is "set-something":
                            self.assertEqual(args.arg_dict[key], 12)


class TestP5IInfoFunctions(unittest.TestCase):
    DEF_P5I_FILE = "http://pkg.oracle.com/solaris/release/p5i/0/SUNW1394.p5i"

    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile

    def tearDown(self):
        self.engine.data_object_cache.clear()
        InstallEngine._instance = None
        self.engine = None
        self.doc = None

    def test_file_name(self):
        '''Test that Origin is set correctly in the node'''
        p5i_node = Software("transfer 1")
        src = Source()
        pub = Publisher()
        origin = Origin(self.DEF_P5I_FILE)
        pub.insert_children([origin])
        src.insert_children([pub])
        p5i_node.insert_children([src])
        self.doc.insert_children([p5i_node])

        soft_list = self.doc.get_children("transfer 1", Software)
        for soft in soft_list:
            src = soft.get_children("source", Source)[0]
            pub = src.get_children("publisher", Publisher)[0]
            origin = pub.get_children("origin", Origin)[0]
            self.assertTrue(origin.origin == self.DEF_P5I_FILE)


class TestSVR4InfoFunctions(unittest.TestCase):
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

    def test_info(self):
        '''Test that all the arguments get into the node correctly'''
        soft_node = Software("SVR4 transfer test 1")
        svr4_node = SVR4Spec()

        dst = Destination()
        path = Dir("/a")
        dst.insert_children([path])

        src = Source()
        path = Dir("/bin")
        src.insert_children([path])

        # first check src and dst
        soft_node.insert_children([dst, src, svr4_node])
        self.doc.insert_children([soft_node])
        soft_list = self.doc.get_children("SVR4 transfer test 1", Software)

        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", SVR4Spec)
            for tr in tr_list:
                try:
                    args = tr.get_children("args", Args)[0]
                except:
                    self.assertTrue(True)
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(tr.action, None)
                self.assertEqual(tr.contents, None)

        # set cpio args
        args = Args({"svr4_args": "-n -d"})
        svr4_node.insert_children([args])

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", SVR4Spec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["svr4_args"], "-n -d")
                self.assertEqual(tr.action, None)
                self.assertEqual(tr.contents, None)

        # set install package content
        svr4_node.action = "install"
        svr4_node.contents = ["SUNWcsr", "SUNWcsu"]

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", SVR4Spec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["svr4_args"], "-n -d")
                self.assertEqual(tr.action, "install")
                self.assertEqual(tr.contents, ["SUNWcsr", "SUNWcsu"])

        # set uninstall package content
        svr4_node.action = "uninstall"
        svr4_node.contents = ["SUNWlxml", "SUNWzfs"]

        # Check that we can read the attributes out correctly
        for soft in soft_list:
            src_list = soft.get_children("source", Source)
            self.assertEqual(len(src_list), 1)

            src_path = src_list[0].get_children("dir", Dir)
            self.assertEqual(len(src_path), 1)
            src = src_path[0].dir_path

            dst_list = soft.get_children("destination", Destination)
            self.assertEqual(len(dst_list), 1)

            dst_path = dst_list[0].get_children("dir", Dir)
            self.assertEqual(len(dst_path), 1)
            dst = dst_path[0].dir_path

            tr_list = soft.get_children("transfer", SVR4Spec)
            for tr in tr_list:
                args = tr.get_children("args", Args)[0]
                self.assertEqual(dst, "/a")
                self.assertEqual(src, "/bin")
                self.assertEqual(args.arg_dict["svr4_args"], "-n -d")
                self.assertEqual(tr.action, "uninstall")
                self.assertEqual(tr.contents, ["SUNWlxml", "SUNWzfs"])

if __name__ == '__main__':
    unittest.main()

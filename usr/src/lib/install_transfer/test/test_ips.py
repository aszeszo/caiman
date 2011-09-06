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

import unittest
import pkg.client.progress as progress

from solaris_install.engine import InstallEngine
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Facet
from solaris_install.transfer.info import Image
from solaris_install.transfer.info import ImType
from solaris_install.transfer.info import IPSSpec
from solaris_install.transfer.info import Mirror
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Property
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.ips import TransferIPS
from solaris_install.transfer.ips import TransferIPSAttr

DRY_RUN = True


class TestIPSAttrFunctions(unittest.TestCase):
    IPS_IMG_DIR = "/rpool/test_ips"

    def setUp(self):
        self.tr_ips = TransferIPSAttr("IPS transfer")
        self.tr_ips.dst = self.IPS_IMG_DIR

    def tearDown(self):
        pass

    def test_create(self):
        '''Test that the IPS image area is created'''
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_dst_not_specified(self):
        '''Test that an error is raised when dst is not
           specified
        '''
        self.tr_ips.dst = None
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

    def test_install(self):
        '''Test that an IPS package can be installed'''
        self.tr_ips.action = "install"
        self.tr_ips.contents = ["SUNWcs"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_uninstall(self):
        '''Test that an IPS package can be uninstalled'''
        self.tr_ips.img_action = "use_existing"
        self.tr_ips.action = "uninstall"
        self.tr_ips.contents = ["system/library/svm-rcm"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_purge_history(self):
        '''Test that the history is purged'''
        self.tr_ips.action = "install"
        self.tr_ips.contents = ["SUNWcs"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

        self.tr_ips.action = "use_existing"
        self.tr_ips.purge_history = True
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_image_args(self):
        '''Test that setting Args for the image works'''
        self.tr_ips.image_args = {"force": True}
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_prog_track_image_args(self):
        '''Test that setting progtrack in image args works'''
        self.tr_ips.image_args = {"progtrack": progress.QuietProgressTracker()}
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_install_args(self):
        '''Test that setting Args for the install works'''
        self.tr_ips.action = "install"
        self.tr_ips.contents = ["SUNWcs"]
        self.tr_ips.args = {"refresh_catalogs": False}
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_uninstall_args(self):
        '''Test that setting Args for the uninstall works'''
        self.tr_ips.action = "uninstall"
        self.tr_ips.contents = ["system/library/svm-rcm"]
        self.tr_ips.args = {"update_index": False}
        self.tr_ips.img_action = "use_existing"
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_multiple_sources(self):
        '''Test that adding multiple sources succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org", ["http://ipkg.sfbay.sun.com/release/"], None),
             ("contrib.opensolaris.org",
              ["http://ipkg.sfbay.sun.com/contrib/"],
              None),
             ("extra", ["http://ipkg.sfbay.sun.com/extra/"], None)]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_source_addition(self):
        '''Test that add another publisher to the repo succeeds'''
        self.tr_ips.img_action = "update"
        self.tr_ips.src = \
            [("opensolaris.org", ["http://pkg.opensolaris.org/dev/"], None),
            ("extra", ["http://pkg.opensolaris.org/extra/"], None)]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_source_replacement(self):
        '''Test that replacing a source succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org", ["http://ipkg.sfbay.sun.com/dev/"], None)]
        self.dst = self.IPS_IMG_DIR
        self.ips_action = "update"
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_mirrors(self):
        '''Test that creating mirrors succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org",
              ["http://ipkg.sfbay.sun.com/release/"],
              ["http://ipkg.central.sun.com:8000/"])]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_mirror_addition(self):
        '''Test that adding mirrors succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org",
              ["http://ipkg.sfbay.sun.com/release/"],
              ["http://ipkg.central.sun.com:8000/"]),
              ("extra",
              ["http://ipkg.sfbay.sun.com/extra/"],
              ["http://ipkg.central.sun.com/extra/"])]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_property(self):
        '''Test that setting properties succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org", ["http://ipkg.sfbay.sun.com/release/"], None),
             ("contrib.opensolaris.org",
              ["http://ipkg.sfbay.sun.com/contrib/"], None),
             ("extra", ["http://ipkg.sfbay.sun.com/extra/"], None)]
        self.tr_ips.properties = {"display-copyrights": 'False',
                                  "preferred-publisher": "extra"}
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_create_facets(self):
        '''Test that creating facets succeeds'''
        self.tr_ips.src = \
            [("opensolaris.org", ["http://ipkg.sfbay.sun.com/release/"], None)]
        self.tr_ips.facets = {"facet.doc": 'True'}
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_invalid_facets(self):
        '''Test that an error is raised with an invalid facet'''
        self.tr_ips.src = \
            [("opensolaris.org", ["http://ipkg.sfbay.sun.com/release/"], None)]
        self.tr_ips.facets = {"doc": 'True'}
        self.assertRaises(Exception, self.tr_ips.execute)

    def test_progress_estimate(self):
        '''Test the progress estimate functionality'''
        self.tr_ips.action = "install"
        self.tr_ips.contents = ["SUNWcs", "SUNWcsd",
                                "entire", "SUNWmd",
                                "babel_install"]
        try:
            estimate = self.tr_ips.get_progress_estimate()
        except Exception as err:
            self.fail(str(err))

        self.assertTrue(estimate == self.tr_ips.DEFAULT_PROG_EST * \
            (len(self.tr_ips.contents) / self.tr_ips.DEFAULT_PKG_NUM))


class TestIPSFunctions(unittest.TestCase):
    IPS_IMG_DIR = "/rpool/test_ips"

    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile
        self.soft_node = Software("IPS transfer")
        self.tr_node = IPSSpec()
        dst = Destination()
        self.ips_image = Image(self.IPS_IMG_DIR, "create")
        ips_im_type = ImType("full")
        self.ips_image.insert_children([ips_im_type])
        dst.insert_children([self.ips_image])
        self.soft_node.insert_children([self.tr_node, dst])
        self.doc.insert_children([self.soft_node])
        self.tr_ips = TransferIPS("IPS transfer")

    def tearDown(self):
        self.engine.data_object_cache.clear()
        InstallEngine._instance = None
        self.doc = None
        self.soft_node = None
        self.tr_node = None
        self.tr_ips = None
        self.engine = None

    def test_create(self):
        '''Test that the IPS Transfer object is created'''
        try:
            try_ips = TransferIPS("IPS transfer")
        except (TypeError, NameError):
            self.fail("Failed to create TransferIPS object")

    def test_install(self):
        '''Test that an IPS package can be installed'''
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs", "entire"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_uninstall(self):
        '''Test that an IPS package can be uninstalled'''
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs", "system/library/svm-rcm"]
        self.tr_node2 = IPSSpec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = ["system/library/svm-rcm"]

        self.soft_node.insert_children([self.tr_node2])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_purge_history(self):
        '''Test that the history is purged'''
        self.tr_node.purge_history = True
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_image_type(self):
        '''Test that image_type functionality succeeds'''
        self.tr_ips = TransferIPS("IPS transfer", {"zonename": "zonename"})
        self.ips_image.delete_children()
        ips_im_type = ImType("partial", zone=True)
        self.ips_image = Image(self.IPS_IMG_DIR, "create")
        self.ips_image.insert_children([ips_im_type])
        dst = Destination()
        dst.insert_children([self.ips_image])
        self.soft_node.delete_children()
        self.soft_node.insert_children([self.tr_node, dst])
        self.doc.delete_children()
        self.doc.insert_children([self.soft_node])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_image_args(self):
        '''Test that setting Args for the image works'''
        image_args = Args(arg_dict={"force": True})
        self.ips_image.insert_children([image_args])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_ssl_key_in_image_args(self):
        '''Test that setting ssl_key in image_args produces an error'''
        image_args = Args(arg_dict={"ssl_key": "aaa"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

    def test_ssl_cert_in_image_args(self):
        '''Test that setting ssl_cert in image_args produces an error'''
        image_args = Args(arg_dict={"ssl_cert": "aaa"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

    def test_install_args(self):
        '''Test that setting Args for the install works'''
        install_args = Args(arg_dict={"refresh_catalogs": False})
        self.tr_node.insert_children([install_args])
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs"]
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_uninstall_args(self):
        '''Test that setting Args for the uninstall works'''
        uninstall_args = Args(arg_dict={"update_index": False})
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs", "system/library/svm-rcm"]
        self.tr_node2 = IPSSpec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = ["system/library/svm-rcm"]
        self.tr_node2.insert_children([uninstall_args])
        self.soft_node.insert_children([self.tr_node2])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_default_publisher(self):
        '''Test that using the default publisher succeeds'''
        src = Source()
        pub = Publisher()
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub.insert_children([origin])
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_multiple_sources(self):
        '''Test that setting multiple sources succeeds'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub2 = Publisher("contrib.opensolaris.org")
        origin2 = Origin("http://ipkg.sfbay.sun.com/contrib/")
        pub3 = Publisher("extra")
        origin3 = Origin("http://ipkg.sfbay.sun.com/extra/")
        pub.insert_children([origin])
        pub2.insert_children([origin2])
        pub3.insert_children([origin3])
        src.insert_children([pub, pub2, pub3])
        self.soft_node.insert_children([src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_source_addition(self):
        '''Test that adding additional sources succeeds'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/dev/")
        pub.insert_children([origin])
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

        # Now add another publisher to the repo
        self.ips_image.action = "update"
        pub2 = Publisher("extra")
        origin2 = Origin("http://ipkg.sfbay.sun.com/extra/")
        pub2.insert_children([origin2])
        src.insert_children([pub2])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_source_replacement(self):
        '''Test that replacing a source succeeds'''
        # Setup an IPS image
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub2 = Publisher("extra")
        origin2 = Origin("http://ipkg.sfbay.sun.com/extra/")
        pub2.insert_children([origin2])
        pub.insert_children([origin])
        src.insert_children([pub, pub2])
        self.soft_node.insert_children([src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

        # Create a new transaction with a differnt publisher/origin.
        # Specify to update the image created above.
        self.soft_node = Software("IPS post install")
        self.doc.insert_children([self.soft_node])
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/dev/")
        pub.insert_children([origin])
        src.insert_children([pub])
        dst = Destination()
        self.ips_image = Image(self.IPS_IMG_DIR, "update")
        dst.insert_children([self.ips_image])
        self.soft_node.insert_children([dst, src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_mirrors(self):
        '''Test creating mirrors succeeds'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        mirror = Mirror("http://ipkg.central.sun.com:8000/")
        pub.insert_children([origin, mirror])
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_property(self):
        '''Test that setting properties succeeds'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub2 = Publisher("contrib.opensolaris.org")
        origin2 = Origin("http://ipkg.sfbay.sun.com/contrib/")
        pub3 = Publisher("extra")
        origin3 = Origin("http://ipkg.sfbay.sun.com/extra/")
        pub.insert_children([origin])
        pub2.insert_children([origin2])
        pub3.insert_children([origin3])
        src.insert_children([pub, pub2, pub3])
        self.soft_node.insert_children([src])
        prop = Property("display-copyrights", 'False')
        prop2 = Property("preferred-publisher", "extra")
        self.ips_image.insert_children([prop, prop2])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_create_facets(self):
        '''Test that creating facets succeeds'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub.insert_children([origin])
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        facet = Facet("facet.doc", 'True')
        self.ips_image.insert_children([facet])
        try:
            self.tr_ips.execute(dry_run=DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_set_invalid_facets(self):
        '''Ensure an error is raised for an invalid facet'''
        src = Source()
        pub = Publisher("opensolaris.org")
        origin = Origin("http://ipkg.sfbay.sun.com/release/")
        pub.insert_children([origin])
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        facet = Facet("doc", 'True')
        self.ips_image.insert_children([facet])

        self.assertRaises(Exception, self.tr_ips.execute)

    def test_progress_estimate(self):
        '''Test that progress estimate succeeds'''
        self.tr_node.action = "install"
        self.tr_node.contents = ["SUNWcs", "SUNWcsd", "entire",
                                         "SUNWmd", "babel_install"]
        try:
            estimate = self.tr_ips.get_progress_estimate()
        except Exception as err:
            self.fail(str(err))

        self.assertTrue(estimate == self.tr_ips.DEFAULT_PROG_EST * \
            (len(self.tr_node.contents) / self.tr_ips.DEFAULT_PKG_NUM))

    def test_invalid_args(self):
        '''Ensure error raised when repo components are set as args'''
        image_args = Args(arg_dict={"prefix": "prefix string"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(ValueError, self.tr_ips.execute, dry_run=DRY_RUN)

        # Test repo_uri fails
        self.ips_image.delete_children()
        image_args = Args(arg_dict={"repo_uri": "url string"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

        # Test origins fails
        self.ips_image.delete_children()
        image_args = Args(arg_dict={"origins": "origin string"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

        # Test mirrors fails
        self.ips_image.delete_children()
        image_args = Args(arg_dict={"mirrors": "mirror string"})
        self.ips_image.insert_children([image_args])
        self.assertRaises(Exception, self.tr_ips.execute, dry_run=DRY_RUN)

    def test_checkpoint_soft_node_match(self):
        '''The checkpoint and software node match'''
        try:
            tr_ips = TransferIPS("IPS transfer")
        except Exception as err:
            self.fail(str(err))


if __name__ == '__main__':
    unittest.main()

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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

import os
import logging
import unittest

from solaris_install.engine import InstallEngine
from solaris_install.logger import InstallLogger
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Image
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import P5ISpec
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.p5i import TransferP5I
from solaris_install.transfer.p5i import TransferP5IAttr

DRY_RUN = True

# allow the user to specify publisher information in environment variables.  If
# not specified, fallback to default values.
PKG_PUBLISHER = os.getenv("TRANSFERTESTPUB", "solaris")
PKG_PUB_PATH = os.getenv("TRANSFERTESTPUBPATH",
                         "http://ipkg.us.oracle.com/solaris11/dev")
PKG_P5IFILE = os.getenv("TESTTRANSFERP5IFILE", "p5i/0/SUNW1394.p5i")
PKG_FULL_P5I = os.path.join(PKG_PUB_PATH, PKG_P5IFILE)

IPS_IMG_DIR = "/tmp"


class TestP5IFunctions(unittest.TestCase):

    def setUp(self):
        InstallEngine._instance = None
        InstallEngine()
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile
        self.soft_node = Software("P5I transfer")
        self.tr_node = P5ISpec()
        dst = Destination()
        self.ips_image = Image(IPS_IMG_DIR, "create")
        dst.insert_children([self.ips_image])
        self.soft_node.insert_children([self.tr_node, dst])
        self.doc.insert_children([self.soft_node])

    def tearDown(self):
        self.engine.data_object_cache.clear()
        InstallEngine._instance = None
        self.doc = None
        self.soft_node = None
        self.tr_node = None
        self.engine = None

    def test_install(self):
        '''Test that p5i install is successful'''
        src = Source()
        pub = Publisher("test")
        origin = Origin(PKG_FULL_P5I)
        pub.insert_children(origin)
        pub_prim = Publisher("test2")
        origin_prim = Origin(PKG_PUB_PATH)
        pub1 = Publisher(PKG_PUBLISHER)
        origin1 = Origin(PKG_PUB_PATH)
        pub_prim.insert_children(origin_prim)
        pub1.insert_children(origin1)
        src.insert_children([pub, pub_prim, pub1])
        self.soft_node.insert_children(src)
        tr_p5i = TransferP5I("P5I transfer")
        try:
            tr_p5i.execute(DRY_RUN)
        except Exception as err:
            self.fail(str(err))

    def test_src_not_specified(self):
        '''Test an error is raised when the source is not specified.
        '''
        tr_p5i = TransferP5I("P5I transfer")
        self.assertRaises(Exception, tr_p5i.execute, DRY_RUN)

    def test_publisher_not_specified(self):
        '''Test an error is raised when the publisher is
           not specified.
        '''
        src = Source()
        self.soft_node.insert_children([src])
        tr_p5i = TransferP5I("P5I transfer")
        self.assertRaises(Exception, tr_p5i.execute, DRY_RUN)

    def test_origin_not_specified(self):
        '''Test an errer is raised when the origin is
           not specified.
        '''
        src = Source()
        pub = Publisher()
        src.insert_children([pub])
        self.soft_node.insert_children([src])
        tr_p5i = TransferP5I("P5I transfer")
        try:
            tr_p5i.execute(DRY_RUN)
            self.assertTrue(False)
        except Exception:
            self.assertTrue(True)

    def test_bogus_p5i_file(self):
        '''Test that including a nonexistent origin
           fails.
        '''
        src = Source()
        pub = Publisher()
        origin = Origin("/tmp/bogus")
        pub.insert_children([origin])
        pub_prim = Publisher()
        origin_prim = Origin(PKG_PUB_PATH)
        pub1 = Publisher("contrib.opensolaris.org")
        origin1 = Origin("http://pkg.opensolaris.org/contrib")
        pub2 = Publisher("extra")
        origin2 = Origin("http://ipkg.sfbay/extra")
        pub_prim.insert_children([origin_prim])
        pub1.insert_children([origin1])
        pub2.insert_children([origin2])
        src.insert_children([pub, pub_prim, pub1, pub2])
        self.soft_node.insert_children([src])
        tr_p5i = TransferP5I("P5I transfer")
        self.assertRaises(Exception, tr_p5i.execute, DRY_RUN)


class TestP5IAttrFunctions(unittest.TestCase):
    def setUp(self):
        logging.setLoggerClass(InstallLogger)
        logging.getLogger("InstallationLogger")

    def tearDown(self):
        InstallLogger.DEFAULTFILEHANDLER = None

    def test_install(self):
        '''Test that the IPS image area is created'''
        tr_p5i = TransferP5IAttr("P5I transfer")
        tr_p5i.src = PKG_FULL_P5I
        tr_p5i.dst = IPS_IMG_DIR
        try:
            tr_p5i.execute(DRY_RUN)
        except Exception as err:
            self.fail(str(err))

if __name__ == '__main__':
    unittest.main()

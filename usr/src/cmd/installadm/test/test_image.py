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

import unittest
import os
import shutil
import tempfile
import osol_install.auto_install.image as image
import osol_install.auto_install.installadm_common as com
from osol_install.auto_install.image import InstalladmImage, ImageError


class TestInstalladmImage(unittest.TestCase):
    '''Tests for InstalladmImage'''

    @classmethod
    def setUpClass(cls):
        '''Class-level set up'''
        cls.webserver_docroot = com.WEBSERVER_DOCROOT
        com.WEBSERVER_DOCROOT = tempfile.mkdtemp(dir="/tmp")

    @classmethod
    def tearDownClass(cls):
        '''Class-level teardown'''
        if os.path.exists(com.WEBSERVER_DOCROOT):
            shutil.rmtree(com.WEBSERVER_DOCROOT)
        com.WEBSERVER_DOCROOT = cls.webserver_docroot

    def setUp(self):
        '''unit test set up'''
        self.tempdirname = tempfile.mkdtemp(dir="/tmp")

    def tearDown(self):
        '''teardown'''
        if os.path.exists(self.tempdirname):
            shutil.rmtree(self.tempdirname)

    def test_path(self):
        '''test image path property'''
        test_path = self.tempdirname
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.path, test_path)

    def test_arch(self):
        '''test image arch property'''
        test_path = self.tempdirname
        sun4v = os.path.join(test_path, "platform", "sun4v")
        os.makedirs(sun4v)
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.arch, "sparc")
        os.rmdir(sun4v)

        sun4u = os.path.join(test_path, "platform", "sun4u")
        os.makedirs(sun4u)
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.arch, "sparc")
        os.rmdir(sun4u)

        i86pc = os.path.join(test_path, "platform", "i86pc")
        os.makedirs(i86pc)
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.arch, "i386")
        os.rmdir(i86pc)

        amd64 = os.path.join(test_path, "platform", "amd64")
        os.makedirs(amd64)
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.arch, "i386")
        os.rmdir(amd64)

        myimage = InstalladmImage(test_path)
        self.assertRaises(ImageError, InstalladmImage.arch.fget, myimage)

    def test_type(self):
        '''test image type'''
        test_path = self.tempdirname
        image_info = os.path.join(test_path, '.image_info')

        # test that image_type gets right value
        with open(image_info, 'w') as info:
            info.write('IMAGE_TYPE=AI')
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.image_type, 'AI')
        os.remove(image_info)

        # test that image_type gets no value
        with open(image_info, 'w') as info:
            info.write('IMAGE_VERSION=3.0')
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.image_type, '')
        os.remove(image_info)

    def test_move(self):
        '''test image move'''
        test_path = self.tempdirname
        myimage = InstalladmImage(test_path)

        # create old symlink normally created by _prep_ai_webserver
        old_link = os.path.join(com.WEBSERVER_DOCROOT, test_path.lstrip("/"))
        old_link_parent = os.path.dirname(old_link)
        os.makedirs(old_link_parent)
        os.symlink(test_path, old_link)
        self.assertTrue(os.path.exists(old_link))

        # call the move function
        newtempdirname = tempfile.mkdtemp(dir="/tmp")
        newpath = myimage.move(newtempdirname)

        # Ensure image is moved and webserver symlinks are updated
        self.assertEqual(newpath, newtempdirname)
        self.assertEqual(myimage.path, newtempdirname)
        self.assertFalse(os.path.exists(old_link))
        new_link = os.path.join(com.WEBSERVER_DOCROOT,
                                newtempdirname.lstrip("/"))
        self.assertTrue(os.path.islink(new_link))
        shutil.rmtree(newtempdirname)

    def test_verify(self):
        '''test image verify'''
        tmpfile = tempfile.mktemp()
        open(tmpfile, 'w')
        self.assertTrue(os.path.exists(tmpfile))
        myimage = InstalladmImage(tmpfile)
        self.assertRaises(ImageError, myimage.verify)
        os.remove(tmpfile)

        test_path = self.tempdirname
        myimage = InstalladmImage(test_path)
        self.assertRaises(ImageError, myimage.verify)

        open(os.path.join(test_path, 'solaris.zlib'), 'w')
        myimage = InstalladmImage(test_path)

    def test_version(self):
        '''test image version property'''
        test_path = self.tempdirname
        myimage = InstalladmImage(test_path)
        image_info = os.path.join(test_path, '.image_info')

        # test that version gets right version
        with open(image_info, 'w') as info:
            info.write('IMAGE_VERSION=3.0')
        self.assertEqual(myimage.version, 3.0)
        os.remove(image_info)

        # test that no version falls back to 0.0
        open(image_info, 'w')
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.version, 0.0)
        os.remove(image_info)

        # test that bad version falls back to 0.0
        with open(image_info, 'w') as info:
            info.write('IMAGE_VERSION=abc123')
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.version, 0.0)
        os.remove(image_info)

        # test that version is saved, once set
        with open(image_info, 'w') as info:
            info.write('IMAGE_VERSION=3.0')
        myimage = InstalladmImage(test_path)
        self.assertEqual(myimage.version, 3.0)
        os.remove(image_info)
        with open(image_info, 'w') as info:
            info.write('IMAGE_VERSION=4.0')
        self.assertEqual(myimage.version, 3.0)


class TestIsIso(unittest.TestCase):
    '''Tests for is_iso'''

    def test_is_iso(self):
        '''test is_iso'''
        tmpfile = tempfile.mktemp()
        with open(tmpfile, 'w') as myfile:
            myfile.write('this is myfile text.')
        self.assertFalse(image.is_iso(tmpfile))
        os.remove(tmpfile)


if __name__ == '__main__':
    unittest.main()

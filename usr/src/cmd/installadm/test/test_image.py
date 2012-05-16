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

import errno
import os
import shutil
import tempfile
import unittest

import pkg.client.api
import pkg.client.imagetypes
import pkg.client.progress
import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.image as image
import osol_install.auto_install.installadm_common as com
from osol_install.auto_install.image import InstalladmImage, ImageError, \
    InstalladmPkgImage
import osol_install.auto_install.service_config as config
from solaris_install import PKG5_API_VERSION


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
        try:
            os.makedirs(old_link_parent)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
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

    def test_copy(self):
        '''test image copy'''
        # create image
        test_path = self.tempdirname
        open(os.path.join(test_path, 'solaris.zlib'), 'w')
        myfilepath = os.path.join(test_path, 'myfile')
        open(myfilepath, 'w')
        os.symlink('myfile', os.path.join(test_path, 'mysym'))
        os.makedirs(os.path.join(test_path, 'a/b/c'))
        myimage = InstalladmImage(test_path)

        # copy image and verify
        newimage = myimage.copy(prefix='mytest')
        newpath = newimage.path
        self.assertTrue(os.path.exists(os.path.join(newpath, 'solaris.zlib')))
        self.assertTrue(os.path.isdir(os.path.join(newpath, 'a/b/c')))
        self.assertTrue(os.path.islink(os.path.join(newpath, 'mysym')))
        self.assertTrue(os.path.exists(os.path.join(newpath, 'myfile')))
        self.assertEqual(os.readlink(os.path.join(newpath, 'mysym')), 'myfile')
        symname = os.path.join(com.WEBSERVER_DOCROOT, newpath.lstrip("/"))
        self.assertTrue(os.path.islink(symname))
        self.assertEqual(os.readlink(symname), newpath)
        shutil.rmtree(newpath)

    def test_delete(self):
        '''test image delete'''
        # create image
        test_path = self.tempdirname
        open(os.path.join(test_path, 'solaris.zlib'), 'w')
        self.assertTrue(os.path.exists(test_path))
        myfilepath = os.path.join(test_path, 'myfile')
        open(myfilepath, 'w')
        os.symlink('myfile', os.path.join(test_path, 'mysym'))
        os.makedirs(os.path.join(test_path, 'a/b/c'))
        myimage = InstalladmImage(test_path)
        webserver_link = os.path.join(com.WEBSERVER_DOCROOT,
                                test_path.lstrip("/"))
        try:
            os.makedirs(os.path.dirname(webserver_link))
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        os.symlink(test_path, webserver_link)

        # delete and verify
        myimage.delete()
        self.assertFalse(os.path.exists(test_path))
        self.assertFalse(os.path.exists(webserver_link))

    def test_is_pkg_based(self):
        '''test is_pkg_based'''
        # create and test non-pkg image
        test_path = self.tempdirname
        open(os.path.join(test_path, 'solaris.zlib'), 'w')
        self.assertTrue(os.path.exists(test_path))
        myimage = InstalladmPkgImage(test_path)
        self.assertFalse(myimage.is_pkg_based())

        # create and test pkg(5) image
        imagedir = tempfile.mkdtemp(dir="/tmp")
        tracker = pkg.client.progress.CommandLineProgressTracker()
        pkg.client.api.image_create('test_image', PKG5_API_VERSION,
            imagedir, pkg.client.imagetypes.IMG_USER, is_zone=False,
            progtrack=tracker)
        myimage = InstalladmPkgImage(imagedir)
        self.assertTrue(myimage.is_pkg_based())
        shutil.rmtree(imagedir)

    def test_check_fmri(self):
        '''test check_fmri'''
        # create pkg(5) image

        # create and test pkg(5) image
        imagedir = tempfile.mkdtemp(dir="/tmp")
        tracker = pkg.client.progress.CommandLineProgressTracker()
        pkg.client.api.ImageInterface(
            '/', PKG5_API_VERSION, tracker, None, 'installadm')

        pkgimage = pkg.client.api.image_create('installadm', PKG5_API_VERSION,
            imagedir, pkg.client.imagetypes.IMG_USER, is_zone=False,
            progtrack=tracker)

        myimage = InstalladmPkgImage(imagedir, pkg_image=pkgimage)
        myimage.check_fmri('pkgs:/solaris/foobarnotapackage')
        shutil.rmtree(imagedir)

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


class MockGetImageDir(object):
    '''Class for mock get_imagedir '''
    def __init__(self, path):
        self.imagedir = path
        
    def __call__(self):
        return self.imagedir


class TestModuleFunctions(unittest.TestCase):
    '''Tests for other module functions'''

    @classmethod
    def setUpClass(cls):
        '''Class-level set up'''
        cls.image_dir_path = com.IMAGE_DIR_PATH
        com.IMAGE_DIR_PATH = tempfile.mkdtemp(dir="/tmp")
        # aismf lines must follow com.IMAGE_DIR_PATH reassignment above
        cls.aismf_get_imagedir = aismf.get_imagedir
        aismf.get_imagedir = MockGetImageDir(com.IMAGE_DIR_PATH)
        cls.ai_service_dir_path = com.AI_SERVICE_DIR_PATH
        com.AI_SERVICE_DIR_PATH = tempfile.mkdtemp(dir="/tmp")
        cls.configai_service_dir_path = config.AI_SERVICE_DIR_PATH
        config.AI_SERVICE_DIR_PATH = com.AI_SERVICE_DIR_PATH

    @classmethod
    def tearDownClass(cls):
        '''Class-level teardown'''
        if os.path.exists(com.IMAGE_DIR_PATH):
            shutil.rmtree(com.IMAGE_DIR_PATH)
        com.IMAGE_DIR_PATH = cls.image_dir_path
        aismf.get_imagedir = cls.aismf_get_imagedir
        if os.path.exists(com.AI_SERVICE_DIR_PATH):
            shutil.rmtree(com.AI_SERVICE_DIR_PATH)
        com.AI_SERVICE_DIR_PATH = cls.ai_service_dir_path
        config.AI_SERVICE_DIR_PATH = cls.configai_service_dir_path

    def test_set_permissions(self):
        '''test set_permissions'''
        # save original umask
        orig_umask = os.umask(0022)

        os.umask(0066)
        imagedir = tempfile.mkdtemp(dir="/tmp")
        image.set_permissions(imagedir)
        mode = os.stat(imagedir).st_mode
        self.assertEqual(mode, 040755)
        os.rmdir(imagedir)

        # return umask to the original value
        os.umask(orig_umask)

    def test_check_imagepath(self):
        '''test check_imagepath'''
        # test for relative pathname
        self.assertRaises(ValueError, image.check_imagepath, 'my/relpath')
        self.assertRaises(ValueError, image.check_imagepath, './my/relpath')

        # test empty dir ok
        imagedir = tempfile.mkdtemp(dir="/tmp")
        image.check_imagepath(imagedir)
        os.rmdir(imagedir)

        # test non-empty dir fails
        imagedir = tempfile.mkdtemp(dir="/tmp")
        open(os.path.join(imagedir, 'myfile'), 'w')
        self.assertRaises(ValueError, image.check_imagepath, imagedir)
        shutil.rmtree(imagedir)

        # test valid image fails
        imagedir = tempfile.mkdtemp(dir="/tmp")
        open(os.path.join(imagedir, com.AI_NETIMAGE_REQUIRED_FILE), 'w')
        self.assertRaises(ValueError, image.check_imagepath, imagedir)
        shutil.rmtree(imagedir)

    def test_default_path_ok(self):
        '''test default_path_ok'''

        self.assertTrue(image.default_path_ok('this_is_my_service'))
        imgpath = os.path.join(com.IMAGE_DIR_PATH, 'this_is_my_service')
        os.makedirs(imgpath)
        self.assertFalse(image.default_path_ok('this_is_my_service'))
        os.rmdir(imgpath)

    def test_get_default_service_name(self):
        '''test get_default_service_name'''
        imagedir = tempfile.mkdtemp(dir="/tmp")
        svcname = 'my_svc_name'
        myimage = InstalladmImage(imagedir)
        image_info = os.path.join(imagedir, '.image_info')

        with open(image_info, 'w') as info:
            info.write('SERVICE_NAME=' + svcname)
        name = image.get_default_service_name(image=myimage, iso=True)
        self.assertEqual(name, svcname)

        # now try again, but have the default path exist
        defpath = os.path.join(com.IMAGE_DIR_PATH, svcname)
        os.makedirs(defpath)
        name = image.get_default_service_name(image=myimage, iso=True)
        self.assertEqual(name, svcname + '_1')

        # now have the servicename already exist
        svcdir = os.path.join(com.AI_SERVICE_DIR_PATH, svcname)
        svcdir2 = os.path.join(com.AI_SERVICE_DIR_PATH, svcname + '_1')
        try:
            os.makedirs(svcdir)
            os.makedirs(svcdir2)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        open(os.path.join(svcdir, '.config'), 'w')
        open(os.path.join(svcdir2, '.config'), 'w')
        name = image.get_default_service_name(image=myimage, iso=True)
        self.assertEqual(name, svcname + '_2')

        # invalid service name in image_info
        os.remove(image_info)
        with open(image_info, 'w') as info:
            info.write('SERVICE_NAME=my.invalid.name')
        name = image.get_default_service_name(image=myimage, iso=True)
        self.assertEqual(name, image.BASE_DEF_SVC_NAME + '_1')

        # Same thing, but default path exists
        os.mkdir(os.path.join(com.IMAGE_DIR_PATH,
                              image.BASE_DEF_SVC_NAME + '_1'))
        name = image.get_default_service_name(image=myimage, iso=True)
        self.assertEqual(name, image.BASE_DEF_SVC_NAME + '_2')

        shutil.rmtree(imagedir)


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

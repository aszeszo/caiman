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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

"""Transfer CPIO checkpoint Unit Tests"""

from osol_install.install_utils import dir_size
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.engine import InstallEngine
from solaris_install.logger import InstallLogger
from solaris_install.transfer.info import CPIOSpec
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.cpio import TransferCPIO
from solaris_install.transfer.cpio import TransferCPIOAttr
from osol_install.install_utils import file_size


from solaris_install.transfer.info import Args

import logging
import os
import shutil
import tempfile
import unittest


class TestCPIOFunctions(unittest.TestCase):
    TEST_DST_DIR = "/tmp/cpio_test_dir"
    TEST_SRC_DIR = "/"
    TEST_FILE_LIST_FILE = "/tmp/test_file_list"
    TEST_CONTENTS_LIST = []
    TEST_DIR_LIST_FILE = "/tmp/test_dir_list"
    TEST_SKIP_FILE_LIST_FILE = "/tmp/test_skip_file_list"
    TEST_DIR_EXCL_LIST_FILE = "/tmp/test_dir_excl_list"
    TEST_MEDIA_TRANSFORM = "/tmp/media_transform"

    def setUp(self):
        InstallEngine._instance = None

        default_log_dir = tempfile.mkdtemp(dir="/tmp", prefix="logging_")
        default_log = default_log_dir + "/install_log"
        InstallEngine(default_log)
        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache.volatile
        self.soft_node = Software("CPIO_Transfer", "CPIO")
        self.tr_node = CPIOSpec()
        self.soft_node.insert_children([self.tr_node])
        self.doc.insert_children([self.soft_node])
        self.tr_cpio = TransferCPIO("CPIO_Transfer")

    def tearDown(self):
        if os.access(self.TEST_DST_DIR, os.F_OK):
            shutil.rmtree(self.TEST_DST_DIR)
        if os.access(self.TEST_FILE_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_FILE_LIST_FILE)
        if os.access(self.TEST_DIR_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_DIR_LIST_FILE)
        if os.access(self.TEST_SKIP_FILE_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_SKIP_FILE_LIST_FILE)
        if os.access(self.TEST_DST_DIR, os.F_OK):
            os.unlink(self.TEST_DST_DIR)
        if os.access(self.TEST_MEDIA_TRANSFORM, os.F_OK):
            os.unlink(self.TEST_MEDIA_TRANSFORM)
        if os.access("/tmp/media_not_exec", os.F_OK):
            os.unlink("/tmp/media_not_exec")
        self.engine.data_object_cache.clear()
        self.doc = None
        self.engine = None
        self.soft_node = None
        self.tr_node = None
        self.tr_cpio = None
        InstallEngine._instance = None
        TEST_CONTENTS_LIST = []

        try:
            shutil.rmtree(os.path.dirname(
                InstallLogger.DEFAULTFILEHANDLER.baseFilename))
        except:
            pass

        logging.Logger.manager.loggerDict = {}
        InstallLogger.DEFAULTFILEHANDLER = None

    def test_software_type(self):
        self.assertTrue(self.soft_node.tran_type == "CPIO")

    def test_entire(self):
        '''Test transfer all of /etc/X11 to /rpool/cpio_test_dir succeeds'''
        # Set up the source
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = ["./"]

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cleanup_temp_files(self):
        '''Test the cleanup of the temporary files'''
        # Set up the source
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = ["./"]

        self.tr_cpio._parse_input()
        try:
            self.tr_cpio._cleanup_tmp_files()
        except Exception as err:
            self.fail(str(err))

    def test_cleanup_temp_files_nonexistent_file(self):
        '''Test cleanup temp files should check nonexistent'''
        self.tr_cpio._transfer_list = [{'action': 'install',
                                        'cpio_args': '-pdum',
                                        'contents': '/noexist'}]
        try:
            self.tr_cpio._cleanup_tmp_files()
        except Exception as err:
            self.fail(str(err))

    def test_cpio_w_file_list_file(self):
        '''Test copy of a file list file succeeds'''
        # Copy /bin/xclock and /bin/pv.sh to /rpool/cpio_test_dir
        # using a file list file as the contents souce

        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_FILE_LIST_FILE
        with open(self.TEST_FILE_LIST_FILE, 'w') as filehandle:
            filehandle.write("bin/xclock" + "\n")
            filehandle.write("bin/pv.sh" + "\n")

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_w_file_list(self):
        '''Test copy from a list succeeds'''
        # Copy /bin/xclock and /bin/pv.sh to /rpool/cpio_test_dir
        # using a file list as the contents source

        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.TEST_CONTENTS_LIST.append("bin/xclock")
        self.TEST_CONTENTS_LIST.append("bin/pv.sh")

        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_CONTENTS_LIST

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_w_dir_list_file(self):
        '''Test directory cpio copy succeeds'''
        # Copy all the directories and files from /etc/X11 and /etc/zones
        # to /rpool/cpio_test_dir using a file for the contents

        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_DIR_LIST_FILE
        with open(self.TEST_DIR_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/X11" + "\n")
            filehandle.write("etc/zones" + "\n")

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_w_dir_list(self):
        '''Test copying a list of directories and files succeeds'''
        # Copy all the directories and files from /etc/X11 and /etc/zones
        # to /rpool/cpio_test_dir using a list for the contents

        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        self.TEST_CONTENTS_LIST.append("bin/xclock")
        self.TEST_CONTENTS_LIST.append("bin/pv.sh")

        # The CPIO values that are specified
        self.TEST_CONTENTS_LIST.append("etc/X11")
        self.TEST_CONTENTS_LIST.append("etc/zones")
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_CONTENTS_LIST

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_non_default_args_set(self):
        '''Test copying a list of directories and files succeeds'''
        # Copy all the directories and files from /etc/X11 and /etc/zones
        # to /rpool/cpio_test_dir using a list for the contents

        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        args = Args({"cpio_args": "-n -d -pdum"})
        self.tr_node.insert_children([args])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        self.TEST_CONTENTS_LIST.append("bin/xclock")
        self.TEST_CONTENTS_LIST.append("bin/pv.sh")

        # The CPIO values that are specified
        self.TEST_CONTENTS_LIST.append("etc/X11")
        self.TEST_CONTENTS_LIST.append("etc/zones")
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_CONTENTS_LIST

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_w_empty_list(self):
        ''' Test that "empty contents list" scenario is handled'''
        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = []

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_cpio_no_contents(self):
        ''' Test that "no contents" scenario is handled'''
        # Set up the source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified - no contents
        self.tr_node.action = "install"

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_skip_file_list_file(self):
        '''Test the success of using skip_file_list'''
        # Copy all the files/dirs from /etc except for /etc/name_to_major
        # to /rpool/cpio_test_dir using a file for the contents

        # Set up the Source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_DIR_LIST_FILE

        # Create and insert a node for the files to be uninstalled
        self.tr_node2 = CPIOSpec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = self.TEST_SKIP_FILE_LIST_FILE
        self.soft_node.insert_children([self.tr_node2])

        # Populate the files
        with open(self.TEST_DIR_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/dhcp" + "\n")
        with open(self.TEST_SKIP_FILE_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/dhcp/duid" + "\n")
            filehandle.write("etc/dhcp/iaid" + "\n")

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_skip_file_list_list(self):
        '''Test the success of using skip_file_list'''
        # Copy all the files/dirs from /etc except for /etc/name_to_major
        # to /rpool/cpio_test_dir using a file for the contents

        # Set up the Source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        #self.tr_node.contents = self.TEST_DIR_LIST_FILE
        self.tr_node.contents = ["etc/dhcp"]

        # Create and insert a node for the files to be uninstalled
        self.tr_node2 = CPIOSpec()
        self.tr_node2.action = "uninstall"
        #self.tr_node2.contents = self.TEST_SKIP_FILE_LIST_FILE
        self.tr_node2.contents = ["etc/dhcp/duid", "etc/dhcp/iaid"]
        self.soft_node.insert_children([self.tr_node2])

         # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_dir_excl_list_file(self):
        '''Test the success of using directory exclusion'''
        # Copy all files/dirs from /etc/xdg except for anything under
        # /etc/xdg/menus to /rpool/cpio_test_dir using a file to
        # specify the contents

        # Set up the Source
        src = Source()
        path = Dir(self.TEST_SRC_DIR)
        src.insert_children([path])

        # Set up the destination
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        # Insert the source and dest into the Software node
        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = self.TEST_DIR_LIST_FILE

        # Populate the dir list file
        with open(self.TEST_DIR_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/xdg" + "\n")

        # Create and insert a node for the excluded files/dirs
        self.tr_node2 = CPIOSpec()
        self.tr_node2.action = "uninstall"
        self.tr_node2.contents = self.TEST_DIR_EXCL_LIST_FILE
        self.soft_node.insert_children([self.tr_node2])

        # Populate the excl file
        with open(self.TEST_DIR_EXCL_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/xdg/menus" + "\n")

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_src_not_exist(self):
        ''' Test that an error is raised when src doesn't exist.'''

        #Set up the source
        src = Source()
        path = Dir("/hello")
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_src_not_specified(self):
        ''' Test that an error is raised when src is not specified'''
        # Test that an error is raised.
        dst = Destination()
        dst_path = self.TEST_DST_DIR
        path = Dir(dst_path)
        dst.insert_children([path])

        self.soft_node.insert_children([dst])
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dst_not_specified(self):
        ''' Test that an error is raised when dst is not specified'''
        # Test that an error is raised.
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        self.soft_node.insert_children([src])
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_skip_file_list_file_not_valid(self):
        '''Test that an error is raised for invalid skip_file_list file'''
        # Set up the source
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "uninstall"
        self.tr_node.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dir_list_not_valid(self):
        '''Test that an error is raised for invalid dir_list file'''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = "/tmp/invalid_dir_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dir_excl_list_not_valid(self):
        '''Test that an error is raised for invalid dir_excl_list'''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "uninstall"
        self.tr_node.contents = "/tmp/invalid_dir_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_media_transform_not_valid(self):
        '''Test that an error is raised for invalid
           media_transform executable
        '''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "transform"
        self.tr_node.contents = "/tmp/invalid_transform_file"

        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_media_transform_not_executable(self):
        '''Test media_transform doesn't have correct permissions error
        '''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "transform"
        self.tr_node.contents = "/tmp/media_not_exec"
        open(self.tr_node.contents, 'w')
        os.chmod(self.tr_node.contents, 01666)
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=False)
        try:
            os.unlink(self.tr_node.contents)
        except (Exception):
            pass

    def test_progress_estimate_invalid_src(self):
        '''Test the progress estimate value when src is invalid.
        '''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "/bogus")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = ["./"]

        try:
            progress_estimate = self.tr_cpio.get_progress_estimate()
        except:
            self.assertTrue(False)
        self.assertTrue(progress_estimate == self.tr_cpio.DEFAULT_PROG_EST)

    def test_progress_estimate(self):
        '''Test that the progress estimate is the value expected.'''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = ["xinit"]

        try:
            progress_estimate = self.tr_cpio.get_progress_estimate()
        except Exception:
            self.assertTrue(False)
        size = 0

        size += file_size(os.path.join(src_path, "./"))
        for contents in self.tr_node.contents:
            size += file_size(os.path.join(src_path, contents))
            for root, subdirs, files in os.walk(os.path.join(src_path,
                                                            contents)):
                for subdir in subdirs:
                    size += file_size(os.path.join(root, subdir))
                for fname in files:
                    size += file_size(os.path.join(root, fname))

        # convert size to kilobytes
        size = size / 1024

        self.assertTrue(progress_estimate == \
                        int(float(size) / self.tr_cpio.DEFAULT_SIZE * \
                            self.tr_cpio.DEFAULT_PROG_EST))

    def test_get_size(self):
        '''Test that get_size returns an error when no source is set'''
        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])
        self.soft_node.insert_children([dst])
        self.assertRaises(IndexError, self.tr_cpio.get_size)

    def test_progress_estimate_with_size(self):
        '''Test progress estimate value when size is pre-calculated  exists
        '''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "install"
        self.tr_node.contents = ["./"]
        size_to_transfer = dir_size(src_path)
        self.tr_node.size = str(size_to_transfer)

        progress_estimate = self.tr_cpio.get_progress_estimate()
        expect_estimate = \
            int((float(size_to_transfer / 1024) / self.tr_cpio.DEFAULT_SIZE) \
                * self.tr_cpio.DEFAULT_PROG_EST)

        self.assertEqual(progress_estimate, expect_estimate)

    def test_media_transform(self):
        '''Test media transform functionality'''
        src = Source()
        src_path = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        path = Dir(src_path)
        src.insert_children([path])

        dst = Destination()
        path = Dir(self.TEST_DST_DIR)
        dst.insert_children([path])

        self.soft_node.insert_children([src, dst])

        # The CPIO values that are specified
        self.tr_node.action = "transform"
        self.tr_node.contents = self.TEST_MEDIA_TRANSFORM
        with open(self.TEST_MEDIA_TRANSFORM, 'w') as filehandle:
            filehandle.write("#!/usr/bin/python\n")
            filehandle.write("import os\n")
            mkdir_cmd = "os.mkdir('" + self.TEST_DST_DIR + "')"
            filehandle.write(mkdir_cmd + "\n")
            mkdir_cmd = "os.mkdir('" + os.path.join(self.TEST_DST_DIR,
                                                    "media") + "')"
            filehandle.write(mkdir_cmd)
        os.chmod(self.TEST_MEDIA_TRANSFORM, 0777)
        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_checkpoint_soft_node_match(self):
        '''The checkpoint and software node match
        '''
        try:
            tr_cpio = TransferCPIO("CPIO_Transfer")
        except Exception as err:
            self.fail(str(err))

    def test_checkpoint_soft_node_mismatch(self):
        '''The checkpoint and software node
           match as expected
        '''
        self.assertRaises(Exception, TransferCPIO, "CPIO Transfer")


class TestCPIOAttrFunctions(unittest.TestCase):
    TEST_DST_DIR = "/tmp/cpio_test_dir"
    TEST_SRC_DIR = "/"
    TEST_FILE_LIST_FILE = "/tmp/test_file_list"
    TEST_DIR_LIST_FILE = "/tmp/test_dir_list"
    TEST_SKIP_FILE_LIST_FILE = "/tmp/test_skip_file_list"
    TEST_DIR_EXCL_LIST_FILE = "/tmp/test_dir_excl_list"
    TEST_MEDIA_TRANSFORM = "/tmp/media_transform"

    def setUp(self):
        self.tr_cpio = TransferCPIOAttr("CPIO Transfer")
        logging.setLoggerClass(InstallLogger)
        logging.getLogger("InstallationLogger")

    def tearDown(self):
        if os.access(self.TEST_FILE_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_FILE_LIST_FILE)
        if os.access(self.TEST_DIR_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_DIR_LIST_FILE)
        if os.access(self.TEST_SKIP_FILE_LIST_FILE, os.F_OK):
            os.unlink(self.TEST_SKIP_FILE_LIST_FILE)
        if os.access(self.TEST_DST_DIR, os.F_OK):
            os.unlink(self.TEST_DST_DIR)
        if os.access(self.TEST_MEDIA_TRANSFORM, os.F_OK):
            os.unlink(self.TEST_MEDIA_TRANSFORM)
        if os.access("/tmp/media_not_exec", os.F_OK):
            os.unlink("/tmp/media_not_exec")
        self.tr_cpio = None
        InstallLogger.DEFAULTFILEHANDLER = None

    def test_entire(self):
        '''Test transfer of directories succeeds'''
        # Test transfer all of /etc/X11 to /rpool/cpio_test_dir succeeds
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "/etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = ["./"]

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_file_list_file(self):
        '''Test transfer of files in list file succeeds'''
        # Copy /bin/xclock and /bin/pv.sh to
        # using a file list file as the contents souce

        self.tr_cpio.src = self.TEST_SRC_DIR
        self.tr_cpio.dst = self.TEST_DST_DIR
        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = self.TEST_FILE_LIST_FILE
        with open(self.TEST_FILE_LIST_FILE, 'w') as filehandle:
            filehandle.write("bin/xclock" + "\n")
            filehandle.write("bin/pv.sh" + "\n")
            filehandle.write("bin/zip" + "\n")
            filehandle.write("bin/who" + "\n")
        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_file_list_list(self):
        '''Test transfer of files from a list succeeds'''
        # Copy /bin/xclock and /bin/pv.sh to
        # using a file list as the contents source

        self.tr_cpio.src = self.TEST_SRC_DIR
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = ["bin/xclock", "bin/pv.sh"]
        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_dir_list(self):
        '''Test transfer of directories from a list succeeds'''
        # Copy all the directories and files from /etc/X11
        # and /etc/zones to /rpool/cpio_test_dir using a list
        # for the contents

        self.tr_cpio.src = self.TEST_SRC_DIR
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.tr_cpio.dir_list = []
        self.tr_cpio.dir_list.append("etc/X11")
        self.tr_cpio.dir_list.append("etc/zones")

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = self.tr_cpio.dir_list

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_skip_file_list_file(self):
        '''Test uninstall of skip_file file list succeeds'''
        # Copy all the files/dirs from /etc except for
        # /etc/name_to_major to /rpool/cpio_test_dir using a
        # file for the contents

        self.tr_cpio.src = self.TEST_SRC_DIR
        self.tr_cpio.dst = self.TEST_DST_DIR

        self.tr_cpio.dir_list = self.TEST_DIR_LIST_FILE
        with open(self.TEST_DIR_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/dhcp" + "\n")

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = self.tr_cpio.dir_list

        self.tr_cpio.skip_file_list = self.TEST_SKIP_FILE_LIST_FILE
        with open(self.TEST_SKIP_FILE_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/duid/duid" + "\n")

        # The CPIO values that are specified for the skip_file_list
        self.tr_cpio.action = "uninstall"
        self.tr_cpio.contents = self.tr_cpio.skip_file_list

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_dir_excl_list(self):
        '''Test uninstall of excluded directories succeeds'''
        # Copy all files/dirs from /etc/xdg except for anything under
        # /etc/xdg/menus to /rpool/cpio_test_dir using a file to
        # specify the contents

        self.tr_cpio.src = self.TEST_SRC_DIR
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.tr_cpio.dir_list = self.TEST_DIR_LIST_FILE
        with open(self.TEST_DIR_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/xdg" + "\n")

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = self.tr_cpio.dir_list

        self.tr_cpio.dir_excl_list = self.TEST_DIR_EXCL_LIST_FILE
        with open(self.TEST_DIR_EXCL_LIST_FILE, 'w') as filehandle:
            filehandle.write("etc/xdg/menus" + "\n")

        # The CPIO values that are specified for the skip_file_list
        self.tr_cpio.action = "uninstall"
        self.tr_cpio.contents = self.tr_cpio.dir_excl_list

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

    def test_src_not_exist(self):
        ''' Test that an error is raised when src doesn't exist.'''
        self.tr_cpio.src = "/hello"
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_src_not_specified(self):
        ''' Test that an error is raised when src isn't specified'''
        self.tr_cpio.src = None
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dst_not_specified(self):
        ''' Test that an error is raised when dst is not specified'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_file_list_not_valid(self):
        '''Test that an error is raised for invalid file_list file'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_skip_file_list_not_valid(self):
        '''Test that an error is raised for invalid skip_file_list file'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "uninstall"
        self.tr_cpio.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dir_list_not_valid(self):
        '''Test that an error is raised for invalid dir_list file'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "install"
        self.tr_cpio.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_dir_excl_list_not_valid(self):
        '''Test that an error is raised for invalid dir_excl_list file'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "uninstall"
        self.tr_cpio.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_media_transform_not_valid(self):
        '''Test that an error is raised for invalid media_transform file'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR

        # The CPIO values that are specified
        self.tr_cpio.action = "transform"
        self.tr_cpio.contents = "/tmp/invalid_file"
        self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)

    def test_media_transform_not_executable(self):
        '''Test failure occurs when media transform is not executable
        '''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.tr_cpio.media_transform = "/tmp/media_not_exec"
        open(self.tr_cpio.media_transform, 'w')
        os.chmod(self.tr_cpio.media_transform, 01666)

        # The CPIO values that are specified
        self.tr_cpio.action = "transform"
        self.tr_cpio.contents = self.tr_cpio.media_transform
        self.tr_cpio.execute(dry_run=True)
        #self.assertRaises(Exception, self.tr_cpio.execute, dry_run=True)
        try:
            os.unlink(self.tr_cpio.media_transform)
        except Exception:
            pass

    def test_media_transform(self):
        '''Test media transform functionality'''
        self.tr_cpio.src = os.path.join(self.TEST_SRC_DIR, "etc/X11")
        self.tr_cpio.dst = self.TEST_DST_DIR
        self.tr_cpio.media_transform = self.TEST_MEDIA_TRANSFORM
        with open(self.TEST_MEDIA_TRANSFORM, 'w') as filehandle:
            filehandle.write("#!/usr/bin/python\n")
        os.chmod(self.TEST_MEDIA_TRANSFORM, 0777)

        # The CPIO values that are specified
        self.tr_cpio.action = "transform"
        self.tr_cpio.contents = self.tr_cpio.media_transform

        try:
            self.tr_cpio.execute(dry_run=True)
        except Exception as err:
            self.fail(str(err))

if __name__ == '__main__':
    unittest.main()

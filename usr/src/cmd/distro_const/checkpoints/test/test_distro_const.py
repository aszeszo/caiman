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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

""" test_distro_const
Test program for solaris_install/distro_const/__init__.py
"""

import logging
import os
import os.path
import sys
import tempfile
import time
import unittest

import solaris_install.distro_const as dc
import solaris_install.distro_const.distro_spec as dc_spec
import solaris_install.distro_const.execution_checkpoint as dc_exec

from lxml import etree

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.logical import Filesystem, Logical, Zpool


def clear_proxy():
    """ simple helper function to clear out the http proxy if it's set
    """
    if "http_proxy" in os.environ:
        del os.environ["http_proxy"]
    if "HTTP_PROXY" in os.environ:
        del os.environ["HTTP_PROXY"]

class TestLockfile(unittest.TestCase):
    """ test case to test the Lockfile context manager
    """

    def setUp(self):
        InstallEngine()

        # create a temporary file
        (self.fd, self.path) = tempfile.mkstemp()

        # immediately remove it for testing
        os.remove(self.path)

    def tearDown(self):
        InstallEngine._instance = None

        # ensure the file has been removed
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_simple_lockfile_create(self):
        """ test simple lockfile creation
        """
        with dc.Lockfile(self.path):
            self.assertTrue(os.path.exists(self.path))
        # verify the lockfile is gone
        self.assertFalse(os.path.exists(self.path))

    def test_two_instances(self):
        """ test invocation of two Lockfiles
        """
        with dc.Lockfile(self.path):
            # since Lockfile is a context manager, we can not use
            # assertRaises
            try:
                with dc.Lockfile(self.path):
                    pass
            except RuntimeError as err:
                self.assertTrue("An instance of distro_const" in str(err))
            else:
                self.fail("Lockfile was successfully created twice")
        # verify the lockfile is gone
        self.assertFalse(os.path.exists(self.path))


class TestDCScreenHandler(unittest.TestCase):
    """ test case for testing the DC specific stream handler
    """
    def setUp(self):
        # create a new logging instance
        self.logger = logging.getLogger("test")
        self.logger.setLevel(logging.DEBUG)

        (self.fh, self.filename) = tempfile.mkstemp(dir="/var/run")
        self.filehandler = logging.FileHandler(self.filename)
        fmt = "%(asctime)-11s %(message)s"
        datefmt = "%H:%M:%S"
        self.filehandler.setFormatter(dc.DCScreenHandler(fmt=fmt,
                                                         datefmt=datefmt))
        self.logger.addHandler(self.filehandler)

    def tearDown(self):
        os.close(self.fh)
        os.remove(self.filename)

    def test_simple_logging(self):
        """ log a simple message and verify it is in the log file
        """
        self.logger.debug("test entry")
        with open(self.filename, "r") as fh:
            self.assertTrue("test entry" in fh.read())

class TestParseArgs(unittest.TestCase):
    """ test case for testing the argument handler to distro_const.py
    """
    def setUp(self):
        self.orig_stderr = sys.stderr
        sys.stderr = sys.stdout

    def tearDown(self):
        sys.stderr = self.orig_stderr

    def test_missing_subcommand(self):
        """ omit the subcommand
        """
        args = ["-p", "foo", "-r", "bar", "manifest.xml"]
        self.assertRaises(SystemExit, dc.parse_args, args)

    def test_invalid_arg_zero(self):
        """ pass an invalid subcommand
        """
        args = ["bad_subcommand", "-p", "foo", "-r", "bar", "manifest.xml"]
        self.assertRaises(SystemExit, dc.parse_args, args)

    def test_too_many_arguments(self):
        """ pass too many arguments
        """
        args = ["build", "manifest1.xml", "manifest2.xml"]
        self.assertRaises(SystemExit, dc.parse_args, args)

    def test_no_arguments(self):
        """ pass zero arguments
        """
        self.assertRaises(SystemExit, dc.parse_args, [])

    def test_l_flag(self):
        """ verify the -l flag works
        """
        args = ["build", "-l", "manifest.xml"]
        try:
            dc.parse_args(args)
        # catch any exception and fail the test
        except:
            self.fail(" ".join(args) + " failed to parse correctly")

    def test_p_flag(self):
        """ verify the -p flag works
        """
        args = ["build", "-p", "checkpoint1", "manifest.xml"]
        try:
            dc.parse_args(args)
        # catch any exception and fail the test
        except:
            self.fail(" ".join(args) + " failed to parse correctly")

    def test_r_flag(self):
        """ verify the -r flag works
        """
        args = ["build", "-r", "checkpoint1", "manifest.xml"]
        try:
            dc.parse_args(args)
        # catch any exception and fail the test
        except:
            self.fail(" ".join(args) + " failed to parse correctly")

    def test_r_and_p_flags(self):
        """ verify the -r and -p flags work together
        """
        args = ["build", "-r", "checkpoint1", "-p", "checkpoint2",
                "manifest.xml"]
        try:
            dc.parse_args(args)
        # catch any exception and fail the test
        except:
            self.fail(" ".join(args) + " failed to parse correctly")


class TestStreamHandler(unittest.TestCase):
    """ test case for setting up the StreamHandler
    """
    def setUp(self):
        self.eng = InstallEngine()
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

    def tearDown(self):
        InstallEngine._instance = None
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                self.logger.removeHandler(handler)

    def test_nonverbose(self):
        """ verify the log level of the StreamHander is INFO
        """
        verbose = False
        list_cps = True
        dc.set_stream_handler(self.logger, list_cps, verbose)
        
        # the StreamHandler will be the last entry in the handlers list
        self.assertTrue(self.logger.handlers[-1].level == logging.INFO)

    def test_verbose(self):
        """ verify the log level of the StreamHander is DEBUG
        """
        verbose = True
        list_cps = True
        dc.set_stream_handler(self.logger, list_cps, verbose)
        
        # the StreamHandler will be the last entry in the handlers list
        self.assertTrue(self.logger.handlers[-1].level == logging.DEBUG)


class TestRegisterCheckpoints(unittest.TestCase):
    """ test case for testing the register_checkpoints function
    """
    def setUp(self):
        self.eng = InstallEngine()
        self.doc = self.eng.data_object_cache

        # create DOC objects with 2 checkpoints
        self.distro = dc_spec.Distro("distro")
        self.execution = dc_exec.Execution("execution")
        self.execution.stop_on_error = "True"
        
        # set the 'checkpoints' to use the unittest module and TestCase class
        self.cp1 = dc_exec.Checkpoint("checkpoint 1")
        self.cp1.mod_path = "unittest"
        self.cp1.checkpoint_class = "TestCase"
        self.cp2 = dc_exec.Checkpoint("checkpoint 2")
        self.cp2.mod_path = "unittest"
        self.cp2.checkpoint_class = "TestCase"

        # create a logger
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

    def tearDown(self):
        InstallEngine._instance = None

    def test_basic_registration(self):
        """ simple registration of two checkpoints
        """
        self.execution.insert_children([self.cp1, self.cp2])
        self.distro.insert_children(self.execution)
        self.doc.volatile.insert_children(self.distro)

        cps = dc.register_checkpoints(self.logger)
        self.assertTrue(len(cps) == 2)

    def test_missing_execution_node(self):
        """ test a missing execution node
        """
        self.doc.volatile.insert_children(self.distro)
        self.assertRaises(RuntimeError, dc.register_checkpoints, self.logger)

    def test_missing_checkpoints(self):
        """ test missing checkpoints
        """
        self.distro.insert_children(self.execution)
        self.doc.volatile.insert_children(self.distro)
        self.assertRaises(RuntimeError, dc.register_checkpoints, self.logger)


class TestParseManifest(unittest.TestCase):
    """ test case for testing the parse_manifest function
    """
    def setUp(self):
        # create a basic manifest
        self.fh, self.path = tempfile.mkstemp(suffix=".xml")

        # create a simple, valid manifest for DC
        self.root = etree.Element("dc")
        distro = etree.SubElement(self.root, "distro")
        distro.set("name", "test")
        distro.set("add_timestamp", "false")
        
        # distro_spec section
        ds = etree.SubElement(distro, "distro_spec")
        ip = etree.SubElement(ds, "img_params")
        etree.SubElement(ip, "media_im")

        # target section
        target = etree.SubElement(distro, "target")
        zp = etree.SubElement(target, "zpool")
        zp.set("action", "use_existing")
        zp.set("name", "rpool")
        fs = etree.SubElement(zp, "filesystem")
        fs.set("name", "rpool/test")
        fs.set("action", "preserve")

        # execution section.  Create 1 checkpoint
        execution = etree.SubElement(distro, "execution")
        execution.set("stop_on_error", "true")
        cp = etree.SubElement(execution, "checkpoint")
        cp.set("name", "checkpoint")
        cp.set("desc", "test checkpoint")
        cp.set("mod_path", "unittest")
        cp.set("checkpoint_class", "TestCase")

        # instantiate the engine
        self.eng = InstallEngine()

    def tearDown(self):
        os.close(self.fh)
        os.remove(self.path)
        InstallEngine._instance = None

    def test_parse_manifest(self):
        """ test parsing of a simple manifest
        """
        xmltree = etree.tostring(self.root, pretty_print=True)
        with open(self.path, "w+") as fh:
            fh.write(xmltree)

        dc.parse_manifest(self.path)
        doc = self.eng.data_object_cache

        # verify the doc's volatile tree is populated
        self.assertTrue(doc.volatile.has_children)
        self.assertTrue(doc.volatile.get_descendants(class_type=Target))
        self.assertTrue(doc.volatile.get_descendants(
            class_type=dc_exec.Execution))
        self.assertTrue(doc.volatile.get_descendants(
            class_type=dc_exec.Checkpoint))


class TestValidateTarget(unittest.TestCase):
    """ test case for testing the validate_target function
    """

    def setUp(self):
        # instantiate the engine
        self.eng = InstallEngine()
        self.doc = self.eng.data_object_cache

        # create a Target DataObjects for later insertion
        self.target = Target("target")
        self.logical = Logical("logical")
        self.target.insert_children(self.logical)

    def tearDown(self):
        InstallEngine._instance = None

    def test_two_filesystems(self):
        """ test to make sure two Filesystem objects correctly errors
        """
        # create a basic zpool object
        zpool = Zpool("rpool")
        zpool.action = "use_existing"

        # create two filesystem objects
        fs1 = Filesystem("rpool/test1")
        fs2 = Filesystem("rpool/test2")

        # create the DOC structure
        self.logical.insert_children(zpool)
        zpool.insert_children([fs1, fs2])

        self.doc.volatile.insert_children(self.target)

        self.assertRaises(RuntimeError, dc.validate_target)

    def test_delete_filesystem(self):
        """ test to make sure the delete action correctly errors
        """
        # create a basic zpool object
        zpool = Zpool("rpool")
        zpool.action = "use_existing"

        # create one filesystem object with an action of delete
        fs = Filesystem("rpool/test1")
        fs.action = "delete"

        # create the DOC structure
        self.logical.insert_children(zpool)
        zpool.insert_children(fs)

        self.doc.volatile.insert_children(self.target)

        self.assertRaises(RuntimeError, dc.validate_target)

    def test_two_zpools(self):
        """ test to make sure two Zpool objects correctly errors
        """
        # create two zpool objects
        zpool1 = Zpool("rpool")
        zpool1.action = "use_existing"
        zpool2 = Zpool("rpool-two")
        zpool2.action = "use_existing"

        # create one filesystem object
        fs1 = Filesystem("rpool/test1")

        # create the DOC structure
        self.logical.insert_children([zpool1, zpool2])
        zpool1.insert_children(fs1)

        self.doc.volatile.insert_children(self.target)

        self.assertRaises(RuntimeError, dc.validate_target)

    def test_delete_zpool(self):
        """ test to make sure the delete action for zpools correctly errors
        """
        # create a basic zpool object with an action of delete
        zpool = Zpool("rpool")
        zpool.action = "delete"

        # create one filesystem object
        fs = Filesystem("rpool/test1")

        # create the DOC structure
        self.logical.insert_children(zpool)
        zpool.insert_children(fs)

        self.doc.volatile.insert_children(self.target)

        self.assertRaises(RuntimeError, dc.validate_target)

    def test_create_root_pool(self):
        """ test to make sure the create action on the bootfs correctly errors
        """
        # create a basic zpool object with an action of create
        zpool = Zpool("rpool")
        zpool.action = "create"

        # create one filesystem object
        fs = Filesystem("rpool/test1")

        # create the DOC structure
        self.logical.insert_children(zpool)
        zpool.insert_children(fs)

        self.doc.volatile.insert_children(self.target)

        self.assertRaises(RuntimeError, dc.validate_target)

    def test_simple_target(self):
        """ test to make sure a simple target validates correctly.  No actual
        ZFS code is executed here.
        """
        # create a basic zpool object
        zpool = Zpool("rpool")
        zpool.action = "use_existing"

        # create one filesystem object
        fs = Filesystem("rpool/test1")
        fs.dataset_path = fs.name

        # create the DOC structure
        self.logical.insert_children(zpool)
        zpool.insert_children(fs)

        self.doc.volatile.insert_children(self.target)

        zpool_name, dataset, action, dataset_mp = dc.validate_target()
        self.assertTrue(zpool_name == zpool.name)
        self.assertTrue(dataset == "rpool/test1")
        self.assertTrue(action == "create")
        # the mountpoint will be None since the Filesystem.from_xml() method
        # is not called to determine the actual mountpoint
        self.assertFalse(dataset_mp)


class TestSetHTTPProxy(unittest.TestCase):
    """ test case for testing the set_http_proxy function
    """

    def setUp(self):
        self.eng = InstallEngine()
        self.doc = self.eng.data_object_cache

        self.distro = dc_spec.Distro("distro")
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

        # ensure there's no proxy left over
        clear_proxy()

    def tearDown(self):
        InstallEngine._instance = None
        clear_proxy()


    def test_http_proxy(self):
        """ test setting the proxy
        """
        self.distro.http_proxy = "http://dc/test/proxy"
        self.doc.volatile.insert_children(self.distro)
        dc.dc_set_http_proxy(self.logger)
        self.assertTrue("http_proxy" in os.environ)
        self.assertTrue("HTTP_PROXY" in os.environ)

    def test_no_distro_object(self):
        """ test not having a distro object in the DOC (and therefor no
        http_proxy entry
        """
        dc.dc_set_http_proxy(self.logger)
        self.assertFalse("http_proxy" in os.environ)
        self.assertFalse("HTTP_PROXY" in os.environ)

    def test_no_proxy_set(self):
        """ test having a distro object, but no proxy set
        """
        self.doc.volatile.insert_children(self.distro)
        dc.dc_set_http_proxy(self.logger)
        self.assertFalse("http_proxy" in os.environ)
        self.assertFalse("HTTP_PROXY" in os.environ)


class TestListCheckpoints(unittest.TestCase):
    """ test case for testing the list_checkpoints function
    """
    def setUp(self):
        self.eng = InstallEngine()
        self.doc = self.eng.data_object_cache

        # create DOC objects with 2 checkpoints
        self.distro = dc_spec.Distro("distro")
        self.execution = dc_exec.Execution("execution")
        self.execution.stop_on_error = "True"
        
        # set the 'checkpoints' to use the unittest module and TestCase class
        self.cp1 = dc_exec.Checkpoint("checkpoint 1")
        self.cp1.mod_path = "unittest"
        self.cp1.checkpoint_class = "TestCase"
        self.cp2 = dc_exec.Checkpoint("checkpoint 2")
        self.cp2.mod_path = "unittest"
        self.cp2.checkpoint_class = "TestCase"

        # create a logger
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

    def tearDown(self):
        InstallEngine._instance = None

    def test_list_checkpoints(self):
        """ test listing out all registered checkpoints.  Since the output goes
        to the stream log, trap on any exception and fail if anything goes
        wrong
        """
        self.execution.insert_children([self.cp1, self.cp2])
        self.distro.insert_children(self.execution)
        self.doc.volatile.insert_children(self.distro)
        try:
            dc.list_checkpoints(self.logger)
        except Exception as err:
            self.fail(str(err))

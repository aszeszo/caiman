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

""" test_custom_script

 Test program for custom_script module
"""

import inspect
import logging
import os
import unittest

import osol_install.errsvc as errsvc

from tempfile import mktemp

from lxml import etree

from solaris_install.data_object import DataObject
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const import configuration
from solaris_install.distro_const import execution_checkpoint
from solaris_install.distro_const import distro_spec
from solaris_install.distro_const.checkpoints.custom_script import CustomScript
from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance, reset_engine
from solaris_install.logger import InstallLogger


# register all the DataObject classes with the DOC
for mod in [configuration, distro_spec, execution_checkpoint]:
    for name, value in inspect.getmembers(mod, inspect.isclass):
        if issubclass(value, DataObject):
            DataObjectCache.register_class(value)

class SimpleDataObject(DataObject):
    """Simple DataObject for testing"""

    def __init__(self, name, value1="Default1", value2="Defaut2",
        value3="Default3"):

        super(SimpleDataObject, self).__init__(name)
        self.value1 = value1
        self.value2 = value2
        self.value3 = value3

    @classmethod
    def can_handle(cls, xml_node):
        """Doesn't support XML Import"""
        return False

    @classmethod
    def from_xml(cls, xml_node):
        """Doesn't support XML Import"""
        return None

    def to_xml(self):
        """Doesn't support XML Export"""
        return None

    def __repr__(self):
        return "%s: name = %s; value1 = %s; value2 = %s; value 3 = %s" % \
            (self.__class__.__name__, self.name, self.value1, self.value2,
             self.value3)


class TestUserScript(unittest.TestCase):
    """ simple test case for execution of custom_script
    """

    logging.setLoggerClass(InstallLogger)
    test_dataset = "/rpool/dc_test2"

    def __init__(self, methodName='runTest'):
        super(TestUserScript, self).__init__(methodName)
        self.engine = None

    def __run_checkpoint_xml(self, test_xml, expect_fail=False):
        """Given a XML extract, feed into Engine, and execute it"""
        # Ensure that there are no previous errors in the errsvc.
        errsvc.clear_error_list()
        # Create XML DOM from string
        xml_tree = etree.fromstring(test_xml)
        self.doc.import_from_manifest_xml(xml_tree, volatile=True)
        # Register checkpoints
        for checkpoint in self.doc.find_path("//execution/[@DataObject]"):
            self.engine.register_checkpoint(
                checkpoint.name,
                checkpoint.mod_path,
                checkpoint.checkpoint_class,
                loglevel=checkpoint.log_level,
                args=checkpoint.args)

        self.engine.execute_checkpoints()

        errs = errsvc.get_errors_by_mod_id("custom-script")

        if expect_fail:
            if errs is None:
                self.fail("Expected failure when running checkpoint.")
        else:
            if errs is not None and len(errs) > 0:
                self.fail(str(errs[0]))

    def setUp(self):
        """setup logging and a doc object
        """
        # Init engine, if not already done.
        if self.engine is not None:
            reset_engine(self.engine)

        self.engine = get_new_engine_instance()

        self.custom_script = CustomScript("Custom Script", "echo Hello")

        self.doc = self.engine.data_object_cache

        self.dict_parent = SimpleDataObject("dicts")

        dd = DataObjectDict("TestDict", dict())
        dd.data_dict['key'] = 1
        self.dict_parent.insert_children(dd)

        dd = DataObjectDict("TestDict2", dict())
        dd.data_dict['key'] = 2
        self.dict_parent.insert_children(dd)

        self.doc.volatile.insert_children(self.dict_parent)

    def tearDown(self):
        """teardown the doc object, and reset engine again.
        """
        self.doc.volatile.delete_children()
        if self.engine is not None:
            reset_engine(self.engine)

    def test_custom_script_execute(self):
        """Test that execution actually works.

        Only creates a file in /tmp and reads it back in.
        """

        tfile = mktemp(prefix="custom_script-")

        self.custom_script.command = \
            "/bin/echo value1=%{//dicts/TestDict.key}" \
            " value2=%{//dicts/TestDict2.key} > " + tfile

        self.custom_script.execute(dry_run=False)

        try:
            f = open(tfile, "r")
            line = f.readline()
            self.assertEqual(line.strip(), "value1=1 value2=2")
            f.close()
        except IOError, e:
            self.fail("Command didn't create file! " + str(e))
        else:
            # Be sure to remove the file.
            if os.path.exists(tfile):
                os.unlink(tfile)

    def test_execute_fail(self):
        """Test XML and execute for failed run."""
        test_xml = """
        <dc>
          <distro name="test">
            <execution stop_on_error="false">
                <checkpoint name="custom-script"
                 mod_path=
                   "solaris_install/distro_const/checkpoints/custom_script"
                 checkpoint_class="CustomScript">
                        <args>/fails/non_existant_script.sh script_args</args>
                </checkpoint>
            </execution>
          </distro>
        </dc>
        """

        self.__run_checkpoint_xml(test_xml, expect_fail=True)

    def test_execute_works(self):
        """Test XML and execute for successful run."""
        test_xml = """
        <dc>
          <distro name="test">
            <execution stop_on_error="false">
                <checkpoint name="custom-script"
                 mod_path=
                   "solaris_install/distro_const/checkpoints/custom_script"
                 checkpoint_class="CustomScript">
                        <args>/usr/bin/echo hello</args>
                </checkpoint>
            </execution>
          </distro>
        </dc>
        """

        self.__run_checkpoint_xml(test_xml, expect_fail=False)

    def test_execute_works_with_split_lines(self):
        """Test custom script executes with command over many lines. """
        test_xml = """
        <dc>
          <distro name="test">
            <execution stop_on_error="false">
                <checkpoint name="custom-script"
                 mod_path=
                   "solaris_install/distro_const/checkpoints/custom_script"
                 checkpoint_class="CustomScript">
                        <args>/usr/bin/echo
                        hello
                        this
                        is
                        a
                        test
                        </args>
                </checkpoint>
            </execution>
          </distro>
        </dc>
        """

        self.__run_checkpoint_xml(test_xml, expect_fail=False)

    def test_execute_works_with_doc_references(self):
        """Test custom script executes with command over many lines. """
        test_xml = """
        <dc>
          <distro name="test">
            <execution stop_on_error="false">
                <checkpoint name="custom-script"
                 mod_path=
                   "solaris_install/distro_const/checkpoints/custom_script"
                 checkpoint_class="CustomScript">
                        <args>/usr/bin/echo
                        allvalues=%{//dicts//.key}
                        value1=%{//dicts/TestDict.key}
                        value2=%{//dicts/TestDict2.key}
                        </args>
                </checkpoint>
            </execution>
          </distro>
        </dc>
        """

        self.__run_checkpoint_xml(test_xml, expect_fail=False)

    def test_execute_fails_with_invalid_doc_references(self):
        """Test custom script executes with command over many lines. """
        test_xml = """
        <dc>
          <distro name="test">
            <execution stop_on_error="false">
                <checkpoint name="custom-script"
                 mod_path=
                   "solaris_install/distro_const/checkpoints/custom_script"
                 checkpoint_class="CustomScript">
                        <args>/usr/bin/echo
                        allvalues=%{//dicts/NoSuchValue.key}
                        </args>
                </checkpoint>
            </execution>
          </distro>
        </dc>
        """

        self.__run_checkpoint_xml(test_xml, expect_fail=True)

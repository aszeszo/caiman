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
"""Test the js2ai.py file"""

import logging
import os
import pwd
import shutil
import sys
import tempfile
import traceback
import unittest

import solaris_install.js2ai as js2ai

from lxml import etree
from StringIO import StringIO
from solaris_install.js2ai.common import pretty_print
from solaris_install.js2ai.common import write_xml_data
from solaris_install.js2ai.default_xml import XMLDefaultData


TEST_SIMPLE_PROFILE_CONFIG = \
"""<?xml version="1.0" encoding="UTF-8"?>
<!--

  Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.

-->
<!DOCTYPE auto_install SYSTEM "file:///usr/share/auto_install/ai.dtd">
<auto_install>
  <ai_instance>
    <target>
        <logical nodump="true" noswap="false">
        <zpool is_root="true" name="rpool">
          <vdev name="rpool_vdev" redundancy="none"/>
        </zpool>
      </logical>
    </target>
    <software type="IPS">
      <source>
        <publisher name="solaris">
          <origin name="http://pkg.oracle.com/solaris/release"/>
        </publisher>
      </source>
    </software>
  </ai_instance>
</auto_install>
"""


def fetch_log(logfile):
    """Return the contents of the logfile"""
    lines = []
    try:
        with open(logfile, "r") as fhandle:
            lines = fhandle.readlines()
    except IOError:
        # The log file may not exit
        pass
    if len(lines) == 0:
        lbuffer = "LOG: EMPTY"
    else:
        lbuffer = "LOG:\n"
        for line in lines:
            lbuffer += line
    return lbuffer


def failure_report(report, logfile):
    """Build a buffer with the data necessary to anaylsis the failure"""
    # Read the log file
    return  "Conversion Report:\n" + str(report) + \
            "\n\n" + fetch_log(logfile)


def exit_code_report(exit_code, expected_code, logfile):
    """Generate report for exit code tests"""
    lbuffer = "Expected exit code %d got exit code: %d\n" % \
        (expected_code, exit_code)
    lbuffer += fetch_log(logfile)
    return lbuffer


def exception_report(err, logfile):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    lbuffer = "Unexpected Exception: %s\n" % err
    lines_tupel = repr(traceback.format_tb(exc_traceback))
    lbuffer += lines_tupel
    lbuffer += "\n\n"
    lbuffer += fetch_log(logfile)
    return lbuffer


def profile_failure_report(tree, report, logfile):
    """Generate profile failure report"""
    rbuffer = "\nResulting XML Tree: "
    if tree is None:
        rbuffer += "No data available"
    else:
        rbuffer += "\n\n" + pretty_print(tree)
    rbuffer += "\n\n\n" + failure_report(report, logfile)
    return rbuffer


class Test_ConversionReport(unittest.TestCase):
    """Test conversion report class"""

    def test_ConversionReport_wNoErrors(self):
        """Tests the most basic case where there are no errors."""
        conv_report = js2ai.ConversionReport()
        self.assertEquals(conv_report.process_errors, 0)
        self.assertEquals(conv_report.conversion_errors, 0)
        self.assertEquals(conv_report.unsupported_items, 0)
        self.assertEquals(conv_report.validation_errors, 0)
        self.assertEquals(conv_report.has_errors(), False)

    def test_ConversionReport_wProcessError(self):
        """Tests ConversionReport with 1 error and 3 None values"""
        conv_report = js2ai.ConversionReport(1, None, None, None)
        self.assertEquals(conv_report.process_errors, 1)
        self.assertEquals(conv_report.conversion_errors, None)
        self.assertEquals(conv_report.unsupported_items, None)
        self.assertEquals(conv_report.validation_errors, None)
        self.assertEquals(conv_report.has_errors(), True)

    def test_ConversionReport_wErrors(self):
        """Test setting values on conversion report via constructor"""
        conv_report = js2ai.ConversionReport(4, 0, 0, 0)
        self.assertEquals(conv_report.process_errors, 4)
        self.assertEquals(conv_report.conversion_errors, 0)
        self.assertEquals(conv_report.unsupported_items, 0)
        self.assertEquals(conv_report.validation_errors, 0)
        self.assertEquals(conv_report.has_errors(), True)

        conv_report.add_conversion_error()
        self.assertEquals(conv_report.conversion_errors, 1)

        conv_report.add_unsupported_item()
        self.assertEquals(conv_report.unsupported_items, 1)

        conv_report.add_validation_error()
        self.assertEquals(conv_report.validation_errors, 1)

        self.assertEquals(conv_report.has_errors(), True)

    def test_ConversionReport_setErrors(self):
        """Test setting values on conversion report via setXXX methods"""
        conv_report = js2ai.ConversionReport()
        conv_report.process_errors = 3
        conv_report.conversion_errors = 2
        conv_report.unsupported_items = 0
        conv_report.validation_errors = 0

        self.assertEquals(conv_report.process_errors, 3)
        self.assertEquals(conv_report.conversion_errors, 2)
        self.assertEquals(conv_report.unsupported_items, 0)
        self.assertEquals(conv_report.validation_errors, 0)


class Test_RuleRead_wProcessErrs1(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Perform test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules files
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            # This rule should fail with one process error\n"
            # since it doesn't follow the min setup of
            # key value begin_script profile end_script
            fhandle.write("any - - - ")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_invalid_format(self):
        """Test to ensure that read_rules() catches invalid format"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_RuleRead_wProcessErrs2(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Setup for test run"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            # This rule should fail with one process error
            # since the referenced profile does not exist
            fhandle.write("hostname sample_host    -       host_class")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_with_non_existing_profile(self):
        """Test read rules catches failure due to non existing profile file"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_RuleRead_wProcessErrs3(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None
    log_file = None

    def setUp(self):
        """Setup for test run"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            # This rule should fail with one process error
            # since the rule line is incomplete
            fhandle.write("arch sparc && \\\n")
            fhandle.write("    disksize c0t3d0 400-600 && \\\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_incomplete_line(self):
        """Test to ensure that read_rules() catches incomplete line"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_RuleRead_wProcessErrs4(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            # This rule should fail with one process error
            # since the rule line is incomplete
            fhandle.write("arch sparc && disksize c0t3d0 400-600 && \\\n")

    def tearDown(self):
        """Test clean up"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_incomplete_line(self):
        """Test to ensure that read_rules() catches incomplete line"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_RuleRead_wProcessErrs5(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            # This rule should fail with one process error
            # since it doesn't follow the min setup of
            # key value begin_script profile end_script
            fhandle.write("any\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_insufficient_args(self):
        """Test to ensure that read_rules() catches insufficient args"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_ProfileRead_wProcessErrs(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None
    profile_name = "profile1"

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the profile file
        filename = os.path.join(self.working_dir, self.profile_name)
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            fhandle.write("package SUNWCall\n")
            fhandle.write("package\n")
            fhandle.write("package SUNWCuser\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_profile_with_one_failure(self):
        """ Test to ensure that read_profile() catches failure in profile file
        """
        js2ai.logger_setup(self.working_dir)
        profile_data = js2ai.read_profile(self.working_dir,
                                                self.profile_name, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.process_errors, 1,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))
        with open(js2ai.logfile_name, 'r') as fhandle:
            lines = fhandle.readlines()
        self.assertEquals(len(lines), 1,
                          failure_report(report, js2ai.logfile_name))


class Test_ProcessRules(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        self.xml_data_obj = XMLDefaultData(None)
        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("# The following rule matches any system:\n\n")
            fhandle.write("arch i386   -   any_machine  -\n")

        # Create the profile file
        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            fhandle.write("boot_device c2t0d0s0\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_process_rules(self):
        """Test to ensure process_rules() and process_profiles() works as
        expected.  The rules/profiles used for this test contain no errors

        """
        rp = js2ai.process_rule(self.working_dir, self.working_dir,
                                self.xml_data_obj, True, True, False)
        ruleFileData = rp.rules_file_data
        report = ruleFileData.conversion_report
        self.assertEquals(report.process_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          failure_report(report, js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 0,
                          failure_report(report, js2ai.logfile_name))

        profiles = rp.defined_profiles
        for key in profiles.iterkeys():
            profile_data = profiles[key]
            self.assertNotEquals(profile_data, None)
            report = profile_data.conversion_report
            self.assertEquals(report.process_errors, 0,
                              failure_report(report, js2ai.logfile_name))
            self.assertEquals(report.conversion_errors, 0,
                              failure_report(report, js2ai.logfile_name))
            self.assertEquals(report.unsupported_items, 0,
                              failure_report(report, js2ai.logfile_name))


class Test_ReadRulesComplex1(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("karch abc && memsize 64-128 begin "
                          "basic_prof end\n\n")

        # Create the profile file
        filename = os.path.join(self.working_dir, "basic_prof")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        keyword1 value1 && keyword2 value2 ....

        """
        rfd = js2ai.read_rules(self.working_dir, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "begin")
        self.assertEquals(defined_rule.end_script, "end")
        self.assertEquals(defined_rule.profile_name, "basic_prof")
        self.assertEquals(key_value.key, "karch", key_value)
        self.assertEquals(key_value.values[0], "abc", key_value)
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "memsize", key_value)
        self.assertEquals(key_value.values[0], "64-128", key_value)

        rp = js2ai.ProcessedData(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex2(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("karch abc && \\\n")
            fhandle.write("memsize 64-128 begin basic_prof end\n\n")

        # Create the profile file
        filename = os.path.join(self.working_dir, "basic_prof")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        keyword1 value1 && \
        keyword2 value2 ....

        """
        rfd = js2ai.read_rules(self.working_dir, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "begin", defined_rule)
        self.assertEquals(defined_rule.end_script, "end", defined_rule)
        self.assertEquals(defined_rule.profile_name, "basic_prof",
                          defined_rule)
        self.assertEquals(key_value.key, "karch", key_value)
        self.assertEquals(key_value.values[0], "abc", key_value)
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "memsize", key_value)
        self.assertEquals(key_value.values[0], "64-128", key_value)

        rp = js2ai.ProcessedData(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex3(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("arch sparc && disksize c0t3d0 400-600 \\\n")
            fhandle.write("\\\n")
            fhandle.write("&& installed c0t3d0s0 solaris_2.1 - profile1 "
                          "- #test\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        arch sparc && disksize c0t3d0 400-600 \
        \
        && installed c0t3d0s0 solaris_2.1 - profile1  - #test

        """
        rfd = js2ai.read_rules(self.working_dir, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "-", defined_rule)
        self.assertEquals(defined_rule.end_script, "-", defined_rule)
        self.assertEquals(defined_rule.profile_name, "profile1", defined_rule)
        self.assertEquals(key_value.key, "arch", key_value)
        self.assertEquals(key_value.values[0], "sparc", key_value)

        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "disksize", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0", key_value)
        self.assertEquals(key_value.values[1], "400-600", key_value)

        key_value = key_values_dict[2]
        self.assertEquals(key_value.key, "installed", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0s0", key_value)

        rp = js2ai.ProcessedData(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex4(unittest.TestCase):
    """Test the read of the rule file with an error condition"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("arch sparc && disksize c0t3d0 \\\n")
            fhandle.write("400-600 && installed c0t3d0s0 solaris_2.1 - p1"
                          " - # xx\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        arch sparc && disksize c0t3d0 \
        400-600 && installed c0t3d0s0 solaris_2.1 - p1  - # xx

        """
        rfd = js2ai.read_rules(self.working_dir, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd.data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "-", defined_rule)
        self.assertEquals(defined_rule.end_script, "-", defined_rule)
        self.assertEquals(defined_rule.profile_name, "p1", defined_rule)
        self.assertEquals(key_value.key, "arch", key_value)
        self.assertEquals(key_value.values[0], "sparc", key_value)

        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "disksize", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0", key_value)
        self.assertEquals(key_value.values[1], "400-600", key_value)

        key_value = key_values_dict[2]
        self.assertEquals(key_value.key, "installed", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0s0", key_value)

        rp = js2ai.ProcessedData(rfd)
        rp.pretty_print_rule_data()


class Test_ReadSysidcfg1(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Using config statement from user config found on web
            fhandle.write("name_service=DNS\n")
            fhandle.write("\t# Comment\n")
            fhandle.write("security_policy=none  # Comment\n")
            fhandle.write("\n")
            fhandle.write("# Comment\n")
            fhandle.write("key=value\n")
            fhandle.write('')

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test to ensure read can property parse simple key=value forms
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), False, report)
        key_values_dict = profile_data.data
        self.assertEquals(len(key_values_dict), 3)
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "name_service", key_value)
        self.assertEquals(key_value.values[0], "DNS", key_value)
        key_value = key_values_dict[3]
        self.assertEquals(key_value.key, "security_policy", key_value)
        self.assertEquals(key_value.values[0], "none", key_value)
        key_value = key_values_dict[6]
        self.assertEquals(key_value.key, "key", key_value)
        self.assertEquals(key_value.values[0], "value", key_value)


class Test_ReadSysidcfg2(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Using config statement from user config found on web
            fhandle.write("name_service=\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test to ensure read can handle bad form of "key=" without value
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), True, report)
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 0, report)


class Test_ReadSysidcfg3(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Using config statement from user config found on web
            fhandle.write("name_service\n")

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test to ensure read can handle bad form of "key" without "=value"
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), True, report)
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 0, report)


class Test_ReadSysidcfg4(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Using config statement from user config found on web
            fhandle.write("name_service=DNS {"
                    "domain_name=informatik.uni-erlangen.de\n"
                    "name_server=131.188.30.105,131.188.30.101,131.188.30.40\n"
                    "\tsearch=informatik.uni-erlangen.de,uni-erlangen.de,"
                    "rrze.uni-erlangen.de} # Comment\n")
            fhandle.write('')

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test to ensure read_sysid() can property parse name_service {} fmt
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), False, report)
        key_values_dict = profile_data.data
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "name_service", key_value)
        self.assertEquals(key_value.values[0], "DNS", key_value)
        self.assertEquals(len(key_value.values), 2)
        payload = key_value.values[1]
        self.assertNotEquals(payload.pop("domain_name", None), None, payload)
        self.assertNotEquals(payload.pop("name_server", None), None, payload)
        self.assertNotEquals(payload.pop("search", None), None, payload)
        self.assertEquals(len(payload), 0, payload)


class Test_ReadSysidcfg5(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Test a different syntax format
            fhandle.write("name_service=DNS\n"
                    "{\n"
                    "name_server=138.2.202.15\n"
                    "search=us.oracle.com\n"
                    "}\n")
            fhandle.write('')

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test read where { is on the line following the supported keyword
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), False, report)
        key_values_dict = profile_data.data
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "name_service", key_value)
        self.assertEquals(key_value.values[0], "DNS", key_value)
        self.assertEquals(len(key_value.values), 2)
        payload = key_value.values[1]
        self.assertNotEquals(payload.pop("name_server", None), None, payload)
        self.assertNotEquals(payload.pop("search", None), None, payload)
        self.assertEquals(len(payload), 0, payload)


class Test_ReadSysidcfg6(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            # Test where a keyword is followed by {} which is not supported
            # for that keyword. ie {} is only allowed after network_interface
            # or name_service
            fhandle.write("root_password=anything\n"
                    "{\n"
                    "name_server=138.2.202.15\n"
                    "search=us.oracle.com\n"
                    "}\n")
            fhandle.write('')

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test read where { is on the line following the unsupported keyword
        """
        profile_data = js2ai.read_sysidcfg(self.working_dir, False)
        self.assertNotEquals(profile_data, None)
        report = profile_data.conversion_report
        self.assertEquals(report.has_errors(), True, report)
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0, report)
        self.assertEquals(report.unsupported_items, 0, report)
        key_values_dict = profile_data.data
        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "root_password", key_value)
        self.assertEquals(key_value.values[0], "anything", key_value)


class Test_ReadSysidcfg7(unittest.TestCase):
    """Test the read of the sysidcfg file"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_sysidcfg(self):
        """Test to ensure we can handle case where sysidcfg isn't there
        """
        self.assertRaises(IOError, js2ai.read_sysidcfg,
                          self.working_dir, False)


class TestNoArgs(unittest.TestCase):
    """Test main method via command line args"""

    def setUp(self):
        """Test setup"""
        self.sys_argv = sys.argv
        self.current_dir = os.getcwd()
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        os.chdir(self.working_dir)

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        os.chdir(self.current_dir)
        shutil.rmtree(self.working_dir)

    def test_no_option(self):
        """Tests calling js2ai with no options"""

        # This will output the usage message and exit with error code 0
        sys.argv = ["js2ai"]
        parser = js2ai.build_option_list()
        self.assertEquals(len(sys.argv), 1)
        parser.print_help()


class TestCommandArgs2(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None
    profile_name = "profile1"

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, self.profile_name)
        with open(filename, 'w') as fhandle:
            fhandle.write("install_type\tinitial_install\n")
            fhandle.write("partitioning\tdefault\n")

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_p_option_valid_profile(self):
        """Tests calling js2ai with -p option set against a valid profile"""

        sys.argv = ["js2ai", "-Sd", self.working_dir,
                    "-D", self.working_dir,
                    "-p", self.profile_name,
                    "-i", "none"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            self.assertEquals(err.code, js2ai.EXIT_SUCCESS,
                              exit_code_report(err.code,
                                               js2ai.EXIT_SUCCESS,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs3(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_p_option_nonexistent_profile(self):
        """Tests calling js2ai with -p option set against non existent
        profile

        """
        sys.argv = ["js2ai", "-d", self.working_dir, "-p", "does_not_exist"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            self.assertEquals(err.code, js2ai.EXIT_IO_ERROR,
                              exit_code_report(err.code,
                                               js2ai.EXIT_IO_ERROR,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs4(unittest.TestCase):
    """Test main method via command line args"""

    def test_d_option_nonexistent_dir(self):
        """Tests calling js2ai with -d option set against non existent
        directory

        """
        sys.argv = ["js2ai", "-d", "/does_not_exist", "-r"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            self.assertEquals(err.code, js2ai.EXIT_IO_ERROR,
                              exit_code_report(err.code,
                                               js2ai.EXIT_IO_ERROR,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs5(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after test run"""
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_D_option_nonexistent_dir(self):
        """Tests calling js2ai with -d option set against non existent dest
        directory

        """
        sys.argv = ["js2ai", "-d", self.working_dir,
                    "-D", "/does_not_exist", "-r"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            self.assertEquals(err.code, js2ai.EXIT_IO_ERROR,
                              exit_code_report(err.code,
                                               js2ai.EXIT_IO_ERROR,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs6(unittest.TestCase):
    """Test main method via command line args"""

    def test_version_option(self):
        """Tests calling js2ai with --version flag"""

        sys.argv = ["js2ai", "--version"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            self.assertEquals(err.code, js2ai.EXIT_SUCCESS,
                              exit_code_report(err.code,
                                               js2ai.EXIT_SUCCESS,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs7(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("# Comment 1 - the lazy brown fox\n")
            fhandle.write("network 924.222.43.0 && karch sun4c     -"
                "   host_class     -\n")
            fhandle.write("# The following rule matches any system:\n\n")
            fhandle.write("arch i386   -   any_machine  -\n")

        # Create the profile file
        filename = os.path.join(self.working_dir, "host_class")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            fhandle.write("partitioning\texplicit\n")
            fhandle.write("fdisk c1t1d0 solaris all\n")

        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            fhandle.write("partitioning\texplicit\n")
            fhandle.write("filesys c0t0d0s0 10240 /\n")

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir)

    def test_d_option_against_valid_rules_profiles(self):
        """Tests calling js2ai with -d option against valid
        rules/profiles, no errors

        """
        sys.argv = ["js2ai", "-Srd", self.working_dir,
                    "-D", self.working_dir, "-i", "none"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            msg = "Got an error code of %d\n%s" \
                % (err.code, fetch_log(js2ai.logfile_name))
            self.assertEquals(err.code, js2ai.EXIT_SUCCESS,
                              exit_code_report(err.code,
                                               js2ai.EXIT_SUCCESS,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgs8(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("network 924.222.43.0 && karch sun4c     - "
                "host_class     -\n")
            fhandle.write("arch i386   -   any_machine  -\n")
            fhandle.write("arch sparc &&\\\n")
            # 1 error should be generated since the disksize keyword is not
            # supported
            fhandle.write("         disksize c0t3d0 400-600 && \\\n")
            # 1 error should be generated since the upgrade profile is missing
            # 1 error should be generated since installed is not supported
            fhandle.write("         installed c0t3d0s0 solaris_2.1 - "
                          "upgrade  -\n")

        # Create the profile file
        filename = os.path.join(self.working_dir, "host_class")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            # 1 error should be generated for the system_type standalone
            fhandle.write("system_type standalone\n")
            fhandle.write("partitioning\texplicit\n")
            fhandle.write("fdisk c1t0d0 solaris all\n")

        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")
            fhandle.write("partitioning\texplicit\n")
            fhandle.write("filesys mirror c0t0d0s3 c0t1d0s3 4096 /\n")

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir)

    def test_d_option_against_invalid_rules_profiles(self):
        """Tests calling js2ai with -d option against rules/profiles,
        with errors

        """
        sys.argv = ["js2ai", "-rSd", self.working_dir,
                    "-D", self.working_dir, "-v", "-i", "none"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            # When there are errors in the rules/profiles the exit code
            # will correspond to the # of failures
            self.assertEquals(err.code, js2ai.EXIT_ERROR,
                              exit_code_report(err.code,
                                               js2ai.EXIT_ERROR,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandArgsValidate(unittest.TestCase):
    """Test -V command line argument"""
    working_dir = None
    filename = "profile.xml"

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        tree = etree.parse(StringIO(TEST_SIMPLE_PROFILE_CONFIG))
        write_xml_data(tree, self.working_dir, self.filename)

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir)

    def test_validate(self):
        """Tests calling js2ai with -V option against a profile that contains
           no errors

        """
        test_file = os.path.join(self.working_dir, self.filename)
        sys.argv = ["js2ai", "-V", test_file]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            # When there are errors in the rules/profiles the exit code
            # will correspond to the # of failures
            self.assertEquals(err.code, js2ai.EXIT_SUCCESS,
                              exit_code_report(err.code,
                                               js2ai.EXIT_SUCCESS,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestCommandOption_S_No_Failures(unittest.TestCase):
    """Test main method via command line args"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("# Test sysidcfg file")
            fhandle.write("root_password=fakepasswordfortest\n")

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir)

    def test_s_option_against_valid_sysidcfg(self):
        """Tests calling js2ai with -s option against valid sysidcfg, no errors

        """
        sys.argv = ["js2ai", "-d", self.working_dir,
                    "-D", self.working_dir, "-s"]
        try:
            js2ai.main()
        except SystemExit, err:
            self.assertEquals(type(err), type(SystemExit()))
            # When there are errors in the rules/profiles the exit code
            # will correspond to the # of failures
            self.assertEquals(err.code, js2ai.EXIT_SUCCESS,
                              exit_code_report(err.code,
                                               js2ai.EXIT_SUCCESS,
                                               js2ai.logfile_name))
        except Exception, err:
            self.fail(exception_report(err, js2ai.logfile_name))


class TestProcessSysidcfg(unittest.TestCase):
    """Test process_sysidcfg against bad sysidcfg"""
    working_dir = None

    def setUp(self):
        """Test setup"""
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.SYSIDCFG_FILENAME)
        with open(filename, 'w') as fhandle:
            fhandle.write("bogus data\n")
            fhandle.write("bogus=data\n")
            fhandle.write("\tbogus=data\n")
        js2ai.logger_setup(self.working_dir)

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir)

    def test_invalid_sysidcfg(self):
        """Tests calling process_sysidcfg against bad sysidcfg

        """
        default_xml = XMLDefaultData(None)
        sysidcfg_data = js2ai.process_sysidcfg(self.working_dir,
                                               self.working_dir,
                                               default_xml,
                                               verbose=False)
        self.assertNotEquals(None, sysidcfg_data)
        report = sysidcfg_data.conversion_report

        self.assertEquals(report.has_errors(), True)
        self.assertEquals(report.process_errors, 1,
                          profile_failure_report(default_xml.tree, report,
                                                 js2ai.logfile_name))
        self.assertEquals(report.conversion_errors, 0,
                          profile_failure_report(default_xml.tree, report,
                                                 js2ai.logfile_name))
        self.assertEquals(report.unsupported_items, 2,
                          profile_failure_report(default_xml.tree, report,
                                                 js2ai.logfile_name))
        self.assertEquals(report.validation_errors, None,
                          profile_failure_report(default_xml.tree, report,
                                                 js2ai.logfile_name))


class TestBadPermissions(unittest.TestCase):
    """Test main method via command line args"""
    """File permission tests"""

    def setUp(self):
        """Test setup"""
        # create a working directory to test with
        self.working_dir = tempfile.mkdtemp()

        # save the EUID of the user running the test
        self.current_uid = os.geteuid()

        # 'nobody' UID
        self.nobody_uid = pwd.getpwnam("nobody")[2]

    def tearDown(self):
        """Clean up after test run"""
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_unreadable_profile(self):
        """Test condition where we can't read profile due to permissions"""
        filename = os.path.join(self.working_dir, "profile")
        with open(filename, 'w') as fhandle:
            fhandle.write("Install_type initial_install\n")

        # chmod the file so nobody can read it
        os.chmod(filename, 0000)

        # change to 'nobody', if running as root
        if self.current_uid == 0:
            os.seteuid(self.nobody_uid)

        self.assertRaises(IOError, js2ai.read_profile, self.working_dir,
                                                      filename, False)

        # change back to root, if needed
        if self.current_uid == 0:
            os.seteuid(self.current_uid)

    def test_unwritable_logfile(self):
        """Test writting to a log file that we don't have perm to write to"""
        # touch a new copy of the file
        with open(os.path.join(self.working_dir, js2ai.LOGFILE), "w"):
            pass

        # chmod the file
        os.chmod(os.path.join(self.working_dir, js2ai.LOGFILE), 0444)

        # change to 'nobody', if running as root
        if self.current_uid == 0:
            os.seteuid(self.nobody_uid)

        self.assertRaises(IOError, js2ai.logger_setup, self.working_dir)

        # change back to root, if needed
        if self.current_uid == 0:
            os.seteuid(self.current_uid)

if __name__ == '__main__':
    unittest.main()

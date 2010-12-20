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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

import logging
import os
import shutil
import sys
import tempfile
import unittest

import solaris_install.js2ai as js2ai

from solaris_install.js2ai.common import ProfileData
from solaris_install.js2ai.common import KeyValues

# Temporary Directory to use
TEMP_DIR = "/tmp"


class Test_ConversionReport(unittest.TestCase):

    def tearDown(self):
        self.conv_report = None

    def test_ConversionReport_wNoErrors(self):
        """Tests the most basic case where there are no errors."""
        conv_report = js2ai.ConversionReport()
        self.assertEquals(conv_report.process_errors, 0)
        self.assertEquals(conv_report.conversion_errors, 0)
        self.assertEquals(conv_report.unsupported_items, 0)
        self.assertEquals(conv_report.has_errors(), False)

    def test_ConversionReport_wProcessError(self):
        """Tests ConversionReport with 1 error and 2 None values"""
        conv_report = js2ai.ConversionReport(1, None, None)
        self.assertEquals(conv_report.process_errors, 1)
        self.assertEquals(conv_report.conversion_errors, None)
        self.assertEquals(conv_report.unsupported_items, None)
        self.assertEquals(conv_report.has_errors(), True)

    def test_ConversionReport_wErrors(self):
        """Test setting values on conversion report via constructor"""
        conv_report = js2ai.ConversionReport(4, 0, 0)
        self.assertEquals(conv_report.process_errors, 4)
        self.assertEquals(conv_report.conversion_errors, 0)
        self.assertEquals(conv_report.unsupported_items, 0)
        self.assertEquals(conv_report.has_errors(), True)

        conv_report.add_conversion_error()
        self.assertEquals(conv_report.conversion_errors, 1)

        conv_report.add_unsupported_item()
        self.assertEquals(conv_report.unsupported_items, 1)
        self.assertEquals(conv_report.has_errors(), True)

    def test_ConversionReport_setErrors(self):
        """Test setting values on conversion report via setXXX methods"""
        conv_report = js2ai.ConversionReport()
        conv_report.process_errors = 3
        conv_report.conversion_errors = 2
        conv_report.unsupported_items = 0

        self.assertEquals(conv_report.process_errors, 3)
        self.assertEquals(conv_report.conversion_errors, 2)
        self.assertEquals(conv_report.unsupported_items, 0)


class Test_RuleRead_wProcessErrs1(unittest.TestCase):
    working_dir = None
    log_file = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        # Create the rules files
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            # This rule should fail with one process error\n"
            # since it doesn't follow the min setup of
            # key value begin_script profile end_script
            f.write("any - - - ")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_invalid_format(self):
        """Test to ensure that read_rules() catches invalid format"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir,
                                         js2ai.RULES_FILENAME, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close()

        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1, "Expecting 1 error in log file")


class Test_RuleRead_wProcessErrs2(unittest.TestCase):
    working_dir = None
    log_file = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            # This rule should fail with one process error
            # since the referenced profile does not exist
            f.write("hostname sample_host    -       host_class")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_with_non_existing_profile(self):
        """Test read rules catches failure due to non existing profile file"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir,
                                         js2ai.RULES_FILENAME, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close()

        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1, "Expecting 1 error in log file")


class Test_RuleRead_wProcessErrs3(unittest.TestCase):
    working_dir = None
    log_file = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            # This rule should fail with one process error
            # since the rule line is incomplete
            f.write("arch sparc && \\\n")
            f.write("    disksize c0t3d0 400-600 && \\\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_incomplete_line(self):
        """Test to ensure that read_rules() catches incomplete line"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir,
                                         js2ai.RULES_FILENAME, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close()

        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1, "Expecting 1 error in log file")


class Test_RuleRead_wProcessErrs4(unittest.TestCase):
    working_dir = None
    log_file = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            # This rule should fail with one process error
            # since the rule line is incomplete
            f.write("arch sparc && disksize c0t3d0 400-600 && \\\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_incomplete_line(self):
        """Test to ensure that read_rules() catches incomplete line"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir,
                                         js2ai.RULES_FILENAME, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close()

        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1, "Expecting 1 error in log file")


class Test_RuleRead_wProcessErrs5(unittest.TestCase):
    working_dir = None
    log_file = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)

        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            # This rule should fail with one process error
            # since it doesn't follow the min setup of
            # key value begin_script profile end_script
            f.write("any\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules_insufficient_args(self):
        """Test to ensure that read_rules() catches insufficient args"""
        js2ai.logger_setup(self.working_dir)
        rulesFileData = js2ai.read_rules(self.working_dir,
                                         js2ai.RULES_FILENAME, True)
        self.assertNotEqual(rulesFileData, None, "No data returned")
        report = rulesFileData.conversion_report
        self.assertEquals(report.process_errors, 1, report)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close()

        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1, "Expecting 1 error in log file")


class Test_ProfileRead_wProcessErrs(unittest.TestCase):
    working_dir = None
    log_file = None
    profile_name = "profile1"

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the profile file
        filename = os.path.join(self.working_dir, self.profile_name)
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            f.write("package SUNWCall\n")
            f.write("package\n")
            f.write("package SUNWCuser\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_profile_with_one_failure(self):
        """ Test to ensure that read_profile() catches failure in profile file
        """
        js2ai.logger_setup(self.working_dir)
        profileData = js2ai.read_profile(self.working_dir,
                                                self.profile_name, False)
        self.assertNotEquals(profileData, None)
        report = profileData.conversion_report
        self.assertEquals(report.process_errors, 1)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)
        self.log_file = os.path.join(self.working_dir, js2ai.LOGFILE)
        with open(self.log_file, 'r') as f:
            readLines = f.readlines()
        f.close
        count = 0
        for line in readLines:
            count = count + 1
        self.assertEquals(count, 1)


class Test_ProcessRules(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("# The following rule matches any system:\n\n")
            f.write("arch i386   -   any_machine  -\n")
        f.close()

        # Create the profile file
        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            f.write("boot_device c2t0d0s0\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_process_rules(self):
        """Test to ensure process_rules() and process_profiles() works as
        expected.  The rules/profiles used for this test contain no errors

        """
        rp = js2ai.process_rule(js2ai.RULES_FILENAME, self.working_dir, \
                                self.working_dir, True, False)
        ruleFileData = rp.rules_file_data
        report = ruleFileData.conversion_report
        self.assertEquals(report.process_errors, 0)
        self.assertEquals(report.conversion_errors, 0)
        self.assertEquals(report.unsupported_items, 0)

        profiles = rp.defined_profiles
        for key in profiles.iterkeys():
            profileData = profiles[key]
            self.assertNotEquals(profileData, None)
            report = profileData.conversion_report
            self.assertEquals(report.process_errors, 0)
            self.assertEquals(report.conversion_errors, 0)
            self.assertEquals(report.unsupported_items, 0)


class Test_ReadRulesComplex1(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("karch abc && memsize 64-128 begin basic_prof end\n\n")
        f.close()

        # Create the profile file
        filename = os.path.join(self.working_dir, "basic_prof")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        keyword1 value1 && keyword2 value2 ....

        """
        rfd = js2ai.read_rules(self.working_dir, js2ai.RULES_FILENAME, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd._data[1]
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

        rp = js2ai.RulesAndAssociatedProfiles(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex2(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("karch abc && \\\n")
            f.write("memsize 64-128 begin basic_prof end\n\n")
        f.close()

        # Create the profile file
        filename = os.path.join(self.working_dir, "basic_prof")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        keyword1 value1 && \
        keyword2 value2 ....

        """
        rfd = js2ai.read_rules(self.working_dir, js2ai.RULES_FILENAME, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd._data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd._data[1]
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

        rp = js2ai.RulesAndAssociatedProfiles(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex3(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("arch sparc && disksize c0t3d0 400-600 \\\n")
            f.write("\\\n")
            f.write("&& installed c0t3d0s0 solaris_2.1 - profile1  - #test\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        arch sparc && disksize c0t3d0 400-600 \
        \
        && installed c0t3d0s0 solaris_2.1 - profile1  - #test

        """
        rfd = js2ai.read_rules(self.working_dir, js2ai.RULES_FILENAME, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd._data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd._data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "-")
        self.assertEquals(defined_rule.end_script, "-")
        self.assertEquals(defined_rule.profile_name, "profile1")
        self.assertEquals(key_value.key, "arch", key_value)
        self.assertEquals(key_value.values[0], "sparc", key_value)

        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "disksize", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0", key_value)
        self.assertEquals(key_value.values[1], "400-600", key_value)

        key_value = key_values_dict[2]
        self.assertEquals(key_value.key, "installed", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0s0", key_value)

        rp = js2ai.RulesAndAssociatedProfiles(rfd)
        rp.pretty_print_rule_data()


class Test_ReadRulesComplex4(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("arch sparc && disksize c0t3d0 \\\n")
            f.write("400-600 && installed c0t3d0s0 solaris_2.1 - p1  - # xx\n")
        f.close()

    def tearDown(self):
        # Delete everything when we are done
        shutil.rmtree(self.working_dir)

    def test_read_rules(self):
        """Test to ensure read_rules() can property parse
        arch sparc && disksize c0t3d0 \
        400-600 && installed c0t3d0s0 solaris_2.1 - p1  - # xx

        """
        rfd = js2ai.read_rules(self.working_dir, js2ai.RULES_FILENAME, False)
        self.assertEquals(rfd.conversion_report.has_errors(), False,
                          rfd.conversion_report)
        defined_rule = rfd._data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]

        # Retreive the rule data for line 1 in the rule file
        defined_rule = rfd._data[1]
        key_values_dict = defined_rule.key_values_dict
        key_value = key_values_dict[0]
        self.assertEquals(defined_rule.begin_script, "-")
        self.assertEquals(defined_rule.end_script, "-")
        self.assertEquals(defined_rule.profile_name, "p1")
        self.assertEquals(key_value.key, "arch", key_value)
        self.assertEquals(key_value.values[0], "sparc", key_value)

        key_value = key_values_dict[1]
        self.assertEquals(key_value.key, "disksize", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0", key_value)
        self.assertEquals(key_value.values[1], "400-600", key_value)

        key_value = key_values_dict[2]
        self.assertEquals(key_value.key, "installed", key_value)
        self.assertEquals(key_value.values[0], "c0t3d0s0", key_value)

        rp = js2ai.RulesAndAssociatedProfiles(rfd)
        rp.pretty_print_rule_data()


# The following test the command line options
# each of these is put into it's own class since
# if we attempt to change the sys.arg list multiple
# times the argv list may have remeants from previous calls
# These tests only test that the proper exit code is returned
# for the various options
class TestCommandArgs1(unittest.TestCase):
    current_dir = None
    working_dir = None
    sys_argv = None

    def setUp(self):
        self.sys_argv = sys.argv
        self.current_dir = os.getcwd()
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()
        os.chdir(self.working_dir)

    def tearDown(self):
        # Delete everything when we are done
        os.chdir(self.current_dir)
        shutil.rmtree(self.working_dir)
        sys.argv = self.sys_argv

    def test_no_option(self):
        """Tests calling js2ai with no options"""

        sys.argv = ["js2ai"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, -1)
        else:
            self.fail('SystemExit -1 expected')


class TestCommandArgs2(unittest.TestCase):
    working_dir = None
    profile_name = "profile1"

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        js2ai.logger_setup(self.working_dir)
        # Create the rules file
        filename = os.path.join(self.working_dir, self.profile_name)
        with open(filename, 'w') as f:
            f.write("install_type\tinitial_install\n")

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_p_option_valid_profile(self):
        """Tests calling js2ai with -p option set against a valid profile"""

        sys.argv = ["js2ai", "-d", self.working_dir, "-p", self.profile_name]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, 0)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit 0 expected')


class TestCommandArgs3(unittest.TestCase):
    def test_p_option_nonexistent_profile(self):
        """Tests calling js2ai with -p option set against non existent
        profile

        """
        sys.argv = ["js2ai", "-d", TEMP_DIR, "-p", "does_not_exist"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, -1)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit -1 expected')


class TestCommandArgs4(unittest.TestCase):
    def test_d_option_nonexistent_dir(self):
        """Tests calling js2ai with -d option set against non existent
        directory

        """
        sys.argv = ["js2ai", "-d", "/does_not_exist"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, 2)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit 2 expected')


class TestCommandArgs5(unittest.TestCase):
    def test_D_option_nonexistent_dir(self):
        """Tests calling js2ai with -d option set against non existent dest
        directory

        """
        sys.argv = ["js2ai", "-d", TEMP_DIR, "-D", "/does_not_exist"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, 2)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit 2 expected')


class TestCommandArgs6(unittest.TestCase):
    def test_version_option(self):
        """Tests calling js2ai with --version flag"""

        sys.argv = ["js2ai", "--version"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, 0)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit 0 expected')


class TestCommandArgs7(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("# Comment 1 - the lazy brown fox\n")
            f.write("network 924.222.43.0 && karch sun4c     -"
                "   host_class     -\n")
            f.write("# The following rule matches any system:\n\n")
            f.write("arch i386   -   any_machine  -\n")
        f.close()

        # Create the profile file
        filename = os.path.join(self.working_dir, "host_class")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            f.write("fdisk c1t1d0 solaris maxfree\n")
        f.close()

        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            f.write("filesys c0t0d0s0 10240 /\n")
        f.close()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_d_option_against_valid_rules_profiles(self):
        """Tests calling js2ai with -d option against valid
        rules/profiles, no errors

        """
        sys.argv = ["js2ai", "-d", self.working_dir]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            self.assertEquals(e.code, 0)
        except Exception, e:
            self.fail('unexpected exception: %s' % e)
        else:
            self.fail('SystemExit 0 expected')


class TestCommandArgs8(unittest.TestCase):
    working_dir = None

    def setUp(self):
        # Create a directory to work in
        self.working_dir = tempfile.mkdtemp()

        # Create the rules file
        filename = os.path.join(self.working_dir, js2ai.RULES_FILENAME)
        with open(filename, 'w') as f:
            f.write("network 924.222.43.0 && karch sun4c     - "
                "host_class     -\n")
            f.write("arch i386   -   any_machine  -\n")
            f.write("arch sparc &&\\\n")
            # 1 error should be generated since the disksize keyword is not
            # supported
            f.write("         disksize c0t3d0 400-600 && \\\n")
            # 1 error should be generated since the upgrade profile is missing
            # 1 error should be generated since installed is not supported
            f.write("         installed c0t3d0s0 solaris_2.1 - upgrade  -\n")
        f.close()

        # Create the profile file
        filename = os.path.join(self.working_dir, "host_class")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            # 1 error should be generated for the system_type standalone
            f.write("system_type standalone\n")
            f.write("fdisk c1t0d0 solaris all\n")
        f.close()

        filename = os.path.join(self.working_dir, "any_machine")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")
            f.write("filesys mirror c0t0d0s3 c0t1d0s3 4096 /\n")
        f.close()

    def tearDown(self):
        shutil.rmtree(self.working_dir)

    def test_d_option_against_invalid_rules_profiles(self):
        """Tests calling js2ai with -d option against rules/profiles,
        with errors

        """
        sys.argv = ["js2ai", "-d", self.working_dir, "-v"]
        try:
            js2ai.main()
        except SystemExit, e:
            self.assertEquals(type(e), type(SystemExit()))
            # When there are errors in the rules/profiles the exit code
            # will correspond to the # of failures
            self.assertEquals(e.code, 4)
        except Exception, e:
            self.fail("unexpected exception: %s" % e)
        else:
            self.fail("SystemExit expected 4 errors")


class TestBadPermissions(unittest.TestCase):
    def setUp(self):
        # create a working directory to test with
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

        # remove the logfile if present
        if os.path.exists(os.path.join(TEMP_DIR, js2ai.LOGFILE)):
            os.remove(os.path.join(TEMP_DIR, js2ai.LOGFILE))

    def test_unwritable_directory(self):
        filename = os.path.join(self.working_dir, "profile")
        with open(filename, 'w') as f:
            f.write("Install_type initial_install\n")

        # chmod the file so nobody can read it
        os.chmod(filename, 0000)
        self.assertRaises(IOError, js2ai.read_profile, self.working_dir,
                                                      filename, False)

    def test_unwritable_logfile(self):
        # remove the logfile if present
        if os.path.exists(os.path.join(TEMP_DIR, js2ai.LOGFILE)):
            os.remove(os.path.join(TEMP_DIR, js2ai.LOGFILE))

        # touch a new copy of the file
        with open(os.path.join(TEMP_DIR, js2ai.LOGFILE), "w"):
            pass

        # chmod the file
        os.chmod(os.path.join(TEMP_DIR, js2ai.LOGFILE), 0444)

        self.assertRaises(SystemExit, js2ai.logger_setup, TEMP_DIR)


if __name__ == '__main__':
    logger = logging.getLogger("js2ai_conv")
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    logger.addHandler(ch)
    unittest.main()

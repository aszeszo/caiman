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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
"""js2ai conversion program"""
import logging
import os
import os.path
import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
import re
import sys
import traceback

from common import _
from common import ConversionReport
from common import KeyValues
from common import generate_error
from common import err
from common import pretty_print
from common import ProfileData
from common import ARCH_X86, ARCH_SPARC
from common import DEFAULT_AI_DTD_FILENAME, DEFAULT_AI_FILENAME
from common import DEFAULT_SC_PROFILE_DTD_FILENAME
from common import ERR_VAL_MODID
from common import LOG_KEY_FILE, LOG_KEY_LINE_NUM
from common import LOGGER
from common import LVL_CONVERSION, LVL_PROCESS
from common import LVL_UNSUPPORTED, LVL_VALIDATION, LVL_WARNING
from common import RULES_FILENAME, SYSIDCFG_FILENAME, SC_PROFILE_FILENAME
from common import fetch_xpath_node
from common import write_xml_data
from common import validate
from conv import XMLProfileData
from conv import XMLRuleData
from conv_sysidcfg import XMLSysidcfgData
from default_xml import XMLDefaultData
from optparse import OptionParser, SUPPRESS_HELP
from lxml import etree
from StringIO import StringIO

VERSION = _("%prog: version 1.0")

COMMENT_PATTERN = re.compile("^([^#]*)#.*")
VALUE_PATTERN = re.compile("\s*(\S+)")
SPACE_PATTERN = re.compile("\s+")
MULTILINE_PATTERN1 = re.compile("([^&]*)(\\\\)(.*)$")
MULTILINE_PATTERN2 = re.compile("([^&]*)(&&)(.*)$")
RULE_STRIP_PATTERN = re.compile("^\s*(\w+)\s+(\w+)\s+(\w+)\s+(\w+).+")
KEY_EQUAL_VALUE_PATTERN = re.compile("([^=]+)=(\S*)")

EXIT_SUCCESS = 0
EXIT_IO_ERROR = 1
EXIT_OPTIONS_ERROR = 2
EXIT_INTERNAL_ERROR = 3
EXIT_VALIDATION_ERROR = 4
EXIT_ERROR = 5      # Converson, Process, or Unknown Error

AI_PREFIX = "AI_"
MERGE_DEFAULT_SUFFIX = "_syscfg"

LOGFILE = "js2ai.log"
ERRFILE = "js2ai.err"

logfile_name = None
logfile_handler = None


class ProcessedData(object):
    """Contents of user defined jumpstart rule file and associated profile
       key value pairs

    """

    def __init__(self, rules_file_data):
        self._rules_file_data = rules_file_data
        self._profiles = dict()

    @property
    def rules_file_data(self):
        """Returns the RuleFileData object for the jumpstart rule file"""
        return self._rules_file_data

    @property
    def defined_profiles(self):
        """Returns a dictionary with all the defined profiles, where key
           is the name of the profile and the value is ProfileData

        """
        return self._profiles

    def add_defined_profile(self, profile_data):
        """Add the data for a profile to the profile dictionary"""
        if profile_data is None or profile_data.name is None:
            raise ValueError
        self.defined_profiles[profile_data.name] = profile_data

    def pretty_print_rule_data(self):
        """Debug routine used to print the rules in the rulesDctionary"""
        print "\n                   Begin      End"
        print "#  Profile         Script     Script      Key         "\
            "Values"
        print "-- --------------- ---------- ----------- -----------"\
            " --------------"

        if self.rules_file_data is None:
            print "None"
            return

        rules_dict = self.rules_file_data.data
        for k, defined_rule in rules_dict.iteritems():
            print "%2d %-15s %-10s %-10s " % (k,
                                                defined_rule.profile_name,
                                                defined_rule.begin_script,
                                                defined_rule.end_script),
            first_line = True
            for data in defined_rule.key_values_dict.itervalues():
                if first_line:
                    # We don't tab the first line
                    first_line = False
                else:
                    # Tab the line out so that we position all keys
                    # beyond the first at the position necessary
                    # for outputing key
                    print "\t\t\t\t\t ",
                print "%-10s  %s" % (data.key, data.values)


class DefinedRule(object):
    """A user defined rule in a jumpstart rule file"""

    def __init__(self, begin_script, profile, end_script):
        self._begin_script = begin_script
        self._profile = profile
        self._end_script = end_script
        self._index = 0
        self._data = dict()

    def add_key_values(self, keyword, values, line_num):
        """Add the keyword and values for the specified rule.  Records the
        line number location for that key/value combination

        """
        key_values = KeyValues(keyword, values, line_num)
        self._data[self._index] = key_values
        self._index += 1

    @property
    def key_values_dict(self):
        """Returns the rule dictionary, where key is the rule line # and the
           data object is dict of rules keywords and values

        """
        return self._data

    @property
    def profile_name(self):
        """Returns the profile that should be applied if the rule keywords
           match

        """
        return self._profile

    @property
    def begin_script(self):
        """Returns the begin script that should be executed for this rule"""
        return self._begin_script

    @property
    def end_script(self):
        """Returns the end script that should be executed for this rule"""
        return self._end_script

    @begin_script.setter
    def begin_script(self, begin_script):
        """Sets the begin script that should be executed for this rule"""
        self._begin_script = begin_script

    @end_script.setter
    def end_script(self, end_script):
        """Set the end script that should be executed for this rule"""
        self._end_script = end_script

    @profile_name.setter
    def profile_name(self, profile_name):
        """Returns the profile that should be applied if the rule keywords
           match
        """
        self._profile = profile_name

    def __str__(self):
        return "begin_script: " + str(self.begin_script) +\
               ", end_script: " + str(self.end_script) +\
               ", profile: " + str(self.profile_name) +\
               ", data: " + str(self._data)


class RulesFileData(object):
    """Contains the contents of a jumpstart rule file"""

    def __init__(self, data, report):
        self._data = data
        self._conv_report = report

    @property
    def data(self):
        """Returns Dictionary of contents of rules file, where key is the
           rule number and the data object is of type DefinedRule

        """
        return self._data

    @property
    def conversion_report(self):
        """Report of all errors encountered"""
        return self._conv_report

    def __str__(self):
        return "name: " + RULES_FILENAME +\
            ", data: [ " + str(self.data) + \
            " ], conversion report: " + str(self.conversion_report)


def logger_setup(log_directory):
    """Performs setup of the various loggers used by the application"""
    global logfile_name
    global logfile_handler

    LOGGER.setLevel(logging.INFO)

    # Add new logging levels that correspond to the error types
    # js2ai is outputing in it's error reports
    logging.addLevelName(LVL_PROCESS, "PROCESS")
    logging.addLevelName(LVL_UNSUPPORTED, "UNSUPPORTED")
    logging.addLevelName(LVL_CONVERSION, "CONVERSION")
    logging.addLevelName(LVL_VALIDATION, "VALIDATION")
    # LVL_WARNING mapped to WARNING so it's already present, don't need to add

    # create console handler and set level to debug
    logfile_name = os.path.join(log_directory, LOGFILE)
    try:
        logfile_handler = logging.FileHandler(logfile_name, 'w')
    except IOError as msg:
        # err is cast to str here since it is possible for it to be None
        raise IOError(_("Failed to open log file: %s\n") % str(msg))

    # Define the format for the log file.  'file' and 'line_num' are
    # not values that the logger knows about.  These will be filled
    # in during the log process via the dictionary that is passed
    # in during the log call through the parameter "extra"
    # For example
    # extra_log_params = {"file": "profile1", "line_num": 10 }
    # logger.warning('error message', extra=extra_log_params)
    #
    # When used with the below formater the above would generate
    #
    # profile1: line 10: WARNING: error message

    format = _("%(file)s:line %(line_num)d:%(levelname)s: %(message)s")
    # add formatter to ch
    logfile_handler.setFormatter(logging.Formatter(format))
    # add ch to logger
    LOGGER.addHandler(logfile_handler)


def logger_key(log_line):
    """Generate the key to use for sorting log files"""
    try:
        filename, line_num_info, line = log_line.split(": ", 2)
        line, line_num = line_num_info.split(" ", 1)
        return "%s %4s" % (filename, line_num)
    except ValueError:
        return log_line


def logger_sort(filename):
    """Sort the contents of log file 'filename'"""
    log_lines = []
    profile_lines = []
    try:
        with open(filename, "r") as f_handle:
            for line in f_handle:
                if line.startswith(RULES_FILENAME):
                    log_lines.append(line)
                else:
                    profile_lines.append(line)
    except IOError:
        raise IOError(_("failed to sort logfile"))
    log_lines.sort(key=logger_key)
    profile_lines.sort(key=logger_key)
    log_lines.extend(profile_lines)
    try:
        with open(filename, "w") as f_handle:
            f_handle.writelines(log_lines)
    except IOError:
        # The log file is gone output all the message to the screen
        err(_("rewrite of log file failed."))
        for line in log_lines:
            sys.stderr.write(line)


def add_validation_errors(filename, validation_errors):
    """Add the validation errors to the log file 'filename'"""
    if len(validation_errors) == 0:
        return
    lines = []
    for val_err in validation_errors:
        lines.append(val_err.error_data[liberrsvc.ES_DATA_FAILED_STR])
    lines.sort()
    if len(lines) > 0:
        try:
            with open(filename, "a") as f_handle:
                f_handle.write(_("\n\nValidation Errors:\n"))
                f_handle.writelines(lines)
        except IOError:
            err(_("failed to write validation errors to logfile"))
            for line in lines:
                sys.stderr.write(line)


def clean_line(line):
    """Process the line removing the tailing comments and extra spaces"""
    match_pattern = COMMENT_PATTERN.match(line)
    if match_pattern is not None:
        line = match_pattern.group(1)

    # Find all tabs and extra spaces between the words
    # and replace with a single space
    return SPACE_PATTERN.sub(" ", line.strip())


def read_rules(src_dir, verbose):
    """Reads the specified jumpstart rules file and returns a dictionary
       of the parsed rules

       Arguments:
       src_dir -- The directory containing the rules file
       verbose  -- verbose ouptut (true/false)

       Returns:
       RuleFileData - the data read from the rules files

    """
    if src_dir is None:
        raise ValueError
    filename = os.path.join(src_dir, RULES_FILENAME)
    if verbose:
        print _("Processing: %s") % RULES_FILENAME

    if not os.path.isfile(filename):
        raise IOError(_("No such file found: %s\n") % filename)

    try:
        with open(filename, "r") as f_handle:
            lines = map(clean_line, f_handle.readlines())
    except IOError:
        raise IOError(_("Failed to read rules file: %s" % filename))

    rules_dict = dict()
    rule_index = 1
    conv_report = ConversionReport(process_errs=0, conversion_errs=0,
                                   unsupported_items=0, validation_errs=None)
    defined_rule = None
    line_num = 0
    line_cnt = len(lines)
    extra_log_params = {LOG_KEY_FILE: RULES_FILENAME, LOG_KEY_LINE_NUM: 0}
    while line_num < line_cnt:
        if defined_rule is not None:
            generate_error(LVL_PROCESS, conv_report,
                           _("Incomplete rule detected"),
                           extra_log_params)
            # Throw away the old defined rule, it's incomplete
            defined_rule = None

        line = lines[line_num]
        line_num += 1
        extra_log_params[LOG_KEY_LINE_NUM] = line_num
        if not line:
            continue

        if defined_rule is None:
            defined_rule = DefinedRule(None, None, None)
        while line:
            # At this point we have a new rule with one or more key
            # value pairs which can span 1 to n lines.  A \
            # is used to continue a line to the next line.
            # A && is used to seprate key value pair groupings
            #
            match_pattern1 = MULTILINE_PATTERN1.match(line)
            match_pattern2 = MULTILINE_PATTERN2.match(line)
            if not match_pattern1 and not match_pattern2:
                try:
                    kv_pairs, begin_script, profile, end_script = \
                        line.rsplit(' ', 3)
                except ValueError:
                    generate_error(LVL_PROCESS, conv_report,
                                   _("invalid rule. Does not conform to "
                                     "required format of <key> <value> "
                                     "<begin_script> <profile> <end_script>:"
                                     " %(line)s") % {"line": line},
                                   extra_log_params)
                    defined_rule = None
                    line = None
                    continue

                defined_rule.begin_script = begin_script
                defined_rule.profile_name = profile
                defined_rule.end_script = end_script

                # Flag the profile as a process error if it doesn't
                # exist so we can output the reference line #
                if profile != "-":
                    if not os.path.isfile(os.path.join(src_dir, profile)):
                        # We don't add this as a processing error.
                        # We'll mark it as a processing error on the
                        # file itself in phase 2 when we process the
                        # profile file directly. However we do record
                        # it to the log so that we will record the
                        # correct line where the problem occurred
                        # It's easier to do it here then later since
                        # our structures do not record the line # the
                        # profile name was read from.
                        generate_error(LVL_PROCESS, conv_report,
                                       _("profile not found: %(prof)s") % \
                                         {"prof": profile},
                                       extra_log_params)
                line = None
            else:
                if match_pattern1 is not None:
                    # Our line did not contain a && but we had a / in it
                    # We've got a line that may be incomplete so we have to
                    # add the next line to it before we can process the key
                    # value pairs.
                    #
                    # NOTE: that this changes our line # for errors
                    # to the line number we just incremented to
                    if line_num < line_cnt:
                        if match_pattern1.group(1) == "":
                            # Check for the special case where we had
                            # line that simply started with a \ ie.
                            #
                            # arch sparc && disksize c0t3d0 400-600 \
                            # \
                            # && installed c0t3d0s0 solaris_2.1 - -  -
                            #
                            # which would return a empty string for pattern
                            # group 1.  If we added it to our line with the
                            # extra space to separate the fields, when we
                            # processed this line in the next loop
                            # we would get a key of ''.  Therefore we set
                            # our line to next line
                            line = lines[line_num]
                        else:
                            line = match_pattern1.group(1).strip() \
                                + " " + lines[line_num]
                        line_num += 1
                    else:
                        line = None
                    continue

                # We matched on MATCH_PATTERN2 and have a line that
                # follows one of these basic forms:
                #
                #   key1 value1 && key2 value2 ....
                #   key1 value1 [value2..] && \
                #       key2 value ....
                #
                kv_pairs = match_pattern2.group(1)

                # Process the first key value pair and then
                # set our line to remainder.
                line = match_pattern2.group(3).strip()
                if line.startswith('\\'):
                    # Our line was in the form:
                    #   key value && \
                    #
                    # Nothing left to process on the current line
                    # Set line to None so we'll break out of the
                    # current loop and we'll read the next line in the
                    # file
                    if line_num < line_cnt:
                        line = lines[line_num]
                        line_num += 1
                    else:
                        # No more lines left to read
                        line = None
            try:
                key, values = kv_pairs.split(' ', 1)
            except ValueError:
                generate_error(LVL_PROCESS, conv_report,
                               _("invalid rule. No value defined for key: "
                                 "%(line)s") % {"line": kv_pairs},
                               extra_log_params)
                defined_rule = None
                line = None
                continue

            value_entries = VALUE_PATTERN.findall(values)
            defined_rule.add_key_values(key, value_entries, line_num)

            if not match_pattern1 and not match_pattern2:
                rules_dict[rule_index] = defined_rule
                rule_index = rule_index + 1
                defined_rule = None

    if rule_index == 0:
        # Failed to read in any valid rules.
        raise IOError(_("Invalid rule file.  No rules found"))

    if defined_rule is not None:
        generate_error(LVL_PROCESS, conv_report,
                       _("Incomplete rule detected"), extra_log_params)
    return RulesFileData(rules_dict, conv_report)


def read_sysidcfg(src_dir, verbose):
    """Reads the sysidcfg file and returns a dictionary
       of the parsed entries

       Arguments:
       src_dir - The directory containing the rules file
       verbose - verbose ouptut (true/false)

       Returns:
       dictionary - the data read from the sysidcfg files

    """

    filename = os.path.join(src_dir, SYSIDCFG_FILENAME)
    if verbose:
        print _("Processing: %s") % SYSIDCFG_FILENAME

    if not os.path.isfile(filename):
        raise IOError(_("No such sysidcfg found: %s" % filename))
    try:
        with open(filename, "r") as f_handle:
            lines = map(clean_line, f_handle.readlines())
    except IOError:
        raise IOError(_("Failed to read file: %s" % filename))

    conv_report = ConversionReport()
    sysidcfg = ProfileData(SYSIDCFG_FILENAME)
    line_continued = None
    line_start = 0
    extra_log_params = {LOG_KEY_FILE: SYSIDCFG_FILENAME, LOG_KEY_LINE_NUM: 0}
    for lineno, line in enumerate(lines):
        # skip blank lines
        if not line:
            continue

        if line_continued is not None:
            line = line_continued + " " + line
            line_continued = None
        else:
            line_start = lineno + 1
        extra_log_params[LOG_KEY_LINE_NUM] = line_start
        try:
            key_value, the_rest = line.split("{", 1)
            try:
                # extra payload present.  Do we have it all
                payload, the_end = the_rest.split("}", 1)
                payload_dict = dict()
                values = VALUE_PATTERN.findall(payload)
                for data in values:
                    match_pattern = KEY_EQUAL_VALUE_PATTERN.match(data)
                    if match_pattern is not None:
                        key = match_pattern.group(1)
                        value = match_pattern.group(2)
                        if value is not None:
                            # Values may optionally be enclosed in single
                            # or double quotes
                            value = value.lstrip("\"'")
                            value = value.rstrip("\"'")
                    else:
                        key = data
                        value = None
                    payload_dict[key] = value
                line = key_value.strip()
            except ValueError:
                line_continued = line
                continue
        except ValueError:
            payload_dict = None
        try:
            key, value = line.split("=", 1)
            if value == "":
                # We got a invalid syntax of:
                # key=
                raise ValueError()
            values = VALUE_PATTERN.findall(value)
            if len(values) > 1:
                # This means we got a invalid syntax of:
                # key=value value1
                generate_error(LVL_PROCESS, conv_report,
                               _("invalid syntax, statement does not conform "
                                 "to key=value syntax"), extra_log_params)
                continue
            if key in ["network_interface", "name_service"]\
                and payload_dict is None:
                # At this point we may or may not have a complete entry
                # as the {} are optional and they could start on the next
                # line.  So what we want to do is cheat and look at the
                # next line and see if it starts with a {
                if lineno + 1 < len(lines):
                    next_line = lines[lineno + 1]
                    if next_line is not None and next_line != "" \
                        and next_line[0] == "{":
                        line_continued = line
                        continue
        except ValueError:
            if line == "":
                generate_error(LVL_PROCESS, conv_report,
                               _("invalid entry, keyword missing"),
                               extra_log_params)
            else:
                generate_error(LVL_PROCESS, conv_report,
                               _("invalid entry, value for keyword missing: "
                                  "%(line)s") % {"line": line},
                               extra_log_params)
            continue
        if payload_dict:
            values = [value, payload_dict]
        else:
            values = [value]
        sysidcfg.data[line_start] = \
            KeyValues(key.lower(), values, line_start)

    if line_continued is not None:
        # What we are testing for here is whether we started reading
        # a line like
        # network_interface=eri0 {primary
        #           hostname=host1
        #           ip_address=192.168.2.7
        #           netmask=255.255.255.0
        #           protocol_ipv6=no
        #           default_route=192.168.2.1
        #
        # where the user forgot to add the missing }
        # this is a serious error.  Don't process the file
        # if this error occurs
        generate_error(LVL_PROCESS, conv_report,
                       _("invalid entry, missing closing '}'"),
                       extra_log_params)
        conv_report.conversion_errors = None
        conv_report.unsupported_items = None
    sysidcfg.conversion_report = conv_report
    return sysidcfg


def read_profile(src_dir, profile_name, verbose):
    """Reads the specified jumpstart profile file and returns a dictionary
       of the parsed rules

       Arguments:
       src_dir - the source directory for the jumpstart files
       profile_name - the jumpstart profile file to read
       verbose - verbose ouptut (true/false)

       Returns:
       ProfileData - the data read for the profile

    """

    if src_dir is None or profile_name is None:
        raise ValueError

    if verbose:
        print _("Processing profile: %s" % profile_name)

    profile_data = ProfileData(profile_name)
    filename = os.path.join(src_dir, profile_name)
    if not os.path.isfile(filename):
        raise IOError(_("No such profile found: %s" % filename))

    profile_dict = profile_data.data

    try:
        with open(filename, "r") as f_handle:
            lines = map(clean_line, f_handle.readlines())
    except IOError:
        raise IOError(_("Failed to read profile: %s" % filename))

    conv_report = ConversionReport()
    extra_log_params = {LOG_KEY_FILE: profile_name, LOG_KEY_LINE_NUM: 0}
    for lineno, line in enumerate(lines):
        # skip blank
        if not line:
            continue
        line_num = lineno + 1
        extra_log_params[LOG_KEY_LINE_NUM] = line_num
        try:
            # split on whitespace a maximum of 1 time
            key, value = line.split(" ", 1)
        except ValueError:
            generate_error(LVL_PROCESS, conv_report,
                           _("invalid entry, value for keyword '%(line)s' "
                             "missing") % {"line": line}, extra_log_params)
            continue
        values = VALUE_PATTERN.findall(value)
        profile_dict[line_num] = KeyValues(key.lower(), values, line_num)

    profile_data.conversion_report = conv_report
    return profile_data


def fetch_ai_profile_dir(directory, profile_name):
    """Return the profile diectory path for the specified profile_name"""
    return os.path.join(directory, AI_PREFIX + profile_name)


def convert_rule(rule_data, rule_num, profile_name, conversion_report,
                 directory, verbose):
    """Take the rule_data dict and output it in the specified dir

       Arguments:
       rule_data - the dict of rule key value pairs
       rule_num - the rule number from the order found in the rules file
       profile_name - the name of the profile
       conversion_report - the convertion report for tracking errors
       directory - the directory where to output the new profile to
       verbose - verbose output (true/false)

       Returns: None
       Raises IOError if rule file not found
       Raises ValueError if rule_data is empty

    """

    if rule_data is None:
        raise ValueError

    if verbose:
        print _("Generating criteria data for: %s") % profile_name

    xml_rule_data = XMLRuleData(rule_data, conversion_report)

    root = xml_rule_data.root

    if root is not None:
        # Write out the xml document
        prof_path = fetch_ai_profile_dir(directory, profile_name)
        filename = ("criteria-%s.xml") % rule_num
        write_xml_data(root, prof_path, filename)


def output_profile(tree, prof_path, profile_name, arch, skip_validation,
                   conversion_report, verbose):
    """Output the profile for the specified xml tree.  If skip_validation
       is set to False,  validate the xml tree and recorded any errors in
       the conversion report

    """
    # Write out the xml document
    prof_file = "%(name)s.%(arch)s.xml" % \
                {"name": profile_name,
                 "arch": arch}
    if verbose:
        print _("Generating %(arch)s manifest for: %(profile)s" %
                {"arch": arch,
                 "profile": profile_name})
    write_xml_data(tree, prof_path, prof_file)
    if skip_validation:
        conversion_report.validation_errors = None
    else:
        # Perform a validation
        validate(profile_name, prof_path, prof_file,
                 DEFAULT_AI_DTD_FILENAME,
                 conversion_report, verbose)


def convert_profile(profile_data, dest_dir, default_xml,
                    local, skip_validation, verbose):
    """Take the profile_data dictionary and output it in the jumpstart 11
       style in the specified directory

       Arguments:
       profile_data - dictionary of profile key value pairs
       dest_dir - the directory where to output the new profile to
       default_xml - the object contains the xml tree to merge changes into
       local - local only package name lookup (true/false)
       skip_validation -- skip validation (true/false)
       verbose - verbose output (true/false)

       Returns: None

    """
    if profile_data is None:
        raise ValueError

    profile_name = profile_data.name
    # A profile name of '-' indicates that it's an interactive profile
    # The data fields for this profile will be empty if the dictionary has
    # no entries in it
    if profile_name == "-":
        return

    if verbose:
        print _("Performing conversion on: %s") % profile_name

    xml_profile_data = XMLProfileData(profile_name, profile_data.data,
                                      profile_data.conversion_report,
                                      default_xml, local)

    if xml_profile_data.tree is not None:
        # Write out the xml document
        prof_path = fetch_ai_profile_dir(dest_dir, profile_name)
        if xml_profile_data.architecture is None:
            # If the architecture is NONE then this implies the
            # profile is not architecture specific.  As such we'll have
            # to generate a profile for both x86 and for sparc
            output_profile(xml_profile_data.fetch_tree(ARCH_X86),
                           prof_path, profile_name,
                           ARCH_X86,
                           skip_validation,
                           profile_data.conversion_report,
                           verbose)
            output_profile(xml_profile_data.fetch_tree(ARCH_SPARC),
                           prof_path, profile_name,
                           ARCH_SPARC,
                           skip_validation,
                           profile_data.conversion_report,
                           verbose)
        else:
            # The architecture is specified.  Only output one profile manifest
            output_profile(xml_profile_data.tree, prof_path, profile_name,
                           xml_profile_data.architecture,
                           skip_validation,
                           profile_data.conversion_report,
                           verbose)
    else:
        profile_data.conversion_report.validation_errors = None


def convert_rules_and_profiles(rules_profile, dest_dir, xml_default_data,
                               local, skip_validation, verbose):
    """Takes the rules and profile data and outputs the new solaris 11
       jumpstart rules and profiles data

       Arguments:
       ruleProfiles -- the rule/profile data to output
       dest_dir -- the directory where to output to
       xml_default_data - the XMLDefaultData object that contains the base
          xml tree that will be copied and then merged into
       local -- local only package name lookup (true/false)
       skip_validation -- skip validation (true/false)
       verbose  -- verbose output (true/false)

       Returns: None

    """

    profile_names = str()

    rules_data = rules_profile.rules_file_data
    if rules_data is not None:
        # Do conversion on rule Data
        # Update conversion report data with failures
        if verbose:
            print _("Performing conversion on: %s") % RULES_FILENAME

        rule_conv_report = rules_data.conversion_report
        rules_dict = rules_data.data

        # The key's for the rules_dict is the rule #
        # The rules are read in order and given a number based on there order
        # in the rules files
        profiles = rules_profile.defined_profiles
        for rule_num, defined_rule in rules_dict.iteritems():
            # Get the data for each rule
            profile = defined_rule.profile_name
            if profile == "-":
                continue
            # Check to see if we're already processed this profile from
            # another rule. If we have already processed it move to the
            # next rule.
            if profile not in profile_names:
                convert_rule(defined_rule, rule_num, profile, rule_conv_report,
                             dest_dir, verbose)
                convert_profile(profiles[profile], dest_dir, xml_default_data,
                                local, skip_validation, verbose)
                # Save the processed profile name in the list of profiles
                profile_names = profile_names + " " + profile


def convert_sysidcfg(sysidcfg, dest_dir, skip_validation, verbose):
    """Take the sysidcfg data object and output it in the jumpstart 11
       style in the specified directory

       Arguments:
       sysidcfg - dictionary of profile key value pairs
       dest_dir - the directory where to output the new profile to
       skip_validation -- skip validation (true/false)
       verbose - verbose output (true/false)

       Returns: None

    """
    if sysidcfg is None:
        raise ValueError

    filename = sysidcfg.name
    if verbose:
        print _("Performing conversion on: %s") % filename

    sysidcfg_data = XMLSysidcfgData(sysidcfg.data,
                                    sysidcfg.conversion_report)
    if sysidcfg_data.tree is not None:
        # Write out the xml document
        if verbose:
            print _("Generating SC Profile")
        write_xml_data(sysidcfg_data.tree, dest_dir, SC_PROFILE_FILENAME)
        if skip_validation:
            sysidcfg.conversion_report.validation_errors = None
        else:
            validate(sysidcfg.name, dest_dir, SC_PROFILE_FILENAME,
                     DEFAULT_SC_PROFILE_DTD_FILENAME,
                     sysidcfg.conversion_report, verbose)


def process_profile(filename, source_dir, dest_dir, default_xml_tree, local,
                    skip_validation, verbose):
    """Take the read in profile data specified by the user and outputs
       the converted solaris 11 profile data to the specified directory

       Arguments:
       filename - the name of the profile file to convert
       source_dir - the name of the source directory
       dest_dir - the directory where to output the new profile to
       default_xml_tree - the xml profile to merge changes into
       local - local only package name lookup (true/false)
       skip_validation -- skip validation (true/false)
       verbose - verbose output (true/false)

       Returns: ProfileData
       Raises IOError if file not found

    """
    if filename == '-':
        # Interactive profile.  Return a empty profile dataset
        return ProfileData(filename)

    profile_data = read_profile(source_dir, filename, verbose)

    # We were able to successfully read (process) the profile
    # Begin the conversion process
    convert_profile(profile_data, dest_dir, default_xml_tree, local,
                    skip_validation, verbose)

    return profile_data


def process_rule(src_dir, dest_dir, xml_default_data, local, skip_validation,
                 verbose):
    """Reads in the rule file and outputs the converted solaris 11 rule file
       to the specified directory.  For every profile referenced in the
       rule file it converts those profiles to the equivalent solaris 11
       profile file to the specified directory

       Arguments:
       src_dir -- the directory where to read the rules file from
       dest_dir -- the directory where to output the new rule/profile files to
       xml_default_data - the XMLDefaultData object that contains the xml tree
            that will be merged into
       local -- local only package name lookup (true/false)
       skip_validation -- skip validation (true/false)
       verbose  -- verbose output (true/false)

       Returns: ProcessedData

    """
    if src_dir is None or dest_dir is None:
        raise ValueError

    rule_data = read_rules(src_dir, verbose)
    raap = ProcessedData(rule_data)
    if rule_data is None:
        return raap
    rules_dict = rule_data.data
    if rules_dict is None:
        return raap

    # The rule file has been successfully read.
    profiles = raap.defined_profiles

    # For each profile referenced in the rule file read and parse
    # the profile file collecting the key value pairs for that profile
    # Add the resulting data to the profiles dictionary
    for defined_rule in rules_dict.itervalues():
        profile_name = defined_rule.profile_name
        if profile_name != "-":
            # A profile was specified for this rule
            # see if we've already processed this profile
            if profile_name in profiles:
                profile_data = profiles[profile_name]
                if profile_data:
                    continue

            try:
                profile_data = read_profile(src_dir, profile_name, verbose)
            except IOError as msg:
                profile_data = ProfileData(profile_name)
                profile_data.conversion_report = \
                    ConversionReport(1, None, None, None)
                err(msg)

            profiles[profile_name] = profile_data

    # The rule file and profile files associated with the rule file
    # have all been processed.
    convert_rules_and_profiles(raap, dest_dir, xml_default_data, local,
                               skip_validation, verbose)
    return raap


def process_sysidcfg(source_dir, dest_dir, skip_validation, verbose):
    """Read in and process the sysidcfg file specified by the user

       Arguments:
       source_dir - the name of the source directory
       dest_dir - the name of the destination (output) directory
       skip_validation -- skip validation (true/false)
       verbose - verbose output (true/false)

       Returns: ProfileData object containing the sysidcfg data
       Raises IOError if file not found

    """

    sysidcfg = read_sysidcfg(source_dir, verbose)

    convert_sysidcfg(sysidcfg, dest_dir, skip_validation, verbose)
    return sysidcfg


def perform_validation(filename, verbose):
    """Perform validation of the specified file"""
    tree = etree.parse(filename)

    # Determine whether we are validating a manifest or SC Profile
    node = fetch_xpath_node(tree, "/auto_install/ai_instance")
    if node is None:
        node = fetch_xpath_node(tree,
                                "/service_bundle[@type='profile']")
        if node is None:
            raise ValueError(_("%(filename)s does not conform to the "
                           "expected layout of manifest file or "
                           "sc profile") %
                           {"filename": filename})
        dtd_filename = DEFAULT_SC_PROFILE_DTD_FILENAME
    else:
        dtd_filename = DEFAULT_AI_DTD_FILENAME

    manifest_path, manifest_filename = os.path.split(filename)
    profile_name, remainder = manifest_filename.rsplit(".", 1)
    processed_data = ProcessedData(None)
    profile_data = ProfileData(profile_name)
    profile_data.conversion_report = \
        ConversionReport(process_errs=None, conversion_errs=None,
                         unsupported_items=None, validation_errs=0)
    processed_data.add_defined_profile(profile_data)
    validate(profile_name, manifest_path, manifest_filename, dtd_filename,
             profile_data.conversion_report, verbose)
    return processed_data


def output_report_data(name, report):
    """Output the data from a single conversion report"""
    # A conversion error and unsupported items count may be None
    # This will occur if a process error prevented any of the file
    # from being processed.  In this case we don't want to output
    # a zero.  Instead we use "-" to represent to the user there
    # is no value for this field
    if report.warnings is None:
        warnings = "-"
    else:
        warnings = str(report.warnings)
    if report.process_errors is None:
        process_err_cnt = "-"
    else:
        process_err_cnt = str(report.process_errors)
    if report.conversion_errors is None:
        conv_err_cnt = "-"
    else:
        conv_err_cnt = str(report.conversion_errors)

    if report.unsupported_items is None:
        unsupported_cnt = "-"
    else:
        unsupported_cnt = str(report.unsupported_items)

    if report.validation_errors is None:
        val_err_cnt = "-"
    else:
        val_err_cnt = str(report.validation_errors)
    print _("%(name)-20s  %(warnings)8s  %(process)7s  %(unsupported)11s"
            "  %(conv)10s  %(validation)10s") % \
          {"name": os.path.basename(name),
          "warnings": warnings,
          "process": process_err_cnt,
          "unsupported": unsupported_cnt,
          "conv": conv_err_cnt,
          "validation": val_err_cnt}


def output_report(process_data, dest_dir, verbose):
    """Outputs a report on the conversion of the jumpstart files.  If verbose
       is False only files that have failures are reported

       Arguments
       process_data - the data object containing the conversion reports
            for all the rules and profiles
       dest_dir -- the directory where the log file was outputed to
       verbose  -- if True output info for all reports, False only failures

    """
    if process_data is None:
        raise ValueError

    rule_report = None
    rule_data = process_data.rules_file_data
    if rule_data is not None:
        rule_report = rule_data.conversion_report

    profiles = process_data.defined_profiles
    error_found = False
    errors = 0
    if not verbose:
        if rule_report is not None and rule_report.has_errors():
            error_found = True
        else:
            if profiles is not None:
                for profile_data in profiles.itervalues():
                    report = profile_data.conversion_report
                    if report.has_errors():
                        error_found = True
                        break

    if verbose or error_found:
        print _("                                Process  Unsupported  "
                "Conversion  Validation\n"
                "Name                  Warnings  Errors   Items        "
                "Errors      Errors\n"
                "-------------------   --------  -------  -----------  "
                "----------  ----------")

        # Always output the rule report 1st
        if rule_report is not None:
            errors = rule_report.error_count()
            if verbose or errors:
                output_report_data(RULES_FILENAME, rule_report)

        # Followed by the reports of the various profiles
        # Sort based on name
        if profiles is not None:
            keylist = profiles.keys()
            keylist.sort()
            for key in keylist:
                profile = profiles[key]
                report = profile.conversion_report
                if verbose or report.has_errors():
                    output_report_data(profile.name, report)
                    errors += report.error_count()

    if errors > 0:
        print _("\nConversion completed. One or more failures occurred.\n"\
            "For errors see %s") % (os.path.join(dest_dir, LOGFILE))
        ret_code = EXIT_ERROR
    else:
        print _("Successfully completed conversion")
        ret_code = EXIT_SUCCESS
    return ret_code


def build_option_list():
    """ function to parse command line arguments to js2ai"""
    desc = _("Utility for converting Solaris 10 jumpstart rules, " \
             "profiles, and sysidcfg files to Solaris 11 compatible AI "
             "manifests and SC profiles")
    usage = _("usage: %prog [-h][--version]\n"
              "       %prog -r | -p <profile_name> [-d <jumpstart_dir>]"
              "[-D <dest_dir>] [-lSv]\n"
              "       %prog -s [-d <jumpstart_dir>] [-D <dest_dir>] [-Sv]\n"
              "       %prog -V <manifest>\n")
    parser = OptionParser(version=VERSION, description=desc, usage=usage)

    parser.add_option("-d", "--dir", dest="source", default=".",
                      action="store", type="string", nargs=1,
                      metavar="<jumpstart_dir>",
                      help=_("jumpstart directory containing origional " + \
                             "rule and profile files or sysidcfg file"))
    parser.add_option("-D", "--dest", dest="destination", default=None,
                      action="store", type="string", nargs=1,
                      metavar="<destination_dir>",
                      help=_("directory to output results to. Default "
                      "destination directory is the source directory"))
    # Auto install profile to use as basis for conversion.  Defaults to
    # DEFAULT_AIL_FILENAME
    parser.add_option("-i", "--initial", dest="default_xml",
                      default=None,
                      action="store", type="string", nargs=1,
                      metavar="<auto_install_profile>",
                      help=SUPPRESS_HELP)
    parser.add_option("-l", "--local", dest="local", default=False,
                      action="store_true",
                      help=_("local only.  No remote package name lookup"))
    parser.add_option("-p", "--profile", dest="profile", default=None,
                      action="store", type="string", nargs=1,
                      metavar="<profile>",
                      help=_("convert the specified JumpStart profile and "
                             "generate a manifest for the profile processed. "
                             "In this case no criteria file is needed or "
                             "generated."))
    parser.add_option("-r", "--rule", dest="rule", default=False,
                      action="store_true",
                      help=_("convert rule and associated profiles and "
                             "generate a manifest for each profile "
                             "processed."))
    parser.add_option("-s", "--sysidcfg", dest="sysidcfg", default=False,
                      action="store_true",
                      help=_("process the sysidcfg file and generate the "
                             "correspond SC Profile"))
    parser.add_option("-S", "--skip", dest="skip", default=False,
                      action="store_true",
                      help=_("skip validation"))
    parser.add_option("-v", "--verbose", dest="verbose", default=False,
                      action="store_true",
                      help="output processing steps")
    parser.add_option("-V", dest="validate", default=False,
                      action="store", type="string", nargs=1,
                      metavar="<manifest>",
                      help="Validate the specified manifest")
    return parser


def parse_args(parser, options, args):
    """Parse the command line arguments looking for argument errors"""
    # Verify that directory user created exists.  If not exit
    if not os.path.isdir(options.source):
        err(_("specified jumpstart directory does not "
                       "exist: %s\n" % options.source))
        return EXIT_IO_ERROR
    if options.destination is None:
        options.destination = os.getcwd()
    else:
        if not os.path.isdir(options.destination):
            err(_("specified destination directory does not " + \
                           "exist: %s\n" % options.destination))
            return EXIT_IO_ERROR
    if options.validate:
        if options.rule or options.profile or \
            options.sysidcfg or options.default_xml:
            parser.error(_("-V option must not be used with any other option"))
    elif not options.rule and not options.profile and \
        not options.sysidcfg:
        parser.error(_("required options -r, -p, or -s must be specified"))

    if options.rule and options.profile is not None:
        parser.error(_("-r and -p options are mutually exclusive"))

    if options.rule and options.sysidcfg:
        parser.error(_("-r and -s options are mutually exclusive"))

    if options.profile and options.sysidcfg:
        parser.error(_("-p and -s options are mutually exclusive"))

    if options.default_xml and options.sysidcfg:
        parser.error(_("-i and -s options are mutually exclusive"))

    if options.local and options.sysidcfg:
        parser.errors(_("-l and -s options are mutually exclusive"))

    if options.skip and options.validate:
        parser.error(_("-S and -V options are mutually exclusive"))

    if options.default_xml is None:
        if os.path.isfile(DEFAULT_AI_FILENAME):
            options.default_xml = DEFAULT_AI_FILENAME
    elif options.default_xml.lower() == "none":
        options.default_xml = None
    elif not os.path.isfile(options.default_xml):
        err(_("no such file found: %s\n") % options.default_xml)
        return EXIT_IO_ERROR

    # Check and handle the condition where user specified -p with a path to
    # the profile
    if options.profile:
        profile = os.path.basename(options.profile)
        if options.profile != profile:
            options.source = os.path.dirname(options.profile)
            options.profile = profile
    return EXIT_SUCCESS


def process(options):
    """Invoke operation requested by the user via the command line"""
    if options.sysidcfg:
        sysidcfg_data = process_sysidcfg(options.source,
                                         options.destination,
                                         options.skip,
                                         options.verbose)
        processed_data = ProcessedData(None)
        processed_data.add_defined_profile(sysidcfg_data)

    elif options.profile:
        xml_default_data = XMLDefaultData(options.default_xml)
        profile_data = process_profile(options.profile,
                                       options.source,
                                       options.destination,
                                       xml_default_data,
                                       options.local,
                                       options.skip,
                                       options.verbose)
        processed_data = ProcessedData(None)
        processed_data.add_defined_profile(profile_data)
    elif options.rule:
        xml_default_data = XMLDefaultData(options.default_xml)
        processed_data = process_rule(options.source,
                                      options.destination,
                                      xml_default_data,
                                      options.local,
                                      options.skip,
                                      options.verbose)
    elif options.validate:
        processed_data = perform_validation(options.validate, options.verbose)
    if options.verbose:
        print "\n"
    return processed_data


def main():
    """js2ai's main function

       Exit Codes:
        0 - Success
        1 - IO Error
        2 - Options Error
        3 - Internal Error
        4 - Manifest validation error
        5 - Conversion/Process/Unknown Item error occurred during conversion

    """

    parser = build_option_list()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(EXIT_SUCCESS)

    (options, args) = parser.parse_args()
    exit_code = parse_args(parser, options, args)
    if exit_code != EXIT_SUCCESS:
        sys.exit(exit_code)

    processed_data = None
    try:
        # set up logging
        logger_setup(options.destination)

        errsvc.clear_error_list()
        processed_data = process(options)
    except IOError, msg:
        err(msg)
        exit_code = EXIT_IO_ERROR
    except ValueError, msg:
        err(msg)
        exit_code = EXIT_ERROR
    except Exception, msg:
        # Unexpected error condition
        # Write out exception stack trace to error log file
        exc_type, exc_value, exc_tb = sys.exc_info()
        err_filename = os.path.join(options.destination, ERRFILE)
        with open(err_filename, "w") as handle:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
        err(_("%(err_msg)s. An unexpected error "
              "occurred, if the problem persists contact your "
              "Oracle customer service representative to report "
              "the problem. Details of the problem to report "
              "are stored in %(err_log)s\n") %
              {"err_msg": msg, "err_log": err_filename})
        sys.exit(EXIT_INTERNAL_ERROR)

    if processed_data is not None:
        code = output_report(processed_data, options.destination,
                             options.verbose)
        if exit_code == EXIT_SUCCESS:
            exit_code = code

    # Close and flush the logfile.  We don't use logging.shutdown()
    # since it will break a number of our testing scenarios
    if logfile_handler is not None:
        LOGGER.removeHandler(logfile_handler)
        logfile_handler.flush()
        logfile_handler.close()
    if exit_code:
        # Sort the log file.  Due to the way that we process the rules,
        # profiles, and sysidcfg the log file will not be in a sorted
        # based on the format (name:line_no) used by the log file
        logger_sort(logfile_name)

    # Add any validation errors to the end of the log file
    validation_errors = errsvc.get_errors_by_mod_id(ERR_VAL_MODID)
    if len(validation_errors) > 0:
        add_validation_errors(logfile_name, validation_errors)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

import gettext
import logging
import os
import os.path
import re
import sys

from common import ConversionReport
from common import KeyValues
from common import ProfileData
from conv import XMLProfileData
from conv import XMLRuleData
from optparse import OptionParser

VERSION = "%prog: 1.0"

COMMENT_PATTERN = re.compile("^([^#]*)#.*")
KEY_VALUE_PATTERN = re.compile("^(\S*)\s*(\S*)", re.I)
VALUE_PATTERN = re.compile("\s*(\S+)")
SPACE_PATTERN = pattern = re.compile("\s+")
MULTILINE_PATTERN1 = re.compile("([^&]*)(\\\\)(.*)$")
MULTILINE_PATTERN2 = re.compile("([^&]*)(&&)(.*)$")
RULE_STRIP_PATTERN = re.compile("^\s*(\w+)\s+(\w+)\s+(\w+)\s+(\w+).+")

_ = gettext.translation("js2ai", "/usr/share/locale", fallback=True).gettext

RULES_FILENAME = "rules"
LOGFILE = "js2ai.log"
FILE_PREFIX = "/AI_"

# LOGGER is for logging all processing, conversion, unknown items errors
# so that the user can review the failures and take steps to fix them
LOGGER = logging.getLogger('js2ai')


class RulesAndAssociatedProfiles(object):
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
            for key, data in defined_rule.key_values_dict.iteritems():
                if first_line:
                    # We don't tab the first line
                    first_line = False
                else:
                    # Tab the line out so that we position all keys
                    # beyond the first at the position necessary
                    # for outputing key
                    print "\t\t\t\t\t ",
                print "%-10s  %s" % (data._key, data._values)


class DefinedRule(object):
    """A user defined rule in a jumpstart rule file"""
    _index = 0

    def __init__(self, begin_script, profile, end_script):
        self._begin_script = begin_script
        self._profile = profile
        self._end_script = end_script
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
    LOGGER.setLevel(logging.INFO)
    # create console handler and set level to debug
    log_filename = os.path.join(log_directory, LOGFILE)
    try:
        ch = logging.FileHandler(log_filename, 'w')
    except IOError, err:
        # err is cast to str here since it is possible for it to be None
        sys.stderr.write(_("Failed to open log file: %s\n") % str(err))
        sys.exit(-1)

    # add formatter to ch
    ch.setFormatter(logging.Formatter("%(message)s"))
    # add ch to logger
    LOGGER.addHandler(ch)


def clean_line(line):
    """Process the line removing the tailing comments and extra spaces"""
    match_pattern = COMMENT_PATTERN.match(line)
    if match_pattern is not None:
        line = match_pattern.group(1)

    # Find all tabs and extra spaces between the words
    # and replace with a single space
    return SPACE_PATTERN.sub(" ", line.strip())


def read_rules(src_dir, rule_name, verbose):
    """Reads the specified jumpstart rules file and returns a dictionary
    of the parsed rules

    Arguments:
    src_dir -- The directory containing the rules file
    rule_name -- the jumpstart rule file to read
    verbose  -- verbose ouptut (true/false)

    Returns:
    RuleFileData - the data read from the rules files

    """
    if src_dir is None or rule_name is None:
        raise ValueError
    filename = os.path.join(src_dir, rule_name)
    if verbose:
        print _("Processing Rule: %s") % rule_name

    if not os.path.isfile(filename):
        sys.stderr.write(_("No such file found: %s\n") % filename)
        sys.exit(-1)

    try:
        with open(filename, "r") as f:
            conv_report = ConversionReport()
            lines = [clean_line(line) for line in f.readlines()]
    except IOError:
        raise IOError(_("Failed to read rules file: %s" % filename))

    rules_dict = dict()
    rule_index = 1
    conv_report = ConversionReport()
    defined_rule = None
    line_num = 0
    line_cnt = len(lines)
    while line_num < line_cnt:
        if defined_rule is not None:
            LOGGER.error(_("%(file)s: line %(lineno)d: " \
                           "Incomplete rule detected") % \
                           {"file": rule_name, "lineno": line_num})
            conv_report.add_process_error()
            # Throw away the old defined rule, it's incomplete
            defined_rule = None

        line = lines[line_num]
        line_num += 1
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
                    LOGGER.error(_("%(file)s: line %(line_num)d: "
                                   "invalid rule. Does not conform to "
                                   "required format of <key> <value> "
                                   "<begin_script> <profile> "
                                   "<end_script>: %(line)s") %
                                   {"file": rule_name, \
                                    "line_num": line_num, \
                                    "line": line})
                    defined_rule = None
                    line = None
                    conv_report.add_process_error()
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
                        LOGGER.error(_("%(file)s: line %(line_num)d: "
                                     "profile not found: %(prof)s") % \
                                     {"file": rule_name, \
                                     "line_num": line_num, \
                                     "prof": profile})
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
                LOGGER.error(_("%(file)s: line %(line_num)d: invalid "
                               "rule. No value defined for key: "
                               "%(line)s") % {"file": rule_name, \
                                              "line_num": line_num, \
                                              "line": kv_pairs})
                defined_rule = None
                conv_report.add_process_error()
                line = None
                continue

            value_entries = VALUE_PATTERN.findall(values)
            defined_rule.add_key_values(key, value_entries, line_num)

            if not match_pattern1 and not match_pattern2:
                rules_dict[rule_index] = defined_rule
                rule_index = rule_index + 1
                defined_rule = None

    if rule_index == 0:
        # Failed to read in any valid rules.  There's nothing else to
        # do so exit
        sys.stderr.write(_("invalid rule file.  No rules found\n"))
        sys.exit(-1)
    if defined_rule is not None:
        LOGGER.error(_("%(file)s: line %(lineno)d: " \
                       "Incomplete rule detected") % \
                       {"file": rule_name, "lineno": line_num})
        conv_report.add_process_error()
    return RulesFileData(rules_dict, conv_report)


def read_profile(src_dir, profile_name, verbose):
    """Reads the specified jumpstart profile file and returns a dictionary
    of the parsed rules

    Arguments:
    src_dir -- The source directory for the jumpstart files
    profile_name -- the jumpstart profile file to read
    verbose  -- verbose ouptut (true/false)

    Returns:
    ProfileData - the data read for the profile

    """

    if src_dir is None or profile_name is None:
        raise ValueError

    if verbose:
        print _("Processing Profile: %s" % profile_name)

    profile_data = ProfileData(profile_name)
    filename = os.path.join(src_dir, profile_name)
    if not os.path.isfile(filename):
        raise IOError(_("No such profile found: %s" % filename))

    profile_dict = profile_data.data

    try:
        with open(filename, "r") as f:
            conv_report = ConversionReport()
            lines = [clean_line(line) for line in f.readlines()]
    except IOError:
        raise IOError(_("Failed to read profile: %s" % filename))

    for lineno, line in enumerate(lines):
        # skip blank
        if not line:
            continue

        try:
            # split on whitespace a maximum of 1 time
            key, value = line.split(" ", 1)
        except ValueError:
            LOGGER.error(_("%(file)s: line %(lineno)d: invalid entry, "
                         "value for keyword '%(line)s' missing") % \
                         {"file": profile_name, \
                          "lineno": (lineno + 1), \
                          "line": line})
            conv_report.add_process_error()
            continue
        values = VALUE_PATTERN.findall(value)
        profile_dict[lineno + 1] = KeyValues(key, values, lineno + 1)

    profile_data.conversion_report = conv_report
    return profile_data


def convert_rule(rule_data, rule_num, profile_name, conversion_report,
                 directory, verbose):
    """Take the rule_data dict and output it in the specified dir

    Args:
    rule_data -- the dict of rule key value pairs
    rule_num -- the rule number rom the order found in the rules file
    conversion_report -- the convertion report for tracking errors
    directory -- the directory where to output the new profile to
    verbose  -- verbose output (true/false)

    Returns: None

    """

    if rule_data is None:
        raise ValueError

    xml_rule_data = XMLRuleData(rule_num, rule_data, conversion_report, LOGGER)

    root = xml_rule_data.root

    if root is not None:
        # Write out the xml document
        prof_path = directory + FILE_PREFIX + profile_name
        crit_file = prof_path + ("/criteria-%s.xml") % rule_num
        if not os.path.exists(prof_path):
            try:
                os.makedirs(prof_path)
            except OSError, msg:
                sys.stderr.write(_("Failed to create directory: %s\n" % msg))
                sys.exit(-1)
        xml_rule_data.write_to_file(crit_file)


def convert_profile(profile_data, directory, local, verbose):
    """Take the profile_data dictionary and output it in the jumpstart 11
    style in the specified directory

    Arguments:
    profile_data -- dictionary of profile key value pairs
    directory -- the directory where to output the new profile to
    local -- local only package name lookup (true/false)
    verbose  -- verbose output (true/false)

    Returns: None

    """
    if profile_data is None:
        raise ValueError

    profile_name = profile_data.name
    # A profile name of '-' indicates that it's an interactive profile
    # The data fields for this profile will be empty the dictionary will
    # no entries
    if profile_name == "-":
        return

    if verbose:
        print _("Performing conversion on: %s") % profile_name

    xml_profile_data = XMLProfileData(profile_name, profile_data.data,
                                      profile_data.conversion_report,
                                      local, LOGGER)

    root = xml_profile_data.root

    if root is not None:
        # Write out the xml document
        prof_path = directory + FILE_PREFIX + profile_name
        prof_file = prof_path + "/" + profile_name + ".xml"
        if not os.path.exists(prof_path):
            try:
                os.makedirs(prof_path)
            except Exception, msg:
                sys.stderr.write(_("Failed to create directory: %s\n" % msg))
                sys.exit(-1)

        xml_profile_data.write_to_file(prof_file)


def convert_rules_and_profiles(rules_profile, directory, local, verbose):
    """Takes the rules and profile data and outputs the new solaris 11
    jumpstart rules and profiles data

    Arguments:
    ruleProfiles -- the rule/profile data to output
    directory -- the directory where to output to
    local -- local only package name lookup (true/false)
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
                convert_profile(profiles[profile], directory, local, verbose)
                # Save the processed profile name in the list of profiles
                profile_names = profile_names + " " + profile
            convert_rule(defined_rule, rule_num, profile, rule_conv_report,
                         directory, verbose)


def process_profile(filename, source_dir, directory, local, verbose):
    """Take the read in profile data specified by the user and outputs
    the converted solaris 11 profile data to the specified directory

    Arguments:
    filename -- the name of the profile file to convert
    source_dir -- the name of the source directory
    directory -- the directory where to output the new profile to
    local -- local only package name lookup (true/false)
    verbose  -- verbose output (true/false)

    Returns: ProfileData

    """
    if filename == '-':
        # Interactive profile.  Return a empty profile dataset
        return ProfileData(filename)

    try:
        profile_data = read_profile(source_dir, filename, verbose)
    except IOError, msg:
        sys.stderr.write("%s\n" % str(msg))
        sys.exit(-1)

    # We were able to successfully read (process) the profile
    # Begin the conversion process
    convert_profile(profile_data, directory, local, verbose)

    return profile_data


def process_rule(rule_name, src_dir, dest_dir, local, verbose):
    """Reads in the rule file specified by the user and outputs the converted
    solaris 11 rule file to the specified directory.  For every profile
    referenced in the rule file it converts those profiles to the equivalent
    solaris 11 profile file to the specified directory

    Arguments:
    filename -- the name of the rule file to convert
    dest_dir -- the directory where to output the new rule/profile files to
    local -- local only package name lookup (true/false)
    verbose  -- verbose output (true/false)

    Returns: RulesAndAssociatedProfiles

    """
    if rule_name is None or src_dir is None or dest_dir is None:
        raise ValueError

    rule_data = read_rules(src_dir, rule_name, verbose)
    rp = RulesAndAssociatedProfiles(rule_data)
    if rule_data is None:
        return rp
    rules_dict = rule_data.data
    if rules_dict is None:
        return rp

    # The rule file has been successfully read.
    profiles = rp.defined_profiles

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
            except IOError, msg:
                profile_data = ProfileData(profile_name)
                profile_data.conversion_report = \
                    ConversionReport(1, None, None)
                sys.stderr.write("%s\n" % str(msg))

            profiles[profile_name] = profile_data

    # The rule file and profile files associated with the rule file
    # have all been processed.
    convert_rules_and_profiles(rp, dest_dir, local, verbose)
    return rp


def output_report_data(name, report):
    """Output the data from a single conversion report"""
    # A conversion error and unsupported items count may be None
    # This will occur if a process error prevented any of the file
    # from being processed.  In this case we don't want to output
    # a zero.  Instead we use "-" to represent to the user there
    # is no value for this field
    if report.conversion_errors is None:
        conv_err_cnt = "-"
    else:
        conv_err_cnt = str(report.conversion_errors)

    if report.unsupported_items is None:
        unsupported_cnt = "-"
    else:
        unsupported_cnt = str(report.unsupported_items)
    print _("%(name)-20s  %(process)12d  %(unsupported)12s  %(conv)12s") % \
          {"name": name,
          "process": report.process_errors,
          "unsupported": unsupported_cnt,
          "conv": conv_err_cnt}


def output_report(rule_and_profile_data, dest_dir, verbose):
    """Outputs a report on the conversion of the jumpstart files.  If verbose
    is False only files that have failures are reported

    Arguments
    rule_and_profile_data - the data object containing the conversion reports
        for all the rules and profiles
    dest_dir -- the directory where the log file was outputed to
    verbose  -- if True output info for all reports, False only failures

    """
    if rule_and_profile_data is None:
        raise ValueError

    rule_report = None
    rule_data = rule_and_profile_data.rules_file_data
    if rule_data is not None:
        rule_report = rule_data.conversion_report
        if rule_report is None:
            sys.stderr.write("rule report is empty\n")
            return -1

    profiles = rule_and_profile_data.defined_profiles
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
        print _("                      Process       Unsupported    "
                "Conversion\n"
                "Rule/Profile Name     Errors        Items          "
                "Errors\n"
                "-------------------   ------------  ------------  "
                "------------")

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
    else:
        print _("Successfully completed conversion")
    return errors


def parse_args():
    """ function to parse command line arguments to js2ai"""

    desc = _("Utility for converting Solaris 10 jumpstart rules and " \
             "profiles to Solaris 11 compatible AI manifests")
    usage = "usage: %prog [options]"
    parser = OptionParser(version=VERSION, description=desc, usage=usage)

    parser.add_option("-p", "--profile", dest="profile", default="",
                      action="store", type="string", nargs=1,
                      metavar="<profile>",
                      help=_("convert specified jumpstart profile only"))
    parser.add_option("-d", "--dir", dest="source", default=".",
                      action="store", type="string", nargs=1,
                      metavar="<jumpstart_directory>",
                      help=_("jumpstart directory containing origional " + \
                             "rule and profile files"))
    parser.add_option("-D", "--dest", dest="destination", default=None,
                      action="store", type="string", nargs=1,
                      metavar="<destination_directory>",
                      help=_("directory to output converted rule and " + \
                      "profile scripts to. Default destination directory " + \
                      "is the source directory"))
    parser.add_option("-l", "--local", dest="local", default=False,
                      action="store_true",
                      help=_("local only.  No remote package name lookup"))
    parser.add_option("-v", "--verbose", dest="verbose", default=False,
                      action="store_true",
                      help=_("turn on verbose output to see the " + \
                             "processing that is occurring"))

    options, args = parser.parse_args()

    if len(args) != 0:
        parser.error(_("Unrecognized argument specified:  %s\n" % args))

    # Verify that directory user created exists.  If not exit
    if not os.path.isdir(options.source):
        parser.error(_("Specified jumpstart directory does not "
                       "exist: %s\n" % options.source))

    if options.destination is None:
        options.destination = options.source
    else:
        if not os.path.isdir(options.destination):
            parser.error(_("Specified destination directory does not " + \
                           "exist: %s\n" % options.destination))
    return options


def main():
    """ js2ai's main function"""

    options = parse_args()

    # set up logging
    logger_setup(options.destination)

    if options.profile:
        profile_data = process_profile(options.profile, options.source,
                                       options.destination, options.local,
                                       options.verbose)
        rules_and_profile_data = RulesAndAssociatedProfiles(None)
        rules_and_profile_data.add_defined_profile(profile_data)
    else:
        rules_and_profile_data = process_rule(RULES_FILENAME, options.source,
                                              options.destination,
                                              options.local,
                                              options.verbose)
    errors = output_report(rules_and_profile_data, options.destination,
                           options.verbose)

    sys.exit(errors)

if __name__ == "__main__":
    main()

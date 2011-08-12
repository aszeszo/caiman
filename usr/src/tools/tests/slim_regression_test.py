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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

import optparse
import os
import re
import sys
import urllib2

import nose

from cStringIO import StringIO

try:
    SRC = os.environ["SRC"]
except KeyError:
    raise SystemExit("unable to find $SRC in environment.  Please add SRC to "
        "/etc/sudoers file under the 'Defaults env_keep=...' section")

# check permissions
if os.geteuid() != 0:
    raise SystemExit("Error:  Root privileges are required")

MASTER_URL = "http://indiana-build.us.oracle.com/job/install_unit_tests/" + \
             "lastBuild/consoleText"


def build_test_map():
    """ build_test_map() - function to dynamically build a mapping of names to
    test directories.
    """

    test_map = dict()
    commands = list()
    libraries = list()

    for root, dirs, files in os.walk(SRC):
        if root.endswith("/test"):
            # first, subtract of the SRC path
            root = root.replace(SRC + "/", "")
            root_path = root.split("/")

            # the root_path will look something like:
            # ['cmd', 'auto-install', 'test']
            # take the second entry as the test name
            test_name = root_path[1]

            # look to see if that test_name is already present.  If so, add the
            # first sub-directory to the test_name
            i = 2
            while test_name in test_map:
                test_name = test_name + "/" + root_path[i]

            # look to see if the test is in the cmd or lib subdirectory
            if root.startswith("cmd"):
                commands.append(test_name)
            else:
                # strip off the "install_" portion of the library test_name
                test_name = test_name.replace("install_", "")
                libraries.append(test_name)

            # set the dictionary entry
            test_map[test_name] = root


    test_map["all"] = ["libraries", "commands"]
    test_map["commands"] = commands
    test_map["libraries"] = libraries
    return test_map


def parse_results(results=None, hudson_num=None):
    """ parse_results() - function to parse either nose test output or hudson
    output.
    """

    test_pattern = re.compile("^(\#\d+) (.*?) \.\.\. (ok|FAIL|ERROR|SKIP)",
                              re.M)
    resultdict = dict()
    if results is None:
        # pull the data from Hudson
        if hudson_num is None:
            results = urllib2.urlopen(MASTER_URL).read()
        else:
            url = MASTER_URL.replace("lastBuild", hudson_num)
            results = urllib2.urlopen(url).read()

    for entry in test_pattern.findall(results):
        try:
            _none, name, result = entry
        except ValueError:
            # skip whatever fails
            continue
        resultdict[name] = result
    return resultdict


def parse_args(test_map):
    """ parse_args() - parse the command line options from the user
    """

    # build a nice output showing the user what tests are available
    map_output = "%25s\n" % "group tests"
    map_output += "%25s:  %s\n" % ("all", ", ".join(test_map["all"]))
    map_output += "%25s:  %s\n" % \
        ("libraries", ", ".join(test_map["libraries"]))
    map_output += "%25s:  %s\n\n" % \
        ("commands", ", ".join(test_map["commands"]))

    map_output += "%25s\n" % "individual tests"
    for key, value in sorted(test_map.items()):
        if key in ["all", "libraries", "commands"]:
            continue
        if isinstance(value, list):
            map_output += "%25s:  %s\n" % (key, ", ".join(value))
        else:
            map_output += "%25s:  %s\n" % (key, value)

    usage = "Usage:  %s [options] [test[,test]...]\nAvailable tests:\n\n%s" % \
        (os.path.basename(sys.argv[0]), map_output)

    parser = optparse.OptionParser(usage)
    parser.add_option("-c", "--config", dest="config",
        default=os.path.join(SRC, "tools/tests/config.nose"),
        help="nose configuration file to use")
    parser.add_option("--suppress-results", dest="suppress_results",
                      default=False, action="store_true",
                      help="suppress the printing of the results")
    parser.add_option("--hudson", dest="hudson_num",
        help="hudson job number to use as a baseline")

    options, args = parser.parse_args()
    if not os.path.isabs(options.config):
        options.config = os.path.abspath(options.config)

    if not args:
        args = ["all"]

    return options, args


def expand_args(key, test_map):
    """ expand_args() - function to expand test_map keys into paths to actual
    tests.
    """

    dir_list = list()
    if key in test_map:
        if isinstance(test_map[key], str):
            dir_list.append(test_map[key])
        elif isinstance(test_map[key], list):
            for entry in test_map[key]:
                if entry in test_map:
                    dir_list.extend(expand_args(entry, test_map))
                else:
                    dir_list.append(entry)
    else:
        dir_list.append(key)
    return dir_list


def main():
    """ primary entry point for execution of tests
    """
    test_map = build_test_map()

    # parse the command line options
    options, args = parse_args(test_map)

    # walk the args list and attempt to build a master list of tests to run
    arg_list = ["nosetests", "--nologcapture", "-w", SRC, "-c", options.config]

    for entry in args:
        arg_list.extend(expand_args(entry, test_map))

    # redirect stdout and stderr to a string
    stderr = StringIO()
    stdout = StringIO()
    sys.stderr = stderr
    sys.stdout = stdout

    # run the tests
    nose.core.TestProgram(argv=arg_list, exit=False)

    # restore stdout and stderr
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
    results = stderr.getvalue()

    # if the user doesn't want result spam, suppress it
    if not options.suppress_results:
        print results

    # gather test results from the latest hudson run
    this_run = parse_results(results=results)
    hudson_run = parse_results(hudson_num=options.hudson_num)

    diffs = False
    regressions = list()
    fixes = list()
    for key, value in this_run.items():
        if key in hudson_run:
            hudson_value = hudson_run[key]
            if value != hudson_value:
                diffs = True
                if hudson_value == "ok":
                    # regression
                    regressions.append(key)
                elif hudson_value in ["ERROR", "FAIL"] and value == "ok":
                    fixes.append(key)

    if not diffs:
        print "No regressions found!"
    else:
        if regressions:
            print "New Regressions:"
            print "----------------"
            print "\n".join(regressions)
            print "\n"
        if fixes:
            print "Tests Now Passing:"
            print "------------------"
            print "\n".join(fixes)
            print "\n"

if __name__ == "__main__":
    main()

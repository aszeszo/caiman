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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import unittest
import osol_install.auto_install.list as list


class DummyCriteriaPrint(list.CriteriaPrintObject):
    def __init__(self):
        pass


class GetCriteriaInfo(unittest.TestCase):
    '''Tests for get_criteria_info.'''

    def setUp(self):
        '''unit test set up'''
        self.crit = DummyCriteriaPrint()

    def test_list_range_bounded_both_sides(self):
        '''Ensure range bounded with different values list correctly'''
        mycriteria = {"MAXmem": 2048, "MINmem": 512}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("mem"))
        self.assertEquals(self.crit.crit["mem"], "512 MB - 2048 MB")

    def test_list_range_bounded_same_on_both_sides(self):
        '''Ensure range bounded with same values list correctly'''
        mycriteria = {"MINmac": u'00ABCDEF0122', "MAXmac": u'00ABCDEF0122'}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("mac"))
        self.assertEquals(self.crit.crit["mac"], "00:AB:CD:EF:01:22")

    def test_list_range_unbounded_min_side(self):
        '''Ensure range with unbounded minimum list correctly'''
        mycriteria = {"MAXipv4": '124213023291'}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("ipv4"))
        self.assertEquals(self.crit.crit["ipv4"], "unbounded - 124.213.23.291")

    def test_list_range_unbounded_max_side(self):
        '''Ensure range with unbounded maximum list correctly'''
        mycriteria = {"MINmem": 2048}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("mem"))
        self.assertEquals(self.crit.crit["mem"], "2048 MB - unbounded")

    def test_list_non_range_criteria(self):
        '''Ensure non-range criteria lists correctly'''
        myplatform = "SUNW,Sun-Fire-V250"
        mycriteria = {"platform": myplatform}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("platform"))
        self.assertEquals(self.crit.crit["platform"], myplatform)

    def test_list_setting_none(self):
        '''Ensure None setting handled correctly'''

        mycriteria = {"arch": "sun4u", "cpu": None}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.crit["arch"], "sun4u")
        self.assertEquals(self.crit.crit["cpu"], "")

    def test_width(self):
        '''Ensure width returned correctly'''

        mycriteria = {"arch": "sun4v", "platform": "SUNW,Sun-Fire-V250",
                      "cpu": "sparc"}
        self.crit.get_criteria_info(mycriteria)
        self.assertEquals(self.crit.max_crit_len, len("platform"))


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.'''

    def test_parse_invalid_options_args(self):
        '''Ensure invalid option and args flagged'''
        myargs = ["-z"]
        self.assertRaises(SystemExit, list.parse_options, myargs)

        myargs = ["badarg"]
        self.assertRaises(SystemExit, list.parse_options, myargs)

    def test_parse_options_unexpected_value(self):
        '''Ensure options with unexpected value caught'''
        myargs = ["-c", "foo"]
        self.assertRaises(SystemExit, list.parse_options, myargs)

        myargs = ["-m", "foo"]
        self.assertRaises(SystemExit, list.parse_options, myargs)

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n"]
        self.assertRaises(SystemExit, list.parse_options, myargs)

    def test_parse_valid(self):
        '''Ensure valid options ok'''
        myargs = []
        options = list.parse_options(cmd_options=myargs)
        self.assertFalse(options.client)
        self.assertFalse(options.manifest)
        self.assertFalse(options.service)

        myargs = ["-m", "-c", "-n", "mysvc"]
        options = list.parse_options(cmd_options=myargs)
        self.assertTrue(options.client)
        self.assertTrue(options.manifest)
        self.assertEqual(options.service, "mysvc")


if __name__ == '__main__':
    unittest.main()

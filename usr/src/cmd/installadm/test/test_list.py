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

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import os
import unittest
import list as list


class GetCriteriaInfo(unittest.TestCase):
    '''Tests for get_criteria_info.'''

    def test_list_range_bounded_both_sides(self):
        '''Ensure range bounded with different values list correctly'''
        mycriteria = {"MAXmem": 2048, "MINmem": 512} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("mem"))
        self.assertEquals(cri_dict["mem"], "512 MB - 2048 MB")

    def test_list_range_bounded_same_on_both_sides(self):
        '''Ensure range bounded with same values list correctly'''
        mycriteria = {"MINmac": u'00ABCDEF0122', "MAXmac": u'00ABCDEF0122'} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("mac"))
        self.assertEquals(cri_dict["mac"], "00:AB:CD:EF:01:22")

    def test_list_range_unbounded_min_side(self):
        '''Ensure range with unbounded minimum list correctly'''
        mycriteria = {"MAXipv4": None, "MINipv4": '124213023291'} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("ipv4"))
        self.assertEquals(cri_dict["ipv4"], "124.213.23.291 - unbounded")

    def test_list_range_unbounded_max_side(self):
        '''Ensure range with unbounded maximum list correctly'''
        mycriteria = {"MINmem": 2048, "MAXmem": None} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("mem"))
        self.assertEquals(cri_dict["mem"], "2048 MB - unbounded")

    def test_list_non_range_criteria(self):
        '''Ensure non-range criteria lists correctly'''
        myplatform = "SUNW,Sun-Fire-V250"
        mycriteria = {"platform": myplatform} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("platform"))
        self.assertEquals(cri_dict["platform"], myplatform)

    def test_list_setting_none(self):
        '''Ensure None setting handled correctly'''

        mycriteria = {"arch": "sun4u", "cpu": None} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(cri_dict["arch"], "sun4u")
        self.assertEquals(cri_dict["cpu"], "")

    def test_width(self):
        '''Ensure width returned correctly'''

        mycriteria = {"arch": "sun4v", "platform":"SUNW,Sun-Fire-V250",
                      "cpu": "sparc"} 
        cri_dict, width = list.get_criteria_info(mycriteria) 
        self.assertEquals(width, len("platform"))


if __name__ == '__main__':
    unittest.main()

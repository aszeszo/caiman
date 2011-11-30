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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import unittest
import osol_install.auto_install.installadm_common as com


class TestValidateServiceName(unittest.TestCase):
    '''Tests for validate_service_name'''

    def setUp(self):
        '''unit test set up'''
        self.name = '12ten6789012twenty9012thirty9012forty89012fifty890' + \
                    '12sixty8901seventy9012eighty901ninety8901hundred90'

    def test_name_max_chars(self):
        '''test that max length service name is ok'''
        svcname = self.name[:com.MAX_SERVICE_NAME_LEN]
        try:
            com.validate_service_name(svcname)
        except ValueError:
            self.fail("validate_service_name failed")

    def test_name_too_long(self):
        '''test that max length +1 service name is too long'''
        svcname = self.name[:com.MAX_SERVICE_NAME_LEN] + '1'
        self.assertRaises(ValueError, com.validate_service_name, svcname)

    def test_name_leading_dash(self):
        '''test that leading dash in service name is not allowed'''
        self.assertRaises(ValueError, com.validate_service_name, "-dashname")

    def test_name_nonalphanum(self):
        '''test that non-alphanumeric char in service name is not allowed'''
        self.assertRaises(ValueError, com.validate_service_name, "nam%e")

    def test_name_required(self):
        '''test that name is required'''
        self.assertRaises(ValueError, com.validate_service_name, "")

    def test_name_dashes_underscores(self):
        '''test that dashes and underscores in service name are ok'''
        svcname = 'my_name_is-foo-bar'
        try:
            com.validate_service_name(svcname)
        except ValueError:
            self.fail("validate_service_name failed")


if __name__ == '__main__':
    unittest.main()

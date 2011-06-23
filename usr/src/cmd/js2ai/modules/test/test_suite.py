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

import unittest
import test_js2ai
import test_conv
import test_common
import test_conv_sysidcfg


def test_suite():
    """ Runs all tests in the various test files"""
    test_loader = unittest.TestLoader()

    suite = test_loader.loadTestsFromModule(test_js2ai)
    suite.addTests(test_loader.loadTestsFromModule(test_conv))
    suite.addTests(test_loader.loadTestsFromModule(test_conv_sysidcfg))
    suite.addTests(test_loader.loadTestsFromModule(test_common))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)

if __name__ == "__main__":
    test_suite()

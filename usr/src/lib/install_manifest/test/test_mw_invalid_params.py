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

'''ManifestWriter invalid params tests'''

import logging
import unittest

import common
from solaris_install.logger import InstallLogger
from solaris_install.manifest import ManifestError
from solaris_install.manifest.writer import ManifestWriter


class InvalidParams(unittest.TestCase):
    '''ManifestWriter invalid params tests'''

    def setUp(self):
        '''Set up logging'''
        logging.setLoggerClass(InstallLogger)


    def test_mw_invalid_params_xslt(self):
        '''
            test_mw_invalid_params_xslt - confirm error if xslt_file doesn't exist
        '''
        self.assertRaises(ManifestError, ManifestWriter, "manifest-writer",
            common.MANIFEST_OUT_OK, xslt_file=common.XSLT_NON_EXISTENT)


    def test_mw_invalid_params_dtd_file(self):
        '''
            test_mw_invalid_params_dtd_file - confirm error if dtd_file doesn't exist
        '''
        self.assertRaises(ManifestError, ManifestWriter, "manifest-writer",
            common.MANIFEST_OUT_OK, dtd_file=common.DTD_NON_EXISTENT)


if __name__ == '__main__':
    unittest.main()

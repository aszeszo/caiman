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

'''test_transfer_files
   Test program for transfer_files
'''

import os
import tempfile
import unittest

from common_create_simple_doc import CreateSimpleDataObjectCache
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.ict.transfer_files import TransferFiles
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestTransferAILogFiles(unittest.TestCase):
    '''test the functionality for InitializeSMF Class'''

    def setUp(self):

        # Set up the Target directory
        self.test_target = tempfile.mkdtemp(dir="/tmp/",
                                            prefix="ict_test_")
        os.chmod(self.test_target, 0777)

        # Create a data object to hold the required data
        self.simple = CreateSimpleDataObjectCache(test_target=self.test_target)
        self.doc = InstallEngine.get_instance().data_object_cache
        self.trans_dict = {}
        self.dod = None

        '''Create a transfer source and destination'''
        source = os.path.join(self.test_target, "var/run/install_log")
        dest = "/var/sadm/install/"
        if not os.path.exists(os.path.dirname(source)):
            os.makedirs(os.path.dirname(source))
        open(source, 'w').close()
        self.trans_dict = {source: dest}

        # Instantiate the checkpoint
        self.trans_files = TransferFiles("TFS")

    def tearDown(self):
        reset_engine()
        self.simple.doc = None
        self.dod = None
        self.trans_dict = {}

    def test_transfer_files(self):
        '''Test transferring logs'''
        self.dod = DataObjectDict("TFS", self.trans_dict, generate_xml=True)
        self.doc.volatile.insert_children(self.dod)

        # Call the execute command for the checkpoint
        self.trans_files.execute()

    def test_transfer_empty_dict(self):
        '''Test no transfer files returns gracefully'''
        self.trans_dict.clear()
        self.dod = DataObjectDict("TFS", self.trans_dict, generate_xml=True)
        self.doc.volatile.insert_children(self.dod)
        try:
            self.trans_files.execute()
        except Exception as e:
            self.fail(str(e))

    def test_transfer_no_source_exists(self):
        '''Test no source doesn't exist'''
        self.trans_dict["/bogus"] = "/bogus/"
        self.dod = DataObjectDict("TFS", self.trans_dict, generate_xml=True)
        self.doc.volatile.insert_children(self.dod)

        try:
            self.trans_files.execute()
        except Exception as e:
            self.fail(str(e))

    def test_nothing_to_transfer(self):
        '''Test no transfer DataObjectDict returns gracefully'''
        try:
            self.trans_files.execute()
        except Exception as e:
            self.fail(str(e))


if __name__ == '__main__':
    unittest.main()

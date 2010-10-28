#!/usr/bin/python2.6
#
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

'''Some unit tests to cover functionality in CheckpointData.py file'''

import os
import sys
import unittest

import solaris_install.engine.checkpoint_data as checkpoint_data
import solaris_install.engine.checkpoint as checkpoint

from solaris_install.engine.test.engine_test_utils import reset_engine

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_THIS_DIR)


class MockCheckpoint(object):
    name = ""
    completed = False

class CheckpointDataTest(unittest.TestCase):

    ''' Test interface related to manipulating CheckpointData '''
    
    def setUp(self):
        self._cwd = os.getcwd()
    
    def tearDown(self):
        os.chdir(self._cwd)
        reset_engine()
    
    def test_relative_load(self):
        ''' Verify loading a checkpoint from a relative path works '''
        os.chdir(_THIS_DIR)
        cp_data = checkpoint_data.CheckpointData("cp_data",
                                                 "empty_checkpoint",
                                                 ".", "EmptyCheckpoint",
                                                 0, (), {})
        
        cp_data._load_module()
        cp = cp_data.load_checkpoint()
        self.assertTrue(isinstance(cp, checkpoint.AbstractCheckpoint),
                        "Expected subclass of AbstractCheckpoint, \
                        got %s" % cp.__class__.__name__)
    
    def test_absolute_load(self):
        ''' Verify loading a checkpoint from an absolute path works '''
        abs_path = _THIS_DIR
        cp_data = checkpoint_data.CheckpointData("cp_data",
                                                 "empty_checkpoint",
                                                 abs_path, "EmptyCheckpoint",
                                                 0, (), {})
        
        cp_data._load_module()
        cp = cp_data.load_checkpoint()
        self.assertTrue(isinstance(cp, checkpoint.AbstractCheckpoint),
                        "Expected subclass of AbstractCheckpoint, \
                        got %s" % cp.__class__.__name__)


if __name__ == '__main__':
    unittest.main()

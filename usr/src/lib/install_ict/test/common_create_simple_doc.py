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
'''
   test_create_simple_doc
   Test Class for testing the ICTs
'''

from solaris_install.engine.test.engine_test_utils import \
    get_new_engine_instance
from solaris_install.target import Target
from solaris_install.target.logical import BE, Logical, Vdev, Zpool
from solaris_install.target.controller import DEFAULT_LOGICAL_NAME, \
    DEFAULT_VDEV_NAME, DEFAULT_ZPOOL_NAME


class CreateSimpleDataObjectCache():
    '''A class that creates a simple data object'''
    def __init__(self, test_target=None):
        '''Initialize the class
           Parameters:
               -test_target - this arg is supplies the
                              test directory
        '''
        self.test_target = test_target
        self.engine = get_new_engine_instance()
        self.doc = self.engine.data_object_cache

        # Create the doc for finding the BE.
        self.desired_root = Target(Target.DESIRED)
        self.doc.persistent.insert_children(self.desired_root)
        self.logical = Logical(DEFAULT_LOGICAL_NAME)
        self.desired_root.insert_children(self.logical)
        self.zpool = Zpool(DEFAULT_ZPOOL_NAME)
        self.zpool.is_root = "true"
        self.logical.insert_children(self.zpool)
        self.vdev = Vdev(DEFAULT_VDEV_NAME)
        self.vdev.redundancy = "none"
        self.zpool.insert_children(self.vdev)
        self.be_obj = BE()
        self.zpool.insert_children(self.be_obj)
        self.be_obj.mountpoint = self.test_target

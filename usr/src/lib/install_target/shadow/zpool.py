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
import os.path

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc

from solaris_install.target.shadow import ShadowList, ShadowExceptionBase


class ShadowZpool(ShadowList):
    """ ShadowZpool - class to hold and validate Zpool objects.
    """
    class DuplicateZpoolNameError(ShadowExceptionBase):
        def __init__(self, zpool_name):
            self.value = "Zpool name %s already inserted" % zpool_name

    class DuplicateMountpointError(ShadowExceptionBase):
        def __init__(self, mountpoint):
            self.value = "mountpoint %s already specified" % mountpoint

    class TooManyRootPoolsError(ShadowExceptionBase):
        def __init__(self, zpool_name):
            self.value = "Zpool %s already marked as root pool" % zpool_name

    def insert(self, index, value):
        # check that the name of the zpool is not already in the list
        if value.name in [zpool.name for zpool in self._shadow]:
            self.set_error(self.DuplicateZpoolNameError(value.name))

        # if is_root is set to True, verify there are no other zpools with
        # is_root set to True
        if value.is_root:
            for zpool in self._shadow:
                if zpool.is_root:
                    self.set_error(self.TooManyRootPoolsError(zpool.name))

        # verify the mountpoint (if specified) doesn't overlap with any other
        # zpool mountpoints
        if value.mountpoint is not None:
            for zpool in self._shadow:
                if zpool.mountpoint is not None:
                    common = os.path.commonprefix([value.mountpoint,
                                                   zpool.mountpoint])

                    # the only character in common should be "/".  If it's
                    # anything else, the mountpoints overlap
                    if common != ("/"):
                        self.set_error(self.DuplicateMountpointError(
                            value.mountpoint))

        # insert the zpool
        ShadowList.insert(self, index, value)

    def __init__(self, container, *args):
        ShadowList.__init__(self, *args)

        self.mod_id = "zpool validation"
        self.container = container

        for entry in args:
            self.append(entry)  # will call self.insert

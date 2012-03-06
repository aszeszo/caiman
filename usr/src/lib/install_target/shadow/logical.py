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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
import osol_install.errsvc as errsvc

from solaris_install.target.shadow import ShadowList, ShadowExceptionBase


class ShadowLogical(ShadowList):
    """ ShadowLogical - class to hold and validate ZFS Dataset objects
    (Filesystem and Zvol)
    """
    class DuplicateDatasetNameError(ShadowExceptionBase):
        def __init__(self, name):
            self.value = "Dataset name %s already inserted" % name

    class DuplicateMountpointError(ShadowExceptionBase):
        def __init__(self, name, mp):
            self.value = "Filesystem name %s already mounted at %s" % \
                         (name, mp)

    class NoswapMismatchError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Zvol marked for swap usage, but Logical element " + \
                         "has noswap=\"true\""

    class NodumpMismatchError(ShadowExceptionBase):
        def __init__(self):
            self.value = "Zvol marked for dump usage, but Logical element " + \
                         "has nodump=\"true\""

    def insert(self, index, value):
        """
        insert() - overridden method for validation of logical DOC objects

        the following checks are done as part of validation:

        - duplicate dataset name (zfs filesystems and zvolss)

        - duplicate dataset mountpoint (zfs filesystems)

        - verifies the <logical> tag's noswap and nodump values do not conflict
          with the use attribute of a Zvol object
        """
        # reset the errsvc for Logical errors
        errsvc.clear_error_list_by_mod_id(self.mod_id)

        # check the existing datasets for name and mountpoint overlap
        for dataset in self._shadow:
            # look for name duplication if not an Options object
            if not hasattr(value, "OPTIONS_PARAM_STR") and \
               value.name == dataset.name:
                self.set_error(self.DuplicateDatasetNameError(dataset.name))

            # check the mountpoint if this is a Filesystem object
            if hasattr(value, "mountpoint") and hasattr(dataset, "mountpoint"):
                if value.mountpoint is not None and \
                   value.mountpoint.lower() not in ["none", "legacy"] and \
                   value.mountpoint == dataset.mountpoint:
                    self.set_error(
                        self.DuplicateMountpointError(dataset.name,
                                                      dataset.mountpoint))

        # check the 'use' attribute for Zvol objects.  The grandparent of the
        # entry is the <logical> element
        if hasattr(value, "use") and value.use is not "none":
            if value.use == "swap" and self.container.parent.noswap:
                self.set_error(self.NoswapMismatchError())
            if value.use == "dump" and self.container.parent.nodump:
                self.set_error(self.NodumpMismatchError())

        # insert the filesystem
        ShadowList.insert(self, index, value)

    def __init__(self, container, *args):
        ShadowList.__init__(self, *args)

        self.mod_id = "zfs dataset validation"
        self.container = container

        for entry in args:
            self.append(entry)  # will call self.insert

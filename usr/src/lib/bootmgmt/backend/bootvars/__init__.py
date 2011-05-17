#! /usr/bin/python2.6
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

"""
Boot variables backend support for pybootmgmt
"""

import sys
from ... import bootutil
from ... import BootmgmtArgumentError


class BackendBootVarsFactory(object):
    @staticmethod
    def get(sysroot, arch, osname):
        """Returns an instance of bootinfo.BootVariables corresponding to the
        architecture and system root passed in."""
        if arch is None:
            arch = bootutil.get_current_arch_string()
        if osname is None:
            raise BootmgmtArgumentError('osname cannot be None')

        bvmod = __name__ + '.' + arch + '.' + osname
        __import__(bvmod, level=0)
        ns = sys.modules[bvmod]
        # bootvars_backend returns the *class*
        return ns.bootvars_backend()(sysroot)

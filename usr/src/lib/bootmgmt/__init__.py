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
A Python package for management of all things Boot
"""


class BootmgmtError(Exception):
    def __init__(self, msg, xcpt=None):
        self.msg = msg
        self.xcpt = xcpt

    def __str__(self):
        if not self.xcpt is None:
            return self.msg + '(' + str(self.xcpt) + ')'
        else:
            return self.msg


class BootmgmtNotSupportedError(BootmgmtError):
    pass


class BootmgmtArgumentError(BootmgmtError):
    pass


class BootmgmtMissingInfoError(BootmgmtError):
    pass


class BootmgmtUnsupportedOperationError(BootmgmtError):
    pass


class BootmgmtMalformedPropertyNameError(BootmgmtError):
    pass


class BootmgmtMalformedPropertyValueError(BootmgmtError):
    def __init__(self, propname, propval):
        super(self, BootmgmtMalformedPropertyValueError).__init__(
           'Invalid value specified for property "%s": %s' %
           (str(propname), str(propval)))
        self.propname = propname
        self.propval = propval


class BootmgmtReadError(BootmgmtError):
    pass


class BootmgmtWriteError(BootmgmtError):
    pass


class BootmgmtUnsupportedPlatformError(BootmgmtError):
    pass


class BootmgmtInterfaceCodingError(BootmgmtError):
    pass


class BootmgmtConfigReadError(BootmgmtError):
    pass


class BootmgmtConfigWriteError(BootmgmtError):
    pass


class BootmgmtIncompleteBootConfigError(BootmgmtError):
    pass


class BootmgmtUnsupportedPropertyError(BootmgmtUnsupportedOperationError):
    pass

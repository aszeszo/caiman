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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
cli.py:  simple module containing a single class with global variables used by
DC.
"""


class CLI(object):
    """ simple class definition for common Solaris CLI calls
    """
    BASH = "/usr/bin/bash"
    CMD7ZA = "/usr/bin/7za"
    CP = "/usr/bin/cp"
    CPIO = "/usr/bin/cpio"
    DD = "/usr/bin/dd"
    DEVFSADM = "/usr/sbin/devfsadm"
    ECHO = "/usr/bin/echo"
    FC_CACHE = "/usr/bin/fc-cache"
    FIND = "/usr/bin/find"
    FIOCOMPRESS = "/usr/sbin/fiocompress"
    INSTALLBOOT = "/usr/sbin/installboot"
    LOFIADM = "/usr/sbin/lofiadm"
    MKISOFS = "/usr/bin/mkisofs"
    PKG = "/usr/bin/pkg"
    PKGREPO = "/usr/bin/pkgrepo"
    PKGSEND = "/usr/bin/pkgsend"
    SVCCFG = "/usr/sbin/svccfg"
    TOUCH = "/usr/bin/touch"
    USBGEN = "/usr/bin/usbgen"

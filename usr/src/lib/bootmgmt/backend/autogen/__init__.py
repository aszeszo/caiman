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
BootInstance autogenerator backend interfaces for pybootmgmt
"""

import sys

autogen_backends = [ 'solaris' ]

class BootInstanceAutogenFactory(object):
    @staticmethod
    def autogen(bootconfig):
        instance_list = []
        for backend in autogen_backends:
            modname = __name__ + '.' + backend
            __import__(modname, level=0)
            ns = sys.modules[modname]
            instance_list += ns.autogenerate_boot_instances(bootconfig)
        return instance_list

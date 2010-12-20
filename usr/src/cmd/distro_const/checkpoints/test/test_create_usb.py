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

""" test_create_usb

 Test program for create_usb
"""

import os.path
import unittest

from subprocess import CalledProcessError

from solaris_install.distro_const.checkpoints.create_usb import CreateUSB
from solaris_install.engine import InstallEngine


class TestCreateUSB(unittest.TestCase):
    """ class for testing the creation of usb files from an iso
    """

    def setUp(self):
        InstallEngine()
        self.c_usb = CreateUSB("Test Create USB")

    def tearDown(self):
        InstallEngine._instance = None

    def test_missing_iso(self):
        self.c_usb.dist_usb = "/var/tmp/temp.usb"
        self.c_usb.dist_iso = "/var/tmp/temp.iso"
        self.c_usb.tmp_mnt = "/var/tmp/tmp_mnt"
        self.assertRaises(CalledProcessError, self.c_usb.run_usbgen)

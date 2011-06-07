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

""" create_usb.py - Generates a USB media based on the prepared package image
area.  The resulting .usb file is created from an .iso file so the .iso file
must exist first.
"""
import os
import os.path
import shutil
import subprocess
import tempfile
import time

from solaris_install import DC_LABEL, DC_PERS_LABEL
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const.distro_spec import Distro
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint

import solaris_install.distro_const.cli as cli
cli = cli.CLI()

_NULL = open("/dev/null", "r+")


class CreateUSB(Checkpoint):
    """ checkpoint class to create a usb image from an iso file
    """

    def __init__(self, name):
        super(CreateUSB, self).__init__(name)

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.dc_pers_dict = {}
        self.pkg_img_path = None
        self.ba_build = None
        self.tmp_dir = None
        self.media_dir = None

        self.add_timestamp = None
        self.distro_name = None
        self.dist_iso = None
        self.dist_usb = None
        self.tmp_mnt = None

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 60

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache

        create_usb_obj = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)
        self.dc_dict = create_usb_obj[0].data_dict

        try:
            self.tmp_dir = self.dc_dict["tmp_dir"]
            self.media_dir = self.dc_dict["media_dir"]
            distro = self.doc.volatile.get_children(class_type=Distro)
            self.add_timestamp = distro[0].add_timestamp
            if self.add_timestamp is not None and \
                self.add_timestamp.capitalize() == "True":
                timestamp = time.strftime("%m-%d-%H-%M")
                self.distro_name = distro[0].name + "-" + timestamp
            else:
                self.distro_name = distro[0].name
        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))
        except ObjectNotFoundError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))

        # check for the existence of an ISO.  If add_timestamp is
        # set, check the DC dict for the value of add_timestamp_iso
        if self.add_timestamp is not None and \
            self.add_timestamp.capitalize() == "True":
            dc_pers_dict = self.doc.persistent.get_children(name=DC_PERS_LABEL,
                class_type=DataObjectDict)
            if dc_pers_dict:
                self.dc_pers_dict = dc_pers_dict[0].data_dict
            else:
                raise RuntimeError(DC_PERS_LABEL + " not found. Can not " + \
                                   "generate USB image")

            self.dist_iso = self.dc_pers_dict["add_timestamp_iso"]
        else:
            self.dist_iso = os.path.join(self.media_dir,
                                         self.distro_name) + ".iso"

        if not os.path.exists(self.dist_iso):
            raise RuntimeError(self.dist_iso + " not found.  Can not " + \
                               "generate USB image")

        self.dist_usb = os.path.join(self.media_dir, self.distro_name) + ".usb"

        # remove any leftover .usb file first
        if os.path.exists(self.dist_usb):
            os.unlink(self.dist_usb)

        # create a temporary mountpoint in tmp_dir
        self.tmp_mnt = tempfile.mkdtemp(dir=self.tmp_dir, suffix="-usb_mnt")
        os.chmod(self.tmp_mnt, 0777)

    def run_usbgen(self):
        """ class method to execute usbgen to create the usb file
        """
        self.logger.info("Making final USB image: %s" % self.dist_usb)
        cmd = [cli.USBGEN, self.dist_iso, self.dist_usb, self.tmp_mnt]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        subprocess.check_call(cmd, stdout=_NULL, stderr=_NULL)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Create USB Checkpoint ===")

        self.parse_doc()

        # create the .usb file
        self.run_usbgen()

        # clean up the temporary mountpoint
        shutil.rmtree(self.tmp_mnt)

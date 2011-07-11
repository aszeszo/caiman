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

""" create_iso.py - Generates an ISO media based on the prepared package image
area.
"""
import os
import platform
import time

from solaris_install import DC_LABEL, DC_PERS_LABEL, run_silent
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const.distro_spec import Distro

import solaris_install.distro_const.cli as cli
cli = cli.CLI()


class CreateISO(Checkpoint):
    """ CreateISO - class to create a bootable ISO from the pkg_image
    directory
    """

    def __init__(self, name):
        super(CreateISO, self).__init__(name)

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.dc_pers_dict = {}
        self.pkg_img_path = None
        self.ba_build = None
        self.media_dir = None

        self.bios_eltorito = None
        self.add_timestamp = None
        self.distro_name = None
        self.dist_iso = None
        self.partial_distro_name = None
        self.partial_dist_iso = None
        self.volsetid = None
        self.mkisofs_cmd = None

        # set the platform
        self.arch = platform.processor()

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 20

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache

        try:
            create_iso_obj = self.doc.volatile.get_children(name=DC_LABEL,
                class_type=DataObjectDict)
            self.dc_dict = create_iso_obj[0].data_dict

            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.ba_build = self.dc_dict["ba_build"]
            self.media_dir = self.dc_dict["media_dir"]
            distro = self.doc.volatile.get_children(class_type=Distro)
            self.partial_distro_name = distro[0].name
            self.add_timestamp = distro[0].add_timestamp

            # append a timestamp to the media name if add_timestamp is
            # marked as True in the manifest
            if self.add_timestamp is not None and \
                self.add_timestamp.capitalize() == "True":
                timestamp = time.strftime("%m-%d-%H-%M")
                self.distro_name = distro[0].name + "-" + timestamp
            else:
                self.distro_name = distro[0].name

            # Look for DC persistent dictionary. Force an error if not found
            # on X86 since the 'bios-eltorito-img' key is required.
            dc_pers_dict = self.doc.persistent.get_children(
                name=DC_PERS_LABEL,
                class_type=DataObjectDict,
                not_found_is_err=(self.arch == 'i386'))
            if dc_pers_dict:
                self.dc_pers_dict = dc_pers_dict[0].data_dict
            if self.arch == 'i386':
                self.bios_eltorito = self.dc_pers_dict["bios-eltorito-img"]
        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))
        except ObjectNotFoundError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))

    def setup(self, bootblock=None):
        """ class method for doing some sanity checks and setting the mkisofs
        command before that command can actually be run.
        """
        # check for the existance of the media_dir
        if not os.path.exists(self.media_dir):
            os.mkdir(self.media_dir, 0755)

        # iso name
        self.dist_iso = os.path.join(self.media_dir, self.distro_name) + ".iso"
        self.logger.info("Making final ISO image: %s" % self.dist_iso)

        # remove any leftover .iso file first
        if os.path.exists(self.dist_iso):
            os.unlink(self.dist_iso)

        # read .volsetid
        vpath = os.path.join(self.ba_build, ".volsetid")
        with open(vpath, "r") as vpath_fh:
            self.volsetid = vpath_fh.read().strip()

        # set the mkisofs_cmd
        if self.arch == "i386":
            self.mkisofs_cmd = [cli.MKISOFS, "-quiet", "-o", self.dist_iso,
                                "-b", self.bios_eltorito, "-c",
                                ".catalog", "-no-emul-boot",
                                "-boot-load-size", "4", "-boot-info-table",
                                "-N", "-l", "-R", "-U", "-allow-multidot",
                                "-no-iso-translate", "-cache-inodes", "-d",
                                "-D", "-volset", self.volsetid, "-V",
                                self.partial_distro_name, self.pkg_img_path]
        else:
            self.mkisofs_cmd = [cli.MKISOFS, "-quiet", "-o", self.dist_iso,
                                "-G", bootblock, "-B", "...", "-N", "-l",
                                "-ldots", "-R", "-D", "-volset",
                                self.volsetid, "-V", self.partial_distro_name,
                                self.pkg_img_path]

    def prepare_bootblock(self, inblock, outblock):
        """ class method to prepare the bootblock for sparc distributions
        """
        # the first 16 sectors (or 8K) of the media contain the bootblock.
        # The hsfs bootblock starts at offset 512.
        self.logger.debug("creating hsfs.bootblock")
        cmd = [cli.DD, "if=%s" % inblock, "of=%s" % outblock, "bs=1b",
               "oseek=1", "count=15", "conv=sync"]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        run_silent(cmd)

    def run_mkisofs(self):
        """ class method to execute mkisofs to create the iso file
        """
        self.logger.debug("executing:  %s" % " ".join(self.mkisofs_cmd))
        run_silent(self.mkisofs_cmd)

    def create_additional_timestamp(self):
        """ class method to create a symlink to the timestamped
        version of the iso file
        """
        self.partial_dist_iso = os.path.join(self.media_dir,
            self.partial_distro_name) + ".iso"

        # remove any leftover .iso file first
        if os.path.exists(self.partial_dist_iso):
            os.unlink(self.partial_dist_iso)

        os.symlink(self.distro_name + ".iso", self.partial_dist_iso)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class to
        create the ISO for x86
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Create ISO Checkpoint ==")

        self.parse_doc()

        if self.arch == "i386":
            self.setup()
            self.run_mkisofs()
        elif self.arch == "sparc":
            # prepare the bootblock
            inblock = os.path.join(self.ba_build,
                                   "platform/sun4u/lib/fs/hsfs/bootblk")
            outblock = os.path.join(self.pkg_img_path, "boot/hsfs.bootblock")
            self.prepare_bootblock(inblock, outblock)
            self.setup(outblock)
            self.run_mkisofs()

        if self.add_timestamp is not None and \
            self.add_timestamp.capitalize() == "True":
            self.create_additional_timestamp()

            # add_timestamp_iso needs to live in the persistent
            # section of the DOC to ensure pause/resume works
            # correctly.
            #
            # update the DC_PERS_LABEL DOC object with an entry
            # for add_timestamp_iso
            if self.dc_pers_dict:
                self.doc.persistent.delete_children(name=DC_PERS_LABEL)

            self.dc_pers_dict["add_timestamp_iso"] = self.dist_iso
            self.doc.persistent.insert_children(DataObjectDict(DC_PERS_LABEL,
                self.dc_pers_dict, generate_xml=True))

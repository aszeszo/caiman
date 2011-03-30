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

""" grub_setup.py - Creates a custom grub menu.lst file
"""
import abc
import os
import os.path

from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const import DC_LABEL
from solaris_install.distro_const.distro_spec import GrubMods, GrubEntry
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint


class GrubSetup(Checkpoint):
    """ GrubSetup - class to customize the grub menu
    """
    DEFAULT_ENTRY = 0
    DEFAULT_TIMEOUT = 30
    # set the DEFAULT_MIN_MEM to 0
    DEFAULT_MIN_MEM = 0

    def __init__(self, name):
        """ constructor for class.
        """
        super(GrubSetup, self).__init__(name)

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.pkg_img_path = None
        self.grub_mods = None
        self.grub_entry_list = None
        self.img_info_path = None
        self.menu_list = None

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 1

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache

        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)[0].data_dict

        try:
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))

        self.img_info_path = os.path.join(self.pkg_img_path, ".image_info")
        self.menu_list = os.path.join(self.pkg_img_path, "boot/grub/menu.lst")

        # retrieve manifest specific grub configurations
        grub_mods = self.doc.volatile.get_descendants(class_type=GrubMods)
        if len(grub_mods) == 0:
            # if there are no GrubMods in the doc, create a new GrubMods
            # instance and allow it to be populated with default values
            # the DEFAULT_MIN_MEM is only used for setting up GRUB_MIN_MEM64
            # in AI .image_info for installadm backward compatibility
            self.grub_mods = GrubMods("grub mods")
        else:
            self.grub_mods = grub_mods[0]

        if self.grub_mods.default_entry is None:
            self.grub_mods.default_entry = self.DEFAULT_ENTRY
        if self.grub_mods.timeout is None:
            self.grub_mods.timeout = self.DEFAULT_TIMEOUT
        if self.grub_mods.min_mem is None:
            self.grub_mods.min_mem = self.DEFAULT_MIN_MEM
        if self.grub_mods.title is None:
            # set the default title
            rel_file = os.path.join(self.pkg_img_path, "etc/release")
            with open(rel_file, "r") as rel:
                # read the first line of /etc/release
                self.grub_mods.title = rel.readline().strip()
        else:
            # the manifest specified a special grub title.  Record it in
            # .image_info
            with open(self.img_info_path, "a+") as fh:
                fh.write("GRUB_TITLE=" + self.grub_mods.title + "\n")

        # verify something is present
        if len(self.grub_mods.title) == 0:
            raise RuntimeError("Error finding or extracting non-empty " + \
                               "release string from /etc/release")

        self.grub_entry_list = self.doc.volatile.get_descendants(
            class_type=GrubEntry)

    @abc.abstractmethod
    def build_entries(self):
        """ abstract method which is required by subclasses to implement
        """
        raise NotImplementedError

    def build_position_specific(self, entries):
        """ class method to insert position specific entries to the menu.lst
        file.
        """
        # walk each entry in the grub_entry_list
        for grub_entry in self.grub_entry_list:
            entry = [" ".join(["title", self.grub_mods.title,
                              grub_entry.title_suffix])]
            for line in grub_entry.lines:
                entry.append("\t" + line)

            # place the entire new entry into the entries list
            if grub_entry.position is None:
                entries.append(entry)
            else:
                entries.insert(int(grub_entry.position), entry)

        return entries

    def write_entries(self, entries):
        """ class method to write out everything in the entries list to the
        menu.lst file.
        """
        with open(self.menu_list, "w") as menu_lst_fh:
            menu_lst_fh.write("default %s\n" % self.grub_mods.default_entry)
            menu_lst_fh.write("timeout %s\n" % self.grub_mods.timeout)

            # write out the entries
            for entry in entries:
                for line in entry:
                    menu_lst_fh.write(line + "\n")
                menu_lst_fh.write("\n")

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Grub Setup Checkpoint ===")

        # parse the DOC object
        self.parse_doc()

        # construct the entries list
        entries = self.build_entries()

        # add all position specific grub entries
        entries = self.build_position_specific(entries)

        # write out the default entry number and default timeout
        # values, along with everything in entries
        self.logger.info("Writing menu.lst")
        self.write_entries(entries)


class AIGrubSetup(GrubSetup):
    """ AIGrubSetup - class to customize the grub menu for AI distributions
    """

    def __init__(self, name, arg=None):
        GrubSetup.__init__(self, name)
        if arg:
            self.__setup(**arg)
        else:
            self.__setup()

    def __setup(self, installadm_entry="boot image"):
        self.installadm_entry = installadm_entry

    def build_entries(self):
        """ class method for constructing the entries list.
        """
        entries = []

        title = "title " + self.grub_mods.title
        kernel = "\tkernel$ /platform/i86pc/kernel/$ISADIR/unix"
        module = "\tmodule$ /platform/i86pc/$ISADIR/boot_archive"

        # create lists of grub titles, kernels, and module lines to use
        ai_titles = [title + " Automated Install custom",
                     title + " Automated Install",
                     title + " Automated Install custom ttya",
                     title + " Automated Install custom ttyb",
                     title + " Automated Install ttya",
                     title + " Automated Install ttyb"]
        ai_kernel = [kernel + " -B install=true,aimanifest=prompt",
                     kernel + " -B install=true",
                     kernel + " -B install=true,aimanifest=prompt," + \
                         "console=ttya",
                     kernel + " -B install=true,aimanifest=prompt," + \
                         "console=ttyb",
                     kernel + " -B install=true,console=ttya",
                     kernel + " -B install=true,console=ttyb"]
        ai_module = len(ai_titles) * [module]

        # create a new list from zipper'ing each of the lists
        entries = zip(ai_titles, ai_kernel, ai_module)

        # boot from hd entry.
        entries.append(["title Boot from Hard Disk",
                        "\trootnoverify (hd0)",
                        "\tchainloader +1"])
        return entries

    def update_img_info_path(self):
        """ class method to write out the .img_info_path file.
        """
        self.logger.debug("updating %s" % self.img_info_path)

        # write out the GRUB_MIN_MEM64 and GRUB_DO_SAFE_DEFAULT lines
        with open(self.img_info_path, "a+") as iip:
            iip.write("GRUB_MIN_MEM64=%s\n" % self.grub_mods.min_mem)
            iip.write("GRUB_DO_SAFE_DEFAULT=true\n")
            iip.write("NO_INSTALL_GRUB_TITLE=%s\n" % self.installadm_entry)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Grub Setup Checkpoint ===")

        # parse the DOC object
        self.parse_doc()

        # update the .img_info_path file
        self.update_img_info_path()

        # construct the entries list
        entries = self.build_entries()

        # add all position specific grub entries
        entries = self.build_position_specific(entries)

        # write out the default entry number and default timeout
        # values, along with everything in entries
        self.logger.info("Writing menu.lst")
        self.write_entries(entries)


class LiveCDGrubSetup(GrubSetup, Checkpoint):
    """ LiveCDGrubSetup - class to customize the grub menu for livecd
    distributions
    """

    def __init__(self, name):
        """ constructor for class.
        """
        super(LiveCDGrubSetup, self).__init__(name)

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 1

    def build_position_specific(self, entries):
        """ class method to insert position specific entries to the menu.lst
        file.
        """
        # walk each entry in the grub_entry_list
        for grub_entry in self.grub_entry_list:
            entry = [" ".join(["title", self.grub_mods.title,
                              grub_entry.title_suffix])]
            for line in grub_entry.lines:
                entry.append("\t" + line)

            # place the entire new entry into the entries list
            if grub_entry.position is None:
                entries.append(entry)
            else:
                entries.insert(int(grub_entry.position), entry)

        return entries

    def build_entries(self):
        """ class method for constructing the entries list.
        """
        entries = []

        title = "title " + self.grub_mods.title
        kernel = "\tkernel$ /platform/i86pc/kernel/$ISADIR/unix"
        module = "\tmodule$ /platform/i86pc/$ISADIR/boot_archive"

        # create lists of grub titles, kernels, and module lines to use
        lcd_titles = [title,
                      title + " VESA driver",
                      title + " text console",
                      title + " Enable SSH"]

        lcd_kernel = [kernel,
                      kernel + " -B livemode=vesa",
                      kernel + " -B livemode=text",
                      kernel + " -B livessh=enable"]

        lcd_module = len(lcd_titles) * [module]

        # create a new list from zipper'ing each of the lists
        entries = zip(lcd_titles, lcd_kernel, lcd_module)

        # boot from hd entry.
        entries.append(("title Boot from Hard Disk", "\trootnoverify (hd0)",
                        "\tchainloader +1"))

        return entries

    def write_entries(self, entries):
        """ class method to write out everything in the entries list to the
        menu.lst file.
        """
        with open(self.menu_list, "w") as menu_lst_fh:
            menu_lst_fh.write("default %s\n" % self.grub_mods.default_entry)
            menu_lst_fh.write("timeout %s\n" % self.grub_mods.timeout)

            # livecd needs graphics entries
            menu_lst_fh.write("splashimage=/boot/grub/splash.xpm.gz\n")
            menu_lst_fh.write("foreground=343434\n")
            menu_lst_fh.write("background=F7FBFF\n")

            # write out the entries
            for entry in entries:
                for line in entry:
                    menu_lst_fh.write(line + "\n")
                menu_lst_fh.write("\n")


class TextGrubSetup(GrubSetup, Checkpoint):
    """ TextGrubSetup - class to customize the grub menu for text installer
    distributions
    """

    def __init__(self, name):
        """ constructor for class.
        """
        super(TextGrubSetup, self).__init__(name)

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 1

    def build_entries(self):
        """ class method for constructing the entries list.
        """
        title = "title " + self.grub_mods.title
        kernel = "\tkernel$ /platform/i86pc/kernel/$ISADIR/unix"
        module = "\tmodule$ /platform/i86pc/$ISADIR/boot_archive"
        entries = [[title, kernel, module]]

        # boot from hd entry.
        entries.append(["title Boot from Hard Disk",
                        "\trootnoverify (hd0)",
                        "\tchainloader +1"])
        return entries

    def write_entries(self, entries):
        """ class method to write out everything in the entries list to the
        text install menu.lst file.
        """
        with open(self.menu_list, "w") as menu_lst_fh:
            menu_lst_fh.write("default %s\n" % self.grub_mods.default_entry)
            # set the timeout for text installs to 5 seconds
            menu_lst_fh.write("timeout 5\n")

            # text installer needs to hide the menu
            menu_lst_fh.write("hiddenmenu\n")

            # write out the entries
            for entry in entries:
                for line in entry:
                    menu_lst_fh.write(line + "\n")
                menu_lst_fh.write("\n")

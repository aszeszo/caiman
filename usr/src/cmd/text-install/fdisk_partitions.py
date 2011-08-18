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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Screen for selecting to use whole disk, or a partition/slice on the disk
'''

import locale
import logging
import platform

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size
from solaris_install.text_install import _, RELEASE, TUI_HELP, LOCALIZED_GB
from solaris_install.text_install.disk_window import DiskWindow
from solaris_install.text_install.ti_target_utils import \
    get_desired_target_disk, get_solaris_partition, dump_doc, ROOT_POOL
from terminalui.base_screen import BaseScreen, SkipException
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


LOGGER = None


class FDiskPart(BaseScreen):
    '''Allow user to choose to use the whole disk, or move to the
    partition/slice edit screen.
    
    '''
    
    BOOT_TEXT = _("Boot")
    HEADER_FDISK = _("Fdisk Partitions: ")
    HEADER_PART_SLICE = _("Solaris Partition Slices")
    HEADER_SLICE = _("Solaris Slices: ")
    HEADER_TYPE_BOOTABLE = _(" %(type)s %(bootable)s")
    PARAGRAPH_FDISK = _("%(release)s can be installed on the whole "
                        "disk or a partition on the disk.") % RELEASE
    PARAGRAPH_PART_SLICE = _("%(release)s can be installed in the "
                             "whole fdisk partition or within a "
                             "slice in the partition") % RELEASE
    PARAGRAPH_SLICE = _("%(release)s can be installed on the whole"
                        " disk or a slice on the disk.") % RELEASE
    FOUND_PART = _("The following partitions were found on the disk.")
    PROPOSED_PART = _("A partition table was not found. The following is"
                      " proposed.")
    FOUND_SLICE = _("The following slices were found on the disk.")
    PROPOSED_SLICE = _("A VTOC label was not found. The following is "
                       "proposed.")
    USE_WHOLE_DISK = _("Use the whole disk")
    USE_WHOLE_PARTITION = _("Use the whole partition")
    USE_SLICE_IN_PART = _("Use a slice in the partition")
    USE_PART_IN_DISK = _("Use a partition of the disk")
    USE_SLICE_IN_DISK = _("Use a slice on the disk")
    
    SPARC_HELP = (TUI_HELP + "/%s/sparc_solaris_slices.txt",
                  _("Solaris Slices"))
    X86_PART_HELP = (TUI_HELP + "/%s/"
                     "x86_fdisk_partitions.txt",
                     _("Fdisk Partitions"))
    X86_SLICE_HELP = (TUI_HELP + "/%s/x86_fdisk_slices.txt",
                      _("Solaris Partition Slices"))
    
    def __init__(self, main_win, target_controller, x86_slice_mode=False):
        '''If x86_slice_mode == True, this screen presents options for using a
        whole partition, or a slice within the partition.
        Otherwise, it presents options for using the whole disk, or using a
        partition (x86) or slice (SPARC) within the disk
        
        '''
        super(FDiskPart, self).__init__(main_win)
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)
        self.x86_slice_mode = x86_slice_mode
        self.is_x86 = True
        self.help_format = "  %s"
        if platform.processor() == "sparc": # SPARC, slices on a disk
            self.is_x86 = False
            self.header_text = FDiskPart.HEADER_SLICE
            self.paragraph = FDiskPart.PARAGRAPH_SLICE
            self.found = FDiskPart.FOUND_SLICE
            self.proposed = FDiskPart.PROPOSED_SLICE
            self.use_whole = FDiskPart.USE_WHOLE_DISK
            self.use_part = FDiskPart.USE_SLICE_IN_DISK
            self.help_data = FDiskPart.SPARC_HELP
        elif self.x86_slice_mode: # x86, slices within a partition
            self.instance = ".slice"
            self.header_text = FDiskPart.HEADER_PART_SLICE
            self.paragraph = FDiskPart.PARAGRAPH_PART_SLICE
            self.found = FDiskPart.FOUND_SLICE
            self.proposed = FDiskPart.PROPOSED_SLICE
            self.use_whole = FDiskPart.USE_WHOLE_PARTITION
            self.use_part = FDiskPart.USE_SLICE_IN_PART
            self.help_data = FDiskPart.X86_SLICE_HELP
            self.help_format = "    %s"
        else: # x86, partitions on a disk
            self.header_text = FDiskPart.HEADER_FDISK
            self.paragraph = FDiskPart.PARAGRAPH_FDISK
            self.found = FDiskPart.FOUND_PART
            self.proposed = FDiskPart.PROPOSED_PART
            self.use_whole = FDiskPart.USE_WHOLE_DISK
            self.use_part = FDiskPart.USE_PART_IN_DISK
            self.help_data = FDiskPart.X86_PART_HELP
        self.disk_win = None
        self.partial_disk_item = None
        self.whole_disk_item = None
        self.disk = None 
        self.tc = target_controller
        self.use_whole_segment = True
    
    def _show(self):
        '''Display partition data for selected disk, and present the two
        choices
        
        '''
        doc = InstallEngine.get_instance().doc
        
        if self.x86_slice_mode:

            disk = get_desired_target_disk(doc)
            if disk.whole_disk:
                raise SkipException

            sol_partition = get_solaris_partition(doc)

            LOGGER.debug("Working with the following partition:")
            LOGGER.debug(str(sol_partition))

            if sol_partition is None:
                # Must have a Solaris partition
                err_msg = "Critical error - no Solaris partition found"
                LOGGER.error(err_msg)
                raise ValueError(err_msg)

            # See if there are any slices in the partition
            all_slices = sol_partition.get_children(class_type=Slice)

            if not all_slices:
                LOGGER.info("No previous slices found")

                # Setting the in_zpool flag to indicate the whole
                # partition should be used.  The needed underlying
                # slices will be created in the next step when
                # the in_zpool flag is detected.
                sol_partition.in_zpool = ROOT_POOL

                raise SkipException
                    
            LOGGER.debug("Preserved partition with existing slices, "
                         "presenting option to install into a slice")

            self.disk = sol_partition

        else:

            self.disk = get_desired_target_disk(doc)

            LOGGER.debug("Working with the following disk:")
            LOGGER.debug(str(self.disk))

            if self.disk.whole_disk:
                LOGGER.debug("disk.whole_disk=True, skip editting")
                raise SkipException

            if self.disk.is_boot_disk():
                bootable = FDiskPart.BOOT_TEXT
            else:
                bootable = u""
            disk_size_gb_str = locale.format("%.1f",
                self.disk.disk_prop.dev_size.get(Size.gb_units)) + LOCALIZED_GB

            type_bootable_str = FDiskPart.HEADER_TYPE_BOOTABLE % \
                {"type": self.disk.disk_prop.dev_type,
                 "bootable": bootable}

            header_text = self.header_text + disk_size_gb_str + \
                type_bootable_str
            self.main_win.set_header_text(header_text)

        y_loc = 1
        y_loc += self.center_win.add_paragraph(self.paragraph, start_y=y_loc)
        
        y_loc += 1
        if self.is_x86 and not self.x86_slice_mode:
            all_parts = self.disk.get_children(class_type=Partition)
        else:
            all_parts = self.disk.get_children(class_type=Slice)

        found_parts = bool(all_parts)

        if found_parts:
            next_line = self.found
        else:
            next_line = self.proposed
        y_loc += self.center_win.add_paragraph(next_line, start_y=y_loc)
        
        y_loc += 1
        disk_win_area = WindowArea(6, 70, y_loc, 0)
        self.disk_win = DiskWindow(disk_win_area, self.disk,
                                   target_controller=self.tc,
                                   window=self.center_win)
        y_loc += disk_win_area.lines
        
        y_loc += 3
        whole_disk_width = textwidth(self.use_whole) + 3
        cols = (self.win_size_x - whole_disk_width) / 2
        whole_disk_item_area = WindowArea(1, whole_disk_width, y_loc, cols)
        self.whole_disk_item = ListItem(whole_disk_item_area,
                                        window=self.center_win,
                                        text=self.use_whole,
                                        centered=True)
        
        y_loc += 1
        partial_width = textwidth(self.use_part) + 3
        cols = (self.win_size_x - partial_width) / 2
        partial_item_area = WindowArea(1, partial_width, y_loc, cols)
        self.partial_disk_item = ListItem(partial_item_area,
                                          window=self.center_win,
                                          text=self.use_part,
                                          centered=True)
        
        self.main_win.do_update()
        if self.use_whole_segment:
            self.center_win.activate_object(self.whole_disk_item)
        else:
            self.center_win.activate_object(self.partial_disk_item)
    
    def on_continue(self):
        '''Set the user's selection in the install target. If they chose
        to use the entire disk (or entire partition), define a single
        partition (or slice) to consume the whole disk (or partition)
        
        '''

        if self.center_win.get_active_object() is self.whole_disk_item:
            self.use_whole_segment = True
            if isinstance(self.disk, Disk):
                LOGGER.debug("Setting whole_disk and creating default"
                             " layout for %s", self.disk)
                disk = self.tc.select_disk(self.disk, use_whole_disk=True)[0]
                disk.whole_disk = True
            else: 
                # it's a partition, set the in_zpool attribute in
                # the object for now.  The next screen will
                # fill in needed slices
                self.disk.in_zpool = ROOT_POOL
        else:
            self.use_whole_segment = False
            if isinstance(self.disk, Disk):
                LOGGER.debug("Setting whole_disk to false")
                self.disk.whole_disk = False
            else:
                self.disk.in_zpool = None

        dump_doc("At the end of fdisk_partitions.continue")

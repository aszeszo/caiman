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

import logging
import platform

from osol_install.profile.install_profile import INSTALL_PROF_LABEL
from osol_install.text_install import _, RELEASE, TUI_HELP
from osol_install.text_install.disk_window import DiskWindow
from solaris_install.engine import InstallEngine
from terminalui.base_screen import BaseScreen, SkipException
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


class FDiskPart(BaseScreen):
    '''Allow user to choose to use the whole disk, or move to the
    partition/slice edit screen.
    
    '''
    
    BOOT_TEXT = _("Boot")
    HEADER_FDISK = _("Fdisk Partitions: %(size).1fGB %(type)s %(bootable)s")
    HEADER_PART_SLICE = _("Solaris Partition Slices")
    HEADER_SLICE = _("Solaris Slices: %(size).1fGB %(type)s %(bootable)s")
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
    
    def __init__(self, main_win, x86_slice_mode=False):
        '''If x86_slice_mode == True, this screen presents options for using a
        whole partition, or a slice within the partition.
        Otherwise, it presents options for using the whole disk, or using a
        partition (x86) or slice (SPARC) within the disk
        
        '''
        super(FDiskPart, self).__init__(main_win)
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
        self.disk_info = None
        self.disk_win = None
        self.partial_disk_item = None
        self.whole_disk_item = None
    
    def _show(self):
        '''Display partition data for selected disk, and present the two
        choices
        
        '''
        doc = InstallEngine.get_instance().doc
        self.install_profile = doc.get_descendants(name=INSTALL_PROF_LABEL,
                                                   not_found_is_err=True)[0]
        
        if self.x86_slice_mode:
            disk = self.install_profile.disk
            self.disk_info = disk.get_solaris_data()
            if self.disk_info is None:
                err_msg = "Critical error - no Solaris partition found"
                logging.error(err_msg)
                raise ValueError(err_msg)
            logging.debug("bool(self.disk_info.slices)=%s",
                          bool(self.disk_info.slices))
            logging.debug("self.disk_info.modified()=%s",
                          self.disk_info.modified())
            if not self.disk_info.slices or self.disk_info.modified():
                logging.debug("Setting partition.use_whole_segment,"
                              "creating default layout, and skipping")
                self.disk_info.use_whole_segment = True
                # We only do slice level editing on x86 if there are
                # existing slices on an existing (unmodified)Solaris
                # partition
                self.disk_info.create_default_layout()
                raise SkipException
            disp_disk = self.install_profile.original_disk.get_solaris_data()
            logging.debug("Preserved partition with existing slices:"
                          " presenting option to install into a slice")
        else:
            self.disk_info = self.install_profile.disk
            disp_disk = self.install_profile.original_disk
            if self.disk_info.boot:
                bootable = FDiskPart.BOOT_TEXT
            else:
                bootable = u""
            header_text = self.header_text % \
                            {"size" : self.disk_info.size.size_as("gb"),
                             "type" : self.disk_info.type,
                             "bootable" : bootable}
            self.main_win.set_header_text(header_text)
        
        y_loc = 1
        y_loc += self.center_win.add_paragraph(self.paragraph, start_y=y_loc)
        
        y_loc += 1
        if self.is_x86 and not self.x86_slice_mode:
            found_parts = bool(self.disk_info.partitions)
        else:
            found_parts = bool(self.disk_info.slices)
        if found_parts:
            next_line = self.found
        else:
            next_line = self.proposed
        y_loc += self.center_win.add_paragraph(next_line, start_y=y_loc)
        
        y_loc += 1
        disk_win_area = WindowArea(6, 70, y_loc, 0)
        self.disk_win = DiskWindow(disk_win_area, disp_disk,
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
        if self.disk_info.use_whole_segment:
            self.center_win.activate_object(self.whole_disk_item)
        else:
            self.center_win.activate_object(self.partial_disk_item)
    
    def on_continue(self):
        '''Set the user's selection in the install_profile. If they chose
        to use the entire disk (or entire partition), define a single
        partition (or slice) to consume the whole disk (or partition)
        
        '''
        if self.center_win.get_active_object() is self.whole_disk_item:
            logging.debug("Setting use_whole_segment and creating default"
                          " layout for %s", type(self.disk_info))
            self.disk_info.use_whole_segment = True
            self.disk_info.create_default_layout()
        else:
            logging.debug("Setting use_whole segment false for %s",
                          type(self.disk_info))
            # If user had previously selected to use the whole disk
            # or partition, set the do_revert flag so that the following
            # screen will know to reset the disk (reverting the call
            # to create_default_layout, above)
            self.disk_info.do_revert = self.disk_info.use_whole_segment
            self.disk_info.use_whole_segment = False

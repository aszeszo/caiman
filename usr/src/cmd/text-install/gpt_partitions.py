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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Screen for selecting to use whole disk, or a GPT partition
'''

import locale
import logging
import platform

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import DEFAULT_VDEV_NAME, \
    DEFAULT_ZPOOL_NAME
from solaris_install.target.physical import GPTPartition
from solaris_install.target.size import Size
from solaris_install.text_install import _, can_use_gpt, RELEASE, TUI_HELP, \
    LOCALIZED_GB
from solaris_install.text_install.disk_window import DiskWindow
from solaris_install.text_install.ti_target_utils import \
    dump_doc, get_desired_target_disk, get_solaris_partition, get_solaris_slice
from terminalui.base_screen import BaseScreen, SkipException, UIMessage
from terminalui.error_window import ErrorWindow
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


LOGGER = None


class GPTPart(BaseScreen):
    '''Allow user to choose to use the whole disk, or move to the
    GPT partition edit screen.
    '''

    BOOT_TEXT = _("Boot")
    HEADER_TYPE_BOOTABLE = _(" %(type)s %(bootable)s")
    USE_WHOLE_DISK = _("Use the whole disk")
    HEADER_GPT = _("GPT Partitions: ")
    PARAGRAPH = _("%(release)s can be installed on the whole disk or a "
                  "GPT partition on the disk.") % RELEASE
    FOUND_PART = _("The following GPT partitions were found on the disk.")
    PROPOSED_PART = _("A partition table was not found. The following is "
                      "proposed.")
    USE_WHOLE_DISK = _("Use the entire disk")
    USE_PART_IN_DISK = _("Use a GPT partition of the disk")
    GPT_HELP = (TUI_HELP + "%s/gpt_partitions.txt", _("GPT Partitions"))

    def __init__(self, main_win, target_controller):
        super(GPTPart, self).__init__(main_win)
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.help_format = "  %s"
        self.header_text = GPTPart.HEADER_GPT
        self.found = GPTPart.FOUND_PART
        self.proposed = GPTPart.PROPOSED_PART
        self.use_whole = GPTPart.USE_WHOLE_DISK
        self.use_part = GPTPart.USE_PART_IN_DISK
        self.help_data = GPTPart.GPT_HELP
        self.disk_win = None
        self.whole_disk_item = None
        self.partial_disk_item = None
        self.relabel_disk_item = None
        self.disk = None
        self.tc = target_controller
        self.use_whole_segment = True
        self.paragraph = GPTPart.PARAGRAPH

    def _show(self):
        '''Display partition data for selected disk, and present the two
        choices
        '''

        doc = InstallEngine.get_instance().doc
        disk = get_desired_target_disk(doc)

        # verify the desired disk has a GPT partition table
        if disk.label == "VTOC":
            raise SkipException

        self.disk = disk

        LOGGER.debug("Working with the following disk:")
        LOGGER.debug(str(self.disk))

        # set the header of the screen
        if self.disk.is_boot_disk():
            bootable = GPTPart.BOOT_TEXT
        else:
            bootable = u""

        disk_size_gb_str = locale.format("%.1f",
            self.disk.disk_prop.dev_size.get(Size.gb_units)) + LOCALIZED_GB

        type_bootable_str = GPTPart.HEADER_TYPE_BOOTABLE % \
            {"type": self.disk.disk_prop.dev_type, "bootable": bootable}

        header_text = self.header_text + disk_size_gb_str + type_bootable_str
        self.main_win.set_header_text(header_text)

        if self.disk.whole_disk:
            LOGGER.debug("disk.whole_disk=True, skip editting")
            raise SkipException

        y_loc = 1
        y_loc += self.center_win.add_paragraph(self.paragraph, start_y=y_loc)

        y_loc += 1
        gpt_partitions = self.disk.get_children(class_type=GPTPartition)
        if gpt_partitions:
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
        '''Set the user's selection in the install target.
        '''

        active_object = self.center_win.get_active_object()
        if active_object is self.whole_disk_item:
            LOGGER.debug("Setting whole_disk for %s", self.disk)
            self.use_whole_segment = True
            self.disk = self.tc.select_disk(self.disk, use_whole_disk=True)[0]
        else:
            LOGGER.debug("Setting whole_disk to false")
            self.use_whole_segment = False
            self.disk.whole_disk = False

        dump_doc("At the end of gpt_partitions.continue")

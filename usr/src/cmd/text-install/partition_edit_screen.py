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
UI Components for displaying a screen allowing the user to edit
partition and slice information
'''

import curses
import locale
import logging
import platform

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import DEFAULT_VDEV_NAME
from solaris_install.target.libadm.const import V_ROOT
from solaris_install.target.physical import Partition, Slice
from solaris_install.target.size import Size
from solaris_install.text_install import _, RELEASE, TUI_HELP, LOCALIZED_GB
from solaris_install.text_install.disk_window import DiskWindow
from solaris_install.text_install.ti_target_utils import \
    get_desired_target_disk, get_solaris_partition, perform_final_validation, \
    ROOT_POOL
from terminalui import LOG_LEVEL_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen, SkipException
from terminalui.window_area import WindowArea

LOGGER = None


class PartEditScreen(BaseScreen):
    '''Allows user editing of partitions on a disk, or slices on a
    disk/partition
    
    '''
    
    PARTITION_PARAGRAPH = _("Oracle Solaris will be installed into the Solaris"
                            " partition. A partition's type can be changed"
                            " using the F5 key.\n\n"
                            "A partition's size can be increased "
                            "up to its Avail space. Avail space can be "
                            "increased by deleting an adjacent partition. "
                            "Delete a partition by changing it to \"Unused\""
                            " using the F5 key.\n\n"
                            "The four primary partition slots are listed on "
                            "the left. If one is an \"Extended\" partition "
                            "its logical partitions are listed on the "
                            "right.") % RELEASE
    SLICE_PARAGRAPH = _("%(release)s will be installed in the \"%(pool)s\" "
                        "slice. Use the F5 key to change a slice to "
                        "\"%(pool)s.\"\n\n"
                        "A slice's size can be increased up to its Avail "
                        "size. Avail can be increased by deleting an adjacent"
                        " slice. Use the F5 key to delete a slice by changing"
                        " it to \"Unused.\"\n\n"
                        "Slices are listed in disk layout order.")
    
    HEADER_x86_PART = _("Select Partition: ")
    HEADER_x86_SLICE = _("Select Slice in Fdisk Partition")
    HEADER_SPARC_SLICE = _("Select Slice: ")
    HEADER_TYPE_BOOTABLE = _(" %(type)s %(bootable)s")
    SLICE_DESTROY_TEXT = _("indicates the slice's current content will be "
                           "destroyed")
    PART_DESTROY_TEXT = _("indicates the partition's current content will "
                          "be destroyed")
    BOOTABLE = _("Boot")
    
    SPARC_HELP = (TUI_HELP + "/%s/"
                  "sparc_solaris_slices_select.txt",
                  _("Select Slice"))
    X86_PART_HELP = (TUI_HELP + "/%s/"
                     "x86_fdisk_partitions_select.txt",
                     _("Select Partition"))
    X86_SLICE_HELP = (TUI_HELP + "/%s/"
                      "x86_fdisk_slices_select.txt",
                      _("Select Slice"))
    
    HELP_FORMAT = "    %s"
    
    def __init__(self, main_win, target_controller, x86_slice_mode=False):
        super(PartEditScreen, self).__init__(main_win)

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.x86_slice_mode = x86_slice_mode
        self.is_x86 = (platform.processor() == "i386")
        self.header_text = platform.processor()
        
        if self.x86_slice_mode: # x86, Slice within a partition
            self.instance = ".slice"
            self.header_text = PartEditScreen.HEADER_x86_SLICE
            self.paragraph_text = PartEditScreen.SLICE_PARAGRAPH
            self.destroy_text = PartEditScreen.SLICE_DESTROY_TEXT
            self.help_data = PartEditScreen.X86_SLICE_HELP
        elif self.is_x86: # x86, Partition on disk
            self.header_text = PartEditScreen.HEADER_x86_PART
            self.paragraph_text = PartEditScreen.PARTITION_PARAGRAPH
            self.destroy_text = PartEditScreen.PART_DESTROY_TEXT
            self.help_data = PartEditScreen.X86_PART_HELP
        else: # SPARC (Slice on disk)
            self.header_text = PartEditScreen.HEADER_SPARC_SLICE
            self.paragraph_text = PartEditScreen.SLICE_PARAGRAPH
            self.destroy_text = PartEditScreen.SLICE_DESTROY_TEXT
            self.help_data = PartEditScreen.SPARC_HELP
            self.help_format = "  %s"
        
        self.disk_win = None
        self.tc = target_controller
    
    def set_actions(self):
        '''Edit Screens add 'Reset' and 'Change Type' actions. Since these
        do not manipulate screen direction, they are captured during
        processing by adding them to center_win's key_dict.
        
        '''
        super(PartEditScreen, self).set_actions()
        reset_action = Action(curses.KEY_F7, _("Reset"))
        change_action = Action(curses.KEY_F5, _("Change Type"))
        self.main_win.actions[reset_action.key] = reset_action
        self.main_win.actions[change_action.key] = change_action
        self.center_win.key_dict[curses.KEY_F7] = self.on_key_F7
    
    # pylint: disable-msg=C0103
    # F7 is the keyname and appropriate here
    def on_key_F7(self, dummy):
        '''F7 -> Reset the DiskWindow'''
        self.disk_win.reset()
        return None
    
    def _show(self):
        '''Display the explanatory paragraph and create the DiskWindow'''

        doc = InstallEngine.get_instance().doc

        if self.x86_slice_mode:

            LOGGER.debug("in x86 slice mode")

            disk = get_desired_target_disk(doc)
            if disk.whole_disk:
                LOGGER.debug("disk.whole_disk=True, skip editting")
                disk.whole_disk = False

                # perform final target validation
                perform_final_validation(doc)

                raise SkipException

            part = get_solaris_partition(doc)

            LOGGER.debug(str(part))
            if part is None:
                err_msg = "Critical error - no Solaris partition found"
                LOGGER.error(err_msg)
                raise ValueError(err_msg)
            if part.in_zpool is not None:
                LOGGER.debug("Whole partition selected. Skipping slice edit")
                LOGGER.debug(str(part))

                #
                # remove the in_zpool value from partition, delete
                # any existing slices, and create
                # the needed underneath slices
                #
                # All the logic from here to the part.bootid line
                # can be removed when GPT partitions is supported.
                #

                existing_slices = part.get_children(class_type=Slice)
                if existing_slices:
                    for ex_slice in existing_slices:
                        part.delete_slice(ex_slice)

                pool_name = part.in_zpool
                slice0 = part.add_slice(0, part.start_sector, \
                    part.size.sectors, Size.sector_units, in_zpool=pool_name, \
                    in_vdev=DEFAULT_VDEV_NAME)
                slice0.tag = V_ROOT
                LOGGER.debug(str(part))

                part.in_zpool = None
                part.bootid = Partition.ACTIVE

                # Make sure in_zpool is not set on the Disk, target controller
                # puts it there in some cases
                disk.in_zpool = None

                # perform final target validation
                perform_final_validation(doc)

                raise SkipException
        else:

            # get selected disk from desired target
            disk = get_desired_target_disk(doc)

            LOGGER.debug("disk.whole_disk: %s", disk.whole_disk)
            LOGGER.debug(str(disk))

            if disk.whole_disk:
                LOGGER.debug("disk.whole_disk true, skipping editing")

                if not self.is_x86:
                    # Unset this so Target Instantiation works correctly
                    disk.whole_disk = False

                    # perform final target validation
                    perform_final_validation(doc)

                raise SkipException

            part = disk
        
        if self.x86_slice_mode:
            header = self.header_text
        else:
            bootable = ""
            if self.is_x86 and disk.is_boot_disk():
                bootable = PartEditScreen.BOOTABLE
            disk_size_str = locale.format("%.1f",
                disk.disk_prop.dev_size.get(Size.gb_units)) + LOCALIZED_GB
            type_boot_str = PartEditScreen.HEADER_TYPE_BOOTABLE % \
                {"type": disk.disk_prop.dev_type,
                 "bootable": bootable}
            header = self.header_text + disk_size_str + type_boot_str
        self.main_win.set_header_text(header)
        
        y_loc = 1
        fmt_dict = {'pool': ROOT_POOL}
        fmt_dict.update(RELEASE)
        y_loc += self.center_win.add_paragraph(self.paragraph_text % fmt_dict,
                                               y_loc)
        
        y_loc += 1
        disk_win_area = WindowArea(6, 70, y_loc, 0)

        self.disk_win = DiskWindow(disk_win_area, part,
                                   window=self.center_win,
                                   editable=True,
                                   error_win=self.main_win.error_line,
                                   target_controller=self.tc)
        y_loc += disk_win_area.lines
        
        y_loc += 1
        LOGGER.log(LOG_LEVEL_INPUT, "calling addch with params start_y=%s,"
                    "start_x=%s, ch=%c", y_loc, self.center_win.border_size[1],
                    DiskWindow.DESTROYED_MARK)
        self.center_win.window.addch(y_loc, self.center_win.border_size[1],
                                     DiskWindow.DESTROYED_MARK,
                                     self.center_win.color_theme.inactive)
        self.center_win.add_text(self.destroy_text, y_loc, 2)
        
        self.main_win.do_update()
        self.center_win.activate_object(self.disk_win)
    
    def validate(self):
        ''' Perform final validation of the desired target
        '''

        if self.is_x86 and not self.x86_slice_mode:
            # delay final validation for x86 until slice mode
            # is completed.
            return

        # perform final target validation
        doc = InstallEngine.get_instance().doc

        if self.is_x86:
            solaris_part = get_solaris_partition(doc)
            if solaris_part is None:
                raise RuntimeError("No Solaris2 partition in desired target")
            solaris_part.bootid = Partition.ACTIVE

        perform_final_validation(doc)

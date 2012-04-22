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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
UI Components for displaying a screen allowing the user to edit partition and
slice information
'''

import curses
import locale
import logging
import platform

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import DEFAULT_VDEV_NAME, \
    DEFAULT_ZPOOL_NAME
from solaris_install.target.libadm.const import V_ROOT
from solaris_install.target.physical import GPTPartition, \
    InsufficientSpaceError, NoPartitionSlotsFree, NoGPTPartitionSlotsFree, \
    Partition
from solaris_install.target.size import Size
from solaris_install.text_install import _, RELEASE, TUI_HELP, LOCALIZED_GB
from solaris_install.text_install.disk_window import DiskWindow
from solaris_install.text_install.ti_target_utils import \
    get_desired_target_disk, get_solaris_partition, perform_final_validation, \
    ROOT_POOL
from terminalui import LOG_LEVEL_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen, SkipException, UIMessage
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

    X86_SELECTION_ERROR = _("A 'Solaris2' partition must be selected for "
                            "installation")
    SPARC_SELECTION_ERROR = _("An 'rpool' slice must be selected for "
                              "installation")
    HELP_FORMAT = "    %s"

    def __init__(self, main_win, target_controller, x86_slice_mode=False):
        super(PartEditScreen, self).__init__(main_win)

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.x86_slice_mode = x86_slice_mode
        self.is_x86 = platform.processor() == "i386"
        self.doc = InstallEngine.get_instance().doc

        if self.x86_slice_mode:  # x86, Slice within a partition
            self.instance = ".slice"
            self.header_text = PartEditScreen.HEADER_x86_SLICE
            self.paragraph_text = PartEditScreen.SLICE_PARAGRAPH
            self.destroy_text = PartEditScreen.SLICE_DESTROY_TEXT
            self.help_data = PartEditScreen.X86_SLICE_HELP
        elif self.is_x86:  # x86, Partition on disk
            self.header_text = PartEditScreen.HEADER_x86_PART
            self.paragraph_text = PartEditScreen.PARTITION_PARAGRAPH
            self.destroy_text = PartEditScreen.PART_DESTROY_TEXT
            self.help_data = PartEditScreen.X86_PART_HELP
        else:  # SPARC (Slice on disk)
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

    def on_key_F7(self, dummy):
        '''F7 -> Reset the DiskWindow'''
        self.disk_win.reset()

    def _show(self):
        '''Display the explanatory paragraph and create the DiskWindow'''

        disk = get_desired_target_disk(self.doc)
        if disk.label == "GPT":
            raise SkipException

        if disk.whole_disk:
            LOGGER.debug("disk.whole_disk=True, skip editting")

            # perform final target validation
            perform_final_validation(self.doc)

            raise SkipException

        if self.x86_slice_mode:
            LOGGER.debug("in x86 slice mode")
            part = get_solaris_partition(self.doc)

            LOGGER.debug(str(part))
            if part is None:
                err_msg = "Critical error - no Solaris partition found"
                LOGGER.error(err_msg)
                raise ValueError(err_msg)
            if part.in_zpool is not None:
                LOGGER.debug("Whole partition selected. Skipping slice edit")
                LOGGER.debug(str(part))

                # remove the in_zpool value from partition, delete any existing
                # slices, and create the needed underneath slices
                part.create_entire_partition_slice(in_zpool=part.in_zpool,
                    in_vdev=DEFAULT_VDEV_NAME, tag=V_ROOT)

                part.bootid = Partition.ACTIVE
                part.in_zpool = None

                LOGGER.debug(str(part))

                # Make sure in_zpool is not set on the Disk, target controller
                # puts it there in some cases
                disk.in_zpool = None

                # perform final target validation
                perform_final_validation(self.doc)

                raise SkipException
        else:
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

        if self.is_x86:
            solaris_part = get_solaris_partition(self.doc)
            if solaris_part is None:
                raise UIMessage(PartEditScreen.X86_SELECTION_ERROR)

            disk = solaris_part.parent

            # unset in_zpool and in_vdev on the partiton and the parent Disk.
            # This is a workaround to CR 7085718
            solaris_part.in_zpool = None
            solaris_part.in_vdev = None
            disk.in_zpool = None
            disk.in_vdev = None

            # create system partitions if required
            try:
                efi_sys, resv, solaris_part = \
                    disk.add_required_partitions(solaris_part)
                LOGGER.debug("EFI System Partition:  %s", str(efi_sys))
                # resv is always None as it is GPT specific so don't log it

            except NoPartitionSlotsFree:
                # If there are no unused partitions left we can't proceed
                LOGGER.warning("No free slots available for EFI system "
                               "partition.")
                raise UIMessage("Too many partitions.  Delete unnecessary "
                                "partitions.")

            except InsufficientSpaceError as ise:
                raise RuntimeError("INTERNAL ERROR: Could not allocate space "
                    "for EFI system partition on disk %s: %s"
                    % (disk, str(ise)))

            if not self.x86_slice_mode:
                # delay final validation for x86 until slice mode is
                # completed.
                return

            # final target validation will be performed now
            solaris_part.bootid = Partition.ACTIVE

        else:
            inner_window = self.disk_win.get_active_object()
            edit_object = inner_window.get_active_object()
            ui_object = edit_object.get_active_object()
            if ui_object is None:
                raise UIMessage(PartEditScreen.SPARC_SELECTION_ERROR)

        perform_final_validation(self.doc)


class GPTPartEditScreen(PartEditScreen):
    """ subclass to handle GPT specific disks
    """

    GPT_PARTITION_PARAGRAPH = _("Oracle Solaris will be installed into the "
                                "highlighted Solaris partition. A partition's "
                                "type can be changed using the F5 key.\n\n"
                                "A partition's size can be increased up to "
                                "its Avail space. Avail space can be "
                                "increased by deleting an adjacent partition. "
                                "Delete a partition by changing it to "
                                "\"Unused\"" " using the F5 key.") % RELEASE
    GPT_PART_DESTROY_TEXT = _("indicates the partition's current content will "
                             "be destroyed")
    HEADER_GPT = _("Select GPT Partition: ")
    GPT_HELP = (TUI_HELP + "/%s/gpt_partitions_select.txt",
                _("Select GPT Partition"))
    SELECTION_ERROR = _("A 'Solaris' partition must be selected for "
                        "installation")

    def __init__(self, main_win, target_controller):
        super(GPTPartEditScreen, self).__init__(main_win, target_controller)

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.doc = InstallEngine.get_instance().doc

        self.header_text = GPTPartEditScreen.HEADER_GPT
        self.paragraph_text = GPTPartEditScreen.GPT_PARTITION_PARAGRAPH
        self.destroy_text = GPTPartEditScreen.GPT_PART_DESTROY_TEXT
        self.help_data = GPTPartEditScreen.GPT_HELP

        self.disk_win = None
        self.tc = target_controller

    def _show(self):
        '''Display the explanatory paragraph and create the DiskWindow'''

        disk = get_desired_target_disk(self.doc)
        if disk.label == "VTOC":
            raise SkipException

        if disk.whole_disk:
            LOGGER.debug("disk.whole_disk=True, skip editting")

            # perform final target validation
            perform_final_validation(self.doc)

            raise SkipException

        part = disk

        bootable = ""
        if self.is_x86 and disk.is_boot_disk():
            bootable = PartEditScreen.BOOTABLE

        disk_size_str = locale.format("%.1f",
            disk.disk_prop.dev_size.get(Size.gb_units)) + LOCALIZED_GB
        type_boot_str = PartEditScreen.HEADER_TYPE_BOOTABLE % \
            {"type": disk.disk_prop.dev_type, "bootable": bootable}
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

        # Before validation can happen, we need to set the in_zpool and in_vdev
        # attributes on *ONLY* the GPT partition the user selected.  We provide
        # the ability for the user to create multiple 'solaris' GPT partitions,
        # but we only use one of them for the root pool.
        # If there are multiple Solaris partitions the user must select one
        # explicitly by highlighting it. If there is only one though, its
        # selection is implicit.
        gpt_partition = None
        disk = get_desired_target_disk(self.doc)

        # In order to get to the specific DOC object we need to translate
        # through the many window layers:
        # main_win.disk_win.[left | right]_win.list_obj.edit_obj.UI_obj.DOC_obj
        inner_window = self.disk_win.get_active_object()
        edit_object = inner_window.get_active_object()
        ui_object = edit_object.get_active_object()

        # trap on any non Solaris partition
        if ui_object is None:
            parts = disk.get_children(class_type=GPTPartition)
            if parts:
                solparts = [p for p in parts if p.is_solaris]
                # Only one Solaris partition, so its selection is implicit.
                if len(solparts) == 1:
                    gpt_partition = solparts[0]

            if gpt_partition is None:
                raise UIMessage(GPTPartEditScreen.SELECTION_ERROR)
        else:
            gpt_partition = ui_object.data_obj.doc_obj

        # unset in_zpool and in_vdev on the parent Disk object
        disk.in_zpool = None
        disk.in_vdev = None

        # unset in_zpool and in_vdev on all other GPT Partitions on this disk
        for entry in disk.get_children(class_type=GPTPartition):
            if entry.name != gpt_partition.name:
                entry.in_zpool = None
                entry.in_vdev = None

        # Set in_zpool, in_vdev and the action for this partition
        gpt_partition.in_zpool = DEFAULT_ZPOOL_NAME
        gpt_partition.in_vdev = DEFAULT_VDEV_NAME
        gpt_partition.action = "create"

        # create required EFI System or BIOS boot partitions and reserved
        # partitions
        try:
            sys_part, resv_part, gpt_partition = \
                disk.add_required_partitions(donor=gpt_partition)
            LOGGER.debug("System/Boot Partition:  %s", str(sys_part))
            LOGGER.debug("Reserved Partition:  %s", str(resv_part))

        except NoGPTPartitionSlotsFree:
            # If there are no unused partitions left we can't proceed
            LOGGER.warning("No free slots available for boot partition.")
            raise UIMessage("Too many partitions.  Delete unnecessary "
                            "partitions.")

        except InsufficientSpaceError as ise:
            raise RuntimeError("INTERNAL ERROR: Could not allocate space "
                "for system partition or reserved partition on disk %s: "
                "%s" % (disk, str(ise)))

        perform_final_validation(self.doc)

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
Screens and functions to display a list of disks to the user.
'''

import curses
import locale
import logging
import platform

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc

from bootmgmt.bootinfo import SystemFirmware
from solaris_install.text_install import _, RELEASE, TUI_HELP, \
    TARGET_DISCOVERY, TRANSFER_PREP, LOCALIZED_GB
from solaris_install.text_install.disk_window import DiskWindow, \
    get_minimum_size, get_recommended_size
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.controller import FALLBACK_IMAGE_SIZE
from solaris_install.target.physical import Disk, GPTPartition, Partition, \
    Slice
from solaris_install.target.size import Size
from solaris_install.text_install import can_use_gpt
from solaris_install.text_install.ti_target_utils import MAX_VTOC
from solaris_install.transfer.media_transfer import get_image_size
from terminalui.base_screen import BaseScreen, QuitException, UIMessage
from terminalui.i18n import fit_text_truncate, textwidth, ljust_columns
from terminalui.list_item import ListItem
from terminalui.scroll_window import ScrollWindow
from terminalui.window_area import WindowArea

LOGGER = None


class TargetDiscoveryError(StandardError):
    '''Class for target discovery related errors'''
    pass


class DiskScreen(BaseScreen):
    '''
    Allow the user to select a (valid) disk target for installation
    Display the partition/slice table for the highlighted disk
    
    '''
    
    HEADER_TEXT = _("Disks")
    PARAGRAPH = _("Where should %(release)s be installed?") % RELEASE
    REC_SIZE_TEXT = _("Recommended size: ")
    MIN_SIZE_TEXT = _("    Minimum size: ")
    DISK_SEEK_TEXT = _("Seeking disks on system")
    FOUND_x86 = _("The following partitions were found on the disk.")
    FOUND_SPARC = _("The following slices were found on the disk.")
    FOUND_GPT = _("The following GPT partitions were found on the disk.")
    PROPOSED_x86 = _("A partition table was not found. The following is "
                     "proposed.")
    PROPOSED_SPARC = _("A VTOC label was not found. The following "
                       "is proposed.")
    PROPOSED_GPT = _("A GPT labeled disk was not found. The following is "
                     "proposed.")
    TOO_SMALL = "<"
    TOO_BIG = ">"
    INVALID_DISK = "!"
    GPT_LABELED = _("GPT labeled disk")
    NO_DISKS = _("No disks found. Additional device drivers may "
                 "be needed.")
    NO_TARGETS = _("%(release)s cannot be installed on any disk") % RELEASE
    TGT_ERROR = _("An error occurred while searching for installation"
                  " targets. Please check the install log and file a bug"
                  " at defect.opensolaris.org.")
    
    DISK_HEADERS = [(8, _("Type")),
                    (10, _(" Size(GB)")),
                    (6, _("Boot")),
                    (44, _("Device")),
                    (3, "")]  # blank header for the notes column
    VENDOR_LEN = 15

    SPINNER = ["\\", "|", "/", "-"]
    
    DISK_WARNING_HEADER = _("Warning")
    DISK_WARNING_TOOBIG = _("Only the first %.1fTB can be used.")
    DISK_WARNING_RELABEL = _("You have chosen a GPT labeled disk. Installing "
                             "onto this disk requires it to be relabeled as "
                             "SMI. This causes IMMEDIATE LOSS of all data "
                             "on the disk. Select Continue only if you are "
                             "prepared to erase all data on this disk now.")

    CANCEL_BUTTON = _("Cancel")
    CONTINUE_BUTTON = _("Continue")
    
    HELP_DATA = (TUI_HELP + "/%s/disks.txt", _("Disks"))
    
    def __init__(self, main_win, target_controller):

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(DiskScreen, self).__init__(main_win)
        if platform.processor() == "i386":
            self.found_text = DiskScreen.FOUND_x86
            self.proposed_text = DiskScreen.PROPOSED_x86
        else:
            self.found_text = DiskScreen.FOUND_SPARC
            self.proposed_text = DiskScreen.PROPOSED_SPARC

        self.gpt_found_text = DiskScreen.FOUND_GPT
        self.gpt_proposed_text = DiskScreen.PROPOSED_GPT
        
        disk_header_text = []
        for header in DiskScreen.DISK_HEADERS:
            header_str = fit_text_truncate(header[1], header[0] - 1,
                                           just="left")
            disk_header_text.append(header_str)

        self.disk_header_text = " ".join(disk_header_text)
        self.max_vtoc_disk_size = (Size(MAX_VTOC)).get(Size.tb_units)
        self.disk_warning_too_big = \
            DiskScreen.DISK_WARNING_TOOBIG % self.max_vtoc_disk_size
        
        self.disks = []
        self.existing_pools = []
        self.disk_win = None
        self.disk_detail = None
        self.num_targets = 0
        self.td_handle = None
        self._size_line = None
        self.selected_disk_index = 0
        self._minimum_size = None
        self._recommended_size = None

        self.engine = InstallEngine.get_instance()
        self.doc = self.engine.data_object_cache
        self.tc = target_controller
        self._target_discovery_completed = False
        self._target_discovery_status = InstallEngine.EXEC_SUCCESS
        self._image_size = None
    
    def determine_minimum(self):
        '''Returns minimum install size, fetching first if needed'''

        self.determine_size_data()
        return self._minimum_size
    
    minimum_size = property(determine_minimum)
    
    def determine_recommended(self):
        '''Returns recommended install size, fetching first if needed'''

        self.determine_size_data()
        return self._recommended_size
    
    recommended_size = property(determine_recommended)
    
    def determine_size_data(self):
        '''Retrieve the minimum and recommended sizes and generate the string
        to present that information.
        '''
        
        if self._minimum_size is None or self._recommended_size is None:
            self._recommended_size = get_recommended_size(self.tc)
            self._minimum_size = get_minimum_size(self.tc)
    
    def get_size_line(self):
        '''Returns the line of text displaying the min/recommended sizes'''

        if self._size_line is None:
            rec_size_str = locale.format("%.1f",
                self.recommended_size.get(Size.gb_units)) + LOCALIZED_GB
            min_size_str = locale.format("%.1f",
                self.minimum_size.get(Size.gb_units)) + LOCALIZED_GB
            self._size_line = DiskScreen.REC_SIZE_TEXT + rec_size_str + \
                DiskScreen.MIN_SIZE_TEXT + min_size_str

        return self._size_line
    
    size_line = property(get_size_line)
    
    def wait_for_disks(self):
        '''Block while waiting for target discovery to finish. Catch F9 and
        quit if needed
        '''
        
        self.main_win.actions.pop(curses.KEY_F2, None)
        self.main_win.actions.pop(curses.KEY_F6, None)
        self.main_win.actions.pop(curses.KEY_F3, None)
        self.main_win.show_actions()

        self.center_win.add_text(DiskScreen.DISK_SEEK_TEXT, 5, 1,
                                 self.win_size_x - 3)
        self.main_win.do_update()
        offset = textwidth(DiskScreen.DISK_SEEK_TEXT) + 2
        spin_index = 0
        self.center_win.window.timeout(250)

        while not self._target_discovery_completed:
            input_key = self.main_win.getch()
            if input_key == curses.KEY_F9:
                if self.confirm_quit():
                    raise QuitException
            self.center_win.add_text(DiskScreen.SPINNER[spin_index], 5, offset)
            self.center_win.no_ut_refresh()
            self.main_win.do_update()
            spin_index = (spin_index + 1) % len(DiskScreen.SPINNER)

        self.center_win.window.timeout(-1)
        self.center_win.clear()

        # check the result of target discovery
        if self._target_discovery_status is not InstallEngine.EXEC_SUCCESS:
            err_data = errsvc.get_errors_by_mod_id(TARGET_DISCOVERY)[0]
            LOGGER.error("Target discovery failed")
            err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
            LOGGER.error(err)
            raise TargetDiscoveryError(("Unexpected error (%s) during target "
                "discovery. See log for details.") % err)

    def _td_callback(self, status, errsvc):
        '''Callback function for Target Discovery checkpoint execution.  The
        status value is saved to be interpreted later.  This function sets the
        self._target_discovery_completed value to true so the wait_for_disks()
        function will know to stop displaying the spinner.
        '''

        self._target_discovery_status = status
        self._target_discovery_completed = True

    def _show(self):
        '''Create a list of disks to choose from and create the window
        for displaying the partition/slice information from the selected
        disk
        '''

        self.wait_for_disks()

        discovered_target = self.doc.persistent.get_first_child( \
            name=Target.DISCOVERED)

        LOGGER.debug(discovered_target)
        if discovered_target is None:
            self.center_win.add_paragraph(DiskScreen.NO_DISKS, 1, 1,
                                          max_x=(self.win_size_x - 1))
            return

        self.disks = discovered_target.get_children(class_type=Disk)
        if not self.disks:
            self.center_win.add_paragraph(DiskScreen.NO_TARGETS, 1, 1,
                                          max_x=(self.win_size_x - 1))
            return

        if self._image_size is None:
            try:
                self._image_size = Size(str(get_image_size(LOGGER)) + \
                    Size.mb_units)
                LOGGER.debug("Image_size: %s", self._image_size)
            except:
                # Unable to get the image size for some reason, allow
                # the target controller to use it's default size.
                LOGGER.debug("Unable to get image size") 
                self._image_size = FALLBACK_IMAGE_SIZE

        # initialize the target controller so the min/max size for the
        # installation can be calculated.  Explicitly do not want to select an
        # initial disk at this time in case none of the disks discovered is
        # usable.  The target controller initialization needs to be done
        # everytime we show the disk selection screen so the desired target
        # node in the DOC can be re-populated with information from target
        # discovery.
        self.tc.initialize(image_size=self._image_size, no_initial_disk=True)
         
        # Go through all the disks found and find ones that have enough space
        # for installation.  At the same time, see if any existing disk is the
        # boot disk.  If a boot disk is found, move it to the front of the list
        num_usable_disks = 0
        boot_disk = None
        for disk in self.disks:
            LOGGER.debug("size: %s, min: %s" % \
                         (disk.disk_prop.dev_size, self.minimum_size))
            if disk.disk_prop.dev_size >= self.minimum_size:
                if disk.is_boot_disk():
                    boot_disk = disk
                num_usable_disks += 1

        if boot_disk is not None:
            self.disks.remove(boot_disk)
            self.disks.insert(0, boot_disk)

        if num_usable_disks == 0:
            self.center_win.add_paragraph(DiskScreen.NO_DISKS, 1, 1,
                                          max_x=(self.win_size_x - 1))
            return

        self.main_win.reset_actions()
        self.main_win.show_actions()
        
        y_loc = 1
        self.center_win.add_text(DiskScreen.PARAGRAPH, y_loc, 1)
        
        y_loc += 1
        self.center_win.add_text(self.size_line, y_loc, 1)
        
        y_loc += 2
        self.center_win.add_text(self.disk_header_text, y_loc, 1)
        
        y_loc += 1
        self.center_win.window.hline(y_loc, self.center_win.border_size[1] + 1,
                                     curses.ACS_HLINE,
                                     textwidth(self.disk_header_text))

        y_loc += 1
        disk_win_area = WindowArea(4, textwidth(self.disk_header_text) + 2,
                                   y_loc, 0)
        disk_win_area.scrollable_lines = len(self.disks) + 1
        self.disk_win = ScrollWindow(disk_win_area, window=self.center_win)
        
        disk_item_area = WindowArea(1, disk_win_area.columns - 2, 0, 1)
        disk_index = 0
        len_type = DiskScreen.DISK_HEADERS[0][0] - 1
        len_size = DiskScreen.DISK_HEADERS[1][0] - 1
        len_boot = DiskScreen.DISK_HEADERS[2][0] - 1
        len_dev = DiskScreen.DISK_HEADERS[3][0] - 1
        len_notes = DiskScreen.DISK_HEADERS[4][0] - 1
        for disk in self.disks:
            disk_text_fields = []
            dev_type = disk.disk_prop.dev_type
            if dev_type is not None:
                type_field = dev_type[:len_type]
                type_field = ljust_columns(type_field, len_type)
            else:
                type_field = " " * len_type
            disk_text_fields.append(type_field)
            disk_size = disk.disk_prop.dev_size.get(Size.gb_units)
            size_field = locale.format("%*.1f", (len_size, disk_size))
            disk_text_fields.append(size_field)
            if disk.is_boot_disk():
                bootable_field = "+".center(len_boot)
            else:
                bootable_field = " " * (len_boot)
            disk_text_fields.append(bootable_field)

            #
            # Information will be displayed in the device column with
            # the following priority:
            #
            # First priority is to display receptacle information, 
            # if available.  If receptacle information is displayed,
            # ctd name will not be displayed.
            #
            # If receptacle information is not available, the ctd name
            # will be displayed.
            #
            # Both items above can take as much as the 44 character wide
            # column as needed.
            #
            # If the receptacle/ctd name is less than 30 characters,
            # manufacturer information will be displayed in the left
            # over space.  There won't be a column heading for the
            # manufacturer information.
            #

            device = disk.receptacle or disk.ctd
            added_device_field = False
            # is there enough room to display the manufacturer?
            if (len_dev - len(device)) >= DiskScreen.VENDOR_LEN:
                vendor = disk.disk_prop.dev_vendor
                if vendor is not None:
                    dev_display_len = len_dev - DiskScreen.VENDOR_LEN 
                    device_field = ljust_columns(device, dev_display_len)
                    disk_text_fields.append(device_field)
                    vendor_field = vendor[:DiskScreen.VENDOR_LEN - 1]
                    vendor_field = ljust_columns(vendor_field,
                                                DiskScreen.VENDOR_LEN - 1)
                    disk_text_fields.append(vendor_field)
                    added_device_field = True

            if not added_device_field:
                device_field = device[:len_dev]
                device_field = ljust_columns(device_field, len_dev)
                disk_text_fields.append(device_field)

            # display "<" or ">" if the disk is too big or too small
            selectable = True
            if disk.disk_prop.dev_size < self.minimum_size:
                selectable = False
                notes_field = DiskScreen.TOO_SMALL.center(len_notes)
                disk_text_fields.append(notes_field)
            elif disk.disk_prop.dev_size > Size(MAX_VTOC):
                notes_field = DiskScreen.TOO_BIG.center(len_notes)
                disk_text_fields.append(notes_field)

            # check the blocksize of the disk.  If it's not 512 bytes and we
            # have an EFI firmware on x86, make the disk unselectable by the
            # user.  See PSARC 2008/769
            elif platform.processor() == "i386" and \
                 disk.geometry.blocksize != 512:
                firmware = SystemFirmware.get()
                if firmware.fw_name == "uefi64":
                    selectable = False
                    notes_field = DiskScreen.INVALID_DISK.center(len_notes)
                    disk_text_fields.append(notes_field)
                    LOGGER.debug("marking disk %s unselectable as its "
                                 "blocksize is not 512 bytes on an UEFI "
                                 "firmware x86 system.", disk.ctd)

            disk_text = " ".join(disk_text_fields)

            disk_item_area.y_loc = disk_index
            disk_list_item = ListItem(disk_item_area, window=self.disk_win,
                                      text=disk_text, add_obj=selectable)
            disk_list_item.on_make_active = on_activate
            disk_list_item.on_make_active_kwargs["disk"] = disk
            disk_list_item.on_make_active_kwargs["disk_select"] = self
            disk_index += 1

        self.disk_win.no_ut_refresh()
        
        y_loc += 7
        disk_detail_area = WindowArea(6, 70, y_loc, 1)

        self.disk_detail = DiskWindow(disk_detail_area, self.disks[0],
                                      target_controller=self.tc,
                                      window=self.center_win)
        
        self.main_win.do_update()
        self.center_win.activate_object(self.disk_win)
        self.disk_win.activate_object(self.selected_disk_index)
    
    def on_change_screen(self):
        ''' Save the index of the current selected object in case the user
        returns to this screen later
        '''

        # Save the index of the selected object
        self.selected_disk_index = self.disk_win.active_object

        LOGGER.debug("disk_selection.on_change_screen, saved_index: %s",
                     self.selected_disk_index)
        LOGGER.debug(self.doc.persistent)
    
    def start_discovery(self):
        # start target discovery
        if not self._target_discovery_completed:
            errsvc.clear_error_list()
            self.engine.execute_checkpoints(pause_before=TRANSFER_PREP,
                                            callback=self._td_callback)

    def validate(self):
        '''Validate the size of the disk.'''

        warning_txt = list()

        disk = self.disk_detail.ui_obj.doc_obj
        disk_size_gb = disk.disk_prop.dev_size.get(Size.gb_units)
        max_vtoc_size_gb = Size(MAX_VTOC).get(Size.gb_units)
        # Disk size warning should only be displayed if we are restricted to
        # VTOC boot disks.
        if not can_use_gpt and disk_size_gb > max_vtoc_size_gb:
            warning_txt.append(self.disk_warning_too_big)
        warning_txt = " ".join(warning_txt)
        
        if warning_txt:
            # warn the user and give user a chance to change
            result = self.main_win.pop_up(DiskScreen.DISK_WARNING_HEADER,
                                          warning_txt,
                                          DiskScreen.CANCEL_BUTTON,
                                          DiskScreen.CONTINUE_BUTTON)
            
            if not result:
                raise UIMessage()  # let user select different disk
            # if user didn't quit it is always OK to ignore disk size,
            # that will be forced less than the maximum in partitioning.

        warning_txt = list()

        # We also need to warn the user if we need to relabel the disk from
        # GPT to SMI-VTOC
        if disk.label == "GPT" and not can_use_gpt:
            warning_txt.append(DiskScreen.DISK_WARNING_RELABEL)
        warning_txt = " ".join(warning_txt)

        if warning_txt:
            # warn the user and give user a chance to change
            result = self.main_win.pop_up(DiskScreen.DISK_WARNING_HEADER,
                                          warning_txt,
                                          DiskScreen.CANCEL_BUTTON,
                                          DiskScreen.CONTINUE_BUTTON)
            
            if not result:
                raise UIMessage()  # let user select different disk

            # if user didn't Cancel it is  OK to relabel the disk.
            # This is one of the lesser known (and potentially dangerous) 
            # features of target controller: select_disk() with
            # use_whole_disk=True can force a relabeling of the disk from GPT
            # to VTOC is necessary for booting from the disk
            disk = self.tc.select_disk(disk, use_whole_disk=True)[0]

            # The DiskWindow object needs its disk reference updated too
            self.disk_detail.set_disk_info(disk_info=disk)


def on_activate(disk, disk_select):
    '''When a disk is selected, pass its data to the disk_select_screen'''

    max_x = disk_select.win_size_x - 1

    LOGGER.debug("on activate..disk=%s", disk)

    gpt_partitions = disk.get_children(class_type=GPTPartition)
    if gpt_partitions:
        display_text = disk_select.gpt_found_text
    else:
        if platform.processor() == "i386":
            fdisk_partitions = disk.get_children(class_type=Partition)
            if fdisk_partitions:
                display_text = disk_select.found_text
            else:
                display_text = disk_select.gpt_proposed_text
        else:
            slices = disk.get_children(class_type=Slice)
            if slices:
                display_text = disk_select.found_text
            else:
                display_text = disk_select.gpt_proposed_text

    # if length of display_text is shorter than max_x, pad rest of string up to
    # max_x with white space, so, when shorter strings are displayed after
    # longer ones, the "rest" of the longer string gets erased.
    need_pad_len = max_x - len(display_text)
    if need_pad_len > 0: 
        display_text += " " * need_pad_len

    # Add the selected disk to the target controller so appropriate defaults
    # can be filled in, if necessary
    selected_disk = disk_select.tc.select_disk(disk)[0]

    # assume we don't want to use whole disk
    selected_disk.whole_disk = False

    disk_select.center_win.add_paragraph(display_text, 11, 1, max_x=max_x)
    disk_select.disk_detail.set_disk_info(disk_info=selected_disk)

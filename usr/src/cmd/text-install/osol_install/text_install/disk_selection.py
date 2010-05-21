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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Screens and functions to display a list of disks to the user.
'''

from copy import deepcopy
import curses
import logging
import platform
import threading
import traceback

from osol_install.profile.disk_info import DiskInfo, SliceInfo
from osol_install.text_install import _
from osol_install.text_install.base_screen import BaseScreen, \
                                                  QuitException, \
                                                  UIMessage
from osol_install.text_install.disk_window import DiskWindow, \
                                                  get_minimum_size, \
                                                  get_recommended_size
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea
from osol_install.text_install.ti_install_utils import get_zpool_list
import osol_install.tgt as tgt


class DiskScreen(BaseScreen):
    '''
    Allow the user to select a (valid) disk target for installation
    Display the partition/slice table for the highlighted disk
    
    '''
    
    HEADER_TEXT = _("Disks")
    PARAGRAPH = _("Where should OpenSolaris be installed?")
    SIZE_TEXT = _("Recommended size:  %(recommend).1fGB      "
                  "Minimum size: %(min).1fGB")
    DISK_SEEK_TEXT = _("Seeking disks on system")
    FOUND_x86 = _("The following partitions were found on the disk.")
    FOUND_SPARC = _("The following slices were found on the disk.")
    PROPOSED_x86 = _("A partition table was not found. The following is "
                     "proposed.")
    PROPOSED_SPARC = _("A VTOC label was not found. The following "
                       "is proposed.")
    PROPOSED_GPT = _("A GPT labeled disk was found. The following is "
                     "proposed.")
    TOO_SMALL = _("Too small")
    TOO_BIG_WARN = _("Limited to %.1f TB")
    GPT_LABELED = _("GPT labeled disk")
    NO_DISKS = _("No disks found. Additional device drivers may "
                 "be needed.")
    NO_TARGETS = _("OpenSolaris cannot be installed on any disk")
    TGT_ERROR = _("An error occurred while searching for installation"
                  " targets. Please check the install log and file a bug"
                  " at defect.opensolaris.org.")
    
    DISK_HEADERS = [(8, _("Type")),
                    (10, _("Size(GB)")),
                    (6, _("Boot")),
                    (9, _("Device")),
                    (15, _("Manufacturer")),
                    (22, _("Notes"))]
    SPINNER = ["\\", "|", "/", "-"]
    
    DISK_WARNING_HEADER = _("Warning")
    DISK_WARNING_TOOBIG = _("Only the first %.1fTB can be used.")
    DISK_WARNING_GPT = _("You have chosen a GPT labeled disk. Installing "
                         "onto a GPT labeled disk will cause the loss "
                         "of all existing data and the disk will be "
                         "relabeled as SMI.")

    CANCEL_BUTTON = _("Cancel")
    CONTINUE_BUTTON = _("Continue")
    
    def __init__(self, main_win):
        super(DiskScreen, self).__init__(main_win)
        if platform.processor() == "i386":
            self.found_text = DiskScreen.FOUND_x86
            self.proposed_text = DiskScreen.PROPOSED_x86
        else:
            self.found_text = DiskScreen.FOUND_SPARC
            self.proposed_text = DiskScreen.PROPOSED_SPARC
        
        disk_header_text = []
        for header in DiskScreen.DISK_HEADERS:
            header_str = header[1][:header[0]-1]
            header_str = header_str.ljust(header[0]-1)
            disk_header_text.append(header_str)
        self.disk_header_text = " ".join(disk_header_text)
        max_note_size = DiskScreen.DISK_HEADERS[5][0]
        self.too_small_text = DiskScreen.TOO_SMALL[:max_note_size]
        max_disk_size = SliceInfo.MAX_VTOC.size_as("tb")
        too_big_warn = DiskScreen.TOO_BIG_WARN % max_disk_size
        self.too_big_warn = too_big_warn[:max_note_size]
        self.disk_warning_too_big = \
            DiskScreen.DISK_WARNING_TOOBIG % max_disk_size
        
        self.disks = []
        self.existing_pools = []
        self.disk_win = None
        self.disk_detail = None
        self.num_targets = 0
        self.td_handle = None
        self._size_line = None
        self.selected_disk = 0
        self._minimum_size = None
        self._recommended_size = None
        self.do_copy = False # Flag indicating if install_profile.disk
                             # should be copied
    
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
            self._recommended_size = get_recommended_size().size_as("gb")
            self._minimum_size = get_minimum_size().size_as("gb")
    
    def get_size_line(self):
        '''Returns the line of text displaying the min/recommended sizes'''
        if self._size_line is None:
            size_dict = {"recommend" : self.recommended_size,
                         "min" : self.minimum_size}
            self._size_line = DiskScreen.SIZE_TEXT % size_dict
        return self._size_line
    
    size_line = property(get_size_line)
    
    def wait_for_disks(self):
        '''Block while waiting for libtd to finish. Catch F9 and quit
        if needed
        
        '''
        if self.td_handle is None:
            self.start_discovery()
        self.main_win.actions.pop(curses.KEY_F2, None)
        self.main_win.actions.pop(curses.KEY_F6, None)
        self.main_win.actions.pop(curses.KEY_F3, None)
        self.main_win.show_actions()
        if self.td_handle.is_alive():
            self.center_win.add_text(DiskScreen.DISK_SEEK_TEXT, 5, 1,
                                     self.win_size_x - 3)
            self.main_win.do_update()
            offset = len(DiskScreen.DISK_SEEK_TEXT) + 2
            spin_index = 0
            self.center_win.window.timeout(250)
            while self.td_handle.is_alive():
                input_key = self.main_win.getch()
                if input_key == curses.KEY_F9:
                    if self.confirm_quit():
                        raise QuitException
                self.center_win.add_text(DiskScreen.SPINNER[spin_index], 5,
                                         offset)
                self.center_win.no_ut_refresh()
                self.main_win.do_update()
                spin_index = (spin_index + 1) % len(DiskScreen.SPINNER)

            self.center_win.window.timeout(-1)
            self.center_win.clear()

        # Get the list of existing zpools on the
        # system and based on that come up with 
        # a unique name for the root pool 
        index = 1
        pool_name = "rpool"
        while pool_name in self.existing_pools:
            pool_name = "rpool%d" % index
            index += 1

        # Set the SliceInfo.DEFAULT_POOL to the unique
        # pool name
        SliceInfo.DEFAULT_POOL.data = pool_name

    def _show(self):
        '''Create a list of disks to choose from and create the window
        for displaying the partition/slice information from the selected
        disk
        
        '''
        self.wait_for_disks()
        self.num_targets = 0
        
        if not self.disks:
            self.center_win.add_paragraph(DiskScreen.NO_DISKS, 1, 1,
                                          max_x=(self.win_size_x - 1))
            return
        
        if isinstance(self.disks[0], BaseException):
            if len(self.disks) == 1:
                raise tgt.TgtError(("Unexpected error (%s) during target "
                                    "discovery. See log for details.") %
                                    self.disks[0])
            else:
                self.disks = self.disks[1:]
                logging.warn("Failure in target discovery, but one or more"
                             " disks found. Continuing.")
        
        boot_disk = self.disks[0]
        for disk in self.disks:
            if (disk.size.size_as("gb") > self.minimum_size):
                self.num_targets += 1
            if disk.boot:
                boot_disk = disk
        self.disks.remove(boot_disk)
        self.disks.insert(0, boot_disk)
        
        if self.num_targets == 0:
            self.center_win.add_paragraph(DiskScreen.NO_TARGETS, 1, 1,
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
                                     len(self.disk_header_text))
        
        y_loc += 1
        disk_win_area = WindowArea(4, len(self.disk_header_text) + 2, y_loc, 0)
        disk_win_area.scrollable_lines = len(self.disks) + 1
        self.disk_win = ScrollWindow(disk_win_area,
                                     window=self.center_win)
        
        disk_item_area = WindowArea(1, disk_win_area.columns - 2, 0, 1)
        disk_index = 0
        len_type = DiskScreen.DISK_HEADERS[0][0] - 1
        len_size = DiskScreen.DISK_HEADERS[1][0] - 1
        len_boot = DiskScreen.DISK_HEADERS[2][0] - 1
        len_dev = DiskScreen.DISK_HEADERS[3][0] - 1
        len_mftr = DiskScreen.DISK_HEADERS[4][0] - 1
        for disk in self.disks:
            disk_text_fields = []
            type_field = disk.type[:len_type]
            type_field = type_field.ljust(len_type)
            disk_text_fields.append(type_field)
            disk_size = disk.size.size_as("gb")
            size_field = "%*.1f" % (len_size, disk_size)
            disk_text_fields.append(size_field)
            if disk.boot:
                bootable_field = "+".center(len_boot)
            else:
                bootable_field = " " * (len_boot)
            disk_text_fields.append(bootable_field)
            device_field = disk.name[:len_dev]
            device_field = device_field.ljust(len_dev)
            disk_text_fields.append(device_field)
            if disk.vendor is not None:
                mftr_field = disk.vendor[:len_mftr]
                mftr_field = mftr_field.ljust(len_mftr)
            else:
                mftr_field = " " * len_mftr
            disk_text_fields.append(mftr_field)
            selectable = True
            if disk_size < self.minimum_size:
                note_field = self.too_small_text
                selectable = False
            elif DiskInfo.GPT in disk.label:
                note_field = DiskScreen.GPT_LABELED
            elif disk_size > SliceInfo.MAX_VTOC.size_as("gb"):
                note_field = self.too_big_warn
            else:
                note_field = ""
            disk_text_fields.append(note_field)
            disk_text = " ".join(disk_text_fields)
            disk_item_area.y_loc = disk_index
            disk_list_item = ListItem(disk_item_area, window=self.disk_win,
                                      text=disk_text, add_obj=selectable)
            disk_list_item.on_make_active = on_activate
            disk_list_item.on_make_active_kwargs["disk_info"] = disk
            disk_list_item.on_make_active_kwargs["disk_select"] = self
            disk_index += 1
        self.disk_win.no_ut_refresh()
        
        y_loc += 7
        disk_detail_area = WindowArea(6, 70, y_loc, 1)
        self.disk_detail = DiskWindow(disk_detail_area, self.disks[0],
                                      window=self.center_win)
        
        self.main_win.do_update()
        self.center_win.activate_object(self.disk_win)
        self.disk_win.activate_object(self.selected_disk)
        # Set the flag so that the disk is not copied by on_change_screen,
        # unless on_activate gets called as a result of the user changing
        # the selected disk.
        self.do_copy = False
    
    def on_change_screen(self):
        ''' Assign the selected disk to the InstallProfile, and make note of
        its index (in case the user returns to this screen later)
        
        '''
        if self.disk_detail is not None:
            if self.do_copy or self.install_profile.disk is None:
                disk = self.disk_detail.disk_info
                self.install_profile.disk = deepcopy(disk)
                self.install_profile.original_disk = disk
            self.selected_disk = self.disk_win.active_object
    
    def start_discovery(self):
        '''Spawn a thread to begin target discovery'''
        logging.debug("spawning target discovery thread")
        self.td_handle = threading.Thread(target=DiskScreen.get_disks,
                                          args=(self.disks,
                                                self.existing_pools))
        logging.debug("starting target discovery thread")
        self.td_handle.start()
    
    @staticmethod
    def get_disks(disks, pools):
        '''
        Call into target discovery and get disk data. The disks found are
        added to the list passed in by the 'disks' argument
        
        '''
        try:
            td_disks = tgt.discover_target_data()
            for disk in td_disks:
                disks.append(DiskInfo(tgt_disk=disk))
            pools.extend(get_zpool_list())
        # If an exception occurs, regardless of type, log it, add it as the
        # first item in the disk list, and consume it (an uncaught Exception
        # in this threaded code would distort the display).
        # During the call to _show, if an exception occurred, the program
        # aborts gracefully
        # pylint: disable-msg=W0703
        except BaseException, err:
            logging.exception(traceback.format_exc())
            disks.insert(0, err)


    def validate(self):
        '''Validate the size of the disk.'''
        disk = self.disk_detail.disk_info
        
        warning_txt = []
        if DiskInfo.GPT in disk.label:
            warning_txt.append(DiskScreen.DISK_WARNING_GPT)
        if disk.size > SliceInfo.MAX_VTOC:
            warning_txt.append(self.disk_warning_too_big)
        warning_txt = " ".join(warning_txt)
        
        if warning_txt:
            # warn the user and give user a chance to change
            result = self.main_win.pop_up(DiskScreen.DISK_WARNING_HEADER,
                                          warning_txt,
                                          DiskScreen.CANCEL_BUTTON,
                                          DiskScreen.CONTINUE_BUTTON)
            
            if not result:
                raise UIMessage() # let user select different disk
            
            # if user didn't quit it is always OK to ignore disk size,
            # that will be forced less than the maximum in partitioning.


def on_activate(disk_info=None, disk_select=None):
    '''When a disk is selected, pass its data to the disk_select_screen'''
    max_x = disk_select.win_size_x - 1
    
    if DiskInfo.GPT in disk_info.label:
        # default to use whole disk for GPT labeled disk
        disk_select.center_win.add_paragraph(DiskScreen.PROPOSED_GPT, 11, 1,
                                             max_x=max_x)
        disk_info.create_default_layout()
        disk_info.use_whole_segment = True
    elif disk_info.was_blank:
        disk_select.center_win.add_paragraph(disk_select.proposed_text, 11, 1,
                                             max_x=max_x)
        disk_info.create_default_layout()
        disk_info.use_whole_segment = True
    else:
        disk_select.center_win.add_paragraph(disk_select.found_text, 11, 1,
                                             max_x=max_x)
    disk_select.disk_detail.set_disk_info(disk_info)
    # User selected a different disk; set the flag so that it gets copied later
    disk_select.do_copy = True

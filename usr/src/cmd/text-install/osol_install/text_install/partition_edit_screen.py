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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
UI Components for displaying a screen allowing the user to edit
partition and slice information
'''

import curses
import logging
import platform

from osol_install.profile.disk_info import PartitionInfo, SliceInfo
from osol_install.text_install.action import Action
from osol_install.text_install.base_screen import BaseScreen, \
                                                  SkipException, \
                                                  UIMessage
from osol_install.text_install.disk_window import DiskWindow, get_minimum_size
from osol_install.text_install.window_area import WindowArea
from osol_install.text_install import _

class PartEditScreen(BaseScreen):
    '''Allows user editing of partitions on a disk, or slices on a
    disk/partition
    
    '''
    
    PARTITION_PARAGRAPH = _("OpenSolaris will be installed into the Solaris "
                            "partition. A partition's type can be changed"
                            " using the F5 key.\n\n"
                            "A partition's size can be increased "
                            "up to its Avail space. Avail space can be "
                            "increased by deleting an adjacent partition. "
                            "Delete a partition by changing it to \"Unused\""
                            " using the F5 key.\n\n"
                            "The four primary partition slots are listed on "
                            "the left. If one is an \"Extended\" partition "
                            "its logical partitions are listed on the right.")
    SLICE_PARAGRAPH = _("OpenSolaris will be installed in the \"%(pool)s\" "
                        "slice. Use the F5 key to change a slice to "
                        "\"%(pool)s.\"\n\n"
                        "A slice's size can be increased up to its Avail "
                        "size. Avail can be increased by deleting an adjacent"
                        " slice. Use the F5 key to delete a slice by changing"
                        " it to \"Unused.\"\n\n"
                        "Slices are listed in disk layout order.")
    
    HEADER_x86_PART = _("Select Partition: %(size).1fGB %(type)s "
                        "%(bootable)s")
    HEADER_x86_SLICE = _("Select Slice in Fdisk Partition")
    HEADER_SPARC_SLICE = _("Select Slice: %(size).1fGB %(type)s"
                           "%(bootable)s")
    SLICE_DESTROY_TEXT = _("indicates the slice's current content will be "
                           "destroyed")
    PART_DESTROY_TEXT = _("indicates the partition's current content will "
                          "be destroyed")
    BOOTABLE = _("Boot")
    
    def __init__(self, main_win, x86_slice_mode=False):
        super(PartEditScreen, self).__init__(main_win)
        self.x86_slice_mode = x86_slice_mode
        self.is_x86 = (platform.processor() == "i386")
        self.header_text = platform.processor()
        
        if self.x86_slice_mode: # x86, Slice within a partition
            self.instance = ".slice"
            self.header_text = PartEditScreen.HEADER_x86_SLICE
            self.paragraph_text = PartEditScreen.SLICE_PARAGRAPH
            self.destroy_text = PartEditScreen.SLICE_DESTROY_TEXT
        elif self.is_x86: # x86, Partition on disk
            self.header_text = PartEditScreen.HEADER_x86_PART
            self.paragraph_text = PartEditScreen.PARTITION_PARAGRAPH
            self.destroy_text = PartEditScreen.PART_DESTROY_TEXT
        else: # SPARC (Slice on disk)
            self.header_text = PartEditScreen.HEADER_SPARC_SLICE
            self.paragraph_text = PartEditScreen.SLICE_PARAGRAPH
            self.destroy_text = PartEditScreen.SLICE_DESTROY_TEXT
        
        self.orig_data = None
        self.disk_win = None
    
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
        part = self.install_profile.disk
        if part.use_whole_segment:
            logging.debug("disk.use_whole_segment true, skipping editing")
            raise SkipException
        if self.x86_slice_mode:
            part = part.get_solaris_data()
            if part is None:
                err_msg = "Critical error - no Solaris partition found"
                logging.error(err_msg)
                raise ValueError(err_msg)
            if part.use_whole_segment:
                logging.debug("partition.use_whole_segment True:"
                              " skipping slice editing")
                raise SkipException
            _orig_disk = self.install_profile.original_disk
            self.orig_data = _orig_disk.get_solaris_data()
            if self.orig_data is None:
                def_type = PartitionInfo.SOLARIS
                def_size = self.install_profile.disk.size
                self.orig_data = PartitionInfo(part_num=1,
                                               partition_id=def_type,
                                               size=def_size)
        else:
            self.orig_data = self.install_profile.original_disk
        
        if self.x86_slice_mode:
            header = self.header_text
        else:
            bootable = ""
            if self.is_x86 and part.boot:
                bootable = PartEditScreen.BOOTABLE
            header = self.header_text % {"size" : part.size.size_as("gb"),
                                         "type" : part.type,
                                         "bootable" : bootable}
        self.main_win.set_header_text(header)
        
        y_loc = 1
        fmt_dict = {'pool' : SliceInfo.DEFAULT_POOL}
        y_loc += self.center_win.add_paragraph(self.paragraph_text % fmt_dict,
                                               y_loc)
        
        y_loc += 1
        disk_win_area = WindowArea(6, 70, y_loc, 0)
        self.disk_win = DiskWindow(disk_win_area, part,
                                   window=self.center_win,
                                   editable=True,
                                   error_win=self.main_win.error_line,
                                   reset=self.orig_data)
        y_loc += disk_win_area.lines
        
        y_loc += 2
        self.center_win.window.addch(y_loc, self.center_win.border_size[1],
                                     DiskWindow.DESTROYED_MARK,
                                     self.center_win.color_theme.inactive)
        self.center_win.add_text(self.destroy_text, y_loc, 2)
        
        self.main_win.do_update()
        self.center_win.activate_object(self.disk_win)
    
    def on_prev(self):
        '''Clear orig_data so re-visits reset correctly'''
        self.orig_data = None
    
    def on_continue(self):
        '''Get the modified partition/slice data from the DiskWindow, and
        update install_profile.disk with it
        
        '''
        disk_info = self.disk_win.disk_info
        if self.x86_slice_mode:
            solaris_part = self.install_profile.disk.get_solaris_data()
            solaris_part.slices = disk_info.slices
        elif self.is_x86:
            self.install_profile.disk.partitions = disk_info.partitions
            solaris_part = self.install_profile.disk.get_solaris_data()
            # If the Solaris partition has changed in any way, the entire
            # partition is used as the install target.
            if solaris_part.modified():
                logging.debug("Solaris partition modified, "
                              "creating default layout")
                solaris_part.create_default_layout()
            else:
                logging.debug("Solaris partition unchanged, using original"
                              " slice data")
                solaris_part.slices = solaris_part.orig_slices
        else:
            self.install_profile.disk.slices = disk_info.slices
    
    def validate(self):
        '''Ensure the Solaris partition or ZFS Root exists and is large
        enough
        
        '''
        disk_info = self.disk_win.disk_info
        if self.is_x86 and not self.x86_slice_mode:
            min_size_text = _("The Solaris2 partition must be at least"
                              " %(size).1fGB")
            missing_part = _("There must be exactly one Solaris2 partition.")
        else:
            min_size_text = _("The size of %(pool)s must be at least"
                              " %(size).1fGB")
            missing_part = _("There must be one ZFS root pool, '%(pool)s.'")
        min_size = round(get_minimum_size().size_as("gb"), 1)
        format_dict = {'pool' : SliceInfo.DEFAULT_POOL,
                       'size': min_size}
        
        try:
            part = disk_info.get_solaris_data(check_multiples=True)
        except ValueError:
            part = None
        
        if part is None:
            raise UIMessage(missing_part % format_dict)
        
        # When comparing sizes, check only to the first decimal place,
        # as that is all the user sees. (Rounding errors that could
        # cause the partition/slice layout to be invalid get cleaned up
        # prior to target instantiation)
        part_size = round(part.size.size_as("gb"), 1)
        if part_size < min_size:
            raise UIMessage(min_size_text % format_dict)

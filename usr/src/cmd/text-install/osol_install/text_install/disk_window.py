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
UI component for displaying (and editing) partition & slice data
'''


from copy import deepcopy
import curses
import logging

from osol_install.profile.disk_space import DiskSpace, round_to_multiple
from osol_install.profile.partition_info import PartitionInfo, UI_PRECISION
from osol_install.text_install import _, LOG_LEVEL_INPUT
from osol_install.text_install.base_screen import UIMessage
from osol_install.text_install.edit_field import EditField
from osol_install.text_install.i18n import fit_text_truncate, textwidth
from osol_install.text_install.inner_window import InnerWindow, no_action
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea
from osol_install.text_install.ti_install_utils import \
    get_minimum_size as get_min_install_size
from osol_install.text_install.ti_install_utils import \
    get_recommended_size as get_rec_install_size
from osol_install.text_install.ti_install_utils import SwapDump, \
                                                       InstallationError

class DiskWindow(InnerWindow):
    '''Display and edit disk information, including partitions and slices'''
    
    STATIC_PARTITION_HEADERS = [(12, _("Primary"), _("Logical")),
                                (9, _("Size(GB)"), _("Size(GB)"))]
    
    EDIT_PARTITION_HEADERS = [(13, _("Primary"), _("Logical")),
                              (9, _("Size(GB)"), _("Size(GB)")),
                              (7, _(" Avail"), _(" Avail"))]
    
    STATIC_SLICE_HEADERS = [(13, _("Slice"), _("Slice")),
                            (2, "#", "#"),
                            (9, _("Size(GB)"), _("Size(GB)"))]
    
    EDIT_SLICE_HEADERS = [(13, _("Slice"), _("Slice")),
                          (2, "#", "#"),
                          (9, _("Size(GB)"), _("Size(GB)")),
                          (7, _(" Avail"), _(" Avail"))]
    
    ADD_KEYS = {curses.KEY_LEFT : no_action,
                curses.KEY_RIGHT : no_action}
    
    DEAD_ZONE = 3
    SCROLL_PAD = 2
    
    MIN_SIZE = None
    REC_SIZE = None
    
    SIZE_PRECISION = UI_PRECISION.size_as("gb")
    DESTROYED_MARK = EditField.ASTERISK_CHAR
    
    def __init__(self, area, disk_info, editable=False,
                 error_win=None, reset=None, **kwargs):
        '''See also InnerWindow.__init__
        
        disk_info (required) - A DiskInfo object containing the data to be
        represented. Also accepts PartitionInfo objects (for displaying slice
        data within that partition). If disk_info has partition(s), those are
        displayed. If not, but it has slices, then those are displayed. If
        neither partition data nor slice data are available, a ValueError is
        raised. This window makes a copy of the disk_info, as well as keeping
        a reference to the original for the purposes of resetting at a later
        time.
        
        headers (required) - List of tuples to populate the header of this
        window with. The first item in each tuple should be the width of the
        header, the second item should be the left side header.
        
        editable (optional) - If True, the window will be created such that
        data is editable.
        
        '''
        self.headers = None
        self.orig_ext_part_field = None
        self.orig_logicals_active = False
        self.ext_part_field = None
        self.error_win = error_win
        self.editable = editable
        self.win_width = None
        self.left_win = None
        self.right_win = None
        self.list_area = None
        self.edit_area = None
        super(DiskWindow, self).__init__(area, add_obj=editable, **kwargs)
        self.left_header_string = None
        self.right_header_string = None
        self._orig_data = None
        self._reset = reset
        self.disk_info = None
        self.has_partition_data = True
        self.key_dict[curses.KEY_LEFT] = self.on_arrow_key
        self.key_dict[curses.KEY_RIGHT] = self.on_arrow_key
        if self.editable:
            self.key_dict[curses.KEY_F5] = self.change_type
        
        if getattr(disk_info, "do_revert", False):
            self.reset()
        else:
            self.set_disk_info(disk_info)
    
    def _init_win(self, window):
        '''Require at least 70 columns and 6 lines to fit current needs for
        display of partitions and slices. Builds two inner ScrollWindows for
        displaying/editing the data.
        
        '''
        if self.area.columns < 70:
            raise ValueError, "Insufficient space - area.columns < 70"
        if self.area.lines < 6:
            raise ValueError, "Insufficient space - area.lines < 6"
        self.win_width = (self.area.columns - DiskWindow.DEAD_ZONE
                          + DiskWindow.SCROLL_PAD) / 2
        
        super(DiskWindow, self)._init_win(window)
        
        win_area = WindowArea(self.area.lines - 1, self.win_width, 2, 0)
        win_area.scrollable_lines = self.area.lines - 2
        self.left_win = ScrollWindow(win_area, window=self, add_obj=False)
        self.left_win.color = None
        self.left_win.highlight_color = None
        win_area.x_loc = self.win_width + DiskWindow.DEAD_ZONE
        win_area.scrollable_lines = 2 * PartitionInfo.MAX_LOGICAL_PARTITIONS
        self.right_win = ScrollWindow(win_area, window=self, add_obj=False)
        self.right_win.color = None
        self.right_win.highlight_color = None
    
    def set_disk_info(self, disk_info):
        '''Set up this DiskWindow to represent disk_info'''
        if getattr(disk_info, "partitions", False):
            self.has_partition_data = True
        elif disk_info.slices:
            self.has_partition_data = False
        else:
            return
        
        if self.has_partition_data:
            if self.editable:
                self.headers = DiskWindow.EDIT_PARTITION_HEADERS
                self.list_area = WindowArea(1, self.headers[0][0] + 
                                            self.headers[1][0],
                                            0, DiskWindow.SCROLL_PAD)
                self.edit_area = WindowArea(1, self.headers[1][0], 0,
                                            self.headers[0][0])
            else:
                self.headers = DiskWindow.STATIC_PARTITION_HEADERS
        else:
            if self.editable:
                self.headers = DiskWindow.EDIT_SLICE_HEADERS
                self.list_area = WindowArea(1, self.headers[0][0] +
                                            self.headers[1][0] +
                                            self.headers[2][0],
                                            0, DiskWindow.SCROLL_PAD)
                self.edit_area = WindowArea(1, self.headers[2][0], 0,
                                            self.headers[0][0] +
                                            self.headers[1][0])
            else:
                self.headers = DiskWindow.STATIC_SLICE_HEADERS
        
        self._orig_data = disk_info
        self.disk_info = deepcopy(disk_info)
        self.disk_info.add_unused_parts()
        
        self.left_win.clear()
        self.right_win.clear()
        self.window.erase()
        self.print_headers()
        
        if self.editable:
            self.active_object = None
            self.build_edit_fields()
            self.right_win.bottom = max(0, len(self.right_win.all_objects) -
                                        self.right_win.area.lines)
            if self.has_partition_data:
                self.orig_ext_part_field = None
                for obj in self.left_win.objects:
                    if (obj.data_obj.is_extended()):
                        self.orig_ext_part_field = obj
                        self.orig_logicals_active = True
                        break
        else:
            self.print_data()
    
    def print_headers(self):
        '''Print the headers for the displayed data.
        
        header[0] - The width of this column. header[1] and header[2] are
                    trimmed to this size
        header[1] - The internationalized text for the left window
        header[2] - The internationalized text for the right window
        
        '''
        self.left_header_string = []
        self.right_header_string = []
        for header in self.headers:
            left_header_str = header[1]
            right_header_str = header[2]
            # Trim the header to fit in the column width,
            # splitting columns with at least 1 space
            # Pad with extra space(s) to align the columns
            left_header_str = fit_text_truncate(left_header_str,
                                                header[0]-1, just="left")
            self.left_header_string.append(left_header_str)
            right_header_str = fit_text_truncate(right_header_str,
                                                header[0]-1, just="left")
            self.right_header_string.append(right_header_str)
        self.left_header_string = " ".join(self.left_header_string)
        self.right_header_string = " ".join(self.right_header_string)
        logging.debug(self.left_header_string)
        self.add_text(self.left_header_string, 0, DiskWindow.SCROLL_PAD)
        right_win_offset = (self.win_width + DiskWindow.DEAD_ZONE +
                            DiskWindow.SCROLL_PAD)
        self.add_text(self.right_header_string, 0, right_win_offset)
        self.window.hline(1, DiskWindow.SCROLL_PAD, curses.ACS_HLINE,
                          textwidth(self.left_header_string))
        self.window.hline(1, right_win_offset, curses.ACS_HLINE,
                          textwidth(self.right_header_string))
        self.no_ut_refresh()
    
    def print_data(self):
        '''Print static (non-editable) data.
        
        Slices - fill the left side, then remaining slices on the right side.
        If for some reason not all slices fit, indicate how many more slices
        there area
        
        Partitions - Put standard partitions on the left, logical partitions
        on the right
        
        '''
        part_index = 0
        if self.has_partition_data:
            max_parts = PartitionInfo.MAX_STANDARD_PARTITIONS
        else:
            max_parts = min(len(self.disk_info.slices),
                                self.left_win.area.lines)
        win = self.left_win
        y_loc = 0
        for next_part in self.disk_info.get_parts():
            if y_loc >= max_parts:
                if win is self.left_win:
                    win = self.right_win
                    y_loc = 0
                    max_parts = win.area.lines
                else:
                    if self.has_partition_data:
                        num_extra = len(self.disk_info.partitions) - part_index
                        more_parts_txt = _("%d more partitions") % num_extra
                    else:
                        num_extra = len(self.disk_info.slices) - part_index
                        more_parts_txt = _("%d more slices") % num_extra
                    win.add_text(more_parts_txt, win.area.lines, 3)
                    break
            x_loc = DiskWindow.SCROLL_PAD
            field = 0
            win.add_text(next_part.get_description(), y_loc, x_loc,
                         self.headers[field][0] - 1)
            x_loc += self.headers[field][0]
            field += 1
            if not self.has_partition_data:
                win.add_text(str(next_part.number), y_loc, x_loc,
                             self.headers[field][0] - 1)
                x_loc += self.headers[field][0]
                field += 1
            win.add_text("%*.1f" % (self.headers[field][0]-1,
                                    next_part.size.size_as("gb")),
                                    y_loc, x_loc,
                                    self.headers[field][0]-1)
            x_loc += self.headers[field][0]
            y_loc += 1
            field += 1
            part_index += 1
        self.right_win.use_vert_scroll_bar = False
        self.no_ut_refresh()
    
    def build_edit_fields(self):
        '''Build subwindows for editing partition sizes
        
        For slices, fill the left side, then the right (right side scrolling as
        needed, though this shouldn't happen unless the number of slices on
        disk exceeds 8 for some reason)
        
        For partitions, fill the left side up to MAX_STANDARD_PARTITIONS,
        and place all logical partitions on the right.
        
        '''
        if self.has_partition_data:
            max_left_parts = PartitionInfo.MAX_STANDARD_PARTITIONS
        else:
            max_left_parts = min(len(self.disk_info.slices),
                                 self.left_win.area.lines)
        part_iter = iter(self.disk_info.get_parts())
        try:
            next_part = part_iter.next()
            self.objects.append(self.left_win)
            for y_loc in range(max_left_parts):
                self.list_area.y_loc = y_loc
                self.create_list_item(next_part, self.left_win, self.list_area)
                next_part.orig_type = next_part.type
                next_part = part_iter.next()
            self.objects.append(self.right_win)
            for y_loc in range(self.right_win.area.scrollable_lines):
                self.list_area.y_loc = y_loc
                self.create_list_item(next_part, self.right_win,
                                      self.list_area)
                next_part.orig_offset = next_part.offset.size_as("gb")
                next_part.orig_size = next_part.size.size_as("gb")
                next_part = part_iter.next()
        except StopIteration:
            if len(self.right_win.all_objects) <= self.right_win.area.lines:
                self.right_win.use_vert_scroll_bar = False
            self.right_win.no_ut_refresh()
        else:
            raise ValueError("Could not fit all partitions in DiskWindow")
        self.no_ut_refresh()
    
    def create_list_item(self, next_part, win, list_area):
        '''Add an entry for next_part (a PartitionInfo or SliceInfo) to
        the DiskWindow
        
        '''
        next_part.is_dirty = False
        next_part.restorable = True
        next_part.orig_offset = next_part.offset.size_as("gb")
        next_part.orig_size = next_part.size.size_as("gb")
        next_part.orig_type = next_part.type
        list_item = ListItem(list_area, window=win, data_obj=next_part)
        list_item.key_dict.update(DiskWindow.ADD_KEYS)
        list_item.on_make_inactive = on_leave_part_field
        list_item.on_make_inactive_kwargs = {"field" : list_item}
        edit_field = EditField(self.edit_area, window=list_item,
                               numeric_pad=" ",
                               validate=decimal_valid,
                               on_exit=on_exit_edit,
                               error_win=self.error_win,
                               add_obj=False,
                               data_obj=next_part)
        edit_field.right_justify = True
        edit_field.validate_kwargs["disk_win"] = self
        edit_field.key_dict.update(DiskWindow.ADD_KEYS)
        self.update_part(part_field=list_item)
        return list_item
    
    def update_part(self, part_info=None, part_field=None):
        '''Sync changed partition data to the screen.'''
        if part_field is None:
            if part_info is None:
                raise ValueError("Must supply either part_info or part_field")
            part_field = self.find_part_field(part_info)[1]
        elif part_info is None:
            part_info = part_field.data_obj
        elif part_field.data_obj is not part_info:
            raise ValueError("part_field must be a ListItem associated with "
                             "part_info")
        if not isinstance(part_field, ListItem):
            raise TypeError("part_field must be a ListItem associated with "
                            "part_info")
        if self.has_partition_data:
            desc_text = part_info.get_description()
        else:
            desc_length = self.headers[0][0] - 1
            desc_text = "%-*.*s %i" % (desc_length, desc_length,
                                       part_info.get_description(),
                                       part_info.number)
        part_field.set_text(desc_text)
        edit_field = part_field.all_objects[0]
        edit_field.set_text("%.1f" % part_info.size.size_as("gb"))
        self.mark_if_destroyed(part_field)
        self._update_edit_field(part_info, part_field, edit_field)

        self.update_avail_space(part_info=part_info)
        if self.has_partition_data:
            if part_info.is_extended():
                self.ext_part_field = part_field
    
    def _update_edit_field(self, part_info, part_field, edit_field):
        '''If the partition/slice is editable, add it to the .objects list.
        If it's also the part_field that's currently selected, then activate
        the edit field.
        
        '''
        if part_info.editable(self.disk_info):
            part_field.objects = [edit_field]
            active_win = self.get_active_object()
            if active_win is not None:
                if active_win.get_active_object() is part_field:
                    part_field.activate_object(edit_field)
        else:
            edit_field.make_inactive()
            part_field.objects = []
            part_field.active_object = None

    def mark_if_destroyed(self, part_field):
        '''Determine if the partition/slice represented by part_field has
        changed such that its contents will be destroyed.
        
        '''
        part_info = part_field.data_obj
        destroyed = part_info.destroyed()
        self.mark_destroyed(part_field, destroyed)
    
    def mark_destroyed(self, part_field, destroyed):
        '''If destroyed is True, add an asterisk indicating that the
        partition or slice's content will be destroyed during installation.
        Otherwise, clear the asterisk
        
        '''
        y_loc = part_field.area.y_loc
        x_loc = part_field.area.x_loc - 1
        if part_field in self.right_win.objects:
            win = self.right_win
        else:
            win = self.left_win
        if destroyed:
            win.window.addch(y_loc, x_loc, DiskWindow.DESTROYED_MARK,
                             win.color_theme.inactive)
        else:
            win.window.addch(y_loc, x_loc, InnerWindow.BKGD_CHAR)
    
    def update_avail_space(self, part_number=None, part_info=None):
        '''Update the 'Avail' column for the specified slice or partition.
        If no number is given, all avail columns are updated
        
        '''
        if part_number is None and part_info is None:
            self._update_all_avail_space()
        else:
            self._update_avail_space(part_number, part_info)

    def _update_all_avail_space(self):
        '''Update the 'Avail' column for all slices or partitions.'''
        idx = 0
        for item in self.left_win.objects:
            self.update_avail_space(idx)
            idx += 1
        for item in self.right_win.objects:
            self.update_avail_space(idx)
            idx += 1
        y_loc = idx - len(self.left_win.objects)
        if self.has_partition_data:
            x_loc = self.headers[0][0] + self.headers[1][0] + 1
            field = 2
        else:
            x_loc = (self.headers[0][0] + self.headers[1][0] +
                     self.headers[2][0] + 1)
            field = 3
        if y_loc > 0:
            self.right_win.add_text(" " * self.headers[field][0],
                                    y_loc, x_loc)
        elif y_loc == 0 and self.has_partition_data:
            # Blank out the size fields of removed (non-original)
            # logical partitions
            orig_logicals = len(self._orig_data.get_logicals())
            for right_y_loc in range(orig_logicals,
                                self.right_win.area.scrollable_lines):
                self.right_win.add_text(" " * self.headers[field][0],
                                        right_y_loc, x_loc)

    def _update_avail_space(self, part_number=None, part_info=None):
        '''Update the 'Avail' column for the specified slice or partition.'''
        if part_number is None:
            win, item = self.find_part_field(part_info)
        elif part_number < len(self.left_win.objects):
            win = self.left_win
            item = win.objects[part_number]
        else:
            win = self.right_win
            item = win.objects[part_number - len(self.left_win.objects)]
        if self.has_partition_data:
            x_loc = self.headers[0][0] + self.headers[1][0] + 1
            field = 2
        else:
            x_loc = (self.headers[0][0] + self.headers[1][0] +
                     self.headers[2][0] + 1)
            field = 3
        y_loc = item.area.y_loc
        part = item.data_obj
        max_space = part.get_max_size(self.disk_info)
        max_space = "%*.1f" % (self.headers[field][0], max_space)
        win.add_text(max_space, y_loc, x_loc)
    
    def find_part_field(self, part_info):
        '''Given a PartitionInfo or SliceInfo object, find the associated
        ListItem. This search compares by reference, and will only succeed
        if you have a handle to the exact object referenced by the ListItem
        
        '''
        for win in [self.left_win, self.right_win]:
            for item in win.objects:
                if item.data_obj is part_info:
                    return win, item
        raise ValueError("Part field not found")
    
    def reset(self, dummy=None):
        '''Reset disk_info to _orig_data.
        Meaningful only for editable DiskWindows
        
        '''
        if self.editable:
            if self._reset is not None:
                self.set_disk_info(self._reset)
            else:
                self.set_disk_info(self._orig_data)
            self.activate_solaris_data()
    
    def activate_solaris_data(self):
        '''Find the Solaris Partition / ZFS Root Pool Slice and activate it.
        See also DiskInfo.get_solaris_data()
        
        '''
        if self.editable:
            solaris_part = self.disk_info.get_solaris_data()
            if solaris_part is None:
                logging.debug("No Solaris data, activating default")
                self.activate_object()
                self.right_win.scroll(scroll_to_line=0)
                return
            disk_order = self.disk_info.get_parts().index(solaris_part)
            logging.debug("solaris disk at disk_order = %s", disk_order)
            if disk_order < len(self.left_win.objects):
                logging.debug("activating in left_win")
                self.left_win.activate_object(disk_order)
                self.activate_object(self.left_win)
                self.right_win.scroll(scroll_to_line=0)
            else:
                activate = disk_order - len(self.left_win.objects)
                logging.debug('activating in right win')
                self.right_win.activate_object_force(activate,
                                                     force_to_top=True)
                self.activate_object(self.right_win)
                left_active = self.left_win.get_active_object()
                if left_active is not None:
                    left_active.make_inactive()
    
    def make_active(self):
        '''On activate, select the solaris partition or ZFS root pool,
        instead of defaulting to 0
        
        '''
        self.set_color(self.highlight_color)
        self.activate_solaris_data()
    
    def on_arrow_key(self, input_key):
        '''
        On curses.KEY_LEFT: Move from the right win to the left win
        On curses.KEY_RIGHT: Move from the left to the right
        
        '''
        if (input_key == curses.KEY_LEFT and
            self.get_active_object() is self.right_win and
            len(self.left_win.objects) > 0):
            
            active_object = self.right_win.get_active_object().area.y_loc
            if (active_object >= len(self.left_win.objects)):
                active_object = len(self.left_win.objects) - 1
            self.activate_object(self.left_win)
            self.left_win.activate_object(active_object)
            return None
        elif (input_key == curses.KEY_RIGHT and
              self.get_active_object() is self.left_win and
              len(self.right_win.objects) > 0):
            active_line = (self.left_win.active_object + 
                             self.right_win.current_line[0])
            active_object = None
            force_to_top = False
            for obj in self.right_win.objects:
                if obj.area.y_loc >= active_line:
                    active_object = obj
                    off_screen = (self.right_win.current_line[0] +
                                  self.right_win.area.lines)
                    if active_object.area.y_loc > off_screen:
                        force_to_top = True
                    break
            if active_object is None:
                active_object = 0
            self.left_win.activate_object(-1, loop=True)
            self.activate_object(self.right_win)
            self.right_win.activate_object_force(active_object,
                                                 force_to_top=force_to_top)
            return None
        return input_key
    
    def no_ut_refresh(self, abs_y=None, abs_x=None):
        '''Refresh self, left win and right win explicitly'''
        super(DiskWindow, self).no_ut_refresh()
        self.left_win.no_ut_refresh(abs_y, abs_x)
        self.right_win.no_ut_refresh(abs_y, abs_x)
    
    def change_type(self, dummy):
        '''Cycle the type for the currently active object, and
        update its field
        
        '''
        logging.debug("changing type")
        part_field = self.get_active_object().get_active_object()
        part_info = part_field.data_obj
        old_type = part_info.type
        if part_info.restorable:
            part_info.cycle_type(self.disk_info, [part_info.orig_type])
        else:
            part_info.cycle_type(self.disk_info)
        new_type = part_info.type
        if old_type != new_type:
            max_size = part_info.get_max_size(self.disk_info)
            if part_info.restorable:
                part_info.is_dirty = (new_type != part_info.orig_type)
            if old_type == part_info.UNUSED:
                if part_info.orig_type == part_info.UNUSED:
                    part_info.size = "%.1fgb" % max_size
                    part_info.adjust_offset(self.disk_info)
                else:
                    part_info.size = part_info.previous_size
            if part_info.is_dirty and part_info.size.size_as("gb") > max_size:
                part_info.size = "%.1fgb" % max_size
                part_info.adjust_offset(self.disk_info)
            if self.has_partition_data:
                if old_type in PartitionInfo.EXTENDED:
                    self.deactivate_logicals()
                elif part_info.is_extended():
                    self.create_extended(part_field)
                elif part_info.is_logical():
                    last_logical = self.right_win.objects[-1].data_obj

                    if (old_type == PartitionInfo.UNUSED and
                        self.right_win.objects[-1] is part_field):
                        logging.debug("part is logical, old type unused, "
                                      "last field")
                        self.append_unused_logical()
                    elif (len(self.right_win.objects) > 1 and
                          new_type == PartitionInfo.UNUSED and
                          self.right_win.objects[-2] is part_field and
                          last_logical.type == PartitionInfo.UNUSED):
                        # If we cycle the second to last partition to Unused,
                        # combine it with the last unused partition
                        remove = self.right_win.objects[-1]
                        self.right_win.remove_object(remove)
                    self.update_part(part_field=self.ext_part_field)
            self.update_part(part_field=part_field)
        logging.log(LOG_LEVEL_INPUT, "part updated to:\n%s", part_info)
        self.update_avail_space()
        part_field.no_ut_refresh()
        return None
    
    def deactivate_logicals(self):
        '''Marks as destroyed all logicals in the original extended partition,
        and sets them as unselectable. Additionally, completely removes
        any logical partitions added by the user.
        
        '''
        if self.orig_logicals_active:
            original_logicals = len(self._orig_data.get_logicals())
            self.orig_logicals_active = False
        else:
            original_logicals = 0
        logging.log(LOG_LEVEL_INPUT, "orig logicals = %s", original_logicals)
        self.disk_info.remove_logicals()
        for obj in self.right_win.objects[:original_logicals]:
            self.mark_destroyed(obj, True)
        for obj in self.right_win.objects[original_logicals:]:
            obj.clear()
            self.right_win.remove_object(obj)

        if self.right_win in self.objects:
            self.objects.remove(self.right_win)
        self.right_win.objects = []
        self.right_win.active_object = None
        scroll = len(self.right_win.all_objects) > self.right_win.area.lines
        self.right_win.use_vert_scroll_bar = scroll
        self.right_win.no_ut_refresh()
    
    def create_extended(self, ext_part_field):
        '''If this is the original extended partition, restore the original
        logical partitions. Otherwise, create a single unused logical
        partition.
        
        '''
        if not ext_part_field.data_obj.modified():
            self.right_win.clear()
            self.orig_logicals_active = True
            logicals = deepcopy(self._orig_data.get_logicals())
            self.disk_info.partitions.extend(logicals)
            for idx, logical in enumerate(logicals):
                self.list_area.y_loc = idx
                self.create_list_item(logical, self.right_win, self.list_area)
            if self.right_win not in self.objects:
                self.objects.append(self.right_win)
            self.right_win.activate_object_force(0, force_to_top=True)
            self.right_win.make_inactive()
            self.right_win.no_ut_refresh()
        else:
            # Leave old data be, create new Unused logical partition
            if self.right_win not in self.objects:
                self.objects.append(self.right_win)
            self.append_unused_logical()
    
    def append_unused_logical(self):
        '''Adds a single Unused logical partition to the right window'''
        new_part = self.disk_info.append_unused_logical()
        self.list_area.y_loc = len(self.right_win.all_objects)
        bottom = self.list_area.y_loc - self.right_win.area.lines + 1
        self.right_win.bottom = max(0, bottom)
        self.create_list_item(new_part, self.right_win, self.list_area)
        scroll = len(self.right_win.all_objects) > self.right_win.area.lines
        self.right_win.use_vert_scroll_bar = scroll
        self.right_win.no_ut_refresh()


def on_leave_part_field(field=None):
    '''When leaving a field, if the field has been modified, mark it as
    non-restorable, meaning the original partition data has been
    modified to the extent that we can no longer safely ensure the preservation
    of any data on it. (DiskWindow.reset will still function)
    
    '''
    part_info = field.data_obj
    if part_info.is_dirty:
        part_info.restorable = False


def decimal_valid(edit_field, disk_win=None):
    '''Check text to see if it is a decimal number of precision no
    greater than the tenths place.
    
    '''
    text = edit_field.get_text().lstrip()
    if text.endswith(" "):
        raise UIMessage(_('Only the digits 0-9 and "." are valid.'))
    vals = text.split(".")
    if len(vals) > 2:
        raise UIMessage(_('A number can only have one "."'))
    try:
        if len(vals[0]) > 0:
            int(vals[0])
        if len(vals) > 1 and len(vals[1]) > 0:
            int(vals[1])
    except ValueError:
        raise UIMessage(_('Only the digits 0-9 and "." are valid.'))
    if len(vals) > 1 and len(vals[1]) > 1:
        raise UIMessage(_("Size can be specified to only one decimal place."))
    if disk_win is not None:
        text = text.rstrip(".")
        if not text:
            text = "0"
        new_size = DiskSpace(text + "gb")
        max_size = edit_field.data_obj.get_max_size(disk_win.disk_info)
        
        # When comparing sizes, check only to the first decimal place,
        # as that is all the user sees. (Rounding errors that could
        # cause the partition/slice layout to be invalid get cleaned up
        # prior to target instantiation)
        new_size_rounded = round(new_size.size_as("gb"), 1)
        max_size_rounded = round(max_size, 1)
        if new_size_rounded > max_size_rounded:
            raise UIMessage(_("The new size (%(size).1f) is greater than "
                              "the available space (%(avail).1f)") %
                              {"size" : new_size_rounded,
                               "avail" : max_size_rounded})
        size_diff = abs(new_size.size_as("gb") - edit_field.data_obj.orig_size)
        if size_diff > DiskWindow.SIZE_PRECISION:
            edit_field.data_obj.size = new_size
            edit_field.data_obj.adjust_offset(disk_win.disk_info)
        else:
            edit_field.data_obj.size = "%fgb" % edit_field.data_obj.orig_size
        disk_win.update_avail_space()
        disk_win.no_ut_refresh()
        part_field = disk_win.find_part_field(edit_field.data_obj)[1]
        disk_win.mark_if_destroyed(part_field)
    return True


def on_exit_edit(edit_field):
    '''On exit, if the user has left the field blank, set the size to 0'''
    text = edit_field.get_text()
    if not text.strip():
        text = "0"
    edit_field.set_text("%.1f" % float(text))


def get_recommended_size():
    '''Returns the recommended size for the installation, in GB'''
    if DiskWindow.REC_SIZE is None:
        try:
            swap_dump = SwapDump()
            rec_size = str(get_rec_install_size(swap_dump)) + "mb"
            DiskWindow.REC_SIZE = DiskSpace(rec_size)
            rec_size = DiskWindow.REC_SIZE.size_as("gb")
            rec_size = round_to_multiple(rec_size, 0.1)
            DiskWindow.REC_SIZE.size = "%sgb" % rec_size
        except (InstallationError):
            logging.warn("Unable to determine recommended install size")
            DiskWindow.REC_SIZE = DiskSpace("10gb")
    return DiskWindow.REC_SIZE


def get_minimum_size():
    '''Returns the minimum disk space needed for installation, in GB. The
    value returned from get_min_install_size is rounded up to the nearest
    tenth of a gigabyte, so that the UI ensures enough space is allocated,
    given that the UI only allows for precision to tenths of a gigabyte.
    
    '''
    if DiskWindow.MIN_SIZE is None:
        try:
            swap_dump = SwapDump()
            min_size = str(get_min_install_size(swap_dump)) + "mb"
            DiskWindow.MIN_SIZE = DiskSpace(min_size)
            min_size = DiskWindow.MIN_SIZE.size_as("gb")
            min_size = round_to_multiple(min_size, 0.1)
            DiskWindow.MIN_SIZE.size = "%sgb" % min_size
        except (InstallationError):
            logging.warn("Unable to determine minimum install size")
            DiskWindow.MIN_SIZE = DiskSpace("6gb")
    return DiskWindow.MIN_SIZE

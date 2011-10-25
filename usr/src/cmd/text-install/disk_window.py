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
UI component for displaying (and editing) partition & slice data
'''


import curses
import locale
import logging
import platform

from copy import deepcopy

from solaris_install.engine import InstallEngine
from solaris_install.text_install import _
from solaris_install.text_install.ti_target_utils import UIDisk, UIPartition, \
    dump_doc, get_desired_target_disk, get_solaris_partition, ROOT_POOL, \
    UI_PRECISION
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.libadm.const import FD_NUMPART as MAX_PRIMARY_PARTS
from solaris_install.target.libadm.const import MAX_EXT_PARTS
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size
from solaris_install.target.libadm.const import V_ROOT

from terminalui.base_screen import UIMessage
from terminalui.edit_field import EditField
from terminalui.i18n import fit_text_truncate, get_encoding, textwidth
from terminalui.inner_window import InnerWindow, no_action
from terminalui.list_item import ListItem
from terminalui.scroll_window import ScrollWindow
from terminalui.window_area import WindowArea

LOGGER = None


class DiskWindow(InnerWindow):
    '''Display and edit disk information, including partitions and slices'''

    STATIC_PARTITION_HEADERS = [(12, _("Primary"), _("Logical")),
                                (10, _(" Size(GB)"), _(" Size(GB)"))]

    EDIT_PARTITION_HEADERS = [(13, _("Primary"), _("Logical")),
                              (10, _(" Size(GB)"), _(" Size(GB)")),
                              (7, _(" Avail"), _(" Avail"))]

    STATIC_SLICE_HEADERS = [(13, _("Slice"), _("Slice")),
                            (2, "#", "#"),
                            (10, _(" Size(GB)"), _(" Size(GB)"))]

    EDIT_SLICE_HEADERS = [(13, _("Slice"), _("Slice")),
                          (2, "#", "#"),
                          (10, _(" Size(GB)"), _(" Size(GB)")),
                          (7, _(" Avail"), _(" Avail"))]

    ADD_KEYS = {curses.KEY_LEFT: no_action,
                curses.KEY_RIGHT: no_action}

    DEAD_ZONE = 3
    SCROLL_PAD = 2

    MIN_SIZE = None
    REC_SIZE = None

    SIZE_PRECISION = Size(UI_PRECISION).get(Size.gb_units)

    DESTROYED_MARK = EditField.ASTERISK_CHAR

    def __init__(self, area, disk_info, editable=False,
                 error_win=None, target_controller=None, **kwargs):
        '''See also InnerWindow.__init__

        disk_info (required) - Either a Disk or Partition object
        containing the data to be represented. If a Partition objects is
        provided, it will be used for displaying slice
        data within that partition. If Disk has partition(s), those are
        displayed. If not, but it has slices, then those are displayed. If
        neither partition data nor slice data are available, a ValueError is
        raised.

        headers (required) - List of tuples to populate the header of this
        window with. The first item in each tuple should be the width of the
        header, the second item should be the left side header.

        editable (optional) - If True, the window will be created such that
        data is editable.

        target_controller(optional) - Target controller

        '''

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

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
        self.disk_info = None
        self.has_partition_data = False
        self.key_dict[curses.KEY_LEFT] = self.on_arrow_key
        self.key_dict[curses.KEY_RIGHT] = self.on_arrow_key
        if self.editable:
            self.key_dict[curses.KEY_F5] = self.change_type

        self.tc = target_controller
        self._ui_obj = None
        self.ui_obj = disk_info

        self.set_disk_info(ui_obj=self.ui_obj)

        LOGGER.debug(self.ui_obj)

        if platform.processor() == "sparc":
            self.is_x86 = False
        else:
            self.is_x86 = True

    @property
    def ui_obj(self):
        return self._ui_obj

    @ui_obj.setter
    def ui_obj(self, part):
        ''' create and set the value for ui_obj depending on type '''
        if isinstance(part, Disk):
            self._ui_obj = UIDisk(self.tc, parent=None, doc_obj=part)
        elif isinstance(part, Partition):
            self._ui_obj = UIPartition(self.tc, parent=None, doc_obj=part)
        else:
            # Must be a either a Disk or Partition.  It's an error to be here
            raise RuntimeError("disk_info object is invalid")

    def _init_win(self, window):
        '''Require at least 70 columns and 6 lines to fit current needs for
        display of partitions and slices. Builds two inner ScrollWindows for
        displaying/editing the data.

        '''
        if self.area.columns < 70:
            raise ValueError("Insufficient space - area.columns < 70")
        if self.area.lines < 6:
            raise ValueError("Insufficient space - area.lines < 6")
        self.win_width = (self.area.columns - DiskWindow.DEAD_ZONE
                          + DiskWindow.SCROLL_PAD) / 2

        super(DiskWindow, self)._init_win(window)

        win_area = WindowArea(self.area.lines - 1, self.win_width, 2, 0)
        win_area.scrollable_lines = self.area.lines - 2
        self.left_win = ScrollWindow(win_area, window=self, add_obj=False)
        self.left_win.color = None
        self.left_win.highlight_color = None
        win_area.x_loc = self.win_width + DiskWindow.DEAD_ZONE
        win_area.scrollable_lines = 2 * MAX_EXT_PARTS
        self.right_win = ScrollWindow(win_area, window=self, add_obj=False)
        self.right_win.color = None
        self.right_win.highlight_color = None

    def set_disk_info(self, ui_obj=None, disk_info=None, no_part_ok=False):
        '''Set up this DiskWindow to represent disk_info'''

        if ui_obj is not None:
            disk_info = ui_obj.doc_obj
        elif disk_info is not None:
            self.ui_obj = disk_info
        else:
            # Should never be this case
            raise RuntimeError("Unable to find ui_obj or disk_info")

        part_list = disk_info.get_children(class_type=Partition)
        if part_list:
            self.has_partition_data = True
        else:
            slice_list = disk_info.get_children(class_type=Slice)
            if slice_list:
                self.has_partition_data = False
            else:
                # No partitions and no slices
                if no_part_ok:
                    if self.is_x86:
                        self.has_partition_data = True
                    else:
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

        LOGGER.debug("have_partition: %s", self.has_partition_data)
        LOGGER.debug(self.ui_obj)

        self.ui_obj.add_unused_parts(no_part_ok=no_part_ok)

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
                                                header[0] - 1, just="left")
            self.left_header_string.append(left_header_str)
            right_header_str = fit_text_truncate(right_header_str,
                                                header[0] - 1, just="left")
            self.right_header_string.append(right_header_str)
        self.left_header_string = " ".join(self.left_header_string)
        self.right_header_string = " ".join(self.right_header_string)
        LOGGER.debug(self.left_header_string)
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
        data = self.ui_obj.get_parts_in_use()

        if len(data) == 0:
            return   # should never be this case

        if self.has_partition_data:
            max_parts = MAX_PRIMARY_PARTS
        else:
            max_parts = min(len(data), self.left_win.area.lines)

        win = self.left_win
        y_loc = 0
        for next_data in data:
            LOGGER.debug("next_data: %s", next_data)
            if y_loc >= max_parts:
                if win is self.left_win:
                    win = self.right_win
                    y_loc = 0
                    max_parts = win.area.lines
                else:
                    num_extra = len(data) - part_index
                    if self.has_partition_data:
                        more_parts_txt = _("%d more partitions") % num_extra
                    else:
                        more_parts_txt = _("%d more slices") % num_extra
                    win.add_text(more_parts_txt, win.area.lines, 3)
                    break
            x_loc = DiskWindow.SCROLL_PAD
            field = 0
            win.add_text(next_data.get_description(), y_loc, x_loc,
                         self.headers[field][0] - 1)
            x_loc += self.headers[field][0]
            field += 1
            if not self.has_partition_data:
                win.add_text(str(next_data.name), y_loc, x_loc,
                             self.headers[field][0] - 1)
                x_loc += self.headers[field][0]
                field += 1
            win.add_text(locale.format("%*.1f", (self.headers[field][0] - 1,
                next_data.size.get(Size.gb_units))), y_loc, x_loc,
                self.headers[field][0] - 1)
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

        For partitions, fill the left side up to MAX_PRIMARY_PARTS,
        and place all logical partitions on the right.

        '''

        data = self.ui_obj.get_parts_in_use()

        if self.has_partition_data:
            max_left_parts = MAX_PRIMARY_PARTS
        else:
            if len(data) == 0:
                return   # should never be this case
            max_left_parts = min(len(data), self.left_win.area.lines)

        part_iter = iter(data)
        try:
            next_part = part_iter.next()
            self.objects.append(self.left_win)
            for y_loc in range(max_left_parts):
                self.list_area.y_loc = y_loc
                self.create_list_item(next_part, self.left_win, self.list_area)
                next_part = part_iter.next()
            self.objects.append(self.right_win)
            for y_loc in range(self.right_win.area.scrollable_lines):
                self.list_area.y_loc = y_loc
                self.create_list_item(next_part, self.right_win,
                                      self.list_area)
                next_part = part_iter.next()
            if len(data) > max_left_parts:
                self.right_win.use_vert_scroll_bar = True
        except StopIteration:
            if len(self.right_win.all_objects) <= self.right_win.area.lines:
                self.right_win.use_vert_scroll_bar = False
            self.right_win.no_ut_refresh()
        else:
            raise ValueError("Could not fit all partitions in DiskWindow")
        self.no_ut_refresh()

    def create_list_item(self, next_part, win, list_area):
        '''Add an entry for next_part (a Partition or Slice) to
        the DiskWindow

        '''
        list_item = ListItem(list_area, window=win, data_obj=next_part)
        list_item.key_dict.update(DiskWindow.ADD_KEYS)
        edit_field = EditField(self.edit_area, window=list_item,
                               numeric_pad=" ",
                               validate=decimal_valid,
                               on_exit=on_exit_edit,
                               error_win=self.error_win,
                               add_obj=False,
                               data_obj=next_part)
        edit_field.right_justify = True
        edit_field.validate_kwargs["disk_win"] = self
        edit_field.on_exit_kwargs["disk_win"] = self
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
            desc_text = "%-*.*s %s" % (desc_length, desc_length,
                                       part_info.get_description(),
                                       part_info.name)
        part_field.set_text(desc_text)
        edit_field = part_field.all_objects[0]
        edit_field.set_text(locale.format("%.1f",
                                          part_info.size.get(Size.gb_units)))
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
        if part_info.editable():
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
        destroyed = part_info.modified()
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
        max_space = part.get_max_size()
        max_space = locale.format("%*.1f", (self.headers[field][0],
                                             max_space.get(Size.gb_units)))
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
        '''Reset ui_obj to value found from Target Discovery.
        Meaningful only for editable DiskWindows

        '''
        if not self.editable:
            return
        doc = InstallEngine.get_instance().doc

        # "reset" the desired target
        reset_obj = None
        if isinstance(self.ui_obj, UIDisk):
            reset_obj = (self.tc.reset_layout(disk=self.ui_obj.doc_obj))[0]
        else:
            # reset the partition by removing the modified Partition, and
            # resetting it with the partition found during target discovery.

            discovered_obj = self.ui_obj.discovered_doc_obj

            desired_disk = get_desired_target_disk(doc)
            desired_part = get_solaris_partition(doc)

            desired_disk.delete_partition(desired_part)
            part_copy = deepcopy(discovered_obj)
            desired_disk.insert_children(part_copy)

            # get the updated reference
            reset_obj = get_solaris_partition(doc)

        dump_doc("After doing reset")

        self.set_disk_info(disk_info=reset_obj)
        self.activate_solaris_data()

    def activate_solaris_data(self):
        '''Find the Solaris Partition / ZFS Root Pool Slice and activate it.

        '''

        if self.editable:
            solaris_part = self.ui_obj.get_solaris_data()
            if solaris_part is None:
                LOGGER.debug("No Solaris data, activating default")
                self.activate_object()
                self.right_win.scroll(scroll_to_line=0)
                return
            disk_order = self.ui_obj.get_parts_in_use().index(solaris_part)
            LOGGER.debug("solaris disk at disk_order = %s", disk_order)
            self.activate_index(disk_order)

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
        LOGGER.debug("changing type")

        part_field = self.get_active_object().get_active_object()
        part_info = part_field.data_obj

        part_order = self.ui_obj.get_parts_in_use().index(part_info)

        old_obj = part_info.discovered_doc_obj
        old_type = list()
        if old_obj is not None:
            if self.has_partition_data:
                old_type.append(old_obj.part_type)
            else:
                if old_obj.in_zpool is not None:
                    old_type.append(old_obj.in_zpool)
                else:
                    in_use = part_info.doc_obj.in_use
                    if in_use is not None:
                        if in_use['used_name']:
                            old_type.append((in_use['used_name'])[0])

        LOGGER.debug("extra type to cycle: %s", old_type)
        part_info.cycle_type(extra_type=old_type)
        self.set_disk_info(ui_obj=self.ui_obj, no_part_ok=True)
        self.activate_index(part_order)

        return None

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

    def activate_index(self, obj_index):
        '''Activate the object at the specified index '''

        if obj_index < len(self.left_win.objects):
            LOGGER.debug("activating in left_win")
            self.left_win.activate_object(obj_index)
            self.activate_object(self.left_win)
            self.right_win.scroll(scroll_to_line=0)
        else:
            activate = obj_index - len(self.left_win.objects)
            LOGGER.debug('activating in right win')
            self.right_win.activate_object_force(activate, force_to_top=True)
            self.activate_object(self.right_win)
            left_active = self.left_win.get_active_object()
            if left_active is not None:
                left_active.make_inactive()

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


def decimal_valid(edit_field, disk_win=None):
    '''Check text to see if it is a decimal number of precision no
    greater than the tenths place.

    '''
    text = edit_field.get_text().lstrip()
    radixchar = locale.localeconv()['decimal_point']
    if text.endswith(" "):
        raise UIMessage(_('Only the digits 0-9 and %s are valid.') % radixchar)
    vals = text.split(radixchar)
    if len(vals) > 2:
        raise UIMessage(_('A number can only have one %s') % radixchar)
    try:
        if len(vals[0]) > 0:
            int(vals[0])
        if len(vals) > 1 and len(vals[1]) > 0:
            int(vals[1])
    except ValueError:
        raise UIMessage(_('Only the digits 0-9 and %s are valid.') % radixchar)
    if len(vals) > 1 and len(vals[1]) > 1:
        raise UIMessage(_("Size can be specified to only one decimal place."))
    if disk_win is not None:
        text = text.rstrip(radixchar)
        if not text:
            text = "0"

        # encode user input per locale for floating point conversion
        text = text.encode(get_encoding())
        new_size = Size(str(locale.atof(text)) + Size.gb_units)
        max_size = edit_field.data_obj.get_max_size()

        # When comparing sizes, check only to the first decimal place,
        # as that is all the user sees. (Rounding errors that could
        # cause the partition/slice layout to be invalid get cleaned up
        # prior to target instantiation)
        new_size_rounded = round(new_size.get(Size.gb_units), 1)
        max_size_rounded = round(max_size.get(Size.gb_units), 1)
        if new_size_rounded > max_size_rounded:
            locale_new_size = locale.format("%.1f", new_size_rounded)
            locale_max_size = locale.format("%.1f", max_size_rounded)
            msg = _("The new size %(size)s is greater than "
                    "the available space %(avail)s") % \
                    {"size": locale_new_size,
                     "avail": locale_max_size}
            raise UIMessage(msg)
    return True


def on_exit_edit(edit_field, disk_win=None):
    '''On exit, if the user has left the field blank, set the size to 0'''

    text = edit_field.get_text()
    if not text.strip():
        text = "0"
        enctext = text.encode(get_encoding())
        # encode per locale for floating point conversion
        edit_field.set_text("%.1f" % locale.atof(enctext))

    part_order = disk_win.ui_obj.get_parts_in_use().index(edit_field.data_obj)
    LOGGER.debug("Part being resized is at index: %s", part_order)

    new_size_text = text.strip()

    LOGGER.debug("Resizing text=%s", new_size_text)
    # encode user input per locale for floating point conversion
    enctext = new_size_text.encode(get_encoding())
    new_size = Size(str(locale.atof(enctext)) + Size.gb_units)
    old_size = edit_field.data_obj.size

    new_size_byte = new_size.get(Size.byte_units)
    old_size_byte = old_size.get(Size.byte_units)

    precision = Size(UI_PRECISION).get(Size.byte_units)

    if abs(new_size_byte - old_size_byte) > precision:
        parent_doc_obj = edit_field.data_obj.doc_obj.parent
        if isinstance(parent_doc_obj, Disk):
            if isinstance(edit_field.data_obj.doc_obj, Partition):
                resized_obj = parent_doc_obj.resize_partition(
                    edit_field.data_obj.doc_obj, new_size.get(Size.gb_units),
                    size_units=Size.gb_units)
            else:
                resized_obj = parent_doc_obj.resize_slice(
                    edit_field.data_obj.doc_obj, new_size.get(Size.gb_units),
                    size_units=Size.gb_units)
        else:
            resized_obj = parent_doc_obj.resize_slice(
                edit_field.data_obj.doc_obj, new_size.get(Size.gb_units),
                size_units=Size.gb_units)

        if isinstance(resized_obj, Partition):
            resized_obj.in_zpool = ROOT_POOL
        else:
            if resized_obj.in_zpool == ROOT_POOL:
                resized_obj.tag = V_ROOT

        if disk_win is not None:
            disk_win.set_disk_info(ui_obj=disk_win.ui_obj)
            disk_win.activate_index(part_order)

    dump_doc("After resize")


def get_recommended_size(target_controller):
    '''Returns the recommended size for the installation, as a Size object '''
    if DiskWindow.REC_SIZE is None:
        DiskWindow.REC_SIZE = target_controller.recommended_target_size
    return DiskWindow.REC_SIZE


def get_minimum_size(target_controller):
    '''Returns the minimum disk space needed for installation,
       as a Size object

    '''

    if DiskWindow.MIN_SIZE is None:
        DiskWindow.MIN_SIZE = target_controller.minimum_target_size
    return DiskWindow.MIN_SIZE

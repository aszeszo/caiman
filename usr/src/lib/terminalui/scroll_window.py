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
UI component allowing subwindows that scroll.
Similar to InnerWindow
'''

import curses
import string

import terminalui

from terminalui import LOG_LEVEL_INPUT
from terminalui.inner_window import InnerWindow


class ScrollWindow(InnerWindow):
    '''A ScrollWindow is an InnerWindow that can scroll

    Note: When adding objects to this window, remember that the
    left 2 columns are reserved for the scroll bar.

    ARROW_DICT entry tuples consist of:
        (offset to scroll, method to check if at end of scroll region,
         parameters to pass to scroll method)

    '''

    ARROW_DICT = {
        curses.KEY_DOWN: (1, "at_bottom", {'lines': 1}),
        curses.KEY_UP: (-1, "at_top", {'lines': -1}),
        curses.KEY_LEFT: (-1, "at_left", {'columns': -1}),
        curses.KEY_RIGHT: (1, "at_right", {'columns': 1})}

    def redrawwin(self):
        '''Mark this ScrollWindow and its children so that they get
        completely repainted on the next screen update.

        '''
        self.window.touchwin()
        for win in self.more_windows:
            win.touchwin()
                
        self.no_ut_refresh()

    def _init_win(self, parent):
        '''Initialize a curses.pad object of appropriate size'''
        if self.is_pad:
            terminalui.LOGGER.debug("_init_win area = (%s)", self.area)

            self.window = parent.window.subwin(self.area.lines,
                                               self.area.columns,
                                               self.area.y_loc,
                                               self.area.x_loc)
            self.pad = parent.pad
        else:
            self.window = curses.newpad(self.area.scrollable_lines,
                                        self.area.scrollable_columns)
        self.window.keypad(1)
        self.window.leaveok(0)
        self.area.lines -= 1
        self.area.lower_right_y = self.area.y_loc + self.area.lines
        self.area.lower_right_x = self.area.x_loc + self.area.columns

    def __init__(self, area, enable_spelldict=False, **kwargs):
        '''ScrollWindow Constructor. See also InnerWindow.__init__

        area (required) - For ScrollWindows, area.scrollable_lines
        and area.scrollable_columns indicates the height or width
        of the scrollable area, respectively. The other parameters
        indicate the width and size of the visible portion of the
        window.

        All other parameters are used as in InnerWindow.__init__

        '''

        self.bottom = 0
        self.right = 0
        self.current_line = (0, 0)        # tuple of y,x
        self._redraw_scroll_bar = True
        if (area.scrollable_lines > area.lines):
            self.bottom = area.scrollable_lines - area.lines
        if (area.scrollable_columns > area.columns):
            self.right = area.scrollable_columns - area.columns
        self._use_vert_scroll_bar = (self.bottom > 1)
        self._use_horiz_scroll_bar = (self.right > 1)
        super(ScrollWindow, self).__init__(area, **kwargs)
        self.is_pad = True
        self.pad = self
        self.key_dict[curses.KEY_UP] = self.on_arrow_key
        self.key_dict[curses.KEY_DOWN] = self.on_arrow_key
        self.key_dict[curses.KEY_LEFT] = self.on_arrow_key
        self.key_dict[curses.KEY_RIGHT] = self.on_arrow_key
        if enable_spelldict:
            # add 'space' (ascii value 32), '-' (value 45) and backspace to the
            # key_dict
            self.key_dict[32] = self.on_letter_key
            self.key_dict[45] = self.on_letter_key
            self.key_dict[curses.KEY_BACKSPACE] = self.on_letter_key
            self.key_dict.update(dict.fromkeys(map(ord, string.lowercase),
                                               self.on_letter_key))
        self.spell_dict = dict()
        self.spell_str = ""

    def set_use_vert_scroll_bar(self, use_vert_scroll_bar):
        '''Setter for self.use_vert_scroll_bar. Triggers a redraw of
        the scroll bar on next call to _update_scroll_bar (called via
        no_ut_refresh)'''
        self._use_vert_scroll_bar = use_vert_scroll_bar
        self._redraw_scroll_bar = True

    def get_use_vert_scroll_bar(self):
        '''Getter for self.use_vert_scroll_bar'''
        return self._use_vert_scroll_bar

    use_vert_scroll_bar = property(get_use_vert_scroll_bar,
                                   set_use_vert_scroll_bar)

    def set_use_horiz_scroll_bar(self, use_horiz_scroll_bar):
        '''Setter for self.use_horiz_scroll_bar. Triggers a redraw of the
        horizontal scroll bar on next call to _update_scroll_bar (called
         via no_ut_refresh)'''
        self._use_horiz_scroll_bar = use_horiz_scroll_bar
        self._redraw_scroll_bar = True

    def get_use_horiz_scroll_bar(self):
        '''Getter for self.use_horiz_scroll_bar'''
        return self._use_horiz_scroll_bar

    use_horiz_scroll_bar = property(get_use_horiz_scroll_bar,
                                    set_use_horiz_scroll_bar)

    def _init_scroll_bar(self):
        '''Initialize the scroll bar'''

        if self.use_vert_scroll_bar:
            self.window.addch(0, 0, curses.ACS_HLINE)
            self.window.vline(1, 0, curses.ACS_VLINE, self.area.lines - 1)
            self.window.vline(self.area.lines, 0, curses.ACS_HLINE,
                              self.area.scrollable_lines - self.area.lines)
            self.window.addch(self.area.scrollable_lines - 1, 0,
                              curses.ACS_HLINE)
        else:
            self.window.vline(0, 0, InnerWindow.BKGD_CHAR,
                              self.area.scrollable_lines)

        if self.use_horiz_scroll_bar:
            terminalui.LOGGER.debug("_init_scroll_bar scrollablecolumns=%s, "
                                    " columns=%s",
                                    self.area.scrollable_columns,
                                    self.area.columns)
            self.window.addch(self.area.lines, 0, curses.ACS_VLINE)
            self.window.hline(self.area.lines, 1, curses.ACS_HLINE,
                              self.area.columns - 1)
            self.window.hline(self.area.lines, self.area.columns,
                              curses.ACS_HLINE,
                              self.area.scrollable_columns - self.area.columns)
            self.window.addch(self.area.lines, self.area.columns - 1,
                              curses.ACS_VLINE)

        self._redraw_scroll_bar = False

    def _update_scroll_bar(self):
        '''Update the scroll bar after scrolling'''
        if self._redraw_scroll_bar:
            terminalui.LOGGER.debug("redraw scoll bar -> init'ing")
            self._init_scroll_bar()
        if self.use_vert_scroll_bar:
            terminalui.LOGGER.log(LOG_LEVEL_INPUT,
                        "use_vert_scroll_bar True -> updating")
            self.window.vline(self.current_line[0] + 1, 0, curses.ACS_VLINE,
                              self.area.lines - 1)
            if self.at_top():
                char = curses.ACS_HLINE
            else:
                char = curses.ACS_UARROW
            self.window.addch(self.current_line[0], 0, char)
            if self.at_bottom():
                char = curses.ACS_HLINE
            else:
                char = curses.ACS_DARROW
            self.window.addch(self.current_line[0] + self.area.lines, 0, char)

        if self.use_horiz_scroll_bar:
            terminalui.LOGGER.log(LOG_LEVEL_INPUT,
                        "use_horiz_scroll_bar True -> updating")
            self.window.hline(self.area.lines, self.current_line[1] + 1,
                              curses.ACS_HLINE, self.area.columns - 1)
            if self.at_left():
                char = curses.ACS_VLINE
            else:
                char = curses.ACS_LARROW
            self.window.addch(self.area.lines, self.current_line[1], char)
            if self.at_right():
                char = curses.ACS_VLINE
            else:
                char = curses.ACS_RARROW
            self.window.hline(self.area.lines, self.current_line[1] +
                              self.area.columns, char, 1)

    def no_ut_refresh(self, abs_y=None, abs_x=None):
        '''The refresh method for ScrollWindows updates the visible portion
        of the pad

        '''
        if abs_y is None or abs_x is None:
            abs_y, abs_x = self.latest_yx
        self._update_scroll_bar()

        self.window.noutrefresh(self.current_line[0],
                                self.current_line[1],
                                self.area.y_loc + abs_y,
                                self.area.x_loc + abs_x,
                                self.area.lower_right_y + abs_y,
                                self.area.lower_right_x + abs_x)

        for obj in self.objects:
            obj.deep_refresh(self.area.y_loc + abs_y, self.area.x_loc + abs_x)

    def deep_refresh(self, y_loc, x_loc):
        '''Refresh the actual physical location on the screen of the part
        of the pad that's visible

        '''

        self.latest_yx = (y_loc, x_loc)
        self.no_ut_refresh(y_loc, x_loc)
        InnerWindow.deep_refresh(self, y_loc, x_loc)

    def scroll(self, lines=None, scroll_to_line=None, columns=None,
               scroll_to_column=None):
        '''Scroll the visible region downward by 'lines'. 'lines' may be
        negative. Alternatively, scroll directly to 'scroll_to_line'
       -OR-
        Scroll the visible region to the right by 'columns'. 'columns'
        may be negative. Alternatively, scroll directly to
        'scroll_to_column'
        Code only supports scrolling in one direction.

        '''
        if scroll_to_line is not None:
            self.current_line = (scroll_to_line, self.current_line[1])
        elif lines is not None:
            current_y = self.current_line[0] + lines
            self.current_line = (current_y, self.current_line[1])
        elif scroll_to_column is not None:
            self.current_line = (self.current_line[0], scroll_to_column)
        elif columns is not None:
            current_x = self.current_line[1] + columns
            self.current_line = (self.current_line[0], current_x)
        else:
            raise ValueError("Missing keyword arg (requires either 'lines', "
                             "'scroll_to_line', 'columns', or "
                             "'scroll_to_columns)")
        if self.current_line[0] > self.bottom - 1:
            self.current_line = (self.bottom - 1, self.current_line[1])
        if self.current_line[1] > self.right - 1:
            self.current_line = (self.current_line[0], self.right - 1)
        self.current_line = (max(0, self.current_line[0]),
                             max(0, self.current_line[1]))
        self.no_ut_refresh()

    def on_letter_key(self, input_key):
        '''Activate the object whose first letter corresponds to the key
        pressed
        
        '''
        # reset the spell string if the user presses <backspace>
        if input_key == curses.KEY_BACKSPACE:
            self.spell_str = ""
            return None

        # add this letter to the spelling list
        self.spell_str += chr(input_key)

        # look for this entry in the spell_dict
        for entry in sorted(self.spell_dict):
            if entry.startswith(self.spell_str):
                self.activate_object_force(self.spell_dict[entry],
                                           force_to_top=True)
                return None
        else:
            return input_key

    def on_arrow_key(self, input_key):
        '''Activate the next/previous object, or, for pure text windows, simply
        scroll down/up one line or right/left one column

        '''
        # reset the spell string
        self.spell_str = ""

        offset = ScrollWindow.ARROW_DICT[input_key][0]
        at_endpt = getattr(self, ScrollWindow.ARROW_DICT[input_key][1])
        if self.active_object is not None:
            try:
                self.activate_object(self.active_object + offset)
                return None
            except IndexError:
                if at_endpt():
                    terminalui.LOGGER.debug("%s returned true, returning "
                                            "input",
                                  ScrollWindow.ARROW_DICT[input_key][1])
                    return input_key
                else:
                    param_dict = ScrollWindow.ARROW_DICT[input_key][2]
                    # pylint: disable-msg=W0142
                    # We are purposefully using ** notation to pass parameters.
                    # Changes to this code should be done carefully and if
                    # the signature to scroll() changes, ARROW_DICT should be
                    # updated.
                    self.scroll(**param_dict)
                    return None
        else:
            if at_endpt():
                terminalui.LOGGER.log(LOG_LEVEL_INPUT,
                                      "Already %s, returning input",
                                      ScrollWindow.ARROW_DICT[input_key][1])
                return input_key
            else:
                param_dict = ScrollWindow.ARROW_DICT[input_key][2]
                # pylint: disable-msg=W0142
                # We are purposefully using ** notation to pass parameters.
                # Changes to this code should be done carefully and if
                # the signature to scroll() changes, ARROW_DICT should be
                # updated.
                self.scroll(**param_dict)
                return None

    def at_bottom(self):
        '''Returns True if this ScrollWindow can't scroll down any further'''
        return self.current_line[0] >= self.bottom - 1

    def at_top(self):
        '''Returns True if this ScrollWindow can't scroll up any further'''
        return self.current_line[0] == 0

    def at_left(self):
        '''Returns True if this ScrollWindow can't scroll left any further'''
        return self.current_line[1] == 0

    def at_right(self):
        '''Returns True if this ScrollWindow can't scroll right any further'''
        return self.current_line[1] >= self.right - 1

    def activate_object(self, index=0, loop=False, jump=False):
        '''Activate the given object, without forcing to the top'''
        self.activate_object_force(index=index, loop=loop, force_to_top=jump)

    def activate_object_force(self, index=0, loop=False, force_to_top=False):
        '''Activate the given object, if it is in the visible region.
        If it's not, scroll one line - if it is then in the visible region,
        activate it, otherwise, do nothing.

        If force_to_top is True, scroll immediately to this object, placing
        it as close to the top of the visible region as possible, and
        activate it.

        '''
        old_obj = self.get_active_object()
        super(ScrollWindow, self).activate_object(index, loop=loop,
                                                  jump=force_to_top)
        active_y_loc = self.get_active_object().area.y_loc
        terminalui.LOGGER.debug("active_y_loc=%s, current_line=%s",
                                active_y_loc, self.current_line)
        if force_to_top:
            terminalui.LOGGER.debug("scroll_to_line=active_y_loc")
            self.scroll(scroll_to_line=active_y_loc)
        elif active_y_loc < self.current_line[0]:
            self.scroll(-1)
            if active_y_loc < self.current_line[0]:
                super(ScrollWindow, self).activate_object(old_obj)
        elif (active_y_loc - self.current_line[0]) > self.area.lines:
            terminalui.LOGGER.debug("scroll to (down) %s",
                          (active_y_loc - self.area.lines))
            self.scroll(1)
            if (active_y_loc - self.current_line[0]) > self.area.lines:
                super(ScrollWindow, self).activate_object(old_obj)
        else:
            terminalui.LOGGER.debug("not scrolling")

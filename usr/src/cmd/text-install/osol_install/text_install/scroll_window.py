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
UI component allowing subwindows that scroll.
Similar to InnerWindow
'''

import curses
import logging

from osol_install.text_install import LOG_LEVEL_INPUT
from osol_install.text_install.inner_window import InnerWindow


class ScrollWindow(InnerWindow):
    '''A ScrollWindow is an InnerWindow that can scroll
    
    Scrolling is currently limited to up/down. Left/right could be
    added later if needed.
    
    Note: When adding objects to this window, remember that the
    left 2 columns are reserved for the scroll bar.
    
    '''
    
    def redrawwin(self):
        '''Mark this ScrollWindow and its children so that they get
        completely repainted on the next screen update.
        
        '''
        self.window.touchwin()
        for win in self.more_windows:
            win.touchwin()
        for obj in self.all_objects:
            obj.redrawwin()
        self.no_ut_refresh()
    
    def _init_win(self, dummy):
        '''Initialize a curses.pad object of appropriate size'''
        self.window = curses.newpad(self.area.scrollable_lines,
                                    self.area.columns)
        self.area.lines -= 1
        self.area.lower_right_y = self.area.y_loc + self.area.lines
        self.area.lower_right_x = self.area.x_loc + self.area.columns
    
    def __init__(self, area, **kwargs):
        '''ScrollWindow Constructor. See also InnerWindow.__init__
        
        area (required) - For ScrollWindows, area.scrollable_lines must be
        set. It indicates the height of the scrollable area. The other
        parameters indicate the width and size of the visible portion
        of the window.
        
        All other parameters are used as in InnerWindow.__init__
        
        '''
        self.bottom = 0
        self.current_line = 0
        self._redraw_scroll_bar = True
        if (area.scrollable_lines > area.lines):
            self.bottom = area.scrollable_lines - area.lines
        self._use_scroll_bar = (self.bottom > 1)
        super(ScrollWindow, self).__init__(area, **kwargs)
        self.is_pad = True
        self.pad = self
        self.no_ut_refresh()
    
    def set_use_scroll_bar(self, use_scroll_bar):
        '''Setter for self.use_scroll_bar. Triggers a redraw of the scroll
        bar on next call to _update_scroll_bar (called via no_ut_refresh)'''
        self._use_scroll_bar = use_scroll_bar
        self._redraw_scroll_bar = True
    
    def get_use_scroll_bar(self):
        '''Getter for self.use_scroll_bar'''
        return self._use_scroll_bar
    
    use_scroll_bar = property(get_use_scroll_bar, set_use_scroll_bar)
    
    def _init_scroll_bar(self):
        '''Initialize the scroll bar'''
        if self.use_scroll_bar:
            logging.debug("use_scroll_bar True -> init'ing")
            self.window.addch(0, 0, curses.ACS_HLINE)
            self.window.vline(1, 0, curses.ACS_VLINE, self.area.lines - 1)
            self.window.vline(self.area.lines, 0, curses.ACS_HLINE,
                              self.area.scrollable_lines - self.area.lines)
            self.window.addch(self.area.scrollable_lines - 1, 0,
                              curses.ACS_HLINE)
        else:
            logging.debug("use_scroll_bar False -> clearing")
            self.window.vline(0, 0, InnerWindow.BKGD_CHAR,
                              self.area.scrollable_lines)
        self._redraw_scroll_bar = False
    
    def _update_scroll_bar(self):
        '''Update the scroll bar after scrolling'''
        if self._redraw_scroll_bar:
            logging.debug("redraw scoll bar -> init'ing")
            self._init_scroll_bar()
        if self.use_scroll_bar:
            logging.log(LOG_LEVEL_INPUT, "use_scroll_bar True -> updating")
            self.window.vline(self.current_line + 1, 0, curses.ACS_VLINE,
                              self.area.lines - 1)
            if self.at_top():
                char = curses.ACS_HLINE
            else:
                char = curses.ACS_UARROW
            self.window.addch(self.current_line, 0, char)
            if self.at_bottom():
                char = curses.ACS_HLINE
            else:
                char = curses.ACS_DARROW
            self.window.addch(self.current_line + self.area.lines, 0, char)
    
    def no_ut_refresh(self):
        '''The refresh method for ScrollWindows updates the visible portion
        of the pad
        
        '''
        self._update_scroll_bar()
        self.window.noutrefresh(self.current_line, 0, self.area.y_loc,
                                self.area.x_loc, self.area.lower_right_y,
                                self.area.lower_right_x)
    
    def scroll(self, lines=None, scroll_to=None):
        '''Scroll the visible region downward by 'lines'. 'lines' may be
        negative. Alternatively, scroll directly to 'scroll_to'
        
        '''
        if scroll_to is not None:
            self.current_line = scroll_to
        elif lines is not None:
            self.current_line += lines
        else:
            raise ValueError("Missing keyword arg (requires either 'lines'"
                             " or 'scroll_to')")
        if self.current_line > self.bottom - 1:
            self.current_line = self.bottom - 1
        self.current_line = max(0, self.current_line)
        self.no_ut_refresh()
    
    def on_key_down(self, input_key):
        '''Activate the next object, or, for pure text windows, simply
        scroll down one line
        
        '''
        if self.active_object is not None:
            try:
                self.activate_object(self.active_object + 1)
                return None
            except IndexError:
                if self.at_bottom():
                    return input_key
                else:
                    self.scroll(1)
                    return None
        else:
            if self.at_bottom():
                logging.log(LOG_LEVEL_INPUT,
                            "Already at bottom, returning input")
                return input_key
            else:
                self.scroll(1)
        return None
    
    def on_key_up(self, input_key):
        '''Activate the previous object, or, for pure text windows, simply
        scroll up one line
        
        '''
        if self.active_object is not None:
            try:
                self.activate_object(self.active_object - 1)
                return None
            except IndexError:
                if self.at_top():
                    return input_key
                else:
                    self.scroll(-1)
                    return None
        else:
            if self.at_top():
                logging.log(LOG_LEVEL_INPUT, "Already at top, returning input")
                return input_key
            else:
                self.scroll(-1)
                return None
    
    def at_bottom(self):
        '''Returns True if this ScrollWindow can't scroll down any further'''
        return self.current_line >= self.bottom - 1
    
    def at_top(self):
        '''Returns True if this ScrollWindow can't scroll up any further'''
        return self.current_line == 0
    
    def activate_object(self, index=0, loop=False):
        '''Activate the given object, without forcing to the top'''
        self.activate_object_force(index=index, loop=loop)
    
    def activate_object_force(self, index=0, loop=False, force_to_top=False):
        '''Activate the given object, if it is in the visible region.
        If it's not, scroll one line - if it is then in the visible region,
        activate it, otherwise, do nothing.
        
        If force_to_top is True, scroll immediately to this object, placing
        it as close to the top of the visible region as possible, and
        activate it.
        
        '''
        old_obj = self.get_active_object()
        super(ScrollWindow, self).activate_object(index, loop=loop)
        active_y_loc = self.get_active_object().area.y_loc
        logging.debug("active_y_loc=%s, current_line=%s", active_y_loc,
                      self.current_line)
        if force_to_top:
            logging.debug("scroll_to=active_y_loc")
            self.scroll(scroll_to=active_y_loc)
        elif active_y_loc < self.current_line:
            self.scroll(-1)
            if active_y_loc < self.current_line:
                super(ScrollWindow, self).activate_object(old_obj)
        elif (active_y_loc - self.current_line) > self.area.lines:
            logging.debug("scroll to (down) %s",
                          (active_y_loc - self.area.lines))
            self.scroll(1)
            if (active_y_loc - self.current_line) > self.area.lines:
                super(ScrollWindow, self).activate_object(old_obj)
        else:
            logging.debug("not scrolling")

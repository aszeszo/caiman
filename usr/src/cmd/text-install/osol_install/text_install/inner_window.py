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
Generic UI pieces representing a portion of the window. Provides
support for handling input, writing text to the screen, and managing
sub-windows within the window.
'''


import logging
import curses
from curses.ascii import ctrl
from copy import copy

from osol_install.text_install import LOG_LEVEL_INPUT


KEY_ESC = 27
KEY_BS = 127 # Backspace code that curses doesn't translate right
KEY_CTRL_H = ord(ctrl('h'))
KEY_TAB = ord(ctrl('i'))
KEY_ENTER = ord(ctrl('j'))
ZERO_CHAR = ord('0')


def no_action(input_key):
    '''Supports defining actions which have no effect and allow parent
    windows to handle the key.
    
    '''
    return input_key


def consume_action(dummy):
    '''Supports defining an action which has no effect, and consume the
    keystroke so that parents do not handle it.
    
    '''
    return None


class InnerWindow(object):
    '''Wrapper around curses.windows objects providing common functions
    
    An InnerWindow wraps around a curses window, and represents an area
    of the screen. Each InnerWindow requires a parent window. The 'ultimate'
    parent of all InnerWindows is the sole instance of MainWindow.
    
    By default, InnerWindows have functions for adding text, processing input,
    and managing children InnerWindows.
    
    The following class variables are used to indicate the status of ESC key
    navigations.
    
    BEGIN_ESC indicates that the next keystroke, if 0-9, should be
    translated to F#
    
    USE_ESC indicates that, at some point during program execution,
    ESC has been pressed, and the footer should, for the remainder of program
    execution, print Esc-#_<description> for navigation descriptions. Once set
    to True, it should never be set back to False.
    
    UPDATE_FOOTER is a flag that indicates that Esc was just hit for the
    first time, and the managing window should immediately update the footer
    text.
    
    '''
    BEGIN_ESC = False
    USE_ESC = False
    UPDATE_FOOTER = False
    KEY_TRANSLATE = {KEY_TAB : curses.KEY_DOWN,
                     KEY_ENTER : curses.KEY_ENTER,
                     KEY_BS : curses.KEY_BACKSPACE,
                     KEY_CTRL_H : curses.KEY_BACKSPACE}
    BKGD_CHAR = ord(' ')
    REPAINT_KEY = ord(ctrl('L'))
    
    def no_ut_refresh(self):
        '''Call noutrefresh on the curses window, and synchronize the
        cursor location as needed
        
        '''
        if self.is_pad: # Let the parent ScrollWindow handle pad updates
            self.window.cursyncup()
            self.pad.no_ut_refresh()
        else:
            self.window.noutrefresh()
    
    def refresh(self):
        '''Like curses.refresh(), call no_ut_refresh followed by doupdate()'''
        self.no_ut_refresh()
        curses.doupdate()
    
    def redrawwin(self):
        '''Mark the window and its children so that it will be completely
        redrawn on the next call to do_update
        
        '''
        self.window.redrawwin()
        for win in self.more_windows:
            win.redrawwin()
        self.no_ut_refresh()
        for obj in self.all_objects:
            obj.redrawwin()
    
    def set_color(self, color):
        '''Sets the color attributes to 'color'
        
        This private method immediately updates the background color.
        Note that it doesn't reference self.color
        
        '''
        if color is None:
            return
        
        self.window.bkgd(InnerWindow.BKGD_CHAR, color)
        self.no_ut_refresh()
        
        for win in self.more_windows:
            win.bkgd(InnerWindow.BKGD_CHAR, color)
            win.noutrefresh()
    
    def _adjust_area(self, window):
        '''Create a copy of area, and adjust its coordinates to be absolute
        if needed
        
        '''
        if not self.is_pad:
            if isinstance(window, InnerWindow):
                self.area.relative_to_absolute(window.window,
                                               border=window.border_size)
            elif window is not None:
                self.area.relative_to_absolute(window)
    
    def _init_win(self, parent):
        '''Create the curses window'''
        if self.is_pad:
            logging.debug("lines=%d, columns=%d, y_loc=%d, x_loc=%d",
                          self.area.lines, self.area.columns, self.area.y_loc,
                           self.area.x_loc)
            self.window = parent.window.subwin(self.area.lines,
                                               self.area.columns,
                                               self.area.y_loc,
                                               self.area.x_loc)
            self.pad = parent.pad
        else:
            self.window = curses.newwin(self.area.lines, self.area.columns,
                                        self.area.y_loc, self.area.x_loc)
        
        self.window.keypad(1)
        self.window.leaveok(0) 
    
    def __init__(self, area, window=None, color_theme=None, color=None,
                 highlight_color=None, at_index=None, add_obj=True,
                 border_size=(0, 0), data_obj=None):
        '''Build an InnerWindow
        
        area (required): Describes the area to use when building this window.
        Coordinates should be relative to window, if window is given. If window
        is not given, these must be absolute coordinates on the terminal
        
        window (optional): The parent window. If given, area is assumed to
        indicate a location within the parent. Additionally, if window is
        an InnerWindow, window.add_object(self) is called to register this
        new window with its parent
        
        color_theme (required if curses window): The color theme for this
        window. This property gets propagated to subwindows. If None, the
        parent window's color_theme is used. Unless this window requires
        unique coloring, the parent theme should be used.
        
        color (optional): The color attributes for this window. If None,
        color_theme.default is used. In general, this parameter is reserved
        for subclasses of InnerWindow. Other consumers should pass in an
        appropriate color_theme.
        
        highlight_color (optional): Color attributes for this window when
        'selected' or 'highlighted.' Defaults to color (meaning
        no highlighting is used. In general, this parameter is reserved
        for subclasses of InnerWindow. Other consumers should pass in an
        appropriate color_theme
        
        '''
        self.border_size = border_size
        self.selectable = True
        self.data_obj = data_obj
        self.on_make_active = None
        self.on_make_inactive = None
        self.on_make_active_kwargs = {}
        self.on_make_inactive_kwargs = {}
        # We check self.is_pad, so that subclasses can set it prior to
        # calling InnerWindow.__init__
        self.is_pad = (getattr(window, "is_pad", False) or
                        getattr(self, "is_pad", False))
        self.pad = None
        self.objects = []
        self.all_objects = []
        self.more_windows = []
        self.active_object = None
        self.key_dict = None
        self._init_key_dict()
        self.area = copy(area)
        self._adjust_area(window)
        self.color_theme = color_theme
        if isinstance(window, InnerWindow):
            window.add_object(self, at_index=at_index, selectable=add_obj)
            if self.color_theme is None:
                self.color_theme = window.color_theme
        self.window = None
        self._init_win(window)
        
        if color is not None:
            self.color = color
        else:
            self.color = self.color_theme.default
        
        if highlight_color is not None:
            self.highlight_color = highlight_color
        else:
            self.highlight_color = self.color
        
        self.set_color(self.color)
    
    def make_active(self):
        '''Highlight this window and activate the active_object, if there
        is one.
        
        '''
        self.set_color(self.highlight_color)
        if self.objects:
            if self.active_object is None:
                self.active_object = 0
            self.objects[self.active_object].make_active()
        # pylint: disable-msg=E1102
        # E1102: <attr> is not callable. However, we're checking that already
        if callable(self.on_make_active):
            self.on_make_active(**self.on_make_active_kwargs)
    
    def make_inactive(self):
        '''Mark this window inactive, setting its color back to 'normal'
        Also make_inactive its active_object.
        
        '''
        self.set_color(self.color)
        if self.active_object is not None:
            self.objects[self.active_object].make_inactive()
        # pylint: disable-msg=E1102
        # E1102: <attr> is not callable. However, we're checking that already
        if callable(self.on_make_inactive):
            self.on_make_inactive(**self.on_make_inactive_kwargs)
    
    def activate_object(self, index=0, loop=False):
        '''Set a specific object to be the active object.
        
        This function accepts either an integer index,
        or an object reference. If an object reference is
        passed in, it must be an object in this InnerWindow.objects
        list.
        
        if loop == True, integers that are out of bounds of the size of the
        objects list are shifted to be in bounds. This allows looping from
        the last item in the list to the first (and vice versa), similar
        to the syntax for accessing list items.
        
        if loop is False, and index is an integer < 0 or > len(self.objects),
        an IndexError is raised.
        
        '''
        if not isinstance(index, int):
            index = self.objects.index(index)
        elif loop:
            index = index % len(self.objects)
        elif index < 0 or index >= len(self.objects):
            err_msg = ("Index (%i) out of range (0-%i)" %
                       (index, len(self.objects)))
            raise IndexError(err_msg)
        if self.active_object is not None:
            self.objects[self.active_object].make_inactive()
        self.objects[index].make_active()
        self.active_object = index
        logging.log(LOG_LEVEL_INPUT, "Object at index %s now active", self.active_object)
        self.no_ut_refresh()
    
    def add_text(self, text, start_y=0, start_x=0, max_chars=None,
                 centered=False):
        '''Add a single line of text to the window
        
        'text' must fit within the specified space, or it will be truncated
        
        '''
        win_y, win_x = self.window.getmaxyx()
        logging.log(LOG_LEVEL_INPUT, "start_y=%d, start_x=%d, max_chars=%s, centered=%s,"
                    " win_max_x=%s, win_max_y=%s",
                    start_y, start_x, max_chars, centered, win_x, win_y)
        max_x = self.window.getmaxyx()[1] - self.border_size[1]
        start_x += self.border_size[1]
        if centered:
            length = len(text)
            max_x = max_x - start_x
            if self.window.getmaxyx()[0] == (start_y + 1):
                max_x -= 1 # Cannot print to bottom-right corner
            start_x = max((max_x - length) / 2 + start_x, start_x)
        
        abs_max_chars = max_x - start_x
        if max_chars is None:
            max_chars = abs_max_chars
        else:
            max_chars = min(max_chars, abs_max_chars)
        
        logging.log(LOG_LEVEL_INPUT, "calling addnstr with params start_y=%s, start_x=%s, "
                    "text=%s, max_chars=%s", start_y, start_x, text, max_chars)
        self.window.addnstr(start_y, start_x, text, max_chars)
        self.no_ut_refresh()
    
    @staticmethod
    def convert_paragraph(text, max_chars):
        '''Break a paragraph of text up into chunks that will each
        fit within max_chars. Splits on whitespace and newlines
        
        max_chars defaults to the size of this window.
        
        '''
        text_lines = text.expandtabs(4).splitlines()
        paragraphed_lines = []
        for line in text_lines:
            if len(line) <= max_chars:
                paragraphed_lines.append(line)
            else:
                start_pt = 0
                end_pt = 0
                while end_pt + max_chars < len(line): 
                    end_pt = line.rfind(" ", start_pt, start_pt + max_chars)
                    if end_pt == -1:
                        end_pt = start_pt + max_chars
                    paragraphed_lines.append(line[start_pt:end_pt].lstrip())
                    start_pt = end_pt + 1
                else:
                    paragraphed_lines.append(line[end_pt:].lstrip())
        return paragraphed_lines
    
    def add_paragraph(self, text, start_y=0, start_x=0, max_y=None,
                      max_x=None):
        '''Add a block of text to the window
        
        Add a paragraph to the screen. If a string is passed in, it is
        converted using convert_paragraph. If a list of strings is passed in,
        each string will fit in the space alloted (long lines will be
        truncated). Any lines that would be printed past max_y will not be
        printed.
        
        The number of lines used is returned.
        
        '''
        logging.log(LOG_LEVEL_INPUT, "add_paragraph: start_y=%d, start_x=%d, max_y=%s, "
                    "max_x=%s", start_y, start_x, max_y, max_x)
        win_size_y, win_size_x = self.window.getmaxyx()
        start_y += self.border_size[0]
        if max_y is None:
            max_y = win_size_y - start_y - self.border_size[0]
        if max_x is None:
            max_x = win_size_x
        max_chars = max_x - start_x - self.border_size[1] - 1
        y_index = start_y
        if isinstance(text, basestring):
            text = self.convert_paragraph(text, max_chars)
        for line in text:
            self.add_text(line, y_index, start_x, max_chars)
            y_index += 1
            if y_index > max_y + start_y:
                logging.warn("Could not fit all text in space for the "
                             "paragraph. Last line:\n%s", line)
                break
        return y_index - start_y
    
    def add_object(self, obj, at_index=None, selectable=True):
        '''Add an InnerWindow) to this window's object list'''
        if at_index is None:
            at_index = len(self.objects)
        if selectable:
            self.objects.insert(at_index, obj)
        self.all_objects.append(obj)
    
    def remove_object(self, obj):
        '''Convenience method for removing an object from both self.objects
        and self.all_objects
        
        '''
        if obj in self.objects:
            obj_index = self.objects.index(obj)
            if obj_index == self.active_object:
                self.active_object = max(0, self.active_object - 1)
            self.objects.remove(obj)
        
        self.all_objects.remove(obj)
        obj.clear()
        self.no_ut_refresh()
    
    def clear(self):
        '''Remove all objects from this window's list and clear the screen
        Also resets the key_dictionary to a default state
        
        The background of this window will still be displayed; clear the parent
        if the window should be removed in entirety
        
        '''
        for obj in self.all_objects:
            obj.clear()
        self.objects = []
        self.all_objects = []
        self.active_object = None
        self.window.erase()
        self.set_color(self.color)
        self._init_key_dict()
    
    def on_key_down(self, input_key):
        '''On curses.KEY_DOWN:
        Move to the next active_object, if this window is handling objects.
        If already at the last object, let the parent handle the keystroke.
        
        '''
        logging.log(LOG_LEVEL_INPUT, "InnerWindow.on_key_down\n%s", type(self))
        if self.active_object is not None:
            try:
                self.activate_object(self.active_object + 1)
                return None
            except IndexError:
                return input_key
        else:
            return input_key
    
    def on_key_up(self, input_key):
        '''On curses.KEY_UP:
        Move to the previous active_object, if this window is handling objects.
        If already at the first object, let the parent handle the keystroke.
        
        '''
        logging.log(LOG_LEVEL_INPUT, "InnerWindow.on_key_up")
        if self.active_object is not None:
            try:
                self.activate_object(self.active_object - 1)
                return None
            except IndexError:
                return input_key
        else:
            return input_key
    
    def process(self, input_key):
        '''Process keyboard input
        
        Keyboard input is handled in a "bottom-up" manner. If this window
        has an active object, the input is passed down to it. If the input
        isn't handled by the object, this object tries to handle it. If it
        can't handle it, the keystroke is passed back up the chain.
        
        '''
        if self.active_object is not None:
            input_key = self.objects[self.active_object].process(input_key)
        if input_key is None:
            return input_key
        else:
            handler = self.key_dict.get(input_key, no_action)
            return handler(input_key)
    
    def _init_key_dict(self):
        '''Map some keystrokes by default:
        
        KEY_DOWN -> InnerWindow.on_key_down
        KEY_UP -> InnerWindow.on_key_up
        
        '''
        self.key_dict = {}
        self.key_dict[curses.KEY_DOWN] = self.on_key_down
        self.key_dict[curses.KEY_UP] = self.on_key_up
        self.key_dict[curses.KEY_LEFT] = no_action
        self.key_dict[curses.KEY_RIGHT] = no_action
        self.key_dict[InnerWindow.REPAINT_KEY] = no_action
    
    @staticmethod
    def translate_input(input_key):
        '''Translate keyboard input codes
        
        This function will translate keyboard input.
        Its primary job is understanding Esc-# sequences and turning them
        into F# key codes. It also converts keys as indicated by
        InnerWindow.KEY_TRANSLATE.
        
        '''
        logging.log(LOG_LEVEL_INPUT, "Got char code %s", input_key)
        if InnerWindow.BEGIN_ESC:
            logging.log(LOG_LEVEL_INPUT, "Ending esc-sequence")
            InnerWindow.BEGIN_ESC = False
            if curses.ascii.isdigit(input_key):
                logging.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_FN")
                return input_key - ZERO_CHAR + curses.KEY_F0
            else:
                logging.log(LOG_LEVEL_INPUT,
                            "Invalid esc-sequence, returning raw input")
        elif input_key == KEY_ESC:
            logging.log(LOG_LEVEL_INPUT, "Beginning esc-sequence")
            if not InnerWindow.USE_ESC:
                InnerWindow.USE_ESC = True
                InnerWindow.UPDATE_FOOTER = True
            InnerWindow.BEGIN_ESC = True
            return None
        input_key = InnerWindow.KEY_TRANSLATE.get(input_key, input_key)
        return input_key
    
    def getch(self):
        '''InnerWindow.getch() searches downward to the bottom-most
        active object. If this *is* the bottom-most active object,
        get the input from the user (blocking, unless self.window.timeout()
        has been set), translate it, and return it.
        Once found, the active object's window.getch() function is called.
        
        This function is required to ensure that curses.window.getch() is
        called from the active object. Curses will update the console
        differently based on which window calls getch()
        
        '''
        if self.active_object is not None:
            return self.objects[self.active_object].getch()
        else:
            try:
                input_key = self.window.getch()
                return InnerWindow.translate_input(input_key)
            except ValueError:
                return None
    
    def get_cursor_loc(self):
        '''Retrieve the cursor location from the active UI element'''
        if self.active_object is not None:
            return self.get_active_object().get_cursor_loc()
        else:
            return None
    
    def get_active_object(self):
        '''Convenience method for retrieving the active object.
        Returns None if no active object is set'''
        if self.active_object is not None:
            return self.objects[self.active_object]
        else:
            return None

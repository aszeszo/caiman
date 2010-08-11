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
Window that represents the entire terminal, and 'top-level' functions,
such as capturing keystrokes that will change the screen
'''

import curses
from curses.ascii import ctrl

from osol_install.text_install import _
from osol_install.text_install.color_theme import ColorTheme
from osol_install.text_install.action import Action
from osol_install.text_install.error_window import ErrorWindow
from osol_install.text_install.i18n import textwidth, \
                                           center_columns, \
                                           get_encoding
from osol_install.text_install.inner_window import InnerWindow
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea


class MainWindow(object):
    '''Represent initscr (the whole screen), and break it into a border,
    header, and central region. Map F# keystrokes to Actions
    
    '''
    
    def __init__(self, initscr, screen_list, theme=None, force_bw=False):
        '''Set the theme, and call reset to initialize the terminal to
        prepare for the first screen.
        
        '''
        
        if theme is not None:
            self.theme = theme
        else:
            self.theme = ColorTheme(force_bw=force_bw)
        self.screen_list = screen_list
        self.initscr = initscr
        self.default_cursor_pos = (initscr.getmaxyx()[0] - 1, 0)
        self.cursor_pos = self.default_cursor_pos
        self.footer = None
        self.header = None
        self._cur_header_text = None
        self.central_area = None
        self.popup_win = None
        self.error_line = None
        self._active_win = None
        self.continue_action = None
        self.back_action = None
        self.help_action = None
        self.quit_action = None
        self.actions = None
        self.reset()
    
    def redrawwin(self):
        '''Completely repaint the screen'''
        self.header.redrawwin()
        self.footer.redrawwin()
        self.error_line.redrawwin()
        self.central_area.redrawwin()
        if self._active_win is self.popup_win:
            self.popup_win.redrawwin()
    
    def do_update(self):
        '''Wrapper to curses.doupdate()'''
        curses.setsyx(*self.get_cursor_loc())
        curses.doupdate()
    
    def get_cursor_loc(self):
        '''Retrieve the current cursor position from the active UI
        element.
        
        '''
        cursor = self.central_area.get_cursor_loc()
        if cursor is None:
            cursor = self.cursor_pos
        return cursor
    
    def reset(self):
        '''Create the InnerWindows representing the header, footer/border,
        error line, and main central_area
        
        '''
        window_size = self.initscr.getmaxyx()
        win_size_y = window_size[0]
        win_size_x = window_size[1]
        footer_area = WindowArea(1, win_size_x, win_size_y - 1, 0)
        self.footer = InnerWindow(footer_area, color_theme=self.theme,
                                  color=self.theme.border)
        top = self.initscr.derwin(1, win_size_x, 0, 0)
        left = self.initscr.derwin(win_size_y - 2, 1, 1, 0)
        right = self.initscr.derwin(win_size_y - 2, 1, 1, win_size_x - 1)
        self.footer.more_windows = [top, left, right]
        self.footer.set_color(self.theme.border)
        header_area = WindowArea(1, win_size_x - 2, 1, 1)
        self.header = InnerWindow(header_area, color_theme=self.theme,
                                  color=self.theme.header)
        central_win_area = WindowArea(win_size_y - 4, win_size_x - 2, 2, 1)
        self.central_area = InnerWindow(central_win_area,
                                        border_size=(0, 2),
                                        color_theme=self.theme)
        self._active_win = self.central_area
        popup_win_area = WindowArea(central_win_area.lines - 10,
                                    central_win_area.columns - 20,
                                    5, 10, central_win_area.lines - 10)
        self.popup_win = ScrollWindow(popup_win_area, window=self.central_area,
                                      color=self.theme.error_msg,
                                      highlight_color=self.theme.error_msg)
        error_area = WindowArea(1, win_size_x - 2, win_size_y - 2, 1)
        self.error_line = ErrorWindow(error_area, color_theme=self.theme)
        self.reset_actions()
    
    def reset_actions(self):
        '''Reset the actions to the defaults, clearing any custom actions
        registered by individual screens
        
        '''
        self.continue_action = Action(curses.KEY_F2, _("Continue"),
                                      self.screen_list.get_next)
        self.back_action = Action(curses.KEY_F3, _("Back"),
                                  self.screen_list.previous_screen)
        self.help_action = Action(curses.KEY_F6, _("Help"),
                                  self.screen_list.show_help)
        self.quit_action = Action(curses.KEY_F9, _("Quit"),
                                  self.screen_list.quit)
        self.set_default_actions()
    
    def clear(self):
        '''Clear all InnerWindows and reset_actions()'''
        self.header.clear()
        self.footer.clear()
        self.central_area.clear()
        self.error_line.clear_err()
        self.reset_actions()
    
    def set_header_text(self, header_text):
        '''Set the header_text'''
        text = center_columns(header_text, self.header.area.columns - 1)
        self.header.add_text(text)
        self._cur_header_text = text
    
    def set_default_actions(self):
        '''Clear the actions dictionary and add the default actions back
        into it
        
        '''
        self.actions = {}
        self.actions[self.continue_action.key] = self.continue_action
        self.actions[self.back_action.key] = self.back_action
        self.actions[self.help_action.key] = self.help_action
        self.actions[self.quit_action.key] = self.quit_action
        
    def show_actions(self):
        '''Read through the actions dictionary, displaying all the actions
        descriptive text along the footer (along with a prefix linked to
        its associated keystroke)
        
        '''
        self.footer.window.clear()
        if InnerWindow.USE_ESC:
            prefix = " Esc-"
        else:
            prefix = "  F"
        strings = []
        length = 0
        action_format = "%s%i_%s"
        for key in sorted(self.actions.keys()):
            key_num = key - curses.KEY_F0
            action_text = self.actions[key].text
            action_str = action_format % (prefix, key_num, action_text)
            strings.append(action_str)
        display_str = "".join(strings)
        max_len = self.footer.window.getmaxyx()[1]
        length = textwidth(display_str)
        if not InnerWindow.USE_ESC:
            length += (len(" Esc-") - len("  F")) * len(self.actions)
        if length > max_len:
            raise ValueError("Can't display footer actions - string too long")
        self.footer.window.addstr(display_str.encode(get_encoding()))
        self.footer.window.noutrefresh()
    
    def getch(self):
        '''Call down into central_area to get a keystroke, and, if necessary,
        update the footer to switch to using the Esc- prefixes
        
        '''
        input_key = self._active_win.getch()
        if input_key == InnerWindow.REPAINT_KEY:
            self.redrawwin()
            input_key = None
        if InnerWindow.UPDATE_FOOTER:
            InnerWindow.UPDATE_FOOTER = False
            self.show_actions()
        return input_key
    
    def process_input(self, current_screen):
        '''Read input until a keystroke that fires a screen change
        is caught
        
        '''
        input_key = None
        while input_key not in self.actions:
            input_key = self.getch()
            input_key = self.central_area.process(input_key)
            self.do_update()
        return self.actions[input_key].do_action(current_screen)
    
    def pop_up(self, header, question, left_btn_txt, right_btn_txt,
               color=None):
        '''Suspend the current screen, setting the header
        to 'header', presenting the 'question,' and providing two 'buttons'.
        Returns True if the RIGHT button is selected, False if the LEFT is
        selected. The LEFT button is initially selected.
        
        '''
        
        
        # Hide the cursor, storing its previous state (visibility) so
        # it can be restored when finished. Then, move the cursor
        # to the default position (in case this terminal type does not support
        # hiding the cursor entirely)
        try:
            old_cursor_state = curses.curs_set(0)
        except curses.error:
            old_cursor_state = 2
        cursor_loc = curses.getsyx()
        curses.setsyx(self.cursor_pos[0], self.cursor_pos[1])
        
        # Add the header, a border, and the question to the window
        self.popup_win.window.border()
        header_x = (self.popup_win.area.columns - textwidth(header)) / 2
        self.popup_win.add_text(header, 0, header_x)
        y_loc = 2
        y_loc += self.popup_win.add_paragraph(question, y_loc, 2)
        y_loc += 2
        
        
        # Set the background color based on the parameter given, or choose
        # a default based on the theme. Set the highlight_color by flipping
        # the A_REVERSE bit of the color
        if color is None:
            color = self.popup_win.color
        self.popup_win.set_color(color)
        highlight_color = color ^ curses.A_REVERSE
        
        # Create two "buttons" of equal size by finding the larger of the
        # two, and centering them
        max_len = max(textwidth(left_btn_txt), textwidth(right_btn_txt))
        left_btn_txt = " [ %s ]" % left_btn_txt.center(max_len)
        right_btn_txt = " [ %s ]" % right_btn_txt.center(max_len)
        button_len = textwidth(left_btn_txt) + 1
        win_size = self.popup_win.window.getmaxyx()
        left_area = WindowArea(1, button_len, y_loc,
                               (win_size[1] / 2) - (button_len + 2))
        left_button = ListItem(left_area, window=self.popup_win,
                               text=left_btn_txt, color=color,
                               highlight_color=highlight_color)
        right_area = WindowArea(1, button_len, y_loc, win_size[1] / 2 + 2)
        right_button = ListItem(right_area, window=self.popup_win,
                                text=right_btn_txt, color=color,
                                highlight_color=highlight_color)
        
        # Highlight the left button, clear any errors on the screen,
        # and display the pop up
        self.popup_win.activate_object(left_button)
        self.popup_win.no_ut_refresh()
        self.error_line.clear_err()
        self.do_update()
        
        self._active_win = self.popup_win
        # Loop until the user selects an option.
        input_key = None
        while input_key != curses.KEY_ENTER:
            input_key = self.getch()
            input_key = self.popup_win.process(input_key)
            if input_key == curses.KEY_LEFT:
                self.popup_win.activate_object(left_button)
            elif input_key == curses.KEY_RIGHT:
                self.popup_win.activate_object(right_button)
            self.do_update()
        self._active_win = self.central_area
        user_selected = (self.popup_win.get_active_object() is right_button)
        
        # Clear the pop up and restore the previous screen, including the
        # cursor position and visibility
        self.popup_win.clear()
        self.central_area.redrawwin()
        curses.setsyx(cursor_loc[0], cursor_loc[1])
        try:
            curses.curs_set(old_cursor_state)
        except curses.error:
            pass
        self.do_update()
        
        return user_selected

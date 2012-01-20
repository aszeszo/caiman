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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Display individual help screen or help topics screen
'''

import curses
import locale
import os
import platform

import terminalui
from terminalui import _
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.i18n import convert_paragraph, textwidth
from terminalui.list_item import ListItem
from terminalui.scroll_window import ScrollWindow
from terminalui.window_area import WindowArea


class HelpScreen(BaseScreen):
    '''Show localized help file pertaining to last traversed screen or
    help topics list from which to choose a desired help topic.

    '''

    def __init__(self, main_win, help_header, help_index, intro):
        super(HelpScreen, self).__init__(main_win)

        try:
            self.locale = locale.setlocale(locale.LC_MESSAGES, "")
        except locale.Error:
            terminalui.LOGGER.warning("System configured with invalid "
                                      "locale(5), falling back to C.")
            self.locale = locale.setlocale(locale.LC_MESSAGES, "C")

        terminalui.LOGGER.debug("locale=%s", self.locale)

        self.help_header = help_header
        self.help_index = help_index
        self.intro = intro

        self.screen = None
        self.screen_last = None
        self.help_info = []
        self.help_dict = None
        self.topics = False
        self.scroll_region = None
        self.cur_help_idx = 0
        self.is_x86 = (platform.processor() == "i386")

    def setup_help_data(self, screens):
        '''Setup the help_dict and help_info structures

        help_dict contains:
            key: screen name
            tuple:  (<helpfile_name>, <header for help screen>)
            tuple:  (<helpfile_name>, <header for help screen
                                       and help topics menu entry>)

        help_info contains tuples:
           (tuple of screen names, format of text)

        '''
        self.help_dict = {}
        self.help_info = []

        for screen in screens:
            if screen.help_data[0]:
                key = screen.__class__.__name__ + screen.instance
                self.help_dict[key] = screen.help_data
                self.help_info.append((key, " " + screen.help_format))

        terminalui.LOGGER.debug("self.help_dict=%s", self.help_dict)
        terminalui.LOGGER.debug("self.help_info=%s", self.help_info)

    def set_actions(self):
        '''Remove the continue key for help screen and Help key for
        help topics screen. Redirect F2_Continue to display the selected
        topic, when at the topics list

        '''

        terminalui.LOGGER.debug("in set_actions self.class_name=%s",
                      self.__class__.__name__)

        # change F6 description
        self.main_win.help_action.text = self.help_index

        # change continue to call continue_action, rather than
        # normal continue. Though we stay on the same screen,
        # we simulate the continue here by changing the screen text.
        #
        help_continue = Action(curses.KEY_F2,
                               self.main_win.continue_action.text,
                               self.continue_action)
        self.main_win.actions[help_continue.key] = help_continue

        if (self.screen == self.__class__.__name__):
            # help topics screen
            self.main_win.actions.pop(self.main_win.help_action.key, None)
        else:
            # help screen
            self.main_win.actions.pop(self.main_win.continue_action.key, None)

    def display_help_topics(self):
        '''Display the help topics screen.'''

        self.main_win.set_header_text(self.help_header)
        y_loc = 1

        y_loc += self.center_win.add_paragraph(self.intro, y_loc, 1,
                                               max_x=(self.win_size_x - 1))
        y_loc += 1

        area = WindowArea(scrollable_lines=(len(self.help_info) + 1),
                          y_loc=y_loc, x_loc=0)
        terminalui.LOGGER.debug("lines=%s", len(self.help_dict))
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x

        self.scroll_region = ScrollWindow(area, window=self.center_win)

        # add the entries to the screen
        terminalui.LOGGER.debug("range=%s", len(self.help_info))
        for idx, info in enumerate(self.help_info):
            # create ListItem for each help topic
            topic_format = info[1]
            topic_title = self.help_dict[info[0]][1]
            help_topic = topic_format % topic_title
            hilite = min(self.win_size_x, textwidth(help_topic) + 1)
            list_item = ListItem(WindowArea(1, hilite, idx, 0),
                                 window=self.scroll_region, text=help_topic)
            terminalui.LOGGER.debug("self.screen_last=%s", self.screen_last)
            if self.screen_last == info[0]:
                terminalui.LOGGER.debug("Set cur_help_idx = %s", idx)
                self.cur_help_idx = idx
        terminalui.LOGGER.debug("beg_y=%d, beg_x=%d",
                                *list_item.window.getbegyx())

        self.center_win.activate_object(self.scroll_region)
        self.scroll_region.activate_object(self.cur_help_idx)

    def continue_action(self, dummy=None):
        '''Called when user presses F2 on help topics screen.
        Results in show being called again to display single file help
        of chosen topic.

        '''
        terminalui.LOGGER.debug("continue_action:%s",
                                self.scroll_region.active_object)
        cur_topic = self.scroll_region.active_object
        self.screen = self.help_info[cur_topic][0]
        terminalui.LOGGER.debug("continue_action self.screen=%s", self.screen)
        self.topics = False
        return self

    def display_help(self):
        '''Display the single file help screen'''
        # customize header
        help_header = "%s: %s"
        terminalui.LOGGER.debug("self.screen is =%s", self.screen)
        if self.screen in self.help_dict:
            help_header = help_header % (_("Help"),
                                         self.help_dict[self.screen][1])
            help_text = self.get_help_text(self.help_dict[self.screen][0])
        else:
            help_header = help_header % (_("Help"), _("Not Available"))
            help_text = _("Help for this screen is not available")

        self.main_win.set_header_text(help_header)

        help_text = convert_paragraph(help_text, self.win_size_x - 5)
        terminalui.LOGGER.debug("help_text #lines=%d, text is \n%s",
                      len(help_text), help_text)
        area = WindowArea(x_loc=0, y_loc=1,
                          scrollable_lines=(len(help_text) + 1))
        area.lines = self.win_size_y - 1
        area.columns = self.win_size_x
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        self.scroll_region.add_paragraph(help_text, start_x=(area.x_loc + 3))
        self.center_win.activate_object(self.scroll_region)

    def _show(self):
        '''Display the screen, either the single file help or help topics.'''

        terminalui.LOGGER.debug("in show self.screen=%s", self.screen)

        if (self.screen == self.__class__.__name__):
            terminalui.LOGGER.debug("setting self topics to true:")
            self.topics = True
        else:
            self.topics = False
            self.screen_last = self.screen
            terminalui.LOGGER.debug("setting self.screen_last to %s",
                                    self.screen_last)

        if self.topics:
            self.display_help_topics()
        else:
            self.display_help()

    def get_help_text(self, filename=None):
        '''
        Get the localized help text for the filename passed in.
        First check locid directory. If not there, strip off
        dot extension (fr_FR.UTF-8 becomes fr_FR). If not there,
        truncate to 2 chars (fr).  If not there, use C.
        '''
        if not filename:
            return ""

        help_file = None
        try:
            for locid in self._get_locids():
                full_path = filename % locid
                terminalui.LOGGER.debug("Accessing help file %s", full_path)
                if os.access(full_path, os.R_OK):
                    break
            terminalui.LOGGER.debug("Opening help file %s", full_path)
            with open(full_path) as help_file:
                help_text = help_file.read()
                terminalui.LOGGER.debug("Done reading help file %s", full_path)
        except IOError:
            terminalui.LOGGER.debug("Unable to open help file %s", full_path)
            help_text = _("Help for this screen is not available")
        return help_text

    def _get_locids(self):
        '''Generate a list of possible locales - folders to check for
        help screen text in. Used by get_help_text() in conjunction with
        a screen's indicated help text file path.

        The list will include one or more of:
            * The current locale (e.g., "en_US.UTF-8")
            * The current locale, stripped of encoding (e.g., "en_US")
            * The current language, stripped of locale (e.g., "en")
            * The default locale ("C")

        '''
        locale = self.locale
        locids = [locale]
        if "." in locale:
            locale = locale.split(".")[0]
            locids.append(locale)
        if len(locale) > 2:
            locids.append(locale[:2])
        locids.append("C")
        return locids

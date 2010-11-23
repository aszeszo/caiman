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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Display individual help screen or help topics screen 
'''

import curses
import locale
import logging
import os
import platform

from osol_install.text_install import _
from osol_install.text_install.action import Action
from osol_install.text_install.base_screen import BaseScreen
from osol_install.text_install.i18n import convert_paragraph, textwidth
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea


HELP_PATH = "/usr/share/text-install/help/"


class HelpScreen(BaseScreen):
    '''Show localized help file pertaining to last traversed screen or
    help topics list from which to choose a desired help topic.
    
    '''
    
    HELP_HEADER = _("Help Topics")
    HELP_INDEX = _("Help Index")
    INTRO = _("Select a topic and press Continue.")
    
    def __init__(self, main_win):
        super(HelpScreen, self).__init__(main_win)
        
        self.locale = locale.setlocale(locale.LC_MESSAGES, "")
        logging.debug("locale=%s", self.locale)
        
        self.screen = None
        self.screen_last = None
        self.help_info = []
        self.help_dict = None
        self.topics = False
        self.scroll_region = None
        self.cur_help_idx = 0
        self.is_x86 = (platform.processor() == "i386") 
        self.setup_help_data()
    
    def setup_help_data(self):
        '''Setup the help_dict and help_info structures
        
        help_dict contains:
            key: screen name 
            tuple:  (<helpfile_name>, <header for help screen>)
            tuple:  (<helpfile_name>, <header for help screen
                                       and help topics menu entry>)
        
        '''
        
        self.help_dict = \
            {
            "WelcomeScreen": ("welcome.txt",
                              _("Welcome and Navigation Instructions")),
            "DiskScreen": ("disks.txt", _("Disks")),
            "NetworkTypeScreen": ("network.txt", _("Network")),
            "NICSelect": ("network_manual.txt",
                          _("Manual Network Configuration")),
            "NICConfigure": ("network_manual.txt",
                             _("Manually Configure: NIC")),
            "TimeZone": ("timezone.txt", _("Time Zone")),
            "DateTimeScreen": ("date_time.txt", _("Date and Time")),
            "UserScreen": ("users.txt", _("Users")),
            "SummaryScreen": ("summary.txt", _("Installation Summary"))
            }
        
        # add x86 and SPARC specific help_dict entries
        if self.is_x86:
            self.help_dict["FDiskPart"] =  \
                ("x86_fdisk_partitions.txt", _("Fdisk Partitions"))
            self.help_dict["PartEditScreen"] = \
                ("x86_fdisk_partitions_select.txt", _("Select Partition"))
            self.help_dict["FDiskPart.slice"] = \
                ("x86_fdisk_slices.txt", _("Solaris Partition Slices"))
            self.help_dict["PartEditScreen.slice"] = \
                ("x86_fdisk_slices_select.txt", _("Select Slice"))
        else:
            self.help_dict["FDiskPart"] = \
                ("sparc_solaris_slices.txt", _("Solaris Slices"))
            self.help_dict["PartEditScreen"] = \
                ("sparc_solaris_slices_select.txt", _("Select Slice"))
        
        logging.debug("self.help_dict=%s", self.help_dict)
        
        # help_info contains tuples:
        #    (tuple of screen names, format of text) 
        
        self.help_info = []
        self.help_info.append((("WelcomeScreen",), "%s"))
        self.help_info.append((("DiskScreen",), "%s"))
        
        # add x86 and SPARC specific entries to self.help_info
        if self.is_x86: 
            self.help_info.append((("FDiskPart",), "  %s"))
            self.help_info.append((("PartEditScreen",), "    %s"))
            self.help_info.append((("FDiskPart.slice",), "    %s"))
            self.help_info.append((("PartEditScreen.slice",), "    %s"))
        else:
            self.help_info.append((("FDiskPart",), "  %s"))
            self.help_info.append((("PartEditScreen",), "  %s"))
        self.help_info.append((("NetworkTypeScreen",), "%s"))
        self.help_info.append((("NICSelect",), "  %s"))
        self.help_info.append((("NICConfigure",), "  %s"))
        self.help_info.append((("TimeZone",), "%s"))
        self.help_info.append((("DateTimeScreen",), "%s"))
        self.help_info.append((("UserScreen",), "%s"))
        self.help_info.append((("SummaryScreen",), "%s"))
        
        logging.debug("self.help_info=%s", self.help_info)
    
    def set_actions(self):
        '''Remove the continue key for help screen and Help key for
        help topics screen. Redirect F2_Continue to display the selected
        topic, when at the topics list
        
        '''
        
        logging.debug("in set_actions self.class_name=%s",
                      self.__class__.__name__)
        
        # change F6 description
        self.main_win.help_action.text = HelpScreen.HELP_INDEX
        
        # change continue to call continue_action, rather than
        # normal continue. Though we stay on the same screen,
        # we simulate the continue here by changing the screen text.
        #
        help_continue = Action(curses.KEY_F2, _("Continue"),
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
        
        self.main_win.set_header_text(HelpScreen.HELP_HEADER)
        y_loc = 1
        
        y_loc += self.center_win.add_paragraph(HelpScreen.INTRO, y_loc, 1,
                                               max_x=(self.win_size_x - 1))
        y_loc += 1
        
        area = WindowArea(scrollable_lines=(len(self.help_info)+1),
                          y_loc=y_loc, x_loc=0)
        logging.debug("lines=%s", len(self.help_dict))
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        
        # add the entries to the screen
        logging.debug("range=%s", len(self.help_info))
        for idx, info in enumerate(self.help_info):
            # create ListItem for each help topic
            topic_format = info[1]
            help_topic = self.get_help_topic(info[0])
            help_topic = topic_format % help_topic
            hilite = min(self.win_size_x, textwidth(help_topic) + 1)
            list_item = ListItem(WindowArea(1, hilite, idx, 0),
                                 window=self.scroll_region, text=help_topic)
            help_screens = info[0]
            logging.debug("help_screens=%s", list(help_screens))
            logging.debug("self.screen_last=%s", self.screen_last)
            if self.screen_last in help_screens:
                logging.debug("Set cur_help_idx = %s", idx)
                self.cur_help_idx = idx
        logging.debug("beg_y=%d, beg_x=%d", *list_item.window.getbegyx())
        
        self.center_win.activate_object(self.scroll_region)
        self.scroll_region.activate_object(self.cur_help_idx)
    
    def continue_action(self, dummy=None):
        '''Called when user preses F2 on help topics screen.
        Results in show being called again to display single file help
        of chosen topic.
         
        '''
        logging.debug("continue_action:%s", self.scroll_region.active_object)
        cur_topic = self.scroll_region.active_object
        self.screen = self.help_info[cur_topic][0][0]
        logging.debug("continue_action self.screen=%s", self.screen)
        self.topics = False
        return self
    
    def get_help_topic(self, name_classes=None):
        '''Get the help topic from the dictionary, given the help class
        tuple passed in. The single file help header in help_dict is
        also the entry used in the help topics menu.
        
        '''
        for key in self.help_dict.keys():
            if key in name_classes:
                return self.help_dict[key][1]
        return ""
    
    def display_help(self):
        '''Display the single file help screen'''
        # customize header
        help_header = "%s: %s"
        logging.debug("self.screen is =%s", self.screen)
        if self.screen in self.help_dict:
            help_header = help_header % (_("Help"),
                                         self.help_dict[self.screen][1])
            help_text = self.get_help_text(self.help_dict[self.screen][0])
        else:
            help_header = help_header % (_("Help"), _("Not Available"))
            help_text = _("Help for this screen is not available")
        
        self.main_win.set_header_text(help_header)
        
        help_text = convert_paragraph(help_text, self.win_size_x - 5)
        logging.debug("help_text #lines=%d, text is \n%s",
                      len(help_text), help_text)
        area = WindowArea(x_loc=0, y_loc=1,
                          scrollable_lines=(len(help_text)+1))
        area.lines = self.win_size_y - 1
        area.columns = self.win_size_x
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        self.scroll_region.add_paragraph(help_text, start_x=(area.x_loc + 3))
        self.center_win.activate_object(self.scroll_region)
    
    def _show(self):
        '''Display the screen, either the single file help or help topics.'''
        
        logging.debug("in show self.screen=%s", self.screen)
        
        if (self.screen is self.__class__.__name__):
            logging.debug("setting self topics to true:")
            self.topics = True
        else:
            self.topics = False
            self.screen_last = self.screen
            logging.debug("setting self.screen_last to %s", self.screen_last)
        
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
        if filename is None:
            return ("")
        
        help_file = None
        try:
            locid = self.locale
            path = "%s%s/%s"
            full_path = path % (HELP_PATH, locid, filename)
            logging.debug("Accessing help file %s", full_path)
            if (not os.access(full_path, os.R_OK)): 
                if (locid.find(".") > 0):
                    locid = locid.split(".")[0]
                    full_path = path % (HELP_PATH, locid, filename)
                    logging.debug("Accessing help file %s", full_path)
                    if (not os.access(full_path, os.R_OK)): 
                        if (len(locid) > 1):
                            locid = locid[:2]
                            full_path = path % (HELP_PATH, locid, filename)
                            logging.debug("Accessing help file %s", full_path)
                            if (not os.access(full_path, os.R_OK)):
                                locid = "C"
                                full_path = path % (HELP_PATH, locid, filename)
            logging.debug("Opening help file %s", full_path)
            help_file = open(full_path, 'r')
        except IOError:
            logging.debug("Unable to open help file %s", full_path)
            help_text = _("Help for this screen is not available")
        else:
            help_text = help_file.read()
            logging.debug("Done reading help file %s", full_path)
        if help_file:
            help_file.close()
        return help_text


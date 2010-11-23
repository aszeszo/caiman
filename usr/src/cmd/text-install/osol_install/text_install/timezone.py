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
Time Zone selection screen - used for all three TimeZone screens
'''

import curses
import logging

from osol_install.libzoneinfo import get_tz_info, tz_isvalid
from osol_install.profile.system_info import SystemInfo
from osol_install.text_install import _, LOG_LEVEL_INPUT
from osol_install.text_install.base_screen import BaseScreen, SkipException
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.scroll_window import ScrollWindow
from osol_install.text_install.window_area import WindowArea


class TimeZone(BaseScreen):
    '''Allow user to select timezone based on already selected
    continent and country.
    
    '''
    
    UTC_TEXT = _("UTC/GMT")
    SCROLL_SIZE = 2
    BORDER_WIDTH = (0, 3)
    REGIONS = "regions"
    LOCATIONS = "locations"
    TIMEZONE = "timezone"
    
    def __init__(self, main_win, screen=None):
        super(TimeZone, self).__init__(main_win)
        self.sys_info = None
        if screen is None:
            self.screen = TimeZone.TIMEZONE
        else:
            self.screen = screen
        self.tz_tuples = None
        self.tz_list = None
        self.cur_timezone_idx = 0
        self.cur_timezone_parent = None
        self.last_timezone_parent = None
        self.cur_continent = None
        self.cur_country = None
        self.scroll_region = None
        self.last_country = None
        self.last_continent = None
        if self.screen == TimeZone.TIMEZONE:
            self.header_text = _("Time Zone")
            self.intro = _("Select your time zone.")
            self.title = _("Time Zones")
        elif self.screen == TimeZone.LOCATIONS:
            self.header_text = _("Time Zone: Locations")
            self.intro = _("Select the location that contains your time zone.")
            self.title = _("Locations")
        else:
            self.header_text = _("Time Zone: Regions")
            self.intro = _("Select the region that contains your time zone.")
            self.title = _("Regions")
    
    def _show(self):
        '''Create the list of time zones'''
        logging.debug("self.screen %s", self.screen)
        
        if self.install_profile.system is None:
            self.install_profile.system = SystemInfo()
        self.sys_info = self.install_profile.system
        
        self.cur_country = self.sys_info.tz_country
        self.cur_continent = self.sys_info.tz_region
        
        if self.cur_continent == SystemInfo.UTC and self.screen != "regions":
            raise SkipException
        
        self.center_win.border_size = TimeZone.BORDER_WIDTH
        
        if self.screen == TimeZone.LOCATIONS:
            self.cur_timezone_parent = self.cur_continent
        elif self.screen == TimeZone.TIMEZONE:
            self.cur_timezone_parent = self.cur_country
        
        logging.debug("cur_continent %s, cur_country %s",
                      self.cur_continent, self.cur_country)
        
        y_loc = 1
        
        y_loc += self.center_win.add_paragraph(self.intro, y_loc)
        
        y_loc += 1
        menu_item_max_width =  self.win_size_x - TimeZone.SCROLL_SIZE
        self.center_win.add_text(self.title, y_loc, TimeZone.SCROLL_SIZE)
        y_loc += 1
        self.center_win.window.hline(y_loc, 3, curses.ACS_HLINE, 40)
        
        y_loc += 1
        
        
        tz_list = self.get_timezones(self.cur_continent, self.cur_country)
        
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=len(tz_list)+1)
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        logging.debug("area.lines=%d, area.columns=%d",
                      area.lines, area.columns)
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        
        utc = 0
        if self.screen == TimeZone.REGIONS:
            utc_area = WindowArea(1, len(TimeZone.UTC_TEXT) + 1, 0,
                                  TimeZone.SCROLL_SIZE)
            utc_item = ListItem(utc_area, window=self.scroll_region,
                                text=TimeZone.UTC_TEXT,
                                data_obj=SystemInfo.UTC)
            utc = 1
        
        # add the entries to the screen
        for idx, timezone in enumerate(tz_list):
            logging.log(LOG_LEVEL_INPUT, "tz idx = %i name= %s",
                        idx, tz_list[idx])
            hilite = min(menu_item_max_width, len(timezone) + 1)
            win_area = WindowArea(1, hilite, idx+utc, TimeZone.SCROLL_SIZE)
            list_item = ListItem(win_area, window=self.scroll_region,
                                 text=timezone, data_obj=timezone)
            y_loc += 1
        
        self.main_win.do_update()
        self.center_win.activate_object(self.scroll_region)
        logging.debug("self.cur_timezone_idx=%s", self.cur_timezone_idx)
        self.scroll_region.activate_object_force(self.cur_timezone_idx,
                                                 force_to_top=True)
    
    def get_timezones(self, continent, country_code):
        '''Get the timezone info, a list of tuples, each with:
            [0] timezone name
            [1] timezone name descriptive
            [2] localized timezone name
        '''
        
        logging.debug("get_timezones continent=%s", continent)
        logging.debug("get_timezones country_code=%s", country_code)
        logging.debug("get_timezones self.cur_timezone_parent=%s,"
                      " self.last_timezone_parent=%s",
                      self.cur_timezone_parent, self.last_timezone_parent)

        if (self.tz_list is None or self.cur_timezone_parent !=
            self.last_timezone_parent):
            self.tz_list = []
            self.cur_timezone_idx = 0
            
            # pass get_tz_info the correct parameters:
            #   none - to get regions/continents
            #   continent  ("America") - to get countries
            #   continent and country code ("America", "US")  - to get the 
            #      timezones
            if self.screen == TimeZone.REGIONS:
                self.tz_tuples = get_tz_info()
            elif self.screen == TimeZone.LOCATIONS:
                self.tz_tuples = get_tz_info(continent)
            else:
                self.tz_tuples = get_tz_info(continent, country_code)
            
            # get name to display. First choice is localized name, then
            # descriptive name, then plain name
            logging.debug("number of timezones=%i", len(self.tz_tuples))
            for item in self.tz_tuples:
                if item[2]:
                    logging.debug("tz2 = %s", item[2])
                    self.tz_list.append(item[2])
                elif item[1]:
                    logging.debug("tz1 = %s", item[1])
                    self.tz_list.append(item[1])
                else:
                    logging.debug("tz0 = %s", item[0])
                    self.tz_list.append(item[0])

        return self.tz_list


    def on_change_screen(self):
        '''Save the chosen timezone's index and name when leaving the screen'''
        self.cur_timezone_idx = self.scroll_region.active_object
        idx = self.cur_timezone_idx
        self.last_timezone_parent = self.cur_timezone_parent
        if self.screen == TimeZone.REGIONS:
            if (self.scroll_region.get_active_object().data_obj ==
                SystemInfo.UTC):
                self.sys_info.tz_region_idx = 0
                self.sys_info.tz_region = SystemInfo.UTC
                self.sys_info.tz_country = SystemInfo.UTC
                self.sys_info.tz_timezone = SystemInfo.UTC
                self.sys_info.tz_display_name = TimeZone.UTC_TEXT
            else:
                self.sys_info.tz_region_idx = idx
                self.sys_info.tz_region = self.tz_tuples[idx-1][0]
            logging.debug("on_change_screen sys_info.tz_region: %s",
                          self.sys_info.tz_region)
        elif self.screen == TimeZone.LOCATIONS:
            self.sys_info.tz_country_idx = idx
            self.sys_info.tz_country = self.tz_tuples[idx][0]
            self.last_continent = self.cur_continent
            logging.debug("on_change_screen sys_info.tz_country: %s",
                          self.sys_info.tz_country)
            logging.debug("on_change_screen sys_info.tz_country_idx: %s",
                          self.sys_info.tz_country_idx)
        else:
            self.sys_info.tz_timezone_idx = idx
            self.sys_info.tz_timezone = self.tz_tuples[idx][0]
            selected_tz = self.scroll_region.get_active_object().data_obj
            self.sys_info.tz_display_name = selected_tz
            self.last_country = self.cur_country
            self.cur_timezone_idx = self.scroll_region.active_object
            logging.debug("on_change_screen self.sys_info.tz_timezone: %s",
                          self.sys_info.tz_timezone)
            logging.debug("on_change_screen self.sys_info.tz_timezone_idx:%s",
                          self.sys_info.tz_timezone_idx)

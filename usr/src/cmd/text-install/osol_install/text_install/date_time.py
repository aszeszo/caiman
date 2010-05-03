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
Gather Date and Time information from the user
'''

import calendar
import datetime
import logging
import os

from osol_install.text_install import _, LOG_LEVEL_INPUT
from osol_install.text_install.base_screen import BaseScreen, UIMessage
from osol_install.text_install.edit_field import EditField
from osol_install.text_install.error_window import ErrorWindow
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.window_area import WindowArea


class DateTimeScreen(BaseScreen):
    '''
    Allow user to select year, month, day, hour, and minute to be
    used to set system clock.
    '''
    
    HEADER_TEXT = _("Date and Time")
    
    YEAR_TEXT = _("Year:")
    MONTH_TEXT = _("Month:")
    DAY_TEXT = _("Day:")
    HOUR_TEXT = _("Hour:")
    MINUTE_TEXT = _("Minute:")
    YEAR_FORMAT = _("(YYYY)")
    
    PARAGRAPH = _("Edit the date and time as necessary.\n"
                  "The time is in 24 hour format.")
    
    YEAR_DIGITS = 4
    TWO_DIGITS = 2
    YEAR_LEN = len(YEAR_TEXT)
    MONTH_LEN = len(MONTH_TEXT)
    DAY_LEN = len(DAY_TEXT)
    HOUR_LEN = len(HOUR_TEXT)
    MINUTE_LEN = len(MINUTE_TEXT)
    MAX_LEN = max(YEAR_LEN, MONTH_LEN, DAY_LEN, HOUR_LEN, MINUTE_LEN) + 1
    
    ITEM_OFFSET = 2
    
    def __init__(self, main_win):
        super(DateTimeScreen, self).__init__(main_win)
        
        year_edit_width = DateTimeScreen.YEAR_DIGITS + 1
        list_width = DateTimeScreen.MAX_LEN + year_edit_width
        self.list_area = WindowArea(1, list_width, 0,
                                    DateTimeScreen.ITEM_OFFSET)
        self.year_edit_area = WindowArea(1, year_edit_width, 0,
                                         DateTimeScreen.MAX_LEN + 1)
        other_edit_width = DateTimeScreen.TWO_DIGITS + 1
        other_edit_offset = (DateTimeScreen.MAX_LEN +
                             (DateTimeScreen.YEAR_DIGITS -
                              DateTimeScreen.TWO_DIGITS) + 1)
        self.edit_area = WindowArea(1, other_edit_width, 0, other_edit_offset)
        self.info_offset = (DateTimeScreen.ITEM_OFFSET +
                            self.list_area.columns + 1)
        self.info_width = len(DateTimeScreen.YEAR_FORMAT)
        err_offset = self.info_offset + self.info_width + 2
        err_width = self.win_size_x - err_offset
        self.err_area = WindowArea(1, err_width, 0, err_offset)
        
        self.year_edit = None
        self.year_err = None
        self.year_list = None
        self.month_edit = None
        self.month_err = None
        self.month_list = None
        self.day_edit = None
        self.day_err = None
        self.day_list = None
        self.hour_edit = None
        self.hour_err = None
        self.hour_list = None
        self.minute_edit = None
        self.minute_err = None
        self.minute_list = None
        self.year_is_valid = True
        self.month_is_valid = True
        self.date_range_loc = None
        self.saved_year = None
        self.saved_month = None
        self.saved_day = None
        self.saved_hour = None
        self.saved_minute = None
        self.saved_days_in_month = None
    
    def _show(self):
        '''
        Prepare the editable fields for day, month, year, hour and minute
        
        '''
        y_loc = 1
        
        y_loc += self.center_win.add_paragraph(DateTimeScreen.PARAGRAPH, y_loc)
        
        
        os.environ["TZ"] = self.install_profile.system.tz_timezone
        now = datetime.datetime.now()
        logging.debug("now year month day hour minute: %s %s %s %s %s",
                      now.year, now.month, now.day, now.hour, now.minute)
        
        # Only update saved values if this is first time on screen or
        # if we have saved offset in profile (F2, return to screen)
        #
        update_vals = False
        if self.saved_year is None:
            update_vals = True
            showtime = now
        elif self.install_profile.system.time_offset != 0:
            showtime = now +  self.install_profile.system.time_offset
            update_vals = True
            self.install_profile.system.time_offset = 0
        
        if update_vals:
            self.saved_year = str(showtime.year)
            self.saved_month = str(showtime.month)
            self.saved_day = str(showtime.day)
            self.saved_hour = str(showtime.hour)
            self.saved_minute = str(showtime.minute)
            self.saved_days_in_month = calendar.monthrange(showtime.year,
                                                           showtime.month)[1]
            
        logging.debug("starting year month day hour minute:_%s_%s_%s_%s_%s",
                      self.saved_year, self.saved_month, self.saved_day,
                      self.saved_hour, self.saved_minute)
        logging.debug("starting days_in_month: %s", self.saved_days_in_month)
        
        
        y_loc += 1
        self.err_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        
        self.year_err = ErrorWindow(self.err_area, window=self.center_win,
                                    centered=False)
        self.year_list = ListItem(self.list_area,
                                  window=self.center_win,
                                  text=DateTimeScreen.YEAR_TEXT)
        self.year_edit = EditField(self.year_edit_area, window=self.year_list,
                                   validate=year_valid,
                                   error_win=self.year_err,
                                   on_exit=year_on_exit,
                                   text=self.saved_year)
        self.year_edit.clear_on_enter = True
        
        self.center_win.add_text(DateTimeScreen.YEAR_FORMAT, y_loc,
                                 self.info_offset)
        
        y_loc += 1
        self.err_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        
        self.month_err = ErrorWindow(self.err_area, window=self.center_win,
                                    centered=False)
        self.month_list = ListItem(self.list_area, window=self.center_win,
                                   text=DateTimeScreen.MONTH_TEXT)
        self.month_edit = EditField(self.edit_area, window=self.month_list,
                                    validate=month_valid,
                                    error_win=self.month_err,
                                    on_exit=month_on_exit,
                                    text=self.saved_month,
                                    numeric_pad="0")
        self.month_edit.clear_on_enter = True
        self.month_edit.right_justify = True
        self.center_win.add_text("(1-12)", y_loc, self.info_offset)
        
        y_loc += 1
        self.err_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        
        self.day_err = ErrorWindow(self.err_area, window=self.center_win,
                                   centered=False)
        self.day_list = ListItem(self.list_area,
                                 window=self.center_win,
                                 text=DateTimeScreen.DAY_TEXT)
        self.day_edit = EditField(self.edit_area, window=self.day_list,
                                  validate=day_valid,
                                  error_win=self.day_err,
                                  on_exit=day_on_exit,
                                  text=self.saved_day,
                                  numeric_pad="0")
        self.day_edit.clear_on_enter = True
        self.day_edit.right_justify = True
        
        self.month_edit.validate_kwargs["date_time"] = self
        self.month_edit.validate_kwargs["year_edit"] = self.year_edit
        self.month_edit.validate_kwargs["day_edit"] = self.day_edit
        
        self.year_edit.validate_kwargs["date_time"] = self
        self.year_edit.validate_kwargs["month_edit"] = self.month_edit
        self.year_edit.validate_kwargs["day_edit"] = self.day_edit
        
        self.day_edit.validate_kwargs["date_time"] = self
        self.day_edit.validate_kwargs["year_edit"] = self.year_edit
        self.day_edit.validate_kwargs["month_edit"] = self.month_edit
        self.date_range_loc = (y_loc, self.info_offset)
        self.update_day_range(self.saved_days_in_month)
        
        y_loc += 1
        self.err_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        
        self.hour_err = ErrorWindow(self.err_area, window=self.center_win,
                                    centered=False)
        self.hour_list = ListItem(self.list_area, window=self.center_win,
                                  text=DateTimeScreen.HOUR_TEXT)
        self.hour_edit = EditField(self.edit_area, window=self.hour_list,
                                   validate=hour_valid,
                                   error_win=self.hour_err,
                                   on_exit=hour_on_exit,
                                   text=self.saved_hour,
                                   numeric_pad="0")
        self.hour_edit.clear_on_enter = True
        self.hour_edit.right_justify = True
        self.center_win.add_text("(0-23)", y_loc, self.info_offset)
        
        y_loc += 1
        self.err_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        
        self.minute_err = ErrorWindow(self.err_area, window=self.center_win,
                                      centered=False)
        self.minute_list = ListItem(self.list_area, window=self.center_win,
                                    text=DateTimeScreen.MINUTE_TEXT)
        self.minute_edit = EditField(self.edit_area,
                                     window=self.minute_list,
                                     validate=minute_valid,
                                     error_win=self.minute_err,
                                     on_exit=minute_on_exit,
                                     text=self.saved_minute,
                                     numeric_pad="0")
        self.minute_edit.clear_on_enter = True
        self.minute_edit.right_justify = True
        self.center_win.add_text("(0-59)", y_loc, self.info_offset)
        
        self.main_win.do_update()
        self.center_win.activate_object(self.year_list)
    
    def validate(self):
        '''Verify each of the edit fields'''
        year_value = self.year_edit.get_text()
        month_value = self.month_edit.get_text()
        day_value = self.day_edit.get_text()
        hour_value = self.hour_edit.get_text()
        minute_value = self.minute_edit.get_text()
        logging.debug("year_value=%s", year_value)
        logging.debug("month_value=%s", month_value)
        logging.debug("day_value=%s", day_value)
        logging.debug("hour_value=%s", hour_value)
        logging.debug("minute_value=%s", minute_value)
        had_err = False
        if not self.year_edit.run_on_exit(): 
            had_err = True
        if not self.month_edit.run_on_exit(): 
            had_err = True
        if not self.day_edit.run_on_exit(): 
            had_err = True
        if not self.hour_edit.run_on_exit(): 
            had_err = True
        if not self.minute_edit.run_on_exit(): 
            had_err = True
        if had_err:
            raise UIMessage, _("Invalid date/time. See errors above.")

    def update_day_range(self, maxday=31):
        '''
        Update the day range displayed. The max number of days can vary
        depending on the month, so calling functions can update appropriately.
        
        '''
        self.center_win.add_text("(1-%d)" % maxday,
                                 self.date_range_loc[0],
                                 self.date_range_loc[1],
                                 self.win_size_x - 3)
        self.saved_days_in_month = maxday


    def on_change_screen(self):
        '''Save current user input for return to screen'''
        self.saved_year = self.year_edit.get_text()
        self.saved_month = self.month_edit.get_text()
        self.saved_day = self.day_edit.get_text()
        self.saved_hour = self.hour_edit.get_text()
        self.saved_minute = self.minute_edit.get_text()

    def on_continue(self):
        '''Save time offset to profile'''
        saved_time = datetime.datetime(int(self.year_edit.get_text()),
                                       int(self.month_edit.get_text()),
                                       int(self.day_edit.get_text()),
                                       int(self.hour_edit.get_text()),
                                       int(self.minute_edit.get_text()))
        userdelta = saved_time - datetime.datetime.now()
        logging.debug("delta time=%s", userdelta)
        self.install_profile.system.time_offset = userdelta
        install_datetime = datetime.datetime.now() + userdelta
        logging.debug("date command would be: /usr/bin/date %s",
                      install_datetime.strftime("%m%d%H%M%y"))

def get_days_in_month(month_edit, year_edit, date_time):
    '''
    Get the number of days in the month. Assumes non-None
    month and year field. Returns 31 if month field is zero
    or not valid and 28 if Feb, but year not valid.
    '''
    if not date_time.month_is_valid:
        logging.debug("get_days_in_month returning 31")
        return(31)
    
    month_num = int(month_edit.get_text())
    if (month_num == 0):
        return(31)

    # if month set to Feb, check for leap year
    if (month_num == 2):
        if not date_time.year_is_valid:
            logging.debug("get_days_in_month returning 28")
            return(28)
        else:
            cur_year =  year_edit.get_text()
            logging.debug("cur_year %s", cur_year)
            if len(cur_year) == 4:
                return (calendar.monthrange(int(cur_year), 2)[1])

    now = datetime.datetime.now()
    return (calendar.monthrange(now.year, month_num)[1])


def check_day_range(month_edit, day_edit, year_edit, date_time):
    '''
    Update the day range max with number of days in month. If days in 
    day_edit field is greater than number of days in month, modify value
    in day_edit field to number days in month.
    '''
    logging.debug('checking day range')
    days_in_month = get_days_in_month(month_edit, year_edit, date_time)
    logging.debug('%s days in month', days_in_month)
    date_time.update_day_range(days_in_month)
    
    if not day_edit.get_text():
        return
    cur_day = int(day_edit.get_text())
    if cur_day > days_in_month:
        day_edit.textbox.do_command(EditField.CMD_MV_BOL) 
        day_edit.set_text(str(days_in_month))
        logging.debug('updating day to %s', days_in_month )


def year_valid(year_edit, month_edit=None, day_edit=None,
               date_time=None):
    '''Check validity of year as each char entered'''
    if date_time:
        date_time.year_is_valid = False
    year_str = year_edit.get_text()
    if not year_str:
        return True
    now = datetime.datetime.now()
    logging.log(LOG_LEVEL_INPUT, "validating year, text=%s=", year_str)
    if not year_str.isdigit():
        raise UIMessage, _("Year must be numeric")
    if year_str[0] != now.strftime("%Y")[0]:
        logging.debug("year doesn't start with 2, text=%s", year_str)
        raise UIMessage, _("Year out of range")
    if len(year_str) > 1 and year_str[1] != now.strftime("%Y")[1]:
        logging.debug("year out of range=%s", year_str)
        raise UIMessage, _("Year out of range")
    if date_time:
        date_time.year_is_valid = True
        if len(year_str) == 4:
            check_day_range(month_edit, day_edit, year_edit, date_time)
    return True


def year_on_exit(year_edit):
    '''Check year when exiting field'''
    year_str = year_edit.get_text()
    logging.debug("year_on_exit, =%s=", year_str)
    year_valid(year_edit)
    if (len(year_str) != 4):
        logging.debug("on exit year out of range=%s", input)
        raise UIMessage, _("Year out of range")
    return True


def month_valid(month_edit, day_edit=None, year_edit=None, date_time=None):
    '''Check validity of month as each char entered'''
    if date_time:
        date_time.month_is_valid = False
    month_str = month_edit.get_text()
    logging.log(LOG_LEVEL_INPUT, "validating month, text=%s=", month_str)
    if not month_str:
        return True
    if not month_str.isdigit():
        raise UIMessage, _("Month must be numeric")
    logging.debug("len = %s, text=%s ", len(month_str), month_str)
    if len(month_str) >= 2:
        if (int(month_str) > 12 or int(month_str) == 0):
            logging.log(LOG_LEVEL_INPUT, "month out of range, =%s", month_str)
            raise UIMessage, _("Month out of range")
    if date_time:
        date_time.month_is_valid = True
        if int(month_str) > 0:
            check_day_range(month_edit, day_edit, year_edit, date_time)
    return True


def month_on_exit(month_edit):
    '''Check month when exiting field'''
    month_str = month_edit.get_text() 
    logging.debug("month_on_exit, =%s=", month_str)
    month_valid(month_edit)
    if (len(month_str) == 0 or int(month_str) == 0):
        logging.debug("on exit month out of range=%s", month_str)
        raise UIMessage, _("Month out of range")
    return True


def day_valid(day_edit, month_edit=None, year_edit=None, date_time=None):
    '''Check validity of day as each char entered'''
    day_str = day_edit.get_text()
    logging.log(LOG_LEVEL_INPUT, "validating day, text=%s=", day_str)
    if not day_str:
        return True
    if not day_str.isdigit():
        raise UIMessage, _("Day must be numeric")
    logging.log(LOG_LEVEL_INPUT, "len = %s, text=%s ", len(day_str), day_str)
    
    # When screen first comes up, there is no month/year_edit
    if (month_edit is None or year_edit is None):
        return True
    
    days_in_month = get_days_in_month(month_edit, year_edit, date_time)
    if (len(day_str) >= 2):
        if (int(day_str) > days_in_month or int(day_str) == 0):
            logging.debug("day out of range, =%s", day_str)
            raise UIMessage, _("Day out of range")
    return True


def day_on_exit(day_edit):
    '''Check day when exiting field'''
    day_str = day_edit.get_text()
    logging.debug("day_on_exit, =%s=", day_str)
    day_valid(day_edit)
    if (len(day_str) == 0 or int(day_str) == 0):
        logging.debug("on exit day out of range=%s", day_str)
        raise UIMessage, _("Day out of range")
    return True


def hour_valid(hour_edit): 
    '''Check validity of hour as each char entered'''
    hour_str = hour_edit.get_text()
    logging.log(LOG_LEVEL_INPUT, "validating hour, text=%s=", hour_str)
    if hour_str and not hour_str.isdigit():
        raise UIMessage, _("Hour must be numeric")
    if len(hour_str) >= 2 and (int(hour_str) > 23):
        logging.debug("hour out of range, =%s", hour_str)
        raise UIMessage, _("Hour out of range")
    return True


def hour_on_exit(hour_edit):
    '''Check hour when exiting field'''
    hour_str = hour_edit.get_text()
    logging.debug("hour_on_exit, =%s=", hour_str)
    if not hour_str:
        raise UIMessage, _("Hour out of range")
    hour_valid(hour_edit)
    return True


def minute_valid(minute_edit):
    '''Check validity of minute as each char entered'''
    minute_str = minute_edit.get_text()
    logging.log(LOG_LEVEL_INPUT, "validating minute, text=%s=", minute_str)
    if minute_str and not minute_str.isdigit():
        raise UIMessage, _("Minute must be numeric")
    if len(minute_str) >= 2 and (int(minute_str) > 59):
        raise UIMessage, _("Minute out of range")
    return True


def minute_on_exit(minute_edit):
    '''Check minute when exiting field'''
    minute_str = minute_edit.get_text()
    logging.debug("minute_on_exit, =%s=", minute_str)
    if not minute_str:
        raise UIMessage, _("Minute out of range")
    minute_valid(minute_edit)
    return True

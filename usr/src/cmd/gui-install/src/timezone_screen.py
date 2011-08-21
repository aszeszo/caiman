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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Disk Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

from datetime import datetime
import logging

import gobject
import gtk

from solaris_install import Popen, CalledProcessError
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.gui_install_common import modal_dialog, \
    GLADE_ERROR_MSG
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.gui_install.timezone import Timezone
from solaris_install.logger import INSTALL_LOGGER_NAME

DATE_CMD = "/usr/bin/date"
LOGGER = None


class TimeZoneScreen(BaseScreen):
    def __init__(self, builder):
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(TimeZoneScreen, self).__init__(builder)
        self.name = "TimeZone Screen"

        # Widgets from Glade XML file
        self.outervbox = self.builder.get_object("outervbox")
        self.yearspinner = self.builder.get_object("yearspinner")
        self.monthspinner = self.builder.get_object("monthspinner")
        self.dayspinner = self.builder.get_object("dayspinner")
        self.hourspinner = self.builder.get_object("hourspinner")
        self.minutespinner = self.builder.get_object("minutespinner")
        self.ampmcombobox = self.builder.get_object("ampmcombobox")
        self.datelabel = self.builder.get_object("datelabel")
        self.timelabel = self.builder.get_object("timelabel")

        if None in [self.outervbox, self.yearspinner, self.monthspinner,
            self.dayspinner, self.hourspinner, self.minutespinner,
            self.ampmcombobox, self.datelabel, self.timelabel]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        # Custom Timer widget, created on first entry to screen
        self.timezone = None

        self.timer = None
        self.currentmin = None
        self.previndex_ampm = 2

    def enter(self):
        toplevel = self.set_main_window_content("datetimezonetoplevel")

        self.activate_stage_label("timezonestagelabel")
        self.set_titles(_("Time Zone, Date and Time"),
            _("Select a city near you on the map or set your time " \
                "zone below,then set the date and time."),
            None)
        self.set_back_next(back_sensitive=True, next_sensitive=True)

        if self.timezone is None:
            # First time initialization
            self.ui_init()

        # Each time we enter the screen we set the time values to the
        # current time, even if the user previously changed them
        self.set_current_date_and_time()

        self.timezone.ctnt_combo.grab_focus()

        toplevel.show_all()

        return False

    def go_back(self):
        pass

    def validate(self):
        (continent, country, timezone) = self.timezone.get_selected_tz()
        if continent is None or country is None or timezone is None:
            self.error_dialog()
            raise NotOkToProceedError()

        if not self.set_system_clock():
            # Not a fatal error
            LOGGER.warn("WARNING: Failed to set TZ and/or date/time")

        # Save the user-entered details to the DOC
        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache
        profile = doc.persistent.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        if profile is not None:
            profile.set_timezone_data(continent.name,
                country.name, timezone.tz_name)

    def ui_init(self):
        self.timezone = Timezone(self.builder, self)
        self.timezone.show()
        self.outervbox.pack_start(self.timezone,
            expand=False, fill=False, padding=0)
        self.outervbox.reorder_child(self.timezone, 0)

        self.yearspinner.set_alignment(1.0)
        self.monthspinner.set_alignment(1.0)
        self.dayspinner.set_alignment(1.0)
        self.hourspinner.set_alignment(1.0)
        self.minutespinner.set_alignment(1.0)
        self.monthspinner.set_width_chars(2)
        self.dayspinner.set_width_chars(2)
        self.hourspinner.set_width_chars(2)
        self.minutespinner.set_width_chars(2)

        sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_BOTH)
        sizegroup.add_widget(self.timezone.ctnt_label)
        sizegroup.add_widget(self.timezone.ctry_label)
        sizegroup.add_widget(self.timezone.tz_label)
        sizegroup.add_widget(self.datelabel)
        sizegroup.add_widget(self.timelabel)

        # Use 24 hour clock initially
        self.ampmcombobox.set_active(self.previndex_ampm)

        # Set up signal handlers
        gobject.GObject.connect(self.monthspinner,
            "insert_text", self.datetimezone_spinners_filter)
        gobject.GObject.connect(self.dayspinner,
            "insert_text", self.datetimezone_spinners_filter)
        gobject.GObject.connect(self.hourspinner,
            "insert_text", self.datetimezone_spinners_filter)
        gobject.GObject.connect(self.minutespinner,
            "insert_text", self.datetimezone_spinners_filter)

        gobject.GObject.connect(self.monthspinner,
            "focus_out_event", self.datetimezone_spinners_focus_out)
        gobject.GObject.connect(self.dayspinner,
            "focus_out_event", self.datetimezone_spinners_focus_out)
        gobject.GObject.connect(self.minutespinner,
            "focus_out_event", self.datetimezone_spinners_focus_out)

        self.timer = gobject.timeout_add(1000, self.update_clock)

    def on_yearspinner_value_changed(self, widget, user_data=None):
        # Leap year handling
        year = widget.get_value_as_int()
        month = self.monthspinner.get_value_as_int()

        if month == 2:
            daysinmonth = self.get_days_in_month(month, year)
            day = self.dayspinner.get_value_as_int()
            self.dayspinner.set_range(1, daysinmonth)

            if day > daysinmonth:
                self.dayspinner.set_value(daysinmonth)
            else:
                self.dayspinner.set_value(day)

    def on_monthspinner_value_changed(self, widget, user_data=None):
        # day range handling
        year = self.yearspinner.get_value_as_int()
        month = widget.get_value_as_int()
        day = self.dayspinner.get_value_as_int()

        daysinmonth = self.get_days_in_month(month, year)
        self.dayspinner.set_range(1, daysinmonth)

        if day > daysinmonth:
            self.dayspinner.set_value(daysinmonth)
        else:
            self.dayspinner.set_value(day)

    def on_dayspinner_value_changed(self, widget, user_data=None):
        # no special handling needed
        pass

    def on_hourspinner_value_changed(self, widget, user_data=None):
        # no special handling needed
        pass

    def on_minutespinner_value_changed(self, widget, user_data=None):
        # no special handling needed
        pass

    def on_ampmcombobox_changed(self, widget, user_data=None):
        # handle switching between 24hr and AM/PM clocks

        oldhours = self.hourspinner.get_value_as_int()
        index = widget.get_active()
        newhours = 0

        if index == 2:
            # Switching to 24 hour mode
            self.hourspinner.set_range(0, 23)
            if self.previndex_ampm == 0:
                # AM -> 24hr
                # 12:00am becomes 00:00
                if oldhours == 12:
                    newhours = 0
                else:
                    newhours = oldhours
            elif self.previndex_ampm == 1:
                # PM -> 24hr
                # 01:00pm becomes 13:00, etc
                if oldhours == 12:
                    newhours = 12
                elif oldhours < 12:
                    newhours = oldhours + 12
        elif index == 1:
            # Switching to PM
            if self.previndex_ampm == 2:
                # 24hr -> PM
                self.hourspinner.set_range(1, 12)
                if (oldhours % 12) == 0:
                    newhours = 12
                elif oldhours > 12:
                    newhours = oldhours - 12
                else:
                    newhours = oldhours
            elif self.previndex_ampm == 0:
                # AM -> PM
                newhours = oldhours
        elif index == 0:
            # Switching to AM
            if self.previndex_ampm == 2:
                # 24hr -> AM
                self.hourspinner.set_range(1, 12)
                if (oldhours % 12) == 0:
                    newhours = 12
                elif oldhours < 12:
                    newhours = oldhours
                elif oldhours > 12:
                    newhours = oldhours - 12
            elif self.previndex_ampm == 1:
                # PM -> AM
                newhours = oldhours

        self.hourspinner.set_value(newhours)
        self.previndex_ampm = index

    def datetimezone_spinners_filter(self, widget, newtext, length,
        position, user_data=None):
        # Gtk SpinButtons already seems to perform all the
        # required validation/prevention here
        pass

    def datetimezone_spinners_focus_out(self, widget, event, user_data=None):
        # no special handling needed
        pass

    def set_current_date_and_time(self):
        currenttime = datetime.now()
        # Year values don't need zero-padding.  The other values do.
        self.yearspinner.set_value(currenttime.year)
        self.monthspinner.set_value(currenttime.month)
        self.monthspinner.set_text("%02d" % currenttime.month)
        self.dayspinner.set_value(currenttime.day)
        self.dayspinner.set_text("%02d" % currenttime.day)
        self.hourspinner.set_value(currenttime.hour)
        self.hourspinner.set_text("%02d" % currenttime.hour)
        self.minutespinner.set_value(currenttime.minute)
        self.minutespinner.set_text("%02d" % currenttime.minute)

    def set_system_clock(self):
        '''
        Set the system date/time, based on the values
        entered on the screen.
        '''

        # Set system time as per the entered date/time values
        year = self.yearspinner.get_value()
        month = self.monthspinner.get_value()
        day = self.dayspinner.get_value()
        hour = self.hourspinner.get_value()
        minute = self.minutespinner.get_value()
        # Preserve the current seconds values
        second = datetime.now().second

        newdatetime = "%02d%02d%02d%02d%04d.%02d" % \
            (month, day, hour, minute, year, second)
        cmd = [DATE_CMD, newdatetime]
        LOGGER.info("Running command: %s" % cmd)
        try:
            p = Popen.check_call(cmd, stdout=Popen.STORE)
        except CalledProcessError, err:
            LOGGER.error("ERROR: [%s] [%s]" % (cmd, err))
            return False

        return True

    def update_clock(self):
        '''
        This timeout is called every second, in order to keep the
        time widgets (minute and hour) up-to-date.

        If the user does not modify the time values, then they will
        update themselves every minute that the user stays on this
        screen.  (Note, only the minute and hour are updated - not
        the date values.)

        If the user, for example, changes the time by setting it
        five minutes ahead, this method will still update the time
        every minute, but it will stay five minutes ahead of system
        time.
        '''

        if not (self.minutespinner.flags() & gtk.MAPPED):
            return True

        newtime = datetime.now()

        if self.currentmin is None:
            # This is the first time this method has been called
            self.currentmin = self.minutespinner.get_value_as_int()

        if self.currentmin != newtime.minute:
            self.minutespinner.spin(gtk.SPIN_STEP_FORWARD)
            self.currentmin = newtime.minute
            if self.currentmin == 0:
                self.hourspinner.spin(gtk.SPIN_STEP_FORWARD)

        return True

    def get_days_in_month(self, month, year):
        ''' mimics the behavior of glib's _date_get_days_in_month
        '''

        if month == 2:
            if (year % 4) == 0:
                if (year % 100) == 0:
                    if (year % 400) == 0:
                        return 29
                    else:
                        return 28
                else:
                    return 29
            else:
                return 28
        elif month in [4, 6, 9, 11]:
            return 30

        return 31

    def error_dialog(self):
        '''displays an error dialog during validation prior to next screen'''

        message = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                                gtk.MESSAGE_ERROR, gtk.BUTTONS_OK)

        msg = '<b>%s</b>\n\n%s' % \
            (_("Time Zone Invalid"), _("Please select a valid time zone"))
        message.set_markup(msg)

        # display the dialog
        resp = message.run()
        message.destroy()

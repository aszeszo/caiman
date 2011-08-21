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
Timezone custom widget
'''

import pygtk
pygtk.require('2.0')

import logging
import os

import gobject
import gtk
import pango

from solaris_install.gui_install.gui_install_common import modal_dialog, \
    COLOR_WHITE, GLADE_DIR, GLADE_ERROR_MSG
from solaris_install.gui_install.map import Map, TZTimezone
from solaris_install.logger import INSTALL_LOGGER_NAME

LOGGER = None


class Timezone(gtk.VBox):
    SELECT_LABEL = _("- Select -")

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip,
        user_data=None):

        (tz, distance) = self.map.get_closest_timezone(x, y)
        if tz is not None:
            if tz.tz_oname is not None:
                contains_slash = False
                words = tz.tz_oname.split("/")
                if len(words) > 1:
                    contains_slash = True

                if contains_slash and len(words[-1]):
                    tooltip.set_text(_(words[-1]))
                    return True
                elif not contains_slash:
                    tooltip.set_text(_(tz.tz_oname))
                    return True

            if tz.tz_name is not None:
                words = tz.tz_name.split("/")
                tooltip.set_text(_(words[-1]))
                return True

        return False

    def on_all_timezones_added(self):
        continents = self.map.world.continents

        (sys_ctnt_index, sys_ctry_index, sys_tz_index) = self.get_current_tz()

        if sys_ctnt_index == -1 or sys_ctry_index == -1 or sys_tz_index == -1:
            sys_ctnt_index = 0
            sys_ctry_index = 0
            sys_tz_index = 0

        tree_iter = self.ctnt_store.append()
        self.ctnt_store.set(tree_iter, 0, None, 1, Timezone.SELECT_LABEL)

        for continent in continents:
            text = continent.name
            tree_iter = self.ctnt_store.append()
            self.ctnt_store.set(tree_iter, 0, continent, 1, _(text))
            path = self.ctnt_store.get_path(tree_iter)
            continent.ref = gtk.TreeRowReference(self.ctnt_store, path)

        self.ctnt_combo.set_active(sys_ctnt_index + 1)
        self.ctry_combo.set_active(sys_ctry_index + 1)
        self.tz_combo.set_active(sys_tz_index + 1)

    def on_region_changed(self, ctnt_combo, user_data=None):
        ctry_combo = self.ctry_combo
        continents = self.map.world.continents

        # clear country list store
        ctry_store = ctry_combo.get_model()
        ctry_store.clear()

        # "- 1" for "- Select -" label
        i = ctnt_combo.get_active() - 1
        if i >= 0 and i < len(continents):
            tree_iter = ctry_store.append()
            ctry_store.set(tree_iter, 0, None, 1, Timezone.SELECT_LABEL)

            for country in continents[i].countries:
                tree_iter = ctry_store.append()
                ctry_store.set(tree_iter, 0, country, 1, _(country.name))
                path = ctry_store.get_path(tree_iter)
                country.ref = gtk.TreeRowReference(ctry_store, path)

        # If continent only has 1 country, make that the active one.
        # Otherwise activate the "select" item
        if i >= 0 and len(continents[i].countries) == 1:
            ctry_combo.set_active(1)
        else:
            ctry_combo.set_active(0)

    def on_country_changed(self, ctry_combo, user_data=None):
        ctnt_combo = self.ctnt_combo
        tz_combo = self.tz_combo
        continents = self.map.world.continents

        # clear timezone list store
        tz_store = tz_combo.get_model()
        tz_store.clear()

        # "- 1" for "- Select -" labels
        i = ctnt_combo.get_active() - 1
        j = ctry_combo.get_active() - 1
        if i >= 0 and i < len(continents) and \
            j >= 0 and j < len(continents[i].countries):

            tree_iter = tz_store.append()
            tz_store.set(tree_iter, 0, None, 1, Timezone.SELECT_LABEL)

            for timezone in continents[i].countries[j].timezones:
                tree_iter = tz_store.append()
                tz_store.set(tree_iter, 0, timezone, 1, _(timezone.name))
                path = tz_store.get_path(tree_iter)
                timezone.ref = gtk.TreeRowReference(tz_store, path)

        # If country only has 1 timezone, make that the active one.
        # Otherwise activate the "select" item
        if i >= 0 and j >= 0 and \
            len(continents[i].countries[j].timezones) == 1:

            tz_combo.set_active(1)
        else:
            tz_combo.set_active(0)

    def on_timezone_changed(self, widget, user_data=None):
        model = self.tz_store
        tree_iter = widget.get_active_iter()

        if tree_iter is not None:
            tz = model.get_value(tree_iter, 0)
            if tz is not None and \
                self.map is not None and \
                self.map.flags() & gtk.REALIZED:

                self.map.set_timezone_selected(tz)
                rect = gtk.gdk.Rectangle(0, 0,
                    self.map.allocation.width, self.map.allocation.height)
                self.map.window.invalidate_rect(rect, False)

                LOGGER.debug("Changing TZ to %s" % tz.tz_name)
                # Save new TZ to the environment so that future calls
                # to datetime.now() & Co will reflect the new timezone
                os.environ['TZ'] = tz.tz_name
                # Call the TimeZoneScreen to update the date/time for new TZ
                self.parent_screen.set_current_date_and_time()

    def __init__(self, builder, parent_screen):
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        gtk.VBox.__init__(self)

        self.builder = builder
        # Save a reference to the TimeZoneScreen that contains this
        # Timezone object, so we can call its set_current_date_and_time()
        # when a different time zone is selected.
        self.parent_screen = parent_screen

        self.map = Map()
        self.map.load_timezones()
        self.map.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self.map.show()
        self.pack_start(self.map, expand=False, fill=False, padding=0)

        gobject.GObject.connect(self, "button-press-event",
            self.on_button_pressed, self)
        gobject.GObject.connect(self, "button-release-event",
            self.on_button_released, self)
        gobject.GObject.connect(self, "motion-notify-event",
            self.on_motion_notify)

        # "has-tooltip" property is being set on Timezone, rather
        # than Map, so that event co-ords are consistent with
        # "motion-notify-event" co-ords.
        gobject.GObject.set_property(self, "has-tooltip", True)
        settings = self.get_settings()
        gobject.GObject.set_property(settings, "gtk-tooltip-timeout", 50)

        gobject.GObject.connect(self, "query-tooltip",
            self.on_query_tooltip)

        self.ctnt_store = None
        self.ctry_store = None
        self.tz_store = None

        self.combo = self.builder.get_object("timezonetoplevel")
        self.ctnt_combo = self.builder.get_object("regioncombobox")
        self.ctry_combo = self.builder.get_object("countrycombobox")
        self.tz_combo = self.builder.get_object("timezonecombobox")
        self.ctnt_label = self.builder.get_object("regionlabel")
        self.ctry_label = self.builder.get_object("countrylabel")
        self.tz_label = self.builder.get_object("timezonelabel")

        if None in [self.combo, self.ctnt_combo, self.ctry_combo,
            self.tz_combo, self.ctnt_label, self.ctry_label, self.tz_label]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        self.combo_init()
        self.on_all_timezones_added()

        self.click_time = None

    def do_unrealize(self):
        self.window.destroy()

    def on_button_pressed(self, widget, event, user_data=None):
        ctnt_model = self.ctnt_store
        ctry_model = self.ctry_store
        tz_model = self.tz_store

        # save the time
        self.click_time = event.time

        if event.button == 1:
            self.map.set_offset(event.x, event.y)
            (tz, distance) = self.map.get_closest_timezone(event.x, event.y)
            if tz is not None:
                # The timezone point is seletced
                #  in the "changed" callback of the combo box.
                continent = tz.country.continent
                path = continent.ref.get_path()
                tree_iter = ctnt_model.get_iter(path)
                if tree_iter is not None:
                    self.ctnt_combo.set_active_iter(tree_iter)

                country = tz.country
                path = country.ref.get_path()
                tree_iter = ctry_model.get_iter(path)
                if tree_iter is not None:
                    self.ctry_combo.set_active_iter(tree_iter)

                path = tz.ref.get_path()
                tree_iter = tz_model.get_iter(path)
                if tree_iter is not None:
                    self.tz_combo.set_active_iter(tree_iter)

        (width, height) = widget.size_request()
        widget.requisition.width = width
        widget.requisition.height = height
        widget.queue_resize()

        return False

    def on_button_released(self, widget, event, user_data=None):
        interval = event.time - self.click_time
        if interval <= 0 or interval >= 200:
            return False

        # if click above on city, do not zoom in
        (tz, distance) = self.map.get_closest_timezone(event.x, event.y)
        if event.button == 1 and \
            self.map.zoom_state != TZTimezone.ZOOM_IN and \
            tz is None:

            self.map.update_offset_with_scale(event.x, event.y)
            self.map.zoom_in()
        elif event.button == 3 and \
            self.map.zoom_state != TZTimezone.ZOOM_OUT:

            self.map.update_offset_with_scale(event.x, event.y)
            self.map.zoom_out()

        (width, height) = widget.size_request()
        widget.requisition.width = width
        widget.requisition.height = height
        widget.queue_resize()

        return False

    def on_motion_notify(self, widget, event, user_data=None):
        if event.state & gtk.gdk.BUTTON1_MASK:
            self.map.update_offset(event.x, event.y)

        (tz, distance) = self.map.get_closest_timezone(event.x, event.y)

        if distance < 100:
            self.map.set_default_cursor()
        else:
            self.map.set_cursor()

        if tz is not None:
            self.map.set_timezone_hovered(tz)
        else:
            self.map.unset_hovered_timezone()

        rect = gtk.gdk.Rectangle(0, 0,
            self.map.allocation.width, self.map.allocation.height)
        self.map.window.invalidate_rect(rect, False)

        return True

    def get_selected_tz(self):
        # "minus 1" to accound for "Select" options
        ictnt = self.ctnt_combo.get_active() - 1
        ictry = self.ctry_combo.get_active() - 1
        itz = self.tz_combo.get_active() - 1

        if ictnt < 0 or ictry < 0 or itz < 0:
            LOGGER.warn("WARNING - Time Zone Invalid")
            return (None, None, None)

        continent = self.map.world.continents[ictnt]
        country = continent.countries[ictry]
        timezone = country.timezones[itz]

        return (continent, country, timezone)

    def get_current_tz(self):
        '''
        Get the current system TZ, via libzoneinfo, and return the indices
        into self.map.world for the continent, country and timezone which
        corresponds to the system timezone.
        '''

        system_timezone = self.map.world.get_system_tz("/")
        if system_timezone is None:
            return (-1, -1, -1)

        ctnt_index = 0
        for continent in self.map.world.continents:
            ctry_index = 0
            for country in continent.countries:
                tz_index = 0
                for timezone in country.timezones:
                    if timezone.tz_name == system_timezone:
                        return (ctnt_index, ctry_index, tz_index)

                    tz_index += 1

                ctry_index += 1

            ctnt_index += 1

        return (-1, -1, -1)

    def combo_init(self):
        self.combo.unparent()
        self.combo.show()
        self.pack_start(self.combo, expand=False, fill=False, padding=6)

        self.ctnt_store = gtk.ListStore(gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING)
        self.ctnt_combo.set_model(self.ctnt_store)
        renderer = gtk.CellRendererText()
        gobject.GObject.set_data(renderer, "ellipsize",
            pango.ELLIPSIZE_MIDDLE)
        self.ctnt_combo.pack_start(renderer, expand=True)
        self.ctnt_combo.set_attributes(renderer, text=1)
        gobject.GObject.connect(self.ctnt_combo,
            "changed",
            self.on_region_changed,
            self)

        self.ctry_store = gtk.ListStore(gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING)
        self.ctry_combo.set_model(self.ctry_store)
        renderer = gtk.CellRendererText()
        gobject.GObject.set_data(renderer, "ellipsize",
            pango.ELLIPSIZE_MIDDLE)
        self.ctry_combo.pack_start(renderer, expand=True)
        self.ctry_combo.set_attributes(renderer, text=1)
        gobject.GObject.connect(self.ctry_combo,
            "changed",
            self.on_country_changed,
            self)

        self.tz_store = gtk.ListStore(gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING)
        self.tz_combo.set_model(self.tz_store)
        renderer = gtk.CellRendererText()
        gobject.GObject.set_data(renderer, "ellipsize", pango.ELLIPSIZE_MIDDLE)
        self.tz_combo.pack_start(renderer, expand=True)
        self.tz_combo.set_attributes(renderer, text=1)
        gobject.GObject.connect(self.tz_combo,
            "changed",
            self.on_timezone_changed,
            self)

    def set_default_focus(self):
        self.ctnt_combo.grab_focus()

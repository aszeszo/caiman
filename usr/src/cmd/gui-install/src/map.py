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
Map custom widget
'''

import pygtk
pygtk.require('2.0')

import ctypes as C
import logging

import gobject
import gtk

from solaris_install.gui_install.gui_install_common import IMAGE_DIR
from solaris_install.gui_install.libzoneinfo_ctypes import \
    TZ_CONTINENT, TZ_COUNTRY, TZ_TIMEZONE, \
    libzoneinfo_get_tz_continents, libzoneinfo_get_tz_countries, \
    libzoneinfo_get_timezones_by_country, libzoneinfo_get_system_tz
from solaris_install.logger import INSTALL_LOGGER_NAME

LOGGER = None


class Map(gtk.DrawingArea):
    ZOOM_IN_SCALE = 1.3

    def do_unrealize(self):
        self.window.destroy()

    def do_size_request(self, requisition, w=695, h=325):
        if self.flags() & gtk.VISIBLE:
            rect = gtk.gdk.Rectangle(0, 0, w, h)

            requisition.width = rect.width
            requisition.height = rect.height
            self.allocation = rect

    def do_realize(self):
        self.set_flags(self.flags() | gtk.REALIZED)
        self.window = gtk.gdk.Window(
            self.get_parent_window(),
            self.allocation.width,
            self.allocation.height,
            gtk.gdk.WINDOW_CHILD,
            self.get_events() |
                gtk.gdk.EXPOSURE_MASK |
                gtk.gdk.POINTER_MOTION_MASK |
                gtk.gdk.BUTTON_PRESS_MASK |
                gtk.gdk.BUTTON_RELEASE_MASK |
                gtk.gdk.BUTTON1_MOTION_MASK,
            wclass=gtk.gdk.INPUT_OUTPUT)

        self.window.set_user_data(self)
        self.style.attach(self.window)
        self.style.set_background(self.window, gtk.STATE_NORMAL)
        self.window.move_resize(*self.allocation)

        self.gc = self.style.fg_gc[gtk.STATE_NORMAL]
        self.show_all()

    def do_size_allocate(self, allocation):
        if self.flags() & gtk.REALIZED:
            self.window.move_resize(*allocation)

    def draw_point(self, x, y, pixbuf):
        width = pixbuf.get_width()
        height = pixbuf.get_height()

        self.window.draw_pixbuf(self.gc,
            pixbuf,
            0, 0,
            int(x - width / 2),
            int(y - height / 2))

    def draw_timezones(self):
        if self.window is None:
            return

        for zone in self.timezones:
            self.draw_timezone(zone)

        if self.hovered_zone is not None:
            self.draw_timezone(self.hovered_zone)

        if self.selected_zone is not None:
            self.draw_timezone(self.selected_zone)

    def do_redraw(self):
        (x, y, w, h, d) = self.window.get_geometry()
        self.do_size_request(self.allocation, w=w, h=h)
        allocation = self.allocation
        rwidth = self.scaled_pixbuf.get_width()
        width = rwidth
        rxoff = self.xoffset
        if width < allocation.width:
            x = int((allocation.width - width) / 2)
        else:
            x = 0
            width = allocation.width

        rheight = self.scaled_pixbuf.get_height()
        height = rheight
        ryoff = self.yoffset
        if height < allocation.height:
            y = int((allocation.height - height) / 2)
        else:
            y = 0
            height = allocation.height

        LOGGER.debug("Map.redraw: x = [%s] y = [%s] " \
            "rxoff = [%s] ryoff = [%s] " \
            "rwidth = [%s] rheight = [%s] width = [%s] height = [%s]" % \
            (x, y, rxoff, ryoff, rwidth, rheight, width, height))
        self.window.clear_area(0, 0, allocation.width, allocation.height)
        self.window.draw_pixbuf(self.gc, self.scaled_pixbuf,
            int(rxoff), int(ryoff), x, y, rwidth - rxoff, rheight - ryoff)

        if rxoff + width > rwidth:
            self.window.draw_pixbuf(self.gc, self.scaled_pixbuf,
                    0, ryoff, x + (rwidth - rxoff), y,
                    (width + rxoff - rwidth), (rheight - ryoff))
        if ryoff + height > rheight:
            self.window.draw_pixbuf(self.gc, self.scaled_pixbuf,
                    rxoff, 0, x, (y + (rheight - ryoff)),
                    (rwidth - rxoff), (height + ryoff - rheight))
        if rxoff + width > rwidth and ryoff + height > rheight:
            self.window.draw_pixbuf(self.gc, self.scaled_pixbuf,
                    0, 0, (x + (rwidth - rxoff)), (y + (rheight - ryoff)),
                    (width + rxoff - rwidth), (height + ryoff - rheight))

    def scale_pixbuf(self, scale):
        if self.scale < scale:
            self.zoom_state = TZTimezone.ZOOM_IN
        elif self.scale > scale:
            self.zoom_state = TZTimezone.ZOOM_OUT
        self.scale = scale

        width = int(self.pixbuf.get_width() * self.scale)
        height = int(self.pixbuf.get_height() * self.scale)

        self.scaled_pixbuf = self.pixbuf.scale_simple(width,
            height, gtk.gdk.INTERP_BILINEAR)

    def scale_map(self):
        if self.zoom_state == TZTimezone.ZOOM_IN:
            self.scale_pixbuf(Map.ZOOM_IN_SCALE)
        elif self.zoom_state == TZTimezone.ZOOM_OUT:
            if self.zoom_out_scale == 0.0:
                scale = float(self.allocation.width) / \
                    float(self.pixbuf.get_width())

                if scale > Map.ZOOM_IN_SCALE:
                    self.zoom_out_scale = Map.ZOOM_IN_SCALE
                else:
                    self.zoom_out_scale = scale

            self.scale_pixbuf(self.zoom_out_scale)

    def update_rectangle(self, update_timezone):
        self.scale_map()
        self.do_redraw()
        if update_timezone:
            self.draw_timezones()

    def do_expose_event(self, event):
        if self.scaled_pixbuf is not None and \
            self.scaled_pixbuf.get_height() < self.allocation.height:
            self.yoffset = 0

        self.update_rectangle(True)

    def __init__(self):
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.world = None
        self.timezones = list()

        self.xoffset = 0
        self.yoffset = 0
        # 'zoom' from C renamed to 'zoom_state' for clarity
        self.zoom_state = TZTimezone.ZOOM_OUT
        self.scale = Map.ZOOM_IN_SCALE
        self.zoom_out_scale = 0.0

        # used to remember the orignal (x,y) when dragging the map
        self.x = 0
        self.y = 0

        self.selected_zone = None
        self.hovered_zone = None

        gtk.DrawingArea.__init__(self)

        self.pixbuf = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "worldmap.png")
        self.scaled_pixbuf = None
        self.hand = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "hand.png")
        self.magnifier = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "magnifier.png")

        city_normal_l = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_normal_l.png")
        city_mouseover_l = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_mouseover_l.png")
        city_selected_l = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_selected_l.png")
        city_normal_s = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_normal_s.png")
        city_mouseover_s = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_mouseover_s.png")
        city_selected_s = gtk.gdk.pixbuf_new_from_file(IMAGE_DIR + \
            "/" + "city_selected_s.png")

        if self.pixbuf is None or \
            self.hand is None or \
            self.magnifier is None or \
            city_normal_l is None or \
            city_mouseover_l is None or \
            city_selected_l is None or \
            city_normal_s is None or \
            city_mouseover_s is None or \
            city_selected_s is None:
            return

        self.city_pixbuf = [
            [city_normal_l, city_normal_s],
            [city_mouseover_l, city_mouseover_s],
            [city_selected_l, city_selected_s]
        ]

        self.hand_cursor = gtk.gdk.Cursor(gtk.gdk.display_get_default(),
            self.hand, 0, 0)

        self.magnifier_cursor = gtk.gdk.Cursor(gtk.gdk.display_get_default(),
            self.magnifier, 0, 0)

    def do_zoom(self, scale):
        self.scale_pixbuf(scale)
        self.draw_timezones()
        self.window.invalidate_rect(self.allocation, False)

    def zoom_in(self):
        self.set_hand_cursor()
        self.do_zoom(Map.ZOOM_IN_SCALE)

    def zoom_out(self):
        self.set_magnifier_cursor()
        self.do_zoom(self.zoom_out_scale)

    def draw_timezone(self, zone):
        if zone.x is None or zone.y is None:
            # Special zones that don't have a location
            return

        x = int(zone.x * self.scale)
        y = int(zone.y * self.scale)

        width = self.scaled_pixbuf.get_width()
        height = self.scaled_pixbuf.get_height()

        # handle the points at the border
        if x - 3 < 0:
            x += 3
        if x + 3 > width:
            x -= 3
        if y - 3 < 0:
            y += 3
        if y + 3 > height:
            y -= 3

        if self.allocation.width > width:
            origx = int((self.allocation.width - width) / 2)
        else:
            origx = 0
        if self.allocation.height > height:
            origy = int(self.allocation.height - height) / 2
        else:
            origy = 0

        x = (x - self.xoffset + width) % width + origx
        y = (y - self.yoffset + height) % height + origy

        self.draw_point(x, y,
            self.city_pixbuf[zone.display_state][self.zoom_state])

    def set_timezone_selected(self, zone):
        if self.selected_zone is not None:
            self.selected_zone.display_state = TZTimezone.POINT_NORMAL

        zone.display_state = TZTimezone.POINT_SELECTED
        self.selected_zone = zone

    def set_timezone_hovered(self, zone):
        if zone.display_state != TZTimezone.POINT_SELECTED:
            if self.hovered_zone is not None and \
                self.hovered_zone.display_state != TZTimezone.POINT_SELECTED:
                self.hovered_zone.display_state = TZTimezone.POINT_NORMAL

            zone.display_state = TZTimezone.POINT_HOVERED
            self.hovered_zone = zone

    def unset_hovered_timezone(self):
        if self.hovered_zone is not None and \
            self.hovered_zone.display_state == TZTimezone.POINT_HOVERED:

            self.hovered_zone.display_state = TZTimezone.POINT_NORMAL

        self.hovered_zone = None

    def load_timezones(self):
        self.world = TZWorld()

        for continent in self.world.continents:
            for country in continent.countries:
                for timezone in country.timezones:
                    width = self.pixbuf.get_width()
                    height = self.pixbuf.get_height()
                    timezone.geography_to_geometry(width, height)

                    self.timezones.append(timezone)

        self.draw_timezones()

    def get_closest_timezone(self, x, y):
        LOGGER.debug("get_closest_timezone (%d, %d)" % (x, y))
        chosen = None
        min_dist = -1
        if self.scaled_pixbuf is None:
            return chosen, min_dist

        width = self.scaled_pixbuf.get_width()
        height = self.scaled_pixbuf.get_height()

        if x > width or y > height:
            # The parent widget is bigger than the map, so ignore events
            # from outside the actual map area
            return chosen, min_dist

        if self.allocation.width > width:
            origx = int((self.allocation.width - width) / 2)
        else:
            origx = 0
        if self.allocation.height > height:
            origy = int((self.allocation.height - height) / 2)
        else:
            origy = 0

        x = (x - origx + self.xoffset) % width
        y = (y - origy + self.yoffset) % height

        for zone in self.timezones:
            if zone.x is None or zone.y is None:
                continue

            dx = zone.x * self.scale - x
            dy = zone.y * self.scale - y
            dist = dx * dx + dy * dy

            if chosen is None or dist < min_dist:
                min_dist = dist
                chosen = zone

        if min_dist > -1 and min_dist < 25:
            LOGGER.debug("\t[%s] : %d" % (chosen.name, min_dist))
            return chosen, min_dist

        # If min_dist >= 25, we still return min_dist, but return
        # None for the timezone
        LOGGER.debug("\t[%s] : %d" % (None, min_dist))
        return None, min_dist

    def update_offset_with_scale(self, x, y):
        ''' Updates:
                self.xoffset
                self.yoffset
        '''

        # Beware that ZOOM_IN means that the map is already zoomed in.
        # So this is a zoom out.
        if self.zoom_state != TZTimezone.ZOOM_IN:
            scale = Map.ZOOM_IN_SCALE / self.zoom_out_scale
        else:
            scale = self.zoom_out_scale / Map.ZOOM_IN_SCALE

        awidth = self.allocation.width
        aheight = self.allocation.height

        # width and height of the worldmap before zooming
        width = self.scaled_pixbuf.get_width()
        height = self.scaled_pixbuf.get_height()

        # width and height of the worldmap after zooming
        new_width = float(width) * scale
        new_height = float(height) * scale

        # Calculate the (x, y) of left top corner of
        # the worldmap in the widget window before zooming.
        if awidth > width:
            origx = int((awidth - width) / 2)
        else:
            origx = 0
        if aheight > height:
            origy = int((aheight - height) / 2)
        else:
            origy = 0

        # Calculate the (x, y) of left top corner of
        # the worldmap in the widget window after zooming.
        if awidth > new_width:
            new_origx = int((awidth - new_width) / 2)
        else:
            new_origx = 0
        if aheight > new_height:
            new_origy = int((aheight - new_height) / 2)
        else:
            new_origy = 0

        # Calculate the new offset between the worldmap
        # and the map widget window.
        self.xoffset = int(((x + self.xoffset - origx) * scale - x + \
            new_origx))
        # Beware that ZOOM_IN means that the map is already zoomed in
        if self.zoom_state == TZTimezone.ZOOM_IN:
            # If we are zooming out, y offset should be 0.
            self.yoffset = 0
        else:
            self.yoffset = int(((y + self.yoffset - origy) * scale - y + \
                new_origy))

        self.xoffset = int((self.xoffset + new_width) % new_width)
        self.yoffset = int((self.yoffset + new_height) % new_height)

    def update_offset(self, newx, newy):
        ''' Updates:
                self.xoffset
                self.yoffset
                self.x
                self.y
        '''

        xoff = int(newx) - self.x
        yoff = int(newy) - self.y
        width = self.scaled_pixbuf.get_width()
        height = self.scaled_pixbuf.get_height()
        if xoff != 0:
            self.xoffset = \
                int((self.xoffset - xoff + width) % width)
        if yoff != 0:
            if self.yoffset - yoff < 0:
                self.yoffset = 0
            elif self.yoffset - yoff > height - self.allocation.height:
                self.yoffset = height - self.allocation.height
            else:
                self.yoffset = \
                    int((self.yoffset - yoff + height) % height)

        self.x = int(newx)
        self.y = int(newy)

    def set_offset(self, x, y):
        self.x = int(x)
        self.y = int(y)

    def set_cursor(self):
        if self.zoom_state == TZTimezone.ZOOM_OUT:
            self.set_magnifier_cursor()
        else:
            self.set_hand_cursor()

    def set_hand_cursor(self):
        self.window.set_cursor(self.hand_cursor)

    def set_magnifier_cursor(self):
        if self.scale < Map.ZOOM_IN_SCALE:
            self.window.set_cursor(self.magnifier_cursor)

    def set_default_cursor(self):
        self.window.set_cursor(None)


gobject.type_register(Map)


#
# Python convenience classes for simplyfying access to the
# libzoneinfo data without having to use ctypes APIs.
#

class TZWorld(object):
    def __init__(self):
        ''' Returns worlwide timezone.

            First, Create a "fake" continent for GMT/UTC.
            Then, get all the known continents from libzoneinfo and
            populate them with their countries' details.
        '''
        # Public attributes
        self.continents = list()

        # First, make fake entries for "GMT/UTC"
        continent = TZContinent(self)
        continent.ctnt_name = "GMT/UTC"
        continent.ctnt_id_desc = "GMT/UTC"
        country = TZCountry(continent)
        country.ctry_code = "GMT/UTC"
        country.ctry_id_desc = "---"
        timezone = TZTimezone(country)
        timezone.tz_name = "UTC"
        timezone.tz_id_desc = "GMT/UTC"
        country.timezones.append(timezone)
        continent.countries.append(country)
        self.continents.append(continent)

        # Now, get remaining continents from libzoneinfo
        p_tz_continents = C.pointer(TZ_CONTINENT())
        num_continents = libzoneinfo_get_tz_continents(
            C.byref(p_tz_continents))

        if num_continents == 0:
            return

        p_tz_continent = p_tz_continents[0]
        for i in range(num_continents):
            continent = TZContinent(self)
            continent.populate(p_tz_continent)
            self.continents.append(continent)

            if p_tz_continent.ctnt_next:
                p_tz_continent = p_tz_continent.ctnt_next[0]

    def get_system_tz(self, val):
        sys_tz = libzoneinfo_get_system_tz(val)

        return sys_tz


class TZContinent(object):
    def __init__(self, world):
        # Public attributes
        self.world = world
        self.countries = list()
        self.ctnt_name = None
        self.ctnt_id_desc = None
        self.ctnt_display_desc = None
        # gtk.TreeRowReference
        self.ref = None

    def populate(self, p_tz_continent):
        ''' Fetch details for this continent and its countries.

            Fill in the top-level attributes realting to this continent,
            then fetch all the countries belonging to it from libzoneinfo.
        '''
        self.ctnt_name = p_tz_continent.ctnt_name
        self.ctnt_id_desc = p_tz_continent.ctnt_id_desc
        self.ctnt_display_desc = p_tz_continent.ctnt_display_desc

        p_tz_countries = C.pointer(TZ_COUNTRY())
        num_countries = libzoneinfo_get_tz_countries(C.byref(p_tz_countries),
            p_tz_continent)

        if num_countries == 0:
            return

        p_tz_country = p_tz_countries[0]
        for i in range(num_countries):
            country = TZCountry(self)
            country.populate(p_tz_country)
            self.countries.append(country)

            if p_tz_country.ctry_next:
                p_tz_country = p_tz_country.ctry_next[0]

    # Read-only property
    @property
    def name(self):
        if self.ctnt_display_desc is not None:
            text = self.ctnt_display_desc
        elif self.ctnt_id_desc is not None:
            text = self.ctnt_id_desc
        else:
            text = self.ctnt_name

        return text


class TZCountry(object):
    def __init__(self, continent):
        # Public attributes
        self.continent = continent
        self.timezones = list()
        self.ctry_code = None
        self.ctry_id_desc = None
        self.ctry_display_desc = None
        # gtk.TreeRowReference
        self.ref = None

    def populate(self, p_tz_country):
        ''' Fetch details for this country and its timezones.

            Fill in the top-level attributes realting to this country,
            then fetch all the timezones belonging to it from libzoneinfo.
        '''
        self.ctry_code = p_tz_country.ctry_code
        self.ctry_id_desc = p_tz_country.ctry_id_desc
        self.ctry_display_desc = p_tz_country.ctry_display_desc

        p_tz_timezones = C.pointer(TZ_TIMEZONE())
        num_timezones = libzoneinfo_get_timezones_by_country(
            C.byref(p_tz_timezones), p_tz_country)

        if num_timezones == 0:
            return

        p_tz_timezone = p_tz_timezones[0]
        for i in range(num_timezones):
            timezone = TZTimezone(self)
            timezone.populate(p_tz_timezone)
            if timezone.is_valid_for_continent(self.continent):
                self.timezones.append(timezone)

            if p_tz_timezone.tz_next:
                p_tz_timezone = p_tz_timezone.tz_next[0]

    # Read-only property
    @property
    def name(self):
        if self.ctry_display_desc is not None:
            text = self.ctry_display_desc
        elif self.ctry_id_desc:
            text = self.ctry_id_desc
        else:
            text = self.ctry_code

        return text


class TZTimezone(object):
    POINT_NORMAL = 0
    POINT_HOVERED = 1
    POINT_SELECTED = 2
    POINT_STATE = 3

    ZOOM_IN = 0
    ZOOM_OUT = 1
    ZOOM_STATE = 2

    def __init__(self, country):
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        # Public attributes
        self.country = country
        # gtk.TreeRowReference
        self.ref = None
        self.tz_name = None
        self.tz_oname = None
        self.tz_id_desc = None
        self.tz_display_desc = None
        self.lat_sign = None
        self.lat_degree = None
        self.lat_minute = None
        self.lat_second = None
        self.long_sign = None
        self.long_degree = None
        self.long_minute = None
        self.long_second = None
        self.longitude = None
        self.latitude = None
        # On-screen co-ordinates (depends on pixbuf size)
        self.x = None
        self.y = None
        # 'state' from C code renamed to 'display_state' for clarity
        self.display_state = TZTimezone.POINT_NORMAL

    def populate(self, p_tz_timezone):
        ''' Fill in the attributes realting to this timezone.
        '''
        self.tz_name = p_tz_timezone.tz_name
        self.tz_oname = p_tz_timezone.tz_oname
        self.tz_id_desc = p_tz_timezone.tz_id_desc
        self.tz_display_desc = p_tz_timezone.tz_display_desc
        self.lat_sign = p_tz_timezone.tz_coord.lat_sign
        self.lat_degree = p_tz_timezone.tz_coord.lat_degree
        self.lat_minute = p_tz_timezone.tz_coord.lat_minute
        self.lat_second = p_tz_timezone.tz_coord.lat_second
        self.long_sign = p_tz_timezone.tz_coord.long_sign
        self.long_degree = p_tz_timezone.tz_coord.long_degree
        self.long_minute = p_tz_timezone.tz_coord.long_minute
        self.long_second = p_tz_timezone.tz_coord.long_second

        # Convert longitude and latitude to floating point numbers
        self.longitude = float(self.long_degree) + \
            float(self.long_minute) / 60.0 + \
            float(self.long_second) / (60.0 * 60.0)
        if (self.long_sign < 0):
            self.longitude = -self.longitude

        self.latitude = float(self.lat_degree) + \
            float(self.lat_minute) / 60.0 + \
            float(self.lat_second) / (60.0 * 60.0)
        if (self.lat_sign < 0):
            self.latitude = -self.latitude

    # Read-only property
    @property
    def name(self):
        if self.tz_name != "UTC" and len(self.country.timezones) == 1:
            # If country only contains 1 timezone, use country name
            text = self.country.name
        elif self.tz_display_desc is not None:
            text = self.tz_display_desc
        elif self.tz_id_desc:
            text = self.tz_id_desc
        else:
            text = self.tz_name

        return text

    def geography_to_geometry(self, width, height):
        if self.longitude is not None:
            self.x = int(float(width) / 2.0 * (1 + self.longitude / 180.0))
        if self.latitude is not None:
            self.y = int(float(height) / 2.0 * (1 - self.latitude / 90.0))

    def is_valid_for_continent(self, continent):
        words = self.tz_oname.split("/")
        if len(words) == 1:
            LOGGER.warn("WARNING - invalid TZ name [%s]" % self.tz_oname)

        if continent.ctnt_id_desc.startswith(words[0]):
            return True

        return False

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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Class for specifying an area of the screen (essentially, a glorified rectangle)
'''

class WindowArea(object):
    '''Small class to describe an curses window area'''
    
    def __init__(self, lines=None, columns=None, y_loc=None, x_loc=None,
                 scrollable_lines=None, scrollable_columns=None):
        '''Attributes:
        lines -> height
        columns -> width
        y_loc -> START y location
        x_loc -> START x location
        scrollable_lines -> Size of the vertical scroll area of this WindowArea.
            This attribute is only relevant for ScrollWindows
        scrollable_columns -> Size of the horizontal scroll area of this WindowArea.
            This attribute is only relevant for ScrollWindows
        
        '''
        self.lines = lines
        self.columns = columns
        self.y_loc = y_loc
        self.x_loc = x_loc
        self._scrollable_lines = scrollable_lines
        self._scrollable_columns = scrollable_columns

    def set_scrollable_lines(self, scrollable_lines):
        '''Setter for self.scrollable_lines'''
        self._scrollable_lines = scrollable_lines

    def get_scrollable_lines(self):
        '''Getter for self.scrollable_lines'''
        if self._scrollable_lines is not None:
            return self._scrollable_lines
        else:
            return self.lines

    def set_scrollable_columns(self, scrollable_columns):
        '''Setter for self.scrollable_columns'''
        self._scrollable_columns = scrollable_columns

    def get_scrollable_columns(self):
        '''Getter for self.scrollable_columns'''
        if self._scrollable_columns is not None:
            return self._scrollable_columns
        else:
            return self.columns

    scrollable_lines = property(get_scrollable_lines, set_scrollable_lines)
    scrollable_columns = property(get_scrollable_columns,
                                  set_scrollable_columns)

    
    def __str__(self):
        result = ("lines=%s, columns=%s, y_loc=%s, x_loc=%s, "
                  "scrollable_lines=%s, scrollable_columns=%s")
        return result % (self.lines, self.columns, self.y_loc, self.x_loc,
                         self.scrollable_lines, self.scrollable_columns)
    
    def relative_to_absolute(self, window, border=(0, 0)):
        '''Translate coordinates from window relative to absolute
        
        This function will translate coordinates from being relative to
        the passed in curses.window, to being absolute coordinates (based
        against the entire terminal)
        
        '''
        start_coords = window.getbegyx()
        self.y_loc += start_coords[0] + border[0]
        self.x_loc += start_coords[1] + border[1]
    
    def absolute_to_relative(self, window):
        '''Translate coordinates from absolute to window relative
        
        This function translates absolute coordinates (based on entire
        terminal) to coordinates relative to the passed in window.
        
        '''
        start_coords = window.getbegyx()
        self.y_loc -= start_coords[0]
        self.x_loc -= start_coords[1]

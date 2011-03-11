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
UI element for representing a single selectable list item
'''

from terminalui.inner_window import InnerWindow


class ListItem(InnerWindow):
    '''
    Represents a single item selectable from a list
    '''
    
    def __init__(self, area, window=None, color_theme=None, color=None,
                 highlight_color=None, text="", centered=False, **kwargs):
        '''
        See also InnerWindow.__init__
        
        Sets color to color_theme.default, and
        highlight to color_theme.list-field
        
        If 'text' is given, adds the text to the display
        '''
        if color_theme is None:
            color_theme = window.color_theme
        if color is None:
            color = color_theme.default
        if highlight_color is None:
            highlight_color = color_theme.list_field
        super(ListItem, self).__init__(area, window=window,
                                       color_theme=color_theme, 
                                       color=color,
                                       highlight_color=highlight_color,
                                       **kwargs)
        self.set_text(text, centered)
    
    def set_text(self, text, centered=False):
        '''Set the text of this ListItem. Shortcut to InnerWindow.add_text
        ensures that this window is cleared first
        
        '''
        self.window.clear()
        self.add_text(text, max_chars=(self.window.getmaxyx()[1] - 1),
                      centered=centered)

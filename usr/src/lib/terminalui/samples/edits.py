#!/usr/bin/python2.6
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
terminalui sample: Text-entry fields

This sample shows how to create a series of editable fields for
gathering user input
'''

from terminalui.base_screen import BaseScreen
from terminalui.edit_field import EditField
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea

class EditSample(BaseScreen):
    HEADER_TEXT = "Edit Fields - Sample"
    
    def _show(self):
        # This will be used (and re-used) later. It defines a subwindow's
        # location at 1, 1, with width 20 and height 1
        win_area = WindowArea(y_loc=1, x_loc=1, lines=1, columns=20)
        
        # Creating an empty editable field is just as simple as creating
        # a list item: define a location, and a parent window.
        field_one = EditField(win_area, window=self.center_win)
        
        
        # Side trick - a WindowArea can be reused. In this case, the y-coord
        # is updated, and then win_area is used for the next EditField.
        win_area.y_loc = 2
        
        # Setting default text for a field is also simple:
        field_two = EditField(win_area, window=self.center_win,
                              text="default")
        
        # For the Text Installer and SCI tool, however, an extra step must
        # be taken. To help with labeling and highlighting, each EditField
        # should be wrapped in a ListItem, like so:
        win_area.y_loc = 3
        list_three = ListItem(win_area, window=self.center_win,
                              text="3: ")
        edit_area = WindowArea(y_loc=0, x_loc=5, lines=1, columns=10)
        field_three = EditField(edit_area, window=list_three)
        # Note that the 'window' parameter for field_three is 'list_three',
        # and that edit_area is a position relative to list_three.
        
        win_area.y_loc = 4
        list_four = ListItem(win_area, window=self.center_win,
                             text="4: ")
        # Since WindowAreas are relative to their parent, edit_area can
        # be reused with no modifications
        field_four = EditField(edit_area, window=list_four, text="default")
        
        
        # As with lists, edit fields must be explicitly given focus. Note that
        # focus can be given by index, or by reference.
        self.center_win.activate_object(field_two)

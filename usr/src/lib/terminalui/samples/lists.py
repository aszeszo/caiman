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
terminalui sample: Create a list of selectable items

This sample describes how to create a screen that presents the
user with a list of selectable items
'''

from terminalui.base_screen import BaseScreen
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


class ListSample(BaseScreen):
    HEADER_TEXT = "Lists - Sample"
    
    TEXT = ("Hello world!")
    PARAGRAPH = ("This is a sample paragraph. Its purpose is to show how "
                 "to display large blocks of text using the terminalui "
                 "tools. "
                 "This is a sample paragraph. Its purpose is to show how "
                 "to display large blocks of text using the terminalui "
                 "tools. "
                 "This is a sample paragraph. Its purpose is to show how "
                 "to display large blocks of text using the terminalui "
                 "tools. ")
    
    def _show(self):
        text = "List Item %s"
        for num in xrange(1, 10):
            # When adding subwindows to a screen's center_win, the location
            # of the subwindow needs to be specified. The location should
            # be relative to the parent window.
            y_loc = num
            x_loc = 1
            height = 1
            width = 15
            win_area = WindowArea(height, width, y_loc, x_loc)
            
            
            # To create a list of selectable items, use ListItems. ListItem
            # is a thin wrapper around InnerWindow, which supports adding
            # text to itself in one step. The 'window' parameter specifies
            # the parent window
            item_text = text % num
            list_item = ListItem(win_area, window=self.center_win,
                                 text=item_text, centered=True)
        
        # After the above loop completes, 'center_win' now has 9 ListItem
        # 'subwindows.' By default, none are marked as 'active' (i.e., none
        # have focus). The activate_object() function of InnerWindow fixes
        # that. (With no parameter, the first ListItem is activated)
        self.center_win.activate_object()

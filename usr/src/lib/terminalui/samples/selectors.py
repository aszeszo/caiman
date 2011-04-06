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
terminalui sample: Skipping screens

This sample demonstrates how to bypass screens that aren't needed
(based on the user's prior selections, for example)
'''

from terminalui.base_screen import BaseScreen, SkipException
from terminalui.edit_field import EditField
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


from hello_world import HelloWorld
from lists import ListSample
from edits import EditSample


# It's possible to selectively skip screens based on any parameters
# desired. In the SCI tool, for example, the network configuration
# screens are only displayed if the user elects for "Manual"
# configuration - otherwise, the screens are skipped.
# This sample demonstrates how.


SELECTED = None
class Selector(BaseScreen):
    # First, a "selection" screen is defined. This screen creates a list
    # of 3 items to choose from. The next screen shown will be based on the
    # user's selections.
    
    HEADER_TEXT = "Choose one"
    
    def __init__(self, main_win):
        super(Selector, self).__init__(main_win)
        self.hello_item = None
        self.list_item = None
        self.edit_item = None
    
    def _show(self):
        # Set up the three list items...
        win_area = WindowArea(lines=1, columns=15, y_loc=1, x_loc=1)
        self.hello_item = ListItem(win_area, window=self.center_win,
                                   text="Hello World")
        win_area.y_loc += 1
        self.list_item = ListItem(win_area, window=self.center_win,
                                  text="Lists")
        win_area.y_loc += 1
        self.edit_item = ListItem(win_area, window=self.center_win,
                                  text="Edit Fields")
        self.center_win.activate_object()
    
    def on_continue(self):
        # ...and then, when the user elects to move forward, go through
        # the usual motions to track their selection. (In this case,
        # store it as a global string; more likely is that it would
        # be stored in the DOC for install projects)
        global SELECTED
        has_focus = self.center_win.get_active_object()
        if has_focus is self.hello_item:
            SELECTED = "hello"
        elif has_focus is self.list_item:
            SELECTED = "list"
        elif has_focus is self.edit_item:
            SELECTED = "edit"
        else:
            SELECTED = None

# Then, for each of the given screens...
class HelloSelect(HelloWorld):
    def _show(self):
        # ... check the state. If the current screen is not applicable
        # to the given scenario, raise a "SkipException", which
        # tells the UI to move past this screen without doing anything.
        if SELECTED != "hello":
            raise SkipException()
        
        # Otherwise, carry on with the usual work of _show'ing the screen
        # (omitted here, for brevity's sake)
        super(HelloSelect, self)._show()


class ListSelect(ListSample):
    def _show(self):
        if SELECTED != "list":
            raise SkipException()
        super(ListSelect, self)._show()


class EditSelect(EditSample):
    def _show(self):
        if SELECTED != "edit":
            raise SkipException()
        super(EditSelect, self)._show()


def get_selector_screens(main_win):
    # Finally, a glimpse into how screen flow is designed. Screen flow is
    # always a "static" list of screens. Under normal conditions, each
    # screen is show in order (though of course, the user can always
    # move backwards should they desire). As demonstrated above, however,
    # each screen can elect to skip itself, if it should not be shown based
    # on the current state of the program.
    return [Selector(main_win),
            HelloSelect(main_win),
            ListSelect(main_win),
            EditSelect(main_win)]

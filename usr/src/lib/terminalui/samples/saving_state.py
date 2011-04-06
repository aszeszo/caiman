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
terminalui sample: Saving & restoring state

This sample shows how to save and restore state upon leaving / returning
from a screen.
'''

from terminalui.base_screen import BaseScreen
from terminalui.edit_field import EditField
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


class StateSample(BaseScreen):
    HEADER_TEXT = "Saving State - Sample"
    
    def __init__(self, main_win):
        # Editable fields and lists aren't very useful if you can't
        # get at the data they provide. Restoring state is "easy" - in the
        # _show() method, just initialize the fields (and/or set the active
        # object) based on the state you want restored. In this example,
        # a screen has four editable fields, each 'remembering' what was in it,
        # and the screen also remembers which field was being edited last.
        
        
        # First, notice that (for the first time in this series), an __init__
        # method is defined. Here, a few variables are initialized to help
        # track state for this screen. In the wild, the state could also
        # be inferred from other sources, such as the DOC.
        
        
        # Of course, the parent class' __init__ should be called first.
        super(StateSample, self).__init__(main_win)
        
        
        # self.current_selection will track what has focus...
        self.current_selection = 0
        # ...and self.saved_text can track what was in the fields
        self.saved_text = {0: "zero",
                           1: "one",
                           2: "two",
                           3: "three"}
        
        # self.fields is defined here, and will be used to get a reference
        # to the given EditField when the time comes to save state. In
        # the Text Installer and SCI tool, fields are generally each given
        # their own attribute (e.g., self.field_one, self.field_two, etc.)
        self.fields = {}
    
    def _show(self):
        # The _show method will not only create the four desired EditFields,
        # but restore saved state as well.
        win_area = WindowArea(lines=1, columns=40, y_loc=1, x_loc=1)
        edit_area = WindowArea(lines=1, columns=20, y_loc=0, x_loc=10)
        for field_num in range(4):
            win_area.y_loc += 1
            field_label = "%s: " % field_num
            list_item = ListItem(win_area, window=self.center_win,
                                 text=field_label)
            # Grab the saved text for the field (assume it's been saved for
            # now; *how* to go about saving it is below)
            field_text = self.saved_text[field_num]
            # And then set that as the text for the field
            edit_field = EditField(edit_area, window=list_item,
                                   text=field_text)
            # Save a reference to the field so other methods can access
            # their data:
            self.fields[field_num] = edit_field
        
        # Since this series of fields also acts as a selectable list,
        # the current selection can be restored as well by changing which
        # object is active:
        self.center_win.activate_object(self.current_selection)
    
    def on_change_screen(self):
        # BaseScreen defines three functions that may be called when
        # the screen "moves on" (and thus, may need to save state)
        # By default, they do nothing - subclasses should override them
        # to get the needed functionality. The three functions are:
        #    * on_continue: Called when the user moves to the next screen
        #    * on_prev: Called when the user goes BACK a screen
        #    * on_change_screen: Called in both cases
        # In most cases, "on_change_screen" is sufficient - whether the user
        # goes forward or back, save the current state. In some cases, it is
        # desirable to not save certain state when moving forward or back
        # (or to perform additional, non-state related tasks); in those cases,
        # use the corresponding function.
        
        
        # For this example, "on_change_screen" is sufficient. When the user
        # moves forward or back, take a record of what text was entered:
        for field_num in range(4):
            field = self.fields[field_num]
            field_text = field.get_text()
            self.saved_text[field_num] = field_text
        
        # ...as well as what field is currently highlighted:
        self.current_selection = self.center_win.active_object

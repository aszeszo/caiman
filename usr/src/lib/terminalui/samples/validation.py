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
terminalui sample: Validating input and displaying errors

This sample shows how to validate user input at each of three levels:
* Per keystroke (EditFields only)
* Upon losing focus (EditFields only)
* Prior to leaving the screen

Additionally, various methods of displaying errors are demonstrated here.
'''

from terminalui.base_screen import BaseScreen, UIMessage
from terminalui.edit_field import EditField
from terminalui.error_window import ErrorWindow
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea

class ValidSample(BaseScreen):
    HEADER_TEXT = "Validation - Sample"
    
    def __init__(self, main_win):
        super(ValidSample, self).__init__(main_win)
        
        # Boilerplate; for storing references to the created ListItems,
        # EditFields, and ErrorWindows
        self.char_list = None
        self.char_field = None
        
        self.char2_list = None
        self.char2_field = None
        self.char2_err = None
        
        self.focus_list = None
        self.focus_field = None
        self.focus_err = None
    
    def _show(self):
        # WindowArea boilerplate
        list_area = WindowArea(lines=1, columns=40, y_loc=1, x_loc=1)
        edit_area = WindowArea(lines=1, columns=20, y_loc=0, x_loc=15)
        
        # EditFields support per-character validation by passing in
        # a callback function as the "validate" keyword argument. The function
        # is called after each keypress with a single parameter, the EditField
        # in question (from which one can grab the current text). If the
        # current value is valid, the function should do nothing. If invalid,
        # a UIMessage exception should be raised.
        
        # For the sake of 'flow', the validation functions for this sample
        # will be defined inline; in general, they should be defined elsewhere
        # in the file. Finally, remember that, since these functions are
        # called after each keystroke, they need to be able to handle partially
        # correct values as well. For example, "2", "25", "255", "255.",
        # "255.2", "255.25", ..., "255.255.255.0" all would need to be accepted
        # by a netmask validation function.
        def digits_only(edit_field):
            text = edit_field.get_text()
            if text and not text.isdigit():
                raise UIMessage("Only digits allowed!")
        
        list_area.y_loc = 1
        self.char_list = ListItem(list_area, window=self.center_win,
                                  text="validate:")
        self.char_edit = EditField(edit_area,
                                   window=self.char_list,
                                   validate=digits_only,
                                   error_win=self.main_win.error_line)
        # The error_win parameter is required to make anything meaningful
        # display to the user; it should be a reference to an ErrorWindow
        # object in which to display the message. (self.main_win.error_line
        # is used here as filler; a more appropriate example follows)
        
        list_area.y_loc = 2
        # There's nothing too special about creating an ErrorWindow;
        # it's much like a ListItem or EditField:
        error_area = WindowArea(lines=1, columns=30, y_loc=2, x_loc=40)
        self.char2_err = ErrorWindow(error_area, self.center_win)
        self.char2_list = ListItem(list_area, window=self.center_win,
                                  text="validate(2):")
        self.char2_edit = EditField(edit_area,
                                    window=self.char2_list,
                                    validate=digits_only,
                                    error_win=self.char2_err)
        
        
        # An EditField can also be checked for validity on loss of focus,
        # by passing a function to the "on_exit" argument
        # (though care must be taken to also check validity when changing
        #  screens; screen changes don't trigger loss-of-focus checks in the
        #  same way)
        # The following EditField illustrates such a thing. (An on_exit
        # function would be an appropriate place to ensure that a user
        # entered "255.255.255.0" for a netmask, and not just "255.")
        list_area.y_loc = 3
        error_area.y_loc = 3
        self.focus_err = ErrorWindow(error_area, self.center_win)
        self.focus_list = ListItem(list_area, window=self.center_win,
                                  text="on_exit:")
        self.focus_edit = EditField(edit_area,
                                    window=self.focus_list,
                                    on_exit=digits_only,
                                    error_win=self.focus_err)
        
        self.center_win.activate_object()
    
    def validate(self):
        # As a final (and perhaps, most important) form of validation, when
        # a subclass of BaseScreen attempts to move *forward* to the next
        # screen, it will call its "validate()" function, if any. Like the
        # callback functions for EditFields, this function should raise a
        # UIMessage if there are any conditions which fail validation.
        # 
        # validate() is not called if the user decides to go backwards; the
        # user is never locked out of reversing their direction
        # 
        # Note: validate() is always called prior to "on_continue()"; thus,
        # any code in the on_continue function, if defined, can be certain
        # that the values for this screen are valid.
        
        # For this sample, the first two fields will be required to have
        # identical text.
        if self.char_edit.get_text() != self.char2_edit.get_text():
            raise UIMessage("First 2 fields must have identical text!")
        # UIMessages raised here are always displayed in the 'footer' area
        # of the screen.

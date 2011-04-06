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
terminalui sample: Text-only screen

This sample shows the bare-bones of adding a screen to a consumer of terminalui
'''

from terminalui.base_screen import BaseScreen


class HelloWorld(BaseScreen):
    # HEADER_TEXT is a class variable consumed by the parent class, BaseScreen
    # The text is displayed in the header at the top of the screen.
    HEADER_TEXT = "Hello World - Sample"
    
    def _show(self):
        # The _show() method is the meat of a subclass of BaseScreen. It is
        # run each time the screen is displayed. It is where one sets up
        # any text, editable fields, etc.
        
        
        # BaseScreen (and subclasses) have access to a "center_win" attribute.
        # This attribute is an InnerWindow object. This InnerWindow, in
        # particular, carves out the majority of the terminal/console.
        
        
        # Adding a single line of text to an InnerWindow is easy:
        self.center_win.add_text("Hello world!")
        # The default location is (0, 0). Note that for consistency with
        # the underlying curses library, coordinates are in the form (y, x)
        
        
        # Adding a paragraph isn't much more difficult:
        paragraph = ("This is a sample paragraph. Its purpose is to show how "
                     "to display large blocks of text using the terminalui "
                     "tools. "
                     "This is a sample paragraph. Its purpose is to show how "
                     "to display large blocks of text using the terminalui "
                     "tools. "
                     "This is a sample paragraph. Its purpose is to show how "
                     "to display large blocks of text using the terminalui "
                     "tools. ")
        y_loc = 2
        y_loc += self.center_win.add_paragraph(paragraph, start_y=y_loc)
        # A y-coordinate is given to this call, so that the previous text
        # isn't overwritten. The text is automatically wrapped, breaking
        # on whitespace.
        
        
        # Since terminal space is limited, one must be careful not to add too
        # much text. Complicating the matter is that translations of your
        # text may take up more or less space. Curses will crash if you try
        # to write text to space to an area outside of your window;
        # InnerWindow objects will simply truncate. The max_chars parameter can
        # be used to specify how far to go before truncating (in the add_text
        # case).
        y_loc += 1
        self.center_win.add_text("Really long line of text will be truncated",
                                 start_y=y_loc, max_chars=10)
        
        # Similarly, add_paragraph has a "max_x" parameter, which specifies
        # how soon to truncate text. Additionally, add_paragraph
        # has a max_y parameter, which can be used to limit the number of
        # lines.
        y_loc += 2
        self.center_win.add_paragraph(paragraph, start_y=y_loc,
                                      max_x=60, max_y=3)

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
Start the installation, provide functions for updating the install progress
'''

import curses
import math

from solaris_install.text_install import _, RELEASE
from solaris_install.text_install.ti_install import perform_ti_install
from terminalui.base_screen import BaseScreen
from terminalui.i18n import ljust_columns
from terminalui.inner_window import InnerWindow
from terminalui.window_area import WindowArea


class InstallProgress(BaseScreen):
    '''Present a progress bar, and callback hooks for an installation
    Thread to update this screen with percent complete and status.
    
    '''
    
    HEADER_TEXT = _("Installing %(release)s") % RELEASE
    PROG_BAR_ENDS = (ord('['), ord(']'))
    
    QUIT_DISK_MODIFIED = _("Do you want to quit the Installer?\n\n"
                           "Any changes made to the disk by the "
                           "Installer will be left \"as is.\"")
    
    def __init__(self, main_win, install_data, target_controller):
        super(InstallProgress, self).__init__(main_win)
        
        # Location on screen where the status messages should get printed
        # Format: (y, x, max-width)
        self.status_msg_loc = (4, 12, 50)
        
        # Location on screen where the progress bar should be displayed
        # Format: (y, x, width)
        self.status_bar_loc = (6, 10, 50)
        
        self.status_bar = None
        self.status_bar_width = None
        self.install_data = install_data
        self.progress_color = None
        self.update_to = None
        self.tc = target_controller
    
    def set_actions(self):
        '''Remove all actions except F9_Quit.'''
        self.main_win.actions.pop(curses.KEY_F2) # Remove F2_Continue
        self.main_win.actions.pop(curses.KEY_F3) # Remove F3_Back
        self.main_win.actions.pop(curses.KEY_F6) # Remove F6_Help

    def _show(self):
        '''Set an initial status message, and initialize the progress bar'''
        self.set_status_message(InstallProgress.HEADER_TEXT)
        self.init_status_bar(*self.status_bar_loc)
        self.main_win.redrawwin()
        self.main_win.do_update()

    def validate_loop(self):
        ''' Do the actual installation '''
        self.center_win.window.timeout(100) # Make getch() non-blocking
        perform_ti_install(self.install_data, self, self.update_status)
        self.center_win.window.timeout(-1) # Restore getch() to be blocking
        return self.main_win.screen_list.get_next(self)

    def update_status(self, percent, message):
        '''Update this screen to display message and set the status
        bar to 'percent'. 

        '''

        self.set_status_message(message)
        self.set_status_percent(percent)
        self.main_win.redrawwin()
        self.main_win.do_update()
    
    def set_status_message(self, message):
        '''Set the status message on the screen, completely overwriting
        the previous message'''
        self.center_win.add_text(ljust_columns(\
            message, self.status_msg_loc[2]), self.status_msg_loc[0],\
            self.status_msg_loc[1], max_chars=self.status_msg_loc[2])
    
    def set_status_percent(self, percent):
        '''Set the completion percentage by updating the progress bar.
        Note that this is implemented as a 'one-way' change (updating to
        a percent that is lower than previously set will not work)
        
        '''
        width = self.status_bar_width
        complete = int(math.ceil(float(percent) / 100.0 * width))
        self.status_bar.add_text(" " * complete, start_y=0, start_x=1,
                                 max_chars=width)
        percent_text = "(%i%%)" % percent
        percent_bar = percent_text.center(width)
        left_half = percent_bar[:complete]
        right_half = percent_bar[complete:]
        self.status_bar.window.addstr(0, 1, left_half, self.progress_color)
        self.status_bar.window.addstr(0, complete + 1, right_half)
        self.status_bar.no_ut_refresh()
    
    def init_status_bar(self, y_loc, x_loc, width):
        '''Initialize the progress bar window and set to 0%'''
        self.status_bar_width = width
        status_bar_area = WindowArea(1, width + 3, y_loc, x_loc + 1)
        self.status_bar = InnerWindow(status_bar_area,
                                      window=self.center_win)
        self.status_bar.window.addch(0, 0, InstallProgress.PROG_BAR_ENDS[0])
        self.status_bar.window.addch(0, width + 1,
                                     InstallProgress.PROG_BAR_ENDS[1])
        self.progress_color = self.center_win.color_theme.progress_bar
        self.set_status_percent(0)

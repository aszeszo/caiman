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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Start a Thread for executing installation, and
track the progress of the installation
'''

import curses
import logging
import math
import threading
import time

from osol_install.text_install import _, LOG_LEVEL_INPUT, RELEASE
from osol_install.text_install.base_screen import BaseScreen
from osol_install.text_install.i18n import ljust_columns
from osol_install.text_install.inner_window import InnerWindow
from osol_install.text_install.window_area import WindowArea
from osol_install.text_install.ti_install import perform_ti_install


class InstallProgress(BaseScreen):
    '''Present a progress bar, and callback hooks for an installation
    Thread to update this screen with percent complete and status.
    
    '''
    
    HEADER_TEXT = _("Installing %(release)s") % RELEASE
    PROG_BAR_ENDS = (ord('['), ord(']'))
    
    def __init__(self, main_win):
        super(InstallProgress, self).__init__(main_win)
        self.really_quit = False
        
        # Location on screen where the status messages should get printed
        # Format: (y, x, max-width)
        self.status_msg_loc = (4, 12, 50)
        
        # Location on screen where the progress bar should be displayed
        # Format: (y, x, width)
        self.status_bar_loc = (6, 10, 50)
        
        self.last_update = 0
        # Minimum elapsed time in seconds between screen updates
        self.update_frequency = 2
        self.status_bar = None
        self.status_bar_width = None
        self.install_profile = None
        self.install_thread = None
        self.progress_color = None
        self.quit_event = threading.Event()
        self.update_event = threading.Event()
        self.time_change_event = threading.Event()
        self.update_to = None
    
    def set_actions(self):
        '''Remove all actions except F9_Quit.'''
        self.main_win.actions.pop(curses.KEY_F2) # Remove F2_Continue
        self.main_win.actions.pop(curses.KEY_F3) # Remove F3_Back
        self.main_win.actions.pop(curses.KEY_F6) # Remove F6_Help
    
    def _show(self):
        '''Set an initial status message, and initialize the progress bar'''
        self.set_status_message(InstallProgress.HEADER_TEXT)
        self.init_status_bar(*self.status_bar_loc)
    
    def validate_loop(self):
        '''Begin the installation. Honor the '-n' flag from the CLI by
        beginning a 'fake' installation thread instead of actually making
        changes to the disk.
        
        After starting the installation thread, wait for input from the
        user, in case they change their mind and try to quit.
        
        '''
        if self.install_profile.no_install_mode:
            self.install_thread = self.start_fake_install_thread()
        else:
            self.install_thread = self.start_install_thread()
        win = self.center_win.window
        win.timeout(100) # Set timeout for getch to 100 ms. The install_thread
                         # will be checked at this frequency to see if it
                         # has finished execution.
                         # Keystroke input will still be processed immediately
        while self.install_thread.is_alive():
            # Wait for the install thread to signal that it has finished
            # updating the system time, so that we can safely use getch(),
            # which times out based on the system clock.
            self.time_change_event.wait()
            input_key = self.main_win.getch()
            if input_key == curses.KEY_F9:
                self.really_quit = self.confirm_quit()
                if self.really_quit: 
                    win.timeout(-1)
                    self.install_thread.join()
                    return None
        win.timeout(-1) # Restore getch() to be blocking
        return self.main_win.screen_list.get_next(self)
    
    def start_install_thread(self):
        '''Instantiate a Thread to do the installation, and start execution.'''
        handle = threading.Thread(target=InstallProgress.perform_install,
                                  args=(self.install_profile, self,
                                        InstallProgress.update_status,
                                        self.quit_event,
                                        self.time_change_event))
        handle.start()
        return handle
    
    def start_fake_install_thread(self):
        '''Instantiate a Thread to perform a 'fake' installation'''
        handle = threading.Thread(target=InstallProgress.fake_install,
                                  args=(self.install_profile, self,
                                        InstallProgress.update_status,
                                        self.quit_event))
        self.time_change_event.set()
        handle.start()
        return handle
    
    @staticmethod
    def perform_install(install_profile, screen, update_status, quit_event,
                        time_change_event):
        '''Call function to perform the actual install.

        '''
        install_profile.install_succeeded = False
        try:
            perform_ti_install(install_profile, screen, update_status,
                               quit_event, time_change_event)
        except BaseException, ex:
            logging.exception(ex)
    
    @staticmethod
    def fake_install(install_profile, screen, update_status, quit_event):
        '''For demonstration purposes only, this function is the target
        of the install thread when the '-n' flag is given at the command
        line. All this thread does is attempt to update the status/progress
        bar at set intervals.
        
        It also checks quit_event (a threading.Event), and, if set, immediately
        returns.
        
        '''
        install_profile.disk.to_tgt()
        for i in range(101):
            update_status(screen, i, "at %d percent" % i)
            logging.log(LOG_LEVEL_INPUT, "at %s percent", i)
            quit_event.wait(0.2)
            if quit_event.is_set():
                logging.error("User forced quit! Aborting")
                install_profile.install_succeeded = False
                return
        install_profile.install_succeeded = True
    
    def update_status(self, percent, message):
        '''Update this screen to display message and set the status
        bar to 'percent'. This is the intended callback function
        for the installation thread.
        
        This function ensures the screen is not updated more often
        then once every 2 seconds (the update_frequency)
        
        The threading.Event, self.update_event, is used to ensure that this
        method does not clobber the confirm_quit pop-up
        
        '''
        if self.update_event.is_set():
            return
        update_time = time.time()
        if (update_time - self.last_update) > self.update_frequency:
            self._update_status(percent, message)
            self.last_update = update_time
    
    def _update_status(self, percent, message):
        '''Immediately update status, without checking the self.update_event
        or last update_time
        
        '''
        self.set_status_message(message)
        self.set_status_percent(percent)
        self.main_win.redrawwin()
        self.main_win.do_update()
    
    def set_status_message(self, message):
        '''Set the status message on the screen, completely overwriting
        the previous message'''
        self.center_win.add_text(ljust_columns(message, self.status_msg_loc[2]),
                                 self.status_msg_loc[0],
                                 self.status_msg_loc[1],
                                 max_chars=self.status_msg_loc[2])
    
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
        self.last_update = 0
        self.set_status_percent(0)
    
    def confirm_quit(self):
        '''Confirm the user truly wants to quit, and if so, set quit_event
        so that the install thread can attempt to shut down as gracefully
        as possible.
        
        Clear update_event so that update_status does not attempt to write
        the progress bar while the user is contemplating the need/desire to
        quit.
        
        '''
        self.update_event.set()
        do_quit = self.main_win.pop_up(BaseScreen.CONFIRM_QUIT_HEADER,
                                       BaseScreen.QUIT_DISK_MOD_TEXT,
                                       BaseScreen.CANCEL_BUTTON,
                                       BaseScreen.CONFIRM_BUTTON)
        update_to = self.update_to
        if update_to is not None:
            self._update_status(update_to[0], update_to[1])
        self.update_event.clear()
        
        if do_quit:
            self.quit_event.set()
        return do_quit

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
Report the status of an installation to the user
'''

import curses

from osol_install.text_install import _, RELEASE
from osol_install.text_install.action import Action
from osol_install.text_install.base_screen import BaseScreen, RebootException


class InstallStatus(BaseScreen):
    '''
    Display text to the user indicating success or failure of the installation.
    Also provide option for viewing the install log
    
    '''
    
    SUCCESS_HEADER = _("Installation Complete")
    FAILED_HEADER = _("Installation Failed")
    
    SUCCESS_TEXT = _("The installation of %(release)s has completed "
                     "successfully.\n\n"
                     "Reboot to start the newly installed software "
                     "or Quit if you wish to perform additional "
                     "tasks before rebooting.\n\n"
                     "The installation log is available at "
                     "%(log_tmp)s. After reboot it can be found"
                     " at %(log_final)s.")
    
    FAILED_TEXT = _("The installation did not complete normally.\n\n"
                    "For more information you can review the"
                    " installation log.\n"
                    "The installation log is available at %(log_tmp)s")
    
    def __init__(self, main_win):
        super(InstallStatus, self).__init__(main_win)
        self.log_locations = {}
    
    def set_actions(self):
        '''Remove all actions except Quit, and add actions for rebooting
        and viewing the log.
        
        '''
        self.main_win.actions.pop(curses.KEY_F2) # Remove F2_Continue
        self.main_win.actions.pop(curses.KEY_F3) # Remove F3_Back
        self.main_win.actions.pop(curses.KEY_F6) # Remove F6_Help
        
        if self.install_profile.install_succeeded:
            reboot_action = Action(curses.KEY_F8, _("Reboot"), reboot_system)
            self.main_win.actions[reboot_action.key] = reboot_action
        
        log_action = Action(curses.KEY_F4, _("View Log"),
                            self.main_win.screen_list.get_next)
        self.main_win.actions[log_action.key] = log_action
        
    
    def _show(self):
        '''Display the correct text based on whether the installation
        succeeded or failed.
        
        '''
        self.log_locations["log_tmp"] = self.install_profile.log_location
        self.log_locations["log_final"] = self.install_profile.log_final
        if self.install_profile.install_succeeded:
            self.header_text = InstallStatus.SUCCESS_HEADER
            paragraph_text = InstallStatus.SUCCESS_TEXT
        else:
            self.header_text = InstallStatus.FAILED_HEADER
            paragraph_text = InstallStatus.FAILED_TEXT
        self.main_win.set_header_text(self.header_text)
        
        fmt = {}
        fmt.update(self.log_locations)
        fmt.update(RELEASE)
        self.center_win.add_paragraph(paragraph_text % fmt, 2)
    
    def confirm_quit(self):
        '''No need to confirm after installation is complete'''
        return True


def reboot_system(screen=None):
    '''Attempts to reboot the system (unless running with the '-n' command
    line flag)
    
    '''
    if screen and screen.install_profile.no_install_mode:
        raise SystemExit("REBOOT")
    else:
        raise RebootException

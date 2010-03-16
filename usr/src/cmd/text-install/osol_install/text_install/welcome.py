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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
Contains the Welcome Screen for the Text Installer
'''

from osol_install.text_install import _
from osol_install.text_install.base_screen import BaseScreen


class WelcomeScreen(BaseScreen):
    '''First screen of the text installer.
    No special __init__ needed beyond that provided by BaseScreen
    
    '''
    
    HEADER_TEXT = _("Welcome to OpenSolaris")
    WELCOME_TEXT = _("Thanks for choosing to install OpenSolaris! This "
                     "installer enables you to install the OpenSolaris "
                     "Operating System (OS) on SPARC or x86 systems.\n\n"
                     "For detailed step-by-step procedures for completing "
                     "this installation, refer to the \"Getting Started "
                     "Guide\" at opensolaris.com/use.\n\n"
                     "The installation log will be at %s.\n\n"
                     "How to navigate through this installer:")
    BULLET_ITEMS = [_("Use the function keys listed at the bottom of each "
                 "screen to move from screen to screen and to perform "
                 "other operations."),
               _("Use the up/down arrow keys to change the selection "
                 "or to move between input fields."),
               _("If your keyboard does not have function keys, or "
                 "they do not respond, press ESC; the legend at the "
                 "bottom of the screen will change to show the ESC keys"
                 " for navigation and other functions.")]
    BULLET = "- "
    
    def set_actions(self):
        '''Remove the F3_Back Action from the first screen'''
        self.main_win.actions.pop(self.main_win.back_action.key, None)
    
    def _show(self):
        '''Display the static paragraph WELCOME_TEXT'''
        log_file = self.install_profile.log_location
        y_loc = 1
        y_loc += self.center_win.add_paragraph(WelcomeScreen.WELCOME_TEXT %
                                               log_file,
                                               start_y=y_loc)
        x_loc = len(WelcomeScreen.BULLET)
        for bullet in WelcomeScreen.BULLET_ITEMS:
            self.center_win.add_text(WelcomeScreen.BULLET, start_y=y_loc)
            y_loc += self.center_win.add_paragraph(bullet, start_y=y_loc,
                                                   start_x=x_loc)

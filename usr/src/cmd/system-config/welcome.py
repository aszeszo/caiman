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
Contains the Welcome Screen for the SCI Tool
'''

from solaris_install.sysconfig import _, SCI_HELP, get_sc_options_from_doc, \
                                      configure_group, SC_GROUP_IDENTITY, \
                                      SC_GROUP_NETWORK, SC_GROUP_NS, \
                                      SC_GROUP_DATETIME, SC_GROUP_LOCATION, \
                                      SC_GROUP_USERS
from terminalui.base_screen import BaseScreen


class WelcomeScreen(BaseScreen):
    '''First screen of the SCI tool.
    No special __init__ needed beyond that provided by BaseScreen
    
    '''
    
    HEADER_TEXT = _("System Configuration Tool")
    WELCOME_TEXT = _("System Configuration Tool enables you to specify "
                     "the following configuration parameters for your "
                     "newly-installed Oracle Solaris 11 system:\n"
                     "%(scgroups)s\n"
                     "System Configuration Tool produces an SMF profile file "
                     "in %(scprof)s.\n\n"
                     "How to navigate through this tool:")
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
    HELP_DATA = (SCI_HELP + "/%s/welcome.txt",
                 _("Welcome and Navigation Instructions"))
    
    def set_actions(self):
        '''Remove the F3_Back Action from the first screen'''
        self.main_win.actions.pop(self.main_win.back_action.key, None)
    
    def _show(self):
        '''Display the static paragraph WELCOME_TEXT and all
           applicable bullet items'''
        sc_options = get_sc_options_from_doc()
        sc_groups = ""
        if configure_group(SC_GROUP_NETWORK):
            sc_groups += _("- network\n")
        elif configure_group(SC_GROUP_IDENTITY):
            sc_groups += _("- system hostname\n")
        if configure_group(SC_GROUP_LOCATION):
            sc_groups += _("- time zone\n")
        if configure_group(SC_GROUP_DATETIME):
            sc_groups += _("- date and time\n")
        if configure_group(SC_GROUP_USERS):
            sc_groups += _("- user and root accounts\n")
        if configure_group(SC_GROUP_NS):
            sc_groups += _("- name services\n")

        fmt = {"scgroups": sc_groups, "scprof": sc_options.profile}
        text = WelcomeScreen.WELCOME_TEXT % fmt

        y_loc = 1
        y_loc += self.center_win.add_paragraph(text, start_y=y_loc)
        x_loc = len(WelcomeScreen.BULLET)
        for bullet in WelcomeScreen.BULLET_ITEMS:
            self.center_win.add_text(WelcomeScreen.BULLET, start_y=y_loc)
            y_loc += self.center_win.add_paragraph(bullet, start_y=y_loc,
                                                   start_x=x_loc)

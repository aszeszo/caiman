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
from terminalui.i18n import convert_paragraph
from terminalui.scroll_window import ScrollWindow
from terminalui.window_area import WindowArea


class WelcomeScreen(BaseScreen):
    '''First screen of the SCI tool.
    No special __init__ needed beyond that provided by BaseScreen
    
    '''
    
    HEADER_TEXT = _("System Configuration Tool")
    WELCOME_TEXT = _("System Configuration Tool enables you to specify "
                     "the following configuration parameters for your "
                     "newly-installed Oracle Solaris 11 system:\n")
    NAVIPRO_TEXT = _("\nSystem Configuration Tool produces an SMF profile "
                     "file in %(scprof)s.\n\n"
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
    BULLET_INDENT = "  "
    HELP_DATA = (SCI_HELP + "/%s/welcome.txt",
                 _("Welcome and Navigation Instructions"))
    INDENT = 2  # begin text right of scroll bar
    
    def set_actions(self):
        '''Remove the F3_Back Action from the first screen'''
        self.main_win.actions.pop(self.main_win.back_action.key, None)
    
    def _show(self):
        '''Display the static paragraph WELCOME_TEXT and all
           applicable bullet items'''
        sc_options = get_sc_options_from_doc()
        max_width = self.win_size_x - WelcomeScreen.INDENT - 1
        text = convert_paragraph(WelcomeScreen.WELCOME_TEXT, max_width)
        # list configuration groups in a comma-separated list with
        # bullet on first line and indentation on subsequent lines
        grouplist = list()
        if configure_group(SC_GROUP_NETWORK):
            grouplist.append(_("network"))
        elif configure_group(SC_GROUP_IDENTITY):
            grouplist.append(_("system hostname"))
        if configure_group(SC_GROUP_LOCATION):
            grouplist.append(_("time zone"))
        if configure_group(SC_GROUP_DATETIME):
            grouplist.append(_("date and time"))
        if configure_group(SC_GROUP_USERS):
            grouplist.append(_("user and root accounts"))
        if configure_group(SC_GROUP_NS):
            grouplist.append(_("name services"))
        grouplist = ", ".join(grouplist)
        grouplist = convert_paragraph(grouplist,
                                      max_width - len(WelcomeScreen.BULLET))
        for ln in range(len(grouplist)):
            if ln == 0:
                text.append(WelcomeScreen.BULLET + grouplist[ln])
            else:
                text.append(WelcomeScreen.BULLET_INDENT + grouplist[ln])
        # display navigation instructions and profile path
        fmt = {"scprof": sc_options.profile}
        text.extend(convert_paragraph(WelcomeScreen.NAVIPRO_TEXT % fmt,
                                      max_width))
        # indent and align while bulletting
        for bullet in WelcomeScreen.BULLET_ITEMS:
            btext = convert_paragraph(bullet,
                                      max_width - len(WelcomeScreen.BULLET))
            for ln in range(len(btext)):
                if ln == 0:
                    text.append(WelcomeScreen.BULLET + btext[ln])
                else:
                    text.append(WelcomeScreen.BULLET_INDENT + btext[ln])
        # prepare welcome text in entire window for scrolling
        area = WindowArea(x_loc=0, y_loc=1, scrollable_lines=(len(text) + 1))
        area.lines = self.win_size_y - 1
        area.columns = self.win_size_x
        scroll_region = ScrollWindow(area, window=self.center_win)
        scroll_region.add_paragraph(text, start_x=WelcomeScreen.INDENT)
        self.center_win.activate_object(scroll_region)

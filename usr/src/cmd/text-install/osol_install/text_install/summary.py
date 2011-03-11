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
Display a summary of the user's selections
'''

import curses
import logging

from osol_install.profile.disk_info import SliceInfo
from osol_install.profile.install_profile import INSTALL_PROF_LABEL
from osol_install.text_install import _, RELEASE, TUI_HELP
from solaris_install.engine import InstallEngine
import solaris_install.sysconfig.profile
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.user_info import UserInfo
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.i18n import convert_paragraph
from terminalui.window_area import WindowArea
from terminalui.scroll_window import ScrollWindow


class SummaryScreen(BaseScreen):
    '''Display a summary of the install profile to the user
    InnerWindow.__init__ is sufficient to initalize an instance
    of SummaryScreen
    
    '''
    
    HEADER_TEXT = _("Installation Summary")
    PARAGRAPH = _("Review the settings below before installing."
                                " Go back (F3) to make changes.")
    
    HELP_DATA = (TUI_HELP + "/%s/summary.txt",
                 _("Installation Summary"))
    
    INDENT = 2
    
    def set_actions(self):
        '''Replace the default F2_Continue with F2_Install'''
        install_action = Action(curses.KEY_F2, _("Install"),
                                self.main_win.screen_list.get_next)
        self.main_win.actions[install_action.key] = install_action
    
    def _show(self):
        '''Prepare a text summary from the install_profile and display it
        to the user in a ScrollWindow
        
        '''
        doc = InstallEngine.get_instance().doc
        self.install_profile = doc.get_descendants(name=INSTALL_PROF_LABEL,
                                                   not_found_is_err=True)[0]
        
        self.sysconfig = solaris_install.sysconfig.profile.from_engine()
        
        y_loc = 1
        y_loc += self.center_win.add_paragraph(SummaryScreen.PARAGRAPH, y_loc)
        
        y_loc += 1
        summary_text = self.build_summary()
        # Wrap the summary text, accounting for the INDENT (used below in
        # the call to add_paragraph)
        max_chars = self.win_size_x - SummaryScreen.INDENT - 1
        summary_text = convert_paragraph(summary_text, max_chars)
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=(len(summary_text)+1))
        area.lines = self.win_size_y - y_loc
        area.columns = self.win_size_x
        scroll_region = ScrollWindow(area, window=self.center_win)
        scroll_region.add_paragraph(summary_text, start_x=SummaryScreen.INDENT)
        
        self.center_win.activate_object(scroll_region)
    
    def build_summary(self):
        '''Build a textual summary from the install_profile'''
        lines = []
        
        lines.append(_("Software: %s") % self.get_release())
        lines.append("")
        lines.append(self.get_disk_summary())
        lines.append("")
        lines.append(self.get_tz_summary())
        lines.append("")
        lines.append(_("Language: *The following can be changed when "
                       "logging in."))
        if self.sysconfig.system.locale is None:
            self.sysconfig.system.determine_locale()
        lines.append(_("  Default language: %s") %
                     self.sysconfig.system.actual_lang)
        lines.append("")
        lines.append(_("Keyboard layout: *The following can be "
                       "changed when logging in."))
        lines.append(_("  Default keyboard layout: %s") %
                     self.sysconfig.system.keyboard)
        lines.append("")
        lines.append(_("Terminal type: %s") %
                     self.sysconfig.system.terminal_type)
        lines.append("")
        lines.append(_("Users:"))
        lines.extend(self.get_users())
        lines.append("")
        lines.append(_("Network:"))
        lines.extend(self.get_networks())
        
        return "\n".join(lines)
    
    def get_networks(self):
        '''Build a summary of the networks in the install_profile,
        returned as a list of strings
        
        '''
        network_summary = []
        network_summary.append(_("  Computer name: %s") %
                               self.sysconfig.system.hostname)
        nic = self.sysconfig.nic
        
        if nic.type == NetworkInfo.AUTOMATIC:
            network_summary.append(_("  Network Configuration: Automatic"))
        elif nic.type == NetworkInfo.NONE:
            network_summary.append(_("  Network Configuration: None"))
        else:
            network_summary.append(_("  Manual Configuration: %s")
                                   % nic.nic_name)
            network_summary.append(_("    IP Address: %s") % nic.ip_address)
            network_summary.append(_("    Netmask: %s") % nic.netmask)
            if nic.gateway:
                network_summary.append(_("    Router: %s") % nic.gateway)
            if  nic.dns_address:
                network_summary.append(_("    DNS: %s") % nic.dns_address)
            if nic.domain:
                network_summary.append(_("    Domain: %s") % nic.domain)
        return network_summary
    
    def get_users(self):
        '''Build a summary of the user information, and return it as a list
        of strings
        
        '''
        root = self.sysconfig.users[UserInfo.ROOT_IDX]
        primary = self.sysconfig.users[UserInfo.PRIMARY_IDX]
        user_summary = []
        if not root.password:
            user_summary.append(_("  Warning: No root password set"))
        if primary.login_name:
            user_summary.append(_("  Username: %s") % primary.login_name)
        else:
            user_summary.append(_("  No user account"))
        return user_summary
    
    def get_disk_summary(self):
        '''Return a string summary of the disk selection'''
        disk = self.install_profile.disk
        
        solaris_data = disk.get_solaris_data()
        if isinstance(solaris_data, SliceInfo):
            slice_data = solaris_data
            part_data = None
        else:
            part_data = solaris_data
            slice_data = part_data.get_solaris_data()
        
        format_dict = {}
        disk_string = [_("Disk: %(disk-size).1fGB %(disk-type)s")]
        format_dict['disk-size'] = disk.size.size_as("gb")
        format_dict['disk-type'] = disk.type
        
        if part_data is not None:
            disk_string.append(_("Partition: %(part-size).1fGB %(part-type)s"))
            format_dict['part-size'] = part_data.size.size_as("gb")
            format_dict['part-type'] = part_data.get_description()
        
        if part_data is None or not part_data.use_whole_segment:
            disk_string.append(_("Slice %(slice-num)i: %(slice-size).1fGB"
                                 " %(pool)s"))
            format_dict['slice-num'] = slice_data.number
            format_dict['slice-size'] = slice_data.size.size_as("gb")
            format_dict['pool'] = slice_data.type[1]
        
        return "\n".join(disk_string) % format_dict
    
    def get_tz_summary(self):
        '''Return a string summary of the timezone selection'''
        timezone = self.sysconfig.system.tz_timezone
        return _("Time Zone: %s") % timezone
    
    @staticmethod
    def get_release():
        '''Read in the release information from /etc/release'''
        try:
            try:
                release_file = open("/etc/release")
            except IOError:
                logging.warn("Could not read /etc/release")
                release_file = None
                release = RELEASE['release']
            else:
                release = release_file.readline()
        finally:
            if release_file is not None:
                release_file.close()
        return release.strip()

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
Support for editing the hostname and, if any wired NICs are found, selecting
how to configure them
'''

import logging

from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig import _, SCI_HELP
import solaris_install.sysconfig.profile
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.system_info import SystemInfo
from terminalui.base_screen import BaseScreen, UIMessage
from terminalui.edit_field import EditField
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


LOGGER = None


class NetworkTypeScreen(BaseScreen):
    '''
    Let the user:
    - Choose the hostname
    - Select network type (Automatic, Manual, or None)
    '''
    
    HEADER_TEXT = _("Network")
    PARAGRAPH = _("Enter a name for this computer that identifies it on "
                  "the network. It must be at least two characters. It "
                  "can contain letters, numbers, and minus signs (-).")
    HOSTNAME_TEXT = _("Computer Name: ")
    NET_TYPE_TEXT = _("Select how the wired ethernet network "
                      "connection is configured.")
    AUTO_TEXT = _("Automatically")
    AUTO_DETAIL = _("Automatically configure the connection")
    MANUAL_TEXT = _("Manually")
    MANUAL_DETAIL = _("Enter the information on the following screen")
    NONE_TEXT = _("None")
    NONE_DETAIL = _("Do not configure the network at this time")
    NO_NICS_FOUND = _("No wired network interfaces found. Additional "
                      "device drivers may be needed.")
    ALL_NICS_FROMGZ = _("No configurable network interfaces found. They are "
                        "all controlled from global zone.")
    
    ITEM_OFFSET = 2
    ITEM_MAX_WIDTH = 17
    ITEM_DESC_OFFSET = ITEM_MAX_WIDTH + ITEM_OFFSET + 1
    HOSTNAME_SCREEN_LEN = 25
    
    HELP_DATA = (SCI_HELP + "/%s/network.txt", _("Network"))
    
    def __init__(self, main_win, configure_network=False):
        global LOGGER
        if LOGGER is None:
            LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
        
        super(NetworkTypeScreen, self).__init__(main_win)
        self.hostfield_offset = textwidth(NetworkTypeScreen.HOSTNAME_TEXT)
        self.menu_item_desc_max = (self.win_size_x -
                                   NetworkTypeScreen.ITEM_DESC_OFFSET)
        
        self.net_type_dict = {}
        self.sys_info = None
        self.automatic = None
        self.manual = None
        self.none_option = None
        self.hostname = None
        self.nic_info = NetworkInfo()

        # find_links() returns tuple containing
        #  * dictionary of configurable NICs
        #  * number of NICs mandated from global zone.
        #
        # Taking that information into account, initialize type
        # of network configuration:
        #  * FROMGZ - One or more link found, but all found links are
        #             controlled from global zone.
        #  * None - otherwise
        #
        # Set 'have_nic' flag to True if there is at least one configurable
        # link, otherwise set the flag to False.
        #
        self.ether_nics, self.fromgz_num = NetworkInfo.find_links()
        self.nic_info.type = None
        self.have_nic = True
        if len(self.ether_nics) == 0:
            self.have_nic = False
            if self.fromgz_num > 0:
                self.nic_info.type = NetworkInfo.FROMGZ

        self.configure_network = configure_network
    
    def _show(self):
        '''Create an EditField for entering hostname, and list items
        for each of the network types
        
        '''
        sc_profile = solaris_install.sysconfig.profile.from_engine()
        
        if sc_profile.system is None:
            sc_profile.system = SystemInfo()
        self.sys_info = sc_profile.system
        if sc_profile.nic is None:
            sc_profile.nic = self.nic_info
        
        y_loc = 1
        
        y_loc += self.center_win.add_paragraph(NetworkTypeScreen.PARAGRAPH,
                                               y_loc)
        
        y_loc += 1
        self.center_win.add_text(NetworkTypeScreen.HOSTNAME_TEXT, y_loc)
        
        max_cols = self.win_size_x - self.hostfield_offset
        cols = min(max_cols, NetworkTypeScreen.HOSTNAME_SCREEN_LEN)
        scrollable_columns = SystemInfo.MAX_HOSTNAME_LEN + 1
        hostname_area = WindowArea(1, cols, y_loc, self.hostfield_offset,
                                   scrollable_columns=scrollable_columns)
        self.hostname = EditField(hostname_area, 
                                  window=self.center_win,
                                  text=self.sys_info.hostname,
                                  validate=hostname_is_valid,
                                  error_win=self.main_win.error_line)
        self.hostname.item_key = None

        # Display network configuration part of screen only if applicable.
        if self.configure_network:
            y_loc += 3

            # If there are no configurable links, there is no point to let
            # user select type of network configuration.
            if not self.have_nic:
                # Inform user that no network interfaces were found
                # on the system.
                # If this is the case of non-global zone with all links
                # mandated from global zone, be more specific.
                if self.nic_info.type == NetworkInfo.FROMGZ:
                    self.center_win.add_paragraph(
                        NetworkTypeScreen.ALL_NICS_FROMGZ, y_loc, 1)
                else:
                    self.center_win.add_paragraph(
                        NetworkTypeScreen.NO_NICS_FOUND, y_loc, 1)

                self.main_win.do_update()
                activate = self.net_type_dict.get(self.nic_info.type,
                                                  self.hostname)
                self.center_win.activate_object(activate)
                return
        
            y_loc += self.center_win.add_paragraph(
                     NetworkTypeScreen.NET_TYPE_TEXT, y_loc)
        
            y_loc += 1
            item_area = WindowArea(1, NetworkTypeScreen.ITEM_MAX_WIDTH, y_loc,
                                   NetworkTypeScreen.ITEM_OFFSET)
            self.automatic = ListItem(item_area, window=self.center_win,
                                      text=NetworkTypeScreen.AUTO_TEXT)
            self.automatic.item_key = NetworkInfo.AUTOMATIC
            self.net_type_dict[self.automatic.item_key] = self.automatic
            self.center_win.add_text(NetworkTypeScreen.AUTO_DETAIL, y_loc,
                                     NetworkTypeScreen.ITEM_DESC_OFFSET,
                                     self.menu_item_desc_max)
        
            y_loc += 2
            item_area.y_loc = y_loc
            self.manual = ListItem(item_area, window=self.center_win,
                                   text=NetworkTypeScreen.MANUAL_TEXT)
            self.manual.item_key = NetworkInfo.MANUAL
            self.net_type_dict[self.manual.item_key] = self.manual
            self.center_win.add_text(NetworkTypeScreen.MANUAL_DETAIL, y_loc,
                                     NetworkTypeScreen.ITEM_DESC_OFFSET,
                                     self.menu_item_desc_max)

            y_loc += 2
            item_area.y_loc = y_loc
            self.none_option = ListItem(item_area, window=self.center_win,
                                        text=NetworkTypeScreen.NONE_TEXT)
            self.none_option.item_key = NetworkInfo.NONE
            self.net_type_dict[self.none_option.item_key] = self.none_option
            self.center_win.add_text(NetworkTypeScreen.NONE_DETAIL, y_loc,
                                     NetworkTypeScreen.ITEM_DESC_OFFSET,
                                     self.menu_item_desc_max)
        
        self.main_win.do_update()
        activate = self.net_type_dict.get(self.nic_info.type,
                                          self.hostname)
        self.center_win.activate_object(activate)
    
    def on_change_screen(self):
        '''Save hostname and selected network type on change screen'''
        if self.configure_network and self.have_nic:
            self.nic_info.type = self.center_win.get_active_object().item_key

        LOGGER.info("Configuring NIC as: %s", self.nic_info.type)
        self.sys_info.hostname = self.hostname.get_text()
    
    def validate(self):
        '''Ensure hostname is set and a network type is chosen (unless no
        NICs are present)
        
        '''
        hostname_text = self.hostname.get_text()
        if not hostname_text:
            raise UIMessage(_("A Hostname is required."))
        if len(hostname_text) < 2:
            raise UIMessage(_("A Hostname must be at least two characters."))
        if self.configure_network and self.have_nic:
            item_key = self.center_win.get_active_object().item_key
            if item_key not in self.net_type_dict:
                raise UIMessage(_("Select the wired network configuration: "
                                   "Automatically, Manually, or None."))


def hostname_is_valid(edit_field):
    '''Check hostname for characters other than a-zA-Z0-9 and hyphens'''
    user_str = edit_field.get_text()
    if not user_str:
        return True
    test_str = user_str.replace(u"-", "a")
    if not test_str.isalnum():
        raise UIMessage(_("The Hostname can only contain letters, numbers, "
                            "and minus signs (-)."))

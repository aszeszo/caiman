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
Allow user to configure a single NIC with manual network information
'''

import logging

from osol_install.profile.ip_address import IPAddress
from osol_install.profile.network_info import NetworkInfo
from osol_install.text_install import _
from osol_install.text_install.base_screen import BaseScreen, \
                                                  SkipException, \
                                                  UIMessage
from osol_install.text_install.edit_field import EditField
from osol_install.text_install.list_item import ListItem
from osol_install.text_install.window_area import WindowArea

class NICConfigure(BaseScreen):
    '''
    Manually configure a single NIC to use a static IP
    '''
    
    HEADER_TEXT = _("Manually Configure: %s")
    
    PARAGRAPH = _("Enter the configuration for the this network"
                  " connection. All entries, except Domain, "
                  "must contain four sets of numbers, 0 to 255,"
                  " separated by periods.")
    IP_LABEL = _("IP Address:")
    IP_DESCRIPTION = _("Must be unique for this network")
    NETMASK_LABEL = _("Netmask:")
    NETMASK_DESCRIPTION = _("Your subnet use may require a different mask")
    GATEWAY_LABEL = _("Gateway:")
    GATEWAY_DESCRIPTION = _("The IP address of the gateway on this subnet")
    DNS_LABEL = _("DNS:")
    DNS_FOUND = _("A DNS server was found on the network")
    DNS_NOT_FOUND = _("Address of the Domain Name Server")
    DOMAIN_LABEL = _("Domain:")
    DOMAIN_FOUND = _("The machine appears to be in this domain")
    DOMAIN_NOT_FOUND = _("The network's domain name")
    
    ITEM_OFFSET = 2
    EDIT_FIELD_LEN = 16
    
    
    def __init__(self, main_win):
        super(NICConfigure, self).__init__(main_win)
        self.dns_description = None
        self.domain_description = None
        item_length = max(len(NICConfigure.IP_LABEL),
                          len(NICConfigure.NETMASK_LABEL),
                          len(NICConfigure.GATEWAY_LABEL),
                          len(NICConfigure.DNS_LABEL),
                          len(NICConfigure.DOMAIN_LABEL))
        item_length += 1
        list_width = item_length + NICConfigure.EDIT_FIELD_LEN
        self.list_area = WindowArea(1, list_width, 0, NICConfigure.ITEM_OFFSET)
        self.edit_area = WindowArea(1, NICConfigure.EDIT_FIELD_LEN, 0,
                                    item_length)
        self.ip_field = None
        self.netmask_field = None
        self.gateway_field = None
        self.dns_field = None
        self.domain_field = None
        self.nic = None
    
    def _show(self):
        '''Create the editable fields for IP address, netmask, gateway,
        dns address and dns domain
        
        '''
        self.nic = self.install_profile.nic
        if self.nic.type != NetworkInfo.MANUAL:
            raise SkipException
        
        nic_name = self.nic.nic_name
        
        if self.nic.find_defaults:
            self.set_defaults(self.nic)
        
        self.main_win.set_header_text(NICConfigure.HEADER_TEXT % nic_name)
        
        max_y = self.win_size_y - 16
        max_x = self.win_size_x - 1
        y_loc = 1
        y_loc += self.center_win.add_paragraph(NICConfigure.PARAGRAPH, y_loc,
                                               max_y=max_y)
        
        max_y = 3
        description_start = (NICConfigure.ITEM_OFFSET * 2 +
                             self.list_area.columns)
        y_loc += 1
        
        self.ip_field = self.make_field(NICConfigure.IP_LABEL,
                                        NICConfigure.IP_DESCRIPTION,
                                        y_loc, max_y, max_x,
                                        description_start,
                                        self.nic.ip_address)
        
        y_loc += max_y
        self.netmask_field = self.make_field(NICConfigure.NETMASK_LABEL,
                                             NICConfigure.NETMASK_DESCRIPTION,
                                             y_loc, max_y, max_x,
                                             description_start,
                                             self.nic.netmask)
        
        y_loc += max_y
        self.gateway_field = self.make_field(NICConfigure.GATEWAY_LABEL,
                                             NICConfigure.GATEWAY_DESCRIPTION,
                                             y_loc, max_y, max_x,
                                             description_start,
                                             self.nic.gateway)
        
        y_loc += max_y
        self.dns_field = self.make_field(NICConfigure.DNS_LABEL,
                                         self.dns_description,
                                         y_loc, max_y, max_x,
                                         description_start,
                                         self.nic.dns_address)
        
        y_loc += max_y
        self.domain_field = self.make_field(NICConfigure.DOMAIN_LABEL,
                                            self.domain_description, y_loc,
                                            max_y, max_x, description_start,
                                            self.nic.domain,
                                            is_ip=False)
        
        self.main_win.do_update()
        self.center_win.activate_object()
    
    def make_field(self, label, description, y_loc, max_y, max_x,
                   description_start, default_val, is_ip=True):
        '''Create a list item with 'label', add an editable field with
        'default_val', and add additional 'description' text following it
        
        '''
        self.list_area.y_loc = y_loc
        list_item = ListItem(self.list_area, text=label, data_obj=label,
                             window=self.center_win)
        if is_ip:
            validate = incremental_validate_IP
        else:
            validate = None
        edit_field = EditField(self.edit_area, window=list_item,
                               text=default_val, validate=validate,
                               error_win=self.main_win.error_line,
                               data_obj=label.rstrip(":"))
        self.center_win.add_paragraph(description, y_loc, description_start,
                                      max_y=(y_loc + max_y), max_x=max_x)
        return edit_field
    
    def validate(self):
        '''Verify the syntactical validity of the IP Address fields'''
        ip_fields = [self.ip_field,
                     self.netmask_field,
                     self.gateway_field,
                     self.dns_field]
        for field in ip_fields:
            validate_ip(field)
        
        if not self.ip_field.get_text():
            raise UIMessage(_("IP Address must not be empty"))
        if not self.netmask_field.get_text():
            raise UIMessage(_("Netmask must not be empty"))
        if self.domain_field.get_text() and not self.dns_field.get_text():
            raise UIMessage(_("DNS server required if Domain set"))
    
    def on_change_screen(self):
        '''Preserve all data on screen changes'''
        self.nic.ip_address = self.ip_field.get_text()
        self.nic.netmask = self.netmask_field.get_text()
        self.nic.gateway = self.gateway_field.get_text()
        self.nic.dns_address = self.dns_field.get_text()
        self.nic.domain = self.domain_field.get_text()
        self.nic.find_defaults = False
        logging.debug("Setting network to:\n%s", self.nic)
    
    def set_defaults(self, nic):
        '''Attempt to find DNS information for the selected NIC, and update
        the descriptive text based on the result
        
        '''
        if nic.find_dns():
            self.dns_description = NICConfigure.DNS_FOUND
        else:
            self.dns_description = NICConfigure.DNS_NOT_FOUND
        if nic.find_domain():
            self.domain_description = NICConfigure.DOMAIN_FOUND
        else:
            self.domain_description = NICConfigure.DOMAIN_NOT_FOUND


def validate_ip(edit_field):
    '''Wrap a call to IPAddress.check_address and raise a UIMessage with
    appropriate message text
    
    '''
    ip_address = edit_field.get_text()
    if not ip_address:
        return True
    try:
        IPAddress.convert_address(ip_address)
    except ValueError:
        raise UIMessage(_("%s must be of the form xxx.xxx.xxx.xxx") %
                        edit_field.data_obj)
    return True

# pylint: disable-msg=C0103
# IP is an abbreviation and appropriately capitalized here
def incremental_validate_IP(edit_field):
    '''Incrementally validate the IP Address as the user enters it'''
    ip_address = edit_field.get_text()
    if not ip_address:
        return True
    try:
        IPAddress.incremental_check(ip_address)
    except ValueError:
        raise UIMessage(_("%s must be of the form xxx.xxx.xxx.xxx") %
                        edit_field.data_obj)
    return True

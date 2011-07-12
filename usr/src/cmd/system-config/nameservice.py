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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Name service selection screens
'''

import logging
import nss
import re
import string

from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig import _, SC_GROUP_NETWORK, SCI_HELP, \
        configure_group
import solaris_install.sysconfig.profile
from solaris_install.sysconfig.profile.ip_address import IPAddress
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.nameservice_info import NameServiceInfo
from terminalui.base_screen import BaseScreen, SkipException, UIMessage
from terminalui.edit_field import EditField
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.scroll_window import ScrollWindow
from terminalui.window_area import WindowArea


LOGGER = None
INDENT = 2          # standard left-side indentation
MAXIP = 16          # maximum width of IP address plus one
MAXDNSSEARCH = 6    # number of domain names on DNS search list
MAXDOMAINLEN = 255  # maximum possible length of a domain
MAXDNLEN = 256      # maximum allowed length of a distinguished name

# pre-compile patterns used in incremental validation
NO_WHITE_NO_SPECIAL_PATTERN = re.compile(r'^[A-Z0-9\-_]+$')
INCREMENTAL_DOMAIN_LABEL_PATTERN = re.compile(r'^[A-Z0-9\-]{0,63}$')
DOMAIN_LABEL_PATTERN = re.compile(r'^[A-Z0-9\-]{1,63}$')


class NameService(BaseScreen):
    HELP_FORMAT = "  %s"
    '''Allow user to select name service '''
    # dimensions
    SCROLL_SIZE = 2
    BORDER_WIDTH = (0, 3)
    # name service choices for display to user
    USER_CHOICE_LIST = [_('DNS'), _('LDAP'), _('NIS'), _('None')]
    # identify name service choices for internal use
    CHOICE_LIST = ['DNS', 'LDAP', 'NIS', None]

    def __init__(self, main_win, screen=None):
        global LOGGER
        if LOGGER is None:
            LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
        super(NameService, self).__init__(main_win)
        self.cur_nschoice_idx = self.CHOICE_LIST.index("DNS")
        self.cur_pbchoice_idx = NameServiceInfo.LDAP_CHOICE_NO_PROXY_BIND
        self.cur_nisnschoice_idx = NameServiceInfo.NIS_CHOICE_AUTO
        self.intro = "DEVELOPER: define intro in subclass"
        # screen controls
        self.nameservice = None
        self.domain = None
        self.dns_server_list = []
        self.dns_search_list = []
        self.ldap_profile = None
        self.ldap_ip = None
        self.ldap_pb_dn = None
        self.ldap_pb_psw = None
        self.nis_ip = None
        self.scroll_region = None

    def _show(self):
        ''' called upon display of a screen '''
        sc_profile = solaris_install.sysconfig.profile.from_engine()
        if sc_profile.nic.type != NetworkInfo.MANUAL and \
                configure_group(SC_GROUP_NETWORK):
            raise SkipException
        if sc_profile.nameservice is None:
            # first time, assign sysconfig values to defaults found above
            LOGGER.debug('assigning NSV to sysconfig.profile')
            sc_profile.nameservice = NameServiceInfo()
            nic = sc_profile.nic
            LOGGER.info("Found NIC:")
            LOGGER.info(nic)
            # if values were learned from the NIC, offer those as defaults
            if nic.domain:
                sc_profile.nameservice.domain = nic.domain
            if nic.dns_address:
                sc_profile.nameservice.dns_server = nic.dns_address
        self.nameservice = sc_profile.nameservice

    def _paint_opening(self):
        ''' paint screen with opening paragraph and blank line
        Returns the row (y-offset) after the blank line '''
        self.center_win.border_size = NameService.BORDER_WIDTH
        return 2 + self.center_win.add_paragraph(self.intro, 1)


class NSChooser(NameService):

    HEADER_TEXT = _("Name Service")
    HELP_DATA = (SCI_HELP + "/%s/name_service.txt", HEADER_TEXT)
    HELP_FORMAT = "%s"

    def __init__(self, main_win):
        super(NSChooser, self).__init__(main_win)
        LOGGER.debug('in NSChooser init')
        self.intro = \
                _("Select the name service that will be used by this "
                  "system. Select None if the desired name service is not "
                  "listed.")

    def _show(self):
        ''' called upon display of a screen '''
        super(NSChooser, self)._show()
        y_loc = self._paint_opening()
        LOGGER.debug(self.nameservice)
        area = WindowArea(x_loc=0, y_loc=y_loc,
                        scrollable_lines=len(NameService.USER_CHOICE_LIST) + 1)
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        # add the entries to the screen
        menu_item_max_width = self.win_size_x - NameService.SCROLL_SIZE
        for idx, nsn in enumerate(NameService.USER_CHOICE_LIST):
            y_loc += 1
            hilite = min(menu_item_max_width, textwidth(nsn) + 1)
            win_area = WindowArea(1, hilite, idx, INDENT)
            ListItem(win_area, window=self.scroll_region, text=nsn,
                     data_obj=nsn)
        self.main_win.do_update()
        self.center_win.activate_object(self.scroll_region)
        self.scroll_region.activate_object_force(self.cur_nschoice_idx,
                                                 force_to_top=True)

    def on_change_screen(self):
        ''' called when changes submitted by user for all screens '''
        # Save the chosen index and object when leaving the screen
        self.cur_nschoice_idx = self.scroll_region.active_object
        idx = self.cur_nschoice_idx
        LOGGER.info("on_change_screen NS chosen=%s", idx)
        self.nameservice.nameservice = NameService.CHOICE_LIST[idx]


class NSDomain(NameService):

    HEADER_TEXT = _("Domain Name")
    HELP_DATA = (SCI_HELP + "/%s/domain.txt", HEADER_TEXT)

    def __init__(self, main_win, screen=None):
        super(NSDomain, self).__init__(main_win)
        self.intro = \
                _("Specify the domain where this system resides. "
                  "Use the domain name's exact capitalization and "
                  "punctuation.")
        self.title = _("Domain Name:")

    def _show(self):
        ''' show domain '''
        super(NSDomain, self)._show()
        if self.nameservice.nameservice is None:
            raise SkipException
        y_loc = self._paint_opening()
        cols = min(MAXDOMAINLEN + 1,
                   self.win_size_x - textwidth(self.title) - INDENT - 1)
        self.center_win.add_text(self.title, y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, textwidth(self.title) + INDENT + 1,
                          scrollable_columns=MAXDOMAINLEN + 1)
        self.domain = EditField(area, window=self.center_win,
                                text=self.nameservice.domain,
                                validate=incremental_validate_domain,
                                error_win=self.main_win.error_line)
        self.main_win.do_update()
        self.center_win.activate_object(self.domain)

    def validate(self):
        validate_domain(self.domain.get_text(), allow_empty=False)

    def on_change_screen(self):
        self.nameservice.domain = self.domain.get_text()
        # default in LDAP-formatted values for domain
        if self.nameservice.nameservice == 'LDAP':
            ns = self.nameservice
            ldapdom = _convert_to_ldap_domain(ns.domain)
            # default in search base from domain
            if not ns.ldap_search_base or \
                    not ns.ldap_search_base.startswith(ldapdom):
                ns.ldap_search_base = ldapdom
            # default in distinguished name from search base 
            if not ns.ldap_pb_dn:
                # provide probable DN default
                ns.ldap_pb_dn = 'cn=proxyagent,ou=profile,' + \
                        ns.ldap_search_base
            elif not ns.ldap_pb_dn.endswith(ns.ldap_search_base):
                # user changed search base, update DN
                dnsplit = ns.ldap_pb_dn.split(',dc=')
                # replace old search base with new
                if len(dnsplit) > 0 and dnsplit[0]:
                    ns.ldap_pb_dn = dnsplit[0] + ',' + ns.ldap_search_base


class NSDNSServer(NameService):

    HEADER_TEXT = _("DNS Server Addresses")
    HELP_DATA = (SCI_HELP + "/%s/dns_server.txt", HEADER_TEXT)

    def __init__(self, main_win, screen=None):
        super(NSDNSServer, self).__init__(main_win)
        self.intro = \
                _("Enter the IP address of the DNS server(s). "
                  "At least one IP address is required.")
        self.title = _("DNS Server IP address:")

    def _show(self):
        super(NSDNSServer, self)._show()
        # check dictionary of screens associated with name service selections
        if self.nameservice.nameservice != 'DNS':
            raise SkipException
        y_loc = self._paint_opening()
        self.dns_server_list = []
        find_1st_nonblank = None
        find_last_nonblank = -1
        for i in range(NameServiceInfo.MAXDNSSERV):
            self.center_win.add_text(self.title, y_loc, INDENT)
            area = WindowArea(1, MAXIP, y_loc,
                              textwidth(self.title) + INDENT + 1)
            y_loc += 1
            if i < len(self.nameservice.dns_server) and \
                    self.nameservice.dns_server[i] is not None:
                text = self.nameservice.dns_server[i]
            else:
                text = ''
            # find first blank field or last non-blank field
            if text:
                find_last_nonblank = i
            elif find_1st_nonblank is None:
                find_1st_nonblank = i
            self.dns_server_list += [EditField(area, window=self.center_win,
                                           text=text,
                                           validate=incremental_validate_ip,
                                           error_win=self.main_win.error_line)]
        self.main_win.do_update()
        # position cursor on first blank or after last field
        if find_1st_nonblank is None:
            idx = min(find_last_nonblank + 1, NameServiceInfo.MAXDNSSERV - 1)
        else:
            idx = find_1st_nonblank
        self.center_win.activate_object(self.dns_server_list[idx])

    def validate(self):
        found = False
        for field in self.dns_server_list:
            validate_ip(field.get_text())
            if field.get_text():
                found = True
        if not found:
            raise UIMessage(
                    _("At least one name server must be specified."))

    def on_change_screen(self):
        dnsl = []
        for i in range(NameServiceInfo.MAXDNSSERV):
            dnsl.append(self.dns_server_list[i].get_text())
        self.nameservice.dns_server = dnsl


class NSDNSSearch(NameService):

    HEADER_TEXT = _("DNS Search List")
    HELP_DATA = (SCI_HELP + "/%s/dns_search.txt", HEADER_TEXT)

    def __init__(self, main_win, screen=None):
        super(NSDNSSearch, self).__init__(main_win)
        self.intro = \
                _("Enter a list of domains to be searched when a DNS "
                  "query is made. If no domain is entered, only the "
                  "DNS domain chosen for this system will be searched.")
        self.title = _("Search domain:")

    def _show(self):
        ''' show DNS search list '''
        super(NSDNSSearch, self)._show()
        # check dictionary of screens associated with name service selections
        if self.nameservice.nameservice != 'DNS':
            raise SkipException
        y_loc = self._paint_opening()
        cols = min(MAXDOMAINLEN + 1,
                   self.win_size_x - textwidth(self.title) - INDENT - 1)
        self.dns_search_list = []
        find_1st_nonblank = None
        find_last_nonblank = -1
        LOGGER.info(self.nameservice.dns_search)
        for i in range(MAXDNSSEARCH):
            self.center_win.add_text(text=self.title, start_y=y_loc,
                                     start_x=INDENT)
            area = WindowArea(1, cols, y_loc,
                              textwidth(self.title) + INDENT + 1)
            y_loc += 1
            if i == 0 and self.nameservice.domain:
                # default in domain user already entered
                text = self.nameservice.domain
                find_last_nonblank = 0
            elif i < len(self.nameservice.dns_search) and \
                    self.nameservice.dns_search[i] is not None:
                text = self.nameservice.dns_search[i]
            else:
                text = ''
            # find first blank field or last non-blank field
            if text:
                find_last_nonblank = i
            elif find_1st_nonblank is None:
                find_1st_nonblank = i
            edf = EditField(area, window=self.center_win,
                            text=text,
                            validate=incremental_validate_domain,
                            error_win=self.main_win.error_line)
            self.dns_search_list += [edf]
        self.main_win.do_update()
        # position cursor on first blank or after last field
        if find_1st_nonblank is None:
            idx = min(find_last_nonblank + 1, MAXDNSSEARCH - 1)
        else:
            idx = find_1st_nonblank
        self.center_win.activate_object(self.dns_search_list[idx])

    def validate(self):
        for field in self.dns_search_list:
            validate_domain(field.get_text())

    def on_change_screen(self):
        dnsl = []
        for i in range(MAXDNSSEARCH):
            dnsl.append(self.dns_search_list[i].get_text())
        self.nameservice.dns_search = dnsl


class NSLDAPProfile(NameService):

    HEADER_TEXT = _("LDAP Profile")
    HELP_DATA = (SCI_HELP + "/%s/ldap_profile.txt", HEADER_TEXT)

    def __init__(self, main_win):
        super(NSLDAPProfile, self).__init__(main_win)
        self.intro = \
                _("Specify the name of the LDAP profile to be used to "
                  "configure this system and the IP address of the "
                  "server that contains the profile.")
        self.title = _("Profile name:")
        self.title2 = _("Profile server IP address:")
        self.title3 = _("Search base:")

    def _show(self):
        super(NSLDAPProfile, self)._show()
        if self.nameservice.nameservice != 'LDAP':
            raise SkipException
        y_loc = self._paint_opening()
        maxtitlelen = max(max(textwidth(self.title), textwidth(self.title2)),
                          textwidth(self.title3))
        aligned_x_loc = maxtitlelen + INDENT + 1
        cols = self.win_size_x - maxtitlelen - INDENT - 1
        self.center_win.add_text(self.title.rjust(maxtitlelen), y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, aligned_x_loc)
        self.ldap_profile = EditField(area, window=self.center_win,
                                      text=self.nameservice.ldap_profile,
                                      error_win=self.main_win.error_line,
                                      validate=inc_validate_nowhite_nospecial)
        # in case of error, tell user what is being validated
        self.ldap_profile.validate_kwargs['etext'] = _('profile name')
        y_loc += 1
        area = WindowArea(1, MAXIP, y_loc, aligned_x_loc)
        self.center_win.add_text(self.title2.rjust(maxtitlelen), y_loc, INDENT)
        self.ldap_ip = EditField(area, window=self.center_win,
                                 text=self.nameservice.ldap_ip,
                                 validate=incremental_validate_ip,
                                 error_win=self.main_win.error_line)
        # search base
        y_loc += 1
        self.center_win.add_text(self.title3.rjust(maxtitlelen), y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, aligned_x_loc,
                          scrollable_columns=MAXDNLEN + 1)
        self.ldap_search_base = EditField(area, window=self.center_win,
                                        text=self.nameservice.ldap_search_base,
                                        error_win=self.main_win.error_line)
        self.main_win.do_update()
        self.center_win.activate_object(self.ldap_ip)

    def validate(self):
        validate_ldap_profile(self.ldap_profile.get_text())
        validate_ip(self.ldap_ip.get_text())
        if not self.ldap_profile.get_text():
            raise UIMessage(_("The LDAP profile name cannot be blank."))
        if not self.ldap_ip.get_text():
            raise UIMessage(_("The LDAP server IP address cannot be blank."))

    def on_change_screen(self):
        self.nameservice.ldap_profile = self.ldap_profile.get_text()
        self.nameservice.ldap_ip = self.ldap_ip.get_text()
        self.nameservice.ldap_search_base = self.ldap_search_base.get_text()
        # update DN with any changes in search_base from user
        ldap_search_base = self.nameservice.ldap_search_base
        if not self.nameservice.ldap_pb_dn.endswith(ldap_search_base):
            dnsplit = self.nameservice.ldap_pb_dn.split(',dc=')
            if len(dnsplit) > 0 and dnsplit[0]:
                self.nameservice.ldap_pb_dn = dnsplit[0] + ',' + \
                        ldap_search_base


class NSLDAPProxyBindChooser(NameService):

    HEADER_TEXT = _("LDAP Proxy")
    HELP_DATA = (SCI_HELP + "/%s/ldap_proxy.txt", HEADER_TEXT)

    def __init__(self, main_win):
        super(NSLDAPProxyBindChooser, self).__init__(main_win)
        self.intro = _('Does the profile specify a proxy credential level '
                       'and an authentication method other than None?')

    def _show(self):
        super(NSLDAPProxyBindChooser, self)._show()
        # check dictionary of screens associated with name service selections
        if self.nameservice.nameservice != 'LDAP':
            raise SkipException
        y_loc = self._paint_opening()
        ynlist = [_('No'),
                  _('Yes')]
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=len(ynlist) + 1)
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        # add the entries to the screen
        for idx, yon in enumerate(ynlist):
            win_area = WindowArea(1, textwidth(yon) + 1, idx, INDENT)
            ListItem(win_area, window=self.scroll_region, text=yon,
                     data_obj=yon)
            self.main_win.do_update()
            self.center_win.activate_object(self.scroll_region)
            self.scroll_region.activate_object_force(self.cur_pbchoice_idx,
                                                     force_to_top=True)

    def on_change_screen(self):
        self.cur_pbchoice_idx = self.scroll_region.active_object
        idx = self.cur_pbchoice_idx
        self.nameservice.ldap_proxy_bind = idx


class NSLDAPProxyBindInfo(NameService):

    HEADER_TEXT = _("Specify LDAP Profile Proxy Bind Information")
    HELP_DATA = (SCI_HELP + "/%s/ldap_proxy.txt", HEADER_TEXT)

    def __init__(self, main_win, screen=None):
        super(NSLDAPProxyBindInfo, self).__init__(main_win)
        self.intro = \
                _("Specify the LDAP proxy bind distinguished name and the "
                  "LDAP proxy bind password.  The network administrator "
                  "can provide this information.")
        self.title = _("Proxy bind distinguished name:")
        # temporary code until ns1_convert method is integrated
        if hasattr(nss.nssscf, 'ns1_convert'):
            self.title2 = _("Proxy bind password:")
        else:
            self.title2 = _("Encrypted proxy bind password:")

    def _show(self):
        super(NSLDAPProxyBindInfo, self)._show()
        if self.nameservice.nameservice != 'LDAP':
            raise SkipException
        if self.nameservice.ldap_proxy_bind == \
                NameServiceInfo.LDAP_CHOICE_NO_PROXY_BIND:
            raise SkipException
        y_loc = self._paint_opening()
        y_loc += 1  # blank line
        self.center_win.add_text(self.title, y_loc, INDENT)
        y_loc += 1  # edit field on following line since it should be big
        cols = self.win_size_x - INDENT - 2
        area = WindowArea(1, cols, y_loc, INDENT + 2,
                          scrollable_columns=MAXDNLEN + 1)
        self.ldap_pb_dn = EditField(area, window=self.center_win,
                                    text=self.nameservice.ldap_pb_dn,
                                    error_win=self.main_win.error_line)
        # in case of error, tell user what is being validated
        self.ldap_pb_dn.validate_kwargs['etext'] = _('distinguished name')
        y_loc += 2  # blank line
        titlelen = textwidth(self.title2)
        self.center_win.add_text(self.title2, y_loc, NameService.SCROLL_SIZE)
        cols = self.win_size_x - titlelen - INDENT - 1
        area = WindowArea(1, cols, y_loc, titlelen + INDENT + 1)
        self.ldap_pb_psw = EditField(area, window=self.center_win,
                                     text=self.nameservice.ldap_pb_psw,
                                     error_win=self.main_win.error_line,
                                     masked=hasattr(nss.nssscf, 'ns1_convert'))
        self.main_win.do_update()
        self.center_win.activate_object(self.ldap_pb_dn)

    def validate(self):
        validate_ldap_proxy_dn(self.ldap_pb_dn.get_text())
        if not self.ldap_pb_dn.get_text():
            raise UIMessage(
                _("The LDAP proxy server distinguished name cannot be blank."))
        validate_ldap_proxy_bind_psw(self.ldap_pb_psw.get_text())

    def on_change_screen(self):
        self.nameservice.ldap_pb_dn = self.ldap_pb_dn.get_text()
        self.nameservice.ldap_pb_psw = self.ldap_pb_psw.get_text()


class NSNISAuto(NameService):

    HEADER_TEXT = _("NIS Name Server")
    HELP_DATA = (SCI_HELP + "/%s/nis.txt", HEADER_TEXT)

    def __init__(self, main_win, screen=None):
        super(NSNISAuto, self).__init__(main_win)
        self.intro = \
                _("Specify how to find a name server for this system.")
        self.intro2 = \
                _("Either let the software search for a name server, "
                  "or specify a name server in the following screen.  ")
        self.intro3 = \
                _("The software can find a name server only if that "
                  "server is on the local subnet.")

    def _show(self):
        super(NSNISAuto, self)._show()
        if self.nameservice.nameservice != 'NIS':
            raise SkipException
        y_loc = self._paint_opening()
        y_loc += self.center_win.add_paragraph(self.intro2, y_loc)
        y_loc += 1
        ynlist = [_('Find one'),
                  _('Specify one')]
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=len(ynlist) + 1)
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        self.scroll_region = ScrollWindow(area, window=self.center_win)
        y_loc += 1  # blank line
        # add the entries to the screen
        for idx, yon in enumerate(ynlist):
            y_loc += 1
            win_area = WindowArea(lines=1, columns=textwidth(yon) + 1,
                                  y_loc=idx, x_loc=INDENT)
            ListItem(win_area, window=self.scroll_region, text=yon,
                     data_obj=yon)
            self.main_win.do_update()
        self.center_win.activate_object(self.scroll_region)
        self.scroll_region.activate_object_force(self.cur_nisnschoice_idx,
                                                 force_to_top=True)
        y_loc += 1  # blank line
        self.center_win.add_paragraph(self.intro3, y_loc)

    def on_change_screen(self):
        self.cur_nisnschoice_idx = self.scroll_region.active_object
        idx = self.cur_nisnschoice_idx
        self.nameservice.nis_auto = idx


class NSNISIP(NameService):

    HEADER_TEXT = _("NIS Name Server Information")
    HELP_DATA = (SCI_HELP + "/%s/nis.txt", HEADER_TEXT)

    def __init__(self, main_win):
        super(NSNISIP, self).__init__(main_win)
        self.intro = \
                _("Enter the IP address of the name server.  IP "
                  "addresses must contain four sets of numbers separated "
                  "by periods (for example, 129.200.9.1).")
        self.title = _("Server's IP address:")

    def _show(self):
        super(NSNISIP, self)._show()
        if self.nameservice.nameservice != 'NIS':
            raise SkipException
        if self.nameservice.nis_auto == NameServiceInfo.NIS_CHOICE_AUTO:
            raise SkipException
        y_loc = self._paint_opening()
        self.center_win.add_text(self.title, y_loc, INDENT)
        maxtitlelen = textwidth(self.title)
        cols = self.win_size_x - maxtitlelen - INDENT - 1
        area = WindowArea(1, cols, y_loc, maxtitlelen + INDENT + 1)
        self.center_win.add_text(self.title, y_loc, INDENT)
        area = WindowArea(1, MAXIP, y_loc, maxtitlelen + INDENT + 1)
        self.nis_ip = EditField(area, window=self.center_win,
                                text=self.nameservice.nis_ip,
                                validate=incremental_validate_ip,
                                error_win=self.main_win.error_line)
        self.main_win.do_update()
        self.center_win.activate_object(self.nis_ip)

    def validate(self):
        validate_ip(self.nis_ip.get_text())
        if not self.nis_ip.get_text():
            raise UIMessage(_("The NIS server IP address cannot be blank."))

    def on_change_screen(self):
        self.nameservice.nis_ip = self.nis_ip.get_text()


def validate_ldap_profile(profile):
    ''' given an LDAP profile string, validate it
    Arg: profile - LDAP profile string
    Raises: UIMessage on failure
    '''
    if not profile:
        raise UIMessage(_("The LDAP profile name cannot be blank."))
    emsg = _("Whitespace characters and quotation marks are not allowed in "
             "LDAP profile names.")
    for cha in profile:
        if cha in string.whitespace or cha in "'\"":
            raise UIMessage(emsg)


def validate_ldap_proxy_dn(proxy_dn):
    ''' given an LDAP proxy distinguished name string, validate it
    Arg: profile - LDAP proxy distinguished name
    Raises: UIMessage on failure
    '''
    if not proxy_dn:
        raise UIMessage(_(
                   "The LDAP proxy bind distinguished name may not be blank."))
    for cha in proxy_dn:
        if cha in string.whitespace:
            raise UIMessage(_("The LDAP proxy bind distinguished name may not "
                              "contain whitespace characters."))
        if cha in "'\"":
            raise UIMessage(_("The LDAP proxy bind distinguished name may not "
                              "contain quotation marks."))


def validate_ldap_proxy_bind_psw(proxy_psw):
    ''' given an LDAP proxy bind password string, validate it
    Arg: profile - LDAP proxy bind password
    Raises: UIMessage on failure
    '''
    if not proxy_psw:
        raise UIMessage(_("The LDAP proxy bind password may not be blank."))
    for cha in proxy_psw:
        if cha in string.whitespace:
            raise UIMessage(_("The LDAP proxy bind password may not contain "
                              "whitespace characters."))
        if cha in "'\"":
            raise UIMessage(_("The LDAP proxy bind password may not contain "
                              "quotation marks."))


def validate_ip(ip_address):
    '''Wrap a call to IPAddress.check_address and raise a UIMessage with
    appropriate message text
    '''
    if not ip_address:
        return True
    try:
        IPAddress.convert_address(ip_address)
    except ValueError:
        raise UIMessage(_("An IP address must be of the form xxx.xxx.xxx.xxx"))


def validate_domain(domain, allow_empty=True):
    ''' given a domain string, validate it
    Args: domain - network domain name
          allow_empty - if False, and domain is blank, failure
    Raises: UIMessage on failure
    '''
    if not domain:
        if allow_empty:
            return
        raise UIMessage(_("The domain cannot be blank."))
    for label in domain.split('.'):
        if len(label) > 63:
            raise UIMessage(
                         _("Domain labels must have less than 64 characters."))
        if label.startswith('-') or label.endswith('-'):
            raise UIMessage(
                _("Domain labels should not start or end with hyphens ('-')."))
        global DOMAIN_LABEL_PATTERN
        if not DOMAIN_LABEL_PATTERN.match(label.upper()):
            raise UIMessage(_("Invalid domain"))


def incremental_validate_ip(edit_field):
    '''Incrementally validate the IP Address as the user enters it
    Arg: edit_field - EditField object for validation
    Raises: UIMessage on failure
    '''
    ip_address = edit_field.get_text()
    if not ip_address:
        return True
    try:
        IPAddress.incremental_check(ip_address)
    except ValueError:
        raise UIMessage(_("An IP address must be of the form xxx.xxx.xxx.xxx"))
    return True


def inc_validate_nowhite_nospecial(edit_field, etext='<empty>'):
    '''Incrementally validate EditField as the user enters it
    Args: edit_field - EditField object for validation
          etext - text to paste upon error
    Raises: UIMessage upon finding whitespace and special characters other than
            hyphens and underscores
    '''
    profile = edit_field.get_text()
    if not profile:
        raise UIMessage(_("The %s cannot be blank.") % etext)
    global NO_WHITE_NO_SPECIAL_PATTERN
    if not NO_WHITE_NO_SPECIAL_PATTERN.match(profile.upper()):
        raise UIMessage(_('Invalid character for %s.') % etext)


def incremental_validate_domain(edit_field):
    '''Incrementally validate EditField as a domain as the user enters it
    Arg: edit_field - EditField object with domain to validate
    Raises: UIMessage if invalid character typed
    '''
    domain = edit_field.get_text()
    for label in domain.split('.'):
        if len(label) > 63:
            raise UIMessage(
                          _("Domain labels must have less than 64 characters"))
        if label.startswith('-'):
            raise UIMessage(_('A domain label may not begin with a hyphen.'))
        global INCREMENTAL_DOMAIN_LABEL_PATTERN
        if not INCREMENTAL_DOMAIN_LABEL_PATTERN.match(label.upper()):
            raise UIMessage(_('Invalid character for domain name.'))


def _convert_to_ldap_domain(domain):
    ''' given a domain in dotted notation, produce an LDAP domain
    Arg: domain - domain to convert
    Returns converted for LDAP as string
    '''
    labels = []
    for label in domain.split('.'):
        labels.append('dc=' + label)
    return ','.join(labels)

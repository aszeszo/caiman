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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
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
INCREMENTAL_DOMAIN_LABEL_PATTERN = re.compile(r'^[A-Z0-9\-_]{0,63}$')
DOMAIN_LABEL_PATTERN = re.compile(r'^[A-Z0-9\-_]{1,63}$')


class NameService(BaseScreen):
    HELP_FORMAT = "  %s"
    '''Allow user to select name service '''
    # dimensions
    SCROLL_SIZE = 2
    BORDER_WIDTH = (0, 3)
    HOSTNAME_SCREEN_LEN = 25
    # name service choices for display to user
    USER_CHOICE_LIST = [_('None'), _('LDAP'), _('NIS')]
    USER_CHOICE_DNS = _('DNS')
    # identify name service choices for internal use
    CHOICE_LIST = [None, 'LDAP', 'NIS']

    MSG_HOST_NAME = _("Enter either a host name or an IP address.")
    MSG_IP_FMT = _("An IP address must be of the form xxx.xxx.xxx.xxx")
    MSG_NO_LEADING_ZEROS = _("IP address segments may not have leading zeros.")
 
    def __init__(self, main_win, screen=None):
        global LOGGER
        if LOGGER is None:
            LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
        super(NameService, self).__init__(main_win)
        self.cur_dnschoice_idx = 0
        self.cur_nschoice_idx = self.CHOICE_LIST.index(None)
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
        LOGGER.debug(sc_profile)
        # Skip naming services screens if user either wants automatic
        # networking configuration or no networking at all.
        if configure_group(SC_GROUP_NETWORK) and \
           (sc_profile.nic.type == NetworkInfo.AUTOMATIC or
            sc_profile.nic.type == NetworkInfo.NONE):
            raise SkipException
        if sc_profile.nameservice is None:
            # first time, assign sysconfig values to defaults found above
            LOGGER.debug('assigning NSV to sysconfig.profile')
            sc_profile.nameservice = NameServiceInfo()
            if hasattr(sc_profile, 'nic') and sc_profile.nic:
                nic = sc_profile.nic
                LOGGER.info("Found NIC:")
                LOGGER.info(nic)
                # if values were learned from the NIC, offer those as defaults
                if nic.domain:
                    sc_profile.nameservice.dns_search.append(nic.domain)
                if nic.dns_address:
                    sc_profile.nameservice.dns_server = nic.dns_address
        self.nameservice = sc_profile.nameservice

    def _paint_opening(self):
        ''' paint screen with opening paragraph and blank line
        Returns the row (y-offset) after the blank line '''
        self.center_win.border_size = NameService.BORDER_WIDTH
        return 2 + self.center_win.add_paragraph(self.intro, 1)


class NSDNSChooser(NameService):

    HEADER_TEXT = _("DNS Name Service")
    HELP_DATA = (SCI_HELP + "/%s/name_service.txt", HEADER_TEXT)
    HELP_FORMAT = "%s"

    def __init__(self, main_win):
        super(NSDNSChooser, self).__init__(main_win)
        LOGGER.debug('in NSDNSChooser init')
        self.intro = \
                _("Indicates whether or not the system should use the DNS "
                  "name service.")

    def _show(self):
        ''' called upon display of a screen '''
        super(NSDNSChooser, self)._show()
        y_loc = self._paint_opening()
        LOGGER.debug(self.nameservice)
        # allow the user to choose DNS or not
        ynlist = [_('Configure DNS'),
                  _('Do not configure DNS')]
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=len(ynlist) + 1)
        area.lines = self.win_size_y - (y_loc + 1)
        area.columns = self.win_size_x
        self.scroll_region_dns = ScrollWindow(area, window=self.center_win)
        # add the entries to the screen
        for idx, yon in enumerate(ynlist):
            win_area = WindowArea(1, textwidth(yon) + 1, idx, INDENT)
            ListItem(win_area, window=self.scroll_region_dns, text=yon,
                     data_obj=yon)
        # finalize positioning
        self.main_win.do_update()
        self.center_win.activate_object(self.scroll_region_dns)
        self.scroll_region_dns.activate_object_force(self.cur_dnschoice_idx,
                                                 force_to_top=True)

    def on_change_screen(self):
        ''' called when changes submitted by user for all screens '''
        # Save the chosen index and object when leaving the screen
        self.cur_dnschoice_idx = self.scroll_region_dns.active_object
        self.nameservice.dns = (self.cur_dnschoice_idx == 0)
        LOGGER.info("on_change_screen DNS chosen? %s", self.nameservice.dns)


class NSAltChooser(NameService):

    HEADER_TEXT = _("Alternate Name Service")
    HELP_DATA = (SCI_HELP + "/%s/name_service.txt", HEADER_TEXT)

    def __init__(self, main_win):
        super(NSAltChooser, self).__init__(main_win)
        self.intro = \
                _("From the list below, select one name service to be "
                  "used by this system. If the desired name service is not "
                  "listed, select None. The selected name service may be "
                  "used in conjunction with DNS.")

    def _show(self):
        ''' called upon display of a screen '''
        super(NSAltChooser, self)._show()
        y_loc = self._paint_opening()
        LOGGER.debug(self.nameservice)
        # allow the user to select an alternate name service
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
        # finalize positioning
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
                _("Specify the domain for the NIS or LDAP name server. "
                  "Use the domain name's exact capitalization and "
                  "punctuation.")
        self.title = _("Domain Name:")

    def _show(self):
        ''' show domain '''
        super(NSDomain, self)._show()
        if not _has_name_service():
            raise SkipException
        if not self.nameservice.nameservice:
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
        ns = self.nameservice
        new_domain = self.domain.get_text()
        if ns.domain != new_domain or \
                (ns.nameservice == 'LDAP' and not ns.ldap_search_base):
            ns.domain = new_domain
            # default in LDAP-formatted values for domain
            if self.nameservice.nameservice == 'LDAP':
                ldapdom = _convert_to_ldap_domain(new_domain)
                # default in search base from domain
                if not ns.ldap_search_base or \
                        not ns.ldap_search_base.startswith(ldapdom):
                    ns.ldap_search_base = ldapdom
                # base DN on search base
                if ns.ldap_pb_dn:
                    # update DN with any changes in search_base from user
                    fixedbase = _ldap_domain_fixup(ns.ldap_pb_dn,
                            ns.ldap_search_base)
                    if fixedbase:
                        # user changed search base, update DN
                        ns.ldap_pb_dn = fixedbase
                else:
                    # provide probable DN default
                    ns.ldap_pb_dn = 'cn=proxyagent,ou=profile,' + \
                            ns.ldap_search_base


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
        if not self.nameservice.dns:
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
        if not self.nameservice.dns:
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
            if i < len(self.nameservice.dns_search) and \
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
        self.title = _("Profile name:")
        self.title3 = _("Search base:")

    def _show(self):
        super(NSLDAPProfile, self)._show()
        if self.nameservice.nameservice != 'LDAP':
            raise SkipException
        if self.nameservice.dns:
            self.intro = \
                _("Specify the name of the LDAP profile to be used to "
                  "configure this system and the host name or IP address of "
                  "the server that contains the profile.")
            self.title2 = _("Profile server host name or IP address:")
        else:
            self.intro = \
                _("Specify the name of the LDAP profile to be used to "
                  "configure this system and the IP address of the "
                  "server that contains the profile.")
            self.title2 = _("Profile server IP address:")
        self.intro += _("  Enter the LDAP search base.")
        y_loc = self._paint_opening()
        maxtitlelen = max(textwidth(self.title), textwidth(self.title2),
                          textwidth(self.title3))
        aligned_x_loc = maxtitlelen + INDENT + 1
        cols = self.win_size_x - aligned_x_loc
        self.center_win.add_text(self.title.rjust(maxtitlelen), y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, aligned_x_loc)
        self.ldap_profile = EditField(area, window=self.center_win,
                                      text=self.nameservice.ldap_profile,
                                      error_win=self.main_win.error_line,
                                      validate=inc_validate_nowhite_nospecial)
        # in case of error, tell user what is being validated
        self.ldap_profile.validate_kwargs['etext'] = _('profile name')
        y_loc += 1
        area = WindowArea(1, cols, y_loc, aligned_x_loc,
                        scrollable_columns=NameService.HOSTNAME_SCREEN_LEN + 1)
        self.center_win.add_text(self.title2.rjust(maxtitlelen), y_loc, INDENT)
        # create edit field, validating for host name or IP address depending
        # on whether DNS was selected
        self.ldap_ip = EditField(area, window=self.center_win,
                                 text=self.nameservice.ldap_ip,
                                 error_win=self.main_win.error_line,
                                 validate=(incremental_validate_host
                                           if self.nameservice.dns
                                           else incremental_validate_ip))
        # search base
        y_loc += 1
        self.center_win.add_text(self.title3.rjust(maxtitlelen), y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, aligned_x_loc,
                          scrollable_columns=MAXDNLEN + 1)
        self.ldap_search_base = EditField(area, window=self.center_win,
                                        text=self.nameservice.ldap_search_base,
                                        error_win=self.main_win.error_line)
        self.main_win.do_update()
        self.center_win.activate_object(self.ldap_profile)

    def validate(self):
        validate_ldap_profile(self.ldap_profile.get_text())
        ldap_ip = self.ldap_ip.get_text()
        if self.nameservice.dns:
            validate_host_or_ip(ldap_ip)
        else:
            validate_ip(ldap_ip)
        if not self.ldap_profile.get_text():
            raise UIMessage(_("The LDAP profile name cannot be blank."))
        if not ldap_ip:
            raise UIMessage(_("The LDAP server IP address cannot be blank."))

    def on_change_screen(self):
        self.nameservice.ldap_profile = self.ldap_profile.get_text()
        self.nameservice.ldap_ip = self.ldap_ip.get_text()
        new_search_base = self.ldap_search_base.get_text()
        if new_search_base != self.nameservice.ldap_search_base:
            self.nameservice.ldap_search_base = new_search_base
            # update DN with any changes in search_base from user
            fixedbase = _ldap_domain_fixup(self.nameservice.ldap_pb_dn,
                                           new_search_base)
            if fixedbase:
                self.nameservice.ldap_pb_dn = fixedbase


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

    def _show(self):
        super(NSNISIP, self)._show()
        LOGGER.info("self.nameservice: %s" % self.nameservice)
        if self.nameservice.nameservice != 'NIS':
            raise SkipException
        if self.nameservice.nis_auto == NameServiceInfo.NIS_CHOICE_AUTO:
            raise SkipException
        if self.nameservice.dns:
            self.intro = \
                _("Enter the host name or IP address of the name server.  "
                  "A host name must have at least 2 characters and can be "
                  "alphanumeric and can contain hyphens.  IP "
                  "addresses must contain four sets of numbers separated "
                  "by periods (for example, 129.200.9.1).")
            self.title = _("Server's host name or IP address:")
        else:
            self.intro = \
                _("Enter the IP address of the name server.  IP "
                  "addresses must contain four sets of numbers separated "
                  "by periods (for example, 129.200.9.1).")
            self.title = _("Server's IP address:")
        y_loc = self._paint_opening()
        self.center_win.add_text(self.title, y_loc, INDENT)
        aligned_x_loc = textwidth(self.title) + INDENT + 1
        cols = self.win_size_x - aligned_x_loc
        area = WindowArea(1, cols, y_loc, aligned_x_loc)
        self.center_win.add_text(self.title, y_loc, INDENT)
        area = WindowArea(1, cols, y_loc, aligned_x_loc,
                        scrollable_columns=NameService.HOSTNAME_SCREEN_LEN + 1)
        # create edit field, validating for host name or IP address depending
        # on whether DNS was selected
        self.nis_ip = EditField(area, window=self.center_win,
                                text=self.nameservice.nis_ip,
                                error_win=self.main_win.error_line,
                                validate=(incremental_validate_host
                                          if self.nameservice.dns
                                          else incremental_validate_ip))
        self.main_win.do_update()
        self.center_win.activate_object(self.nis_ip)

    def validate(self):
        nis_ip = self.nis_ip.get_text()
        if self.nameservice.dns:
            validate_host_or_ip(nis_ip)
        else:
            validate_ip(nis_ip)
        if not nis_ip:
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


def validate_host_or_ip(host_name):
    '''Validate argument as either a valid hostname or IP address
    Raises: UIMessage if not valid
    '''
    if not host_name:
        return
    # assume host name if input starts with alpha character
    if host_name[0].isalpha():
        for chr in host_name:
            if not chr.isalnum() and not chr in u"-.":
                raise UIMessage(_("A host name can only contain letters, "
                                  "numbers,  periods, and minus signs (-)."))
        return
    # attempt validation as a numeric IP address
    try:
        IPAddress.convert_address(host_name)
    except ValueError as err:
        if err[0] == IPAddress.MSG_NO_LEADING_ZEROS:
            raise UIMessage(NameService.MSG_NO_LEADING_ZEROS)
        raise UIMessage(NameService.MSG_HOST_NAME)


def validate_ip(ip_address):
    '''Wrap a call to IPAddress.convert_address and raise a UIMessage with
    appropriate message text
    '''
    if not ip_address:
        return
    try:
        IPAddress.convert_address(ip_address)
    except ValueError as err:
        if err[0] == IPAddress.MSG_NO_LEADING_ZEROS:
            raise UIMessage(NameService.MSG_NO_LEADING_ZEROS)
        raise UIMessage(NameService.MSG_IP_FMT)


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
    except ValueError as err:
        if err[0] == IPAddress.MSG_NO_LEADING_ZEROS:
            raise UIMessage(NameService.MSG_NO_LEADING_ZEROS)
        raise UIMessage(NameService.MSG_IP_FMT)
    return True


def incremental_validate_host(edit_field):
    '''Incrementally validate the host as the user enters it
    Arg: edit_field - EditField object for validation
    Raises: UIMessage on failure
    '''
    host_name = edit_field.get_text()
    if not host_name:
        return True
    # assume host name if input starts with alpha character
    if host_name[0].isalpha():
        for chr in host_name:
            if not chr.isalnum() and not chr in u"-.":
                raise UIMessage(_("A host name can only contain letters, "
                                  "numbers,  periods, and minus signs (-)."))
        return True
    # attempt validation as a numeric IP address
    try:
        IPAddress.incremental_check(host_name)
    except ValueError as err:
        if err[0] == IPAddress.MSG_NO_LEADING_ZEROS:
            raise UIMessage(NameService.MSG_NO_LEADING_ZEROS)
        raise UIMessage(NameService.MSG_HOST_NAME)
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


def _has_name_service():
    nsv = solaris_install.sysconfig.profile.from_engine().nameservice
    if nsv.dns:
        return True
    if nsv.nameservice:
        return True
    return False


def _convert_to_ldap_domain(domain):
    ''' given a domain in dotted notation, produce an LDAP domain
    Arg: domain - domain to convert
    Returns converted for LDAP as string
    '''
    labels = []
    for label in domain.split('.'):
        labels.append('dc=' + label)
    return ','.join(labels)


def _ldap_domain_fixup(old, new_search_base):
    ''' if existing LDAP-formatted value, does not have the specified
    search base, replace it with the specified search base
    Args:
        old - the existing LDAP-formatted value
        new_search_base - the search base to replace it with
    '''
    if old.endswith(new_search_base):
        return None
    dnsplit = old.split(',dc=')
    if len(dnsplit) > 0 and dnsplit[0]:
        return dnsplit[0] + ',' + new_search_base
    return None

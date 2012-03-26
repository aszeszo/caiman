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
Display a summary of the user's selections
'''

import curses
import logging

from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig import _, SCI_HELP, configure_group, \
                                      SC_GROUP_IDENTITY, SC_GROUP_KBD, \
                                      SC_GROUP_LOCATION, SC_GROUP_NETWORK, \
                                      SC_GROUP_NS, SC_GROUP_SUPPORT, \
                                      SC_GROUP_USERS
from solaris_install.sysconfig.nameservice import NameService
import solaris_install.sysconfig.profile
from solaris_install.sysconfig.profile.nameservice_info import NameServiceInfo
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.support_info import SupportInfo

from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.i18n import convert_paragraph
from terminalui.window_area import WindowArea
from terminalui.scroll_window import ScrollWindow

LOGGER = None


class SummaryScreen(BaseScreen):
    '''Display a summary of the SC profile that will be applied
    to the system
    '''

    HEADER_TEXT = _("System Configuration Summary")
    PARAGRAPH = _("Review the settings below before continuing."
                  " Go back (F3) to make changes.")

    HELP_DATA = (SCI_HELP + "/%s/summary.txt",
                 _("System Configuration Summary"))

    INDENT = 2

    def __init__(self, main_win):
        global LOGGER
        if LOGGER is None:
            LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
        super(SummaryScreen, self).__init__(main_win)

    def set_actions(self):
        '''Replace the default F2_Continue with F2_Apply'''
        install_action = Action(curses.KEY_F2, _("Apply"),
                                self.main_win.screen_list.get_next)
        self.main_win.actions[install_action.key] = install_action

    def _show(self):
        '''Prepare a text summary from the DOC and display it
        to the user in a ScrollWindow

        '''
        y_loc = 1
        y_loc += self.center_win.add_paragraph(SummaryScreen.PARAGRAPH, y_loc)

        y_loc += 1
        self.sysconfig = solaris_install.sysconfig.profile.from_engine()
        summary_text = self.build_summary()
        # Wrap the summary text, accounting for the INDENT (used below in
        # the call to add_paragraph)
        max_chars = self.win_size_x - SummaryScreen.INDENT - 1
        summary_text = convert_paragraph(summary_text, max_chars)
        area = WindowArea(x_loc=0, y_loc=y_loc,
                          scrollable_lines=(len(summary_text) + 1))
        area.lines = self.win_size_y - y_loc
        area.columns = self.win_size_x
        scroll_region = ScrollWindow(area, window=self.center_win)
        scroll_region.add_paragraph(summary_text, start_x=SummaryScreen.INDENT)

        self.center_win.activate_object(scroll_region)

    def build_summary(self):
        '''Build a textual summary from solaris_install.sysconfig profile'''

        if self.sysconfig is None:
            return ""
        else:
            summary_text = []

            # display summary only for configured areas
            # locale and timezone belong to SC_GROUP_LOCATION group
            if configure_group(SC_GROUP_LOCATION):
                summary_text.append(self.get_tz_summary())

                summary_text.append("")
                summary_text.append(_("Language: *The following can be changed"
                                      " when logging in."))
                if self.sysconfig.system.locale is None:
                    self.sysconfig.system.determine_locale()
                summary_text.append(_("  Default language: %s") %
                                    self.sysconfig.system.actual_lang)

            # keyboard layout belongs to SC_GROUP_KBD group
            if configure_group(SC_GROUP_KBD):
                summary_text.append("")
                summary_text.append(_("Keyboard layout: *The following can be "
                                      "changed when logging in."))
                summary_text.append(_("  Default keyboard layout: %s") %
                                    self.sysconfig.system.keyboard)
                summary_text.append("")

            if hasattr(self.sysconfig.system, 'terminal_type'):
                summary_text.append(_("Terminal type: %s") %
                                    self.sysconfig.system.terminal_type)

            # user/root accounts belong to SC_GROUP_USERS group
            if configure_group(SC_GROUP_USERS):
                summary_text.append("")
                summary_text.append(_("Users:"))
                summary_text.extend(self.get_users())

            # network belongs to SC_GROUP_IDENTITY and SC_GROUP_NETWORK groups
            if configure_group(SC_GROUP_NETWORK) or \
               configure_group(SC_GROUP_IDENTITY):
                summary_text.append("")
                summary_text.append(_("Network:"))
                summary_text.extend(self.get_networks())
            if configure_group(SC_GROUP_NS):
                self._get_nameservice(summary_text)

            # support configuration
            if configure_group(SC_GROUP_SUPPORT):
                summary_text.append("")
                summary_text.append(_("Support configuration:"))
                summary_text.extend(self.get_support())

            return "\n".join(summary_text)

    def get_networks(self):
        '''Build a summary of the networks in the install_profile,
        returned as a list of strings

        '''
        network_summary = []

        # hostname belongs to 'identity' group
        if configure_group(SC_GROUP_IDENTITY):
            network_summary.append(_("  Computer name: %s") %
                                   self.sysconfig.system.hostname)

        if not configure_group(SC_GROUP_NETWORK):
            return network_summary

        nic = self.sysconfig.nic
        if nic.type == NetworkInfo.AUTOMATIC:
            network_summary.append(_("  Network Configuration: Automatic"))
        elif nic.type == NetworkInfo.NONE:
            network_summary.append(_("  Network Configuration: None"))
        elif nic.type == NetworkInfo.FROMGZ:
            network_summary.append(_("  Network Configuration:"
                                     " Mandated from global zone"))
        elif nic.type == NetworkInfo.MANUAL:
            network_summary.append(_("  Manual Configuration: %s")
                                   % NetworkInfo.get_nic_desc(nic.nic_iface))
            network_summary.append(_("IP Address: %s") % nic.ip_address)
            network_summary.append(_("Netmask: %s") % nic.netmask)
            if nic.gateway:
                network_summary.append(_("Router: %s") % nic.gateway)
        return network_summary

    def _get_nameservice(self, summary):
        ''' Find all name services information and append to summary '''
        nameservice_summary(self.sysconfig.nameservice, summary)

    def get_users(self):
        '''Build a summary of the user information, and return it as a list
        of strings

        '''
        root = self.sysconfig.users.root
        primary = self.sysconfig.users.user
        user_summary = []
        if not root.password:
            user_summary.append(_("  Warning: No root password set"))
        if primary.login_name:
            user_summary.append(_("  Username: %s") % primary.login_name)
        else:
            user_summary.append(_("  No user account"))
        return user_summary

    def get_tz_summary(self):
        '''Return a string summary of the timezone selection'''
        timezone = self.sysconfig.system.tz_timezone
        return _("Time Zone: %s") % timezone

    def get_support(self):
        '''Return a string summary of the support selection.'''
        support_summary = []
        support = self.sysconfig.support

        if support.netcfg == SupportInfo.NOSVC:
            support_summary.append(_("  Not generating a Support profile as "
                                     "OCM and ASR services are not "
                                     "installed."))
            return support_summary

        ocm_level = None
        asr_level = None

        if support.mos_email:
            if support.ocm_mos_password or support.ocm_ciphertext:
                ocm_level = "auth"
            elif support.ocm_available:
                ocm_level = "unauth"
            if support.asr_mos_password or support.asr_private_key:
                asr_level = "auth"

        if (ocm_level == None and asr_level == None):
            support_summary.append(_("  No telemetry will be "
                                     "sent automatically"))
        elif ocm_level == "unauth":
            # No need to check ASR; ocm_level == unauth implies no password
            # given, so asr_level will never be auth here.
            support_summary.append(_("  Telemetry will be sent and associated "
                                     "with email address:"))
            support_summary.append("       %s" % support.mos_email)
            support_summary.append(_("    but will not be registered with My "
                                     "Oracle Support because"))
            support_summary.append(_("    no password was saved."))
        else:
            # Equivalent to (ocm_level == "auth" or asr_level == "auth")
            support_summary.append(_("  Telemetry will be sent and will be "
                                     "registered with My Oracle Support"))
            support_summary.append(_("    using email address:"))
            support_summary.append("       %s" % support.mos_email)

            # Use the presence of OCM ciphertext to assume that successful OCM
            # validation took place.
            if support.ocm_ciphertext:
                support_summary.append(_("  MOS credentials validated "
                                         "for OCM"))
            elif support.ocm_available:
                support_summary.append(_("  MOS credentials NOT validated "
                                         "for OCM"))

            # Use the presence of ASR private_key to assume that successful ASR
            # validation took place.
            if support.asr_private_key:
                support_summary.append(_("  MOS credentials validated "
                                         "for ASR"))
            elif support.asr_available:
                support_summary.append(_("  MOS credentials NOT validated "
                                         "for ASR"))

            # Display different messages for different situations.
            if ((support.ocm_available and not support.ocm_ciphertext) or
                (support.asr_available and not support.asr_private_key)):
                # Installed systems may have different network config.
                support_summary.append(_("  Validation will be attempted "
                                         "again on (re)boot of "
                                         "target system(s)"))
        if support.netcfg == SupportInfo.PROXY:
            if support.proxy_user:
                proxy_line = (_("  Secure proxy "))
            else:
                proxy_line = (_("  Proxy "))
            proxy_line += (_("specified: host: %s" %
                             support.proxy_hostname))
            if support.proxy_port:
                proxy_line += (_("  port: %s" % support.proxy_port))
            if support.proxy_user:
                proxy_line += (_("  user: %s" % support.proxy_user))
            support_summary.append(proxy_line)
        elif support.netcfg == SupportInfo.HUB:
            if support.ocm_hub:
                support_summary.append(_("  OCM hub: %s" % support.ocm_hub))
            if support.asr_hub:
                support_summary.append(_("  ASR hub: %s" % support.asr_hub))

        return support_summary


def nameservice_summary(nameservice, summary):
    '''sppend name service summary information
    Args: nameservice - name service info
        summary - list of summary lines to append to
    '''
    if not nameservice:
        return
    if not nameservice.dns and not nameservice.nameservice:
        return
    # fetch localized name for name service
    if nameservice.dns:
        summary.append(_("Name service: %s") % NameService.USER_CHOICE_DNS)
        # strip empty list entries
        dnslist = [ln for ln in nameservice.dns_server if ln]
        summary.append(_("DNS servers: ") + " ".join(dnslist))
        dnslist = [ln for ln in nameservice.dns_search if ln]
        summary.append(_("DNS Domain search list: ") + " ".join(dnslist))
    if nameservice.nameservice == 'LDAP':
        ns_idx = NameService.CHOICE_LIST.index(nameservice.nameservice)
        summary.append(_("Name service: %s") %
                       NameService.USER_CHOICE_LIST[ns_idx])
        summary.append(_("Domain: %s") % nameservice.domain)
        summary.append(_("LDAP profile: ") + nameservice.ldap_profile)
        summary.append(_("LDAP server's IP: ") + nameservice.ldap_ip)
        summary.append(_("LDAP search base: ") +
                       nameservice.ldap_search_base)
        if nameservice.ldap_proxy_bind == \
                NameServiceInfo.LDAP_CHOICE_PROXY_BIND:
            summary.append(_("LDAP proxy bind distinguished name: ") +
                           nameservice.ldap_pb_dn)
            summary.append(_("LDAP proxy bind password: [concealed]"))
    elif nameservice.nameservice == 'NIS':
        ns_idx = NameService.CHOICE_LIST.index(nameservice.nameservice)
        summary.append(_("Name service: %s") %
                       NameService.USER_CHOICE_LIST[ns_idx])
        summary.append(_("Domain: %s") % nameservice.domain)
        if nameservice.nis_auto == NameServiceInfo.NIS_CHOICE_AUTO:
            summary.append(_("NIS server: broadcast"))
        elif nameservice.nis_ip:
            summary.append(_("NIS server's IP: ") + nameservice.nis_ip)
        # offer user help for modifying name service sources
        if nameservice.dns:
            summary.append(_("Note: DNS will be configured to resolve "
                             "host and IP node names."))
            summary.append(_("This setting can be modified upon "
                             "rebooting. For example:"))
            summary.append("# svccfg -s svc:/system/name-service/switch")
            summary.append("svc:/system/name-service/switch> "
                           "setprop config/host=\"files nis dns\"")
            summary.append("svc:/system/name-service/switch> quit")
            summary.append("# svcadm refresh svc:/system/name-service/switch")
            summary.append(_("See nsswitch.conf(4), svccfg(1M) and "
                             "nscfg(1M)."))

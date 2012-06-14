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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Display a summary of the user's selections
'''

import curses
import locale
import logging

import solaris_install.sysconfig.profile

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.support_info import SupportInfo
from solaris_install.sysconfig.summary import nameservice_summary
from solaris_install.target.libdiskmgt import const as libdiskmgt_const
from solaris_install.target.size import Size
from solaris_install.text_install import _, RELEASE, TUI_HELP, LOCALIZED_GB
from solaris_install.text_install.ti_target_utils import \
    get_desired_target_disk, get_solaris_gpt_partition, \
    get_solaris_partition, get_solaris_slice
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.i18n import convert_paragraph
from terminalui.window_area import WindowArea
from terminalui.scroll_window import ScrollWindow

LOGGER = None


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
        '''Prepare a text summary and display it to the user in a ScrollWindow

        '''

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self.sysconfig = solaris_install.sysconfig.profile.from_engine()

        y_loc = 1
        y_loc += self.center_win.add_paragraph(SummaryScreen.PARAGRAPH, y_loc)

        y_loc += 1
        summary_text = self.build_summary()

        LOGGER.info("The following configuration is used for "
                    "installation: %s\n", summary_text)
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
        '''Build a textual summary from the DOC data'''
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
        lines.append("  " + _("Default language: %s") %
                     self.sysconfig.system.actual_lang)
        lines.append("")
        lines.append(_("Keyboard layout: *The following can be "
                       "changed when logging in."))
        lines.append("  " + _("Default keyboard layout: %s") %
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
        self._get_nameservice(lines)
        lines.append("")
        lines.append(_("Support configuration:"))
        lines.extend(self.get_support())

        return "\n".join(lines)

    def get_networks(self):
        '''Build a summary of the networks from the DOC data,
        returned as a list of strings

        '''
        network_summary = []
        network_summary.append("  " + _("Computer name: %s") %
                               self.sysconfig.system.hostname)
        nic = self.sysconfig.nic

        if nic.type == NetworkInfo.AUTOMATIC:
            network_summary.append("  " +
                                   _("Network Configuration: Automatic"))
        elif nic.type == NetworkInfo.NONE:
            network_summary.append("  " + _("Network Configuration: None"))
        elif nic.type == NetworkInfo.MANUAL:
            network_summary.append("  " + _("Manual Configuration: %s")
                                   % NetworkInfo.get_nic_desc(nic.nic_iface))
            network_summary.append("    " +
                                   _("IP Address: %s") % nic.ip_address)
            network_summary.append("    " +
                                   _("Netmask: %s") % nic.netmask)
            if nic.gateway:
                network_summary.append("    " + _("Router: %s") % nic.gateway)
        return network_summary

    def _get_nameservice(self, summary):
        ''' Find all name services information and append to summary '''
        # append lines of name service info to summary
        nameservice_summary(self.sysconfig.nameservice, summary)

    def get_users(self):
        '''Build a summary of the user information, and return it as a list
        of strings

        '''
        root = self.sysconfig.users.root
        primary = self.sysconfig.users.user
        user_summary = []
        if not root.password:
            user_summary.append("  " + _("Warning: No root password set"))
        if primary.login_name:
            user_summary.append("  " + _("Username: %s") % primary.login_name)
        else:
            user_summary.append("  " + _("No user account"))
        return user_summary

    def get_disk_summary(self):
        '''Return a string summary of the disk selection'''

        doc = InstallEngine.get_instance().doc
        disk = get_desired_target_disk(doc)

        disk_string = list()

        disk_size_str = locale.format("%.1f",
            disk.disk_prop.dev_size.get(Size.gb_units)) + LOCALIZED_GB

        locale_disk_str = _("Disk: ") + disk_size_str + " " + \
            str(disk.disk_prop.dev_type)
        disk_string.append(locale_disk_str)

        if not disk.whole_disk:

            if disk.label != "VTOC":
                part_data = get_solaris_gpt_partition(doc)
                if part_data is not None:
                    type_str = str(part_data.part_type)
            else:
                part_data = get_solaris_partition(doc)
                if part_data is not None:
                    type_str = str(libdiskmgt_const.PARTITION_ID_MAP[
                                   part_data.part_type])
            if part_data is not None:
                part_size_str = locale.format("%.1f",
                    part_data.size.get(Size.gb_units)) + LOCALIZED_GB

                locale_part_str = _("Partition: ") + part_size_str + " " +\
                    type_str
                disk_string.append(locale_part_str)

            if part_data is None or not part_data.in_zpool:
                slice_data = get_solaris_slice(doc)

                slice_num_str = _("Slice %s: ") % slice_data.name

                slice_size_str = locale.format("%.1f",
                    slice_data.size.get(Size.gb_units)) + LOCALIZED_GB

                locale_slice_str = slice_num_str + slice_size_str + " " +\
                    str(slice_data.in_zpool)
                disk_string.append(locale_slice_str)

        return "\n".join(disk_string)

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
                LOGGER.warn("Could not read /etc/release")
                release_file = None
                release = RELEASE['release']
            else:
                release = release_file.readline()
        finally:
            if release_file is not None:
                release_file.close()
        return release.strip()

    def get_support(self):
        '''Return a string summary of the support selection.'''
        support_summary = []
        support = self.sysconfig.support

        if support.netcfg == SupportInfo.NOSVC:
            support_summary.append("  " + _("OCM and ASR services are not "
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
            support_summary.append("  " + _("No telemetry will be "
                                            "sent automatically"))
        elif ocm_level == "unauth":
            # No need to check ASR; ocm_level == unauth implies no password
            # given, so asr_level will never be auth here.
            support_summary.append("  " + _("OCM telemetry will be sent and "
                                            "associated with email address:\n"
                                            "       %s") % support.mos_email)
            support_summary.append("  " + _("Telemetry will not be registered "
                                            "with My Oracle Support because "
                                            "no password was saved."))
        else:
            # Equivalent to (ocm_level == "auth" or asr_level == "auth")
            if ocm_level is not None:
                support_summary.append("  " + _("OCM telemetry will be sent."))
            if asr_level is not None:
                support_summary.append("  " + _("ASR telemetry will be sent."))
            support_summary.append("  " + _("Telemetry will be registered "
                                            "with My Oracle Support using "
                                            "email address:\n"
                                            "       %s") % support.mos_email)

            # Use the presence of OCM ciphertext to assume that successful OCM
            # validation took place.
            if support.ocm_ciphertext:
                support_summary.append("  " + _("MOS credentials validated "
                                         "for OCM"))
            elif support.ocm_available:
                support_summary.append("  " + _("MOS credentials NOT yet "
                                                "validated for OCM"))

            # Use the presence of ASR private_key to assume that successful ASR
            # validation took place.
            if support.asr_private_key:
                support_summary.append("  " + _("MOS credentials validated "
                                                "for ASR"))
            elif support.asr_available:
                support_summary.append("  " + _("MOS credentials NOT yet "
                                                "validated for ASR"))

            # Display different messages for different situations.
            if ((support.ocm_available and not support.ocm_ciphertext) or
                (support.asr_available and not support.asr_private_key)):
                # Installer environment.
                support_summary.append("  " + _("Validation will be attempted "
                                                "again when target "
                                                "(re)boots."))
        if support.netcfg == SupportInfo.PROXY:
            if support.proxy_user:
                support_summary.append("  " +
                                       _("Secure proxy specified: "
                                         "Host and port: %s:%s ") %
                                         (support.proxy_hostname,
                                          support.proxy_port))
            else:
                support_summary.append("  " +
                                       _("Proxy specified: "
                                         "Host and port: %s:%s ") %
                                         (support.proxy_hostname,
                                          support.proxy_port))
            if support.proxy_user:
                support_summary.append("    " +
                                       _("User: %s") % support.proxy_user)
        elif support.netcfg == SupportInfo.HUB:
            if support.ocm_hub:
                support_summary.append("  " + _("OCM hub: %s") %
                                                support.ocm_hub)
            if support.asr_hub:
                support_summary.append("  " + _("ASR hub: %s") %
                                                support.asr_hub)

        return support_summary

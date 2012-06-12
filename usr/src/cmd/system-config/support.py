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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Set root password and primary user data
'''

import curses
import logging
import re

import solaris_install.sysconfig.profile
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig import _, SCI_HELP
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.support_info import SupportInfo
from solaris_install.sysconfig.profile.support_info import CONV_NONE
from terminalui.base_screen import BaseScreen, SkipException, UIMessage
from terminalui.edit_field import EditField, PasswordField
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea
from terminalui.i18n import textwidth

_LOGGER = None


def LOGGER():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
    return _LOGGER

_SAVE_ANYWAY_MSG = _("  Press F2 again to save anyway.")

_DUMMY_PASSWORD = "dummy"

_MAX_CRED_WIDTH = 40
_MAX_URL_WIDTH = 128

_HEADER_OFFSET = 2
_ITEM_OFFSET = 4
_RIGHT_MARGIN = 2

_STARS = re.compile("^\**$")


def _is_filler(strg, length):
    ''' Returns True if a string contains only stars.'''
    if not strg:
        return False
    return (_STARS.match(strg) and (len(strg) == length))


def _set_filler(length):
    '''Returns a filler string of given length'''
    return "*" * length


class SupportMOSScreen(BaseScreen):
    '''Main Support screen.  Prompts user for MOS email and password.'''

    HEADER_TEXT = _("Support - Registration")
    INTRO_1 = _(
        "Provide your email address to be informed of security issues, "
        "install the product and initiate configuration manager.")
    INTRO_2 = _(
        "Please see http://www.oracle.com/support/policies.html for details.")
    EMAIL_LABEL = _("Email:")
    EMAIL_FOOTER_TEXT = _("Easier for you if you use your My Oracle Support "
                          "email address/username.")
    PASSWORD_HEADER_TEXT = _("Please enter your password if you wish to "
                             "receive security updates via My Oracle Support.")
    PASSWORD_LABEL = _("My Oracle Support password:")

    HELP_DATA = (SCI_HELP + "/%s/support_main.txt", _("Support"))

    PASS_SCREEN_LEN = 16  # also used as column width for user input
    HEADER_OFFSET = _HEADER_OFFSET
    ITEM_OFFSET = _ITEM_OFFSET
    RIGHT_MARGIN = _RIGHT_MARGIN

    def __init__(self, main_win):
        super(SupportMOSScreen, self).__init__(main_win)

        (full_field_width, self.email_label_width, self.password_label_width,
         self.email_edit_width, self.password_edit_width) = \
            self.calc_sizes(self.win_size_x)

        self.window_area = WindowArea()

        self.error_area = WindowArea(lines=2, columns=full_field_width,
                                     y_loc=self.win_size_y - 3, x_loc=0)

        # For mechanism that allows a 2nd press of F2 to save w/o validation.
        # Initialized as disabled.
        self.error_override = False

        self.add_keys = {curses.KEY_UP: self.on_arrow_key,
                         curses.KEY_DOWN: self.on_arrow_key,
                         curses.KEY_ENTER: self.on_arrow_key}

    @staticmethod
    def calc_sizes(win_size_x):
        '''Return sizes of MOS cred field params used in this and other screens

        Args:
          win_size_x: width of the window

        Returns:
          full_field_width: width of the window available for fields
          email_label_width: width of the email label (to left of email field)
          password_label_width: width of the password label
          email_edit_width: width of email field
          password_edit_width: width of password field
        '''

        # Width of the widest possible field in the screen.  Assumes that
        # window will be sufficiently large to accommodate left and right
        # margins.
        full_field_width = (win_size_x -
                            SupportMOSScreen.ITEM_OFFSET -
                            SupportMOSScreen.RIGHT_MARGIN)

        email_label_width = textwidth(SupportMOSScreen.EMAIL_LABEL) + 1
        password_label_width = textwidth(SupportMOSScreen.PASSWORD_LABEL) + 1
        email_edit_width = full_field_width - email_label_width
        password_edit_width = \
            full_field_width - password_label_width - email_label_width

        return (full_field_width, email_label_width, password_label_width,
                email_edit_width, password_edit_width)

    @staticmethod
    def show_abbrev_creds(center_win, win_size_x, y_loc, x_loc,
                          mos_email_text, mos_password_fill):
        '''Function to show MOS credential fields in other screens.

        Provides a convenient way for other screens to append MOS email and
        password fields for display.  As such, labeling and embellishments are
        minimal.

        Args:
          center_win: main window all widgets are attached to.
          win_size_x: width of window.
          y_loc: starting Y screen coordinate of where to post creds fields.
          x_loc: starting X screen coordinate of where to post creds fields.
          mos_email_text: initial text of email field.
          mos_password_text: initial text of password field.

        Returns:
          mos_email_edit: widget from which email text can be taken.
          mos_password_edit: widget from which password text can be taken.
          mos_password_edit_width: width of password field.
        '''

        # Get field sizes.
        (full_field_width, email_label_width, password_label_width,
         email_edit_width, mos_password_edit_width) = \
            SupportMOSScreen.calc_sizes(win_size_x)

        window_area = WindowArea()

        # Set up Email label or title.
        window_area.y_loc = y_loc
        window_area.x_loc = x_loc
        window_area.lines = 1
        window_area.columns = email_label_width
        mos_email_label = ListItem(window_area, window=center_win,
                                   text=SupportMOSScreen.EMAIL_LABEL)

        # Set up editable email field next to the email label.
        window_area.x_loc += email_label_width
        window_area.columns = email_edit_width
        window_area.scrollable_columns = max(email_edit_width, _MAX_CRED_WIDTH)
        mos_email_edit = EditField(window_area, window=center_win,
                                   text=mos_email_text)

        # Set up password label or title on the next line.
        y_loc += 1
        window_area.y_loc = y_loc
        window_area.x_loc = x_loc
        window_area.lines = 1
        window_area.columns = password_label_width
        mos_password_label = ListItem(window_area, window=center_win,
                                      text=SupportMOSScreen.PASSWORD_LABEL)

        # Set up editable password field next to the password label.
        window_area.x_loc += password_label_width
        window_area.columns = mos_password_edit_width
        window_area.scrollable_columns = max(mos_password_edit_width,
                                             _MAX_CRED_WIDTH)
        mos_password_edit = PasswordField(window_area, window=center_win,
                                          fill=mos_password_fill)
        return (mos_email_edit, mos_password_edit, mos_password_edit_width)

    def _show(self):
        '''Display the MOS credential fields.

        Assumes that network configuration has already been determined.
        '''

        # Get/Initialized SupportInfo.  This also gets some configuration info.
        sc_profile = solaris_install.sysconfig.profile.from_engine()
        if sc_profile.support is None:
            sc_profile.support = SupportInfo()
        self.support = sc_profile.support

        # Skip all support screens if neither OCM nor ASR are present.
        # NOSVC is checked by all support screens before they are displayed.
        if self.support.netcfg == SupportInfo.NOSVC:
            LOGGER().info("Neither OCM nor ASR will be installed on system.")
            raise SkipException

        # Note that requested network configuration is None.
        if sc_profile.nic and sc_profile.nic.type == NetworkInfo.NONE:
            LOGGER().info("Not enabling OCM and ASR since network will not be "
                          "configured on installed system.")
            # Don't display any support screens.
            self.support.netcfg = SupportInfo.NOCFGNET
            # Store blank credentials.
            self.support.mos_email = None
            self.support.mos_password = None
            self.support.ocm_mos_password = None
            self.support.asr_mos_password = None
            raise SkipException

        # Set up full fields and decorations on the screen.
        y_loc = 1
        self.center_win.add_paragraph(SupportMOSScreen.INTRO_1,
                                      start_y=y_loc,
                                      start_x=SupportMOSScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)

        y_loc += 3
        self.center_win.add_paragraph(SupportMOSScreen.INTRO_2,
                                      start_y=y_loc,
                                      start_x=SupportMOSScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)

        y_loc += 3
        self.window_area.y_loc = y_loc
        self.window_area.x_loc = self.ITEM_OFFSET
        self.window_area.lines = 1
        self.window_area.columns = self.email_label_width
        self.email_label = ListItem(self.window_area, window=self.center_win,
                                       text=SupportMOSScreen.EMAIL_LABEL)

        email_field_start = self.ITEM_OFFSET + self.email_label_width
        self.window_area.x_loc = email_field_start
        self.window_area.columns = self.email_edit_width
        self.window_area.scrollable_columns = max(self.email_edit_width,
                                                  _MAX_CRED_WIDTH)
        self.email_edit = EditField(self.window_area,
                                    window=self.center_win,
                                    text=self.support.mos_email)
        y_loc += 1
        self.center_win.add_paragraph(SupportMOSScreen.EMAIL_FOOTER_TEXT,
                                      start_y=y_loc,
                                      start_x=email_field_start,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 3
        self.center_win.add_paragraph(SupportMOSScreen.PASSWORD_HEADER_TEXT,
                                      start_y=y_loc,
                                      start_x=self.ITEM_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 3
        self.window_area.y_loc = y_loc
        self.window_area.x_loc = email_field_start
        self.window_area.lines = 1
        self.window_area.columns = self.password_label_width
        self.password_label = ListItem(self.window_area,
                                       window=self.center_win,
                                       text=SupportMOSScreen.PASSWORD_LABEL)

        self.window_area.x_loc += self.password_label_width
        self.window_area.columns = self.password_edit_width
        self.window_area.scrollable_columns = max(self.password_edit_width,
                                                  _MAX_CRED_WIDTH)
        self.password_edit = PasswordField(self.window_area,
                                           window=self.center_win,
                                           fill=self.support.mos_password)

        self.center_win.key_dict.update(self.add_keys)
        self.center_win.activate_object(self.email_edit)

    def on_arrow_key(self, input_key):
        '''
        Have up and down toggle between email and password.
        Have <CR> go from email to password.
        '''
        active = self.center_win.get_active_object()
        if (input_key == curses.KEY_UP) and (active == self.password_edit):
            self.center_win.activate_object(self.email_edit)
            return None
        elif (((input_key == curses.KEY_DOWN) or
               (input_key == curses.KEY_ENTER)) and
              (active == self.email_edit)):
            self.center_win.activate_object(self.password_edit)
            return None
        return input_key

    def validate(self):
        '''Error-check and try to authenticate to Oracle

        Assumes that at least one of OCM or ASR exists.

        Does not assume a valid network connection exists.  If Oracle cannot
        be contacted, show the user a warning but let the user save them by
        bypassing validation when this method is called a second time with the
        same set of credentials.

        If Oracle can determine that credentials are not valid, do not allow
        the user to save them.

        Both OCM and ASR should find the same sets of credentials valid.  If
        the two services disagree, there is some wider problem.  Let the user
        save the credentials;  there may be a server problem somewhere which
        is temporary.  Assume that the services will attempt to validate them
        later.

        Part of knowing whether the user can "save anyway" without
        re-authentication, when validation is entered a second time, requires
        knowing that the credentials have changed.  However, the password
        cannot be saved in the clear.  After encrypting the password
        successfully, the clear MOS password is set to stars.  If the user
        re-enters it, the stars will change to the newly-entered password,
        indicating a change, and triggering a re-authentication.  If the
        password was blank to begin with and is entered the second time around,
        also indicates a change triggering re-authentication.
        '''

        # Save old email to check for changes.
        old_mos_email = self.support.mos_email
        old_mos_password = self.support.mos_password

        # Get new email and password.
        # "Filler" password means no changes from before.
        self.support.mos_email = CONV_NONE(self.email_edit.get_text())
        self.support.mos_password = CONV_NONE(self.password_edit.get_text())

        # Sanitize the password edit field.
        if self.support.mos_password:
            self.password_edit.set_text(_set_filler(self.password_edit_width))
        else:
            self.password_edit.clear_text()

        # If entered password changed, invalidate the encrypted ones that come
        # from the old entered one.
        if old_mos_password != self.support.mos_password:
            self.support.ocm_mos_password = None
            self.support.asr_mos_password = None

        # Credentials have changed when test email field differs from last
        # entered email field data, or if old password is blank and new one is
        # not, or if old one is not blank and new one is.
        creds_changed = ((old_mos_email != self.support.mos_email) or
                         (old_mos_password != self.support.mos_password))

        # If error_override is set, this is the second time the user hit the
        # "continue" key and an override is allowed.  Override if credentials
        # have not be altered by the user since.
        if self.error_override and not creds_changed:
            return
        self.error_override = False

        # Real validation begins here.

        # Check MOS email and password.
        (self.error_override, message) = \
            self.support.check_mos(self.error_override)
        if message:
            if self.error_override:
                message += _SAVE_ANYWAY_MSG
            raise UIMessage(message)

        # Attempt authentication if email and password are non-blank.
        # Use the mode that netcfg is set to.  This will start as DIRECT
        # if this screen is shown, and can change as user goes through the
        # screens.
        if self.support.mos_password:
            self.main_win.error_line.display_err(
                "Attempting to contact Oracle.  Please wait...")
            (ocm_status, asr_status) = \
                self.support.phone_home(self.support.netcfg)

            self.main_win.error_line.clear_err()

            # Sanitize MOS password.  It is replaced by less sensitive data.
            # Sanitize password if, for both OCM and ASR, we have fields
            # returned from authorization, or the service is unavailable, or
            # the script could not do encryption.  The latter case can happen
            # if the script is old or is otherwise incompatible.
            if ((self.support.ocm_mos_password or
                 self.support.ocm_ciphertext or
                 not self.support.ocm_available or
                 ocm_status == SupportInfo.OCM_NO_ENCR) and
                (self.support.asr_mos_password or
                 self.support.asr_private_key or
                 not self.support.asr_available or
                 asr_status == SupportInfo.ASR_NO_ENCR)):
                self.support.mos_password = \
                    _set_filler(self.password_edit_width)
            else:
                self.support.mos_password = None

            # A clear OCM and ASR mos password reflects success.  Clear them as
            # they could have been set on a previous failure.
            if ocm_status == SupportInfo.OCM_SUCCESS:
                self.support.ocm_mos_password = None
            if asr_status == SupportInfo.ASR_SUCCESS:
                self.support.asr_mos_password = None

            # If one of OCM or ASR accepted the credentials but the other did
            # not, there is a bigger problem somewhere.  Allow override.
            self.error_override = \
                ((ocm_status != SupportInfo.OCM_BAD_CRED and
                  self.support.ocm_available) or
                 (asr_status != SupportInfo.ASR_BAD_CRED and
                  self.support.asr_available))

            message = SupportInfo.phone_home_msg(ocm_status, asr_status)
            if message:
                if self.error_override:
                    message += _SAVE_ANYWAY_MSG
                raise UIMessage(message)


class SupportNetConfigScreen(BaseScreen):
    '''Allow user to select:
    - No proxy (use system internet connection parameters)
    - Configure proxy settings
    - Configure aggregation hubs
    '''

    # Identify choices for internal use
    CHOICES = [
               (SupportInfo.DIRECT,
                _("No proxy"),
                _("Use system Internet connection parameters.")),
               (SupportInfo.PROXY,
                _("Proxy"),
                _("Enter proxy information on the next screen")),
               (SupportInfo.HUB,
                _("Aggregation Hubs"),
                _("Enter hubs information on the next screen"))
              ]

    HEADER_TEXT = _("Support - Network Configuration")
    INTRO_1 = _(
        "To improve products and services, Oracle Solaris relays "
        "configuration data to the Oracle support organization.")

    INTRO_2 = _("Select an internet access method for OCM and ASR.")

    HELP_DATA = (SCI_HELP + "/%s/support_net_config.txt", _("Support"))

    HEADER_OFFSET = _HEADER_OFFSET
    ITEM_OFFSET = _ITEM_OFFSET
    RIGHT_MARGIN = _RIGHT_MARGIN

    def __init__(self, main_win):
        super(SupportNetConfigScreen, self).__init__(main_win)

        self.window_area = WindowArea()

        self.choice_dict = dict()

        self.max_title_len = 0
        for (key, title, text) in self.CHOICES:
            title_len = textwidth(title)
            if title_len > self.max_title_len:
                self.max_title_len = title_len

        self.current_choice = None

    def _show(self):
        '''Display a menu for selecting the network configuration options'''

        sc_profile = solaris_install.sysconfig.profile.from_engine()
        self.support = sc_profile.support

        # Show no more screens if neither service exists on this system, the
        # user doesn't want to configure a proxy or hub, or the user wants
        # disconnected mode.
        if (self.support.netcfg == SupportInfo.NOSVC or
            self.support.netcfg == SupportInfo.NOCFGNET or
            (self.support.netcfg == SupportInfo.DIRECT and
             not self.support.mos_email)):
            raise SkipException

        full_field_width = (self.win_size_x -
                            SupportNetConfigScreen.ITEM_OFFSET -
                            SupportNetConfigScreen.RIGHT_MARGIN)

        y_loc = 1
        self.center_win.add_paragraph(SupportNetConfigScreen.INTRO_1,
                                      start_y=y_loc,
                                      start_x=SupportNetConfigScreen.
                                          HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 3
        self.center_win.add_paragraph(SupportNetConfigScreen.INTRO_2,
                                      start_y=y_loc,
                                      start_x=SupportNetConfigScreen.
                                          HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 2

        # Set default selection based on whether or not authentication was
        # successful in the previous screen.
        if self.current_choice is None:
            if ((not self.support.mos_password) or
                (self.support.ocm_ciphertext and
                 self.support.asr_private_key)):
                self.current_choice = SupportInfo.DIRECT
            else:
                self.current_choice = SupportInfo.PROXY

        self.window_area.x_loc = self.ITEM_OFFSET
        self.window_area.lines = 1

        # Display all choices.
        for choice in SupportNetConfigScreen.CHOICES:
            self.window_area.y_loc = y_loc
            key, title, text = choice
            line = title.ljust(self.max_title_len + 2) + text
            self.window_area.columns = min(textwidth(line) + 1,
                                           full_field_width)
            widget = ListItem(self.window_area, window=self.center_win,
                              text=line)
            widget.item_key = key
            self.choice_dict[key] = widget
            y_loc += 2

        # Make the "current choice" as determined above, active.
        self.center_win.activate_object(self.choice_dict[self.current_choice])

    def on_change_screen(self):
        '''Save current choice, and go to the next screen based on choice.'''
        self.current_choice = self.center_win.get_active_object().item_key
        self.support.netcfg = self.current_choice


class SupportProxyScreen(BaseScreen):
    '''Allow user to enter proxy information'''

    HEADER_TEXT = _("Support - Proxy Configuration")
    INTRO_1 = _(
        "Complete HTTP proxy information if OCM and ASR require a dedicated "
        "proxy in order to contact the Oracle support organization.")
    INTRO_2 = _("Proxy information")
    INTRO_3 = _("Enter username and password only if "
                "configuring a secure proxy.")

    HOSTNAME_LABEL = _("Hostname:")
    PORT_LABEL = _("Port:")
    USERNAME_LABEL = _("Username:")
    PASSWORD_LABEL = _("Password:")

    HELP_DATA = (SCI_HELP + "/%s/support_net_config.txt", _("Support"))

    HEADER_OFFSET = _HEADER_OFFSET
    LEFT_ITEM_OFFSET = _ITEM_OFFSET
    RIGHT_MARGIN = _RIGHT_MARGIN

    def __init__(self, main_win):
        super(SupportProxyScreen, self).__init__(main_win)

        self.window_area = WindowArea()

        # Show email and password in screen when true.
        self.show_mos_credentials = False

        # For mechanism that allows a 2nd press of F2 to save w/o validation.
        # Initialized as disabled.
        self.error_override = False

        self.add_keys = {curses.KEY_UP: self.on_arrow_key,
                         curses.KEY_DOWN: self.on_arrow_key,
                         curses.KEY_LEFT: self.on_arrow_key,
                         curses.KEY_RIGHT: self.on_arrow_key,
                         curses.KEY_ENTER: self.on_arrow_key}

        self.field_dict = {}

    def _show(self):
        '''Display a menu for selecting the network configuration options'''

        # Skip if this screen is not supposed to be shown.
        sc_profile = solaris_install.sysconfig.profile.from_engine()
        self.support = sc_profile.support
        if (self.support.netcfg != SupportInfo.PROXY):
            raise SkipException

        full_field_width = (self.win_size_x -
                            SupportProxyScreen.LEFT_ITEM_OFFSET -
                            SupportProxyScreen.RIGHT_MARGIN)
        right_item_offset = (full_field_width / 2) + \
                            SupportProxyScreen.LEFT_ITEM_OFFSET

        y_loc = 1
        self.center_win.add_paragraph(SupportProxyScreen.INTRO_1,
                                      start_y=y_loc,
                                      start_x=SupportProxyScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 4
        self.center_win.add_paragraph(SupportProxyScreen.INTRO_2,
                                      start_y=y_loc,
                                      start_x=SupportProxyScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)

        y_loc += 2
        self.window_area.y_loc = y_loc
        self.window_area.x_loc = SupportProxyScreen.LEFT_ITEM_OFFSET
        self.window_area.lines = 1
        self.window_area.columns = \
            textwidth(SupportProxyScreen.HOSTNAME_LABEL) + 1
        self.hostname_label = ListItem(self.window_area,
                                       window=self.center_win,
                                       text=SupportProxyScreen.HOSTNAME_LABEL)

        self.window_area.x_loc += self.window_area.columns
        self.window_area.columns = \
            right_item_offset - SupportProxyScreen.RIGHT_MARGIN - \
            self.window_area.x_loc + 1
        self.window_area.scrollable_columns = \
            max(self.window_area.columns, _MAX_URL_WIDTH)
        self.hostname_edit = EditField(self.window_area,
                                       window=self.center_win,
                                       text=self.support.proxy_hostname)

        # Assign each editable field "edit coordinates".
        # These help the up, down, left and right buttons navigate the fields.
        self.field_dict["0,0"] = self.hostname_edit

        self.window_area.x_loc = right_item_offset
        self.window_area.columns = textwidth(SupportProxyScreen.PORT_LABEL) + 1
        self.port_label = ListItem(self.window_area, window=self.center_win,
                                   text=SupportProxyScreen.PORT_LABEL)

        self.window_area.x_loc += self.window_area.columns
        self.window_area.columns = 6        # 5 digits
        self.window_area.scrollable_columns = self.window_area.columns
        self.port_edit = EditField(self.window_area,
                                   window=self.center_win,
                                   text=self.support.proxy_port,
                                   validate=self.port_valid,
                                   error_win=self.main_win.error_line)
        self.field_dict["1,0"] = self.port_edit

        y_loc += 2
        self.center_win.add_paragraph(SupportProxyScreen.INTRO_3,
                                      start_y=y_loc,
                                      start_x=SupportProxyScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 2
        self.window_area.y_loc = y_loc
        self.window_area.x_loc = SupportProxyScreen.LEFT_ITEM_OFFSET
        self.window_area.columns = \
            textwidth(SupportProxyScreen.USERNAME_LABEL) + 1
        self.username_label = ListItem(self.window_area,
                                       window=self.center_win,
                                       text=SupportProxyScreen.USERNAME_LABEL)

        self.window_area.x_loc += self.window_area.columns
        self.window_area.columns = \
            right_item_offset - SupportProxyScreen.RIGHT_MARGIN - \
            self.window_area.x_loc + 1
        self.window_area.scrollable_columns = \
            max(self.window_area.columns, _MAX_CRED_WIDTH)
        self.username_edit = EditField(self.window_area,
                                       window=self.center_win,
                                       text=self.support.proxy_user)
        self.field_dict["0,1"] = self.username_edit

        self.window_area.x_loc = right_item_offset
        self.window_area.columns = \
            textwidth(SupportProxyScreen.PASSWORD_LABEL) + 1
        self.password_label = ListItem(self.window_area,
                                       window=self.center_win,
                                       text=SupportProxyScreen.PASSWORD_LABEL)

        self.window_area.x_loc += self.window_area.columns
        self.proxy_password_edit_width = \
            full_field_width - self.window_area.x_loc + 1
        self.window_area.columns = self.proxy_password_edit_width

        self.window_area.scrollable_columns = \
            max(self.proxy_password_edit_width, _MAX_CRED_WIDTH)
        self.password_edit = PasswordField(self.window_area,
                                           window=self.center_win,
                                           fill=self.support.proxy_password)
        self.field_dict["1,1"] = self.password_edit

        # Show MOS credential fields only if needed (i.e. when a proxy has been
        # set up so that Oracle can be contacted, and Oracle has determined
        # that credentials don't validate.
        if self.show_mos_credentials:
            y_loc += 2
            (self.mos_email_edit, self.mos_password_edit,
             self.mos_password_edit_width) = \
                SupportMOSScreen.show_abbrev_creds(self.center_win,
                                                   self.win_size_x,
                                                   y_loc,
                                                   self.LEFT_ITEM_OFFSET,
                                                   self.support.mos_email,
                                                   self.support.mos_password)

            # Assign edit coordinates to the new fields, and add the mos
            # credential widgets to the field dict.
            self.field_dict["0,2"] = self.mos_email_edit
            self.field_dict["0,3"] = self.mos_password_edit

            # Lines 2 and 3  have 1 item each.
            self.field_dict["max2"] = 0
            self.field_dict["max3"] = 0
            # Four lines total.
            self.field_dict["max_y"] = 3

        else:
            # Show only proxy fields.  Two lines total.
            self.field_dict["max_y"] = 1

        # Lines 0 and 1 have two items each.
        self.field_dict["max0"] = 1
        self.field_dict["max1"] = 1

        self.center_win.key_dict.update(self.add_keys)

        # Put the spotlight on the email address if credentials are shown.
        if self.show_mos_credentials:
            self.center_win.activate_object(self.mos_email_edit)
        else:
            self.center_win.activate_object(self.hostname_edit)

    def on_arrow_key(self, input_key):
        '''
        Implement up, down, left, right arrow keys.
        '''

        # Get coordinates of active object, and use coordinate arithmetic to
        # find the object to be active next.
        active = self.center_win.get_active_object()
        active_key = [key for (key, value) in self.field_dict.items()
                      if value == active]
        strx, stry = active_key[0].split(",")
        x = int(strx)
        y = int(stry)
        x_max = self.field_dict["max%d" % y]
        if ((input_key == curses.KEY_LEFT) and (x != 0)):
            x -= 1
        elif ((input_key == curses.KEY_RIGHT) and (x != x_max)):
            x += 1
        elif (input_key == curses.KEY_UP):
            if (x != 0):
                x -= 1
            elif ((x == 0) and (y != 0)):
                x = x_max
                y -= 1
            else:
                return input_key
        elif (input_key == curses.KEY_DOWN or input_key == curses.KEY_ENTER):
            y_max = self.field_dict["max_y"]
            if (x != x_max):
                x += 1
            elif ((x == x_max) and (y != y_max)):
                x = 0
                y += 1
            else:
                return input_key
        else:
            return input_key
        self.center_win.activate_object(self.field_dict["%d,%d" % (x, y)])
        return None

    def validate(self):
        '''Validate entered data, including contacting Oracle to authenticate.
        '''

        # Check for override.  Save old values.  Retrieve any new ones.  Check
        # for changes.  If no changes and user can override, return without
        # validation.

        old_proxy_hostname = self.support.proxy_hostname
        old_proxy_port = self.support.proxy_port
        old_proxy_password = self.support.proxy_password
        old_proxy_user = self.support.proxy_user

        self.support.proxy_hostname = CONV_NONE(self.hostname_edit.get_text())
        self.support.proxy_port = CONV_NONE(self.port_edit.get_text())
        self.support.proxy_user = CONV_NONE(self.username_edit.get_text())
        self.support.proxy_password = CONV_NONE(self.password_edit.get_text())

        # Sanitize the password edit field.
        if self.support.proxy_password:
            self.password_edit.set_text(_set_filler
                                              (self.proxy_password_edit_width))
        else:
            self.password_edit.clear_text()

        old_mos_email = self.support.mos_email
        old_mos_password = self.support.mos_password
        if self.show_mos_credentials:
            self.support.mos_email = CONV_NONE(self.mos_email_edit.get_text())
            self.support.mos_password = \
                CONV_NONE(self.mos_password_edit.get_text())

            # Sanitize the password edit field.
            if self.support.mos_password:
                self.mos_password_edit.set_text(_set_filler
                                            (self.mos_password_edit_width))
            else:
                self.password_edit.clear_text()

            # If entered password changed, invalidate the encrypted ones that
            # come from the old entered one.
            if old_mos_password != self.support.mos_password:
                self.support.ocm_mos_password = None
                self.support.asr_mos_password = None

        creds_changed = ((old_proxy_hostname != self.support.proxy_hostname) or
                         (old_proxy_port != self.support.proxy_port) or
                         (old_proxy_password != self.support.proxy_password) or
                         (old_proxy_user != self.support.proxy_user) or
                         (old_mos_email != self.support.mos_email) or
                         (old_mos_password != self.support.mos_password))

        if self.error_override and not creds_changed:
            return
        self.error_override = False

        # Wipe out hub information as it is orthogonal to proxy information.
        if self.support.proxy_hostname:
            self.support.ocm_hub = ""
            self.support.asr_hub = ""

        # Real validation begins here.

        # Check MOS email and password.
        (self.error_override, message) = \
            self.support.check_mos(self.error_override)
        if message:
            if self.error_override:
                message += _SAVE_ANYWAY_MSG
            raise UIMessage(message)

        # Proxy-field-specific syntax checks.

        # Err if proxy_hostname or proxy_port is blank.
        if (not self.support.proxy_hostname or not self.support.proxy_port):
            raise UIMessage(_("Please fill in proxy hostname and proxy port "
                              "or press F3 to go back"))

        # Err if only one of proxy password or proxy_user is given
        if ((self.support.proxy_password and not self.support.proxy_user) or
            (self.support.proxy_user and not self.support.proxy_password)):
            raise UIMessage(_("Non-blank proxy user and password must be "
                              "given together"))

        # Initialize for the cases where phone_home is NOT called.
        ocm_status = SupportInfo.OCM_SUCCESS
        asr_status = SupportInfo.ASR_SUCCESS

        # Attempt authentication if email and password are non-blank.
        if self.support.mos_password:
            self.main_win.error_line.display_err(
                "Attempting to contact Oracle.  Please wait...")
            (ocm_status, asr_status) = \
                self.support.phone_home(SupportInfo.PROXY)
            self.main_win.error_line.clear_err()

            if self.show_mos_credentials:
                # Sanitize MOS password.  It is replaced by less sensitive data
                if ((self.support.ocm_mos_password or
                     self.support.ocm_ciphertext or
                     not self.support.ocm_available or
                     ocm_status == SupportInfo.OCM_NO_ENCR) and
                    (self.support.asr_mos_password or
                     self.support.asr_private_key or
                     not self.support.asr_available or
                     asr_status == SupportInfo.ASR_NO_ENCR)):
                    self.support.mos_password = \
                        _set_filler(self.mos_password_edit_width)
                else:
                    self.support.mos_password = None

            # Sanitize proxy password.  It is replaced by less sensitive data
            if ((self.support.ocm_proxy_password or
                 not self.support.ocm_available or
                 ocm_status == SupportInfo.OCM_NO_ENCR) and
                (self.support.asr_proxy_password or
                 not self.support.asr_available or
                 asr_status == SupportInfo.ASR_NO_ENCR) and
                self.support.proxy_password):
                self.support.proxy_password = \
                        _set_filler(self.proxy_password_edit_width)
            else:
                self.support.proxy_password = None

            # A clear OCM and ASR mos password reflects success.  Clear them as
            # they could have been set on a previous failure.
            if ocm_status == SupportInfo.OCM_SUCCESS:
                self.support.ocm_mos_password = None
            if asr_status == SupportInfo.ASR_SUCCESS:
                self.support.asr_mos_password = None

            # Unless OCM and ASR both returned BAD_CRED, allow override.
            # If successful, no exception will be raised and control won't
            # return here again.
            #
            # If one of OCM or ASR accepted the credentials but the other did
            # not, there is a bigger problem somewhere.  Allow override.
            if (((ocm_status != SupportInfo.OCM_BAD_CRED) and
                 self.support.ocm_available) or
                ((asr_status != SupportInfo.ASR_BAD_CRED) and
                 self.support.asr_available)):
                self.error_override = True
            else:
                self.show_mos_credentials = True

        # No mos password, but need to encrypt proxy password.
        elif self.support.proxy_password:
            self.main_win.error_line.display_err(
                "Attempting to contact Oracle.  Please wait...")
            (ocm_status, asr_status) = \
                self.support.phone_home(SupportInfo.PROXY,
                                        force_encrypt_only=True)
            self.main_win.error_line.clear_err()

        message = SupportInfo.phone_home_msg(ocm_status, asr_status)
        if message:
            # Redisplay screen to include MOS credentials if needed.
            if self.show_mos_credentials:
                self.center_win.make_inactive()
                self._show()
                self.main_win.do_update()
            if self.error_override:
                message += _SAVE_ANYWAY_MSG
            raise UIMessage(message)

    def port_valid(self, edit_field):
        '''Validate port number'''
        value = edit_field.get_text()
        if (not (value.isdigit() and (0 <= int(value) < 0x10000))):
            raise UIMessage("Port number must be a number from 0 to 65535")


class SupportHubScreen(BaseScreen):
    '''Allow user to enter hub information'''

    HEADER_TEXT = _("Support - Hub Configuration")
    INTRO_1 = _("OCM and ASR data can be relayed to the Oracle support "
                "organization through local aggregation systems or \"hubs\" "
                "that pool data and forward it.")
    INTRO_2 = _("Enter at least one hub URL.")

    OCM_HUB_LABEL = "    OCM Hub URL:"
    ASR_HUB_LABEL = "ASR Manager URL:"

    HELP_DATA = (SCI_HELP + "/%s/support_net_config.txt", _("Support"))

    HEADER_OFFSET = _HEADER_OFFSET
    ITEM_OFFSET = _ITEM_OFFSET
    RIGHT_MARGIN = _RIGHT_MARGIN

    def __init__(self, main_win):
        super(SupportHubScreen, self).__init__(main_win)

        self.window_area = WindowArea()

        # Show email and password in screen when true.
        self.show_mos_credentials = False

        # For mechanism that allows a 2nd press of F2 to save w/o validation.
        # Initialized as disabled.
        self.error_override = False

        self.add_keys = {curses.KEY_UP: self.on_arrow_key,
                         curses.KEY_DOWN: self.on_arrow_key,
                         curses.KEY_ENTER: self.on_arrow_key}

    def _show(self):
        '''Display a menu for selecting the network configuration options

        It is assumed that at least one of ocm and asr services will be
        present.
        '''

        sc_profile = solaris_install.sysconfig.profile.from_engine()
        self.support = sc_profile.support

        # Skip if this screen is not supposed to be shown.
        if (self.support.netcfg != SupportInfo.HUB):
            raise SkipException

        self.field_array = list()

        full_field_width = (self.win_size_x -
                            SupportHubScreen.ITEM_OFFSET -
                            SupportHubScreen.RIGHT_MARGIN)

        y_loc = 1
        self.center_win.add_paragraph(SupportHubScreen.INTRO_1,
                                      start_y=y_loc,
                                      start_x=SupportHubScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 5
        self.center_win.add_paragraph(SupportHubScreen.INTRO_2,
                                      start_y=y_loc,
                                      start_x=SupportHubScreen.HEADER_OFFSET,
                                      max_y=y_loc + 2,
                                      max_x=self.win_size_x - 1)
        y_loc += 2

        if self.support.ocm_available:
            self.window_area.y_loc = y_loc
            self.window_area.x_loc = SupportHubScreen.ITEM_OFFSET
            self.window_area.lines = 1
            self.window_area.columns = \
                textwidth(SupportHubScreen.OCM_HUB_LABEL) + 1
            self.ocm_hub_label = ListItem(self.window_area,
                                          window=self.center_win,
                                          text=SupportHubScreen.OCM_HUB_LABEL)

            self.window_area.x_loc += self.window_area.columns
            self.window_area.columns = full_field_width - \
                SupportHubScreen.RIGHT_MARGIN - self.window_area.x_loc + 1
            self.window_area.scrollable_columns = \
                max(self.window_area.columns, _MAX_URL_WIDTH)
            self.ocm_hub_edit = EditField(self.window_area,
                                          window=self.center_win,
                                          text=self.support.ocm_hub,
                                          on_exit=self.url_valid)

            self.field_array.append(self.ocm_hub_edit)
            y_loc += 1

        if self.support.asr_available:
            self.window_area.y_loc = y_loc
            self.window_area.x_loc = SupportHubScreen.ITEM_OFFSET
            self.window_area.lines = 1
            self.window_area.columns = \
                textwidth(SupportHubScreen.ASR_HUB_LABEL) + 1
            self.asr_hub_label = ListItem(self.window_area,
                                          window=self.center_win,
                                          text=SupportHubScreen.ASR_HUB_LABEL)

            self.window_area.x_loc += self.window_area.columns
            self.window_area.columns = full_field_width - \
                SupportHubScreen.RIGHT_MARGIN - self.window_area.x_loc + 1
            self.window_area.scrollable_columns = \
                max(self.window_area.columns, _MAX_URL_WIDTH)
            self.asr_hub_edit = EditField(self.window_area,
                                          window=self.center_win,
                                          text=self.support.asr_hub,
                                          on_exit=self.url_valid)
            self.field_array.append(self.asr_hub_edit)

        # Show MOS credential fields only if needed (i.e. when a hub has been
        # set up so that Oracle can be contacted, and Oracle has determined
        # that credentials don't validate.
        if self.show_mos_credentials:
            y_loc += 2
            (self.mos_email_edit, self.mos_password_edit,
             self.mos_password_edit_width) = \
                SupportMOSScreen.show_abbrev_creds(self.center_win,
                                                   self.win_size_x,
                                                   y_loc,
                                                   self.ITEM_OFFSET,
                                                   self.support.mos_email,
                                                   self.support.mos_password)

            # Extend the array of widgets so arrow keys can accommodate the
            # extra fields.
            self.field_array.extend([self.mos_email_edit,
                                     self.mos_password_edit])

        self.center_win.key_dict.update(self.add_keys)
        self.center_win.activate_object(self.field_array[0])

    def on_arrow_key(self, input_key):
        '''
        Implement up, down arrow keys.
        '''

        # Use the field array index to determine the next field.
        active = self.center_win.get_active_object()
        if ((input_key == curses.KEY_UP) and (active != self.field_array[0])):
            self.center_win.activate_object(self.field_array[
                self.field_array.index(active) - 1])
            return None
        elif (((input_key == curses.KEY_DOWN) or
               (input_key == curses.KEY_ENTER)) and
              (active != self.field_array[-1])):
            self.center_win.activate_object(self.field_array[
                self.field_array.index(active) + 1])
            return None
        return input_key

    def validate(self):
        '''Validate entered data, including contacting Oracle to authenticate.
        '''

        # Check for override.  Save old values.  Retrieve any new ones.  Check
        # for changes.  If no changes and user can override, return without
        # validation.

        old_ocm_hub = self.support.ocm_hub
        old_asr_hub = self.support.asr_hub

        if self.support.ocm_available:
            self.support.ocm_hub = CONV_NONE(self.ocm_hub_edit.get_text())
            self.support.ocm_hub = \
                SupportHubScreen.make_url(self.support.ocm_hub)
        if self.support.asr_available:
            self.support.asr_hub = CONV_NONE(self.asr_hub_edit.get_text())
            self.support.asr_hub = \
                SupportHubScreen.make_url(self.support.asr_hub)

        old_mos_email = self.support.mos_email
        old_mos_password = self.support.mos_password
        if self.show_mos_credentials:
            self.support.mos_email = CONV_NONE(self.mos_email_edit.get_text())
            self.support.mos_password = \
                CONV_NONE(self.mos_password_edit.get_text())

            # Sanitize the password edit field.
            if self.support.mos_password:
                self.mos_password_edit.set_text(_set_filler
                                                (self.mos_password_edit_width))
            else:
                self.mos_password_edit.clear_text()

            # If entered password changed, invalidate the encrypted ones that
            # come from the old entered one.
            if old_mos_password != self.support.mos_password:
                self.support.ocm_mos_password = None
                self.support.asr_mos_password = None

        creds_changed = ((old_ocm_hub != self.support.ocm_hub) or
                         (old_asr_hub != self.support.asr_hub) or
                         (old_mos_email != self.support.mos_email) or
                         (old_mos_password != self.support.mos_password))

        if self.error_override and not creds_changed:
            return
        self.error_override = False

        # Wipe out proxy information as it is orthogonal to hub information.
        if self.support.ocm_hub or self.support.asr_hub:
            self.support.proxy_hostname = ""
            self.support.proxy_port = ""
            self.support.proxy_user = ""
            self.support.proxy_password = ""

        # Check MOS email and password.
        (self.error_override, message) = \
            self.support.check_mos(self.error_override)
        if message:
            if self.error_override:
                message += _SAVE_ANYWAY_MSG
            raise UIMessage(message)

        # Err if both hubs are blank.
        if (not self.support.ocm_hub and not self.support.asr_hub):
            raise UIMessage(_("Please fill in one or more hubs "
                              "or press F3 to go back"))

        # Attempt authentication if email and password are non-blank.
        if self.support.mos_password:
            self.main_win.error_line.display_err(
                "Attempting to contact Oracle.  Please wait...")
            (ocm_status, asr_status) = \
                self.support.phone_home(SupportInfo.HUB)
            self.main_win.error_line.clear_err()

            if self.show_mos_credentials:
                # Sanitize MOS password.  It is replaced by less sensitive data
                if ((self.support.ocm_mos_password or
                     self.support.ocm_ciphertext or
                     not self.support.ocm_available or
                     ocm_status == SupportInfo.OCM_NO_ENCR) and
                    (self.support.asr_mos_password or
                     self.support.asr_private_key or
                     not self.support.asr_available or
                     asr_status == SupportInfo.ASR_NO_ENCR)):
                    self.support.mos_password = \
                        _set_filler(self.mos_password_edit_width)
                else:
                    self.support.mos_password = None

            # A clear OCM and ASR mos password reflects success.  Clear them as
            # they could have been set on a previous failure.
            if ocm_status == SupportInfo.OCM_SUCCESS:
                self.support.ocm_mos_password = None
            if asr_status == SupportInfo.ASR_SUCCESS:
                self.support.asr_mos_password = None

            # Unless OCM and ASR both returned BAD_CRED, allow override.
            # If successful, no exception will be raised and control won't
            # return here again.
            #
            # If one of OCM or ASR accepted the credentials but the other did
            # not, there is a bigger problem somewhere.  Allow override.
            if (((ocm_status != SupportInfo.OCM_BAD_CRED) and
                 self.support.ocm_available) or
                ((asr_status != SupportInfo.ASR_BAD_CRED) and
                 self.support.asr_available)):
                self.error_override = True
            else:
                self.show_mos_credentials = True

            message = SupportInfo.phone_home_msg(ocm_status, asr_status)
            if message:
                # Redisplay screen to include MOS credentials if needed.
                if self.show_mos_credentials:
                    self.center_win.make_inactive()
                    self._show()
                    self.main_win.do_update()
                if self.error_override:
                    message += _SAVE_ANYWAY_MSG
                raise UIMessage(message)

    def url_valid(self, edit_field):
        '''Transform the edit_field's value into a valid URL if needed.'''
        edit_field.set_text(SupportHubScreen.make_url(edit_field.get_text()))

    @staticmethod
    def make_url(value):
        '''Transform 'value' into a valid URL if needed.'''
        if value is None or "://" in value:
            return value
        if value:
            return "http://" + value

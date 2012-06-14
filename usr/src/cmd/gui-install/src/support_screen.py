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
Support Registration Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import logging
import time
import threading

import gobject
import gtk

from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.gui_install_common import _, \
    make_url, modal_dialog, open_browser, GLADE_ERROR_MSG, INTERNAL_ERR_MSG
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile import from_engine
from solaris_install.sysconfig.profile.support_info import SupportInfo


LOGGER = None
MAX_PORT = 65535
VALIDATION_ERROR_MSG = "Validation Error:"
AUTH_SLEEP_INTERVAL = 0.1

# Strings displayed in GUI
SUPPORT_SCREEN_TITLE = _("Support Registration")
SUPPORT_SCREEN_SUBTITLE = _(" ")
ANON_EMAIL_ADDRESS = _("anonymous@oracle.com")
MISSING_PASSWD_ERROR = _("You must enter a valid My Oracle Support password "
    "to receive security updates.")
MISSING_PROXY_HOST_ERROR = _("Hostname must be given for Proxy option")
PROXY_USER_PASS_ERROR = _("Proxy Username and Password error")
NO_HUB_ERROR = _("Neither Hub entered")
NO_REG_WARN_MSG = _("Do you wish to remain uninformed of critical security "
    "issues in your configuration?")
ENTER_VALID_EMAIL_MSG = _("Enter a valid email address.")
ENTER_VALID_PASSWD_MSG = _("Enter a valid My Oracle Support password.")
ENTER_PROXY_HOST_MSG = _("Enter a valid Proxy Hostname")
ENTER_PROXY_USER_PASS_MSG = _("Either enter both Proxy Username and Password, "
    "or neither")
ENTER_OCM_ASR_MSG = _("Enter OCM Hub URL and/or ASR Manager URL")
AUTHENTICATING_MSG = _("Contacting Oracle to authenticate credentials...")
OVERRIDE_ALLOWED_MSG = _("Press 'Next' again to continue anyway")
OCM_AUTH_FAILED_MSG = _("Failed to authenticate with Oracle OCM.")
ASR_AUTH_FAILED_MSG = _("Failed to authenticate with Oracle ASR.")


class SupportScreen(BaseScreen):
    '''
        The Support Registration screen.
    '''

    def __init__(self, builder):
        ''' Initializer method - called from constructor.

            Params:
            - builder, a gtk.Builder object, used to retrieve Gtk+
              widgets from Glade XML files.

            Returns: Nothing
        '''
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(SupportScreen, self).__init__(builder)
        self.name = "Support Screen"

        self._support_email_entry = None
        self._support_authenticate_checkbox = None
        self._support_authenticate_section = None
        self._support_password_entry = None
        self._support_net_access_section = None
        self._support_no_proxy_radio = None
        self._support_proxy_radio = None
        self._support_proxy_section = None
        self._support_proxy_hostname_entry = None
        self._support_proxy_port_entry = None
        self._support_proxy_username_entry = None
        self._support_proxy_password_entry = None
        self._support_aggregation_radio = None
        self._support_aggregation_section = None
        self._support_ocm_entry = None
        self._support_asr_entry = None
        self._support_status_label = None
        self._toplevel = None

        self._email = None
        self._mos_pass = None
        self._proxy_hostname = None
        self._proxy_port = None
        self._proxy_username = None
        self._proxy_pass = None
        self._ocm_url = None
        self._asr_url = None
        self._auth_chosen = None
        self._no_proxy_chosen = None
        self._proxy_chosen = None
        self._aggregation_chosen = None
        self._support_info = None
        self._last_validation_ok = False
        self._allow_error_override = False
        self._allow_no_reg_override = False

        # Fetch all the gtk.Builder widgets we need in this class
        self._support_email_entry = self.builder.get_object(
            "support_email_entry")
        self._support_authenticate_checkbox = self.builder.get_object(
            "support_authenticate_checkbox")
        self._support_authenticate_section = self.builder.get_object(
            "support_authenticate_section")
        self._support_password_entry = self.builder.get_object(
            "support_password_entry")
        self._support_net_access_section = self.builder.get_object(
            "support_net_access_section")
        self._support_no_proxy_radio = self.builder.get_object(
            "support_no_proxy_radio")
        self._support_proxy_radio = self.builder.get_object(
            "support_proxy_radio")
        self._support_proxy_section = self.builder.get_object(
            "support_proxy_section")
        self._support_proxy_hostname_entry = self.builder.get_object(
            "support_proxy_hostname_entry")
        self._support_proxy_port_entry = self.builder.get_object(
            "support_proxy_port_entry")
        self._support_proxy_username_entry = self.builder.get_object(
            "support_proxy_username_entry")
        self._support_proxy_password_entry = self.builder.get_object(
            "support_proxy_password_entry")
        self._support_aggregation_radio = self.builder.get_object(
            "support_aggregation_radio")
        self._support_aggregation_section = self.builder.get_object(
            "support_aggregation_section")
        self._support_ocm_entry = self.builder.get_object(
            "support_ocm_entry")
        self._support_asr_entry = self.builder.get_object(
            "support_asr_entry")
        self._support_status_label = self.builder.get_object(
            "support_status_label")

        if None in [self._support_email_entry,
                    self._support_authenticate_checkbox,
                    self._support_authenticate_section,
                    self._support_password_entry,
                    self._support_net_access_section,
                    self._support_no_proxy_radio,
                    self._support_proxy_radio,
                    self._support_proxy_section,
                    self._support_proxy_hostname_entry,
                    self._support_proxy_port_entry,
                    self._support_proxy_username_entry,
                    self._support_proxy_password_entry,
                    self._support_aggregation_radio,
                    self._support_aggregation_section,
                    self._support_ocm_entry,
                    self._support_asr_entry,
                    self._support_status_label,
                   ]:
            modal_dialog(INTERNAL_ERR_MSG, GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    def enter(self):
        ''' Show the Support Registration Screen.

            This method is called when the user navigates to this screen
            via the Back or Next buttons.
        '''

        if self._toplevel is None:
            self._first_time_init()

        self._toplevel = self.set_main_window_content("support_top_level")

        # Screen-specific configuration
        self.activate_stage_label("supportstagelabel")
        self.set_titles(SUPPORT_SCREEN_TITLE, SUPPORT_SCREEN_SUBTITLE, None)
        self._support_status_label.hide()
        self._toplevel.show()
        self._support_email_entry.grab_focus()
        self.set_back_next(back_sensitive=True, next_sensitive=True)

        return False

    def go_back(self):
        ''' Perform any checks required before allowing to user to
            go back to the previous screen.

            Does nothing.
        '''
        pass

    def validate(self):
        ''' Validate the user selections before proceeding.

            Raises: NotOkToProceedError
        '''
        LOGGER.info("Starting Support Registration validation.")

        # Gather user inputs from screen
        email = None
        if self._support_email_entry.get_text():
            email = self._support_email_entry.get_text()

        auth_chosen = self._support_authenticate_checkbox.get_active()

        mos_pass = None
        if auth_chosen:
            if self._support_password_entry.get_text():
                mos_pass = self._support_password_entry.get_text()

        no_proxy_chosen = self._support_no_proxy_radio.get_active()

        proxy_chosen = self._support_proxy_radio.get_active()

        proxy_hostname = None
        proxy_port = None
        proxy_username = None
        proxy_pass = None
        if proxy_chosen:
            if self._support_proxy_hostname_entry.get_text():
                proxy_hostname = self._support_proxy_hostname_entry.get_text()

            if self._support_proxy_port_entry.get_text():
                proxy_port = self._support_proxy_port_entry.get_text()

            if self._support_proxy_username_entry.get_text():
                proxy_username = self._support_proxy_username_entry.get_text()

            if self._support_proxy_password_entry.get_text():
                proxy_pass = self._support_proxy_password_entry.get_text()

        aggregation_chosen = self._support_aggregation_radio.get_active()

        ocm_url = None
        asr_url = None
        if aggregation_chosen:
            if self._support_ocm_entry.get_text():
                ocm_url = self._support_ocm_entry.get_text()

            if self._support_asr_entry.get_text():
                asr_url = self._support_asr_entry.get_text()

        LOGGER.debug("User inputs:")
        LOGGER.debug("Email               [%s]", email)
        LOGGER.debug("Enter MOS password? [%s]", auth_chosen)
        if mos_pass is not None:
            log_pw = '*' * len(mos_pass)
        else:
            log_pw = None
        LOGGER.debug("  MOS Password      [%s]", log_pw)
        LOGGER.debug("No proxy?           [%s]", no_proxy_chosen)
        LOGGER.debug("Proxy?              [%s]", proxy_chosen)
        LOGGER.debug("  Hostname          [%s]", proxy_hostname)
        LOGGER.debug("  Port              [%s]", proxy_port)
        LOGGER.debug("  Username          [%s]", proxy_username)
        if proxy_pass is not None:
            log_pw = '*' * len(proxy_pass)
        else:
            log_pw = None
        LOGGER.debug("  Password          [%s]", log_pw)
        LOGGER.debug("Aggregation Hubs?   [%s]", aggregation_chosen)
        LOGGER.debug("  OCM Hub URL       [%s]", ocm_url)
        LOGGER.debug("  ASR Manager URL   [%s]", asr_url)

        # Validate user inputs:
        # ERROR - password entered, but no email
        if mos_pass and not email:
            self._support_email_entry.grab_focus()
            msg1 = SupportInfo.MSGS["pswd_no_email"]
            msg2 = ENTER_VALID_EMAIL_MSG
            LOGGER.error(VALIDATION_ERROR_MSG)
            LOGGER.error(msg1)
            modal_dialog(msg1, msg2)
            raise NotOkToProceedError(msg1)

        # ERROR - incorrectly formatted email address
        if email:
            if '@' not in email or email[-1] == '@':
                self._support_email_entry.grab_focus()
                msg1 = SupportInfo.MSGS["missing_@"]
                msg2 = ENTER_VALID_EMAIL_MSG
                LOGGER.error(VALIDATION_ERROR_MSG)
                LOGGER.error(msg1)
                modal_dialog(msg1, msg2)
                raise NotOkToProceedError(msg1)

        # ERROR - authentication requested, but no password given
        if auth_chosen and mos_pass is None:
            self._support_password_entry.grab_focus()
            msg1 = MISSING_PASSWD_ERROR
            msg2 = ENTER_VALID_PASSWD_MSG
            LOGGER.error(VALIDATION_ERROR_MSG)
            LOGGER.error(msg1)
            modal_dialog(msg1, msg2)
            raise NotOkToProceedError(msg1)

        # ERROR - Proxy chosen, but no proxy hostname given
        if proxy_chosen and not proxy_hostname:
            self._support_proxy_hostname_entry.grab_focus()
            msg1 = MISSING_PROXY_HOST_ERROR
            msg2 = ENTER_PROXY_HOST_MSG
            LOGGER.error(VALIDATION_ERROR_MSG)
            LOGGER.error(msg1)
            modal_dialog(msg1, msg2)
            raise NotOkToProceedError(msg1)

        # ERROR - only one of proxy password or username was given
        if proxy_chosen and (bool(proxy_username) != bool(proxy_pass)):
            self._support_proxy_username_entry.grab_focus()
            msg1 = PROXY_USER_PASS_ERROR
            msg2 = ENTER_PROXY_USER_PASS_MSG
            LOGGER.error(VALIDATION_ERROR_MSG)
            LOGGER.error(msg1)
            modal_dialog(msg1, msg2)
            raise NotOkToProceedError(msg1)

        # ERROR - Aggregation Hub chosen, but neither OCM nor ASR Hub given
        if aggregation_chosen and not ocm_url and not asr_url:
            self._support_ocm_entry.grab_focus()
            msg1 = NO_HUB_ERROR
            msg2 = ENTER_OCM_ASR_MSG
            LOGGER.error(VALIDATION_ERROR_MSG)
            LOGGER.error(msg1)
            modal_dialog(msg1, msg2)
            raise NotOkToProceedError(msg1)

        # Determine if user inputs have changed in any material way from
        # last time authentication was attempted
        any_changes = False
        if self._support_info is None:
            # First time through
            sc_profile = from_engine()
            if sc_profile.support is None:
                sc_profile.support = SupportInfo()
            self._support_info = sc_profile.support
            any_changes = True
        else:
            if email != self._email:
                any_changes = True
            elif auth_chosen != self._auth_chosen:
                any_changes = True
            elif auth_chosen and mos_pass != self._mos_pass:
                any_changes = True
            # Note: only one of no_proxy_chosen, proxy_chosen,
            # aggregation_chosen can be True at a time.
            elif no_proxy_chosen != self._no_proxy_chosen:
                any_changes = True
            elif proxy_chosen != self._proxy_chosen:
                any_changes = True
            elif proxy_chosen:
                if proxy_hostname != self._proxy_hostname:
                    any_changes = True
                elif proxy_port != self._proxy_port:
                    any_changes = True
                elif proxy_username != self._proxy_username:
                    any_changes = True
                elif proxy_pass != self._proxy_pass:
                    any_changes = True
            elif aggregation_chosen:
                if ocm_url != self._ocm_url:
                    any_changes = True
                elif asr_url != self._asr_url:
                    any_changes = True

        # WARNING - don't allow user to skip registration without
        # showing them a warning message
        if not email and not self._allow_no_reg_override:
            # set flag so we only show this once; next time just proceed
            self._allow_no_reg_override = True
            msg1 = SupportInfo.MSGS["no_email"]
            msg2 = NO_REG_WARN_MSG
            LOGGER.info("Validation Warning:")
            LOGGER.info(msg1)
            ok_to_proceed = modal_dialog(msg1, msg2, two_buttons=True,
                                         yes_no=True)

            if ok_to_proceed:
                self._clear_sc_profile()
                return

            self._support_email_entry.grab_focus()
            raise NotOkToProceedError(msg1)

        # Save values entered for comparison next time around
        self._email = email
        self._auth_chosen = auth_chosen
        self._mos_pass = mos_pass
        self._no_proxy_chosen = no_proxy_chosen
        self._proxy_chosen = proxy_chosen
        self._proxy_hostname = proxy_hostname
        self._proxy_port = proxy_port
        self._proxy_username = proxy_username
        self._proxy_pass = proxy_pass
        self._aggregation_chosen = aggregation_chosen
        self._ocm_url = ocm_url
        self._asr_url = asr_url

        # Handle situations where we can proceed without doing authentication

        # User still authenticated from last time and hasn't changed anything
        if not any_changes and self._last_validation_ok:
            LOGGER.debug("No need to repeat validation - continuing")
            return

        # User explicitly does not wish to register
        if not self._email and not self._auth_chosen \
           and self._allow_no_reg_override:
            # Ensure no previous values are saved in SC Profile and proceed
            LOGGER.info("No email or MOS password given - not registering")
            self._clear_sc_profile()
            return

        # User overriding failed authentication and wishes to proceed anyway
        if not any_changes and self._allow_error_override:
            LOGGER.debug("Allowing override of auth error - continuing")
            return

        # User didn't provide a password, so no point trying to authenticate
        if not self._mos_pass:
            # Save what we have to SC Profile in DOC and proceed
            LOGGER.debug("Allowing override of auth error - continuing")
            self._update_sc_profile()
            return

        # Save what we have to SC Profile in DOC and perform authentication
        self._update_sc_profile()
        self._do_authentication()

    #--------------------------------------------------------------------------
    # Gtk+ signal handler methods

    def authenticate_checkbox_toggled(self, widget, user_data=None):
        ''' Handler for "toggled" signal in the authentication checkbox.

            Enables Password field when checkbox is checked and disables it
            when checkbox is unchecked.
        '''
        if widget.get_active():
            self._support_authenticate_section.set_sensitive(True)
        else:
            self._support_authenticate_section.set_sensitive(False)

    def no_proxy_radio_toggled(self, widget, user_data=None):
        ''' Handler for "toggled" signal in the 'No proxy' radio button.

            Hides the Proxy and Aggregation Hubs fields when button is
            pressed.
        '''
        if widget.get_active():
            self._support_proxy_section.hide()
            self._support_aggregation_section.hide()

    def proxy_radio_toggled(self, widget, user_data=None):
        ''' Handler for "toggled" signal in the 'Proxy' radio button.

            Shows the Proxy fields and hides the Aggregation Hubs fields
            when button is pressed.
        '''
        if widget.get_active():
            self._support_proxy_section.show()
            self._support_aggregation_section.hide()

    def aggregation_radio_toggled(self, widget, user_data=None):
        ''' Handler for "toggled" signal in the 'Aggregation Hubs' radio
            button.

            Hides the Proxy fields and shows the Aggregation Hubs fields
            when button is pressed.
        '''
        if widget.get_active():
            self._support_proxy_section.hide()
            self._support_aggregation_section.show()

    def proxy_port_insert_text(self, widget, new_text, new_text_len, pos):
        ''' Handler for "insert-text" signal in the Port field.

            Ensures only numerical value <= MAX_PORT can be entetred.
        '''
        # Ensure the inserted text consists only of digit(s)
        for char in new_text:
            if not char.isdigit():
                gobject.GObject.stop_emission(widget, "insert-text")
                return

        old_text = widget.get_text()
        old_len = len(old_text)
        pos = widget.get_position()
        if pos < 0 or pos > old_len:
            return

        updated_text = "%s%s%s" % \
            (old_text[0:pos], new_text, old_text[pos:old_len])

        if int(updated_text) > MAX_PORT:
            gobject.GObject.stop_emission(widget, "insert-text")

    def details_link_activated(self, widget, uri, user_data=None):
        ''' Handler for "activate-link" signal in header label
            ('http://...support/policies...').

            Open Browser with link from screen.
        '''
        open_browser(uri)
        return True

    def url_field_changed(self, widget, event=None, data=None):
        ''' Handler for "changed" signal in OCM and ASR URL fields.

            Prepend "http://" if required.
        '''
        current_val = widget.get_text()
        url_val = make_url(current_val)
        if current_val != url_val:
            widget.set_text(url_val)

    #--------------------------------------------------------------------------
    # Private methods

    def _first_time_init(self):
        '''
            Screen initiatization tasks that are only to be performed on the
            first occasion this screen is brought up.
        '''
        self._support_email_entry.set_text(ANON_EMAIL_ADDRESS)
        self._support_authenticate_section.set_sensitive(True)
        self._support_authenticate_checkbox.set_active(True)
        self._support_proxy_section.hide()
        self._support_aggregation_section.hide()
        self._support_no_proxy_radio.set_active(True)

    def _clear_sc_profile(self):
        '''
            Clear out any support-related fields from SC Profile in DOC.
        '''
        self._support_info.mos_email = None
        self._support_info.mos_password = None
        self._support_info.ocm_index = None
        self._support_info.ocm_ciphertext = None
        self._support_info.asr_mos_password = None
        self._support_info.asr_index = None
        self._support_info.asr_public_key = None
        self._support_info.asr_private_key = None

        self._support_info.proxy_hostname = None
        self._support_info.proxy_port = None
        self._support_info.proxy_user = None
        self._support_info.proxy_password = None
        self._support_info.ocm_hub = None
        self._support_info.asr_hub = None

        self._support_info.ocm_mos_password = None
        self._support_info.asr_clientID = None
        self._support_info.asr_timestamp = None

    def _update_sc_profile(self):
        '''
            Update support-related fields in SC Profile in DOC with
            the our latest data.
        '''
        self._support_info.mos_email = self._email
        self._support_info.mos_password = self._mos_pass

        if self._no_proxy_chosen:
            self._support_info.netcfg = SupportInfo.DIRECT
            self._support_info.proxy_hostname = ""
            self._support_info.proxy_port = ""
            self._support_info.proxy_user = ""
            self._support_info.proxy_password = ""
            self._support_info.ocm_hub = ""
            self._support_info.asr_hub = ""
        elif self._proxy_chosen:
            self._support_info.netcfg = SupportInfo.PROXY
            self._support_info.proxy_hostname = self._proxy_hostname
            self._support_info.proxy_port = self._proxy_port
            self._support_info.proxy_user = self._proxy_username
            self._support_info.proxy_password = self._proxy_pass
            self._support_info.ocm_hub = ""
            self._support_info.asr_hub = ""
        else:
            # must be Aggregation hub
            self._support_info.netcfg = SupportInfo.HUB
            self._support_info.proxy_hostname = ""
            self._support_info.proxy_port = ""
            self._support_info.proxy_user = ""
            self._support_info.proxy_password = ""
            self._support_info.ocm_hub = self._ocm_url
            self._support_info.asr_hub = self._asr_url

    def _do_authentication(self):
        ''' Setup and run a thread to call OCM/ASR authentication.

            Returns: nothing

            Raises: NotOkToProceedError
        '''
        if self._no_proxy_chosen:
            net_mode = SupportInfo.DIRECT
        elif self._proxy_chosen:
            net_mode = SupportInfo.PROXY
        else:
            # must be Aggregation hub
            net_mode = SupportInfo.HUB

        # This operation can take more than a few seconds, so:
        # - disable the Back/Next buttons
        # - show a status message
        # - run authentication in a separate thread
        # - wait for thread to finish
        # (otherwise GUI would appear unresponsive)
        self.set_back_next(back_sensitive=False, next_sensitive=False)
        self._support_status_label.set_markup(
            '<span font_desc="Bold">%s</span>' % AUTHENTICATING_MSG)
        self._support_status_label.show()
        thread = AuthenticationThread(self._support_info, net_mode)
        # Keep passing control back to Gtk+ to process its event queue
        # until AuthenticationThread has completed.
        while thread.isAlive():
            while gtk.events_pending():
                gtk.main_iteration(False)
            # allow the thread some time to do it's work
            time.sleep(AUTH_SLEEP_INTERVAL)
        ocm_status = thread.ocm_status
        asr_status = thread.asr_status

        # Log the results
        LOGGER.debug("authentication return values")
        LOGGER.debug("  ocm_status       [%s]", ocm_status)
        LOGGER.debug("  asr_status       [%s]", asr_status)

        # Reset the screen
        self._support_status_label.hide()
        self.set_back_next(back_sensitive=True, next_sensitive=True)

        # Handle any errors returned by either OCM or ASR
        if (ocm_status != SupportInfo.OCM_SUCCESS or
            asr_status != SupportInfo.ASR_SUCCESS):
            LOGGER.error("Error returned by OCM and/or ASR:")

            self._last_validation_ok = False
            # Construct error messages for the failures reported
            # by OCM and/or ASR
            err_title = ''
            err_msg = ''
            if ocm_status != SupportInfo.OCM_SUCCESS:
                err_title += OCM_AUTH_FAILED_MSG
                if ocm_status == SupportInfo.PH_TIMEOUT:
                    err_msg += SupportInfo.MSGS["ocm_timeout"]
                elif ocm_status == SupportInfo.OCM_BAD_CRED:
                    err_msg += SupportInfo.MSGS["ocm_bad_cred"]
                elif ocm_status == SupportInfo.OCM_NET_ERR:
                    err_msg += SupportInfo.MSGS["ocm_net_err"]
                else:
                    err_msg += SupportInfo.MSGS["ocm_auth_err"]
            if asr_status != SupportInfo.ASR_SUCCESS:
                if err_title:
                    err_title += "\n"
                if err_msg:
                    err_msg += "\n"

                err_title += ASR_AUTH_FAILED_MSG
                if asr_status == SupportInfo.PH_TIMEOUT:
                    err_msg += SupportInfo.MSGS["asr_timeout"]
                elif asr_status == SupportInfo.ASR_BAD_CRED:
                    err_msg += SupportInfo.MSGS["asr_bad_cred"]
                elif asr_status == SupportInfo.ASR_NET_ERR:
                    err_msg += SupportInfo.MSGS["asr_net_err"]
                else:
                    err_msg += SupportInfo.MSGS["asr_auth_err"]

            # If both OCM and ASR returned BAD_CRED, then do not allow
            # error override; otherwise do.
            # (eg either the failure(s) were due to networking, etc, or
            # one returned BAD_CRED and other didn't - which indicates
            # a problem with the auth servers)
            if (ocm_status == SupportInfo.OCM_BAD_CRED and
                asr_status == SupportInfo.ASR_BAD_CRED):
                LOGGER.info("Both OCM and ASR returned BAD_CRED - not "
                    "allowing error override")
                self._allow_error_override = False
            else:
                LOGGER.info("Failure(s) were either not due to BAD_CRED, "
                    " or were inconsistent - allowing errror override")
                self._allow_error_override = True

            if self._allow_error_override:
                err_msg = err_msg + "\n\n" + OVERRIDE_ALLOWED_MSG

            self._support_email_entry.grab_focus()
            LOGGER.error(err_msg)
            modal_dialog(err_title, err_msg)
            raise NotOkToProceedError(err_msg)

        # Authentication was successful.
        # Set flag so we don't have to authenticate again if user doesn't
        # change anything
        LOGGER.info("Support authentication was successful.")
        self._last_validation_ok = True


class AuthenticationThread(threading.Thread):
    '''
        Thread class for running authentication.
    '''

    def __init__(self, support_info, net_mode, force_encrypt_only=False):
        ''' Initializer method - called from constructor.

            Params:
            - support_info, a SupportInfo object
            - net_mode, one of SupportInfo.DIRECT, SupportInfo.PROXY,
              SupportInfo.HUB
            - force_encrypt_only, Boolean

            Returns: Nothing
        '''
        threading.Thread.__init__(self)

        self._support_info = support_info
        self._net_mode = net_mode
        self._force_encrypt_only = force_encrypt_only

        self.ocm_status = None
        self.asr_status = None

        # invoke run()
        self.start()

    def run(self):
        ''' Override run method from parent class.

            Makes the actual authentication call.

            Sets:
            - self.ocm_status
            - self.asr_status
        '''
        (self.ocm_status, self.asr_status) = \
            self._support_info.phone_home(self._net_mode,
                force_encrypt_only=self._force_encrypt_only)

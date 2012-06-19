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
Disk Discovery Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import logging
import re
import string
import time
import threading

import gobject
import gtk

from solaris_install import run, CalledProcessError
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.gui_install_common import _, \
    is_discovery_complete, modal_dialog, queue_td_iscsi, \
    set_td_results_state, start_td_iscsi, GLADE_ERROR_MSG, \
    ISCSI_LABEL
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.libima.ima import is_iscsiboot
from solaris_install.target.physical import Disk, Iscsi, ISCSIADM
from solaris_install.sysconfig.profile.ip_address import IPAddress


LOGGER = None

# Regex for iSCSI Qualified Names
IQN_RE = re.compile("iqn\.\d{4}\-\d{2}\.\w+\.\w+", re.I)


class DiskDiscoveryScreen(BaseScreen):
    '''
        The Disk Discovery screen.
    '''

    # Strings displayed in GUI
    INTERNAL_ERROR_MSG = _("Internal error")
    DISK_DISCOVERY_TITLE = _("Disk Discovery")
    DISK_DISCOVERY_SUBTITLE = _("What types of disks would you like the "
                                "Installer to discover?")
    NO_DISK_TYPE_SELECTED_MSG = _("No disk types selected.")
    SELECT_DISK_TYPE_MSG = _("You must select at least one of the disk types "
                             "to search for.")
    TARGET_IP_1_FIELD = _("Target IP (#1)")
    TARGET_IP_2_FIELD = _("Target IP (#2)")
    TARGET_IP_3_FIELD = _("Target IP (#3)")
    TARGET_IP_4_FIELD = _("Target IP (#4)")
    TARGET_LUN_FIELD = _("LUN")
    NO_INITIATOR_NODE_MSG = _("Could not obtain Initiator Node Name for "
                              "this host")
    REQUIRED_FIELD_MISSING_MSG = _("Required field not entered")
    ENTER_REQUIRED_FIELD_MSG = _("You must enter a value for : ")
    INVALID_IP_MSG = _("Invalid Target IP address")
    INVALID_TARGET_IQN_MSG = _("Invalid Target IQN string")
    INVALID_INITIATOR_IQN_MSG = _("Invalid Initiator IQN string")
    ENTER_VALID_VALUE_MSG = _("Enter a valid value")
    CHAP_PASSWORD_INVALID_LENGTH = _("CHAP password must be between 12 and 16 "
                                     "characters")
    CHAP_USERNAME_MISSING = _("CHAP username not specified")
    CHAP_PASSWORD_MISSING = _("CHAP password not specified")
    MAPPING_TARGET_MSG = _("Mapping iSCSI Target...")
    MAPPING_LUN_MSG = _("Mapping iSCSI LUN...")
    CANNOT_MAP_LUN_MSG = _("Unable to map iSCSI LUN")

    def __init__(self, builder):
        ''' Initializer method - called from constructor.

            Params:
            - builder, a gtk.Builder object, used to retrieve Gtk+
              widgets from Glade XML files.

            Returns: Nothing
        '''
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(DiskDiscoveryScreen, self).__init__(builder)
        self.name = "Disk Discovery Screen"
        self._dhcp_ip = None
        self._dhcp_port = None
        self._dhcp_lun = None
        self._dhcp_target = None
        self._iscsi = None
        self._target_ip = None
        self._target_lun = None
        self._target_name = None
        self._target_port = None
        self._initiator_name = None
        self._chap_name = None
        self._chap_password = None
        self._toplevel = None

        # Fetch all the gtk.Builder widgets we need in this class
        self._discovery_top_level_vbox = self.builder.get_object(
            "discovery_top_level_vbox")
        self._discovery_local_check = self.builder.get_object(
            "discovery_local_check")
        self._discovery_iscsi_check = self.builder.get_object(
            "discovery_iscsi_check")
        self._discovery_iscsi_detail_vbox = self.builder.get_object(
            "discovery_iscsi_detail_vbox")
        self._discovery_dhcp_radio = self.builder.get_object(
            "discovery_dhcp_radio")
        self._discovery_dhcp_unavail_label = self.builder.get_object(
            "discovery_dhcp_unavail_label")
        self._discovery_criteria_radio = self.builder.get_object(
            "discovery_criteria_radio")
        self._discovery_criteria_detail_table = self.builder.get_object(
            "discovery_criteria_detail_table")
        self._discovery_target_ip_1_entry = self.builder.get_object(
            "discovery_target_ip_1_entry")
        self._discovery_target_ip_2_entry = self.builder.get_object(
            "discovery_target_ip_2_entry")
        self._discovery_target_ip_3_entry = self.builder.get_object(
            "discovery_target_ip_3_entry")
        self._discovery_target_ip_4_entry = self.builder.get_object(
            "discovery_target_ip_4_entry")
        self._discovery_lun_entry = self.builder.get_object(
            "discovery_lun_entry")
        self._discovery_target_name_entry = self.builder.get_object(
            "discovery_target_name_entry")
        self._discovery_port_entry = self.builder.get_object(
            "discovery_port_entry")
        self._discovery_initiator_name_label = self.builder.get_object(
            "discovery_initiator_name_label")
        self._discovery_initiator_name_entry = self.builder.get_object(
            "discovery_initiator_name_entry")
        self._discovery_iscsi_boot_label = self.builder.get_object(
            "discovery_iscsi_boot_label")
        self._discovery_chap_check = self.builder.get_object(
            "discovery_chap_check")
        self._discovery_chap_detail_table = self.builder.get_object(
            "discovery_chap_detail_table")
        self._discovery_chap_name_entry = self.builder.get_object(
            "discovery_chap_name_entry")
        self._discovery_chap_pass_entry = self.builder.get_object(
            "discovery_chap_pass_entry")
        self._discovery_status_label = self.builder.get_object(
            "discovery_status_label")

        if None in [self._discovery_top_level_vbox,
                    self._discovery_local_check,
                    self._discovery_iscsi_check,
                    self._discovery_iscsi_detail_vbox,
                    self._discovery_dhcp_radio,
                    self._discovery_dhcp_unavail_label,
                    self._discovery_criteria_radio,
                    self._discovery_criteria_detail_table,
                    self._discovery_target_ip_1_entry,
                    self._discovery_target_ip_2_entry,
                    self._discovery_target_ip_3_entry,
                    self._discovery_target_ip_4_entry,
                    self._discovery_lun_entry,
                    self._discovery_target_name_entry,
                    self._discovery_port_entry,
                    self._discovery_initiator_name_label,
                    self._discovery_initiator_name_entry,
                    self._discovery_iscsi_boot_label,
                    self._discovery_chap_check,
                    self._discovery_chap_detail_table,
                    self._discovery_chap_name_entry,
                    self._discovery_chap_pass_entry,
                    self._discovery_status_label]:
            modal_dialog(self.INTERNAL_ERROR_MSG, GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    def enter(self):
        ''' Show the Disk Screen.

            This method is called when the user navigates to this screen
            via the Back and Next buttons.
        '''
        if self._toplevel is None:
            self._first_time_init()

        self._toplevel = self.set_main_window_content(
            "discovery_top_level_vbox")

        # Screen-specific configuration
        self.activate_stage_label("diskdiscoverystagelabel")
        self.set_titles(self.DISK_DISCOVERY_TITLE,
                        self.DISK_DISCOVERY_SUBTITLE, None)
        self._discovery_status_label.hide()
        self._toplevel.show()
        self._discovery_local_check.grab_focus()
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
        LOGGER.info("Starting Disk Discovery validation.")

        iscsi = None
        doc = InstallEngine.get_instance().doc

        # error #1 - at least one disk type must be checked
        if not self._discovery_local_check.get_active() and \
           not self._discovery_iscsi_check.get_active():
            msg = "No disk types selected."
            LOGGER.error(self.NO_DISK_TYPE_SELECTED_MSG)
            modal_dialog(self.NO_DISK_TYPE_SELECTED_MSG,
                         self.SELECT_DISK_TYPE_MSG)
            raise NotOkToProceedError(msg)

        if self._discovery_iscsi_check.get_active():
            # Save the on-screen iSCSI criteria values
            self._target_ip = ''
            text = self._discovery_target_ip_1_entry.get_text()
            if len(text):
                self._target_ip += text
            self._target_ip += '.'
            text = self._discovery_target_ip_2_entry.get_text()
            if len(text):
                self._target_ip += text
            self._target_ip += '.'
            text = self._discovery_target_ip_3_entry.get_text()
            if len(text):
                self._target_ip += text
            self._target_ip += '.'
            text = self._discovery_target_ip_4_entry.get_text()
            if len(text):
                self._target_ip += text

            text = self._discovery_lun_entry.get_text()
            if len(text):
                self._target_lun = text
            else:
                self._target_lun = None

            text = self._discovery_target_name_entry.get_text()
            if len(text):
                self._target_name = text
            else:
                self._target_name = None

            text = self._discovery_port_entry.get_text()
            if len(text):
                self._target_port = text
            else:
                self._target_port = None

            text = self._discovery_initiator_name_entry.get_text()
            if len(text):
                self._initiator_name = text
            else:
                self._initiator_name = None

            if self._discovery_chap_check.get_active():
                text = self._discovery_chap_name_entry.get_text()
                if len(text):
                    self._chap_name = text
                else:
                    self._chap_name = None

                text = self._discovery_chap_pass_entry.get_text()
                if len(text):
                    self._chap_password = text
                else:
                    self._chap_password = None
            else:
                self._chap_name = None
                self._chap_password = None

            LOGGER.info("iSCSI criteria")
            LOGGER.info("==============")
            LOGGER.info("Target IP: %s", self._target_ip)
            LOGGER.info("LUN: %s", self._target_lun)
            LOGGER.info("Target Name: %s", self._target_name)
            LOGGER.info("Port: %s", self._target_port)
            LOGGER.info("Initiator Name: %s", self._initiator_name)
            LOGGER.info("CHAP Name: %s", self._chap_name)
            if self._chap_password is not None:
                log_pw = '*' * len(self._chap_password)
            else:
                log_pw = None
            LOGGER.info("CHAP Password: %s", log_pw)

            # ERROR - required fields must be entered
            required_fields = {
                self._discovery_target_ip_1_entry: self.TARGET_IP_1_FIELD,
                self._discovery_target_ip_2_entry: self.TARGET_IP_2_FIELD,
                self._discovery_target_ip_3_entry: self.TARGET_IP_3_FIELD,
                self._discovery_target_ip_4_entry: self.TARGET_IP_4_FIELD,
            }
            #    self._discovery_lun_entry: self.TARGET_LUN_FIELD,
            for field in required_fields:
                if not field.get_text():
                    msg = self.REQUIRED_FIELD_MISSING_MSG
                    LOGGER.error(msg + " : " + required_fields[field])
                    modal_dialog(msg,
                        self.ENTER_REQUIRED_FIELD_MSG + required_fields[field])
                    field.grab_focus()
                    raise NotOkToProceedError(msg)

            # ERROR - IP must be proper IP address
            try:
                IPAddress.convert_address(self._target_ip)
            except ValueError as error:
                msg = self.INVALID_IP_MSG
                LOGGER.error(msg + " : " + str(error))
                modal_dialog(msg, str(error))
                self._discovery_target_ip_1_entry.grab_focus()
                raise NotOkToProceedError(msg)

            # ERROR - Initiator Name must match regular expression
            if self._initiator_name is not None:
                if IQN_RE.match(self._initiator_name) is None:
                    msg = self.INVALID_INITIATOR_IQN_MSG
                    LOGGER.error(msg)
                    modal_dialog(msg, self.ENTER_VALID_VALUE_MSG)
                    self._discovery_initiator_name_entry.grab_focus()
                    raise NotOkToProceedError(msg)

            # ERROR - Target name name must match regular expression
            if self._target_name is not None:
                if IQN_RE.match(self._target_name) is None:
                    msg = self.INVALID_TARGET_IQN_MSG
                    LOGGER.error(msg)
                    modal_dialog(msg, self.ENTER_VALID_VALUE_MSG)
                    self._discovery_target_name_entry.grab_focus()
                    raise NotOkToProceedError(msg)

            # ERROR - if CHAP name is given, password must also
            # be given, and vice versa
            if self._chap_name and not self._chap_password:
                msg = self.CHAP_PASSWORD_MISSING
                LOGGER.error(msg)
                modal_dialog(msg, self.ENTER_VALID_VALUE_MSG)
                self._discovery_chap_pass_entry.grab_focus()
                raise NotOkToProceedError(msg)
            if self._chap_password and not self._chap_name:
                msg = self.CHAP_USERNAME_MISSING
                LOGGER.error(msg)
                modal_dialog(msg, self.ENTER_VALID_VALUE_MSG)
                self._discovery_chap_name_entry.grab_focus()
                raise NotOkToProceedError(msg)

            # ERROR - CHAP password must be correct length
            if self._chap_password is not None:
                if not 12 <= len(self._chap_password) <= 16:
                    msg = self.CHAP_PASSWORD_INVALID_LENGTH
                    LOGGER.error(msg)
                    modal_dialog(msg, self.ENTER_VALID_VALUE_MSG)
                    self._discovery_chap_pass_entry.grab_focus()
                    raise NotOkToProceedError(msg)

            # ERROR - must be able to connect to LUN to verify iSCSI disk
            # teardown any currently-configured Iscsis before trying
            # to connect to new LUN
            old_iscsis = doc.volatile.get_children(name=ISCSI_LABEL,
                class_type=Iscsi)
            for old_iscsi in old_iscsis:
                try:
                    LOGGER.debug("teardown previous iSCSI: %s", old_iscsi)
                    old_iscsi.teardown()
                except CalledProcessError as error:
                    # Not a fatal error
                    LOGGER.warn("Iscsi.teardown failed: " + str(error))

                # remove from 'discovered targets' any Disks associated with
                # this iSCSI target
                if old_iscsi.ctd_list:
                    discovered = doc.persistent.get_first_child(
                        name=Target.DISCOVERED)

                    for disk in discovered.get_descendants(class_type=Disk):
                        if disk.ctd in old_iscsi.ctd_list:
                            disk.delete()

            iscsi = Iscsi(ISCSI_LABEL)
            iscsi.target_ip = self._target_ip
            iscsi.target_lun = self._target_lun
            iscsi.target_name = self._target_name
            iscsi.target_port = self._target_port
            # Don't attempt to change the initiator node name if iSCSI booting
            if not is_iscsiboot():
                iscsi.initiator_name = self._initiator_name
            iscsi.chap_name = self._chap_name
            iscsi.chap_password = self._chap_password

            # Depending on validity and location of IP, Iscsi.setup_iscsi()
            # can take a while, so show a status message and run setup_iscsi()
            # in a separate thread (otherwise the GUI would appear
            # unresponsive and the user may think it has hung).
            self.set_back_next(back_sensitive=False, next_sensitive=False)
            if iscsi.target_lun is not None:
                self._discovery_status_label.set_markup(
                    '<span font_desc="Bold">%s</span>' % self.MAPPING_LUN_MSG)
            else:
                self._discovery_status_label.set_markup(
                    '<span font_desc="Bold">%s</span>' %
                    self.MAPPING_TARGET_MSG)
            self._discovery_status_label.show()
            thread = SetupIscsiThread(iscsi)
            # Keep passing control back to Gtk+ to process its event queue
            # until SetupIscsiThread has completed.
            while thread.is_alive():
                while gtk.events_pending():
                    gtk.main_iteration(False)
                # allow the thread some time to do it's work
                time.sleep(0.1)

            self._discovery_status_label.hide()
            self.set_back_next(back_sensitive=True, next_sensitive=True)
            if thread.error is not None:
                msg = self.CANNOT_MAP_LUN_MSG
                LOGGER.error(msg)
                LOGGER.error(str(thread.error))
                modal_dialog(msg, str(thread.error))
                self._discovery_target_ip_1_entry.grab_focus()
                raise NotOkToProceedError(msg)

        # Validation is complete.  Now:
        # - save user choices (Local disks, iSCSI) in user profile
        # if iSCSI option was checked:
        #   - save Iscsi obj in DOC
        #   - run TargetDiscovery(iSCSI), either right now or when
        #     other TDs are finished
        profile = doc.volatile.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        if profile is None:
            raise RuntimeError("INTERNAL ERROR: Unable to retrieve "
                "InstallProfile from DataObjectCache")
        profile.set_disk_selections(
            show_local=self._discovery_local_check.get_active(),
            show_iscsi=self._discovery_iscsi_check.get_active())

        if self._discovery_iscsi_check.get_active():
            # There should only be one Iscsi obj in DOC at a time
            for old_iscsi in old_iscsis:
                LOGGER.debug("Removing old Iscsi object from DOC: %s",
                    old_iscsi)
                old_iscsi.delete()

            doc.volatile.insert_children(iscsi)

            # If other TargetDiscoveries (eg local disk) have already
            # completed, then run TD(iSCSI) now, otherwise queue it to
            # run later
            if is_discovery_complete():
                LOGGER.debug("Starting TargetDiscovery(iSCSI) directly")
                start_td_iscsi()
            else:
                LOGGER.debug("Queueing TargetDiscovery(iSCSI) to run later")
                queue_td_iscsi()

        # Every time we progress from this screen, set a flag to tell
        # the Disk Screen that it must re-process the TD results
        set_td_results_state(False)

    #--------------------------------------------------------------------------
    # Signal handler methods

    def iscsi_disks_toggled(self, widget, user_data=None):
        ''' Signal handler for "toggled" event in
            self._discovery_iscsi_check widget.
        '''
        if widget.get_active():
            self._discovery_iscsi_detail_vbox.show()
        else:
            self._discovery_iscsi_detail_vbox.hide()

    def dhcp_autodiscovery_toggled(self, widget, user_data=None):
        ''' Signal handler for "toggled" event in
            self._discovery_dhcp_radio widget.
        '''
        if widget.get_active():
            if self._dhcp_ip is not None:
                try:
                    segments = IPAddress.convert_address(self._dhcp_ip)
                except ValueError as error:
                    title = self.INVALID_IP_MSG
                    msg = self._dhcp_ip + ' : ' + str(error)
                    LOGGER.error(title)
                    LOGGER.error(msg)
                    modal_dialog(title, msg)
                else:
                    self._discovery_target_ip_1_entry.set_text(
                        str(segments[0]))
                    self._discovery_target_ip_2_entry.set_text(
                        str(segments[1]))
                    self._discovery_target_ip_3_entry.set_text(
                        str(segments[2]))
                    self._discovery_target_ip_4_entry.set_text(
                        str(segments[3]))

            if self._dhcp_port is not None:
                self._discovery_port_entry.set_text(str(self._dhcp_port))
            if self._dhcp_lun is not None:
                self._discovery_lun_entry.set_text(str(self._dhcp_lun))
            if self._dhcp_target is not None:
                self._discovery_target_name_entry.set_text(
                    str(self._dhcp_target))

            # Gray out the criteria fields
            self._discovery_criteria_detail_table.set_sensitive(False)

    def dhcp_criteria_toggled(self, widget, user_data=None):
        ''' Signal handler for "toggled" event in
            self._discovery_criteria_radio widget.
        '''
        if widget.get_active():
            # Un-gray the criteria fields (but leave the values as they are)
            self._discovery_criteria_detail_table.set_sensitive(True)

    def chap_toggled(self, widget, user_data=None):
        ''' Signal handler for "toggled" event in
            self._discovery_chap_check widget.
        '''
        if widget.get_active():
            self._discovery_chap_detail_table.set_sensitive(True)
        else:
            self._discovery_chap_detail_table.set_sensitive(False)

    def numeric_ip_field_insert(self, widget, new_text, new_text_len, pos):
        ''' Signal handler for "insert-text" event in the 4 Target IP
            fields.
        '''
        # Auto-advance to next field if DOT ('.') pressed
        if new_text == '.':
            gobject.GObject.stop_emission(widget, "insert-text")
            widget.get_toplevel().child_focus(gtk.DIR_TAB_FORWARD)
            return

        self._numeric_field_insert(widget, new_text, auto_advance=True)

    def numeric_port_field_insert(self, widget, new_text, new_text_len, pos):
        ''' Signal handler for "insert-text" event in the Port field.
        '''
        self._numeric_field_insert(widget, new_text, max_len=5)

    def hex_lun_field_insert(self, widget, new_text, new_text_len, pos):
        ''' Signal handler for "insert-text" event in the LUN field.
        '''
        self._numeric_field_insert(widget, new_text, max_len=4, allow_hex=True)

    #--------------------------------------------------------------------------
    # Private methods

    def _first_time_init(self):
        '''
            Screen initiatization tasks that are only to be performed on the
            first occasion this screen is brought up.
        '''
        # Check if DHCP Autodiscovery is available.  If it is, we will
        # pre-populate fields using the autodiscovery rootpath details.
        dhcp_params = Iscsi.get_dhcp()
        if dhcp_params is not None:
            self._dhcp_ip = dhcp_params[0]
            self._dhcp_port = dhcp_params[1]
            self._dhcp_lun = dhcp_params[2]
            self._dhcp_target = dhcp_params[3]

        # Set various form fields to their initial state of
        # grayed out/active, checked/unchecked, hidden/visible, etc
        self._discovery_local_check.set_active(True)
        if self._dhcp_ip is None:
            self._discovery_dhcp_radio.set_sensitive(False)
        else:
            self._discovery_dhcp_unavail_label.hide()
        self._discovery_criteria_radio.set_active(True)
        self._discovery_chap_detail_table.set_sensitive(False)
        self._discovery_iscsi_detail_vbox.hide()

        # Pre-populate the iSCSI Port field
        self._discovery_port_entry.set_text(Iscsi.ISCSI_DEFAULT_PORT)

        # Pre-populate initiator name with the for this host
        LOGGER.debug("Getting iSCSI Initiator Node Name for this system")
        cmd = [ISCSIADM, "list", "initiator-node"]
        try:
            popen = run(cmd)
        except CalledProcessError as error:
            title = self.NO_INITIATOR_NODE_MSG
            msg = cmd + " failed : " + str(error)
            LOGGER.error(title)
            LOGGER.error(msg)
            modal_dialog(title, msg)
        else:
            for line in popen.stdout.splitlines():
                if line.startswith("Initiator node name:"):
                    initiator_name = line.split(": ")[1]
                    break
            if initiator_name is not None:
                self._discovery_initiator_name_entry.set_text(initiator_name)
                LOGGER.debug("iSCSI Initiator Name is: ", initiator_name)
            else:
                title = self.NO_INITIATOR_NODE_MSG
                msg = popen.stdout.splitlines()
                LOGGER.error(title)
                LOGGER.error(msg)
                modal_dialog(title, msg)

        # initiator-name is not changeable for iscsi booting, so disable
        # the field in this case
        if is_iscsiboot():
            LOGGER.debug("iSCSI booting - disabling initiator node field")
            self._discovery_initiator_name_label.set_sensitive(False)
            self._discovery_initiator_name_entry.set_sensitive(False)
        else:
            self._discovery_iscsi_boot_label.hide()

    def _numeric_field_insert(self, widget, new_text, max_len=3,
                              auto_advance=False, allow_hex=False):
        ''' Convenience method called by IP, Port and LUN field sig handlers
        '''
        # Ensure the inserted text consists only of digits (or hex chars)
        for char in new_text:
            if allow_hex:
                if not char in string.hexdigits:
                    gobject.GObject.stop_emission(widget, "insert-text")
                    return
            else:
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

        if auto_advance:
            # Auto-advance to next field if updated text length is max_len
            if len(updated_text) == max_len:
                widget.get_toplevel().child_focus(gtk.DIR_TAB_FORWARD)
                return

        # Ensure the newly inserted text does not make the updated text
        # longer than max_len (eg if user pasted several chars in)
        if len(updated_text) > max_len:
            gobject.GObject.stop_emission(widget, "insert-text")


class SetupIscsiThread(threading.Thread):
    '''
        Thread class for running Iscsi.setup_iscsi()
    '''

    def __init__(self, iscsi):
        ''' Initializer method - called from constructor.

            Params:
            - iscsi, an Iscsi object containing user-entered criteria.

            Returns: Nothing
        '''
        threading.Thread.__init__(self)
        self.iscsi = iscsi
        self.error = None
        self.start()    # invokes run()

    def run(self):
        ''' Override run method from parent class.

            Calls Iscsi.setup_iscsi().
            Sets self.error if it fails.
        '''
        # attempt to connect to the LUN
        try:
            self.iscsi.setup_iscsi()
        except (CalledProcessError, RuntimeError) as error:
            # remove the iSCSI configuration since it's invalid
            try:
                self.iscsi.teardown()
            except CalledProcessError:
                pass
            self.error = error

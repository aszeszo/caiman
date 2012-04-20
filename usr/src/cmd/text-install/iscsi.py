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

#
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#

""" Screen and functionality to display iSCSI options to the user.
"""

import curses
import logging
import re
import string

from solaris_install import CalledProcessError, run
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile.ip_address import IPAddress
from solaris_install.target.libima.ima import is_iscsiboot
from solaris_install.target.physical import Iscsi
from solaris_install.text_install import _, ISCSI_LABEL, TUI_HELP
from terminalui.base_screen import BaseScreen, SkipException, UIMessage
from terminalui.edit_field import EditField, PasswordField
from terminalui.i18n import textwidth
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea

ISCSIADM = "/usr/sbin/iscsiadm"
LOGGER = None

# IQN strings must start with the format:  iqn.YYYY-MM.TLD.domain
IQN_RE = re.compile("iqn\.\d{4}\-\d{2}\.\w+\.\w+", re.I)


class IscsiScreen(BaseScreen):
    """ Allow the user to specify parameters for iSCSI LUNs
    """

    HEADER_TEXT = _("iSCSI Discovery")
    INTRO = _("The installer needs additional information for iSCSI LUN "
              "discovery")
    FOUND_DHCP_LABEL = _("DHCP has iSCSI parameters defined for this host")
    TARGET_IP_LABEL = _("Target IP:")
    TARGET_PORT_LABEL = _("Port:")
    TARGET_LUN_LABEL = _("Target LUN:")
    TARGET_NAME_LABEL = _("Target Name:")
    INITIATOR_NAME_LABEL = _("Initiator Name:")
    USE_CHAP_LABEL = _("Use CHAP:")
    CHAP_NAME_LABEL = _("CHAP Name:")
    CHAP_PASSWORD_LABEL = _("CHAP Password:")
    REQUIRED_FIELD_LABEL = _("Required Field")
    USE_CHAP_LABEL = _("If using CHAP for authentication")
    MAPPING_LUN_LABEL = _("Mapping iSCSI LUN...")
    MAPPING_TARGET_LABEL = _("Mapping iSCSI Target...")
    ISCSI_BOOT_LABEL = _("iSCSI boot enabled - Initiator Name set in BIOS")

    # error strings
    MISSING_TARGET_IP = _("Target IP address not provided")
    INVALID_TARGET_IP = _("Invalid Target IP address")
    INVALID_INITIATOR_IQN = _("Invalid Initiator IQN string")
    INVALID_TARGET_IQN = _("Invalid Target IQN string")
    CHAP_USERNAME_MISSING = _("CHAP username not specified")
    CHAP_PASSWORD_MISSING = _("CHAP password not specified")
    CHAP_PASSWORD_TOO_SHORT = _("CHAP password must be between 12 and 16 "
                                "characters")
    UNABLE_TO_MAP = _("Unable to map iSCSI LUN: ")

    HELP_DATA = (TUI_HELP + "/%s/iscsi.txt", _("iSCSI"))

    MAX_IP_LEN = 15
    MAX_LUN_LEN = 4
    MAX_PORT_LEN = 5
    MAX_NAME_LEN = 223
    CHAP_LEN = 16
    ITEM_OFFSET = 2
    DEAD_ZONE = 3
    REQUIRED_MARK = EditField.ASTERISK_CHAR

    def __init__(self, main_win):
        """ screen object containing iSCSI criteria objects
        """

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)
        super(IscsiScreen, self).__init__(main_win)

        self.target_ip = None
        self.target_port = None
        self.target_lun = None
        self.target_name = None
        self._initiator_name = None
        self.chap_name = None
        self.chap_password = None

        self.full_win_width = self.win_size_x - IscsiScreen.DEAD_ZONE
        self.half_win_width = (self.win_size_x - IscsiScreen.DEAD_ZONE) / 2

        self.default_edit = WindowArea(y_loc=0, lines=1,
                                       columns=IscsiScreen.CHAP_LEN)
        self.right_edit = WindowArea(y_loc=0, lines=1,
                                     columns=IscsiScreen.MAX_PORT_LEN)
        self.name_edit = WindowArea(y_loc=0, lines=1,
            scrollable_columns=IscsiScreen.MAX_NAME_LEN + 1)
        self.chap_edit = WindowArea(y_loc=0, lines=1,
                                    columns=IscsiScreen.CHAP_LEN)
        self.target_ip_list = None
        self.target_ip_edit = None
        self.target_port_list = None
        self.target_port_edit = None
        self.target_lun_list = None
        self.target_lun_edit = None
        self.target_name_edit = None
        self.initiator_name_edit = None
        self.chap_name_edit = None
        self.chap_password_edit = None

        # key map dictionary for Target entries
        self.add_keys = {curses.KEY_LEFT: self.on_arrow_key,
                         curses.KEY_RIGHT: self.on_arrow_key,
                         curses.KEY_DOWN: self.on_arrow_key,
                         curses.KEY_UP: self.on_arrow_key}

        self.iscsi_obj = None
        self.is_iscsiboot = is_iscsiboot()

    def on_arrow_key(self, input_key):
        """ override the default behavior of the arrow keys for specific
        EditFields.
        """

        # get the active object
        active = self.center_win.get_active_object()

        # only allow the right arrow to move from IP to Port
        if input_key == curses.KEY_RIGHT and active is self.target_ip_list:
            self.center_win.activate_object(self.target_port_list)
            return None

        # only allow the left arrow to move from Port to IP
        elif input_key == curses.KEY_LEFT and active is self.target_port_list:
            self.center_win.activate_object(self.target_ip_list)
            return None

        # override the default behavior for the up and down arrows to skip the
        # Port field if moving from IP to LUN
        elif input_key == curses.KEY_DOWN and active is self.target_ip_list:
            self.center_win.activate_object(self.target_lun_list)
            return None
        elif input_key == curses.KEY_UP and active is self.target_lun_list:
            self.center_win.activate_object(self.target_ip_list)
            return None

        return input_key

    def check_dhcp(self):
        """ query the DHCP server for the Rootpath string.  If present, update
        the proper attributes.
        """

        dhcp_params = Iscsi.get_dhcp()
        if dhcp_params is not None:
            self.target_ip,
            self.target_port,
            self.target_lun,
            self.target_name = dhcp_params
            return True
        return False

    @property
    def initiator_name(self):
        """ property to return the initiator name
        """

        if self._initiator_name is None:
            cmd = [ISCSIADM, "list", "initiator-node"]
            p = run(cmd)
            for line in p.stdout.splitlines():
                if line.startswith("Initiator node name:"):
                    self._initiator_name = line.split(": ")[1]
        return self._initiator_name

    @initiator_name.setter
    def initiator_name(self, name):
        """ property setter for _initiator_name
        """

        self._initiator_name = name

    def _show(self):
        """ create the screen to collect user input
        """

        # look in the DOC for an Iscsi object
        eng = InstallEngine.get_instance()
        iscsi_obj = eng.doc.volatile.get_children(name=ISCSI_LABEL,
                                                  class_type=Iscsi)

        # If there's no iscsi object in the DOC, skip this screen
        if not iscsi_obj:
            raise SkipException
        else:
            self.iscsi_obj = iscsi_obj[0]
            LOGGER.debug("show Iscsi object:  %s" % str(self.iscsi_obj))

        y_loc = 1
        self.center_win.add_paragraph(IscsiScreen.INTRO, start_y=y_loc)

        # look to see if DHCP is providing information
        if self.check_dhcp():
            y_loc += 2
            self.center_win.add_paragraph(IscsiScreen.FOUND_DHCP_LABEL,
                                          start_y=y_loc)

        # Target IP
        y_loc += 2

        # Mark this field required
        self.center_win.window.addch(y_loc, 2, IscsiScreen.REQUIRED_MARK,
            self.center_win.color_theme.inactive)

        edit_start = textwidth(IscsiScreen.TARGET_IP_LABEL) + \
                     IscsiScreen.ITEM_OFFSET
        ip_area = WindowArea(y_loc=y_loc, x_loc=1, lines=1,
            columns=edit_start + IscsiScreen.MAX_IP_LEN + 1)

        self.target_ip_list = ListItem(ip_area,
                                       window=self.center_win,
                                       text=IscsiScreen.TARGET_IP_LABEL)
        self.target_ip_list.key_dict.update(self.add_keys)

        self.default_edit.x_loc = edit_start
        self.default_edit.columns = IscsiScreen.MAX_IP_LEN + 1
        self.target_ip_edit = EditField(self.default_edit,
                                        window=self.target_ip_list,
                                        validate=incremental_validate_ip,
                                        error_win=self.main_win.error_line)
        self.target_ip_edit.key_dict.update(self.add_keys)
        if self.target_ip is not None:
            self.target_ip_edit.set_text(self.target_ip)

        # Target Port
        edit_start = ip_area.x_loc + \
                     textwidth(IscsiScreen.TARGET_PORT_LABEL) + \
                     IscsiScreen.ITEM_OFFSET
        port_area = WindowArea(y_loc=y_loc,
            x_loc=self.half_win_width + IscsiScreen.DEAD_ZONE,
            lines=1, columns=edit_start + IscsiScreen.MAX_PORT_LEN + 1)

        self.target_port_list = ListItem(port_area,
                                         window=self.center_win,
                                         text=IscsiScreen.TARGET_PORT_LABEL)
        self.target_port_list.key_dict.update(self.add_keys)

        self.right_edit.x_loc = edit_start
        self.right_edit.columns = IscsiScreen.MAX_PORT_LEN + 1
        self.target_port_edit = EditField(self.right_edit,
                                          window=self.target_port_list,
                                          validate=incremental_validate_digits,
                                          error_win=self.main_win.error_line,
                                          text=Iscsi.ISCSI_DEFAULT_PORT)
        self.target_port_edit.key_dict.update(self.add_keys)
        if self.target_port is not None:
            self.target_port_edit.set_text(self.target_port)

        # Target LUN
        y_loc += 1

        edit_start = textwidth(IscsiScreen.TARGET_LUN_LABEL) + \
                     IscsiScreen.ITEM_OFFSET
        lun_area = WindowArea(y_loc=y_loc, x_loc=1, lines=1,
            columns=edit_start + IscsiScreen.MAX_LUN_LEN + 1)

        self.target_lun_list = ListItem(lun_area,
                                        window=self.center_win,
                                        text=IscsiScreen.TARGET_LUN_LABEL)
        self.target_lun_list.key_dict.update(self.add_keys)

        self.default_edit.x_loc = edit_start
        self.default_edit.columns = IscsiScreen.MAX_LUN_LEN + 1
        self.target_lun_edit = EditField(self.default_edit,
                                         window=self.target_lun_list,
                                         validate=incremental_validate_hex,
                                         error_win=self.main_win.error_line)
        self.target_lun_edit.key_dict.update(self.add_keys)
        if self.target_lun is not None:
            self.target_lun_edit.set_text(self.target_lun)

        # Target Name
        y_loc += 2
        name_area = WindowArea(y_loc=y_loc, x_loc=1, lines=1,
            columns=self.full_win_width)

        name_area.y_loc = y_loc
        target_name_list = ListItem(name_area, window=self.center_win,
                                    text=IscsiScreen.TARGET_NAME_LABEL)

        self.name_edit.x_loc = textwidth(IscsiScreen.TARGET_NAME_LABEL) + \
                                         IscsiScreen.ITEM_OFFSET
        self.name_edit.columns = self.full_win_width - \
                                 textwidth(IscsiScreen.TARGET_NAME_LABEL) - \
                                 IscsiScreen.ITEM_OFFSET
        self.target_name_edit = EditField(self.name_edit,
                                          window=target_name_list)
        if self.target_name is not None:
            self.target_name_edit.set_text(self.target_name)

        # Horizontal line
        y_loc += 1
        self.center_win.window.hline(y_loc, 3, curses.ACS_HLINE,
                                     self.full_win_width)

        # Initiator Name
        y_loc += 1

        if self.is_iscsiboot:
            # the system BIOS is configured for iSCSI boot.  This means the
            # user will be unable to change the initiator-name.  Display the
            # name, but don't allow it to be changed.
            text = "%s  %s" % \
                (IscsiScreen.INITIATOR_NAME_LABEL, self.initiator_name)
            self.center_win.add_text(text, start_y=y_loc, start_x=1)
            y_loc += 1
            self.center_win.add_text(IscsiScreen.ISCSI_BOOT_LABEL,
                                     start_y=y_loc, start_x=1)
        else:
            # display the edit field as normal
            name_area.y_loc = y_loc
            initiator_name_list = ListItem(name_area, window=self.center_win,
                text=IscsiScreen.INITIATOR_NAME_LABEL)

            self.name_edit.x_loc = \
                textwidth(IscsiScreen.INITIATOR_NAME_LABEL) + \
                IscsiScreen.ITEM_OFFSET
            self.name_edit.columns = self.full_win_width - \
                textwidth(IscsiScreen.INITIATOR_NAME_LABEL) - \
                IscsiScreen.ITEM_OFFSET
            self.initiator_name_edit = EditField(self.name_edit,
                                                 window=initiator_name_list,
                                                 text=self.initiator_name)

        y_loc += 2
        self.center_win.add_text(IscsiScreen.USE_CHAP_LABEL, y_loc, 1)

        # CHAP username
        y_loc += 1
        edit_start = textwidth(IscsiScreen.CHAP_NAME_LABEL) + \
                               IscsiScreen.ITEM_OFFSET
        chapname_area = WindowArea(y_loc=y_loc, x_loc=15, lines=1,
            columns=edit_start + IscsiScreen.CHAP_LEN)

        chap_name_list = ListItem(chapname_area, window=self.center_win,
                                  text=IscsiScreen.CHAP_NAME_LABEL)

        self.chap_edit.x_loc = edit_start
        self.chap_edit.columns = IscsiScreen.CHAP_LEN + 1
        self.chap_edit.scrollable_columns = IscsiScreen.MAX_NAME_LEN + 1
        self.chap_name_edit = EditField(self.chap_edit, window=chap_name_list)
        if self.chap_name is not None:
            self.chap_name_edit.set_text(self.chap_name)

        # CHAP password
        y_loc += 1
        edit_start = textwidth(IscsiScreen.CHAP_PASSWORD_LABEL) + \
                     IscsiScreen.ITEM_OFFSET
        chapname_area.y_loc = y_loc
        chap_password_list = ListItem(chapname_area, window=self.center_win,
                                      text=IscsiScreen.CHAP_PASSWORD_LABEL)

        self.chap_edit.x_loc = textwidth(IscsiScreen.CHAP_PASSWORD_LABEL) + \
                               IscsiScreen.ITEM_OFFSET
        self.chap_edit.scrollable_columns = None
        self.chap_password_edit = PasswordField(self.chap_edit,
                                                window=chap_password_list)
        if self.chap_password is not None:
            self.chap_password_edit.set_text(self.chap_password)

        # Legend
        y_loc += 2
        self.center_win.window.addch(y_loc, 1, IscsiScreen.REQUIRED_MARK,
            self.center_win.color_theme.inactive)
        self.center_win.add_text(IscsiScreen.REQUIRED_FIELD_LABEL, y_loc, 1)

        self.main_win.do_update()
        self.center_win.activate_object()

    def on_change_screen(self):
        """ save the user's choices in case they return to this screen
        """

        self.target_ip = self.target_ip_edit.get_text()
        self.target_port = self.target_port_edit.get_text()
        self.target_lun = self.target_lun_edit.get_text()
        self.target_name = self.target_name_edit.get_text()
        if not self.is_iscsiboot:
            self.initiator_name = self.initiator_name_edit.get_text()
        self.chap_name = self.chap_name_edit.get_text()
        self.chap_password = self.chap_password_edit.get_text()

    def validate(self):
        """ validate the iSCSI attributes before continuing to disk selection.
        """

        target_ip = self.target_ip_edit.get_text()
        target_lun = self.target_lun_edit.get_text()
        target_port = self.target_port_edit.get_text()
        target_name = self.target_name_edit.get_text()
        if not self.is_iscsiboot:
            initiator_name = self.initiator_name_edit.get_text()
        chap_name = self.chap_name_edit.get_text()
        chap_password = self.chap_password_edit.get_text()

        # validate the target IP
        if not target_ip:
            raise UIMessage(IscsiScreen.MISSING_TARGET_IP)
        else:
            try:
                IPAddress.convert_address(target_ip)
            except ValueError as error:
                raise UIMessage("%s: %s" % \
                    (IscsiScreen.INVALID_TARGET_IP, str(error)))

        # validate the IQN strings (by default re.match only matches at the
        # beginning of a string)
        if not self.is_iscsiboot and initiator_name:
            if IQN_RE.match(initiator_name) is None:
                raise UIMessage(IscsiScreen.INVALID_INITIATOR_IQN)

        if target_name:
            if IQN_RE.match(target_name) is None:
                raise UIMessage(IscsiScreen.INVALID_TARGET_IQN)

        # validate that both CHAP username and password were specified (or not
        # at all)
        if chap_name and not chap_password:
            raise UIMessage(IscsiScreen.CHAP_PASSWORD_MISSING)
        if chap_password and not chap_name:
            raise UIMessage(IscsiScreen.CHAP_USERNAME_MISSING)

        # validate the CHAP password
        if chap_password:
            if not 12 <= len(chap_password) <= 16:
                raise UIMessage(IscsiScreen.CHAP_PASSWORD_TOO_SHORT)

        # Update the Iscsi DOC object
        self.iscsi_obj.target_ip = target_ip

        # force target_lun back to None if the user comes back and removes the
        # LUN entry from the screen
        if target_lun:
            self.iscsi_obj.target_lun = target_lun
        else:
            self.iscsi_obj.target_lun = None

        if target_name:
            self.iscsi_obj.target_name = target_name
        if target_port:
            self.iscsi_obj.target_port = target_port

        if not self.is_iscsiboot and initiator_name:
            self.iscsi_obj.initiator_name = initiator_name

        if chap_name:
            self.iscsi_obj.chap_name = chap_name
        if chap_password:
            self.iscsi_obj.chap_password = chap_password

        # attempt to connect to the LUN
        if target_lun:
            self.main_win.error_line.display_err(IscsiScreen.MAPPING_LUN_LABEL)
        else:
            self.main_win.error_line.display_err(
                IscsiScreen.MAPPING_TARGET_LABEL)

        try:
            self.iscsi_obj.setup_iscsi()
            LOGGER.debug("Iscsi object:  %s" % str(self.iscsi_obj))
        except (CalledProcessError, RuntimeError) as err:
            # remove the iSCSI configuration since it's invalid
            try:
                self.iscsi_obj.teardown()
            except CalledProcessError:
                # ignore any errors
                pass
            raise UIMessage("%s %s" % (IscsiScreen.UNABLE_TO_MAP, str(err)))


def incremental_validate_ip(edit_field):
    """ Incrementally validate the IP Address as the user enters it
    """

    ip_address = edit_field.get_text()
    if not ip_address:
        return True

    try:
        IPAddress.incremental_check(ip_address)
    except ValueError as err:
        raise UIMessage(str(err))

    return True


def incremental_validate_digits(edit_field):
    """ Incrementally validate fields that only accept numeric values
    """

    text = edit_field.get_text()
    if text and not text.isdigit():
        raise UIMessage("Only digits allowed!")

    return True


def incremental_validate_hex(edit_field):
    """ Incrementally validate fields that only accept hexadecimal values
    """

    text = edit_field.get_text()
    if text:
        for char in text:
            if not char in string.hexdigits:
                raise UIMessage("Only hexadecimal digits allowed!")

    return True

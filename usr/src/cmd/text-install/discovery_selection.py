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

"""
Contains the discovery selection screen for the user to choose between local
disk discovery and iSCSI disk discovery.
"""

import logging

from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.physical import Iscsi
from solaris_install.text_install import _, ISCSI_LABEL, TUI_HELP
from terminalui.base_screen import BaseScreen
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea


LOGGER = None


class DiscoverySelection(BaseScreen):
    """ Allow the user to select which method of target discovery to use.
    NOTE:  Local disk discovery will always happen, regardless of this choice
    """

    HEADER_TEXT = _("Discovery Selection")
    PARAGRAPH = _("Select discovery method for disks")
    LOCAL_TEXT = _("Local Disks")
    LOCAL_DETAIL = _("Discover local disks")
    ISCSI_TEXT = _("iSCSI")
    ISCSI_DETAIL = _("Discover iSCSI LUNs")

    ITEM_OFFSET = 2
    ITEM_MAX_WIDTH = 21
    ITEM_DESC_OFFSET = ITEM_MAX_WIDTH + ITEM_OFFSET + 1

    HELP_DATA = (TUI_HELP + "/%s/discovery_selection.txt",
                 _("Discovery Selection"))

    def __init__(self, main_win):
        """ screen object containing the discovery selection choices
        """

        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(DiscoverySelection, self).__init__(main_win)

        self.local = None
        self.iscsi = None
        self.current_selection = 0

    def _show(self):
        """ create the screen for the user to select a discovery method
        """

        y_loc = 1
        y_loc += self.center_win.add_paragraph(DiscoverySelection.PARAGRAPH,
                                               y_loc)

        y_loc += 1
        item_area = WindowArea(1, DiscoverySelection.ITEM_MAX_WIDTH, y_loc, 1)
        self.local = ListItem(item_area, window=self.center_win,
                              text=DiscoverySelection.LOCAL_TEXT)
        self.local.item_key = "local"
        self.center_win.add_text(DiscoverySelection.LOCAL_DETAIL, y_loc,
                                 DiscoverySelection.ITEM_DESC_OFFSET,
                                 self.win_size_x - 3)

        y_loc += 2
        item_area.y_loc = y_loc
        self.iscsi = ListItem(item_area, window=self.center_win,
                              text=DiscoverySelection.ISCSI_TEXT)
        self.iscsi.item_key = "iscsi"
        self.center_win.add_text(DiscoverySelection.ISCSI_DETAIL, y_loc,
                                 DiscoverySelection.ITEM_DESC_OFFSET,
                                 self.win_size_x - 3)

        self.main_win.do_update()
        self.center_win.activate_object(self.current_selection)

    def on_change_screen(self):
        """ save the user's choice in case they return to this screen
        """

        choice = self.center_win.get_active_object().item_key
        LOGGER.debug("discovery selection:  %s", choice)
        eng = InstallEngine.get_instance()

        if choice == "iscsi":
            # remove any existing Iscsi DOC objects so there are no duplicates
            prev_iscsi = eng.doc.volatile.get_first_child(name=ISCSI_LABEL,
                                                          class_type=Iscsi)
            if prev_iscsi:
                prev_iscsi.delete()

            # create an empty Iscsi DOC object
            iscsi_doc_obj = Iscsi(ISCSI_LABEL)

            # add the object to the DOC
            eng.doc.volatile.insert_children(iscsi_doc_obj)
        else:
            # look for an existing iSCSI object in the DOC.  If there is one,
            # remove it
            iscsi_doc_obj = eng.doc.volatile.get_first_child(class_type=Iscsi,
                name=ISCSI_LABEL)

            if iscsi_doc_obj is not None:
                iscsi_doc_obj.delete()

        self.current_selection = self.center_win.active_object

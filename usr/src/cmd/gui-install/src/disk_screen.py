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
Disk Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import locale
import logging
import os

import glib
import gobject
import gtk

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.fdisk_panel import FdiskPanel
from solaris_install.gui_install.gpt_panel import GPTPanel
from solaris_install.gui_install.gui_install_common import \
    empty_container, get_td_results_state, is_discovery_complete, \
    modal_dialog, set_td_results_state, IMAGE_DIR, COLOR_WHITE, \
    DEFAULT_LOG_LOCATION, GLADE_ERROR_MSG, ISCSI_LABEL, N_
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.controller import TargetController, \
    BadDiskError, BadDiskBlockSizeError, SubSizeDiskError, DEFAULT_ZPOOL_NAME
from solaris_install.target.logical import Zpool, Zvol, Filesystem
from solaris_install.target.physical import Disk, Iscsi, Slice
from solaris_install.target.shadow.physical import ShadowPhysical
from solaris_install.target.size import Size

ROOT_POOL = DEFAULT_ZPOOL_NAME
EXPORT_FS_NAME = 'export'
EXPORT_FS_MOUNTPOINT = '/export'
EXPORT_HOME_FS_NAME = 'export/home'

LOGGER = None


class DiskScreen(BaseScreen):
    '''
        The Disk screen.

        There are two distinct versions of this screen:
        - if the user enters this screen before TD has completed
          execution, they will see the "Finding Disks..." version,
          which just shows a spinning icon, and has the Next
          button disabled
        - once TD has completed, the "Disk Selection" version can be
          shown, which has a row of buttons, one for each discovered
          disk, along the top of the screen, and a complex set of
          widgets which allows the user to partition the disk, at
          the bottom.  The Next button is enabled.
    '''
    BUSY_TEXT = N_("Finding Disks")
    BUSY_MARKUP = '<span font_desc="Bold">%s</span>'

    #--------------------------------------------------------------------------
    # API methods

    def __init__(self, builder):
        ''' Initializer method - called from constructor.

            Params:
            - builder, a gtk.Builder object, used to retrieve Gtk+
              widgets from Glade XML files.

            Returns: Nothing
        '''
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(DiskScreen, self).__init__(builder)
        self.name = "Disk Screen"

        self._monitor_timeout_id = None
        self._td_disks = list()
        self._selected_disk = None
        self._target_controller = None
        self._wholediskmode = False
        self._disk_buttons = list()

        self._toplevel = None

        # Top-level widget for the "Finding Disks" version of screen
        self._finding_disks_vbox = None
        # Top-level widget for the "Disk Selection" version of screen
        self._disk_buttons_hbuttonbox = None

        self._disksviewport = self.builder.get_object("disksviewport")
        self._diskselectionhscrollbar = self.builder.get_object(
            "diskselectionhscrollbar")
        self._diskerrorimage = self.builder.get_object("diskerrorimage")
        self._diskwarningimage = self.builder.get_object("diskwarningimage")
        self._diskstatuslabel = self.builder.get_object("diskstatuslabel")
        self._partitioningvbox = self.builder.get_object("partitioningvbox")
        self._diskradioalignment = self.builder.get_object(
            "diskradioalignment")
        self._diskwarninghbox = self.builder.get_object("diskwarninghbox")
        self._wholediskradio = self.builder.get_object("wholediskradio")
        self._partitiondiskradio = self.builder.get_object(
            "partitiondiskradio")
        self._custompartitionbox = self.builder.get_object(
            "custompartitionbox")

        if None in [self._disksviewport, self._diskselectionhscrollbar,
            self._diskerrorimage, self._diskwarningimage,
            self._diskstatuslabel, self._partitioningvbox,
            self._diskradioalignment, self._diskwarninghbox,
            self._wholediskradio, self._partitiondiskradio,
            self._custompartitionbox]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        # We use this indirection to facilitate different partitioning control
        # backends for MBR/fdisk and GPT partition formats
        self._fdisk_panel = FdiskPanel(self.builder)
        self._gpt_panel = GPTPanel(self.builder)
        self._disk_panel = self._gpt_panel
        self._custompartitionbox.pack_start(self._disk_panel.toplevel,
            expand=True, fill=True, padding=0)
        self._icon_theme = gtk.icon_theme_get_default()
        self._busy_label = None

    def enter(self):
        ''' Show the Disk Screen.

            This method is called when the user navigates to this screen
            via the Back and Next buttons.
        '''

        self._toplevel = self.set_main_window_content("diskselectiontoplevel")

        # Screen-specific configuration
        self.activate_stage_label("diskselectionstagelabel")

        # Initially, hide the Partitioning VBox and Disk selection scrollbar
        self._partitioningvbox.hide()
        self._diskselectionhscrollbar.hide()

        if is_discovery_complete():
            self._show_screen_for_td_complete()
        else:
            self._show_screen_for_td_not_complete()
            # Only set one timeout monitor at a time, even if user enters the
            # screen multiple times before TD completes
            if self._monitor_timeout_id is None:
                self._monitor_timeout_id = \
                    glib.timeout_add(200, self._td_completion_monitor)

        return False

    def go_back(self):
        ''' Perform any checks required before allowing to user to
            go back to the previous screen.

            Does nothing.
        '''
        pass

    def validate(self):
        ''' Validate the user selections before proceeding.

            Perform a series of validations on the deleted
            disk and the selected partitions, if appropriate.

            If the Disk and/or Partitions are not suitable for the install,
            then display an error dialog and raise an exception.

            Raises: NotOkToProceedError
        '''

        LOGGER.info("Starting validation.")

        # First, tell the disk panel to tidy up the disk
        self._disk_panel.finalize()

        # Validation phases:
        # 1. Start off by validating the generic stuff such as a disk being
        #    selected, big enough etc.
        #
        # 2. Then get into the specifics by handing over validation control
        #    to the disk_panel object for fdisk/gpt specific checks.
        #
        # 3. Validate the logical elements.
        #
        # 4. Throw up misc. warnings (not errors) if space is tight

        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache
        desired_root = doc.get_descendants(name=Target.DESIRED,
            class_type=Target,
            max_depth=2,
            max_count=1,
            not_found_is_err=True)[0]
        # UI only allows 1 disk to be selected, so no need to
        # check for multiple selected disks
        selected_disk = desired_root.get_first_child(class_type=Disk)

        # ERROR #1 - No disk selected
        # (UI will prevent this happening, but this check remains
        # for completeness.)
        if selected_disk is None:
            LOGGER.error("No disk selected.")
            modal_dialog(_("No disk has been selected for "
                "Oracle Solaris installation."),
                _("Select a disk."))
            self._raise_error("No disk selected")

        # ERROR #2 - No suitable disk selected
        # (TargetController will prevent this happening, but this check remains
        # for completeness.)
        if selected_disk.disk_prop is None or \
            selected_disk.disk_prop.dev_size is None or \
            selected_disk.disk_prop.dev_size < \
            self._target_controller.minimum_target_size:

            LOGGER.error("Disk too small.")
            LOGGER.error("Minimum size is %s" % \
                self._target_controller.minimum_target_size)
            if selected_disk.disk_prop is not None and \
                selected_disk.disk_prop.dev_size is not None:

                LOGGER.error("Disk size is (%s)." % \
                    selected_disk.disk_prop.dev_size)
            else:
                LOGGER.error("No size info available.")

            modal_dialog(_("The selected disk is not suitable for "
                "Oracle Solaris installation."),
                _("Select another disk."))
            self._raise_error("Disk too small")

        # ERROR #2.5 - No suitable disk selected
        # (TargetController will prevent this happening, but this check remains
        # for completeness.)
        if not self._target_controller._is_block_size_compatible(
            selected_disk):

            LOGGER.error("Disk block size incompatible: %d",
                         selected_disk.geometry.blocksize)

            modal_dialog(_("The selected disk has a block size of %d bytes, "
                "which is incompatible for Oracle Solaris installation on "
                "this system."),
                _("Select another disk."))
            self._raise_error("Disk block size incompatible")

        # ERROR #3 - Tell disk_panel to do its bit if custom partitioning
        # selected. For whole disk we trust ZFS to get it right.
        if selected_disk.whole_disk:
            pool_size = selected_disk.disk_prop.dev_size
        else:
            try:
                solaris_partyslice = self._disk_panel.validate()
                pool_size = solaris_partyslice.size
            except NotOkToProceedError as nok:
                self._raise_error(str(nok))

        # Finish up with the logical section
        # Create swap and dump, as required

        (swap_type, swap_size, dump_type, dump_size) = \
            self._target_controller.calc_swap_dump_size(
                self._target_controller.minimum_target_size,
                pool_size,
                swap_included=True)

        desired_zpool = desired_root.get_descendants(name=ROOT_POOL,
                                                     class_type=Zpool,
                                                     not_found_is_err=True)[0]

        if swap_type == TargetController.SWAP_DUMP_ZVOL:
            desired_zpool.delete_children(name="swap", class_type=Zvol)

            swap_zvol = desired_zpool.add_zvol("swap",
                int(swap_size.get(units=Size.mb_units)), Size.mb_units,
                use="swap")

        if dump_type == TargetController.SWAP_DUMP_ZVOL:
            desired_zpool.delete_children(name="dump", class_type=Zvol)

            dump_zvol = desired_zpool.add_zvol("dump",
                int(dump_size.get(units=Size.mb_units)), Size.mb_units,
                use="dump", create_failure_ok=True)

        # Add export and export/home, if they do not already exist
        export_fs = desired_zpool.get_first_child(name=EXPORT_FS_NAME,
            class_type=Filesystem)

        if export_fs is None:
            desired_zpool.add_filesystem(EXPORT_FS_NAME,
                mountpoint=EXPORT_FS_MOUNTPOINT)

        export_home_fs = desired_zpool.get_first_child(
            name=EXPORT_HOME_FS_NAME, class_type=Filesystem)

        if export_home_fs is None:
            desired_zpool.add_filesystem(EXPORT_HOME_FS_NAME)

        # ERROR #4 - Target class final validation
        LOGGER.info("Performing Target.final_validation().")
        errsvc.clear_error_list()
        if not desired_root.final_validation():
            # Certain errors reported by final_validation don't concern us
            error_is_fatal = False
            all_errors = errsvc.get_all_errors()
            for err in all_errors:
                if isinstance(
                    err.error_data[liberrsvc.ES_DATA_EXCEPTION],
                    ShadowPhysical.SliceInUseError):

                    LOGGER.warn("ShadowPhysical.SliceInUseError - not fatal")
                    LOGGER.warn("Error: mod id %s, type %s",
                        err.get_mod_id(), str(err.get_error_type()))
                    LOGGER.warn("Error value: %s",
                        err.error_data[liberrsvc.ES_DATA_EXCEPTION].value)
                elif isinstance(
                    err.error_data[liberrsvc.ES_DATA_EXCEPTION],
                    ShadowPhysical.GPTPartitionInUseError):

                    LOGGER.warn("ShadowPhysical.GPTPartitionInUseError " \
                                "- not fatal")
                    LOGGER.warn("Error: mod id %s, type %s",
                        err.get_mod_id(), str(err.get_error_type()))
                    LOGGER.warn("Error value: %s",
                        err.error_data[liberrsvc.ES_DATA_EXCEPTION].value)
                else:
                    error_is_fatal = True
                    LOGGER.error("Fatal validation error:")
                    LOGGER.error("Error mod id %s, type: %s" % \
                        (err.get_mod_id(), str(err.get_error_type())))
                    LOGGER.error("Error class: %r" % \
                        err.error_data[liberrsvc.ES_DATA_EXCEPTION])
                    LOGGER.error("Error value: %s" % \
                        err.error_data[liberrsvc.ES_DATA_EXCEPTION].value)
                    LOGGER.error("Desired Targets in DOC:\n%s" % \
                        desired_root.get_xml_tree_str())

            if error_is_fatal:
                modal_dialog(_("Final validation failed."), "%s\n\n%s" % \
                    (_("See log file for details."), DEFAULT_LOG_LOCATION))
                self._raise_error("final_validation failed")
        LOGGER.info("final_validation passed.")

        # WARNING #1 - disk is smaller than recommended size (whole_disk only)
        if selected_disk.whole_disk:
            if selected_disk.disk_prop is None or \
                selected_disk.disk_prop.dev_size is None or \
                selected_disk.disk_prop.dev_size < \
                self._target_controller.recommended_target_size:

                LOGGER.info("Disk smaller than recommended")
                LOGGER.info("Recommended size is %s",
                    self._target_controller.recommended_target_size)
                if selected_disk.disk_prop is not None and \
                    selected_disk.disk_prop.dev_size is not None:
                    LOGGER.info("Disk size is (%s)",
                        selected_disk.disk_prop.dev_size)
                else:
                    LOGGER.info("No size info available")

                ok_to_proceed = modal_dialog(_("The selected disk is "
                    "smaller than the recommended minimum size."),
                    _("You may have difficulties upgrading the system "
                    "software and/or installing and running additional "
                    "applications."),
                    two_buttons=True)
                if not ok_to_proceed:
                    self._raise_error("Disk smaller than recommended")

        # WARNING #2 - Solaris partition is smaller than recommended size
        # Identify the correct Solaris Partition or GPTPartition object.
        # (not whole_disk only)
        else:
            if isinstance(solaris_partyslice, Slice):
                solaris_partition = solaris_partyslice.parent
            else:
                solaris_partition = solaris_partyslice

            if solaris_partition.size < \
                self._target_controller.recommended_target_size:

                LOGGER.info("Partition smaller than recommended")
                LOGGER.info("Recommended size is %s",
                    self._target_controller.recommended_target_size)
                LOGGER.info("Partition size is (%s)", solaris_partition.size)

                ok_to_proceed = modal_dialog(_("The selected partition is "
                    "smaller than the recommended minimum size."),
                    _("You may have difficulties upgrading the system "
                    "software and/or installing and running additional "
                    "applications."),
                    two_buttons=True)
                if not ok_to_proceed:
                    self._raise_error("Partition smaller than recommended")

        # Save the TargetController in the DOC (used to retrieve the
        # minimum_target_size and call setup_vfstab_for_swap())
        profile = doc.volatile.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        if profile is not None:
            profile.set_disk_data(self._target_controller)

        LOGGER.info("Validation succeeded. Desired Targets in DOC:\n%s",
            desired_root.get_xml_tree_str())

    #--------------------------------------------------------------------------
    # Signal handler methods

    def diskbutton_toggled(self, toggle_button, disk):
        ''' Signal handler for "toggled" signal in _diskselectionhscrollbar.
        '''

        if not toggle_button.get_active():
            # We're not interested when the button is being de-activated
            return

        if self._target_controller is not None:
            try:
                selected_disks = self._target_controller.select_disk(
                    disk, use_whole_disk=self._wholediskmode)
            except SubSizeDiskError as err:
                self._diskwarningimage.hide()
                self._diskerrorimage.show()
                markup = '<span font_desc="Bold">%s</span>' \
                    % _("This disk is too small")
                self._diskstatuslabel.set_markup(markup)
                logging.debug("Selected disk [%s] is too small for " \
                    "installation" % disk.ctd)
                # Prevent user from proceeding or customisation
                self.set_back_next(back_sensitive=True, next_sensitive=False)
                self._partitioningvbox.set_sensitive(False)
                # Hide the custom partitioning details
                self._disk_panel.hide()
                self._wholediskradio.set_active(True)
                return
            except BadDiskBlockSizeError as err:
                self._diskwarningimage.hide()
                self._diskerrorimage.show()
                markup = '<span font_desc="Bold">%s</span>' \
                    % _("This disk has an incompatible block size")
                self._diskstatuslabel.set_markup(markup)
                logging.debug("Selected disk [%s] blocksize is not " \
                    "compatible for installation" % disk.ctd)
                # Prevent user from proceeding or customisation
                self.set_back_next(back_sensitive=True, next_sensitive=False)
                self._partitioningvbox.set_sensitive(False)
                # Hide the custom partitioning details
                self._disk_panel.hide()
                self._wholediskradio.set_active(True)
                return
            except BadDiskError, err:
                LOGGER.error("ERROR: TargetController cannot " \
                    "select disk [%s]" % disk.ctd)
                modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                    (_("See log file for details."), DEFAULT_LOG_LOCATION))
                self.set_back_next(back_sensitive=True, next_sensitive=False)
                return

            self._select_disk_panel()
            LOGGER.info("Disk [%s] selected" % selected_disks[0])
            self._diskwarningimage.hide()
            self._diskerrorimage.hide()
            self._diskstatuslabel.set_markup('')
            self._partitioningvbox.set_sensitive(True)
            self._display_selected_disk_details()
            self.set_back_next(back_sensitive=True, next_sensitive=True)

    def installationdisk_wholediskradio_toggled(self, widget,
        user_data=None):
        ''' Signal handler for "toggled" event in _wholediskradio.
        '''

        if not widget.get_active():
            # We're not interested when the button is being de-activated
            return

        self._wholediskmode = True

        selected_disk = self._target_controller.desired_disks[0]
        # Re-select the disk, this time with use_whole_disk=True
        try:
            selected_disks = self._target_controller.select_disk(
                selected_disk,
                use_whole_disk=self._wholediskmode)
        except BadDiskError, err:
            LOGGER.error("ERROR: TargetController cannot " \
                "select disk [%s]" % selected_disk.ctd)
            modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))
            self.set_back_next(back_sensitive=True, next_sensitive=False)
            return

        self._select_disk_panel()
        LOGGER.info("Disk [%s] selected", selected_disk.ctd)

        self._display_selected_disk_details()

    def installationdisk_partitiondiskradio_toggled(self, widget,
        user_data=None):
        ''' Signal handler for "toggled" event in _partitiondiskradio.
        '''

        if not widget.get_active():
            # We're not interested when the button is being de-activated
            return

        self._wholediskmode = False

        selected_disk = self._target_controller.desired_disks[0]
        # Re-select the disk, this time with use_whole_disk=False
        try:
            selected_disks = self._target_controller.select_disk(
                selected_disk,
                use_whole_disk=self._wholediskmode)
        except BadDiskError, err:
            LOGGER.error("ERROR: TargetController cannot " \
                "select disk [%s]" % selected_disk.ctd)
            modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))
            self.set_back_next(back_sensitive=True, next_sensitive=False)
            return

        self._select_disk_panel()
        LOGGER.info("Disk [%s] selected" % selected_disk.ctd)

        self._display_selected_disk_details()

    def viewport_adjustment_changed(self, adjustment, scrollbar):
        ''' Signal handler for "changed" event in _diskselectionhscrollbar.
        '''

        lower = adjustment.get_lower()
        upper = adjustment.get_upper()
        pagesize = adjustment.get_page_size()

        if (upper - lower) <= pagesize:
            scrollbar.hide()
        else:
            scrollbar.show()

    #--------------------------------------------------------------------------
    # Private methods

    def _process_td_results(self):
        '''
            If TD completed successfully, the attributes
            self._td_disks and self._target_controller will be set.

            In any event self._td_complete will be set to True.
        '''

        self._td_disks = list()
        self._target_controller = None
        self._selected_disk = None

        # Fetch the Disk objects from "discovered targets" in DOC
        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache
        discovered_root = None
        try:
            discovered_root = doc.get_descendants(name=Target.DISCOVERED,
                class_type=Target, max_depth=2, max_count=1,
                not_found_is_err=True)[0]
        except ObjectNotFoundError, err:
            LOGGER.error("TD didn't create 'discovered' Target: [%s]" % \
                str(err))
            return
        LOGGER.info("TD XML:\n%s" % discovered_root.get_xml_tree_str())
        try:
            self._td_disks = discovered_root.get_children(class_type=Disk,
                not_found_is_err=True)
        except ObjectNotFoundError, err:
            LOGGER.error("No Disks in 'discovered' Target: [%s]" % \
                str(err))
            LOGGER.error("TD XML:\n%s" % \
                discovered_root.get_xml_tree_str())
            return

        # Only retain those disks that match the user's selected disk types
        profile = doc.volatile.get_first_child(name="GUI Install",
                                               class_type=InstallProfile)
        if profile is None:
            raise RuntimeError("INTERNAL ERROR: Unable to retrieve "
                "InstallProfile from DataObjectCache")
        LOGGER.debug("Including local disks? : %s", profile.show_local)
        LOGGER.debug("Including iSCSI disks? : %s", profile.show_iscsi)
        matching_disks = list()
        for disk in self._td_disks:
            if profile.show_iscsi and \
                disk.disk_prop is not None and \
                disk.disk_prop.dev_type == "iSCSI":
                matching_disks.append(disk)
                LOGGER.debug("Including (iSCSI) disk: %s", disk.ctd)
                continue
            if profile.show_local and \
                (disk.disk_prop is None or \
                disk.disk_prop.dev_type != "iSCSI"):
                matching_disks.append(disk)
                LOGGER.debug("Including (non-iSCSI) disk: %s", disk.ctd)
                continue
            LOGGER.debug("Excluding disk: %s", disk.ctd)
        self._td_disks = matching_disks
        if not self._td_disks:
            LOGGER.error("No discovered disks match user criteria")
            LOGGER.error("Criteria: local disks? : %s", profile.show_local)
            LOGGER.error("Criteria: iSCSI disks? : %s", profile.show_iscsi)
            return

        # Set up the TargetController
        LOGGER.info("TD found %d disks matching criteria", len(self._td_disks))
        self._target_controller = TargetController(doc)

        # First, let TargetController choose an initially-selected disk,
        # as per its rules.
        try:
            # Note: we are assuming that TargetController.initialize()
            # selects a disk not in whole_disk mode
            selected_disks = self._target_controller.initialize()
        except BadDiskError, err:
            LOGGER.error("TargetController failed to select an "
                "initial disk: [%s]", err)
            return
        self._selected_disk = selected_disks[0]
        LOGGER.info("Disk [%s] selected" % self._selected_disk.ctd)

        # If TargetController's choice for initial disk does not match
        # users choices (iSCSI vs local), then select the first remaining
        # suitable disk
        for td_disk in self._td_disks:
            if td_disk.name_matches(self._selected_disk):
                # TC's initial disk is in our filtered list - carry on.
                break
        else:
            LOGGER.debug("TargetController's initial disk does not match "
                         "criteria, so picking a new one")
            for td_disk in self._td_disks:
                try:
                    selected_disks = self._target_controller.select_disk(
                        td_disk, use_whole_disk=self._wholediskmode)
                except SubSizeDiskError as err:
                    LOGGER.debug("TC says disk is too small: [%s] [%s]",
                                 td_disk, err)
                    continue
                except BadDiskError, err:
                    LOGGER.debug("TC says disk is not suitable: [%s] [%s]",
                                 td_disk, err)
                    continue

                self._selected_disk = selected_disks[0]
                LOGGER.info("Disk [%s] selected" % self._selected_disk.ctd)
                break
            else:
                LOGGER.error("NONE OF THE REAMINING DISKS ARE SUITABLE")
                self._selected_disk = None
                return

        LOGGER.info("TD AND TC FINISHED SUCCESSFULLY!")

    def _set_screen_titles(self):
        # NB This messing about is because we want to re-use the existing
        # localized size formatting string from C, but the Python formatting
        # options are different
        size_str = _("Recommended size: %lldGB Minimum: %.1fGB")
        size_str = size_str.replace('%lld', '%s')
        size_str = size_str.replace('%.1f', '%s')

        if self._target_controller is None:
            # Blank out the size values until they are available
            size_str = size_str.replace('%s', '')
        else:
            rec_size = locale.format('%.1f',
                self._target_controller.recommended_target_size.get(
                    units=Size.gb_units))
            min_size = locale.format('%.1f',
                self._target_controller.minimum_target_size.get(
                    units=Size.gb_units))
            size_str = size_str % (rec_size, min_size)

        self.set_titles(_("Disk Selection"),
            _("Where should Oracle Solaris be installed?"),
            size_str)

    def _show_screen_for_td_not_complete(self):
        self._diskstatuslabel.set_markup('')
        self._set_screen_titles()

        # Only create the widgets which don't come from Glade once
        if self._finding_disks_vbox is None:
            self._finding_disks_vbox, self._busy_label = \
                self._create_finding_disks_vbox()

        empty_container(self._disksviewport)
        self._disksviewport.add(self._finding_disks_vbox)
        self._disksviewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self._disksviewport.show_all()
        self._toplevel.show()

        self._busy_label.grab_focus()

        self.set_back_next(back_sensitive=True, next_sensitive=False)

    def _show_screen_for_td_complete(self):
        if not get_td_results_state():
            self._process_td_results()
            set_td_results_state(True)

        self._diskstatuslabel.set_markup('')

        # If an error occurred in TD or TC, then inform the user
        # ERROR #1 - TD didn't find any Disks
        # ERROR #2 - TC couldn't select an initial Disk
        error_occurred = False
        if not self._td_disks or self._selected_disk is None:
            error_occurred = True
            markup = '<span font_desc="Bold">%s</span>' % \
                _("No suitable disks were found.")
            self._diskstatuslabel.set_markup(markup)
            self._diskerrorimage.show()

        self._set_screen_titles()

        # Recreate the disk buttons each time, as each execution of
        # TD can find different disks
        self._disk_buttons_hbuttonbox = \
            self._create_disk_buttons_hbuttonbox()
        self._create_disk_buttons()

        empty_container(self._disksviewport)
        self._disksviewport.add(self._disk_buttons_hbuttonbox)
        self._disksviewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self._disksviewport.show_all()

        # Hook up the scrollbar to the viewport
        viewportadjustment = self._diskselectionhscrollbar.get_adjustment()
        gobject.GObject.connect(viewportadjustment,
            "changed",
            self.viewport_adjustment_changed,
            self._diskselectionhscrollbar)
        self._disksviewport.set_hadjustment(viewportadjustment)

        if not error_occurred:
            # Match the currently selected disk to one of the disk
            # radio buttons and make that button active
            active_button = None
            for button in self._disk_buttons:
                td_disk = gobject.GObject.get_data(button, "Disk")
                if td_disk.name_matches(self._selected_disk):
                    button.set_active(True)
                    active_button = button
                    break
            else:
                # _process_td_results should have prevented this
                raise RuntimeError("INTERNAL ERROR: selected disk does not"
                                   " match any disk icon")

            # Set whole disk/partition disk radio button to initial setting
            if self._wholediskmode:
                self._wholediskradio.set_active(True)
            else:
                self._partitiondiskradio.set_active(True)

            # Show the disk partitioning radio buttons and associated widgets
            self._diskradioalignment.show_all()

            self._display_selected_disk_details()

            if active_button:
                active_button.grab_focus()

            self._partitioningvbox.show()

        self._toplevel.show()

        if error_occurred:
            self.set_back_next(back_sensitive=True, next_sensitive=False)
        else:
            self.set_back_next(back_sensitive=True, next_sensitive=True)

    def _td_completion_monitor(self):
        '''
            Monitors the completion status of target discovery and shows
            the disk & partitioning controls if this screen is mapped.
        '''
        if is_discovery_complete():
            if (self._toplevel is not None) and \
                (self._toplevel.flags() & gtk.MAPPED):
                self._show_screen_for_td_complete()
            self._monitor_timeout_id = None
            return False
        else:
            return True

    def _display_selected_disk_details(self):
        self._select_disk_panel()
        selected_disks = self._target_controller.desired_disks
        if selected_disks:
            if self._wholediskmode:
                # Show "Entire disk will be erased" warning
                self._diskwarninghbox.show()

                # Hide the custom disk partitioning details.
                self._disk_panel.hide()
            else:
                # Hide "Entire disk will be erased" warning
                self._diskwarninghbox.hide()
                self._disk_panel.display(selected_disks[0],
                    self._target_controller)

    def _create_finding_disks_vbox(self):
        '''
            Creates the new widgets required for the "Finding Disks..."
            version of the screen.

            This method should only be called once per execution
            of the app.
        '''

        finding_disks_vbox = gtk.VBox(homogeneous=False, spacing=0)

        label = gtk.Label()
        markup_str = DiskScreen.BUSY_MARKUP % _(DiskScreen.BUSY_TEXT)
        label.set_markup(markup_str)

        busyimage = gtk.image_new_from_file(IMAGE_DIR + "/"
            "gnome-spinner.gif")

        finding_disks_vbox.pack_start(label, expand=False,
            fill=False, padding=0)
        finding_disks_vbox.pack_end(busyimage, expand=False,
            fill=False, padding=0)

        return finding_disks_vbox, label

    def _create_disk_button_icon(self, disk):
        '''
           Creates a disk button icon appropriate for the specificed disk.
        '''
        if disk.disk_prop is not None and disk.disk_prop.dev_type == "iSCSI":
            # use our own iSCSI disk icon
            disk_pixbuf = gtk.gdk.pixbuf_new_from_file(
                os.path.join(IMAGE_DIR, "iscsi_disk.png"))
            disk_width = disk_pixbuf.get_width()
            disk_height = disk_pixbuf.get_height()
        else:
            # use our own generic disk icon
            disk_pixbuf = gtk.gdk.pixbuf_new_from_file(
                os.path.join(IMAGE_DIR, "generic_disk.png"))
            disk_width = disk_pixbuf.get_width()
            disk_height = disk_pixbuf.get_height()

        emblem_iconinfo = None
        # Apply any additional emblems appropriate for the disk
        # Too small or incompatible block_size
        if disk.disk_prop.dev_size < \
            self._target_controller.minimum_target_size or \
            not self._target_controller._is_block_size_compatible(disk):
            emblem_iconinfo = self._icon_theme.lookup_icon("dialog-error",
                16, 0)
        # No readable partition table / disk label
        elif disk.label is None:
            emblem_iconinfo = self._icon_theme.lookup_icon("dialog-warning",
                16, 0)

        if emblem_iconinfo is not None:
            emblem_filename = emblem_iconinfo.get_filename()
            emblem_pixbuf = gtk.gdk.pixbuf_new_from_file(emblem_filename)
            emblem_width = emblem_pixbuf.get_width()
            emblem_height = emblem_pixbuf.get_height()
            emblem_pixbuf.composite(disk_pixbuf,
                disk_width - emblem_width,
                disk_height - emblem_height,
                emblem_width,
                emblem_height,
                disk_width - emblem_width,
                disk_height - emblem_height,
                1,
                1,
                gtk.gdk.INTERP_BILINEAR,
                192)
        disk_image = gtk.image_new_from_pixbuf(disk_pixbuf)
        disk_image.show()

        return disk_image

    def _set_disk_button_icon(self, button, image):
        '''
            Sets the icon for button to image
        '''
        vbox = button.get_data("iconvbox")
        oldimage = button.get_data("icon")
        if oldimage is not None:
            oldimage.destroy()
        vbox.pack_start(image, True, True, 0)
        button.set_data("icon", image)

    def _create_disk_buttons(self):
        '''
            Creates the graphical disk selection radio button widgets
        '''
        self._disk_buttons = list()
        first_button = None
        for td_disk in self._td_disks:
            name, summary = td_disk.get_details()

            # If applicable, also show the iSCSI LUN for this disk in the
            # tooltip, by looking at the saved device->LUN dictionary in
            # the Iscsi obj in DOC
            if td_disk.ctd is not None:
                doc = InstallEngine.get_instance().doc
                iscsi = doc.volatile.get_first_child(name=ISCSI_LABEL,
                                                     class_type=Iscsi)
                if iscsi:
                    if td_disk.ctd in iscsi.iscsi_dict:
                        summary += "\n" + \
                            _("iSCSI LUN : %s") % \
                                iscsi.iscsi_dict[td_disk.ctd].lun_num

            label = gtk.Label(name)
            if first_button is None:
                button = gtk.RadioButton()
                first_button = button
            else:
                # Add subsequent buttons to the same RadioButton group
                # as the first one
                button = gtk.RadioButton(group=first_button)
            button.set_mode(False)
            button.set_relief(gtk.RELIEF_NONE)
            button.set_tooltip_text(summary)

            # Attach the Disk object to the RadioButton for future retrieval
            gobject.GObject.set_data(button, "Disk", td_disk)
            # Save the buttons so we can activate them later
            self._disk_buttons.append(button)

            align = gtk.Alignment(0.5, 0.5, 0, 0)
            button.add(align)

            vbox = gtk.VBox(homogeneous=False, spacing=0)
            align.add(vbox)

            vbox.pack_end(label, expand=False, fill=False, padding=0)

            button.set_data("iconvbox", vbox)
            self._set_disk_button_icon(button,
                self._create_disk_button_icon(td_disk))

            self._disk_buttons_hbuttonbox.pack_start(button,
                expand=False, fill=False, padding=0)

            button.connect("toggled",
                self.diskbutton_toggled,
                td_disk)

        # Update disk button icons if icon theme changes
        self._icon_theme.connect("changed", self._icon_theme_changed)

    def _create_disk_buttons_hbuttonbox(self):
        '''
            Creates the horizontal container widget for disk buttons.

            This method should only be called once per execution
            of the app.
        '''
        disk_buttons_hbuttonbox = gtk.HButtonBox()
        disk_buttons_hbuttonbox.set_spacing(36)
        disk_buttons_hbuttonbox.set_layout(gtk.BUTTONBOX_START)

        return disk_buttons_hbuttonbox

    def _icon_theme_changed(self, theme):
        '''
            Signal handler for when icon theme is changed. Updates disk
            button icons to correspond to new icon theme style
        '''
        for button in self._disk_buttons:
            disk = button.get_data("Disk")
            self._set_disk_button_icon(button,
                self._create_disk_button_icon(disk))

    def _raise_error(self, msg):
        ''' Raise the NotOkToProceed exception.

            Before raising the exception,  we re-display the current disk's
            details.  This is mainly relevant for the Fdisk panel, to
            ensure the partitions are setup for the user to continue
            editing them, once the dialog has been dismissed.
        '''
        self._display_selected_disk_details()

        raise NotOkToProceedError(msg)

    def _select_disk_panel(self):
        ''' Sets the correct disk_panel object type (gpt_panel or fdisk_panel)
            for the currently selected disk.
        '''
        selected_disks = self._target_controller.desired_disks
        if not selected_disks:
            return

        selected_disk = selected_disks[0]
        if selected_disk.label == "GPT" and \
            not isinstance(self._disk_panel, GPTPanel):
            self._disk_panel.hide()
            self._custompartitionbox.remove(self._disk_panel.toplevel)
            self._disk_panel = self._gpt_panel
            self._custompartitionbox.pack_start(self._disk_panel.toplevel,
                expand=True, fill=True, padding=0)
        elif selected_disk.label == "VTOC" and \
            not isinstance(self._disk_panel, FdiskPanel):
            self._disk_panel.hide()
            self._custompartitionbox.remove(self._disk_panel.toplevel)
            self._disk_panel = self._fdisk_panel
            self._custompartitionbox.pack_start(self._disk_panel.toplevel,
                expand=True, fill=True, padding=0)

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
Disk Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import locale
import logging

import glib
import gobject
import gtk
import numpy

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from solaris_install import CalledProcessError
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.fdisk_panel import FdiskPanel
from solaris_install.gui_install.gui_install_common import \
    empty_container, modal_dialog, IMAGE_DIR, COLOR_WHITE, \
    DEFAULT_LOG_LOCATION, GLADE_ERROR_MSG, N_
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target import Target
from solaris_install.target.controller import TargetController, \
    BadDiskError, SubSizeDiskError, DEFAULT_ZPOOL_NAME
from solaris_install.target.libadm.const import V_ROOT
from solaris_install.target.logical import Zpool, Zvol, Filesystem
from solaris_install.target.physical import Disk, Partition, \
    Slice
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

        self._td_complete = False
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

        if None in [self._disksviewport, self._diskselectionhscrollbar,
            self._diskerrorimage, self._diskwarningimage,
            self._diskstatuslabel, self._partitioningvbox,
            self._diskradioalignment, self._diskwarninghbox,
            self._wholediskradio, self._partitiondiskradio]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        self.fdisk_panel = FdiskPanel(self.builder)
        self._icon_theme = gtk.icon_theme_get_default()
        self._busy_label = None

    def enter(self):
        ''' Show the Disk Screen.

            This method is called when the user navigates to this screen
            via the Back and Next buttons.
        '''

        self._toplevel = self.set_main_window_content("diskselectiontoplevel")

        # Screen-specific configuration
        self.activate_stage_label("diskstagelabel")

        # Initially, hide the Partitioning VBox and Disk selection scrollbar
        self._partitioningvbox.hide_all()
        self._diskselectionhscrollbar.hide()

        if self._td_complete:
            self._show_screen_for_td_complete()
        else:
            self._show_screen_for_td_not_complete()
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

        # First, tell the FdiskPanel to tidy up the disk
        self.fdisk_panel.finalize()

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

        # Fetch the Solaris2 partition
        partitions = selected_disk.get_children(class_type=Partition)
        solaris_partitions = [part for part in partitions \
            if part.part_type == Partition.name_to_num("Solaris2")]

        # ERROR #3 - No Solaris partitions defined
        if len(solaris_partitions) == 0:
            LOGGER.error("No Solaris2 partition on disk.")
            modal_dialog(_("The selected disk contains no "
                "Solaris partitions."),
                _("Create one Solaris partition or use the whole disk."))
            self._raise_error("No Solaris partitions on disk.")

        # ERROR #4 - Must be only one Solaris partition
        if len(solaris_partitions) > 1:
            LOGGER.error("Too many Solaris2 partitions on disk.")
            modal_dialog(_("There must be only one "
                "Solaris partition."),
                _("Change the extra Solaris partitions to another type."))
            self._raise_error("Too many Solaris partitions on disk.")

        # ERROR #5 - Solaris partition is too small
        if solaris_partitions[0].size < \
            self._target_controller.minimum_target_size:
            LOGGER.error("Solaris2 partition too small.")
            LOGGER.error("Minimum size is %s." % \
                self._target_controller.minimum_target_size)
            LOGGER.error("Partition size is (%s)." % \
                solaris_partitions[0].size)
            modal_dialog(_("The Solaris partition is too "
                "small for Solaris installation."),
                _("Increase the size of the Solaris partition."))
            self._raise_error("Solaris2 partition too small")

        # Do any necessary tidying up before final validation
        if not selected_disk.whole_disk:
            self._fixup_solaris_partition(solaris_partitions[0])

        # Create swap and dump, as required

        # Get the Solaris slice
        solaris_slice = None
        all_slices = solaris_partitions[0].get_children(class_type=Slice)
        for slc in all_slices:
            if slc.in_zpool == ROOT_POOL:
                solaris_slice = slc

        if solaris_slice is None:
            LOGGER.error("Cannot locate Solaris (rpool) slice.")
            modal_dialog(_("Validation failed."), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))
            self._raise_error("Cannot locate Solaris (rpool) slice.")

        (swap_type, swap_size, dump_type, dump_size) = \
            self._target_controller.calc_swap_dump_size(
                self._target_controller.minimum_target_size,
                solaris_slice.size,
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

        # ERROR #6 - Target class final validation
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
        if solaris_partitions[0].size < \
            self._target_controller.recommended_target_size:

            LOGGER.info("Partition smaller than recommended")
            LOGGER.info("Recommended size is %s",
                self._target_controller.recommended_target_size)
            LOGGER.info("Partition size is (%s)", solaris_partitions[0].size)

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
        profile = doc.persistent.get_first_child(
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
                # Hide the custom fdisk partitioning details
                self.fdisk_panel.hide()
                self._wholediskradio.set_active(True)
                return
            except BadDiskError, err:
                LOGGER.error("ERROR: TargetController cannot " \
                    "select disk [%s]" % disk.ctd)
                self._selected_disk = None
                modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                    (_("See log file for details."), DEFAULT_LOG_LOCATION))
                self.set_back_next(back_sensitive=True, next_sensitive=False)
                return

            self._selected_disk = selected_disks[0]
            LOGGER.info("Disk [%s] selected" % self._selected_disk.ctd)
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

        # Re-select the disk, this time with use_whole_disk=True
        try:
            selected_disks = self._target_controller.select_disk(
                self._selected_disk,
                use_whole_disk=self._wholediskmode)
        except BadDiskError, err:
            LOGGER.error("ERROR: TargetController cannot " \
                "select disk [%s]" % self._selected_disk.ctd)
            self._selected_disk = None
            modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))
            self.set_back_next(back_sensitive=True, next_sensitive=False)
            return

        self._selected_disk = selected_disks[0]
        LOGGER.info("Disk [%s] selected", self._selected_disk.ctd)

        self._display_selected_disk_details()

    def installationdisk_partitiondiskradio_toggled(self, widget,
        user_data=None):
        ''' Signal handler for "toggled" event in _partitiondiskradio.
        '''

        if not widget.get_active():
            # We're not interested when the button is being de-activated
            return

        self._wholediskmode = False

        # Re-select the disk, this time with use_whole_disk=False
        try:
            selected_disks = self._target_controller.select_disk(
                self._selected_disk,
                use_whole_disk=self._wholediskmode)
        except BadDiskError, err:
            LOGGER.error("ERROR: TargetController cannot " \
                "select disk [%s]" % self._selected_disk.ctd)
            self._selected_disk = None
            modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))
            self.set_back_next(back_sensitive=True, next_sensitive=False)
            return

        self._selected_disk = selected_disks[0]
        LOGGER.info("Disk [%s] selected" % self._selected_disk.ctd)

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
    # Callback methods

    def td_callback(self, status, failed_cps):
        '''
            This is the callback registered with the InstallEngine to
            be called when TargetDiscovery completes execution.

            If TD completes successfully, the attributes
            self._td_disks and self._target_controller will be set.

            If TargetController successfully selects an initial disk,
            then self.selected_disk will be set.

            In any event self._td_complete will be set to True.
        '''

        # Ensure that the checkpoint did not record any errors
        if status != InstallEngine.EXEC_SUCCESS:
            # Log the errors, but then attempt to proceed anyway
            LOGGER.error("ERROR: TargetDiscovery FAILED")

            for failed_cp in failed_cps:
                err_data_list = errsvc.get_errors_by_mod_id(failed_cp)
                if len(err_data_list):
                    err_data = err_data_list[0]
                    err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
                else:
                    err = "Unknown error"

                LOGGER.error("Checkpoint [%s] logged error: [%s]" % \
                    (failed_cp, err))

        # Fetch and save the Disk objects from "discovered targets" in DOC
        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache
        discovered_root = None
        try:
            discovered_root = doc.get_descendants(name=Target.DISCOVERED,
                class_type=Target,
                max_depth=2,
                max_count=1,
                not_found_is_err=True)[0]
        except ObjectNotFoundError, err:
            LOGGER.error("TD didn't create 'discovered' Target: [%s]" % \
                str(err))

        if discovered_root is not None:
            LOGGER.info("TD XML:\n%s" % discovered_root.get_xml_tree_str())

            try:
                self._td_disks = discovered_root.get_children(class_type=Disk,
                    not_found_is_err=True)
            except ObjectNotFoundError, err:
                LOGGER.error("No Disks in 'discovered' Target: [%s]" % \
                    str(err))
                LOGGER.error("TD XML:\n%s" % \
                    discovered_root.get_xml_tree_str())

        # Set up the TargetController and let it select an initial disk
        if self._td_disks:
            LOGGER.info("TD found %d disks" % len(self._td_disks))
            self._target_controller = TargetController(doc)

            try:
                # Note: we are assuming that TargetController.initialize()
                # selects a disk not in whole_disk mode
                selected_disks = self._target_controller.initialize()
            except BadDiskError, err:
                LOGGER.error("ERROR - TargetController failed to select an " \
                    "initial disk: [%s]" % str(err))

            if selected_disks:
                LOGGER.info("TD FINISHED SUCCESSFULLY!")

                self._selected_disk = selected_disks[0]
                LOGGER.info("Disk [%s] selected" % self._selected_disk.ctd)
            else:
                LOGGER.error("TD DID NOT FINISH SUCCESSFULLY!")

        # _td_completion_monitor() will notice this and display the controls
        self._td_complete = True

    #--------------------------------------------------------------------------
    # Private methods

    def _fixup_solaris_partition(self, partition):
        ''' Perform any necessary tidying up on the Solaris partition.

            Params:
            - partition, a Partition object representing the Solaris2
              partition for this install

            Actions taken:
            1. Create slice 0.
                At this stage the slices on the Solaris2 partition may be
                in a number of states:
                - discovered slices from a previous install may still be
                  present if the user has not made any adjustments to the
                  partition (although they may not match our requirements)
                - slices added by TargetController may be present
                - there may be no slices if the user has made any adjustments
                  to the type or size of the partition (as these operations
                  involve removing any child slices)
                The application does not allow the user any control over
                slice configuration, and we need to ensure a consistent state
                before proceeding, so we remove any existing slices found
                on the Solaris partition and create slice 0.

            2. Activate the partition, if needed.
                Ensure that the bootid attribute of the partition is
                ACTIVE
        '''

        # Create slice 0
        LOGGER.info("Creating slice 0 on Solaris2 partition.")

        # If we are setting in_zpool and in_vdev on the slice, we must ensure
        # they are unset on the Disk
        disk = partition.parent
        if disk is not None:
            disk.in_zpool = None
            disk.in_vdev = None

        partition.create_entire_partition_slice(in_zpool=ROOT_POOL,
                                                in_vdev="vdev", tag=V_ROOT)

        # Activate the partition (primary partition's only)
        if partition.is_primary:
            if partition.bootid != Partition.ACTIVE:
                LOGGER.info("Activating Solaris2 partition.")
                partition.bootid = Partition.ACTIVE

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

        self.set_titles(_("Disk"),
            _("Where should Oracle Solaris be installed?"),
            size_str)

    def _show_screen_for_td_not_complete(self):
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
        self._set_screen_titles()

        # Only create the widgets which don't come from Glade once
        if self._disk_buttons_hbuttonbox is None:
            self._disk_buttons_hbuttonbox = \
                self._create_disk_buttons_hbuttonbox()
            self._create_disk_buttons()

        # Match the currently selected disk to one of the disk
        # radio buttons and make that button active
        active_button = None
        if self._selected_disk is not None:
            for button in self._disk_buttons:
                td_disk = gobject.GObject.get_data(button, "Disk")
                if td_disk.name_matches(self._selected_disk):
                    button.set_active(True)
                    active_button = button
                    break

        # If an error occurred in TD or TC, then activate the
        # appropriate widgets

        # ERROR #1 - TD didn't find any Disks
        if not self._td_disks:
            markup = '<span font_desc="Bold">%s</span>' % \
                _("No disks were found.")
            self._diskstatuslabel.set_markup(markup)
            self._diskerrorimage.show()
            self._diskstatuslabel.show()

        # ERROR #2 - TC couldn't select an initial Disk
        if self._selected_disk is None:
            modal_dialog(_("Internal Error"), "%s\n\n%s" % \
                (_("See log file for details."), DEFAULT_LOG_LOCATION))

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

        # Set the whoe disk/partition disk radio button to its initial setting
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

        if not self._td_disks or self._selected_disk is None:
            self.set_back_next(back_sensitive=True, next_sensitive=False)
        else:
            self.set_back_next(back_sensitive=True, next_sensitive=True)

    def _td_completion_monitor(self):
        '''
            Monitors the completion status of target discovery and shows
            the disk & partitioning controls if this screen is mapped.
        '''
        if self._td_complete:
            if (self._toplevel is not None) and \
                (self._toplevel.flags() & gtk.MAPPED):
                self._show_screen_for_td_complete()
            return False
        else:
            return True

    def _display_selected_disk_details(self):
        if self._selected_disk is not None:
            if self._wholediskmode:
                # Show "Entire disk will be erased" warning
                self._diskwarninghbox.show()

                # Hide the custom fdisk partitioning details
                self.fdisk_panel.hide()
            else:
                # Hide "Entire disk will be erased" warning
                self._diskwarninghbox.hide()

                self.fdisk_panel.display(self._selected_disk,
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
        disk_iconinfo = self._icon_theme.lookup_icon("gnome-dev-harddisk",
            48, 0)
        if disk_iconinfo is None:
            # If we cannot get the icon info from the theme, then
            # just fall back to making up a blank image
            markup = '<span font_desc="Bold">%s</span>' % _("Unable "
                "to display correct 'disk' graphics, but all other "
                "information is available.")
            self._diskstatuslabel.set_markup(markup)
            self._diskerrorimage.show()
            self._diskstatuslabel.show()
            LOGGER.warn("WARNING - couldn't get harddisk icon from theme - "
                 "using blank icon.")
            disk_width = 48
            disk_height = 48
            pixbuf_array = numpy.zeros((disk_height, disk_width, 4), 'B')
            disk_pixbuf = gtk.gdk.pixbuf_new_from_array(pixbuf_array,
                gtk.gdk.COLORSPACE_RGB, 8)
        else:
            disk_filename = disk_iconinfo.get_filename()
            disk_pixbuf = gtk.gdk.pixbuf_new_from_file(disk_filename)
            disk_width = disk_pixbuf.get_width()
            disk_height = disk_pixbuf.get_height()

        emblem_iconinfo = None
        # Apply any additional emblems appropriate for the disk
        # Too small
        if disk.disk_prop.dev_size < \
            self._target_controller.minimum_target_size:
            emblem_iconinfo = self._icon_theme.lookup_icon("dialog-error",
                16, 0)

        # NB - Future enhancement: emblems required for disks > 2Tib and
        # disks with unreadable partition table (not sure how to extract this
        # info from TargetController/TD yet.
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
        first_button = None
        for td_disk in self._td_disks:
            name, summary = td_disk.get_details()
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

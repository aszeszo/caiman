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
Panel for configuring GPT partitions.

Classes:
    GPTPanel
    UIDisk
    UIPartition
'''

import pygtk
pygtk.require('2.0')

import locale
import logging

import gobject
import gtk

from copy import copy

from solaris_install.gui_install.base_screen import NotOkToProceedError
from solaris_install.gui_install.disk_panel import DiskPanel
from solaris_install.gui_install.gui_install_common import \
    COLOR_WHITE, modal_dialog, GLADE_DIR, GLADE_ERROR_MSG
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import BadDiskError, \
    DEFAULT_VDEV_NAME, DEFAULT_ZPOOL_NAME
from solaris_install.target.libefi import const as efi_const
from solaris_install.target.physical import GPTPartition, \
    InsufficientSpaceError, NoGPTPartitionSlotsFree
from solaris_install.target.size import Size

# Glade layout file for this widget
GPT_GLADE = "gpt-panel.xml"

PARTITION_ACTION_PRESERVE = "preserve"

# Minimum usable partition size, (just under) 0.1 GB
MIN_USABLE_SIZE = Size("0.09" + Size.gb_units)
# Maximum acceptable rounding error, (just over) 0.1 GB
ACCEPTABLE_ROUNDING_ERR_GB = 0.11
ZERO_SIZE = Size("0" + Size.byte_units)

LOGGER = None


class GPTPanel(DiskPanel):
    '''
        Controls the creation, display and user interaction with the
        GPT partitioning table on the DiskScreen.

        APIs:
            from solaris_install.gui_install.gpt_panel import GPTPanel

            gpt_panel = GPTPanel(gtk_builder)
            gpt_panel.hide()
            gpt_panel.display(disk, target_controller)
            gpt_panel.finalize()
    '''
    editable_types = (efi_const.EFI_UNUSED, efi_const.EFI_USR)
    resizable_types = (efi_const.EFI_USR,)

    def __init__(self, builder):
        ''' Initializer method. Called from the constructor.

            Params:
            - builder, a GtkBuilder object used to retrieve widgets
              from the Glade XML files

            Returns: nothing
        '''
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        super(GPTPanel, self).__init__(builder)

        allowed_types = list(GPTPanel.editable_types)
        self._allowed_types = tuple(allowed_types)

        self._disk = None
        self._ui_disk = None
        self._target_controller = None
        self._signal_widgets = dict()
        self._radio_buttons = None

        builder.add_from_file(GLADE_DIR + "/" + GPT_GLADE)
        # Widgets from the Glade XML files that are referenced in this class
        self._toplevel = builder.get_object("gptpaneltoplevel")
        viewport = builder.get_object("gptviewport")
        self.gpetable = builder.get_object("gpetable")
        self._unreadableparts = builder.get_object("unreadablepartshbox")
        self._readableparts = builder.get_object("partsfoundlabel")
        self._resetbutton = builder.get_object("gptresetbutton")

        if None in [self._toplevel,
            viewport,
            self.gpetable,
            self._unreadableparts,
            self._readableparts,
            self._resetbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        viewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)

        # Initially hide the widgets and empty any widgets that
        # may have been in the gpttable, which will be dynamically
        # populated when we display.
        self._toplevel.hide()
        self._unreadableparts.hide()

        # Connect up the reset button clicked signal
        self._resetbutton.connect("clicked",
            self._reset_button_clicked)

    #--------------------------------------------------------------------------
    # Property methods
    @property
    def allowed_types(self):
        ''' Instance proprerty to return the list of allowed partition type
            GUIDs
        '''
        return self._allowed_types

    @property
    def toplevel(self):
        ''' Instance property to return the toplevel widget of the
            DiskPanel subclass object
        '''
        return self._toplevel

    #--------------------------------------------------------------------------
    # API methods
    def hide(self):
        ''' Hide the entire panel.

            Returns: nothing
        '''
        self.toplevel.hide()

    def display(self, disk, target_controller):
        ''' Show the custom gpt partitioning panel for the given Disk.

            Params:
            - disk, the Disk object that is being displayed/modified
            - target_controller, the TargetController object used to
              refetch the disk's previous layout, if Reset is pressed.

            Returns: nothing
        '''
        self._disk = disk
        self._target_controller = target_controller

        # Set _ui_disk to None to force a complete redraw
        self._ui_disk = None
        self._update()
        self.toplevel.show()

    def finalize(self):
        ''' Tidies up the currently selected disk, so that it is
            ready for validation.

            1. As the user edited the disk, "Empty" partitions may have
            been temporarily added to represent the available space that
            could be used to create new partitions.
            We must now remove these "Empty" partitions before proceeding.

            2. Resulting from the above, the partition names may no
            longer begin at the lowest available names (eg our first
            partition may be "2" instead of "1").  We shuffle the
            partition names up.

            Returns: nothing
        '''

        if self._disk is None:
            return

        LOGGER.debug("Disk layout before tidy up:\n%s" % self._disk)

        # Delete "Empty" partitions
        partitions = self._disk.get_children(class_type=GPTPartition)
        for partition in partitions:
            if partition.action == "create" and partition.is_unused:
                LOGGER.debug("Deleting GPT partition %s" % partition.name)
                self._disk.delete_gptpartition(partition)

        # Shuffle up the partition names so that they occupy the lowest
        # available names.
        partitions = self._disk.get_children(class_type=GPTPartition)
        for partition in sorted(partitions, key=lambda p: int(p.name)):
            if partition.action != "create":
                continue
            # Don't mess with the reserved partition which should be at
            # partition name 8 or higher. add_gpt_reserve() takes care of
            # ensuring this
            if partition.is_reserved:
                continue

            lowest_available_name = self._disk.get_next_partition_name()

            if lowest_available_name is not None:
                if int(partition.name) > int(lowest_available_name):
                    LOGGER.debug("Renaming partition %s to %s" % \
                        (partition.name, lowest_available_name))

                    # We can't just change the partition name - we must
                    # add a new one and delete the old one.
                    self._disk.add_gptpartition(lowest_available_name,
                        partition.start_sector, partition.size.sectors,
                        size_units=Size.sector_units,
                        partition_type=partition.guid,
                        in_zpool=partition.in_zpool,
                        in_vdev=partition.in_vdev)

                    self._disk.delete_gptpartition(partition)

        LOGGER.info("Disk layout after tidy up:\n%s" % self._disk)

    def validate(self):
        ''' Validate the user selections before proceeding.

            Perform a series of validations on the selected
            disk and the selected partitions, if appropriate.

            If the Disk and/or Partitions are not suitable for the install,
            then display an error dialog and raise an exception.

            Raises: NotOkToProceedError
        '''
        # Refuse to validate a VTOC labeled disk
        if self._disk.label == "VTOC":
            raise RuntimeError("Internal error: GPT based validation " \
                "is invalid for VTOC labeled disk: %s" \
                 % self._disk)

        # Fetch the Solaris partition
        partitions = self._disk.get_children(class_type=GPTPartition)
        solaris_partitions = [p for p in partitions if p.is_solaris]

        # ERROR #1 - No Solaris partitions defined
        if len(solaris_partitions) == 0:
            LOGGER.error("No Solaris partition on disk.")
            modal_dialog(_("The selected disk contains no "
                "Solaris partitions."),
                _("Create one Solaris partition or use the whole disk."))
            raise NotOkToProceedError("No Solaris partitions on disk.")

        selected_partitions = [p for p in solaris_partitions if \
             p.in_zpool == DEFAULT_ZPOOL_NAME and \
             p.in_vdev == DEFAULT_VDEV_NAME]

        # ERROR #2 - Must be one selected Solaris partition
        if len(selected_partitions) == 0:
            LOGGER.error("No selected Solaris partitions on disk.")
            modal_dialog(_("There must be one selected "
                "Solaris partition."),
                _("Please select one Solaris partition."))
            raise NotOkToProceedError("No Solaris partition selected.")

        # ERROR #3 - Must be only one selected Solaris partition
        # This should be impossible because single selection is enforced by the
        # radio buttons under normal circumstances
        if len(selected_partitions) > 1:
            LOGGER.error("Too many Solaris partitions selected.")
            modal_dialog(_("There must be only one selected"
                "Solaris partition."),
                _("Ensure that only one Solaris partition is selected."))
            raise NotOkToProceedError("Too many Solaris partitions selected.")

        # ERROR #4 - Solaris partition is too small
        if selected_partitions[0].size < \
            self._target_controller.minimum_target_size:
            LOGGER.error("Selected Solaris partition too small.")
            LOGGER.error("Minimum size is %s." % \
                self._target_controller.minimum_target_size)
            LOGGER.error("Partition size is (%s)." % \
                solaris_partitions[0].size)
            modal_dialog(_("The selected Solaris partition is too "
                "small for Solaris installation."),
                _("Increase the size of the selected Solaris partition."))
            raise NotOkToProceedError("Selected Solaris partition too small")

        self._fixup_solaris_partition(selected_partitions[0])

        return selected_partitions[0]

    #--------------------------------------------------------------------------
    # Signal handler methods

    def radio_button_toggled(self, radiobutton, index):
        ''' Signal handler for when the partition radio Button
            emits the "toggled" signal.
        '''
        try:
            ui_partition = self._ui_disk.ui_partitions[index]
        except IndexError:
            raise RuntimeError("INTERNAL ERROR: try to get toggle state for "
                               "non-existant partition %d" % index)
        active = radiobutton.get_active()
        if active is False:
            ui_partition.is_install_target = False
            # Don't bother with calling self._update()
            # It would end up getting invoked twice when the new
            # selection radio button is activated, which we will
            # catch below.
        else:
            ui_partition.is_install_target = True
            self._update()

    def size_value_changed(self, spinbutton, index):
        ''' Signal handler for when the partition size SpingButton
            emits the "value_changed" signal.
        '''
        try:
            ui_partition = self._ui_disk.ui_partitions[index]
        except IndexError:
            raise RuntimeError("INTERNAL ERROR: try to resize non-existant "
                               "GPT partition %d" % index)

        if ui_partition.partition.guid not in GPTPanel.resizable_types:
            raise RuntimeError("INTERNAL ERROR - attempt to resize non "
                                 "resizable partition %d" % index)

        new_size_val = spinbutton.get_value()

        ui_partition.resize(new_size_val, size_units=Size.gb_units)

        self._update()

    def type_changed(self, combo, index):
        ''' Signal handler for when the partition type ComboBox
            emits the "changed" signal.
        '''

        try:
            ui_partition = self._ui_disk.ui_partitions[index]
        except IndexError:
            raise RuntimeError("INTERNAL ERROR: try to change type for "
                               "non-existant partition %d" % index)

        new_iter = combo.get_active_iter()
        model = combo.get_model()
        if new_iter is None:
            raise RuntimeError("INTERNAL ERROR: try to change type  "
                                 "to unspecified value" % index)

        new_guid = model.get_value(new_iter, 1)
        ui_partition.partition.change_type(new_guid)

        self._update()

    def size_insert_text(self, widget, new_text, new_text_len,
                         position, index):
        ''' Signal handler for when the partition size SpinButtons
            receive an "insert-text" signal.
        '''

        old_text = widget.get_text()
        old_len = len(old_text)
        pos = widget.get_position()
        if pos < 0 or pos > old_len:
            return

        updated_text = "%s%s%s" % \
            (old_text[0:pos], new_text, old_text[pos:old_len])

        # Check the updated entry is a valid floating point number
        try:
            updated_val = locale.atof(updated_text)
        except ValueError:
            gobject.GObject.stop_emission(widget, "insert-text")
            return

        # Check the updated entry is within the allowed range
        range_min, range_max = widget.get_range()
        if updated_val < range_min or updated_val > range_max:
            gobject.GObject.stop_emission(widget, "insert-text")
            return

        # Check the updated entry has no more than 1 decimal place
        # (We cannot assume that "." is always the decimal point char,
        # so any non-digital char is taken to be the decimal point.)
        for char in updated_text:
            if not char.isdigit():
                index = updated_text.index(char)
                if len(updated_text) > index + 2:
                    gobject.GObject.stop_emission(widget, "insert-text")

    def size_delete_text(self, widget, start, end, index):
        ''' Signal handler for when the partition size SpinButtons
            receive a "delete-text" signal.
        '''

        old_text = widget.get_text()
        old_len = len(old_text)

        if end == -1:
            end = old_len

        new_text = "%s%s" % (old_text[0:start], old_text[end:old_len])

        try:
            new_val = locale.atof(new_text)
        except ValueError:
            return

        range_min, range_max = widget.get_range()
        if new_val > range_max:
            gobject.GObject.stop_emission(widget, "delete-text")

    #--------------------------------------------------------------------------
    # Private methods

    def _autoselect_solaris_partition(self, ui_disk):
        ''' Looks for the first suitable Solaris partition (guid == EFI_USR)
            of adequate size and selects it.
            If a previous selection exists then the selection is unchanged
            so long as its type and size are still valid for Solaris
            installation
        '''
        fallback = None
        existing = None
        for uip in ui_disk.ui_partitions:
            if uip.is_install_target:
                uip.radiobutton.set_active(True)
                existing = uip
                # If the partition is big enough then we're all set,
                # othewise we will keep looking for a fallback
                if uip.is_viable_target:
                    uip.warningbox.show()
                    break
            # find the first available Solaris (EFI_USR) partition
            # that's big enough and ref. it as a fallback partition
            # in case we don't find one that's already explicitly
            # set up as a root pool vdev.
            elif fallback is None and \
                uip.is_viable_target:
                fallback = uip
        else:
            if fallback is not None:
                if existing is not None:
                    existing.is_install_target = False
                    existing.warningbox.hide()
                fallback.radiobutton.set_active(True)
                fallback.is_install_target = True
                fallback.warningbox.show()

    def _fixup_solaris_partition(self, partition):
        ''' Perform any necessary tidying up on the Solaris partition.

            Params:
            - partition, a GPTPartition object representing the Solaris
              partition for this install

            Actions taken:
            1. Set the partition action to "create"
            2. Unset zpool and zdev attributes on the partitions disk parent
            3. Allocate the required EFI system or BIOS boot partition
            4. Allocate the required Solaris reserved partition
        '''
        sys_part = None
        resv_part = None
        # Set the partition action to "create"
        partition.action = "create"

        # If we are setting in_zpool and in_vdev on the GPT partition,
        # we must ensure they are unset on the Disk
        disk = partition.parent
        disk.in_zpool = None
        disk.in_vdev = None

        partitions = disk.get_children(class_type=GPTPartition)
        # Create required (EFI System or BIOS boot) and reserved partitions

        try:
            sys_part, resv_part, partition = \
                disk.add_required_partitions(partition)

        except NoGPTPartitionSlotsFree as nsf:
            # If there are no unused partitions left we can't proceed
            LOGGER.error("No free slots available for boot partition.")
            modal_dialog(_("The selected disk has no more available " \
                "slots to create a system boot partition"),
                _("Allow at least one unused partition"))
            raise NotOkToProceedError("No free slots available for " \
                                      "system boot partition.")

        except InsufficientSpaceError as ise:
            raise RuntimeError("INTERNAL ERROR: Could not allocate space"
                "for system partition or reserved partition on disk %s: "
                "%s" % (disk, str(ise)))

    def _block_all_handlers(self):
        ''' Block all the known signal handlers.
        '''
        for handler_id in self._signal_widgets.keys():
            gobject.GObject.handler_block(self._signal_widgets[handler_id],
                                          handler_id)

    def _unblock_all_handlers(self):
        ''' Unblock all the known signal handlers.
        '''
        for handler_id in self._signal_widgets.keys():
            gobject.GObject.handler_unblock(self._signal_widgets[handler_id],
                                            handler_id)

    def _disconnect_all_handlers(self):
        ''' Remove all the known signal handlers.
        '''
        for handler_id in self._signal_widgets.keys():
            gobject.GObject.disconnect(self._signal_widgets[handler_id],
                                       handler_id)
            self._signal_widgets.pop(handler_id)

    def _reset_button_clicked(self, widget):
        ''' Signal handler for when the Reset Button is pressed.

            Call TargetController to reset the disk to original layout.

            This method is associated with the reset Button from
            the Glade XML file and in the ScreenManager.
        '''

        if self._target_controller is None:
            return

        try:
            selected_disks = self._target_controller.reset_layout()
        except BadDiskError, err:
            raise RuntimeError("INTERNAL ERROR: TargetController could not "
                "reset layout for disk %s: %s" % (self._disk, err))

        # We only support single disk installs, so we can assume there
        # is only 1 selected Disk
        self._disk = selected_disks[0]

        self.display(self._disk, self._target_controller)

    def _update(self):
        ''' re-fetch all the details for the currently selected disk
            and redraw gpetable to reflect the new details.
        '''

        new_ui_disk = UIDisk(self._disk, self)

        if self._need_complete_redraw(new_ui_disk):
            self._complete_redraw(new_ui_disk)
        else:
            self._selective_redraw(new_ui_disk)

        self._ui_disk = new_ui_disk
        if self._disk.label is None:
            self._readableparts.hide()
            self._unreadableparts.show()
        else:
            self._unreadableparts.hide()
            self._readableparts.show()

    def _need_complete_redraw(self, new_ui_disk):
        ''' compare self._ui_disk and new_ui_disk, checking if there have
            been any changes that require a complete redraw.

            Returns:
            - True if a complete redraw is required
            - False otherwise.
        '''

        if self._ui_disk is None:
            # This may be because this is the first time the panel is
            # being drawn, or because a new disk has been selected, or
            # because the reset button has been pressed.
            return True

        if self._ui_disk.num_parts != new_ui_disk.num_parts:
            # A partition has been added or removed.
            return True

        # If a required partition was added automatically, force a redraw.
        if new_ui_disk.added_required_partitions:
            return True

        for old_part, new_part in zip(self._ui_disk.ui_partitions,
                                      new_ui_disk.ui_partitions):
            old_is_dummy = old_part.partition is None
            new_is_dummy = new_part.partition is None
            if old_is_dummy != new_is_dummy:
                # A row of the panel occupied by a real partition is
                # now occupied by a dummy, or vice versa
                return True

        # Other changes to size or type that do not induce significant
        # changes (such as creating or removing a partition) don't need
        # a full redraw
        return False

    def _complete_redraw(self, new_ui_disk):
        ''' Remove all the widgets inside gpetable; re-create a new
            set of widgets for the the new disk details and display them.
        '''

        self._disconnect_all_handlers()
        self._empty_table()
        self._radio_buttons = None
        for index, ui_partition in enumerate(new_ui_disk.ui_partitions):
            self._add_partition_to_table(index + 1, ui_partition)
        # Reattach the reset button to the empty table
        self.gpetable.attach(self._resetbutton,
            2, 3,
            index + 2, index + 5,
            gtk.FILL, gtk.FILL)
        self._autoselect_solaris_partition(new_ui_disk)
        self.gpetable.show()

        self._unblock_all_handlers()

    def _selective_redraw(self, new_ui_disk):
        ''' Intelligently adjust only those on-screen widgets that
            need to be updated by comparing the previous saved details
            in self._ui_disk and the new values in new_ui_disk and
            updating the relevant widgets to reflect the changes.

            Note that a change to a single value can require
            changes to multiple widgets.
        '''

        # sanity check that it makes sense to be doing a selective redraw
        if self._ui_disk.num_parts != new_ui_disk.num_parts:
            raise RuntimeError("INTERNAL ERROR: cannot do selective redraw")

        # We don't want the changes we make now to trigger additional
        # signal handler calls, so block them all before we start
        self._block_all_handlers()

        # iterate through the UIPartitions in the old vs new UIDisks
        # - for every value that has changed, update the relevant widget(s)
        for row in range(self._ui_disk.num_parts):
            old = self._ui_disk.ui_partitions[row]
            new = new_ui_disk.ui_partitions[row]

            old_min_in_gb = round(old.min_size.get(units=Size.gb_units), 1)
            new_min_in_gb = round(new.min_size.get(units=Size.gb_units), 1)
            old_max_in_gb = round(old.max_size.get(units=Size.gb_units), 1)
            new_max_in_gb = round(new.max_size.get(units=Size.gb_units), 1)

            if old_min_in_gb != new_min_in_gb:
                # If the min size has changed, we need to:
                # - update the range of the size SpinButton
                old.sizespinner.set_range(new_min_in_gb, new_max_in_gb)

            if old_max_in_gb != new_max_in_gb:
                # If the max size has changed, we need to:
                # - update the "Avail" Label text
                # - update the range of the size SpinButton

                old.availlabel.set_text(locale.str(new_max_in_gb))
                old.sizespinner.set_range(new_min_in_gb, new_max_in_gb)

            # If the new partition type is not Solaris or not big enough
            # for installation then desensitise the radio button. The
            # autoselect method will try to pick an alternative shortly
            # after.
            if new.is_viable_target:
                old.radiobutton.set_sensitive(True)
            else:
                old.radiobutton.set_sensitive(False)

            disk = new.partition.parent
            if old.guid != new.guid:
                # If the partition guid has changed, we may also need to
                # - re-do the list of partition types for the
                #   ComboBox and reset the active selection
                # - update the value of the size SpinButton
                # - update the sensitivity of the size SpinButton
                # - change the selection and sensitivity state of radiobutton

                # Set the new active iter
                types_store = old.typecombo.get_model()
                types_store.foreach(old.set_guid_for_combo_model,
                                    new.guid)

                if old.guid not in self.allowed_types:
                    # The user changed from an unsupported type to one
                    # of the supported types. Remove the corresponding
                    # iter of the old type from the tree model.

                    types_store.foreach(old.remove_guid_from_combo_model,
                                        old.guid)

                # The display size value may have changed as it can be
                # 0 or the real value depending on the partition type
                old_display_in_gb = round(
                    old.display_size.get(units=Size.gb_units), 1)
                new_display_in_gb = round(
                    new.display_size.get(units=Size.gb_units), 1)
                if new_display_in_gb != old_display_in_gb:
                    old.sizespinner.set_value(new_display_in_gb)

                # The sensitivty of the Size SpinButton may have changed
                # as only Solaris partitions can be explicitly resized
                if new.is_size_editable != old.is_size_editable:
                    old.sizespinner.set_sensitive(new.is_size_editable)

            if old.data_loss_warn != new.data_loss_warn:
                # If the data_loss_warn flag has changed, we need to show
                # or hide the warnings, as appropriate
                if new.data_loss_warn:
                    old.warningbox.show()
                else:
                    old.warningbox.hide()

            if old.is_install_target != new.is_install_target:
                # If the solaris install target state of the partition
                # has changed we need to adjust the radiobutton
                # accordingly
                old.radiobutton.set_active(new.is_install_target)

        for row in range(self._ui_disk.num_parts):
            # As we are not recreating the widgets, we need to save
            # the references to them in new_ui_disk for the next time
            # round
            old = self._ui_disk.ui_partitions[row]
            new = new_ui_disk.ui_partitions[row]

            new.radiobutton = old.radiobutton
            new.typecombo = old.typecombo
            new.sizespinner = old.sizespinner
            new.availlabel = old.availlabel
            new.warningbox = old.warningbox
        self._autoselect_solaris_partition(new_ui_disk)
        # Re-enable signal handlers
        self._unblock_all_handlers()

    def _empty_table(self):
        ''' Empty and destroy the partitioning contents of gpetable.
            (But not the column header labels or reset button)
        '''
        for child in self.gpetable.get_children():
            top_attach = self.gpetable.child_get_property(child,
                "top-attach")
            # Skip the first row which contains the header labels
            if 0 < top_attach:
                self.gpetable.remove(child)
                # Destroy only the rows with UIPartition objects,
                # but not the reset button at the bottom which we need
                if child != self._resetbutton:
                    child.destroy()

    def _add_partition_to_table(self, row, ui_partition):
        ''' Dynamically create all the widgets needed to display
            a partition and add them to gpetable.

            Params:
            - row, the row number in gpetable for this partition
            - ui_partition, a UIPartition object containing the row
              to be added.  ui_partition may represent a real
              Partition or may be one of the dummies used to show
              the full number of GPT partitions that can be created.

            Returns: Nothing

            The following attributes of ui_partition will be set to
            references to the relevant newly created widgets, for
            later retrieval:
                ui_partition._radiobutton
                ui_partition.typecombo
                ui_partition.sizespinner
                ui_partition.availlabel
                ui_partition.warningbox
        '''
        # partition selection RadioButton (determines Solaris tgt partition)
        radiobutton = gtk.RadioButton()
        # Join the radiobutton to the existing logical group
        if self._radio_buttons is None:
            self._radio_buttons = radiobutton
        else:
            radiobutton.set_group(self._radio_buttons)

        if ui_partition.is_viable_target:
            radiobutton.set_sensitive(True)
        else:
            radiobutton.set_sensitive(False)

        radiobutton.set_active(ui_partition.is_install_target)
        self.gpetable.attach(radiobutton,
            0, 1,
            row, row + 1,
            gtk.FILL, gtk.FILL)
        radiobutton.show()

        # Partition type ComboBox
        types_store = gtk.ListStore(
            gobject.TYPE_STRING,    # Partition type label
            gobject.TYPE_PYOBJECT)  # Partition GUID
        typecombo = gtk.ComboBox(model=types_store)
        textcell = gtk.CellRendererText()
        typecombo.pack_end(textcell, expand=True)
        typecombo.set_attributes(textcell, text=0)
        typecombo.set_cell_data_func(textcell, self._render_type_name)
        typecombo.set_sensitive(ui_partition.is_type_editable)

        for guid in ui_partition.allowed_types:
            efi_name, tag = efi_const.PARTITION_GUID_PTAG_MAP.get(guid,
                ("Unknown", None))
            name = _(efi_name)

            tree_iter = types_store.append()
            if ui_partition.guid == guid:
                typecombo.set_active_iter(tree_iter)
            types_store.set(tree_iter,
                0, name,
                1, guid)

        self.gpetable.attach(typecombo,
            1, 2,
            row, row + 1,
            gtk.FILL, gtk.FILL)
        typecombo.show()

        # SpinButton
        sizespinner = gtk.SpinButton(
            adjustment=gtk.Adjustment(0.0, 0.0, 1.0, 1.0, 0.0, 0.0),
            climb_rate=0.1, digits=1)
        min_size_in_gb = round(
            ui_partition.min_size.get(units=Size.gb_units), 1)
        max_size_in_gb = round(
            ui_partition.max_size.get(units=Size.gb_units), 1)
        display_size_in_gb = round(
            ui_partition.display_size.get(units=Size.gb_units), 1)

        # Sanity check that size is within computed range
        if display_size_in_gb < min_size_in_gb:
            LOGGER.warn("New GPT partition size (%6.2f) is below " \
                "computed minimum (%6.2f). Adjusting." % \
                (display_size_in_gb, min_size_in_gb))
            display_size_in_gb = min_size_in_gb
        if display_size_in_gb > max_size_in_gb:
            LOGGER.warn("New GPT partition size (%6.2f) is above " \
                "computed amximum (%6.2f). Adjusting." % \
                (display_size_in_gb, max_size_in_gb))
            display_size_in_gb = max_size_in_gb

        sizespinner.set_range(min_size_in_gb, max_size_in_gb)
        sizespinner.set_value(display_size_in_gb)
        sizespinner.set_sensitive(ui_partition.is_size_editable)
        self.gpetable.attach(sizespinner,
            2, 3,
            row, row + 1,
            gtk.FILL, gtk.FILL)
        sizespinner.show()

        # available size label
        availlabel = gtk.Label(locale.str(max_size_in_gb))
        availlabel.set_alignment(1.0, 0.5)
        self.gpetable.attach(availlabel,
            3, 4,
            row, row + 1,
            gtk.FILL, gtk.FILL)
        availlabel.show()

        # Set up the warning image & label
        warningbox = gtk.HBox(homogeneous=False, spacing=5)
        warningimage = gtk.image_new_from_stock(
            gtk.STOCK_DIALOG_WARNING,
            gtk.ICON_SIZE_MENU)

        disk = ui_partition.partition.parent
        if ui_partition.guid in disk.required_guids:
            warninglabel = gtk.Label(_(
                '<span size="smaller">Required</span>'))
            warningimage.hide()
        else:
            warninglabel = gtk.Label(_('<span size="smaller"><span '
                'font_desc="Bold">Warning: </span> The data in this '
                'partition will be erased.</span>'))
            warningimage.show()
        warninglabel.set_use_markup(True)
        warningbox.pack_start(warningimage, expand=False,
            fill=False, padding=0)
        warningbox.pack_start(warninglabel, expand=False,
            fill=False, padding=0)
        self.gpetable.attach(warningbox,
            4, 5,
            row, row + 1,
            gtk.FILL, gtk.FILL)
        warninglabel.show()
        if ui_partition.data_loss_warn or \
            ui_partition.guid in disk.required_guids:
            warningbox.show()
        else:
            warningbox.hide()

        handler_id = radiobutton.connect("toggled",
                                       self.radio_button_toggled,
                                       ui_partition.index)
        self._signal_widgets[handler_id] = radiobutton
        radiobutton.handler_block(handler_id)

        handler_id = typecombo.connect("changed",
                                       self.type_changed,
                                       ui_partition.index)
        self._signal_widgets[handler_id] = typecombo
        typecombo.handler_block(handler_id)

        handler_id = sizespinner.connect("value_changed",
                                         self.size_value_changed,
                                         ui_partition.index)
        self._signal_widgets[handler_id] = sizespinner
        sizespinner.handler_block(handler_id)

        handler_id = sizespinner.connect("insert-text",
                                         self.size_insert_text,
                                         ui_partition.index)
        self._signal_widgets[handler_id] = sizespinner
        sizespinner.handler_block(handler_id)

        handler_id = sizespinner.connect("delete-text",
                                         self.size_delete_text,
                                         ui_partition.index)
        self._signal_widgets[handler_id] = sizespinner
        sizespinner.handler_block(handler_id)

        # Save references to the widgets that we may need to update
        # directly later on
        ui_partition.radiobutton = radiobutton
        ui_partition.typecombo = typecombo
        ui_partition.sizespinner = sizespinner
        ui_partition.availlabel = availlabel
        ui_partition.warningbox = warningbox

        self.gpetable.show()

    def _render_type_name(self, celllayout, cell, model, tree_iter):
        ''' Render function called when partition type changes.
        '''
        text = model.get(tree_iter, 0)

        if text is None:
            return

        cell.set_data("text", text)


class UIDisk(object):
    ''' Class for representing a disk within the GPTPanel.

        This is mainly a container for the UIPartition objects.

        APIs:
            from solaris_install.gui_install.gpd_panel import UIDisk

            ui_disk = UIDisk(disk)
            num_partitions = ui_disk.num_parts
            ui_partition = ui_disk.ui_partitions[index]
    '''

    def __init__(self, disk, parent):
        ''' Initializer method, called from the constructor.

            Params:
            - disk, a Disk object, whose GPTPartition children will be used
              to populate a list of UIPartition objects.

            Returns: Nothing.
        '''
        self.parent = parent
        self.ui_partitions = list()
        self._disk = disk
        self.added_required_partitions = False

        # Remove any unused partitions so that contiguous gaps can be
        # collapsed into larger chunks
        for part in filter(lambda gpe: gpe.is_unused and \
                           gpe.action == "create",
                           disk.get_children(class_type=GPTPartition)):
            part.delete()

        self._add_holey_partitions()

        partitions = disk.get_children(class_type=GPTPartition)

        # sort the partitions by their location (ie. start_sector), not the
        # partition name, which doesn't affect on-disk ordering
        spartitions = sorted(partitions,
                             key=lambda part: part.start_sector)

        index = 0
        for index, partition in enumerate(spartitions):
            ui_partition = UIPartition(partition,
                index,
                self)
            self.ui_partitions.append(ui_partition)

        for ui_partition in self.ui_partitions:
            ui_partition.min_size = ui_partition.compute_min_size()
            ui_partition.max_size = ui_partition.compute_max_size()

    #--------------------------------------------------------------------------
    # Properties

    @property
    def num_parts(self):
        ''' Number of non-dummy and non-reserved partitions in this UIDisk.
        '''
        return len(self.ui_partitions)

    #--------------------------------------------------------------------------
    # Private methods

    def _add_holey_partitions(self):
        ''' Create Unused, zero sized GPT partitions representing
            gaps (holey partitions) to self._disk, as necessary.

            If there are less than the allowed number of GPT
            partitions on the disk and there are unused gaps on the
            disk, then create new GPT partitions, of type UNUSED
            to occupy those gaps.

            (Any of these UNUSED partitions added here, which the user
            does not change to a proper type, will be removed later
            when finalize() is called.)
        '''
        partitions = self._disk.get_children(class_type=GPTPartition)
        upartitions = [p for p in partitions \
                       if not (int(p.name) > efi_const.EFI_NUMUSERPAR and \
                               p.is_reserved)]
        # Don't offer any more partition slots even if space is available,
        # if there are already more than the supported number of partitions
        # defined.
        missing_parts = efi_const.EFI_NUMUSERPAR - len(upartitions)
        if missing_parts > 0:
            # sort disk gaps by location
            for gap in sorted(self._disk.get_gaps(),
                              key=lambda gap: gap.start_sector):
                if missing_parts == 0:
                    break

                if gap.size < MIN_USABLE_SIZE:
                    continue

                new_name = self._disk.get_next_partition_name()
                if new_name is None:
                    raise RuntimeError("INTERNAL ERROR - cannot get free GPT "
                                       "partition name")

                self._disk.add_gptpartition(str(new_name),
                    gap.start_sector, gap.size.sectors,
                    size_units=Size.sector_units,
                    partition_type=efi_const.EFI_UNUSED)

                missing_parts -= 1

    def __repr__(self):
        ''' String representation of object, for debugging and logging.
        '''

        ret_str = "[UIDisk: "
        if self._disk is None:
            ret_str += "<NO DISK>"
        else:
            ret_str += str(self._disk)
        ret_str += "\n"

        for ui_partition in self.ui_partitions:
            ret_str += "%s\n" % ui_partition

        ret_str += "\n]"

        return ret_str


class UIPartition(object):
    ''' Class representing a single GPT partition row within a GPTPanel.
    '''

    def __init__(self, partition, index, parent):
        ''' Initializer method - called form constructor.

            Parameters:
            - partition, the GPTPartition object that this UIPartition
              represents, or None, if this is to be a 'dummy' UIPartition.
            - index the zero based index of this partition within the
              GPTPartition table
            - parent, the parent UIDisk object
        '''

        self.partition = partition
        self.index = index
        self.parent = parent

        if self.partition is None:
            self.guid = efi_const.EFI_UNUSED
            self.is_size_editable = False
            self.is_type_editable = False
            self.display_size = ZERO_SIZE
            self._data_loss_warn = False
        else:
            self.guid = self.partition.guid
            if self.guid in GPTPanel.resizable_types:
                self.is_size_editable = True
            else:
                self.is_size_editable = False
            if self.partition.is_reserved:
                self.is_type_editable = False
            else:
                self.is_type_editable = True
            if self.partition.is_unused:
                self.display_size = ZERO_SIZE
            else:
                self.display_size = copy(self.partition.size)

            # Show data loss warning if any changes have been made.
            # We use the partition action to deduce if any changes have
            # been made.  Initially, TD will set action="preserve" for
            # all partitions.  Any changes made (resize, change_type)
            # result in the partition being deleted and recreated, with
            # action="create".  So, any action other than preserve means
            # changes have been made.
            if self.partition.action == PARTITION_ACTION_PRESERVE:
                self._data_loss_warn = False
            else:
                self._data_loss_warn = True

        # Identify what would appear to be the desired installation target
        # partition, even if it's not currently big enough.
        if self.partition.is_solaris and \
            self.partition.in_zpool == DEFAULT_ZPOOL_NAME:
            self.is_install_target = True
        else:
            self.is_install_target = False

        # These attributes cannot be computed until all of the
        # UIPartitions for the parent have been instantiated
        self.min_size = None
        self.max_size = None

        # These widget reference attributes are only set later
        # when this UIPartition is displayed
        self.typecombo = None
        self.sizespinner = None
        self.availlabel = None
        self.warningbox = None

    #--------------------------------------------------------------------------
    # Properties

    @property
    def allowed_types(self):
        ''' Returns a tuple (of GUIDS) containing the partition type GUIDS
            that this partition may be changed to.
        '''
        # Always show at least the UNUSED type, even for dummy UIPartitions
        if self.partition is None:
            types_list = [efi_const.EFI_UNUSED]
        else:
            # All non-dummy UIPartitions can be set to Solaris or the
            # appropriate boot partition (EFI System or BIOS boot) for
            # the system firmware type, or left preserved if it's not
            # an allowed type (for creation)
            types_list = list(self.parent.parent.allowed_types)
            if self.partition.guid is not None and \
                self.partition.guid not in self.parent.parent.allowed_types:
                types_list.append(self.partition.guid)

        return tuple(types_list)

    @property
    def data_loss_warn(self):
        ''' Returns True if a data loss warning should be displayed next
            to the partition
        '''
        if self.is_install_target or self._data_loss_warn:
            return True
        return False

    @property
    def is_install_target(self):
        ''' Returns True if this is the selected partition for Solaris
            installation. Returns False otherwise
        '''
        return self._is_install_target

    @is_install_target.setter
    def is_install_target(self, value):
        ''' Sets the is_install_target property to value (True or False)
            Raises a ValueError if caller attempts to set this property
            on a non-Solaris partition to True
        '''
        if value:
            if self.partition.is_solaris is False:
                raise ValueError("Setting a non-Solaris GPT partition as " \
                                   "the installation target is not allowed")
            self.partition.in_vdev = DEFAULT_VDEV_NAME
            self.partition.in_zpool = DEFAULT_ZPOOL_NAME
            self._is_install_target = True
        else:
            self.partition.in_vdev = None
            self.partition.in_zpool = None
            self._is_install_target = False

    @property
    def is_viable_target(self):
        ''' Returns True if the partition associated with this object is
            a viable target for Solaris installation. Returns False otherwise.
        '''
        if self.partition.is_solaris and \
            self.partition.size >= \
                self.parent.parent._target_controller.minimum_target_size:
            return True
        return False

    #--------------------------------------------------------------------------
    # API methods

    def compute_min_size(self):
        ''' The minimum size that this UIPartition can currently
            shrink to.

            This should only be called after all the UIPartitions
            within a GPTPanel have been instantiated, as it needs
            to access other UIPartitions.
        '''
        if self.partition is None:
            return ZERO_SIZE

        if self.partition.guid == efi_const.EFI_UNUSED:
            return ZERO_SIZE

        if self.partition.is_solaris:
            # Minimum size that partitions are not allowed to shrink below
            return MIN_USABLE_SIZE

        # For unsupported types or boot partitions, just return current size
        return self.partition.size

    def compute_max_size(self):
        ''' The maximum size that this UIPartition can currently
            grow to (ie the available space).

            This should only be called after all the UIPartitions
            within a GPTPanel have been instantiated, as it needs
            to access the other partitions.

            The value is computed as follows:
            - the current size of the partition
              + any 'gap' on the disk immediately after the partition
              + any 'gap' on the disk immediately before the partition
              + the size of the proceding partition, if it's UNUSED
              + the size of the preceding partition, if it's UNUSED
        '''
        if self.partition is None:
            return ZERO_SIZE

        # Keep a running total of how much space if available.  Do
        # all calculations in sectors for convenience
        sectors = self.partition.size.sectors

        if self.partition.parent is None:
            LOGGER.warn("Computing max_size for orphan GPT partition %s" % \
                self)
            return Size(str(sectors) + Size.sector_units)

        if self.partition.guid not in GPTPanel.resizable_types:
            # For non resizable types, return the current size so as not to
            # imply that they can be resized
            return Size(str(sectors) + Size.sector_units)

        gap = self.partition.get_gap_after()
        if gap is not None:
            sectors += gap.size.sectors

        gap = self.partition.get_gap_before()
        if gap is not None:
            sectors += gap.size.sectors

        next_ui_partition = self._get_next()
        if next_ui_partition is not None and \
            next_ui_partition.partition.guid == efi_const.EFI_UNUSED:

            sectors += next_ui_partition.partition.size.sectors

        prev_ui_partition = self._get_previous()
        if prev_ui_partition is not None and \
            prev_ui_partition.partition.guid == efi_const.EFI_UNUSED:

            sectors += prev_ui_partition.partition.size.sectors

        return Size(str(sectors) + Size.sector_units)

    def delete_gptpartition(self):
        ''' Delete the Partition associated with this UIPartition from
            its parent Disk.
        '''
        if self.partition is not None:
            disk = self.partition.parent
            if disk is not None:
                disk.delete_gptpartition(self.partition)

    def resize(self, new_size_val, size_units=Size.gb_units):
        '''Prepares the disk for a resize by getting unused partitions
           out of the way.
        '''
        # Delete adjacent UNUSED partitions
        next_ui_partition = self._get_next()
        if next_ui_partition is not None and \
            next_ui_partition.partition.guid == efi_const.EFI_UNUSED:
            next_ui_partition.delete_gptpartition()
        prev_ui_partition = self._get_previous()
        if prev_ui_partition is not None and \
            prev_ui_partition.partition.guid == efi_const.EFI_UNUSED:
            prev_ui_partition.delete_gptpartition()

        disk = self.partition.parent
        new_size = Size(str(new_size_val) + size_units,
            blocksize=disk.geometry.blocksize)

        round_err = Size(str(ACCEPTABLE_ROUNDING_ERR_GB) + str(Size.gb_units),
            blocksize=disk.geometry.blocksize)

        # Sanity check to make sure that the new_size_val isn't attempting
        # to exceed the computed maximum size for the partition.
        # If we are only slightly over, then assume this is just a rounding
        # error and resize to the max available
        if new_size.sectors < self.max_size.sectors + round_err.sectors:
            if new_size.sectors < self.max_size.sectors:
                resized_part = disk.resize_gptpartition(self.partition,
                    new_size.sectors,
                    size_units=Size.sector_units)
            else:
                resized_part = disk.resize_gptpartition(self.partition,
                    self.max_size.sectors,
                    size_units=Size.sector_units)
            return resized_part
        else:
            raise RuntimeError("Unable to resize partition: requested "
                                 "%ld sectors exceeds maximum of %ld" % \
                                 (new_size.sectors, self.max_size.sectors))

    def remove_guid_from_combo_model(self, model, path, iiter, guid):
        ''' Helper method to remove the row from gtk.TreeModel iter
            containing the guid value
        '''
        if model.get_value(iiter, 1) == guid:
            model.remove(iiter)
            return True
        return False

    def set_guid_for_combo_model(self, model, path, iiter, guid):
        ''' Helper method to set the active row iter in the combobox
            containing the guid value
        '''
        if model.get_value(iiter, 1) == guid:
            self.typecombo.set_active_iter(iiter)
            return True
        return False

    #--------------------------------------------------------------------------
    # Private methods

    def _get_previous(self):
        ''' Returns the first UIPartition before the current object.

            If the current UIPartition is logical, then the previous logical
            UIPartition is returned; if not, the previous non-logical
            UIPartition is returned.

            If no suitable UIPartition is found, None is returned.
        '''
        prev_pos = self.index - 1

        while prev_pos >= 0:
            prev = self.parent.ui_partitions[prev_pos]
            if prev.partition is not None:
                return prev
            prev_pos -= 1

        return None

    def _get_next(self):
        ''' Returns the first UIPartition after the current object.

            If no suitable UIPartition is found, None is returned.
        '''
        next_pos = self.index + 1

        while next_pos < self.parent.num_parts:
            next_part = self.parent.ui_partitions[next_pos]
            if next_part.partition is not None:
                return next_part
            next_pos += 1

        return None

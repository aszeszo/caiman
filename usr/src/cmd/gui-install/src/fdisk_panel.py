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
Panel for configuring fdisk partitions.

Classes:
    FdiskPanel
    UIDisk
    UIPartition
'''

import pygtk
pygtk.require('2.0')

from copy import copy
import locale
import logging

import gobject
import gtk

from solaris_install.gui_install.gui_install_common import \
    COLOR_WHITE, empty_container, modal_dialog, GLADE_ERROR_MSG
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import BadDiskError
from solaris_install.target.libadm.const import FD_NUMPART, MAX_EXT_PARTS
from solaris_install.target.libdiskmgt import const as diskmgt_const
from solaris_install.target.physical import Partition
from solaris_install.target.shadow.physical import LOGICAL_ADJUSTMENT
from solaris_install.target.size import Size


# These are the only Partition types this module knows about.
# Any other partitions discovered on the disk will be displayed,
# but cannot be modified unless they are changed to one of these
# types first.
PARTITION_TYPE_UNUSED = Partition.name_to_num("Empty")
PARTITION_TYPE_SOLARIS2 = Partition.name_to_num("Solaris2")
PARTITION_TYPE_EXTENDED = Partition.name_to_num("DOS Extended")
# Use our partition names in preference to the libdiskmgt ones.
ALL_PARTITION_NAMES = {
    PARTITION_TYPE_UNUSED: _("Unused"),
    PARTITION_TYPE_SOLARIS2: _("Solaris2"),
    PARTITION_TYPE_EXTENDED: _("Extended"),
}
# The position within the ComboBox selection list for each type
ALL_PARTITION_POSITIONS = {
    PARTITION_TYPE_UNUSED: 0,
    PARTITION_TYPE_SOLARIS2: 1,
    PARTITION_TYPE_EXTENDED: 2,
}

PARTITION_ACTION_PRESERVE = "preserve"

# Minimum usable partition size, (just under) 0.1 GB
MIN_USABLE_SIZE = Size("0.09" + Size.gb_units)
# Maximum acceptable rounding error, (just over) 0.1 GB
ACCEPABLE_ROUNDING_ERR = Size("0.11" + Size.gb_units)
ZERO_SIZE = Size("0" + Size.byte_units)

LOGGER = None


class FdiskPanel(object):
    '''
        Controls the creation, display and user interaction with the
        Fdisk partitioning table on the DiskScreen.

        APIs:
            from solaris_install.gui_install.fdisk_panel import FdiskPanel

            fdisk_panel = FdiskPanel(gtk_builder)
            fdisk_panel.hide()
            fdisk_panel.display(disk, target_controller)
            fdisk_panel.finalize()
    '''

    #--------------------------------------------------------------------------
    # API methods

    def __init__(self, builder):
        ''' Initializer method. Called from the constructor.

            Params:
            - builder, a GtkBuilder object used to retrieve widgets
              from the Glade XML files

            Returns: nothing
        '''

        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        self._disk = None
        self._ui_disk = None
        self._target_controller = None
        self._signal_widgets = dict()

        # Widgets from the Glade XML files that are referenced in this class
        self._custompartioningalignment = \
            builder.get_object("custompartioningalignment")
        self._custompartitioningvbox = \
            builder.get_object("custompartitioningvbox")
        self._partinfomessagesvbox = \
            builder.get_object("partinfomessagesvbox")
        self._unreadablepartsouterhbox = \
            builder.get_object("unreadablepartsouterhbox")
        self._partsfoundlabel = builder.get_object("partsfoundlabel")
        self._custominfolabel = builder.get_object("custominfolabel")
        self._fdiskscrolledwindow = \
            builder.get_object("fdiskscrolledwindow")
        self._fdiskviewport = builder.get_object("fdiskviewport")
        self._fdisktable = builder.get_object("fdisktable")
        self._partitiontypelabel = \
            builder.get_object("partitiontypelabel")
        self._partitionsizelabel = \
            builder.get_object("partitionsizelabel")
        self._partitionavillabel = \
            builder.get_object("partitionavaillabel")
        self._fdiskresetbutton = builder.get_object("fdiskresetbutton")

        if None in [self._custompartioningalignment,
            self._custompartitioningvbox, self._partinfomessagesvbox,
            self._unreadablepartsouterhbox, self._partsfoundlabel,
            self._custominfolabel, self._fdiskscrolledwindow,
            self._fdiskviewport, self._fdisktable, self._partitiontypelabel,
            self._partitionsizelabel, self._partitionavillabel,
            self._fdiskresetbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        # Initially hide all the widgets and empty any widgets that
        # may have been in the fdisktable, which will be dynamically
        # populated when we display.
        self._custompartioningalignment.hide_all()
        empty_container(self._fdisktable)

    def hide(self):
        ''' Hide the entire panel.

            Returns: nothing
        '''

        self._custompartioningalignment.hide()

    def display(self, disk, target_controller):
        ''' Show the custom fdisk partitioning panel for the given Disk.

            Params:
            - disk, the Disk object that is being displayed/modified
            - target_controller, the TargetController object used to
              refetch the disk's previous layout, if Reset is pressed.

            Returns: nothing
        '''

        self._disk = disk
        self._target_controller = target_controller

        # Setting _ui_disk to None forces a complete redraw
        self._ui_disk = None
        self._update()

        self._custompartioningalignment.show()
        self._custompartitioningvbox.show()

        # Show the appropriate messages
        self._partinfomessagesvbox.show()
        self._unreadablepartsouterhbox.hide()
        self._partsfoundlabel.show()
        self._custominfolabel.show()

        self._fdiskscrolledwindow.show()
        self._fdiskviewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self._fdiskviewport.show()

    def finalize(self):
        ''' Tidies up the currently selected disk, so that it is
            ready for validation.

            1. As the user edited the disk, "Empty" partitions may have
            been temporarily added to represent the available space that
            could be used to create new partitions.
            We must now remove these "Empty" partitions before proceeding.

            2. Resulting from the above, the partition names may no
            longer begin at the lowest available names (eg our first
            partition may be "2" instead of "1").  We must shuffle the
            partition names up.  Otherwise, there can be problems with
            installgrub & co later.

            Returns: nothing
        '''

        if self._disk is None:
            return

        LOGGER.debug("Disk layout before tidy up:\n%s" % self._disk)

        # Delete "Empty" partitions
        partitions = self._disk.get_children(class_type=Partition)
        for part in partitions:
            if part.action == "create" and \
                part.part_type == Partition.name_to_num("Empty"):
                LOGGER.debug("Deleting partition %s" % part.name)
                self._disk.delete_partition(part)

        # Shuffle up the partition names so that they occupy the lowest
        # available names.
        partitions = self._disk.get_children(class_type=Partition)
        for part in sorted(partitions, key=lambda p: int(p.name)):
            if part.action != "create":
                continue

            if part.is_logical:
                lowest_available_name = self._disk.get_next_partition_name(
                    primary=False)
            else:
                lowest_available_name = self._disk.get_next_partition_name(
                    primary=True)

            if lowest_available_name is not None:
                if int(part.name) > int(lowest_available_name):
                    LOGGER.debug("Renaming partition %s to %s" % \
                        (part.name, lowest_available_name))

                    # We can't just change the partition name - we must
                    # add a new one and delete the old one.
                    self._disk.add_partition(lowest_available_name,
                        part.start_sector, part.size.sectors,
                        size_units=Size.sector_units,
                        partition_type=part.part_type,
                        bootid=part.bootid,
                        in_zpool=part.in_zpool,
                        in_vdev=part.in_vdev)

                    self._disk.delete_partition(part)

        LOGGER.info("Disk layout after tidy up:\n%s" % self._disk)

    #--------------------------------------------------------------------------
    # Signal handler methods

    def reset_button_clicked(self, widget, user_data=None):
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

        # Set _ui_disk to None to force a complete redraw
        self._ui_disk = None
        self._update()

    def type_changed(self, widget, index):
        ''' Signal handler for when the partition type ComboBoxes
            receive a "changed" signal.
        '''

        try:
            ui_partition = self._ui_disk.ui_partitions[index]
        except IndexError:
            raise RuntimeError("INTERNAL ERROR: try to change type for "
                               "non-existant partition %d" % index)

        new_type_index = widget.get_active()

        if new_type_index == -1:
            raise RuntimeError("INTERNAL ERROR: try to unset type for "
                               "partition [%s]" % ui_partition)
        elif new_type_index == 0:
            new_type = PARTITION_TYPE_UNUSED
        elif new_type_index == 1:
            new_type = PARTITION_TYPE_SOLARIS2
        elif new_type_index == 2:
            new_type = PARTITION_TYPE_EXTENDED

            # Ensure there is only one EXTENDED at a time
            for temp in self._ui_disk.ui_partitions:
                if temp.is_extended:
                    modal_dialog(
                        _("Only one extended partition can exist."),
                        _("Choose another type."))
                    if ui_partition.part_type == PARTITION_TYPE_UNUSED:
                        old_index = 0
                    elif ui_partition.part_type == PARTITION_TYPE_SOLARIS2:
                        old_index = 1
                    # Can't be PARTITION_TYPE_EXTENDED, must be 'other'
                    else:
                        old_index = 3
                    # Revert to previous type silently
                    widget.handler_block_by_func(self.type_changed)
                    widget.set_active(old_index)
                    widget.handler_unblock_by_func(self.type_changed)
                    return
        else:
            raise RuntimeError("INTERNAL ERROR: try to change type to "
                               "invalid value [%s]" % new_type_index)

        ui_partition.change_type(new_type)

        self._update()

    def size_value_changed(self, widget, index):
        ''' Signal handler for when the partition size SpinButtons
            receive a "value_changed" signal.
        '''

        try:
            ui_partition = self._ui_disk.ui_partitions[index]
        except IndexError:
            raise RuntimeError("INTERNAL ERROR: try to resize non-existant "
                               "partition %d" % index)

        new_size = widget.get_value()

        ui_partition.resize(new_size, size_units=Size.gb_units)

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

    def render_partitiontype_name(self, celllayout, cell, model, tree_iter):
        ''' Render function called when partition type changes.
        '''
        text = model.get(tree_iter, 0)

        if text is None:
            return

        gobject.GObject.set_data(cell, "text", text)

    #--------------------------------------------------------------------------
    # Private methods

    def _update(self):
        ''' re-fetch all the details for the currently selected disk
            and redraw fdisktable to reflect the new details.
        '''

        new_ui_disk = UIDisk(self._disk)

        if self._need_complete_redraw(new_ui_disk):
            self._complete_redraw(new_ui_disk)
        else:
            self._selective_redraw(new_ui_disk)

        self._ui_disk = new_ui_disk

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

        for old_part, new_part in zip(self._ui_disk.ui_partitions,
                                      new_ui_disk.ui_partitions):
            old_is_dummy = old_part.partition is None
            new_is_dummy = new_part.partition is None
            if old_is_dummy != new_is_dummy:
                # A row of the panel occupied by a real partition is
                # now occupied by a dummy, or vice versa
                return True

            if old_part.is_logical != new_part.is_logical:
                # A row of the panel occupied by a logical partition is
                # now occupied by a primary, or vice versa
                return True

        # Other changes to size or type that do not induce significant
        # changes (such as creating or removing a partition) don't need
        # a full redraw
        return False

    def _complete_redraw(self, new_ui_disk):
        ''' Remove all the widgets inside fdisktable; re-create a new
            set of widgets for the the new disk details and display them.
        '''

        self._disconnect_all_handlers()

        self._empty_table()

        # The number of rows needed for fdisktable is the number
        # of partitions (primary, logical and dummy) plus two (for
        # titles and reset button).
        # The number of columns is always 4.
        self._fdisktable.resize(new_ui_disk.num_parts + 2, 4)

        index = 0

        self._add_titles_to_table(index)
        index += 1

        for ui_partition in new_ui_disk.ui_partitions:
            self._add_partition_to_table(index, ui_partition)
            index += 1

        self._add_footer_to_table(index)

        self._fdisktable.show()

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

            if old.part_type != new.part_type:
                # If the partition type has changed, we may also need to
                # - re-do the list of partition types for the
                #   ComboBox and reset the active selection
                # - update the value of the size SpinButton
                # - update the sensitivity of the size SpinButton

                if old.part_type not in ALL_PARTITION_NAMES:
                    # The user changed from an unsupported type to one
                    # of the supported types.  We re-do the list of
                    # allowed partition types, which will have the
                    # effect of removing the unsupported type
                    partitiontype_store = gtk.ListStore(gobject.TYPE_STRING)
                    types_list = new.allowed_types
                    for part_type in types_list:
                        tree_iter = partitiontype_store.append()
                        partitiontype_store.set(tree_iter, 0, part_type)
                    old.typecombo.set_model(partitiontype_store)
                    old.typecombo.set_active(new.type_index)

                # The display size value may have changed as it can be
                # 0 or the real value depending on the partition type
                old_display_in_gb = round(
                    old.display_size.get(units=Size.gb_units), 1)
                new_display_in_gb = round(
                    new.display_size.get(units=Size.gb_units), 1)
                if new_display_in_gb != old_display_in_gb:
                    old.sizespinner.set_value(new_display_in_gb)

                # The sensitivty of the Size SpinButton may have changed
                # as only SOLARIS2 and EXTENDED partitions can be
                # explicitly resized
                if new.is_size_editable != old.is_size_editable:
                    old.sizespinner.set_sensitive(new.is_size_editable)

            if old.data_loss_warn != new.data_loss_warn:
                # If the data_loss_warn flag has changed, we need to show
                # or hide the warnings, as appropriate
                if new.data_loss_warn:
                    old.warningbox.show()
                else:
                    old.warningbox.hide()

        for row in range(self._ui_disk.num_parts):
            # As we are not recreating the widgets, we need to save
            # the references to them in new_ui_disk for the next time
            # round
            old = self._ui_disk.ui_partitions[row]
            new = new_ui_disk.ui_partitions[row]

            new.typecombo = old.typecombo
            new.sizespinner = old.sizespinner
            new.availlabel = old.availlabel
            new.warningbox = old.warningbox

        # Re-enable signal handlers
        self._unblock_all_handlers()

    def _empty_table(self):
        ''' Empty the contents of fdisktable.

            The non-dynamically created widgets (the titles in the first
            row and the reset button in the last row) are just removed,
            as they need to be accessed again when the table is redrawn.
            All the other widgets (those in the inner rows) are also
            destroyed to free up resources.
        '''

        for child in self._fdisktable.get_children():
            top_attach = self._fdisktable.child_get_property(child,
                "top-attach")

            self._fdisktable.remove(child)

            if self._ui_disk is not None and \
                1 <= top_attach <= self._ui_disk.num_parts:
                child.destroy()

    def _add_titles_to_table(self, row):
        ''' Add the three column headers to fdisktable.
        '''

        self._fdisktable.attach(self._partitiontypelabel,
            0, 1, row, row + 1, gtk.FILL, gtk.FILL)

        self._fdisktable.attach(self._partitionsizelabel,
            1, 2, row, row + 1, gtk.FILL, gtk.FILL)

        self._fdisktable.attach(self._partitionavillabel,
            2, 3, row, row + 1, gtk.FILL, gtk.FILL)

        self._partitiontypelabel.show()
        self._partitionsizelabel.show()
        self._partitionavillabel.show()

    def _add_footer_to_table(self, row):
        ''' Add the reset button to fdisktable.
        '''

        self._fdisktable.attach(self._fdiskresetbutton,
            1, 2, row, row + 1, gtk.FILL, gtk.FILL)

        self._fdiskresetbutton.show_all()

    def _add_partition_to_table(self, row, ui_partition):
        ''' Dynamically create all the widgets needed to display
            a partition and add them to fdisktable.

            Params:
            - row, the row number in fdisktable for this partition
            - ui_partition, a UIPartition object containing the row
              to be added.  ui_partition may represent a real
              Partition or may be one of the dummies used to show
              the full number of primaries that can be created.

            Returns: Nothing

            The following attributes of ui_partition will be set to
            references to the relevant newly created widgets, for
            later retrieval:
                ui_partition.typecombo
                ui_partition.sizespinner
                ui_partition.availlabel
                ui_partition.warningbox
        '''

        # partition type ComboBox
        #------------------------
        typealign = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
        # Indent logical partitions so they stand out
        if ui_partition.is_logical:
            indent = 12
        else:
            indent = 0
        typealign.set_padding(0, 0, indent, 0)
        typecombo = gtk.ComboBox()
        partitiontype_store = gtk.ListStore(gobject.TYPE_STRING)
        types_list = ui_partition.allowed_types
        for part_type in types_list:
            tree_iter = partitiontype_store.append()
            partitiontype_store.set(tree_iter, 0, part_type)
        typecombo.set_model(partitiontype_store)
        renderer = gtk.CellRendererText()
        typecombo.pack_start(renderer, expand=True)
        typecombo.set_attributes(renderer, text=0)
        typecombo.set_cell_data_func(renderer, self.render_partitiontype_name)
        typecombo.set_active(ui_partition.type_index)
        typecombo.set_sensitive(ui_partition.is_type_editable)
        typealign.add(typecombo)
        self._fdisktable.attach(typealign,
            0, 1, row, row + 1, gtk.FILL, gtk.FILL)
        typealign.show()
        typecombo.show()

        # partition size SpinButton
        #--------------------------
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
            LOGGER.warn("New partition size (%6.2f) is below " \
                "computed minimum (%6.2f). Adjusting." % \
                (display_size_in_gb, min_size_in_gb))
            display_size_in_gb = min_size_in_gb
        if display_size_in_gb > max_size_in_gb:
            LOGGER.warn("New partition size (%6.2f) is above " \
                "computed amximum (%6.2f). Adjusting." % \
                (display_size_in_gb, max_size_in_gb))
            display_size_in_gb = max_size_in_gb

        sizespinner.set_range(min_size_in_gb, max_size_in_gb)
        sizespinner.set_value(display_size_in_gb)
        sizespinner.set_sensitive(ui_partition.is_size_editable)
        self._fdisktable.attach(sizespinner,
            1, 2, row, row + 1, gtk.FILL, gtk.FILL)
        sizespinner.show_all()

        # available space Label
        #----------------------
        availlabel = gtk.Label(locale.str(max_size_in_gb))
        availlabel.set_justify(gtk.JUSTIFY_RIGHT)
        availlabel.set_alignment(0.0, 0.5)
        self._fdisktable.attach(availlabel,
            2, 3, row, row + 1, gtk.FILL, gtk.FILL)
        availlabel.show()

        # warning Image/Label
        #--------------------
        warningbox = gtk.HBox(homogeneous=False, spacing=5)
        warningimage = gtk.image_new_from_stock(
            gtk.STOCK_DIALOG_WARNING,
            gtk.ICON_SIZE_MENU)
        warninglabel = gtk.Label(_('<span size="smaller"><span '
            'font_desc="Bold">Warning: </span> The data in this '
            'partition will be erased.</span>'))
        warninglabel.set_use_markup(True)
        warningbox.pack_start(warningimage, expand=False,
            fill=False, padding=0)
        warningbox.pack_start(warninglabel, expand=False,
            fill=False, padding=0)
        self._fdisktable.attach(warningbox,
            3, 4, row, row + 1, gtk.FILL, gtk.FILL)
        warningimage.show()
        warninglabel.show()
        if ui_partition.data_loss_warn:
            warningbox.show()
        else:
            warningbox.hide()

        # Connect (and immediately, temporarily, block) signal handlers
        handler_id = gobject.GObject.connect(typecombo,
                                             "changed",
                                             self.type_changed,
                                             ui_partition.row)
        self._signal_widgets[handler_id] = typecombo
        gobject.GObject.handler_block(self._signal_widgets[handler_id],
                                      handler_id)

        handler_id = gobject.GObject.connect(sizespinner,
                                             "value_changed",
                                             self.size_value_changed,
                                             ui_partition.row)
        self._signal_widgets[handler_id] = sizespinner
        gobject.GObject.handler_block(self._signal_widgets[handler_id],
                                      handler_id)

        handler_id = gobject.GObject.connect(sizespinner,
                                             "insert-text",
                                             self.size_insert_text,
                                             ui_partition.row)
        self._signal_widgets[handler_id] = sizespinner
        gobject.GObject.handler_block(self._signal_widgets[handler_id],
                                      handler_id)

        handler_id = gobject.GObject.connect(sizespinner,
                                             "delete-text",
                                             self.size_delete_text,
                                             ui_partition.row)
        self._signal_widgets[handler_id] = sizespinner
        gobject.GObject.handler_block(self._signal_widgets[handler_id],
                                      handler_id)

        # Save references to the widgets that we may need to update
        # directly later on
        ui_partition.typecombo = typecombo
        ui_partition.sizespinner = sizespinner
        ui_partition.availlabel = availlabel
        ui_partition.warningbox = warningbox

        self._fdisktable.show()

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


class UIDisk(object):
    ''' Class for representing a disk within the FdiskPanel.

        This is mainly a container for the UIPartition objects.

        APIs:
            from solaris_install.gui_install.fdisk_panel import UIDisk

            ui_disk = UIDisk(disk)
            num_partitions = ui_disk.num_parts
            ui_partition = ui_disk.ui_partitions[index]
    '''

    #--------------------------------------------------------------------------
    # API methods

    def __init__(self, disk):
        ''' Initializer method, called from the constructor.

            Params:
            - disk, a Disk object, whose Partition children will be used
              to populate a list of UIPartition objects.

            Returns: Nothing.
        '''

        self.ui_partitions = list()

        self._disk = disk

        self._add_unused_partitions()

        # Populate self.ui_partitions with the Partition
        # children of disk
        primaries = disk.primary_partitions
        row = 0
        # sort the partitions by their location (ie start_sector),
        # (not the partition name, which doesn't affect on-disk ordering)
        for partition in sorted(primaries,
                                key=lambda part: part.start_sector):
            ui_partition = UIPartition(partition, row, self)
            row += 1
            self.ui_partitions.append(ui_partition)

            if partition.is_extended:
                # There can only be one Extended partition per disk, so
                # any logical partitions on the disk must belong to it
                logicals = disk.logical_partitions
                for logical in sorted(logicals,
                                      key=lambda part: part.start_sector):
                    ui_partition = UIPartition(logical, row, self)
                    row += 1
                    self.ui_partitions.append(ui_partition)

        # If there are less than the allowed number of primary
        # partitions, create dummy entries to show how many
        # primary partitions the user can create
        for index in range(len(primaries), FD_NUMPART):
            ui_partition = UIPartition(None, row, self)
            row += 1
            self.ui_partitions.append(ui_partition)

        # Compute the min and max space for each UIPartition.
        # This can only be done after all the UIPartitions have
        # been instantiated as it relies on accessing data from
        # the other UIPartitions.
        for ui_partition in self.ui_partitions:
            ui_partition.min_size = ui_partition.compute_min_size()
            ui_partition.max_size = ui_partition.compute_max_size()

    #--------------------------------------------------------------------------
    # Properties

    @property
    def num_parts(self):
        ''' Number for UIPartitions in this UIDisk.
        '''
        return len(self.ui_partitions)

    #--------------------------------------------------------------------------
    # Private methods

    def _add_unused_partitions(self):
        ''' Add UNUSED primary and logical partitions to self._disk,
            as necessary.

            If there are less than the allowed number of primary
            partitions on the disk and there are unused gaps on the
            disk, then create new primary partitions, of type UNUSED
            to occupy those gaps.

            If there is an EXTENDED partition and there are unused
            gaps within that partition, then create new logical
            partitions, of type UNUSED, to occupy those gaps, up
            to max allowed number of logicals.

            (Any of these UNUSED partitions added here, which the user
            does not change to a proper type, will be removed later
            when finalize() is called.)
        '''

        primaries = self._disk.primary_partitions

        missing_primaries = FD_NUMPART - len(primaries)
        if missing_primaries:
            # sort disk gaps by location
            for gap in sorted(self._disk.get_gaps(),
                              key=lambda gap: gap.start_sector):
                if missing_primaries == 0:
                    break

                if gap.size < MIN_USABLE_SIZE:
                    continue

                new_name = self._disk.get_next_partition_name(primary=True)
                if new_name is None:
                    raise RuntimeError("INTERNAL ERROR - cannot get "
                                       "free partition name")

                new_partition = self._disk.add_partition(str(new_name),
                    gap.start_sector, gap.size.sectors,
                    size_units=Size.sector_units,
                    partition_type=PARTITION_TYPE_UNUSED)

                missing_primaries -= 1

        for partition in primaries:
            if partition.is_extended:
                num_logicals = len(self._disk.logical_partitions)
                gaps = partition.parent.get_logical_partition_gaps()
                for gap in gaps:
                    if num_logicals >= MAX_EXT_PARTS:
                        break

                    if gap.size < MIN_USABLE_SIZE:
                        continue

                    new_name = self._disk.get_next_partition_name(
                        primary=False)
                    if new_name is None:
                        raise RuntimeError("INTERNAL ERROR - cannot get "
                                           "free logical partition name")

                    new_partition = self._disk.add_partition(str(new_name),
                        gap.start_sector,
                        gap.size.sectors,
                        size_units=Size.sector_units,
                        partition_type=PARTITION_TYPE_UNUSED)

                    num_logicals += 1

                break

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
    ''' Class representing a single partition row within a UIDisk.

        APIs:
            from solaris_install.gui_install.fdisk_panel import UIPartition

            ui_partition = UIPartition(partition, row, ui_disk)

            ui_partition.resize(size_value, units=Size.gb_units)
            ui_partition.change_type(type)
            ui_partition.compute_min_size()
            ui_partition.compute_max_size()
            ui_partition.delete_partition()

            ui_partition.partition          # Partition object or None
            ui_partition.row                # int
            ui_partition.parent             # UIDisk object
            ui_partition.part_type          # int
            ui_partition.is_logical         # Boolean
            ui_partition.is_extended        # Boolean
            ui_partition.is_size_editable   # Boolean
            ui_partition.is_type_editable   # Boolean
            ui_partition.display_size       # Size object
            ui_partition.data_loss_warn     # Boolean
            ui_partition.allowed_types      # list of strings
            ui_partition.type_index         # int
            ui_partition.min_size           # Size object
            ui_partition.max_size           # Size object
            # Gtk+ widgets:
            ui_partition.typealign          # gtk.Alignment
            ui_partition.typecombo          # gtk.ComboBox
            ui_partition.sizespinner        # gtk.SpinButton
            ui_partition.availlabel         # gtk.Label
            ui_partition.warningbox         # gtk.HBox
    '''

    #--------------------------------------------------------------------------
    # API methods

    def __init__(self, partition, row, parent):
        ''' Initializer method - called form constructor.

            Params:
            - partition, the Partition object that this UIPartition
              represents, or None, if this is to be a 'dummy' UIPartition.
            - row, the position of this UIPartition within the parent
              UIDisk's ui_partition list
            - parent, the UIDisk parent object
        '''

        self.partition = partition
        self.row = row
        self.parent = parent

        if self.partition is None:
            self.part_type = PARTITION_TYPE_UNUSED
            self.is_logical = False
            self.is_extended = False
            self.is_size_editable = False
            self.is_type_editable = False
            self.display_size = ZERO_SIZE
            self.data_loss_warn = False
        else:
            self.part_type = self.partition.part_type
            self.is_logical = self.partition.is_logical
            self.is_extended = self.partition.is_extended
            if self.part_type in \
                [PARTITION_TYPE_SOLARIS2, PARTITION_TYPE_EXTENDED]:
                self.is_size_editable = True
            else:
                self.is_size_editable = False
            self.is_type_editable = True
            if self.part_type == PARTITION_TYPE_UNUSED:
                self.display_size = ZERO_SIZE
            else:
                self.display_size = copy(self.partition.size)
            if self.part_type == PARTITION_TYPE_SOLARIS2:
                # Always show data loss warning for Solaris2 partitions
                self.data_loss_warn = True
            else:
                # Show data loss warning if any changes have been made.
                # We use the partition action to deduce if any changes have
                # been made.  Initially, TD will set action="preserve" for
                # all partitions.  Any changes made (resize, change_type)
                # result in the partition being deleted and recreated, with
                # action="create".  So, any action other than preserve means
                # changes have been made.
                if self.partition.action == PARTITION_ACTION_PRESERVE:
                    self.data_loss_warn = False
                else:
                    self.data_loss_warn = True

        # These attributes are slightly more complex to compute
        self.allowed_types = self._get_allowed_types()
        self.type_index = self._get_type_index()

        # These attributes cannot be computed until all of the
        # UIPartitions for the parent have been instantiated
        self.min_size = None
        self.max_size = None

        # These widget reference attributes are only set later
        # when this UIPartition is displayed
        self.typealign = None
        self.typecombo = None
        self.sizespinner = None
        self.availlabel = None
        self.warningbox = None

    #--------------------------------------------------------------------------
    # API methods

    def resize(self, new_size_val, size_units=Size.gb_units):
        ''' Resize the Partition associated with this UIPartition
            to the given size.

            Any UNUSED UIPartitions which might be affected by this
            resizing are simply deleted, which will result in them appearing
            as empty 'gaps' on the Disk.  These will be automatically
            recreated with the correct new size when the FdiskPanel is next
            redrawn, if there is still sufficient space for them.

            If the Partition's size is decreasing, we can now just
            resize it and return.

            If the size is increasing, we must figure out if it can retain its
            current start_sector and grow into what was the proceeding empty
            gap or UNUSED space, or if we must adjust the start_sector
            and grow into what was the preceeding empty gap or UNUSED
            space. The preference is to retain the current start_sector,
            if possible.

            If there is a small shortfall in the available space for the
            partition to grow into, this is assumed to be a rounding error,
            as the UI deals in units of 0.1 GB.  If the shortfall is any
            bigger, RuntimeError is raised - the calling code should
            prevent invalid resize requests being made.

            Params:
            - new_size_val, a floating point number for the new size
            - size_units, defaults to GB

            Returns: the new Partition object.  (Resizing a Partition
            involves deleting the old object and creating a new one.)
            Note: the new, resized partition will not have any Slice
            children that were present before resizing. So these must
            be re-created, if needed.

            Raises: RuntimeError
        '''

        if self.partition is None:
            raise RuntimeError("INTERNAL ERROR - try to resize dummy "
                               "partition [%s]" % self)

        # Delete adjacent UNUSED partitions
        next_ui_partition = self._get_next()
        if next_ui_partition is not None and \
            next_ui_partition.part_type == PARTITION_TYPE_UNUSED:
            next_ui_partition.delete_partition()
        prev_ui_partition = self._get_previous()
        if prev_ui_partition is not None and \
            prev_ui_partition.part_type == PARTITION_TYPE_UNUSED:
            prev_ui_partition.delete_partition()

        if self.is_extended:
            # Delete UNUSED logical partitions within this EXTENDED partition
            for ui_partition in self.parent.ui_partitions:
                if ui_partition.is_logical and \
                    ui_partition.part_type == PARTITION_TYPE_UNUSED:
                    ui_partition.delete_partition()

        new_size = Size(str(new_size_val) + size_units)

        if self.partition.size >= new_size:
            # Short-circuit for the simple case where the size is
            # decreasing - just resize it and return
            new_partition = self.partition.resize(new_size.sectors,
                size_units=Size.sector_units)
            return new_partition

        # Keep track of how much space is available to us and of
        # the highest end sector we can increase to
        sectors_available = self.partition.size.sectors
        highest_end_sector = self.partition.start_sector + \
            self.partition.size.sectors

        gap_after = self._get_gap_after()
        if gap_after is not None:
            sectors_available += gap_after.size.sectors
            highest_end_sector = gap_after.start_sector + \
                                 gap_after.size.sectors

        if new_size.sectors <= sectors_available:
            # There is enough free space after the partition to grow into,
            # so we don't need to adjust the start_sector
            new_partition = self.partition.resize(new_size.sectors,
                size_units=Size.sector_units)
            return new_partition

        gap_before = self._get_gap_before()
        if gap_before is not None:
            sectors_available += gap_before.size.sectors

        if new_size.sectors <= sectors_available:
            new_partition = self.partition.resize(new_size.sectors,
                size_units=Size.sector_units,
                start_sector=highest_end_sector - \
                new_size.sectors)
            return new_partition

        # if we are only slightly short, then assume this
        # is just a rounding error and resize to the max available
        if new_size.sectors - sectors_available <= \
            ACCEPABLE_ROUNDING_ERR.sectors:

            new_partition = self.partition.resize(sectors_available,
                size_units=Size.sector_units,
                start_sector=highest_end_sector - sectors_available)
            return new_partition

        raise RuntimeError("Unable to resize partition: need "
                           "%ld sectors, only have %ld" % \
                           (new_size.sectors, sectors_available))

    def change_type(self, new_type):
        ''' Change the type of the Partition associated with this
            UIPartition to the given type.

            Note: the new, resized partition will not have any Slice
            children that were present before resizing. So these must
            be re-created, if needed.
        '''

        if self.partition is None:
            raise RuntimeError("INTERNAL ERROR: try to change type for "
                               "dummy partition %s" % self)

        # If old type was EXTENDED, delete the logicals first
        disk = self.partition.parent
        if self.is_extended and disk is not None:
            # There can only be one Extended partition per disk, so
            # any logical partitions on the disk must belong to it
            for logical in disk.logical_partitions:
                disk.delete_partition(logical)

        self.partition.change_type(new_type)

    def compute_min_size(self):
        ''' The minimum size that this UIPartition can currently
            shrink to.

            This should only be called after all the UIPartitions
            within a UIDisk have been instantiated, as it needs
            to access other UIPartitions.
        '''

        if self.partition is None:
            return ZERO_SIZE

        if self.part_type == PARTITION_TYPE_UNUSED:
            return ZERO_SIZE

        if self.part_type == PARTITION_TYPE_SOLARIS2:
            # Minimum size that partitions are not allowed to shrink below
            return MIN_USABLE_SIZE

        if self.part_type == PARTITION_TYPE_EXTENDED:
            # Add up the sizes of the logicals (ignoring any UNUSED
            # logicals). Do all calculations in sectors for convenience
            sectors = 0
            for ui_partition in self.parent.ui_partitions:
                if ui_partition.is_logical and \
                    ui_partition.part_type != PARTITION_TYPE_UNUSED:
                    sectors += ui_partition.partition.size.sectors

            # Ensure returned value is at least the minimum size
            if sectors < MIN_USABLE_SIZE.sectors:
                return MIN_USABLE_SIZE

            return Size(str(sectors) + Size.sector_units)

        # For unsupported types, just return current size
        return self.partition.size

    def compute_max_size(self):
        ''' The maximum size that this UIPartition can currently
            grow to (ie the available space).

            This should only be called after all the UIPartitions
            within a UIDisk have been instantiated, as it needs
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
            LOGGER.warn("Computing max_size for orphan partition %s" % \
                self)
            return Size(str(sectors) + Size.sector_units)

        if self.part_type not in ALL_PARTITION_NAMES:
            # For unsupported types, return the current size so as not to
            # imply that they can be resized
            return Size(str(sectors) + Size.sector_units)

        gap = self._get_gap_after()
        if gap is not None:
            sectors += gap.size.sectors

        gap = self._get_gap_before()
        if gap is not None:
            sectors += gap.size.sectors

        next_ui_partition = self._get_next()
        if next_ui_partition is not None and \
            next_ui_partition.part_type == PARTITION_TYPE_UNUSED:

            sectors += next_ui_partition.partition.size.sectors

        prev_ui_partition = self._get_previous()
        if prev_ui_partition is not None and \
            prev_ui_partition.part_type == PARTITION_TYPE_UNUSED:

            sectors += prev_ui_partition.partition.size.sectors

        return Size(str(sectors) + Size.sector_units)

    def delete_partition(self):
        ''' Delete the Partition associated with this UIPartition from
            its parent Disk.
        '''

        if self.partition is not None:
            disk = self.partition.parent
            if disk is not None:
                disk.delete_partition(self.partition)

    #--------------------------------------------------------------------------
    # Private methods

    def _get_allowed_types(self):
        ''' Returns a list (of strings) containing the partition types
            that this partition may be changed to.
        '''

        # Always show at least the UNUSED type, even for dummy UIPartitions
        types_list = [ALL_PARTITION_NAMES[PARTITION_TYPE_UNUSED]]

        if self.partition is not None:
            # All non-dummy UIPartitions can be set to Solaris2
            types_list.append(ALL_PARTITION_NAMES[PARTITION_TYPE_SOLARIS2])

            if not self.is_logical:
                # Only Primary partitions can be set to Extended
                types_list.append(
                    ALL_PARTITION_NAMES[PARTITION_TYPE_EXTENDED])

            if self.part_type not in ALL_PARTITION_NAMES:
                # For unsupported types, try to retrieve the name from
                # libdiskmgt.  (This UIPartition's size will be read-only
                # unless it is first changed to a supported type.)
                try:
                    type_name = \
                        _(diskmgt_const.PARTITION_ID_MAP[self.part_type])
                except IndexError:
                    type_name = _("Unknown")
                types_list.append(type_name)

        return types_list

    def _get_type_index(self):
        ''' Returns the index within the allowed types of this
            object's type.
        '''

        if self.part_type in ALL_PARTITION_NAMES:
            return ALL_PARTITION_POSITIONS[self.part_type]

        # An unsupported type will always be the last option in the list
        return len(self._get_allowed_types()) - 1

    def _get_gap_before(self):
        ''' Returns the HoleyObject gap that occurs immediately before the
            current partition, or None if there isn't such a gap.

            If the current partition is logical, only logical gaps (gaps
            within an EXTENDED partition) are considered; otherwise, only
            Disk gaps (gaps between primary partitions (or slices)) are
            considered.
        '''

        if self.partition is not None and self.partition.parent is not None:
            if self.is_logical:
                gaps = self.partition.parent.get_logical_partition_gaps()
                adjacent_size = LOGICAL_ADJUSTMENT + 1
            else:
                gaps = self.partition.parent.get_gaps()
                adjacent_size = 1

            for gap in gaps:
                if abs(gap.start_sector + gap.size.sectors \
                       - self.partition.start_sector) <= adjacent_size:
                    return gap

        return None

    def _get_gap_after(self):
        ''' Returns the HoleyObject gap that occurs immediately after the
            current partition, or None if there isn't such a gap.

            If the current partition is logical, only logical gaps (gaps
            within an EXTENDED partition) are considered; otherwise, only
            Disk gaps (gaps between primary partitions (or slices)) are
            considered.
        '''

        if self.partition is not None and self.partition.parent is not None:
            if self.is_logical:
                gaps = self.partition.parent.get_logical_partition_gaps()
                adjacent_size = LOGICAL_ADJUSTMENT + 1
            else:
                gaps = self.partition.parent.get_gaps()
                adjacent_size = 1

            for gap in gaps:
                if abs(self.partition.start_sector + \
                    self.partition.size.sectors - gap.start_sector) <= \
                    adjacent_size:
                    return gap

        return None

    def _get_next(self):
        ''' Returns the first non-dummy UIPartition after the current object.

            If the current UIPartition is logical, then the next logical
            UIPartition is returned; if not, the next non-logical
            UIPartition is returned.

            If no suitable UIPartition is found, None is returned.
        '''

        next_pos = self.row + 1

        while next_pos < self.parent.num_parts:
            next_part = self.parent.ui_partitions[next_pos]
            if next_part.partition is not None and \
               next_part.is_logical == self.is_logical:
                return next_part
            next_pos += 1

        return None

    def _get_previous(self):
        ''' Returns the first non-dummy UIPartition before the current object.

            If the current UIPartition is logical, then the previous logical
            UIPartition is returned; if not, the previous non-logical
            UIPartition is returned.

            If no suitable UIPartition is found, None is returned.
        '''

        prev_pos = self.row - 1

        while prev_pos >= 0:
            prev = self.parent.ui_partitions[prev_pos]
            if prev.partition is not None and \
               prev.is_logical == self.is_logical:
                return prev
            prev_pos -= 1

        return None

    def __repr__(self):
        ''' String representation of object, for debugging and logging.
        '''

        ret_str = "[UIPartition: "

        if self.partition is None:
            ret_str += "Dummy "

            ret_str += "partition, pos %s: " % \
                (self.row)
        else:
            if self.is_logical:
                ret_str += "\t"

            ret_str += "Real (name=%s) (type=%s) " % \
                (self.partition.name, self.part_type)

            ret_str += "partition, pos %s, " % \
                (self.row)

            ret_str += "start %ld, end %ld, size %ld secs / %6.2f GB " % \
                (self.partition.start_sector,
                self.partition.start_sector + self.partition.size.sectors,
                self.partition.size.sectors,
                self.partition.size.get(units=Size.gb_units))

        ret_str += "]"

        return ret_str

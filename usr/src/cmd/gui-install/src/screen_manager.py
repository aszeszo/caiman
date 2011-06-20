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
Class for managing progression through the GUI Install's
different screens.
'''

import pygtk
pygtk.require('2.0')

import logging
from glib import GError
import gtk
import warnings

from solaris_install.gui_install.base_screen import NotOkToProceedError
from solaris_install.gui_install.confirm_screen import ConfirmScreen
from solaris_install.gui_install.disk_screen import DiskScreen
from solaris_install.gui_install.failure_screen import FailureScreen
from solaris_install.gui_install.finish_screen import FinishScreen
from solaris_install.gui_install.gui_install_common import exit_gui_install, \
    modal_dialog, COLOR_WHITE, GLADE_DIR, GLADE_ERROR_MSG
from solaris_install.gui_install.help_dialog import HelpDialog
from solaris_install.gui_install.progress_screen import ProgressScreen
from solaris_install.gui_install.timezone_screen import TimeZoneScreen
from solaris_install.gui_install.user_screen import UserScreen
from solaris_install.gui_install.welcome_screen import WelcomeScreen
from solaris_install.logger import INSTALL_LOGGER_NAME

MAIN_GLADE = "gui-install.xml"
DISK_GLADE = "installationdisk.xml"
TIMEZONE_GLADE = "date-time-zone.xml"
USER_GLADE = "users.xml"
CONFIRM_GLADE = "confirmation.xml"
PROGRESS_GLADE = "installation.xml"
FAILURE_GLADE = "failure.xml"

LOGGER = None


class ScreenManager(object):
    '''
        Screen-management class.
    '''

    DEF_WIDTH = 890
    DEF_HEIGHT = 690

    def __init__(self, logname):
        global LOGGER

        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        # Set the icon for all windows that do not have an icon set
        gtk.window_set_default_icon_name("system-software-install")

        LOGGER.info('Loading GLADE files...')
        # Set up gtk.Builder and load all the Glade UI files
        self.builder = gtk.Builder()
        try:
            self.builder.add_from_file(GLADE_DIR + "/" + MAIN_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + DISK_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + TIMEZONE_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + USER_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + CONFIRM_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + PROGRESS_GLADE)
            self.builder.add_from_file(GLADE_DIR + "/" + FAILURE_GLADE)
        except GError, err:
            print "Error loading Glade files.  Exiting.\n(%s)" % str(err)
            LOGGER.error('Error loading Glade files failed (%s)' % str(err))
            exit_gui_install(errcode=1)
        LOGGER.info('Done loading GLADE files.')

        self.translate_labels()

        # Some of the windows imported from Glade may already have
        # Visible=True set, so we unmap them all here to prevent them
        # getting displayed before we want them to be
        objs = self.builder.get_objects()
        for obj in objs:
            if type(obj) == gtk.Window:
                obj.unmap()

        # quitapp list used to determine if gtk.main_quit() should be called
        self.quitapp = list()

        # Instantiate each of the app's screens now
        self._welcome_screen = WelcomeScreen(self.builder)
        self._disk_screen = DiskScreen(self.builder)
        self._timezone_screen = TimeZoneScreen(self.builder)
        self._user_screen = UserScreen(self.builder)
        self._confirm_screen = ConfirmScreen(self.builder)
        self._progress_screen = ProgressScreen(self.builder, self.finishapp)
        self._finish_screen = FinishScreen(self.builder, logname, self.quitapp)
        self._failure_screen = FailureScreen(self.builder, logname,
            self.quitapp)
        self.list = [
            self._welcome_screen,
            self._disk_screen,
            self._timezone_screen,
            self._user_screen,
            self._confirm_screen,
            self._progress_screen,
            self._finish_screen,
            self._failure_screen
        ]
        self.index = 0
        self._active_screen = None
        self.destroyed = False
        self.helpdialog = None
        self.success = True

        # Map the signals listed in the Glade files to callback
        # functions
        signal_map = {
            "on_quitbutton_clicked": self.quit,
            "on_helpbutton_clicked": self.help,
            "on_backbutton_clicked": self.prev_screen,
            "on_nextbutton_clicked": self.next_screen,
            "on_upgradebutton_clicked": self.no_op,
            "on_installbutton_clicked": self.next_screen,
            "on_rebootbutton_clicked": self.next_screen,
            "on_releasenotesbutton_clicked": self.no_op,
            "on_logbutton_clicked": self.no_op,
            "on_failurelogbutton_clicked": self.no_op,
            #
            # Progress screen:
            #
            "installation_file_leave":
                self._progress_screen.installation_file_leave,
            "installation_file_enter":
                self._progress_screen.installation_file_enter,
            "installation_file_key_release":
                self._progress_screen.installation_file_key_release,
            #
            "gtk_main_quit": self.no_op,
            "on_users_entry_changed": self.no_op,
            "on_hostname_focus_out_event": self.no_op,
            "on_userentry_focus_in_event": self.no_op,
            "on_username_focus_out_event": self.no_op,
            "on_loginname_focus_out_event": self.no_op,
            "on_userpassword_focus_out_event": self.no_op,
            #
            # Timezone screen:
            #
            "on_yearspinner_value_changed":
                self._timezone_screen.on_yearspinner_value_changed,
            "on_monthspinner_value_changed":
                self._timezone_screen.on_monthspinner_value_changed,
            "on_dayspinner_value_changed":
                self._timezone_screen.on_dayspinner_value_changed,
            "on_hourspinner_value_changed":
                self._timezone_screen.on_hourspinner_value_changed,
            "on_minutespinner_value_changed":
                self._timezone_screen.on_minutespinner_value_changed,
            "on_ampmcombobox_changed":
                self._timezone_screen.on_ampmcombobox_changed,
            #
            # Disk screen:
            #
            "partition_3_spinner_value_changed": self.no_op,
            "partition_3_spinner_focus_in_handler": self.no_op,
            "partition_3_spinner_focus_out_handler": self.no_op,
            "partition_2_spinner_value_changed": self.no_op,
            "partition_2_spinner_focus_in_handler": self.no_op,
            "partition_2_spinner_focus_out_handler": self.no_op,
            "partition_1_spinner_value_changed": self.no_op,
            "partition_1_spinner_focus_in_handler": self.no_op,
            "partition_1_spinner_focus_out_handler": self.no_op,
            "partition_0_spinner_value_changed": self.no_op,
            "partition_0_spinner_focus_in_handler": self.no_op,
            "partition_0_spinner_focus_out_handler": self.no_op,
            "disk_partitioning_reset_button_clicked":
                self._disk_screen.fdisk_panel.reset_button_clicked,
            "partition_0_combo_changed": self.no_op,
            "partition_1_combo_changed": self.no_op,
            "partition_2_combo_changed": self.no_op,
            "partition_3_combo_changed": self.no_op,
            "installationdisk_partitiondiskradio_toggled":
                self._disk_screen.installationdisk_partitiondiskradio_toggled,
            "installationdisk_wholediskradio_toggled":
                self._disk_screen.installationdisk_wholediskradio_toggled,
        }
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        missing_handlers = self.builder.connect_signals(signal_map)
        if missing_handlers is not None:
            LOGGER.warn("Internal issue - Missing Signal Handlers!")

        # Configure the application's main window
        self._window = self.builder.get_object("mainwindow")
        self._screencontentviewport = self.builder.get_object(
            "screencontentviewport")

        if None in [self._window, self._screencontentviewport]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        self._window.set_default_size(ScreenManager.DEF_WIDTH,
            ScreenManager.DEF_HEIGHT)
        self._screencontentviewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)

        # add the window to the quitapp list
        self.quitapp.append(self._window)

    def translate_labels(self):
        '''Temporary function to hack around translation errors.
        '''
        for object_name in ["welcomesummarylabel", "label13",
                            "label5", "backlabel", "regionlabel",
                            "countrylabel", "timezonescreenlabel", "timelabel",
                            "datelabel", "yyyymmddlabel", "userlabel",
                            "userpassword1label", "userpassword2label",
                            "loginnamelabel", "usernamelabel", "hostlabel",
                            "hostnamelabel", "disklabel", "softwarelabel",
                            "timezonelabel", "languagelsabel", "accountlabel",
                            "finishlabel1", "rebootlabel", "label14",
                            "finishlogbuttonlabel", "failureinfolabel",
                            "failuredetaillabel", "logbuttonlabel", "label16",
                            "label6", "label3", "partitioningchoicelabel",
                            "label4", "unreadablepartslabel",
                            "partsfoundlabel", "custominfolabel", "label20",
                            "partitionsizelabel", "partitiontypelabel",
                            "partitionavaillabel", "diskwarninglabel"]:
            # get a handle to the label
            needs_translation = self.builder.get_object(object_name)
            # replace the current label text with the translated text
            if needs_translation:
                needs_translation.set_label(_(needs_translation.get_label()))

        # the AM/PM/24 hour time combo box needs to be handled differently
        ampmcombobox = self.builder.get_object("ampmcombobox")
        if ampmcombobox:
            # make a list of translated labels excluding trailing '\n'
            labels = _("AM\nPM\n24 Hour\n").split('\n')[:-1]
            # get the store and iterate over the labels replacing them with
            # the translated labels
            store = ampmcombobox.get_model()
            if store:
                store_iter = store.get_iter('0')
                for label in labels:
                    if store_iter:
                        store.set(store_iter, 0, label)
                        store_iter = store.iter_next(store_iter)

    # Read-only properties
    @property
    def disk_screen(self):
        '''Returns the DiskScreen object.'''
        return self._disk_screen

    @property
    def active_screen(self):
        '''Returns the currently active screen.'''
        return self._active_screen

    def main(self):
        '''main function for the class'''
        self._active_screen = self.list[self.index]
        LOGGER.info("Initial screen is screen [%d] [%s]" % \
            (self.index, self._active_screen.name))
        self._active_screen.enter()
        self._window.connect("destroy", self.quit)
        self._window.connect("delete_event", self.destroy_event)

        self._window.show()

        # Pass control over to Gtk+
        gtk.main()

    # Signal callbacks
    def prev_screen(self, widget):
        '''callback for the "Prev" button'''
        if self.index <= 0:
            LOGGER.warn("No previous screen available")
            return

        try:
            self._active_screen.go_back()
        except NotOkToProceedError, err:
            LOGGER.error("ERROR Cannot leave screen: [%s]" % \
                str(err))
            return

        self.index -= 1
        self._active_screen = self.list[self.index]
        LOGGER.info("Prev screen is screen [%d] [%s]" % \
            (self.index, self._active_screen.name))
        try:
            self._active_screen.enter()
        except NotOkToProceedError, err:
            LOGGER.error("ERROR Cannot enter screen: [%s]" % \
                str(err))

        if self.helpdialog:
            self.helpdialog.update_help(self.index)

    def finishapp(self, success=True):
        self.success = success
        self.next_screen(None)

    def next_screen(self, widget):
        '''callback for the "Next" button'''
        if self.index >= len(self.list) - 1:
            LOGGER.warn("No next screen available")
            return

        try:
            self._active_screen.validate()
        except NotOkToProceedError, err:
            LOGGER.error("ERROR Validation error on screen: [%s]" % \
                str(err))
            return

        self.index += 1
        self._active_screen = self.list[self.index]
        if self._active_screen == self._finish_screen:
            if not self.success:
                self._active_screen = self._failure_screen

        LOGGER.info("Next screen is screen [%d] [%s]" % \
            (self.index, self._active_screen.name))
        try:
            auto_advance = self._active_screen.enter()
        except NotOkToProceedError, err:
            LOGGER.error("ERROR Cannot enter screen: [%s]" % \
                str(err))
            auto_advance = False

        if self.helpdialog:
            self.helpdialog.update_help(self.index)

        if auto_advance:
            self.next_screen(None)

    def destroy_event(self, widget, event):
        '''catches delete events on the window and uses quit_dialog to
           display the quit warning dialog
        '''
        self.destroyed = self.__quit_dialog()

        return not self.destroyed

    def quit(self, widget):
        '''callback for the quit button and destroy window.  Uses quit_dialog
           to display the quit warning dialog.
        '''
        # check if the destroy event initiated the quit
        if self.destroyed:
            # is only the screenwindow up?
            if len(self.quitapp) == 1:
                # quit the application
                gtk.main_quit()
            else:
                # log window is also up, hide the screenwindow and
                # remove a window from the quitapp list
                self._window.hide_all()
                self.quitapp.pop()
                if self.helpdialog:
                    self.helpdialog.undisplay()

            return

        quit_boolean = self.__quit_dialog()
        # check if the user quit the application
        if quit_boolean:
            # is only the screenwindowup?
            if len(self.quitapp) == 1:
                # quit the application
                gtk.main_quit()
            else:
                # log window is also up, hide the screenwindow and
                # remove a window from the quitapp list
                self._window.hide_all()
                self.quitapp.pop()
                if self.helpdialog:
                    self.helpdialog.undisplay()

    def __quit_dialog(self):
        '''function to display the quit dialog'''
        # create a simple quit modal dialog
        message = gtk.MessageDialog(self._window, gtk.DIALOG_MODAL,
                                gtk.MESSAGE_WARNING, gtk.BUTTONS_OK_CANCEL,
                                _("Do you want to quit this installation ?"))

        # display the dialog
        resp = message.run()
        message.destroy()

        return resp == gtk.RESPONSE_OK

    def help(self, widget):
        '''callback for the help button.'''
        if not self.helpdialog:
            self.helpdialog = HelpDialog(self.builder)

        self.helpdialog.display(self.index)

    def no_op(self, widget=None, data=None):
        '''nop_op function that allows stubbing out of the
           signal_map dictionary
        '''
        pass

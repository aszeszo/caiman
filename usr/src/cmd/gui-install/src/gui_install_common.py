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
Common definitions, variables and functions for the GUI installer
'''

import pygtk
pygtk.require('2.0')

import gettext
import locale
import linecache
import logging
import os
import sys
import threading
import time

import gobject
import gtk

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from solaris_install import CalledProcessError, post_install_logs_path, \
    run
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.physical import Iscsi

# Define "_()" for gettext
_ = gettext.translation("solaris_install_guiinstall", "/usr/share/locale",
                        fallback=True).ugettext

# Dir which this executable is run from
EXE_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
# usr/share dir (relative to EXE_DIR)
SHARE_DIR = os.path.abspath(EXE_DIR + "/../share")
# Location of Glade/GtkBuilder .xml files
GLADE_DIR = SHARE_DIR + "/gui-install"
GLADE_ERROR_MSG = _("Unable to retrieve a widget from Glade XML files.")
# Location of .png/.gif files for icons, etc
IMAGE_DIR = SHARE_DIR + "/gui-install"

# default install log file
DEFAULT_LOG_LOCATION = "/system/volatile/install_log"

# final log location after installation
LOG_LOCATION_FINAL = post_install_logs_path("install_log").lstrip("/")

# PID file for checking for multiple instances of program
PIDFILE = "/system/volatile/gui-install.pid"

# current log file
LOGNAME = None

# default logging level
DEFAULT_LOG_LEVEL = logging.INFO

# debug logging level
DEBUG_LOG_LEVEL = logging.DEBUG

# default log format
LOG_FORMAT = ("%(asctime)s - %(levelname)-8s: %(message)s")

# default logging variables
LOG_LEVEL_INPUT = 5
LOG_NAME_INPUT = "INPUT"

RELEASE = _("Oracle Solaris")
INTERNAL_ERR_MSG = _("Internal error")

COLOR_WHITE = gtk.gdk.Color("white")

FIREFOX = '/usr/bin/firefox'

# Commonly used Checkpoint definitions
CLEANUP_CPIO_INSTALL = "cleanup-cpio-install"
TRANSFER_PREP = "PrepareTransfer"
VARSHARE_DATASET = "VarShareDataset"

# Flags for tracking TargetDiscovery status
TD_LOCAL_COMPLETE = False
TD_ISCSI_COMPLETE = False
WAIT_FOR_TD_LOCAL = False
WAIT_FOR_TD_ISCSI = False
QUEUE_TD_ISCSI = False
TD_RESULTS_STATE = True

# Identifiers for TargetDiscovery and its arguments
TARGET_DISCOVERY = "TargetDiscovery"
ISCSI_TARGET_DISCOVERY = "iSCSI TargetDiscovery"
ISCSI_LABEL = "iSCSI"


def get_encoding():
    ''' Get encoding of current locale
    '''
    enc = locale.getlocale(locale.LC_CTYPE)[1]
    if enc is None:
        enc = locale.getpreferredencoding()

    return enc


def empty_container(gtk_container, destroy=False):
    ''' Convenience function for emptying out the contents of a Gtk+
        container.'''
    old_content = gtk_container.get_children()
    for child in old_content:
        gtk_container.remove(child)
        if destroy:
            child.destroy()


def exit_gui_install(logname=None, errcode=0):
    '''Teardown any existing iSCSI objects, Close out the logger and exit with
    errcode'''

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    # get the Iscsi object from the DOC, if present.
    doc = InstallEngine.get_instance().doc
    iscsi = doc.volatile.get_first_child(name=ISCSI_LABEL, class_type=Iscsi)
    if iscsi:
        logger.debug("User has exited installer.  Tearing down Iscsi object")
        try:
            iscsi.teardown()
        except CalledProcessError as error:
            # Not a fatal error
            logger.warn("Iscsi.teardown failed: " + str(error))

    logger.info("**** END ****")
    logger.close()

    del_pid_file()

    if logname is not None:
        print _("Exiting GUI Installer. Log is available at:\n%s") % logname
    if isinstance(errcode, unicode):
        errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def modal_dialog(title, text, two_buttons=False, yes_no=False):
    ''' Display a modal dialog box.

        Params:
        - title, the Dialog Box title text string
        - text, the Dialog Box message string
        - two_buttons, if False (the default) only provide a single CLOSE
          button to terminate the dialog (in this case the return value
          will always be False); if True, provide two options for user to
          select;  see yes_no for further details.
        - yes_no, only applicable if two_buttons is True; if yes_no is
          False (default), then the two buttons will be OK and CANCEL buttons
          and the return value will be True if OK is pressed or False if
          CANCEL is pressed.
          if yes_no is True, then the two buttons will be YES and NO buttons
          and the return value will be True is YES is pressed or False if
          NO is pressed.

        Returns:
        True or False
    '''

    if two_buttons:
        if yes_no:
            buttons = gtk.BUTTONS_YES_NO
        else:
            buttons = gtk.BUTTONS_OK_CANCEL
    else:
        buttons = gtk.BUTTONS_CLOSE

    dialog = gtk.MessageDialog(None,
        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        gtk.MESSAGE_ERROR,
        buttons)

    msg = "<b>%s</b>\n\n%s" % (title, text)
    dialog.set_markup(msg)

    if two_buttons:
        if yes_no:
            dialog.set_default_response(gtk.RESPONSE_YES)
        else:
            dialog.set_default_response(gtk.RESPONSE_OK)

    # display the dialog
    response = dialog.run()
    dialog.destroy()

    if two_buttons:
        if response == gtk.RESPONSE_OK:
            return True
        elif response == gtk.RESPONSE_YES:
            return True
    return False


def other_instance_is_running():
    ''' Check if another instance of this program is running.

        Returns:
        - True if other instance is running
        - False otherwise

        Check if the PIDFILE already exists, and if so,
        confirm that the PID it contains matches a
        currently running process.
    '''

    if os.path.exists(PIDFILE):
        linecache.checkcache(PIDFILE)
        previous_pid = int(linecache.getline(PIDFILE, 1))
        this_pid = os.getpid()

        if this_pid != previous_pid:
            # Double check that the PID we found actually
            # matches a currently running process, and
            # which is not this process.
            pids = os.listdir("/proc")
            for pid in pids:
                pid = int(pid)
                if pid == previous_pid:
                    return True

    return False


def write_pid_file():
    ''' Write this process' PID to PIDFILE.

        Assumes we are running as root.
    '''

    with open(PIDFILE, 'w') as pidfile:
        this_pid = os.getpid()
        pidfile.write(str(this_pid) + '\n')


def del_pid_file():
    ''' Remove the PIDFILE.
    '''

    if os.path.exists(PIDFILE):
        os.remove(PIDFILE)


def N_(message):
    ''' Dummy function used to mark text for delayed translation.
        Use of this function name is standard gettext practice.
    '''

    return message


def open_browser(uri=None):
    '''
        Run web browser with optional uri in a separate thread.
    '''
    thread = _RunBrowserThread(uri)


def make_url(value):
    ''' Transform value into a valid URL if not already one.
    '''
    if value is None or not value or value.find("://") != -1:
        return value
    return "http://" + value


class _RunBrowserThread(threading.Thread):
    '''
        Thread class for running web browser.
    '''

    def __init__(self, uri):
        ''' Initializer method - called from constructor.

            Params:
            - uri, URI to open in browser, or None, if you
              just wish to start the browser.

            Returns: Nothing
        '''
        threading.Thread.__init__(self)

        self.uri = uri

        # invoke run()
        self.start()

    def run(self):
        ''' Override run method from parent class.

            Runs Firefox.
        '''

        cmd = [FIREFOX]
        if self.uri is not None:
            cmd.append(self.uri)

        try:
            run(cmd)
        except CalledProcessError, err:
            logger = logging.getLogger(INSTALL_LOGGER_NAME)
            logger.error("ERROR: executing command [%s] failed: [%s]", cmd,
                         err)


#--------------------------------------------------------------------------
# TargetDiscovery-related functions

def start_td_local():
    ''' Kicks off the TargetDiscovery checkpoint for local disks.

        By passing the InstallEngine a callback function, TD is
        run in a separate thread and control is immediately passed
        back to this function.  The application is notified when
        TD completes by having the callback function called.

        Returns: nothing
    '''
    global WAIT_FOR_TD_LOCAL, TD_LOCAL_COMPLETE

    WAIT_FOR_TD_LOCAL = True
    TD_LOCAL_COMPLETE = False

    engine = InstallEngine.get_instance()
    errsvc.clear_error_list()
    engine.execute_checkpoints(start_from=TARGET_DISCOVERY,
        pause_before=TRANSFER_PREP,
        callback=td_local_callback)


def start_td_iscsi():
    ''' Kicks off the TargetDiscovery checkpoint for an iSCSI disk.

        By passing the InstallEngine a callback function, TD is
        run in a separate thread and control is immediately passed
        back to this function.  The application is notified when
        TD completes by having the callback function called.

        Returns: nothing
    '''
    global WAIT_FOR_TD_ISCSI, TD_ISCSI_COMPLETE

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    WAIT_FOR_TD_ISCSI = True
    TD_ISCSI_COMPLETE = False

    engine = InstallEngine.get_instance()
    iscsi = engine.doc.volatile.get_first_child(name=ISCSI_LABEL,
        class_type=Iscsi)
    if iscsi is None:
        logger.error("INTERNAL ERROR: cannot get Iscsi object from DOC")
        raise RuntimeError("INTERNAL ERROR: cannot get Iscsi object from DOC")

    logger.debug("Starting TD(iSCSI) with search_name: %s", iscsi.ctd_list)
    kwargs = {"search_type": "disk", "search_name": iscsi.ctd_list}
    # Either re-run an already-registered TD(iSCSI) checkpoint
    # or register one for the first time
    for checkpoint in engine._checkpoints:
        if checkpoint.name == ISCSI_TARGET_DISCOVERY:
            logger.debug("Re-using existing %s checkpoint" %
                ISCSI_TARGET_DISCOVERY)
            checkpoint.kwargs = kwargs
            break
    else:
        # register a new iSCSI target discovery checkpoint
        engine.register_checkpoint(ISCSI_TARGET_DISCOVERY,
            "solaris_install/target/discovery",
            "TargetDiscovery",
            kwargs=kwargs,
            insert_before=TRANSFER_PREP)
    errsvc.clear_error_list()
    engine.execute_checkpoints(start_from=ISCSI_TARGET_DISCOVERY,
        pause_before=TRANSFER_PREP,
        callback=td_iscsi_callback)


def start_td_iscsi_deferred():
    '''
        This is called as a glib timeout, when we cannot invoke
        start_td_iscsi() directly.

        It returns False, so that the timeout does not repeat.
    '''
    # Wait until we are certain the engine has finished execution
    engine = InstallEngine.get_instance()
    while engine._is_executing_checkpoints():
        time.sleep(0.1)

    start_td_iscsi()
    return False


def queue_td_iscsi():
    '''
        Set up the global variables to indicate that we want to
        run TD(iscsi) when the currently executing TD completes.`
    '''
    global QUEUE_TD_ISCSI, WAIT_FOR_TD_ISCSI, TD_ISCSI_COMPLETE

    QUEUE_TD_ISCSI = True
    WAIT_FOR_TD_ISCSI = True
    TD_ISCSI_COMPLETE = False


def td_local_callback(status, failed_cps):
    '''
        This is the callback registered with the InstallEngine to
        be called when TargetDiscovery (for local disks) completes.

        Logs any Checkpoint errors and sets TD_LOCAL_COMPLETE to True.
        If TD(iSCSI) has been queued, then run it.
    '''
    global TD_LOCAL_COMPLETE, WAIT_FOR_TD_LOCAL, QUEUE_TD_ISCSI

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    # Ensure that the checkpoint did not record any errors
    if status != InstallEngine.EXEC_SUCCESS:
        # Log the errors, but then attempt to proceed anyway
        logger.error("ERROR: TargetDiscovery (local disks) FAILED")

        for failed_cp in failed_cps:
            err_data_list = errsvc.get_errors_by_mod_id(failed_cp)
            if len(err_data_list):
                err_data = err_data_list[0]
                err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
            else:
                err = "Unknown error"

            logger.error("Checkpoint [%s] logged error: [%s]" % \
                (failed_cp, err))

    TD_LOCAL_COMPLETE = True
    WAIT_FOR_TD_LOCAL = False

    if QUEUE_TD_ISCSI:
        # We cannot directly register the next checkpoint from
        # this callback function, as the Engine is still executing.
        # So, we defer registration slightly by doing it via
        # idle_add.  The function passed into idle_add() gets run
        # from the Gtk+ main loop when it gets an opportunity.
        logger.debug("Kicking off TD(iSCSI) indirectly")
        gobject.idle_add(start_td_iscsi_deferred)
        QUEUE_TD_ISCSI = False


def td_iscsi_callback(status, failed_cps):
    '''
        This is the callback registered with the InstallEngine to
        be called when TargetDiscovery (for iSCSI disks) completes.

        Logs any Checkpoint errors and sets TD_ISCSI_COMPLETE to True.
        If TD(iSCSI) has been queued, then run it.
    '''
    global TD_ISCSI_COMPLETE, WAIT_FOR_TD_ISCSI, QUEUE_TD_ISCSI

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    # Ensure that the checkpoint did not record any errors
    if status != InstallEngine.EXEC_SUCCESS:
        # Log the errors, but then attempt to proceed anyway
        logger.error("ERROR: TargetDiscovery (iSCSI disks) FAILED")

        for failed_cp in failed_cps:
            err_data_list = errsvc.get_errors_by_mod_id(failed_cp)
            if len(err_data_list):
                err_data = err_data_list[0]
                err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
            else:
                err = "Unknown error"

            logger.error("Checkpoint [%s] logged error: [%s]" % \
                (failed_cp, err))

        # fetch Iscsi from DOC and unconfig and delete it
        engine = InstallEngine.get_instance()
        iscsis = engine.doc.volatile.get_children(name=ISCSI_LABEL,
            class_type=Iscsi)
        for iscsi in iscsis:
            try:
                logger.debug("teardown previous iSCSI: %s", iscsi)
                iscsi.teardown()
            except CalledProcessError as error:
                # Not a fatal error
                logger.warn("Iscsi.teardown failed: " + str(error))

            logger.debug("Removing old Iscsi object from DOC: %s", iscsi)
            iscsi.delete()

    TD_ISCSI_COMPLETE = True
    WAIT_FOR_TD_ISCSI = False

    if QUEUE_TD_ISCSI:
        # We cannot directly register the next checkpoint from
        # this callback function, as the Engine is still executing,
        # so we do so via idle_add (which runs function in main loop
        # when it gets an opportunity)
        logger.debug("Kicking off TD(iSCSI) indirectly")
        gobject.idle_add(start_td_iscsi_deferred)
        QUEUE_TD_ISCSI = False


def is_discovery_complete():
    '''
        Returns True if all the currently planned TargetDiscoveries
        have finished.  Otherwise, returns False.
    '''

    if WAIT_FOR_TD_LOCAL:
        if not TD_LOCAL_COMPLETE:
            return False

    if WAIT_FOR_TD_ISCSI:
        if not TD_ISCSI_COMPLETE:
            return False

    return True


def get_td_results_state():
    '''
        Returns True if outstanding TD results have been
        processed.  Otherwise, returns False, indicating that
        they must be processed.
    '''

    return TD_RESULTS_PROCESSED


def set_td_results_state(val):
    '''
        Set flag TD_RESULTS_PROCESSED to val.
        Parameters:
        - val, a boolean
    '''
    global TD_RESULTS_PROCESSED

    TD_RESULTS_PROCESSED = val

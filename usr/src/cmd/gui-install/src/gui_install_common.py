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

import gtk

from solaris_install.logger import INSTALL_LOGGER_NAME

# Define "_()" for gettext
_ = gettext.translation("gui-install", "/usr/share/locale",
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
DEFAULT_LOG_LOCATION = "/tmp/install_log"

# final log location after installation
LOG_LOCATION_FINAL = "var/sadm/system/logs/install_log"

# PID file for checking for multiple instances of program
PIDFILE = "/system/volatile/gui-install.pid"

# current log file
LOGNAME = None

# default logging level
DEFAULT_LOG_LEVEL = "info"

# debug logging level
DEBUG_LOG_LEVEL = "debug"

# default log format
LOG_FORMAT = ("%(asctime)s - %(levelname)-8s: %(message)s")

# default logging variables
LOG_LEVEL_INPUT = 5
LOG_NAME_INPUT = "INPUT"

RELEASE = _("Oracle Solaris")

COLOR_WHITE = gtk.gdk.Color("white")

FIREFOX = '/usr/bin/firefox'

# Commonly used Checkpoint definitions
CLEANUP_CPIO_INSTALL = "cleanup-cpio-install"
TRANSFER_PREP = "PrepareTransfer"
TARGET_INIT = "TargetInitialization"


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
    '''Close out the logger and exit with errcode'''
    logger = logging.getLogger(INSTALL_LOGGER_NAME)
    logger.info("**** END ****")
    logger.close()

    del_pid_file()

    if logname is not None:
        print _("Exiting GUI Installer. Log is available at:\n%s") % logname
    if isinstance(errcode, unicode):
        errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def modal_dialog(title, text, two_buttons=False):
    ''' Display a modal dialog box.

        Params:
        - title, the Dialog Box title text string
        - text, the Dialog Box message string
        - two_buttons, if False (the default) only provide a single CLOSE
          button to terminate the dialog (in this case the return value
          will always be False); if True provide OK and CANCEL buttons
          and the return value will be True if OK is pressed or False if
          CANCEL is pressed.

        Returns:
        True or False
    '''

    if two_buttons:
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
        dialog.set_default_response(gtk.RESPONSE_OK)

    # display the dialog
    response = dialog.run()
    dialog.destroy()

    if response == gtk.RESPONSE_OK:
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

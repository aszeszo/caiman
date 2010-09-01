#!/usr/bin/python2.6
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Text / (n)Curses based UI for installing Oracle Solaris
'''

import curses
import logging
import os
import platform
import signal
import subprocess
import sys
import traceback
import locale
import gettext
from optparse import OptionParser

import libbe_py
from osol_install.liblogsvc import init_log
from osol_install.profile.install_profile import InstallProfile
from osol_install.text_install import _, \
                                      LOG_LOCATION_FINAL, \
                                      DEFAULT_LOG_LOCATION, \
                                      DEFAULT_LOG_LEVEL, \
                                      DEBUG_LOG_LEVEL, \
                                      LOG_FORMAT, \
                                      LOG_LEVEL_INPUT, \
                                      LOG_NAME_INPUT, \
                                      RELEASE
from osol_install.text_install.base_screen import RebootException
from osol_install.text_install.date_time import DateTimeScreen
from osol_install.text_install.disk_selection import DiskScreen
from osol_install.text_install.fdisk_partitions import FDiskPart
from osol_install.text_install.help_screen import HelpScreen
from osol_install.text_install.i18n import get_encoding
from osol_install.text_install.install_progress import InstallProgress
from osol_install.text_install.install_status import InstallStatus
from osol_install.text_install.log_viewer import LogViewer
from osol_install.text_install.main_window import MainWindow
from osol_install.text_install.network_nic_configure import NICConfigure
from osol_install.text_install.network_nic_select import NICSelect
from osol_install.text_install.network_type import NetworkTypeScreen
from osol_install.text_install.partition_edit_screen import PartEditScreen
from osol_install.text_install.screen_list import ScreenList
from osol_install.text_install.summary import SummaryScreen
from osol_install.text_install.timezone import TimeZone
from osol_install.text_install.users import UserScreen
from osol_install.text_install.welcome import WelcomeScreen


def setup_curses():
    '''Initialize the curses module'''
    initscr = curses.initscr()
    if curses.has_colors():
        curses.start_color()
    curses.noecho()
    curses.cbreak()
    curses.meta(1)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    return initscr


def cleanup_curses():
    '''Return the console to a usable state'''
    curses.echo()
    curses.nocbreak()
    curses.endwin()
    os.system("/usr/bin/clear")


def exit_text_installer(logname=None, errcode=0):
    '''Close out the logger and exit with errcode'''
    logging.info("**** END ****")
    logging.shutdown()
    if logname is not None:
        print _("Exiting Text Installer. Log is available at:\n%s") % logname
    if isinstance(errcode, unicode):
	errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def setup_logging(logname, log_level):
    '''Initialize the logger, logging to logname at log_level'''
    log_level = log_level.upper()
    if hasattr(logging, log_level):
        log_level = getattr(logging, log_level.upper())
    elif log_level == LOG_NAME_INPUT:
        log_level = LOG_LEVEL_INPUT
    else:
        raise IOError(2, "Invalid --log-level parameter", log_level.lower())
    logging.basicConfig(filename=logname, level=log_level,
                        filemode='w', format=LOG_FORMAT)
    logging.addLevelName(LOG_LEVEL_INPUT, LOG_NAME_INPUT)
    logging.info("**** START ****")


def make_screen_list(main_win):
    '''Initialize the screen list. On x86, add screens for editing slices
    within a partition. Also, trigger the target discovery thread.
    
    '''
    
    result = []
    result.append(WelcomeScreen(main_win))
    disk_screen = DiskScreen(main_win)
    disk_screen.start_discovery()
    result.append(disk_screen)
    result.append(FDiskPart(main_win))
    result.append(PartEditScreen(main_win))
    if platform.processor() == "i386":
        result.append(FDiskPart(main_win, x86_slice_mode=True))
        result.append(PartEditScreen(main_win, x86_slice_mode=True))
    result.append(NetworkTypeScreen(main_win))
    result.append(NICSelect(main_win))
    result.append(NICConfigure(main_win))
    result.append(TimeZone(main_win, screen=TimeZone.REGIONS))
    result.append(TimeZone(main_win, screen=TimeZone.LOCATIONS))
    result.append(TimeZone(main_win))
    result.append(DateTimeScreen(main_win))
    result.append(UserScreen(main_win))
    result.append(SummaryScreen(main_win))
    result.append(InstallProgress(main_win))
    result.append(InstallStatus(main_win))
    result.append(LogViewer(main_win))
    return result


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, "")
    gettext.install("textinstall", "/usr/share/locale", unicode=True)
    if os.getuid() != 0:
        print _("The %(release)s Text Installer must be run with "
                "root privileges") % RELEASE
        sys.exit(1)
    USAGE = "usage: %prog [-l FILE] [-v LEVEL] [-d] [-n]"
    PARSER = OptionParser(usage=USAGE, version="%prog 1.1")
    PARSER.add_option("-l", "--log-location", dest="logname",
                      help=_("Set log location to FILE (default: %default)"),
                      metavar="FILE", default=DEFAULT_LOG_LOCATION)
    PARSER.add_option("-v", "--log-level", dest="log_level",
                      default=None,
                      help=_("Set log verbosity to LEVEL. In order of "
                             "increasing verbosity, valid values are 'error' "
                             "'warn' 'info' 'debug' or 'input'\n[default:"
                             " %default]"),
                      choices=["error", "warn", "info", "debug", "input"],
                      metavar="LEVEL")
    PARSER.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=False, help=_("Enable debug mode. Sets " 
                      "logging level to 'input' and enables CTRL-C for " 
                      "killing the program\n"))
    PARSER.add_option("-b", "--no-color", action="store_true", dest="force_bw",
                      default=False, help=_("Force the installer to run in "
                      "black and white. This may be useful on some SPARC "
                      "machines with unsupported frame buffers\n"))
    PARSER.add_option("-n", "--no-install", action="store_true",
                      dest="no_install", default=False,
                      help=_("Runs in 'no installation' mode. When run"
                      " in 'no installation' mode, no persistent changes are"
                      " made to the disks and booted environment\n"))
    OPTIONS, ARGS = PARSER.parse_args()
    if OPTIONS.log_level is None:
        if OPTIONS.debug:
            OPTIONS.log_level = DEBUG_LOG_LEVEL
        else:
            OPTIONS.log_level = DEFAULT_LOG_LEVEL
    try:
        setup_logging(OPTIONS.logname, OPTIONS.log_level)
    except IOError, err:
        PARSER.error("%s '%s'" % (err.strerror, err.filename))
    logging.debug("CLI Options: log location = %s, verbosity = %s, debug "
                  "mode = %s, no install = %s, force_bw = %s",
                  OPTIONS.logname, OPTIONS.log_level, OPTIONS.debug,
                  OPTIONS.no_install, OPTIONS.force_bw)
    init_log(0) # initialize logging service
    INSTALL_PROFILE = None
    try:
        try:
            INITSCR = setup_curses()
            WIN_SIZE_Y, WIN_SIZE_X = INITSCR.getmaxyx()
            if WIN_SIZE_Y < 24 or WIN_SIZE_X < 80:
                MSG = _("     Terminal too small. Min size is 80x24."
                        " Current size is %(x)ix%(y)i.") % \
                        {'x': WIN_SIZE_X, 'y': WIN_SIZE_Y}
                exit_text_installer(errcode=MSG)
            INSTALL_PROFILE = InstallProfile()
            INSTALL_PROFILE.log_location = OPTIONS.logname
            INSTALL_PROFILE.log_final = LOG_LOCATION_FINAL
            INSTALL_PROFILE.no_install_mode = OPTIONS.no_install
            if platform.processor() == "i386":
                INSTALL_PROFILE.is_x86 = True
            else:
                INSTALL_PROFILE.is_x86 = False
            SCREEN_LIST = ScreenList()
            MAIN_WIN = MainWindow(INITSCR, SCREEN_LIST,
                                  force_bw=OPTIONS.force_bw)
            SCREEN_LIST.help = HelpScreen(MAIN_WIN)
            WIN_LIST = make_screen_list(MAIN_WIN)
            SCREEN_LIST.screen_list = WIN_LIST 
            SCREEN = SCREEN_LIST.get_next()
            CTRL_C = None
            while SCREEN is not None:
                logging.debug("Install profile:\n%s", INSTALL_PROFILE)
                logging.debug("Displaying screen: %s", type(SCREEN))
                SCREEN = SCREEN.show(INSTALL_PROFILE)
                if not OPTIONS.debug and CTRL_C is None:
                    # This prevents the user from accidentally hitting
                    # ctrl-c halfway through the install. Ctrl-C is left
                    # available through the first screen in case terminal
                    # display issues make it impossible for the user to
                    # quit gracefully
                    CTRL_C = signal.signal(signal.SIGINT, signal.SIG_IGN)
            cleanup_curses()
            ERRCODE = 0
        finally:
            cleanup_curses()
    except RebootException:
        if INSTALL_PROFILE.is_x86:
            RET_VAL, BE_LIST = libbe_py.beList()
            if RET_VAL == 0:
                for be in BE_LIST:
                    if be.get("active_boot", False):
                        root_ds = be['root_ds']
                        call_cmd = ["/usr/sbin/reboot", "-f", "--", root_ds]
                        try:
                            subprocess.call(call_cmd)
                        except OSError, err:
                            logging.warn("Fast reboot failed:\n\t'%s'\n%s",
                                         " ".join(call_cmd), err)
                        else:
                            logging.warn("Fast reboot failed. Will attempt"
                                         " standard reboot\n(Fast reboot "
                                         "args:%s)", " ".join(call_cmd))
                        break
        # Fallback reboot. If the subprocess.call(..) command above fails,
        # Simply do a standard reboot.
        subprocess.call("/usr/sbin/reboot")
    except SystemExit:
        raise
    except:
        logging.error(str(INSTALL_PROFILE))
        logging.error(traceback.format_exc())
        EXC_TYPE, EXC_VALUE = sys.exc_info()[:2]
        print _("An unhandled exception occurred.")
        if str(EXC_VALUE):
            print '\t%s: "%s"' % (EXC_TYPE.__name__, str(EXC_VALUE))
        else:
            print "\t%s" % EXC_TYPE.__name__
        print _("Full traceback data is in the installation log")
        print _("Please file a bug at http://defect.opensolaris.org")
        ERRCODE = 1
    exit_text_installer(OPTIONS.logname, ERRCODE)

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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Text / (n)Curses based UI for installing Oracle Solaris
'''

import gettext

# Variables used by modules this module imports
# Defined here to avoid circular import errors
_ = gettext.translation("textinstall", "/usr/share/locale",
                        fallback=True).ugettext
RELEASE = {"release" : _("Oracle Solaris")}
TUI_HELP = "/usr/share/text-install/help"


import curses
import locale
import logging
from optparse import OptionParser
import os
import platform
import signal
import subprocess
import sys
import traceback

import libbe_py
from osol_install.liblogsvc import init_log
from osol_install.profile.install_profile import InstallProfile, \
                                                 INSTALL_PROF_LABEL
from osol_install.text_install.disk_selection import DiskScreen
from osol_install.text_install.fdisk_partitions import FDiskPart
from osol_install.text_install.install_progress import InstallProgress
from osol_install.text_install.install_status import InstallStatus, \
                                                     RebootException
from osol_install.text_install.log_viewer import LogViewer
from osol_install.text_install.partition_edit_screen import PartEditScreen
from osol_install.text_install.summary import SummaryScreen
from osol_install.text_install.welcome import WelcomeScreen
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
import solaris_install.sysconfig as sysconfig
import terminalui
from terminalui import LOG_LEVEL_INPUT, LOG_NAME_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.help_screen import HelpScreen
from terminalui.i18n import get_encoding, set_wrap_on_whitespace
from terminalui.main_window import MainWindow
from terminalui.screen_list import ScreenList


LOG_LOCATION_FINAL = "/var/sadm/system/logs/install_log"
DEFAULT_LOG_LOCATION = "/tmp/install_log"
DEFAULT_LOG_LEVEL = "info"
DEBUG_LOG_LEVEL = "debug"
LOG_FORMAT = ("%(asctime)-25s %(name)-10s "
              "%(levelname)-10s %(message)-50s")
REBOOT = "/usr/sbin/reboot"


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
    logging.info("**** START ****")
    return log_level


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
    
    result.extend(sysconfig.get_all_screens(main_win))
    
    result.append(SummaryScreen(main_win))
    result.append(InstallProgress(main_win))
    result.append(InstallStatus(main_win))
    result.append(LogViewer(main_win))
    return result


def _reboot_cmds(is_x86):
    '''Generate list of cmds to try fast rebooting'''
    cmds = []
    
    ret_val, be_list = libbe_py.beList()
    if ret_val == 0:
        for be in be_list:
            if be.get("active_boot", False):
                root_ds = "%s" % be['root_ds']
                if is_x86:
                    cmds.append([REBOOT, "-f", "--", root_ds])
                else:
                    # SPARC requires "-Z" before the root dataset
                    cmds.append([REBOOT, "-f", "--", "-Z", root_ds])
                break
        
    # Fallback reboot. If the subprocess.call(..) command above fails,
    # simply do a standard reboot.
    cmds.append([REBOOT])
    return cmds


def reboot(is_x86):
    '''Reboot the machine, attempting fast reboot first if available'''
    cmds = _reboot_cmds(is_x86)
    for cmd in cmds:
        try:
            subprocess.call(cmd)
        except OSError, err:
            logging.warn("Reboot failed:\n\t'%s'\n%s",
                         " ".join(cmd), err)
        else:
            logging.warn("Reboot failed:\n\t'%s'.\nWill attempt"
                         " standard reboot", " ".join(cmd))


def prepare_engine(options):
    eng = InstallEngine(loglevel=options.log_level, debug=options.debug)
    terminalui.init_logging(INSTALL_LOGGER_NAME)
    
    install_profile = InstallProfile()
    install_profile.log_location = options.logname
    install_profile.log_final = LOG_LOCATION_FINAL
    install_profile.no_install_mode = options.no_install
    
    eng.doc.persistent.insert_children([install_profile])

    sysconfig.register_checkpoint()


def init_locale():
    locale.setlocale(locale.LC_ALL, "")
    gettext.install("textinstall", "/usr/share/locale", unicode=True)
    set_wrap_on_whitespace(_("DONT_TRANSLATE_BUT_REPLACE_msgstr_WITH_True_"
                             "OR_False: Should wrap text on whitespace in"
                             " this language"))
    BaseScreen.set_default_quit_text(_("Confirm: Quit the Installer?"),
                                     _("Do you want to quit the Installer?"),
                                     _("Cancel"),
                                     _("Quit"))


def main():
    init_locale()
    
    if os.getuid() != 0:
        sys.exit(_("The %(release)s Text Installer must be run with "
                   "root privileges") % RELEASE)
    usage = "usage: %prog [-l FILE] [-v LEVEL] [-d] [-n]"
    parser = OptionParser(usage=usage, version="%prog 1.1")
    parser.add_option("-l", "--log-location", dest="logname",
                      help=_("Set log location to FILE (default: %default)"),
                      metavar="FILE", default=DEFAULT_LOG_LOCATION)
    parser.add_option("-v", "--log-level", dest="log_level",
                      default=None,
                      help=_("Set log verbosity to LEVEL. In order of "
                             "increasing verbosity, valid values are 'error' "
                             "'warn' 'info' 'debug' or 'input'\n[default:"
                             " %default]"),
                      choices=["error", "warn", "info", "debug", "input"],
                      metavar="LEVEL")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      default=False, help=_("Enable debug mode. Sets " 
                      "logging level to 'input' and enables CTRL-C for " 
                      "killing the program\n"))
    parser.add_option("-b", "--no-color", action="store_true", dest="force_bw",
                      default=False, help=_("Force the installer to run in "
                      "black and white. This may be useful on some SPARC "
                      "machines with unsupported frame buffers\n"))
    parser.add_option("-n", "--no-install", action="store_true",
                      dest="no_install", default=False,
                      help=_("Runs in 'no installation' mode. When run"
                      " in 'no installation' mode, no persistent changes are"
                      " made to the disks and booted environment\n"))
    options, args = parser.parse_args()
    if options.log_level is None:
        if options.debug:
            options.log_level = DEBUG_LOG_LEVEL
        else:
            options.log_level = DEFAULT_LOG_LEVEL
    try:
        options.log_level = setup_logging(options.logname, options.log_level)
    except IOError, err:
        parser.error("%s '%s'" % (err.strerror, err.filename))
    logging.debug("CLI options: log location = %s, verbosity = %s, debug "
                  "mode = %s, no install = %s, force_bw = %s",
                  options.logname, options.log_level, options.debug,
                  options.no_install, options.force_bw)
    init_log(0) # initialize old logging service
    profile = None
    try:
        with terminalui as initscr:
            win_size_y, win_size_x = initscr.getmaxyx()
            if win_size_y < 24 or win_size_x < 80:
                msg = _("     Terminal too small. Min size is 80x24."
                        " Current size is %(x)ix%(y)i.") % \
                        {'x': win_size_x, 'y': win_size_y}
                exit_text_installer(errcode=msg)
            prepare_engine(options)
            
            screen_list = ScreenList()
            actions = [Action(curses.KEY_F2, _("Continue"),
                              screen_list.get_next),
                       Action(curses.KEY_F3, _("Back"),
                              screen_list.previous_screen),
                       Action(curses.KEY_F6, _("Help"), screen_list.show_help),
                       Action(curses.KEY_F9, _("Quit"), screen_list.quit)]
            
            main_win = MainWindow(initscr, screen_list, actions,
                                  force_bw=options.force_bw)
            screen_list.help = HelpScreen(main_win, _("Help Topics"),
                                          _("Help Index"),
                                          _("Select a topic and press "
                                            "Continue."))
            win_list = make_screen_list(main_win)
            screen_list.help.setup_help_data(win_list)
            screen_list.screen_list = win_list
            screen = screen_list.get_next()
            ctrl_c = None
            doc = InstallEngine.get_instance().doc
            while screen is not None:
                profile = doc.get_descendants(name=INSTALL_PROF_LABEL,
                                              not_found_is_err=True)
                logging.debug("Install profile:\n%s", profile)
                logging.debug("Displaying screen: %s", type(screen))
                screen = screen.show()
                if not options.debug and ctrl_c is None:
                    # This prevents the user from accidentally hitting
                    # ctrl-c halfway through the install. Ctrl-C is left
                    # available through the first screen in case terminal
                    # display issues make it impossible for the user to
                    # quit gracefully
                    ctrl_c = signal.signal(signal.SIGINT, signal.SIG_IGN)
            errcode = 0
    except RebootException:
        reboot(platform.processor() == "i386")
    except SystemExit:
        raise
    except:
        logging.exception(str(profile))
        exc_type, exc_value = sys.exc_info()[:2]
        print _("An unhandled exception occurred.")
        if str(exc_value):
            print '\t%s: "%s"' % (exc_type.__name__, str(exc_value))
        else:
            print "\t%s" % exc_type.__name__
        print _("Full traceback data is in the installation log")
        print _("Please file a bug at http://defect.opensolaris.org")
        errcode = 1
    exit_text_installer(options.logname, errcode)

if __name__ == '__main__':
    main()

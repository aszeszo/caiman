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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#


'''System Configuration Interactive (SCI) Tool'''


import gettext

_ = gettext.translation("sysconfig", "/usr/share/locale",
                        fallback=True).ugettext
SCI_HELP = "/usr/share/sysconfig/help"


import atexit
import curses
import gettext
import locale
import logging
from optparse import OptionParser
import os
import signal
import sys

from solaris_install import engine
from solaris_install.engine import InstallEngine, RollbackError
from solaris_install.logger import FileHandler, INSTALL_LOGGER_NAME
from solaris_install.sysconfig.date_time import DateTimeScreen
from solaris_install.sysconfig.network_nic_configure import NICConfigure
from solaris_install.sysconfig.network_nic_select import NICSelect
from solaris_install.sysconfig.network_type import NetworkTypeScreen
from solaris_install.sysconfig.profile import ConfigProfile, SMFConfig, \
                                              SMFInstance, SMFPropertyGroup, \
                                              SMFProperty
from solaris_install.sysconfig.summary import SummaryScreen
from solaris_install.sysconfig.timezone import TimeZone
from solaris_install.sysconfig.users import UserScreen
from solaris_install.sysconfig.welcome import WelcomeScreen

import terminalui
from terminalui import LOG_LEVEL_INPUT, LOG_NAME_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.help_screen import HelpScreen
from terminalui.i18n import get_encoding, set_wrap_on_whitespace
from terminalui.main_window import MainWindow
from terminalui.screen_list import ScreenList


DEFAULT_LOG_LOCATION = "/var/tmp/install/sysconfig.log"
DEFAULT_LOG_LEVEL = "info"
LOG_FORMAT = ("%(asctime)s - %(levelname)-8s: "
              "%(filename)s:%(lineno)d %(message)s")
LOGGER = None
XSLT_FILE = os.environ.get('SC_XSLT',
                           '/usr/share/sysconfig/xslt/doc2sc_profile.xslt')
SC_FILE = os.environ.get('SC_FILE', '/tmp/sc_manifest.xml')
GENERATE_SC_PROFILE_CHKPOINT='generate-sc-profile'


# Public functions for consumers of sysconfig

def get_all_screens(main_win):
    '''Initializes a full set of screens'''
    
    result = []
    result.append(NetworkTypeScreen(main_win))
    result.append(NICSelect(main_win))
    result.append(NICConfigure(main_win))
    result.append(TimeZone(main_win, screen=TimeZone.REGIONS))
    result.append(TimeZone(main_win, screen=TimeZone.LOCATIONS))
    result.append(TimeZone(main_win))
    result.append(DateTimeScreen(main_win))
    result.append(UserScreen(main_win))
    
    return result


def register_checkpoint(sc_profile=SC_FILE, xslt=XSLT_FILE):
    '''Registers the GENERATE_SC_PROFILE_CHKPOINT checkpoint with the engine.
    Also adds config_profile to InstallEngine.doc.persistent'''
    eng = InstallEngine.get_instance()
    
    sc_kwargs = {'xslt_file' : xslt}
    sc_args = [sc_profile]
    eng.register_checkpoint(GENERATE_SC_PROFILE_CHKPOINT,
                            "solaris_install/manifest/writer",
                            "ManifestWriter", args=sc_args, kwargs=sc_kwargs)
    
    eng.doc.persistent.insert_children([ConfigProfile()])


# Private functions for use by /usr/bin/sysconfig

def _parse_options(arguments):
    usage = "usage: %prog [-l FILE] [-v LEVEL] [-n] [-b]"
    parser = OptionParser(usage=usage)
    
    parser.add_option("-l", "--log-location", dest="logname",
                      help=_("Set log location to FILE (default: %default)"),
                      metavar="FILE", default=DEFAULT_LOG_LOCATION)
    parser.add_option("-v", "--log-level", dest="log_level",
                      default=DEFAULT_LOG_LEVEL,
                      help=_("Set log verbosity to LEVEL. In order of "
                             "increasing verbosity, valid values are 'error' "
                             "'warn' 'info' 'debug' or 'input'\n[default:"
                             " %default]"),
                      choices=["error", "warn", "info", "debug", "input"],
                      metavar="LEVEL")
    parser.add_option("-b", "--no-color", action="store_true", dest="force_bw",
                      default=False, help=_("Force the tool to run in "
                      "black and white. This may be useful on some SPARC "
                      "machines with unsupported frame buffers\n"))
    parser.add_option("-n", action="store_true",
                      dest="dry_run", default=False,
                      help=_("Runs the tool, but does not apply the "
                             "configuration to the system.\n"))
    
    options, args = parser.parse_args(arguments)
    
    if args:
        parser.error("Unexpected positional argument(s): %s" % args)
    
    options.debug = (options.log_level.lower() in ['debug', 'input'])
    
    log_level = options.log_level.upper()
    if hasattr(logging, log_level):
        options.log_level = getattr(logging, log_level.upper())
    elif log_level == LOG_NAME_INPUT:
        options.log_level = LOG_LEVEL_INPUT
    else:
        raise IOError(2, "Invalid --log-level parameter", log_level.lower())
    
    return options


def _exit(logname, errcode=0):
    '''Close out the logger and exit with errcode'''
    LOGGER.info("**** END ****")
    # LOGGER.close() # LOGGER.close() is broken - CR 7012566
    print _("Exiting System Configuration Tool. Log is available at:\n"
            "%s") % logname
    if isinstance(errcode, unicode):
        # pylint: disable-msg=E1103
        errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def _make_screen_list(main_win):
    screens = []
    screens.append(WelcomeScreen(main_win))
    screens.extend(get_all_screens(main_win))
    screens.append(SummaryScreen(main_win))
    
    return screens


def _show_screens(options):
    with terminalui as initscr:
        win_size_y, win_size_x = initscr.getmaxyx()
        if win_size_y < 24 or win_size_x < 80:
            msg = _("     Terminal too small. Min size is 80x24."
                    " Current size is %(x)ix%(y)i.") % \
                    {'x': win_size_x, 'y': win_size_y}
            sys.exit(msg)
        screen_list = ScreenList()
        
        actions = [Action(curses.KEY_F2, _("Continue"), screen_list.get_next),
                   Action(curses.KEY_F3, _("Back"),
                          screen_list.previous_screen),
                   Action(curses.KEY_F6, _("Help"), screen_list.show_help),
                   Action(curses.KEY_F9, _("Quit"), screen_list.quit)]
        
        main_win = MainWindow(initscr, screen_list, actions,
                              force_bw=options.force_bw)
        screen_list.help = HelpScreen(main_win, _("Help Topics"),
                                      _("Help Index"),
                                      _("Select a topic and press Continue."))

        win_list = _make_screen_list(main_win)
        screen_list.help.setup_help_data(win_list)
        screen_list.screen_list = win_list
        screen = screen_list.get_next()
        
        ctrl_c = signal.signal(signal.SIGINT, signal.SIG_IGN)
        while screen is not None:
            eng = InstallEngine.get_instance()
            sc_prof = eng.doc.persistent.get_first_child(name="sysconfig")
            LOGGER.debug("Sysconfig profile:\n%s", sc_prof)
            LOGGER.debug("Displaying screen: %s", type(screen))
            screen = screen.show()


def _prepare_engine(options):
    '''Initialize the InstallEngine'''
    eng = InstallEngine(loglevel=options.log_level, debug=options.debug)
    
    
    logger = logging.getLogger(INSTALL_LOGGER_NAME)
    logger.addHandler(FileHandler(options.logname, mode='w'))
    
    # Don't set the global LOGGER until we're certain that logging
    # is up and running, so the main() except clause can figure out
    # if exception data can be written to the log or if it needs to
    # dump to stdout
    global LOGGER
    LOGGER = logger
    
    terminalui.init_logging(INSTALL_LOGGER_NAME)
    
    register_checkpoint()


def _init_locale():
    locale.setlocale(locale.LC_ALL, "")
    gettext.install("sysconfig", "/usr/share/locale", unicode=True)
    set_wrap_on_whitespace(_("DONT_TRANSLATE_BUT_REPLACE_msgstr_WITH_True_"
                             "OR_False: Should wrap text on whitespace in"
                             " this language"))
    BaseScreen.set_default_quit_text(_("Confirm: Quit?"),
                                     _("Do you really want to quit?"),
                                     _("Cancel"),
                                     _("Quit"))


def main():
    _init_locale()
    
    options = _parse_options(sys.argv[1:])
    
    if os.getuid() != 0:
        sys.exit(_("The System Configuration tool must be run "
                   "with root privileges"))
    
    try:
        _prepare_engine(options)
        _show_screens(options)
        _exit(options.logname, errcode=0)
    except SystemExit:
        raise
    except:
        if LOGGER is None:
            # Error occurred before logging is setup; no place to
            # dump the traceback
            raise
        LOGGER.exception(_("An unhandled exception occurred."))
        exc_type, exc_value = sys.exc_info()[:2]
        
        try:
            doc = InstallEngine.get_instance().doc.persistent
            sc_prof = doc.get_first_child(name="sysconfig")
            LOGGER.error("Sysconfig profile:\n%s", sc_prof)
        except:
            # Ignore any errors to avoid masking the original exception
            pass
        
        print _("An unhandled exception occurred.")
        if exc_value:
            print '\t%s: "%s"' % (exc_type.__name__, exc_value)
        else:
            print "\t%s" % exc_type.__name__
        print _("Full traceback data is in the log")
        _exit(options.logname, errcode=1)


if __name__ == '__main__':
    main()

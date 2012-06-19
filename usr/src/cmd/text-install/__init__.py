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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Text / (n)Curses based UI for installing Oracle Solaris
'''

import gettext
import os

from solaris_install import gpt_firmware_check, ApplicationData, \
    check_log_level
from solaris_install.getconsole import get_console, SERIAL_CONSOLE

#
# Determining whether LC_MESSAGES environment variable needs to be set
# or not must be done before the gettext.translation() call so the
# correct localized messages are used.
#
console_type = get_console()

#
# If running from a serial console, translation will be enabled.
# If running on a physical console, translation will
# be disabled by setting LC_MESSAGES to C
#
if console_type != SERIAL_CONSOLE:
    os.environ["LC_MESSAGES"] = "C"

# If True means this system is GPT boot capable. Typically False
# only if using an older OBP on SPARC.
can_use_gpt = gpt_firmware_check()

# Variables used by modules this module imports
# Defined here to avoid circular import errors
_ = gettext.translation("solaris_install_textinstall", "/usr/share/locale",
                        fallback=True).ugettext
RELEASE = {"release": _("Oracle Solaris")}
TUI_HELP = "/usr/share/text-install/help"

# Localized values used by other files
LOCALIZED_GB = _("GB")

# Names of registered checkpoints.
TARGET_DISCOVERY = "TargetDiscovery"
ISCSI_TARGET_DISCOVERY = "iSCSI TargetDiscovery"
TARGET_INIT = "TargetInitialization"
VARSHARE_DATASET = "VarShareDataset"
TRANSFER_PREP = "PrepareTransfer"
CLEANUP_CPIO_INSTALL = "cleanup-cpio-install"
INIT_SMF = "initialize-smf"
BOOT_CONFIG = "boot-configuration"
DUMP_ADMIN = "update-dump-admin"
DEVICE_CONFIG = "device-config"
APPLY_SYSCONFIG = "apply-sysconfig"
BOOT_ARCHIVE = "boot-archive"
TRANSFER_FILES = "transfer-ti-files"
CREATE_SNAPSHOT = "create-snapshot"

# DOC label
ISCSI_LABEL = "iSCSI"

import curses
import locale
import logging
import platform
import signal
import subprocess
import sys
import traceback

from optparse import OptionParser

import solaris_install.sysconfig as sysconfig

from solaris_install import Popen, CalledProcessError, post_install_logs_path
from solaris_install.ict.transfer_files import add_transfer_files_to_doc
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME, FileHandler
from solaris_install.target.controller import TargetController
from solaris_install.target.libbe.be import be_list
from solaris_install.target.physical import Iscsi
from solaris_install.target.size import Size
from solaris_install.text_install.discovery_selection import DiscoverySelection
from solaris_install.text_install.disk_selection import DiskScreen
from solaris_install.text_install.fdisk_partitions import FDiskPart
from solaris_install.text_install.gpt_partitions import GPTPart
from solaris_install.text_install.install_progress import InstallProgress
from solaris_install.text_install.install_status import InstallStatus, \
    RebootException
from solaris_install.text_install.iscsi import IscsiScreen
from solaris_install.text_install.log_viewer import LogViewer
from solaris_install.text_install.partition_edit_screen import \
    GPTPartEditScreen, PartEditScreen
from solaris_install.text_install.summary import SummaryScreen
from solaris_install.text_install.ti_install_utils import InstallData
from solaris_install.text_install.welcome import WelcomeScreen
from solaris_install.transfer.media_transfer import TRANSFER_ROOT, \
    TRANSFER_MISC, TRANSFER_MEDIA
import terminalui
from terminalui import LOG_LEVEL_INPUT, LOG_NAME_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen, QuitException
from terminalui.help_screen import HelpScreen
from terminalui.i18n import get_encoding, set_wrap_on_whitespace
from terminalui.main_window import MainWindow
from terminalui.screen_list import ScreenList


LOG_LOCATION_FINAL = post_install_logs_path('install_log')
DEFAULT_LOG_LOCATION = "/system/volatile/install_log"
DEFAULT_LOG_LEVEL = logging.INFO
DEBUG_LOG_LEVEL = logging.DEBUG
REBOOT = "/usr/sbin/reboot"

LOGGER = None


def exit_text_installer(logname=None, errcode=0):
    '''Teardown any existing iSCSI objects, Close out the logger and exit with
    errcode'''

    # get the Iscsi object from the DOC, if present.
    doc = InstallEngine.get_instance().doc
    iscsi = doc.volatile.get_first_child(name=ISCSI_LABEL, class_type=Iscsi)
    if iscsi:
        # The user exited prematurely, so try to tear down the Iscsi object
        try:
            LOGGER.debug("User has exited installer.  Tearing down "
                         "Iscsi object")
            iscsi.teardown()
        except CalledProcessError as err:
            # only print something to the screen if the errcode is nonzero
            if errcode != 0:
                print _("Unable to tear down iSCSI initiator:\n%s" % err)
            else:
                LOGGER.debug("Tearing down Iscsi object failed:  %s" % err)

    LOGGER.info("**** END ****")
    LOGGER.close()
    if logname is not None:
        print _("Exiting Text Installer. Log is available at:\n%s") % logname
    if isinstance(errcode, unicode):
        errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def make_screen_list(main_win, target_controller, install_data):
    '''Initialize the screen list. On x86, add screens for editing slices
    within a partition. Also, trigger the target discovery thread.
    '''

    result = list()
    result.append(WelcomeScreen(main_win, install_data))
    result.append(DiscoverySelection(main_win))
    result.append(IscsiScreen(main_win))
    disk_screen = DiskScreen(main_win, target_controller)
    result.append(disk_screen)
    result.append(FDiskPart(main_win, target_controller))
    result.append(GPTPart(main_win, target_controller))
    result.append(PartEditScreen(main_win, target_controller))
    result.append(GPTPartEditScreen(main_win, target_controller))
    if platform.processor() == "i386":
        result.append(FDiskPart(main_win, target_controller,
                                x86_slice_mode=True))
        result.append(PartEditScreen(main_win, target_controller,
                                     x86_slice_mode=True))
    result.extend(sysconfig.get_all_screens(main_win))

    # do not run target discovery until after all the sysconfig screens
    # are configured.  Otherwise, subprocess.Popen will be running
    # in parallel in multiple threads and it might lead to deadlock
    # as discussed in Python bug 2320.
    disk_screen.start_discovery()

    result.append(SummaryScreen(main_win))
    result.append(InstallProgress(main_win, install_data, target_controller))
    result.append(InstallStatus(main_win, install_data))
    result.append(LogViewer(main_win, install_data))
    return result


def _reboot_cmds(is_x86):
    '''Generate list of cmds to try fast rebooting'''
    cmds = list()

    for be_name, be_pool, root_ds, is_active in be_list():
        if is_active:
            if is_x86:
                cmds.append([REBOOT, "-f", "--", root_ds])
            else:
                # SPARC requires "-Z" before the root dataset
                cmds.append([REBOOT, "-f", "--", "-Z", root_ds])

    # Fallback reboot. If the subprocess.call(..) command above fails, simply
    # do a standard reboot.
    cmds.append([REBOOT])
    return cmds


def reboot(is_x86):
    '''Reboot the machine, attempting fast reboot first if available'''
    cmds = _reboot_cmds(is_x86)
    for cmd in cmds:
        try:
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                             logger=LOGGER)
        except (CalledProcessError):
            LOGGER.warn("Reboot failed:\n\t'%s'", " ".join(cmd))
        else:
            LOGGER.warn("Reboot failed:\n\t'%s'.\nWill attempt"
                        " standard reboot", " ".join(cmd))


def prepare_engine(options):
    ''' Instantiate the engine, setup logging, and register all
        the checkpoints to be used for doing the install.
    '''

    # Set up logging and initialize the InstallEngine
    work_dir = os.path.dirname(options.logname)
    logname = os.path.basename(options.logname)
    app_data = ApplicationData("text-install", work_dir=work_dir,
                               logname=logname)

    # Check to make sure the log levels are valid.
    if check_log_level(options.log_level):
        # This delineation is necessary because of the "INPUT" log
        # level that is available in the text installer. It won't
        # register as an integer, while the logging levels will.
        if isinstance(options.log_level, int):
            eng = InstallEngine(app_data.logname, loglevel=options.log_level,
                                debug=options.debug)
        else:
            eng = InstallEngine(app_data.logname, debug=options.debug)
    else:
        raise IOError(2, "Invalid --log-level parameter", options.log_level)

    doc = InstallEngine.get_instance().doc
    doc.persistent.insert_children(app_data)

    global LOGGER
    LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)
    LOGGER.info("**** START ****")

    terminalui.init_logging(INSTALL_LOGGER_NAME)

    # Information regarding checkpoints used for the Text Installer.
    # The values specified are used as arguments for registering the
    # checkpoint.  If function signature for any of the checkpoints are
    # is modified, these values need to be modified as well.
    eng.register_checkpoint(TARGET_DISCOVERY,
                            "solaris_install/target/discovery",
                            "TargetDiscovery")

    eng.register_checkpoint(TRANSFER_PREP,
                           "solaris_install/transfer/media_transfer",
                           "init_prepare_media_transfer")

    eng.register_checkpoint(VARSHARE_DATASET,
                            "solaris_install/target/varshare",
                            "VarShareDataset")

    eng.register_checkpoint(TARGET_INIT,
                            "solaris_install/target/instantiation",
                            "TargetInstantiation")

    # The following 3 are transfer checkpoints
    eng.register_checkpoint(TRANSFER_ROOT,
                           "solaris_install/transfer/cpio",
                           "TransferCPIO")

    eng.register_checkpoint(TRANSFER_MISC,
                           "solaris_install/transfer/cpio",
                           "TransferCPIO")

    eng.register_checkpoint(TRANSFER_MEDIA,
                            "solaris_install/transfer/cpio",
                            "TransferCPIO")

    # sys config checkpoint must be registered after transfer checkpoints
    sysconfig.register_checkpoint()

    # rest of the checkpoints are for finishing up the install process
    eng.register_checkpoint(CLEANUP_CPIO_INSTALL,
                            "solaris_install/ict/cleanup_cpio_install",
                            "CleanupCPIOInstall")

    eng.register_checkpoint(INIT_SMF,
                            "solaris_install/ict/initialize_smf",
                            "InitializeSMF")

    eng.register_checkpoint(BOOT_CONFIG,
                            "solaris_install/boot/boot",
                            "SystemBootMenu")

    eng.register_checkpoint(DUMP_ADMIN,
                            "solaris_install/ict/update_dumpadm",
                            "UpdateDumpAdm")

    eng.register_checkpoint(DEVICE_CONFIG,
                            "solaris_install/ict/device_config",
                            "DeviceConfig")

    eng.register_checkpoint(APPLY_SYSCONFIG,
                            "solaris_install/ict/apply_sysconfig",
                            "ApplySysConfig")

    eng.register_checkpoint(BOOT_ARCHIVE,
                            "solaris_install/ict/boot_archive",
                            "BootArchive")

    # Build up list of files to be added to DataObjectCache for transfer
    # to new boot environment.
    tf_dict = dict()
    tf_dict['/var/adm/messages'] = post_install_logs_path('messages')
    add_transfer_files_to_doc(TRANSFER_FILES, tf_dict)
    eng.register_checkpoint(TRANSFER_FILES,
                            "solaris_install/ict/transfer_files",
                            "TransferFiles")

    eng.register_checkpoint(CREATE_SNAPSHOT,
                            "solaris_install/ict/create_snapshot",
                            "CreateSnapshot")


def init_locale():

    locale.setlocale(locale.LC_ALL, "")
    gettext.install("solaris_install_textinstall",
                    "/usr/share/locale",
                    unicode=True)
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
        prepare_engine(options)
    except IOError, err:
        parser.error("%s '%s'" % (err.strerror, err.filename))
    LOGGER.debug("CLI options: log location = %s, verbosity = %s, debug "
                 "mode = %s, no install = %s, force_bw = %s",
                 options.logname, options.log_level, options.debug,
                 options.no_install, options.force_bw)

    install_data = InstallData()
    install_data.log_location = options.logname
    install_data.log_final = LOG_LOCATION_FINAL
    install_data.no_install_mode = options.no_install

    try:
        with terminalui as initscr:
            win_size_y, win_size_x = initscr.getmaxyx()
            if win_size_y < 24 or win_size_x < 80:
                msg = _("     Terminal too small. Min size is 80x24."
                        " Current size is %(x)ix%(y)i.") % \
                        {'x': win_size_x, 'y': win_size_y}
                exit_text_installer(errcode=msg)

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
            doc = InstallEngine.get_instance().doc

            debug_tc = False
            if options.debug:
                debug_tc = True
            target_controller = TargetController(doc, debug=debug_tc,
                                                 dry_run=options.no_install)

            win_list = make_screen_list(main_win, target_controller,
                                        install_data)
            screen_list.help.setup_help_data(win_list)
            screen_list.screen_list = win_list
            screen = screen_list.get_next()
            ctrl_c = None
            errcode = 0
            while screen is not None:
                LOGGER.debug("Displaying screen: %s", type(screen))
                screen = screen.show()
                if not options.debug and ctrl_c is None:
                    # This prevents the user from accidentally hitting
                    # ctrl-c halfway through the install. Ctrl-C is left
                    # available through the first screen in case terminal
                    # display issues make it impossible for the user to
                    # quit gracefully
                    ctrl_c = signal.signal(signal.SIGINT, signal.SIG_IGN)
    except QuitException:
        LOGGER.info("User quit the installer.")
    except RebootException:
        reboot(platform.processor() == "i386")
    except SystemExit:
        raise
    except:
        LOGGER.info(str(InstallEngine.get_instance().doc))
        LOGGER.info(str(install_data))
        LOGGER.exception("Install failed")
        exc_type, exc_value = sys.exc_info()[:2]
        print _("An unhandled exception occurred.")
        if str(exc_value):
            print '\t%s: "%s"' % (exc_type.__name__, str(exc_value))
        else:
            print "\t%s" % exc_type.__name__
        print _("Full traceback data is in the installation log")
        errcode = 1
    exit_text_installer(options.logname, errcode)

if __name__ == '__main__':
    main()

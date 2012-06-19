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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Gtk+ based UI for installing Oracle Solaris
'''

import pygtk
pygtk.require('2.0')

import __builtin__
import gettext
# Set up translation functionality.
__builtin__._ = gettext.gettext
import locale
import logging
from optparse import OptionParser
import os
import sys

import g11nsvc
import gtk

import osol_install.errsvc as errsvc
from solaris_install import ApplicationData, CalledProcessError, Popen, \
    post_install_logs_path, run, check_log_level
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.gui_install_common import exit_gui_install, \
    modal_dialog, other_instance_is_running, start_td_local, write_pid_file, \
    CLEANUP_CPIO_INSTALL, DEBUG_LOG_LEVEL, DEFAULT_LOG_LEVEL, \
    DEFAULT_LOG_LOCATION, GLADE_DIR, LOG_FORMAT, LOG_LEVEL_INPUT, \
    LOG_NAME_INPUT, LOGNAME, RELEASE, TARGET_DISCOVERY, TRANSFER_PREP, \
    VARSHARE_DATASET
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.gui_install.screen_manager import ScreenManager
from solaris_install.ict.transfer_files import add_transfer_files_to_doc
from solaris_install.logger import INSTALL_LOGGER_NAME, FileHandler
import solaris_install.sysconfig as sysconfig

# setup target instantiation checkpoint dictionary
TI_CHKPS = dict()
TI_CHKPS[TARGET_DISCOVERY] = (TARGET_DISCOVERY,
                              "solaris_install/target/discovery",
                              "TargetDiscovery")

TI_CHKPS[TRANSFER_PREP] = (TRANSFER_PREP,
                           "solaris_install/transfer/media_transfer",
                           "init_prepare_media_transfer")

TI_CHKPS[VARSHARE_DATASET] = (VARSHARE_DATASET,
                              "solaris_install/target/varshare",
                              "VarShareDataset")

TARGET_INIT = "TargetInitialization"
TI_CHKPS[TARGET_INIT] = (TARGET_INIT,
                         "solaris_install/target/instantiation",
                         "TargetInstantiation")

TRANSFER_ROOT = "transfer-root"
TI_CHKPS[TRANSFER_ROOT] = (TRANSFER_ROOT,
                           "solaris_install/transfer/cpio",
                           "TransferCPIO")

TRANSFER_MISC = "transfer-misc"
TI_CHKPS[TRANSFER_MISC] = (TRANSFER_MISC,
                           "solaris_install/transfer/cpio",
                           "TransferCPIO")

GENERATE_SC_PROFILE_CHKPOINT = 'generate-sc-profile'

TRANSFER_MEDIA = "transfer-media"
TI_CHKPS[TRANSFER_MEDIA] = (TRANSFER_MEDIA,
                            "solaris_install/transfer/cpio",
                            "TransferCPIO")

TI_CHKPS[CLEANUP_CPIO_INSTALL] = (CLEANUP_CPIO_INSTALL,
                      "solaris_install/ict/cleanup_cpio_install",
                      "CleanupCPIOInstall")

INIT_SMF = "initialize-smf"
TI_CHKPS[INIT_SMF] = (INIT_SMF,
                      "solaris_install/ict/initialize_smf",
                      "InitializeSMF")

BOOT_CONFIG = "boot-configuration"
TI_CHKPS[BOOT_CONFIG] = (BOOT_CONFIG,
                         "solaris_install/boot/boot",
                         "SystemBootMenu")

DUMP_ADMIN = "update-dump-admin"
TI_CHKPS[DUMP_ADMIN] = (DUMP_ADMIN,
                        "solaris_install/ict/update_dumpadm",
                        "UpdateDumpAdm")

DEVICE_CONFIG = "device-config"
TI_CHKPS[DEVICE_CONFIG] = (DEVICE_CONFIG,
                           "solaris_install/ict/device_config",
                           "DeviceConfig")

APPLY_SYSCONFIG = "apply-sysconfig"
TI_CHKPS[APPLY_SYSCONFIG] = (APPLY_SYSCONFIG,
                             "solaris_install/ict/apply_sysconfig",
                             "ApplySysConfig")

BOOT_ARCHIVE = "boot-archive"
TI_CHKPS[BOOT_ARCHIVE] = (BOOT_ARCHIVE,
                          "solaris_install/ict/boot_archive",
                          "BootArchive")

TRANSFER_FILES = "transfer-gui-files"
TI_CHKPS[TRANSFER_FILES] = (TRANSFER_FILES,
                            "solaris_install/ict/transfer_files",
                            "TransferFiles")

CREATE_SNAPSHOT = "create-snapshot"
TI_CHKPS[CREATE_SNAPSHOT] = (CREATE_SNAPSHOT,
                             "solaris_install/ict/create_snapshot",
                             "CreateSnapshot")


def setup_checkpoints():
    '''Sets up the checkpoints for the installation within the install engine
    '''
    logger = logging.getLogger(INSTALL_LOGGER_NAME)
    engine = InstallEngine.get_instance()
    logger.debug("**** Establishing checkpoints ****")
    logger.debug("Establishing the " + TARGET_DISCOVERY + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TARGET_DISCOVERY]))
    logger.debug("Establishing the " + TRANSFER_PREP + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TRANSFER_PREP]))
    logger.debug("Establishing the " + VARSHARE_DATASET + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[VARSHARE_DATASET]))
    logger.debug("Establishing the " + TARGET_INIT + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TARGET_INIT]))
    logger.debug("Establishing the " + TRANSFER_ROOT + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TRANSFER_ROOT]))
    logger.debug("Establishing the " + TRANSFER_MISC + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TRANSFER_MISC]))
    logger.debug("Establishing the " + TRANSFER_MEDIA + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[TRANSFER_MEDIA]))
    logger.debug("Establishing the " + GENERATE_SC_PROFILE_CHKPOINT + \
                " checkpoint")
    sysconfig.register_checkpoint()
    logger.debug("Establishing the " + CLEANUP_CPIO_INSTALL + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[CLEANUP_CPIO_INSTALL]))
    logger.debug("Establishing the " + INIT_SMF + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[INIT_SMF]))
    logger.debug("Establishing the " + BOOT_CONFIG + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[BOOT_CONFIG]))
    logger.debug("Establishing the " + DUMP_ADMIN + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[DUMP_ADMIN]))
    logger.debug("Establishing the " + DEVICE_CONFIG + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[DEVICE_CONFIG]))
    logger.debug("Establishing the " + APPLY_SYSCONFIG + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[APPLY_SYSCONFIG]))
    logger.debug("Establishing the " + BOOT_ARCHIVE + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[BOOT_ARCHIVE]))
    logger.debug("Establishing the " + TRANSFER_FILES + " checkpoint")
    # Build up list of files to be added to DataObjectCache for transfer
    # to new boot environment.
    tf_dict = dict()
    tf_dict['/var/adm/messages'] = post_install_logs_path('messages')
    add_transfer_files_to_doc(TRANSFER_FILES, tf_dict)
    engine.register_checkpoint(*(TI_CHKPS[TRANSFER_FILES]))
    logger.debug("Establishing the " + CREATE_SNAPSHOT + " checkpoint")
    engine.register_checkpoint(*(TI_CHKPS[CREATE_SNAPSHOT]))
    logger.debug("**** Checkpoints Established ****")


def init_install_profile():
    '''
        Initialize the profile for storing user-entered details.
        Assumes that InstallEngine has been instantiated first.
    '''
    data_object_name = "GUI Install"

    engine = InstallEngine.get_instance()
    doc = engine.data_object_cache

    # Clear out any other "GUI Install" InstallProfiles in the
    # DOC - there should only be one.
    doc.volatile.delete_children(
        name=data_object_name,
        class_type=InstallProfile)

    profile = InstallProfile(data_object_name)
    doc.volatile.insert_children(profile)


def save_locale_in_doc():
    '''Saves the current locale set by the user from the locale screen upon
       initial boot into the DOC.'''
    # get the current locale
    locale_ops = g11nsvc.G11NSvcLocaleOperations()

    locale_ops.setlocale(localename=os.environ['LANG'])
    the_locale = locale_ops.getlocale()
    locale_description = locale_ops.get_territory_desc(the_locale, the_locale)

    # Save the locale details to the DOC
    engine = InstallEngine.get_instance()
    doc = engine.data_object_cache
    profile = doc.volatile.get_first_child(
        name="GUI Install",
        class_type=InstallProfile)
    if profile is None:
        SystemExit("Internal Error, GUI Install DOC not found")

    profile.set_locale_data([locale_description], [the_locale], the_locale)


def _init_locale():
    '''Initialize the locale for gui-install'''
    locale.setlocale(locale.LC_ALL, "")
    gettext.install("solaris_install_guiinstall",
                    "/usr/share/locale",
                    unicode=True)


def main():
    '''Main routine for the gui-install-er'''
    _init_locale()

    # This is needed or InstallEngine threading won't work
    gtk.gdk.threads_init()

    # check we are running as root
    if os.getuid() != 0:
        sys.exit(_("The %s installer must be run as "
                   "root. Quitting.") % RELEASE)

    if other_instance_is_running():
        modal_dialog(
            _("Installer Startup Terminated"),
            _("Only one instance of this Installer is allowed. "
            "Another instance is already running."))
        sys.exit(_("Only one instance of this Installer is allowed. "
            "Another instance is already running."))

    write_pid_file()

    usage = "usage: %prog [-l FILE] [-v LEVEL] [-d]"
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
    options, args = parser.parse_args()

    # Initialize the Engine and set up logging
    work_dir = os.path.dirname(options.logname)
    logname = os.path.basename(options.logname)
    app_data = ApplicationData("gui-install", work_dir=work_dir,
                               logname=logname)

    if options.log_level is None:
        if options.debug:
            options.log_level = DEBUG_LOG_LEVEL
        else:
            options.log_level = DEFAULT_LOG_LEVEL
        InstallEngine(app_data.logname, loglevel=options.log_level, debug=True)
    elif check_log_level(options.log_level):
        InstallEngine(app_data.logname, loglevel=options.log_level,
                      debug=options.debug)
    else:
        raise IOError(2, "Invalid --log-level parameter", options.log_level)

    doc = InstallEngine.get_instance().doc
    doc.persistent.insert_children(app_data)

    logger = logging.getLogger(INSTALL_LOGGER_NAME)
    logger.info("**** START ****")

    logger.debug("CLI options: log location = %s, verbosity = %s, debug "
        "mode = %s", app_data.logname,
        logging.getLevelName(options.log_level).lower(), options.debug)

    setup_checkpoints()
    manager = ScreenManager(app_data.logname)

    start_td_local()

    init_install_profile()
    save_locale_in_doc()
    manager.main()

    exit_gui_install(logname=app_data.logname, errcode=0)

if __name__ == '__main__':
    main()

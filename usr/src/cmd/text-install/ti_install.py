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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Installation engine for Text Installer
'''

import curses
import os
import logging
import datetime
import shutil

from select import select

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
import solaris_install.sysconfig as sysconfig

from osol_install.libzoneinfo import tz_isvalid
from solaris_install import Popen
from solaris_install.engine import InstallEngine
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.target.controller import TargetController
from solaris_install.target.size import Size
from solaris_install.target.libbe.be import be_unmount
from solaris_install.text_install import TRANSFER_PREP, \
    VARSHARE_DATASET, CLEANUP_CPIO_INSTALL
from solaris_install.text_install import ti_install_utils as ti_utils
from solaris_install.text_install.progress import InstallProgressHandler
from solaris_install.text_install.ti_target_utils import \
    get_desired_target_disk, get_desired_target_zpool, get_desired_target_be, \
    get_solaris_gpt_partition, get_solaris_slice, ROOT_POOL
from solaris_install.transfer.info import Software, IPSSpec

LOGGER = None

#
# Handle for accessing the InstallStatus class
#
INSTALL_STATUS = None


def exec_callback(status, failed_cp):
    ''' callback function for engine.execute_checkpoints '''

    LOGGER.debug("exec_callback parameters:")
    LOGGER.debug("status: %s", status)
    LOGGER.debug("failed_cp: %s", failed_cp)

    # check the result of execution
    INSTALL_STATUS.exec_status = status
    INSTALL_STATUS.stop_report_status()

    if status == InstallEngine.EXEC_FAILED:
        for fcp in failed_cp:
            err_data = (errsvc.get_errors_by_mod_id(fcp))[0]
            LOGGER.error("Checkpoint %s failed" % fcp)
            err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
            LOGGER.error(err)


class InstallStatus(object):
    '''Stores information on the installation progress, and provides a
    hook for updating the screen.
    '''

    def __init__(self, screen, update_status_func):
        '''screen and update_status_func are values passed in from
        the main app
        '''

        self.screen = screen
        self.update_status_func = update_status_func
        self.prog_handler = InstallProgressHandler(LOGGER)
        self.prog_handler.startProgressServer()
        self.exec_status = InstallEngine.EXEC_SUCCESS
        LOGGER.addHandler(self.prog_handler)

    def report_status(self):
        '''Update the install status. Also checks the quit_event to see
        if the installation should be aborted.

        '''
        try:
            processing_quit = False
            while self.prog_handler.server_up:
                if not processing_quit:
                    ready_to_read = select([self.prog_handler.engine_skt],
                                           [], [], 0.25)[0]
                    if len(ready_to_read) > 0:
                        percent, msg = self.prog_handler.parseProgressMsg(\
                            ready_to_read[0])
                        LOGGER.debug("message = %s", msg)
                        LOGGER.debug("percent = %s", percent)
                        self.update_status_func(float(percent), msg)

                # check whether F9 is pressed
                input_key = self.screen.main_win.getch()
                if input_key == curses.KEY_F9:
                    LOGGER.info("User selected Quit")
                    really_quit = self.screen.confirm_quit()
                    if really_quit:
                        LOGGER.info("User confirmed Quit")
                        engine = InstallEngine.get_instance()
                        engine.cancel_checkpoints()
                        processing_quit = True
        except Exception:
            LOGGER.exception("progressServer Error")

    def stop_report_status(self):
        self.prog_handler.stopProgressServer()


def do_ti_install(install_data, screen, update_status_func):
    '''Installation engine for text installer.
       Raises InstallationError for any error occurred during install.
    '''

    sysconfig_profile = sysconfig.profile.from_engine()

    #
    # The following information is needed for installation.
    # Make sure they are provided before even starting
    #

    # timezone
    timezone = sysconfig_profile.system.tz_timezone
    LOGGER.debug("time zone: %s", timezone)

    # Validate the value specified for timezone
    if not tz_isvalid(timezone):
        LOGGER.error("Timezone value specified (%s) is not valid", timezone)
        raise ti_utils.InstallationError

    # Compute the time to set.
    install_time = datetime.datetime.now() + \
        sysconfig_profile.system.time_offset

    # Set the system time to the time specified by the user.
    cmd = ["/usr/bin/date", install_time.strftime("%m%d%H%M%y")]
    Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                     logger=LOGGER)

    hostname = sysconfig_profile.system.hostname
    LOGGER.debug("hostname: " + hostname)

    engine = InstallEngine.get_instance()
    doc = engine.doc

    # look to see if the target disk has 'whole_disk' set
    disk = get_desired_target_disk(doc)
    if disk.whole_disk:
        inst_device_size = disk.disk_prop.dev_size
    else:
        # look for a GPT partition first
        gpt_partition = get_solaris_gpt_partition(doc)

        if gpt_partition is None:
            solaris_slice = get_solaris_slice(doc)
            if solaris_slice is None:
                raise ti_utils.InstallationError("Unable to find solaris "
                                                 "slice")
            inst_device_size = solaris_slice.size
        else:
            inst_device_size = gpt_partition.size

    LOGGER.info("Installation Device Size: %s", inst_device_size)

    minimum_size = screen.tc.minimum_target_size
    LOGGER.info("Minimum required size: %s", minimum_size)
    if inst_device_size < minimum_size:
        LOGGER.error("Size of device specified for installation "
                     "is too small")
        LOGGER.error("Size of install device: %s", inst_device_size)
        LOGGER.error("Minimum required size: %s", minimum_size)
        raise ti_utils.InstallationError

    recommended_size = screen.tc.recommended_target_size
    LOGGER.info("Recommended size: %s", recommended_size)
    if inst_device_size < recommended_size:
        # Warn users that their install target size is not optimal
        # Just log the warning, but continue with the installation.
        LOGGER.warning("Size of device specified for installation is "
                       "not optimal")
        LOGGER.warning("Size of install device: %s", inst_device_size)
        LOGGER.warning("Recommended size: %s", recommended_size)

    (swap_type, swap_size, dump_type, dump_size) = \
        screen.tc.calc_swap_dump_size(minimum_size, inst_device_size,
                                      swap_included=True)

    desired_zpool = get_desired_target_zpool(doc)
    if swap_type == TargetController.SWAP_DUMP_ZVOL:
        desired_zpool.add_zvol("swap", swap_size.get(Size.mb_units),
                               Size.mb_units, use="swap")

    if dump_type == TargetController.SWAP_DUMP_ZVOL:
        desired_zpool.add_zvol("dump", dump_size.get(Size.mb_units),
                               Size.mb_units, use="dump",
                               create_failure_ok=True)

    LOGGER.info("Swap type: %s", swap_type)
    LOGGER.info("Swap size: %s", swap_size)
    LOGGER.info("Dump type: %s", dump_type)
    LOGGER.info("Dump size: %s", dump_size)

    # Specify for the shared datasets <root_pool>/export and
    # <root_pool>/export/home be created.  We will specify
    # a mountpoint for <root_pool>/export dataset.
    # We must not specify a mountpoint for <root_pool>/export/home.
    # It should inherit the mountpoint from <root_pool>/export.

    desired_zpool.add_filesystem("export", mountpoint="/export")
    desired_zpool.add_filesystem("export/home")

    # Add the list of packages to be removed after the install to the DOC
    pkg_remove_list = ['pkg:/system/install/media/internal',
                       'pkg:/system/install/text-install']
    pkg_spec = IPSSpec(action=IPSSpec.UNINSTALL, contents=pkg_remove_list)
    pkg_rm_node = Software(CLEANUP_CPIO_INSTALL, type="IPS")
    pkg_rm_node.insert_children(pkg_spec)
    doc.volatile.insert_children(pkg_rm_node)

    # execute the prepare transfer checkpoint.  This checkpoint must be
    # executed by itself, before executing any of the transfer related
    # checkpoints.  The transfer checkpoints requires data setup from the
    # prepare transfer checkpoint.
    status, failed_cp = engine.execute_checkpoints(
        start_from=TRANSFER_PREP, pause_before=VARSHARE_DATASET)

    if status != InstallEngine.EXEC_SUCCESS:
        err_data = errsvc.get_errors_by_mod_id(TRANSFER_PREP)[0]
        LOGGER.error("%s checkpoint failed" % TRANSFER_PREP)
        err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
        LOGGER.error(err)
        raise ti_utils.InstallationError("Failed to execute checkpoint "
                                         "%s", TRANSFER_PREP)

    global INSTALL_STATUS
    INSTALL_STATUS = InstallStatus(screen, update_status_func)

    LOGGER.debug("Executing rest of checkpoints")

    engine.execute_checkpoints(callback=exec_callback,
        dry_run=install_data.no_install_mode)

    INSTALL_STATUS.report_status()

    if INSTALL_STATUS.exec_status is InstallEngine.EXEC_CANCELED:
        raise ti_utils.InstallationCanceledError("User selected cancel.")

    if INSTALL_STATUS.exec_status is InstallEngine.EXEC_FAILED:
        raise ti_utils.InstallationError("Failed executing checkpoints")

    if install_data.no_install_mode:
        # all subsequent code depends on the install target being setup
        return

    new_be = get_desired_target_be(doc)
    install_mountpoint = new_be.mountpoint

    # If swap was created, add appropriate entry to <target>/etc/vfstab
    LOGGER.debug("install mountpoint: %s", install_mountpoint)
    LOGGER.debug("new_be: %s", new_be)
    screen.tc.setup_vfstab_for_swap(ROOT_POOL, install_mountpoint)

    post_install_cleanup(install_data)


def post_install_cleanup(install_data):
    '''Do final cleanup to prep system for first boot '''

    # make sure we are not in the alternate root.
    # Otherwise, be_unmount() fails
    os.chdir("/root")

    doc = InstallEngine.get_instance().doc
    new_be = get_desired_target_be(doc)

    # Transfer the log file
    final_log_loc = new_be.mountpoint + install_data.log_final
    LOGGER.debug("Copying %s to %s" % (install_data.log_location,
                  final_log_loc))
    try:
        shutil.copyfile(install_data.log_location, final_log_loc)
    except (IOError, OSError) as err:
        LOGGER.error("Failed to copy %s to %s" % (install_data.log_location,
                      install_data.log_final))
        LOGGER.exception(err)
        raise ti_utils.InstallationError

    be_unmount(new_be.name)


def perform_ti_install(install_data, screen, update_status_func):
    '''Wrapper to call the do_ti_install() function.
       Sets the variable indicating whether the installation is successful or
       not.
    '''

    global LOGGER
    LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

    try:
        do_ti_install(install_data, screen, update_status_func)
        install_data.install_succeeded = True
        LOGGER.info("Install completed successfully")
    except ti_utils.InstallationCanceledError:
        install_data.install_succeeded = False
        LOGGER.info("Install canceled by user.")
    except Exception:
        LOGGER.exception("Install FAILED.")
        install_data.install_succeeded = False

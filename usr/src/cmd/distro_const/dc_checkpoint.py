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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
#
"""dc_checkpoint.py - Distribution constructor code to deal with the
    checkpointing functionality.

"""
import os
from subprocess import Popen, PIPE, call 
import shutil
import filecmp
import logging
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.dc_utils import get_manifest_boolean

from osol_install.distro_const.dc_defs import DC_LOGGER_NAME, BUILD_DATA, \
    FINALIZER_CHECKPOINT_SCRIPT, FINALIZER_ROLLBACK_SCRIPT, \
    FINALIZER_SCRIPT_NAME_TO_ARGSLIST, FINALIZER_SCRIPT_NAME, \
    FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_MESSAGE, \
    FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_NAME, GENERAL_ERR, SUCCESS, \
    STOP_ON_ERR, CHECKPOINT_ENABLE
# =============================================================================
class Step:
# =============================================================================
    """Step contains the information needed for each different checkpoint step.
    The number of steps on the system is determined by the number of
    checkpoints the user wishes to create.

       _step_num  - number of the checkpoint. Increments by one for
                           each successive step.
       _step_name - name associated with this step. If no name is given it
                           will default to the text version of the number.
       _message - Message to be printed to indicate which step the build is
                           on.
       _state_file - Name of the file to copy the manifest file to for this
                           step. It is equal to .step_<_step_name>
       _zfs_snapshots - Name of the zfs snapshot. It is equal to the
                           zfs_dataset_name@step_<_step_name>

    """
    step_num = 0

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_step_num(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the step number. """
        return self._step_num

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_step_name(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the name of the step."""
        return self._step_name

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_step_message(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the message associated with the step."""
        return self._message

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_state_file(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the name of the state file for this step."""
        return self._state_file

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_zfs_snapshot(self, num):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the name of the zfs snapshot associated with the step."""
        return self._zfs_snapshots[num]

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_zfs_snapshot_list(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the list of the zfs snapshots associated with the step."""
        return self._zfs_snapshots

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, step_name, message, state_file,
                 zfs_dataset):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self._step_num = Step.step_num
        self._step_name = step_name
        self._message = message
        self._state_file = state_file
        self._zfs_snapshots = []
        for i, zfs_dataset_name in enumerate(zfs_dataset) :
            self._zfs_snapshots.insert(i, "%s@%s" % (zfs_dataset_name,
                                       ".step_" + step_name))
        Step.step_num += 1


# =============================================================================
class Checkpoints:
# =============================================================================
    """Class to hold all of the checkpoint info.
        step_list = Information for each step.
        _resume_step = step to resume executing at.
        _pause_step= step to stop executing at.
        _current_step = step currently executing.
        _manifest_file = name of the manifest file that holds the
            configuration information
        _checkpoint_avail = Tells if checkpointing is available.
        _zfs_found = Is zfs on the system?
        _build_area_mntpt = mount point for the build area
        _build_area_dataset = zfs dataset for the build area

    """
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def incr_current_step(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Increment the value of the step executing."""
        self._current_step += 1

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_current_step(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the value of the step currently executing."""
        return self._current_step

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_resume_step(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the step to resume execution from."""
        return self._resume_step

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_resume_step(self, num):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the step to resume execution from to the number
        passed in.

        """
        self._resume_step = num

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_pause_step(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the step to pause execution at."""
        return self._pause_step

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_pause_step(self, num):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the step to pause execution at to the number passed in."""
        self._pause_step = num

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_manifest(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the name of the manifest file."""
        return self._manifest_file

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_manifest(self, manifest):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the name of the manifest file to the value passed in."""
        self._manifest_file = manifest

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_checkpointing_avail(self, flag):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the flag that indicates if checkpointing is available
        or not.

        """
        self._checkpoint_avail = flag

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_checkpointing_avail(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the value of the flag that indicates if checkpointing is
        available or not.

        """
        return self._checkpoint_avail

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_zfs_found(self, flag):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the flag that indicates if zfs was found on the system.""" 
        self._zfs_found = flag

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_zfs_found(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the flag that indicates if zfs was found on the
        system.

        """ 
        return self._zfs_found

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_build_area_mntpt(self, mntpt):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the value of the build area mountpoint."""
        self._build_area_mntpt = mntpt

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_build_area_mntpt(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the value of the build area mountpoint."""
        return self._build_area_mntpt

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_build_area_dataset(self, dataset):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Set the value of the location of the build area zfs dataset."""
        self._build_area_dataset = dataset

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_build_area_dataset(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Return the value of the location of the build area zfs
        dataset.

        """
        return self._build_area_dataset

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def step_setup(self, message, name, zfs_dataset):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Setup the step structure with the basic information needed
        to create a step.
        message - Message to print out at start of the step.
                i.e. "Downloading IPS packages"
        name - User friendly name for the step.
        zfs_dataset - Name of the zfs dataset.

        """

        # The .step files goes at the root directory of the image area.
        build_area = self.get_build_area_mntpt()
        state_file = build_area + "/.step_" + name
        self.step_list.append(Step(name, message, state_file, zfs_dataset))

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def create_checkpoint(self, name):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Create a checkpoint. This involves creating a zfs snapshot and
        copying the manifest file to the .step_<name> file.
        name - name of the checkpoint
        Returns 0 on success
                non zero error code on error

        """
        # If zfs is not on the system, we just skip the portion that
        # creates the the checkpoint and continue on building.
        dc_log = logging.getLogger(DC_LOGGER_NAME)
        if not self.get_checkpointing_avail(): 
            return 0
        pausestep = self.get_pause_step()
        for step_obj in self.step_list:
            if name == step_obj.get_step_name():
                stepnum = step_obj.get_step_num()
                for zfs_snapshot in step_obj.get_zfs_snapshot_list():
                    ret = shell_cmd("/usr/sbin/zfs snapshot " +
                                    zfs_snapshot, dc_log)
                    if ret :
                        return ret
                    shutil.copy(
                         self.get_manifest(),
                         step_obj.get_state_file())
                if pausestep == stepnum:
                    dc_log.info("Stopping at %s" % name)
                else:
                    dc_log.info("==== %s: %s" % (name,
                                step_obj.get_step_message()))
                self.incr_current_step()
                return 0
        dc_log.info("Unable to create checkpoint for %s. " % name)
        dc_log.info("You will not be able to resume from this step.")
        return 0

    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self):
    #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self._resume_step = -1
        self._pause_step = 9999
        self._current_step = 0
        self._manifest_file = ""
        self._build_area_mntpt = ""
        self._build_area_dataset = None
        self._checkpoint_avail = True
        self._zfs_found = True
        self.step_list = []


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def shell_cmd(cmd, log_handler):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Execute a shell command
    Input:
        cmd - string specifying the command to execute

    """
    try:
        ret = call(cmd, shell=True)
    except OSError, err:
        log_handler.error(cmd + " execution failed:", str(err))
    return ret

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def step_from_name(cp, name) :
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Determine the step, given the step name. Each step has a
    unique number and name. Search through the step_list for the given
    name and return the step. If a step with the given name can't be found
    the user must have specified an invalid name. Print a message telling
    them this.
    Input:
        name - name of the step to find.
    Return:
        the step.
        None

    """
    for step_obj in cp.step_list:
        if name == step_obj.get_step_name():
            return step_obj
    if name.isdigit():
        try:
            stepno = int(name)
            for step_obj in cp.step_list:
                if stepno == step_obj.get_step_num():
                    return step_obj
        except (TypeError, ValueError):
            pass
    dc_log = logging.getLogger(DC_LOGGER_NAME)
    dc_log.error("An invalid step (%s) was specified." % name)
    dc_log.error("Valid step names are: ")
    for step_obj in cp.step_list :
        dc_log.error(step_obj.get_step_name())
    return None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def snapshot_list(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Return a list of snapshots associated with the build area. Snapshots
    will be in creation time order (earliest first)
    Cull out the empty snapshot by only looking for the .step_ ones.

    Returns:
            list of snapshot names
            -1 on error

    """
    dc_log = logging.getLogger(DC_LOGGER_NAME)
    cmd =  "/usr/sbin/zfs list -s creation -t snapshot -o name " + \
           "| grep " + cp.get_build_area_dataset() + BUILD_DATA + \
           "@.step_"

    try:
        snap_list = Popen(cmd, shell=True,
                              stdout=PIPE).communicate()[0].rsplit("\n")
    except OSError:
        dc_log.error("Failed to obtain the list of zfs snapshots")
        return -1

    return snap_list

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def determine_resume_step(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Determine which step to resume from. If the user specifies to resume
    at the latest step via dist-const -r ./manifest_file, then we
    need to determine what the last step started was.
    Returns:
        step number to resume running at.

    """
    highest_step = -1

    # Get a list of the .step_ snapshots for this build area
    snap_list = snapshot_list(cp)
    if snap_list == -1:
        return highest_step

    # For each step, see if all the  zfs snapshot exists. If they do, modify
    # the "highest step" to be that step. If not, exit because we've
    # found a step without a snapshot. We don't want to allow restarting
    # after this or the results may be inconsistent.
    for step_obj in cp.step_list:
        for zfs_snapshot in step_obj.get_zfs_snapshot_list():
            step_num = -1
            for snapshot in snap_list:
                if zfs_snapshot == snapshot:
                    step_num = step_obj.get_step_num()
                    break
            if step_num == -1:
                return highest_step
        highest_step = max(highest_step, step_num)
    return highest_step

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def verify_resume_step(cp, num):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Verify that the state the user specified execution to resume at was
    valid. The step must be less than or equal to the step at which the
    previous build exited.
    Input:
        num - step number the user specified to resume at.
    Return:
        0 - success
       -1 - error

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # laststep will be the latest resumable step.
    laststep = determine_resume_step(cp)
    if laststep == -1:
        dc_log.error("There are no valid steps to resume from. ")
        dc_log.error("Please rerun the build without the -r or "
                     "-R options.")
        return -1
    if num > laststep:
        dc_log.error("You must specify an earlier step to resume at.")
        dc_log.error("Valid steps to resume from are: ")
        # print all steps from the first up to and including
        # the last step it is legal to resume from.
        for step in cp.step_list[:laststep+1]:
            dc_log.error("%s%s" % (step.get_step_name().ljust(20),
                         step.get_step_message().ljust(10)))
        return -1

    # Get a list of all snapshots associated with our build_area.
    snap_list = snapshot_list(cp)
    if snap_list == -1:
        return -1

    # Verify that all snapshots prior to and including the specified
    # step are listed in the manifest in the correct order.
    # If all snapshots are not listed in the manifest or are in a different
    # order, we may have an inconsistency. The build should be aborted
    # and the user must correct this issue.
    for step_obj in cp.step_list:
        step_num = step_obj.get_step_num()
        if step_num > num :
            break

        snapshot_name = snap_list[step_num].replace(
            cp.get_build_area_dataset() + BUILD_DATA + "@.step_", "")
        if snapshot_name != step_obj.get_step_name():
            dc_log.error("The manifest file is inconsistent with your "
                         "build area.")
            dc_log.error("Please resolve if you wish to use the resume "
                         "functionality.")
            return -1

    return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def verify_resume_state(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Verifies the  state file of each step and or below 'num'. The state
    files must be the same as the current manifest file.
    If the files are not the same, execution continues but a warning is
    printed.
    Input:
        stepno - number of step whose state file to verify

    """
    change = 0
    pstr = ""
    num = cp.get_resume_step()
    manifest = cp.get_manifest()
    for step_obj in cp.step_list:
        if num >= step_obj.get_step_num():
            # Compare the .step<name> file to the manifest file.
            # They should be the same since on step creation the
            # manifest file was copied to the .step_<name> file
            # unless the user has modified the manifest file. This
            # could cause indeterminate results so we want to warn
            # the user of this situation.
            if not filecmp.cmp(step_obj.get_state_file(), manifest, 0):
                change = 1
                pstr += " %s" % step_obj.get_step_name()
    if (change):
        dc_log = logging.getLogger(DC_LOGGER_NAME)
        dc_log.info("WARNING: The manifest file, %s, has changed "
                    % manifest)
        dc_log.info("since Step(s) %s was generated." % pstr)
        dc_log.info("Results may be indeterminate.")

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_checkpoint_script(cp, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    """Queue up the script to create the checkpoint for the designated
    step.

    """

    arglist = []
    currentstep = cp.get_current_step()
    pausestep = cp.get_pause_step()
    arglist.append(cp.get_manifest())
    arglist.append(cp.step_list[currentstep].get_state_file())
    for snapshot in cp.step_list[currentstep].get_zfs_snapshot_list():
        arglist.append(snapshot)
    if currentstep == pausestep:
        arglist.append("Stopping at %s: %s " % \
                      (cp.step_list[currentstep].get_step_name(),
                      cp.step_list[currentstep].get_step_message()))
    else:
        arglist.append("==== %s: %s " % \
                       (cp.step_list[currentstep].get_step_name(),
                       cp.step_list[currentstep].get_step_message()))

    return (finalizer_obj.register(FINALIZER_CHECKPOINT_SCRIPT, arglist))


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_rollback_script(cp, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    """Queue up the script to rollback to the designated step."""

    arglist = []
    currentstep = cp.get_current_step()
    for snapshot in cp.step_list[currentstep].get_zfs_snapshot_list():
        arglist.append(snapshot)
    arglist.append("==== %s: %s " % \
                   (cp.step_list[currentstep].get_step_name(),
                    cp.step_list[currentstep].get_step_message()))
    return (finalizer_obj.register(FINALIZER_ROLLBACK_SCRIPT, arglist))

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_finalizer_script(cp, finalizer_obj, manifest_server_obj, script):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    """Queue up the designated finalizer script."""

    # Args list gets returned as a single string which can contain multiple
    # args, if the args list exists. Split into individual args, accounting
    # for the possibility of an empty list.
    script_args = get_manifest_list(manifest_server_obj,
                                    FINALIZER_SCRIPT_NAME_TO_ARGSLIST % script)

    ret = finalizer_obj.register(script, script_args)
    cp.incr_current_step()
    return (ret)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def add_finalizer_scripts(cp, manifest_server_obj, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Check to see if the finalizer script should be executed. It should only
    be executed if 1) checkpointing is available/on and 2) the steps to
    pause or resume at don't exclude it.

    Input:
            manifest_server_obj - Manifest server object
            finalizer_obj - finalizer object
    Returns:
            SUCCESS - no error
            GENERAL_ERR - unable to register one or more finalizer script

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # assume no error, if there's an error, this will be set to 1
    ret = SUCCESS

    finalizer_script_list = get_manifest_list(manifest_server_obj,
                                              FINALIZER_SCRIPT_NAME)

    resumestep = cp.get_resume_step()
    pausestep = cp.get_pause_step()
    stop_on_err = get_manifest_boolean(manifest_server_obj,
                                       STOP_ON_ERR)
    if stop_on_err is None:
        # this should never happen, since default module should have
        # taken care of filling in the default value of true
        stop_on_err = 1

    for script in finalizer_script_list:
        if not script:
            continue

        if not cp.get_checkpointing_avail():
            # Queue up the finalizer script and return
            if (queue_up_finalizer_script(cp, finalizer_obj,
                                          manifest_server_obj,
                                          script)):
                dc_log.error("Failed to register finalizer " \
                             "script: " + script)
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            continue

        currentstep = cp.get_current_step()
        if currentstep == pausestep:
            # Pause after checkpointing. This means we queue up the
            # checkpoint script but not the finalizer script.
            if (queue_up_checkpoint_script(cp, finalizer_obj)):
                dc_log.error("Failed to register checkpoint " \
                             "script with finalizer module")
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            return (ret)
        if currentstep > resumestep:
            # We're past the resume step and we have checkpointing,
            # so register the checkpointing script and the finalizer
            # script.
            if (queue_up_checkpoint_script(cp, finalizer_obj)):
                dc_log.error("Failed to register checkpoint " \
                             "script with finalizer module")
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            if (queue_up_finalizer_script(cp, finalizer_obj,
                                          manifest_server_obj,
                                          script)):
                dc_log.error("Failed to register finalizer " \
                             "script: " + script)
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            continue
        elif currentstep == resumestep:
            # At the specified step to resume from.
            # Register the rollback script and the finalizer script.
            if (queue_up_rollback_script(cp, finalizer_obj)):
                dc_log.error("Failed to register rollback " \
                             "script with finalizer module")
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            if (queue_up_finalizer_script(cp, finalizer_obj,
                                          manifest_server_obj,
                                          script)):
                dc_log.error("Failed to register finalizer " \
                             "script: " + script)
                if (stop_on_err):
                    return GENERAL_ERR
                else:
                    ret = GENERAL_ERR
            continue
        else:
            # We're not yet to the specified resume step so
            # increment our step counter and continue on.
            cp.incr_current_step()
            continue

    return (ret)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def remove_state_file(step):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Remove the specified .step_ file from the system."""
    filename = step.get_state_file()
    try:
        os.remove(filename)
    except OSError:
        pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def delete_checkpoint(step):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Delete the checkpoint. This will delete
    the zfs snapshot and .step file.

    """
    for zfs_dataset_name in step.get_zfs_snapshot_list():
        # Destroy the snapshot!
        dc_log = logging.getLogger(DC_LOGGER_NAME)
        shell_cmd("/usr/sbin/zfs destroy " + zfs_dataset_name
                  + " >/dev/null 2>&1", dc_log)
    remove_state_file(step)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def verify_manifest_filename(name):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Verify the specified manifest file is readable.
    Returns
       0 - success
      -1 on error

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    try:
        file_name = open("%s" % name, "r")
    except IOError:
        dc_log.error("You have specified a file (%s) that is unable "
                     "to be read." % name)
        return -1

    file_name.close()
    return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def determine_chckpnt_avail(cp, manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Determine if checkpointing is available by reading
    the manifest file variable and checking to see if
    zfs is on they system.

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # The checkpointing available is set to true by default in the
    # checkpointing class __init__ method. Here we check to see if
    # checkpointing is disabled in the manifest file. If so, return
    if get_manifest_value(manifest_server_obj,
                          CHECKPOINT_ENABLE).lower() == "false":
        cp.set_checkpointing_avail(False)
        return

    # Check to see if checkpointing is disabled because zfs is not on
    # the system.
    try:
        if os.access('/sbin/zfs', os.X_OK) == True:
            return
    except OSError:
        dc_log.error("Unable to determine if ZFS is available "
                     "on the system. Checkpointing will be unavailable")

    # zfs not on the system so no checkpointing
    cp.set_checkpointing_avail(False)
    cp.set_zfs_found(False)
    return

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def checkpoint_setup(cp, manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Sets up and defines all checkpoints. All checkpoints must
    have an entry (in chronological order) here.

    format:
     step_setup( message, name, [dataset list])
           message: the message to print to the screen to indicate the step
           name: ascii name for the step.
           dataset list: list with the names of the datasets to snapshot
   
    """

    finalizer_script_list = get_manifest_list(manifest_server_obj,
                                              FINALIZER_SCRIPT_NAME)

    # Set up a checkpoint for each finalizer script specified.
    for script in finalizer_script_list:
        checkpoint_message = get_manifest_value(manifest_server_obj,
            FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_MESSAGE % script)
        checkpoint_name = get_manifest_value(manifest_server_obj,
            FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_NAME % script)
        if checkpoint_name is None :
            dc_log = logging.getLogger(DC_LOGGER_NAME)
            dc_log.error("The checkpoint name to use for the " \
                         "finalizer script %s is missing." % script)
            dc_log.error("Please check your manifest file.")
            return -1
        if checkpoint_message is None:
            checkpoint_message = "Executing " + script
        cp.step_setup(checkpoint_message, checkpoint_name,
            [cp.get_build_area_dataset() + BUILD_DATA])
    return 0

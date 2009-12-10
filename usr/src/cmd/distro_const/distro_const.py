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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""distro_const.py -> Main for the Distribution Constructor. """

import getopt
import sys
import os
import atexit
import logging
import shutil
import time
from subprocess import Popen, PIPE
from osol_install.finalizer import DCFinalizer
from osol_install.ManifestServ import ManifestServ
from osol_install.ManifestServ import ManifestServError
import osol_install.distro_const.dc_checkpoint as dc_ckp 
import osol_install.distro_const.dc_ti as ti 
import osol_install.distro_const.dc_utils as dcu

from osol_install.distro_const.dc_defs import DC_LOGGER_NAME, \
    DC_MANIFEST_DATA, BUILD_DATA, PKG_IMAGE, MEDIA, TMP, BOOT_ARCHIVE, \
    LOGS, DISTRO_NAME, STOP_ON_ERR, SUCCESS, CHECKPOINT_RESUME 

# =============================================================================
# Error Handling
# =============================================================================

class UsageError(Exception):
    """ UsageError exception class """
    pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Print the usage statement and exit
def usage():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """usage for the DC. Command should be of the form:
          distro_const build -R <manifest-file>
          distro_const build -r <step name or number> <manifest-file>
          distro-const build -p <step name or number> <manifest-file>
          distro_const build -l <manifest-file>

    Raises: UsageError

    """
    dc_log = logging.getLogger(DC_LOGGER_NAME)
    dc_log.error("""
Usage:
    distro_const build -R <manifest-file>
    distro_const build -r <step name or number> <manifest-file>
    distro_const build -p <step name or number> <manifest-file>
    distro_const build -l <manifest-file>
    """)

    raise UsageError

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_server_obj(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Read the manifest file name from the command line and create an object
        to read information from the file. 
    Inputs:
          cp: checkpointing object
    Returns:
          A manifest server object which allows access to the manifest file.

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    if len(sys.argv) < 3:
        usage()

    subcommand = sys.argv[1]
    if subcommand != "build":
        dc_log.error("Invalid or missing subcommand")
        usage()

    # Read the manifest file from the command line
    try:
        pargs2 = getopt.getopt(sys.argv[2:], "r:p:hRl?")[1]
    except getopt.GetoptError:
        usage()

    if len(pargs2) == 0:
        usage()

    manifest_file = pargs2[0]
    err = dc_ckp.verify_manifest_filename(manifest_file)
    if err != 0:
        raise Exception, ""
    cp.set_manifest(manifest_file)
    return  ManifestServ(manifest_file, DC_MANIFEST_DATA)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def start_manifest_server(manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Start up the socket for the manifest server.

    Inputs:
           manifest_server_obj : A manifest server object which allows
                                 access to the manifest file.

    """

    manifest_server_obj.start_socket_server()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_command_line(cp, manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Parse the command line options.
    usage: dist_const build [-R] manifest-file
        dist_const build [-r <integer or string>] manifest-file
        dist_const build [-p <integer or string>] manifest-file
        dist_const build [-l] manifest-file

        -R will resume from the last executed step
        -r will resume from the specified step
        -p will pause at the specified step
        -l will list the valid steps to resume/pause at

    Also, verify that the pause step and the resume step are valid. The
    pause step must be one of the steps. The resume step must be less than
    or equal to the last step executed.  This method will also remove the
    zfs snapshots and the .step file for steps equal to or that come after
    the step where execution will start. For a full build or a pause, this
    means all checkpoints will be removed. For a resume, the checkpoint to
    be resumed from and all later checkpoints are removed.
    Return 0 = success
           1 = success but don't continue on with building.
          -1 = Error

    """

    subcommand = sys.argv[1]

    # See if the user has specified a step to resume from in the manifest
    # file. If so, keep it around. If the user has also specified one on
    # the command line, that will overwrite the manifest value.
    stepname = dcu.get_manifest_value(manifest_server_obj,
                                      CHECKPOINT_RESUME)
    if stepname is not None:
        step = dc_ckp.step_from_name(cp, stepname)
        if step is None:
            return -1
        stepno = step.get_step_num()
        if stepno:
            cp.set_resume_step(stepno)

    # Read the command line arguments and parse them.
    try:
        opts2 = getopt.getopt(sys.argv[2:], "r:p:hRl?")[0]
    except getopt.GetoptError:
        usage()
    if subcommand == "build":
        step_resume = False
        resume = False
        pause = False
        do_list = False
        dc_log = logging.getLogger(DC_LOGGER_NAME)
        for opt, arg in opts2:
            if (opt == "-h") or (opt == "-?"):
                usage()

            # Since all command line opts have to do with
            # checkpointing, check here to see
            # if checkpointing is available.
            if not cp.get_checkpointing_avail():
                dc_log.error("Checkpointing is not available")
                dc_log.error("Rerun the build without " + opt)
                return -1

            if opt == "-r":
                # Check to see if -r has already been specified
                if step_resume == True:
                    usage()

                # resume from the specified step.
                step = dc_ckp.step_from_name(cp, arg)
                if step is None:
                    return -1
                stepno = step.get_step_num()
                cp.set_resume_step(stepno)
                step_resume = True
            elif opt == "-p":
                # Check to see if -p has already been specified
                if pause:
                    usage()

                # pause at the specified step.
                step = dc_ckp.step_from_name(cp, arg)
                if step is None:
                    return -1
                stepno = step.get_step_num()
                cp.set_pause_step(stepno)
                pause = True
            elif opt == "-R":
                # resume from the last executed step.
                stepno = dc_ckp.determine_resume_step(cp)
                if stepno == -1:
                    dc_log.error("There are no valid " \
                                 "steps to resume from.")
                    dc_log.error("Please rerun the build " \
                                 "without the -r or -R options.")
                    return -1
                cp.set_resume_step(stepno)
                resume = True
            elif opt == "-l":
                do_list = True

        # If a resume step was specified via -r, -R or the manifest file,
        # check to see if it's valid. If not, abort the build.
        if cp.get_resume_step() != -1:
            err = dc_ckp.verify_resume_step(cp, cp.get_resume_step())
            if err != 0 :
                return -1

        # -R and -r not allowed on the same command line.
        if resume and step_resume:
            dc_log.error("-R and -r cannot be specified for the "
                         "same build. ")
            usage()

        # -l and -R, -r, or -p combination not allowed.
        # -l must be the only option.
        if do_list and (pause or resume or step_resume):
            dc_log.error("-l and -R, -r, or -p cannot be "
                         "specified for the same build")
            usage()

        # We've checked for the bad combos.
        # If a -l was specified, print out the info.
        if do_list:
            # query for valid resume/pause steps
            # All steps are valid to pause at. The
            # steps that are valid to resume from
            # will be marked "resumable"
            laststep = dc_ckp.determine_resume_step(cp)
            dc_log.error("\nStep           Resumable Description")
            dc_log.error("-------------- --------- -------------")
            for step_obj in cp.step_list:
                if laststep != -1 \
                    and step_obj.get_step_num() <= laststep:
                    r_flag = "X"
                else:
                    r_flag = " "
                dc_log.error("%s%s%s" % \
                             (step_obj.get_step_name().ljust(15),
                             r_flag.center(10),
                             step_obj.get_step_message().ljust(10)))
            return 1

        # If -r/-R and -p were both specified,
        # the pause step must be later than the resume.
        if cp.get_pause_step() <= cp.get_resume_step() :
            dc_log.error("The resume step must be earlier "
                         "than the pause step.")
            usage()

        if cp.get_resume_step() != -1 :
            dc_ckp.verify_resume_state(cp)
            # destroy all zfs snapshots and .step files for
            # steps after the resume step
            for step_obj in cp.step_list[cp.get_resume_step() + 1:]:
                dc_ckp.delete_checkpoint(step_obj)
        else :
            # Delete all zfs snapshots and .step files
            for step_obj in cp.step_list:
                dc_ckp.delete_checkpoint(step_obj)

    else :
        # Currently we only support the build subcommand
        dc_log.error("Invalid or missing subcommand")
        usage()
    return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def have_empty_snapshot(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Check to see if the build_data@empty snapshot exists
    Args: cp - checkpointing object

    Returns: True if the snapshot exists
             False if it doesn't exist or there's an error

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    dataset = cp.get_build_area_dataset()
    cmd = "/usr/sbin/zfs list -t snapshot " + \
          dataset + BUILD_DATA + "@empty" + " 2>/dev/null"
    try:
        (rtout, rterr) = Popen(cmd, shell=True,
                               stdout=PIPE, stderr=PIPE).communicate()

    except OSError, err:
        dc_log.error("Exception caught when listing zfs"
                     " snapshots." + str(err))
        return False

    # If there is an error from the zfs list -t snapshot command,
    # print the error in the log file and return.
    # Disabling E1103:%s %r has no %r member (but some types could
    # not be inferred) 
    # pylint: disable-msg=E1103
    if len(rterr.strip()) != 0:
        dc_log.error(rterr.strip())
    # pylint: enable-msg=E1103
        return False

    # Check to see if there is an @empty snapshot.
    # Disabling E1103:%s %r has no %r member (but some types could
    # not be inferred) 
    # pylint: disable-msg=E1103
    if len(rtout.strip()) != 0:
    # pylint: enable-msg=E1103
        return True
    else:
        return False

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanup_build_data_area(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ cleanup_build_data_area makes sure that the build_data area
    of the build_area is empty in the case of a full build.

    If ZFS is used (checkpointing or not), this function relies on and
    maintains a snapshot of an empty build data area.  To this function,
    cleanup is merely rolling back to the @empty snapshot.

    If no @empty snapshot exists but ZFS is used, a zfs destroy of
    the build_data area followed by a zfs create of it will be
    performed to ensure the area is empty, and an @empty snapshot
    will be created.

    If ZFS isn't used, then the equivalent of an rm -rf is done on the
    build_data area and the area is then re-created empty.

    Args: cp - checkpointing opject

    Returns: -1 for Failure
              0 for Success

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # If zfs is used (independent of whether or not checkpointing is used),
    # we need to check for the empty snapshot and either rollback to it
    # if it exists or create it if it doesn't exist.
    dataset = cp.get_build_area_dataset()
    if (dataset is not None):
        # Check to see if the empty snapshot is there.
        if (have_empty_snapshot(cp)):

            # Rollback to the empty snapshot.
            cmd = "/usr/sbin/zfs rollback -r " + dataset + \
                  BUILD_DATA + "@empty"
            try:
                ret = dc_ckp.shell_cmd(cmd, dc_log)
            except OSError, err:
                dc_log.error(str(err))
                ret = -1

            if (ret == -1):
                dc_log.error("Error rolling back pkg_image "
                             "area to an empty state")
                return -1
        else:
            # We can't rollback to the empty snapshot
            # destroy the old build_data area and recreate it
            # in order to get a clean build_data area.

            cmd = "zfs destroy -r " + dataset + BUILD_DATA
            try:
                ret = dc_ckp.shell_cmd(cmd, dc_log)
            except OSError, err:
                dc_log.error("Exception caught during zfs "
                             "dataset destroy: " + str(err))
                ret = -1
            if ret == -1:
                dc_log.error("Error destroying the "
                             "build_data area")
                return -1

            ret = ti.create_zfs_build_data_area(cp)
            if ret == -1:
                dc_log.error("Error creating the ZFS "
                             "build_data area")
                return -1

            # We now have a clean/empty build_data area.
            # Create the empty snapshot to rollback to
            # in subsequent builds.
            ba_dataset = dataset + BUILD_DATA + "@empty"
            cmd = "/usr/sbin/zfs snapshot " + ba_dataset
            try:
                ret = dc_ckp.shell_cmd(cmd, dc_log)
            except OSError, err:
                dc_log.error("Exception caught when "
                             "creating zfs snapshot " + dataset)
                ret = -1
            if (ret == -1):
                dc_log.error("Error creating "
                             "the empty rollback for " + dataset)
                return -1
    else:
        # Zfs is not used for this build area.  Manually remove the
        # build_data area and recreate it. This forces the
        # directories to be empty.

        # The second arg tells rmtree to ignore errors.
        shutil.rmtree(cp.get_build_area_mntpt() +  BUILD_DATA, True)
        ret = ti.create_ufs_build_data_area(cp)
        if ret:
            dc_log.error("Error creating the UFS build_data area")
            return -1
    return 0

#
# Main distribution constructor function.
#
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main_func():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    """Main processing function for the Distribution Constructor. Will set
    up the checkpoints, create the build area, start the socket server to
    read the manifest file, create the finalizer script queue and then
    start the execution of the finalizer scripts. 

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # Must be root to run DC. Check for that.
    if os.getuid() != 0:
        dc_log.error("You must be root to run distro_const")
        return 1

    # Sets the umask for the DC app
    os.umask(022)

    cp = dc_ckp.Checkpoints()

    try:
        # Create the object used to extract the data
        manifest_server_obj = get_manifest_server_obj(cp)
    except UsageError:
        raise
    except:
        return 1

    try:
        # Start the socket server
        start_manifest_server(manifest_server_obj)

        # Set up to shut down socket server cleanly on exit
        atexit.register(manifest_server_obj.stop_socket_server)
    except ManifestServError:
        return 1

    # create the build area and determine if
    # checkpointing is available. When creating the
    # build area we also create the areas for the
    # package image (pkg_image), output media (media),
    # logfiles (logs) and boot archive (boot_archive).
    if ti.create_build_area(cp, manifest_server_obj):
        return 1

    # Set up the structures for all checkpoints
    if cp.get_checkpointing_avail() == True:
        if dc_ckp.checkpoint_setup(cp, manifest_server_obj):
            return 1

    # Parse the command line so we know to resume (and where) or not
    ret = parse_command_line(cp, manifest_server_obj)
    if ret == 1:
             # Don't continue processing. Return but nothing is wrong.
        return 0
    if ret == -1:
             # Error parsing the command line. Return indicating such.
        return 1

    # The build is going to start, will start logging
    (simple_log_name, detail_log_name) = \
        dcu.setup_dc_logfile_names(cp.get_build_area_mntpt() + LOGS)
    dc_log.info("Simple Log: " + simple_log_name)
    dc_log.info("Detail Log: " + detail_log_name)
    dcu.add_file_logging(simple_log_name, detail_log_name)

    dc_log.info("Build started " + time.asctime(time.localtime()))
    dc_log.info("Distribution name: " +
        (dcu.get_manifest_value(manifest_server_obj, DISTRO_NAME)))
    dataset = cp.get_build_area_dataset()
    if dataset is not None:
        dc_log.info("Build Area dataset: " + dataset)
    dc_log.info("Build Area mount point: " + cp.get_build_area_mntpt())

    # If we're doing a build that is a -r or -R build, then
    # we don't need to cleanup.
    if cp.get_resume_step() == -1:
        # Cleanup the pkg_image area via either a remove of the files
        # if there is not checkpointing or rolling back to the @empty
        # snapshot if there is checkpointing.
        if cleanup_build_data_area(cp) != 0:
            dc_log.info("Build completed " + time.asctime(time.localtime()))
            dc_log.info("Build failed.")
            return 1

    stop_on_err_bool = dcu.get_manifest_boolean(manifest_server_obj,
                                                STOP_ON_ERR)

    # register the scripts with the finalizer
    build_area = cp.get_build_area_mntpt()
    pkg_img_area = build_area + PKG_IMAGE
    tmp_area = build_area + TMP
    ba_build_area = build_area + BOOT_ARCHIVE
    media_dir = build_area + MEDIA

    finalizer_obj = DCFinalizer([manifest_server_obj.get_sockname(),
                                 pkg_img_area, tmp_area, ba_build_area,
                                 media_dir])
    if (finalizer_obj.change_exec_params(stop_on_err=stop_on_err_bool,
                                         logger_name = DC_LOGGER_NAME) != 0):
        dc_log.error("Unable to set stop on error or logger name "
                     "for finalizer")

    status = dc_ckp.add_finalizer_scripts(cp, manifest_server_obj,
                                          finalizer_obj)
    if (status != SUCCESS):
        dc_log.info("Build completed " + time.asctime(time.localtime()))
        dc_log.info("Build failed.")
        return (status)

    # Execute the finalizer scripts
    status = finalizer_obj.execute()
    dc_log.info("Build completed " + time.asctime(time.localtime()))
    if (status != 0):
        dc_log.info("Build failed.")
    else:
        dc_log.info("Build is successful.")

    dcu.cleanup_dir(cp.get_build_area_mntpt() + TMP)
    return (status)

if __name__ == "__main__":

    RET_VAL = 1 # this will be set to 0 if main_func() succeed
    DC_LOG = dcu.setup_dc_logging()

    # Pylint bug: See http://www.logilab.org/ticket/8764
    # pylint: disable-msg=C0321
    try:
        RET_VAL = main_func()
    except UsageError:
        RET_VAL = 2

    except SystemExit, e:
        DC_LOG.info(str(e))

    except Exception, ex:
        DC_LOG.exception(ex)

    finally:

        # shutdown applies to the whole logging system for this app,
        # not just the DC logger
        logging.shutdown()

    sys.exit(RET_VAL)

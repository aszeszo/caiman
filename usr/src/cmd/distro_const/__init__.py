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

#
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

"""init module for the distribution constructor"""

__all__ = ["cli", "distro_const", "execution_checkpoint", "distro_spec"]


import logging
import optparse
import os
import shutil
import sys
import time

import solaris_install.distro_const.distro_spec
import solaris_install.distro_const.execution_checkpoint

import osol_install.errsvc as errsvc
import solaris_install.transfer.info as transfer
import solaris_install.configuration

from osol_install.install_utils import set_http_proxy
from osol_install.liberrsvc import ES_DATA_EXCEPTION
from solaris_install import CalledProcessError, run, DC_LABEL
from solaris_install.boot.boot_spec import BootMods
from solaris_install.data_object import DataObject, ObjectNotFoundError
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const.execution_checkpoint import Execution
from solaris_install.distro_const.distro_spec import Distro
from solaris_install.engine import FileNotFoundError, InstallEngine, \
    NoDatasetError, RollbackError, UsageError, UnknownChkptError
from solaris_install.engine import INSTALL_LOGGER_NAME
from solaris_install.logger import DEFAULTLOG, FileHandler, InstallFormatter
from solaris_install.manifest.parser import ManifestError
from solaris_install.target import Target
from solaris_install.target.logical import Filesystem, Zpool
from solaris_install.transfer.info import Destination, Dir, Image, Software, \
    Source

DC_LOCKFILE = "distro_const.lock"
DC_LOGGER = None


class Lockfile(object):
    """ Lockfile - context manager for locking the distro_const dataset to
    prevent multiple invocations of distro_const from running at the same time
    """
    def __init__(self, filename):
        """ filename is the path of the file to use to lock the dataset
        """
        self.filename = filename

    def __enter__(self):
        """ method which checks for the lockfile before creating one.  If the
        lockfile exists, exit with an error
        """

        if os.path.exists(self.filename):
            raise RuntimeError("distro_const: An instance of distro_const "
                               "is already running in %s" % 
                               os.path.split(self.filename)[0])
        else:
            # touch the lockfile
            with open(self.filename, "w"):
                pass

    def __exit__(self, *exc_info):
        """ method to remove the lockfile
        """
        if os.path.exists(self.filename):
            try:
                os.remove(self.filename)
            except BaseException as err:
                raise RuntimeError("Could not remove %s: %s" % \
                                   (self.filename, err))


class DCScreenHandler(logging.Formatter):
    """ DC-specific StreamHandler class.  Suppresses traceback printing to the
    screen by overloading the format() method
    """

    def format(self, record):
        """ overloaded method to prevent the traceback from being printed
        """
        record.message = record.getMessage()
        record.asctime = self.formatTime(record, self.datefmt)
        s = self._fmt % record.__dict__
        return s


def parse_args(baseargs=sys.argv[1:]):
    """ parse_args() - function used to parse the command line arguments to
    distro_const.
    """
    usage = "%prog build [-v] [-r <checkpoint name>] " + \
            "[-p <checkpoint name>] " + \
            "[-l] manifest"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", dest="verbose", default=False,
                      action="store_true", help="Specifies verbose mode")
    parser.add_option("-r", "--resume", dest="resume_checkpoint",
                      help="Checkpoint to resume execution from")
    parser.add_option("-p", "--pause", dest="pause_checkpoint",
                      help="Checkpoint to pause execution on")
    parser.add_option("-l", "--list", dest="list_checkpoints",
                      action="store_true",
                      help="List all possible checkpoints")

    (options, args) = parser.parse_args(baseargs)

    # verify there are exactly two arguments (subcommand and manifest)
    if not args:
        parser.error("subcommand and manifest not specified")
    # currently only the 'build' subcommand is supported
    elif args[0] != "build":
        parser.error("invalid or missing subcommand")
    elif len(args) != 2:
        parser.error("invalid number of arguments to distro_const")

    return (options, args)


def set_stream_handler(DC_LOGGER, list_cps, verbose):
    """ function to setup the stream_handler of the logging module for output
    to the screen.
    """
    # create a simple StreamHandler to output messages to the screen
    screen_sh = logging.StreamHandler()

    # set the verbosity of the output
    if verbose:
        screen_sh.setLevel(logging.DEBUG)
    else:
        screen_sh.setLevel(logging.INFO)

    # set the columns.  If the user only wants to list the checkpoints, omit
    # the timestamps
    if list_cps:
        fmt = "%(message)s"
        screen_sh.setFormatter(DCScreenHandler(fmt=fmt))
    else:
        fmt = "%(asctime)-11s %(message)s"
        datefmt = "%H:%M:%S"
        screen_sh.setFormatter(DCScreenHandler(fmt=fmt, datefmt=datefmt))
    DC_LOGGER.addHandler(screen_sh)


def register_checkpoints(DC_LOGGER):
    """ register each checkpoint in the execution section of the
    manifest with the InstallEngine.

    Also set the stop_on_error property of the InstallEngine based on what
    that property is set to in the manifest.
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # get the execution_list from the Distro object
    execution_obj = doc.volatile.get_descendants(class_type=Execution)
    if not execution_obj:
        raise RuntimeError("No Execution section found in the manifest")

    # verify the manifest contains checkpoints to execute
    checkpoints = execution_obj[0].get_children()
    if not checkpoints:
        raise RuntimeError("No checkpoints found in the Execution section "
                           "of the manifest")

    eng.stop_on_error = (execution_obj[0].stop_on_error.capitalize() == "True")

    # register the checkpoints with the engine
    registered_checkpoints = []
    for checkpoint in checkpoints:
        try:
            DC_LOGGER.debug("Registering Checkpoint:  " + checkpoint.name)
            eng.register_checkpoint(checkpoint.name, checkpoint.mod_path,
                checkpoint.checkpoint_class, insert_before=None,
                loglevel=checkpoint.log_level, args=checkpoint.args,
                kwargs=checkpoint.kwargs)

        except ImportError as err:
            DC_LOGGER.exception("Error registering checkpoint "
                                "'%s'\n" % checkpoint.name + \
                                "Check the 'mod_path' and 'checkpoint_class' "
                                "specified for this checkpoint")
            raise

        registered_checkpoints.append((checkpoint.name, checkpoint.desc))

    return registered_checkpoints


def execute_checkpoint(log=DEFAULTLOG, resume_checkpoint=None,
                       pause_checkpoint=None):
    """ wrapper to the execute_checkpoints methods
    """
    eng = InstallEngine.get_instance()

    if resume_checkpoint is not None:
        (status, failed_cps) = eng.resume_execute_checkpoints(
            start_from=resume_checkpoint, pause_before=pause_checkpoint,
            dry_run=False, callback=None)
    else:
        (status, failed_cps) = eng.execute_checkpoints(start_from=None,
            pause_before=pause_checkpoint, dry_run=False, callback=None)

    if status != InstallEngine.EXEC_SUCCESS:
        for failed_cp in failed_cps:
            for err in errsvc.get_errors_by_mod_id(failed_cp):
                DC_LOGGER.info("'%s' checkpoint failed" % failed_cp)
                DC_LOGGER.info(err.error_data[ES_DATA_EXCEPTION])
                # if a CalledProcessError is raised during execution of a
                # checkpoint, make sure the strerror() is also logged to give
                # the user additional feedback
                if isinstance(err.error_data[ES_DATA_EXCEPTION],
                              CalledProcessError):
                    DC_LOGGER.debug(os.strerror(
                        err.error_data[ES_DATA_EXCEPTION].returncode))
        raise RuntimeError("Please check the log for additional error "
                           "messages. \nLog: " + log)


def parse_manifest(manifest):
    """ function to parse the manifest
    """
    eng = InstallEngine.get_instance()

    kwargs = dict()
    kwargs["call_xinclude"] = True
    args = [manifest]
    eng.register_checkpoint("manifest-parser",
                            "solaris_install/manifest/parser",
                            "ManifestParser", args=args, kwargs=kwargs)
    execute_checkpoint()


def validate_target():
    """ validate_target() - function to validate the target element specified
    in the manifest.
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # retrieve the build dataset
    fs = doc.get_descendants(class_type=Filesystem)
    if not fs:
        raise RuntimeError("distro_const: No dataset specified")

    if len(fs) > 1:
        raise RuntimeError("distro_const: More than one dataset specified "
                           "as the build dataset")

    # verify the base_action is not "delete" for the Filesystem
    if fs[0].action == "delete":
        raise RuntimeError("distro_const: 'delete' action not supported "
                           "for Filesystems")

    # get the zpool name and action
    zpool = doc.get_descendants(class_type=Zpool)
    if not zpool:
        raise RuntimeError("distro_const: No zpool specified")

    if len(zpool) > 1:
        raise RuntimeError("distro_const: More than one zpool specified")

    if zpool[0].action in ["delete", "create"]:
        raise RuntimeError("distro_const: '%s' action not supported for "
                           "Zpools" % zpool[0].action)

    if not zpool[0].exists:
        raise RuntimeError("distro_const: Zpool '%s' does not exist" %
                           zpool[0].name)

    return zpool[0], fs[0]


def setup_build_dataset(zpool, fs, resume_checkpoint=None):
    """ Setup the build datasets for use by DC. This includes setting up:
    - top level build dataset
    - a child dataset named 'build_data'
    - a child dataset named 'media'
    - a child dataset named 'logs'
    - a snapshot of the empty build_data dataset - build_data@empty
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    build_data = eng.dataset
    empty_snap = Filesystem(os.path.join(zpool.name, fs.name,
                                         "build_data@empty"))
    logs = Filesystem(os.path.join(zpool.name, fs.name, "logs"))
    media = Filesystem(os.path.join(zpool.name, fs.name, "media"))

    if fs.action == "create":
        # recursively destroy the Filesystem dataset before creating it
        fs.destroy(dry_run=False, recursive=True)

    fs.create()
    build_data.create()
    logs.create()
    media.create()

    if fs.action == "preserve":
        # check to see if base_dataset/build_data@empty exists.
        if resume_checkpoint is None and empty_snap.exists:
            # rollback the dataset only if DC is not resuming from a specific
            # checkpoint
            build_data.rollback("empty", recursive=True)

    if not empty_snap.exists:
        build_data.snapshot("empty")

    # Now that the base dataset is created, store the mountpoint ZFS calculated
    base_dataset_mp = fs.get("mountpoint")

    # check for the existence of a lock file, bail out if one exists.
    if os.path.exists(base_dataset_mp):
        if os.path.exists(os.path.join(base_dataset_mp, DC_LOCKFILE)):
            raise RuntimeError("distro_const: An instance of distro_const "
                               "is already running in %s" % base_dataset_mp)

    DC_LOGGER.info("Build datasets successfully setup")
    return (base_dataset_mp, build_data.get("mountpoint"),
            logs.get("mountpoint"), media.get("mountpoint"))


def dc_set_http_proxy(DC_LOGGER):
    """ set the http_proxy and HTTP_PROXY environment variables
    if an http_proxy is specified in the manifest.
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # get the Distro object from the DOC that contains all of the
    # checkpoint objects as the children
    distro = doc.volatile.get_descendants(class_type=Distro)
    if not distro:
        return

    if distro[0].http_proxy is not None:
        DC_LOGGER.debug("Setting http_proxy to %s" % distro[0].http_proxy)
        set_http_proxy(distro[0].http_proxy)
    else:
        DC_LOGGER.debug("No http_proxy specified in the manifest")


def list_checkpoints(DC_LOGGER):
    """ List the checkpoints listed in the manifest
    """
    eng = InstallEngine.get_instance()
    # register each checkpoint listed in the execution section
    registered_checkpoints = register_checkpoints(DC_LOGGER)
    resumable_checkpoints = None

    try:
        resumable_checkpoints = eng.get_resumable_checkpoints()
    except (NoDatasetError, FileNotFoundError) as err:
        # the build dataset is probably a virgin dataset
        DC_LOGGER.debug("No checkpoints are resumable: %s" % err)

    DC_LOGGER.info("Checkpoint           Resumable Description")
    DC_LOGGER.info("----------           --------- -----------")
    for (name, desc) in registered_checkpoints:
        if resumable_checkpoints is not None and \
            name in resumable_checkpoints:
            DC_LOGGER.info("%-20s%6s     %-20s" % (name, "X", desc))
        else:
            DC_LOGGER.info("%-20s%6s     %-20s" % (name, " ", desc))


def update_doc_paths(build_data_mp):
    """ function to replace placeholder strings in the DOC with actual paths

    build_data_mp - mountpoint of the build_data dataset
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # find all of the Software nodes
    software_list = doc.volatile.get_descendants(class_type=Software)

    # iterate over each node, looking for Dir and/or Image nodes
    for software_node in software_list:
        for dir_node in software_node.get_descendants(class_type=Dir):
            path = dir_node.dir_path
            path = path.replace("{BUILD_DATA}", build_data_mp)
            path = path.replace("{BOOT_ARCHIVE}",
               os.path.join(build_data_mp, "boot_archive"))
            path = path.replace("{PKG_IMAGE_PATH}",
               os.path.join(build_data_mp, "pkg_image"))
            dir_node.dir_path = path
        for image_node in software_node.get_descendants(class_type=Image):
            path = image_node.img_root
            path = path.replace("{BUILD_DATA}", build_data_mp)
            path = path.replace("{BOOT_ARCHIVE}",
               os.path.join(build_data_mp, "boot_archive"))
            path = path.replace("{PKG_IMAGE_PATH}",
               os.path.join(build_data_mp, "pkg_image"))
            image_node.img_root = path


def main():
    """ primary execution function for distro_const
    """
    # clear the error service to be sure that we start with a clean slate
    errsvc.clear_error_list()

    options, args = parse_args()
    manifest = args[-1]
    pause_checkpoint = None
    resume_checkpoint = None

    verbose = options.verbose
    list_cps = options.list_checkpoints

    try:
        # We initialize the Engine with stop_on_error set so that if there are
        # errors during manifest parsing, the processing stops
        eng = InstallEngine(debug=False, stop_on_error=True)
        doc = eng.data_object_cache

        global DC_LOGGER
        DC_LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)

        # set the logfile name
        log_name = "log.%s" % time.strftime("%Y-%m-%d.%H:%M")
        detail_log_name = "detail-%s" % log_name
        simple_log_name = "simple-%s" % log_name

        # create an additional FileHandler for a simple log
        base, logfile = os.path.split(DEFAULTLOG)
        simple_logname = os.path.join(base, "simple-" + logfile)
        simple_fh = FileHandler(simple_logname)
        simple_fh.setLevel(logging.INFO)
        DC_LOGGER.addHandler(simple_fh)

        if options.resume_checkpoint:
            resume_checkpoint = options.resume_checkpoint
            DC_LOGGER.info("distro_const will resume from:  " + \
                           resume_checkpoint)
        if options.pause_checkpoint:
            pause_checkpoint = options.pause_checkpoint
            DC_LOGGER.info("distro_const will pause at:  " + pause_checkpoint)

        # create a simple StreamHandler to output messages to the screen
        set_stream_handler(DC_LOGGER, list_cps, verbose)

        parse_manifest(manifest)

        # validate the target section of the manifest
        zpool, fs = validate_target()

        # set the engine's dataset to enable snapshots
        eng.dataset = os.path.join(zpool.name, fs.name, "build_data")

        if list_cps:
            list_checkpoints(DC_LOGGER)
        else:
            (base_dataset_mp, build_data_mp, logs_mp, media_mp) = \
                setup_build_dataset(zpool, fs, resume_checkpoint)

            # update the DOC with actual directory values
            update_doc_paths(build_data_mp)

            # lock the dataset
            with Lockfile(os.path.join(base_dataset_mp, DC_LOCKFILE)):
                # output the log file path to the screen and transfer the logs
                new_detaillog = os.path.join(logs_mp, detail_log_name)
                new_simplelog = os.path.join(logs_mp, simple_log_name)
                DC_LOGGER.info("Simple log: %s" % new_simplelog)
                DC_LOGGER.info("Detail Log: %s" % new_detaillog)
                DC_LOGGER.transfer_log(destination=new_detaillog)
                simple_fh.transfer_log(destination=new_simplelog)

                # set the http_proxy if one is specified in the manifest
                dc_set_http_proxy(DC_LOGGER)

                # register each checkpoint listed in the execution section
                registered_checkpoints = register_checkpoints(DC_LOGGER)

                # if we're trying to pause at the very first checkpoint,
                # there's nothing to execute, so return 0
                if pause_checkpoint == registered_checkpoints[0][0]:
                    return 0

                # populate the DOC with the common information needed by the
                # various checkpoints
                doc_dict = {"pkg_img_path": os.path.join(build_data_mp,
                                                         "pkg_image"),
                            "ba_build": os.path.join(build_data_mp,
                                                     "boot_archive"),
                            "tmp_dir": os.path.join(build_data_mp, "tmp"),
                            "media_dir": media_mp}
                doc.volatile.insert_children(DataObjectDict(DC_LABEL, doc_dict,
                                                            generate_xml=True))

                execute_checkpoint(new_detaillog, resume_checkpoint,
                    pause_checkpoint)

    # catch any errors and log them.
    except BaseException as msg:
        if DC_LOGGER is not None:
            DC_LOGGER.exception(msg)
        else:
            # DC_LOGGER hasn't even been setup and we ran into an error
            print msg
        return 1
    finally:
        if DC_LOGGER is not None:
            DC_LOGGER.close()

    return 0

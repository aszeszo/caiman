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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

"""init module for the distribution constructor"""

__all__ = ["cli", "distro_const", "execution_checkpoint", "distro_spec"]


import logging
import optparse
import os
import shutil
import sys
import time

import distro_spec
import execution_checkpoint

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

# manifest parser dictionary.  These values are used to register the manifest
# parser checkpoint with the engine
MP_DICT = {}
MP_DICT["name"] = "manifest-parser"
MP_DICT["mod_path"] = "solaris_install/manifest/parser"
MP_DICT["class"] = "ManifestParser"

# target instantiation dictionary.  These values are used to register the
# ti checkpoint with the engine
TI_DICT = {}
TI_DICT["name"] = "target-instantiation"
TI_DICT["mod_path"] = "solaris_install/target/instantiation"
TI_DICT["class"] = "TargetInstantiation"

DC_LOCKFILE = "distro_const.lock"

# create a logger for DC
DC_LOGGER = None


class Lockfile(object):
    """ Lockfile - context manager for locking the distro_const dataset to
    prevent multiple invocations of distro_const from running at the same time
    """
    def __init__(self, filename):
        """ constructor for class.  filename is the path of the file to use to
        lock the dataset
        """
        self.filename = filename

    def __enter__(self):
        """ class method which checks for the lockfile before creating one.  If
        the lockfile exists, exit with an error
        """
        if os.path.exists(self.filename):
            raise RuntimeError("distro_const: An instance of distro_const " \
                               "is already running in " \
                               "%s" % os.path.split(self.filename)[0])
        else:
            # touch the lockfile
            with open(self.filename, "w"):
                pass

    def __exit__(self, *exc_info):
        """ class method to remove the lockfile
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


def parse_args(baseargs=None):
    """ parse_args() - function used to parse the command line arguments to
    distro_const.
    """
    if baseargs is None:
        baseargs = sys.argv[1:]

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

    # get the execution object from the DOC that contains all of the
    # checkpoint objects as the children

    # get the execution_list from the Distro object
    distro_obj = doc.volatile.get_first_child(class_type=Distro)
    execution_obj = distro_obj.get_first_child(class_type=Execution)
    if execution_obj is None:
        raise RuntimeError("No Execution section found in the manifest")

    # get_children, with no parameters, will return an empty list if there are
    # no children
    checkpoints = execution_obj.get_children()
    if len(checkpoints) == 0:
        raise RuntimeError("No checkpoints found in the Execution section "
                           "of the manifest")

    # set stop_on_error commensurate with what's specified in the manifest
    eng.stop_on_error = (execution_obj.stop_on_error.capitalize() == "True")

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
    """ wrapper to the execute_checkpoints (and friends) methods
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
    eng.register_checkpoint(MP_DICT["name"], MP_DICT["mod_path"],
                            MP_DICT["class"], args=args, kwargs=kwargs)
    execute_checkpoint()


def validate_target():
    """ validate_target() - function to validate the target element specified
    in the manifest.
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # retrieve the build dataset
    build_datasets = doc.get_descendants(class_type=Filesystem)
    if len(build_datasets) > 1:
        raise RuntimeError("More than one dataset specified as the build "
                           "dataset")

    base_dataset = build_datasets[0].name
    base_action = build_datasets[0].action
    base_mountpoint = build_datasets[0].mountpoint

    # verify the base_action is not "delete" for the Filesystem
    if base_action == "delete":
        raise RuntimeError("distro_const: 'delete' action not supported "
                           "for Filesystems")

    # get the zpool name and action
    build_zpool = doc.get_descendants(class_type=Zpool)
    if len(build_zpool) > 1:
        raise RuntimeError("More than one zpool specified")

    zpool_name = build_zpool[0].name
    zpool_action = build_zpool[0].action
    zpool_mountpoint = build_zpool[0].mountpoint

    if zpool_action == "delete":
        raise RuntimeError("distro_const: 'delete' action not supported "
                           "for Zpools")

    # if the user has selected "create" for the action, verify the zpool is
    # not the bootfs zpool since there is an implied "delete" before any
    # "create" actions in TI
    elif zpool_action == "create":
        if is_root_pool(zpool_name):
            raise RuntimeError("distro_const: 'create' action not allowed "
                               "on a build dataset that is also a root "
                               "pool: " + zpool_name)

        # since the zpool_action is "create", unless the mountpoint of the
        # base_dataset is explictly set, it will be set to None.
        if base_mountpoint is None:
            # let ZFS figure out the mountpoint
            if zpool_mountpoint is None:
                base_mountpoint = os.path.join("/", base_dataset)
            else:
                # if the mountpoint has been specified, strip the zpool name
                # from the dataset name.
                fixed_name = "/".join(base_dataset.split("/")[1:])
                base_mountpoint = os.path.join(zpool_mountpoint, fixed_name)

    return(zpool_name, base_dataset, base_action, base_mountpoint)


def setup_build_dataset(zpool_name, base_dataset, base_action, base_dataset_mp,
                        resume_checkpoint=None, execute=True):
    """ Setup the build datasets for use by DC. This includes setting up:
    - top level build dataset
    - a child dataset named 'build_data'
    - a child dataset named 'media'
    - a child dataset named 'logs'
    - a snapshot of the empty build_data dataset - build_data@empty
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # register an internal TI checkpoint
    eng.register_checkpoint(TI_DICT["name"], TI_DICT["mod_path"],
                            TI_DICT["class"])

    if not execute:
        return

    build_data = Filesystem(os.path.join(zpool_name, base_dataset,
                                         "build_data"))
    empty_snap = Filesystem(os.path.join(zpool_name, base_dataset,
                                         "build_data@empty"))

    # set the other mountpoints
    build_data_mp = os.path.join(base_dataset_mp, "build_data")
    logs_mp = os.path.join(base_dataset_mp, "logs")
    media_mp = os.path.join(base_dataset_mp, "media")

    # if resume_checkpoint is not None, ensure that the build datasets do
    # actually exist
    if resume_checkpoint is not None:
        if base_dataset_mp is None or \
           build_data_mp is None or \
           logs_mp is None or \
           media_mp is None or\
           not empty_snap.exists:
            raise RuntimeError("Build dataset not correctly setup.  "
                               "distro_const cannot be resumed.")

    # check for the existence of a lock file, bail out
    # if one exists.
    if base_dataset_mp is not None and os.path.exists(base_dataset_mp):
        if os.path.exists(os.path.join(base_dataset_mp, DC_LOCKFILE)):
            raise RuntimeError("distro_const: An instance of distro_const " \
                               "is already running in " + base_dataset_mp)

    # create DOC nodes
    build_data_node = Filesystem(os.path.join(base_dataset, "build_data"))
    build_data_node.mountpoint = build_data_mp
    logs_node = Filesystem(os.path.join(base_dataset, "logs"))
    logs_node.mountpoint = logs_mp
    media_node = Filesystem(os.path.join(base_dataset, "media"))
    media_node.mountpoint = media_mp

    if base_action == "preserve":
        # check to see if base_dataset/build_data@empty exists.
        if resume_checkpoint is None and empty_snap.exists:
            # rollback the dataset only if DC is not resuming from a specific
            # checkpoint
            build_data.rollback("empty", recursive=True)

    build_data_node.action = base_action
    logs_node.action = base_action
    media_node.action = base_action

    # insert all three nodes.
    zpool = doc.get_descendants(class_type=Zpool)[0]
    zpool.insert_children([build_data_node, logs_node, media_node])

    execute_checkpoint()

    # the from_xml() call of Filesystem tries to manually set the mountpoint of
    # the base dataset.  In doing that, it makes assumptions about how ZFS
    # determines the mountpoint of the dataset.  Now that ZFS has created the
    # dataset, query ZFS to set the mountpoint based on what ZFS set it to.
    base_dataset_object = Filesystem(os.path.join(zpool_name, base_dataset))
    base_dataset_mp = base_dataset_object.get("mountpoint")

    # (re)set the other mountpoints
    build_data_mp = os.path.join(base_dataset_mp, "build_data")
    logs_mp = os.path.join(base_dataset_mp, "logs")
    media_mp = os.path.join(base_dataset_mp, "media")

    # create the @empty snapshot if needed
    if not empty_snap.exists:
        build_data.snapshot("empty")

    DC_LOGGER.info("Build datasets successfully setup")
    return (base_dataset_mp, build_data_mp, logs_mp, media_mp)


def dc_set_http_proxy(DC_LOGGER):
    """ set the http_proxy and HTTP_PROXY environment variables
    if an http_proxy is specified in the manifest.
    """
    eng = InstallEngine.get_instance()
    doc = eng.data_object_cache

    # get the Distro object from the DOC that contains all of the
    # checkpoint objects as the children
    distro = doc.volatile.get_descendants(class_type=Distro)
    if len(distro) == 0:
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


def is_root_pool(pool_name):
    """ function to determine if a zpool is the boot pool
    """
    cmd = ["/usr/sbin/zpool", "get", "bootfs", pool_name]
    p = run(cmd)
    # if the pool is the boot pool, the output looks like
    # NAME   PROPERTY  VALUE                SOURCE
    # rpool  bootfs    rpool/ROOT/dataset   local
    # if the pool is NOT the boot pool, the VALUE will be a hypen (-)
    for line in p.stdout.splitlines():
        if line.startswith(pool_name):
            if line.split()[2] != "-":
                return True
    return False


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

        base_dataset = None

        parse_manifest(manifest)

        # get a reference to the data object cache
        doc = eng.data_object_cache

        # validate the target section of the manifest
        zpool_name, base_dataset, base_action, base_dataset_mp = \
            validate_target()

        if list_cps:
            # set the execute flag of setup_build_dataset to 'False'
            # to prevent any actions from occuring. The TI checkpoint
            # needs to be registered with the engine for list_checkpoints
            # to work correctly.
            setup_build_dataset(zpool_name, base_dataset, base_action,
                base_dataset_mp, resume_checkpoint, execute=False)

            # set the InstallEngine.dataset property to enable snapshots
            eng.dataset = os.path.join(zpool_name, base_dataset, "build_data")

            list_checkpoints(DC_LOGGER)
        else:
            (base_dataset_mp, build_data_mp, logs_mp, media_mp) = \
                setup_build_dataset(zpool_name, base_dataset, base_action,
                    base_dataset_mp, resume_checkpoint)

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

                # reset the InstallEngine.dataset property to enable snapshots
                eng.dataset = os.path.join(zpool_name, base_dataset,
                                           "build_data")

                # register each checkpoint listed in the execution section
                registered_checkpoints = register_checkpoints(DC_LOGGER)

                # now populate the DOC with the common information needed
                # by the various checkpoints -- pkg_img_path, etc
                doc_dict = {"pkg_img_path": os.path.join(build_data_mp,
                                                         "pkg_image"),
                            "ba_build": os.path.join(build_data_mp,
                                                     "boot_archive"),
                            "tmp_dir": os.path.join(build_data_mp, "tmp"),
                            "media_dir": media_mp}
                doc.volatile.insert_children(DataObjectDict(DC_LABEL, doc_dict,
                                                            generate_xml=True))

                # if we're trying to pause at the very first checkpoint,
                # there's nothing to execute, so return 0
                if pause_checkpoint == registered_checkpoints[0][0]:
                    return 0

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

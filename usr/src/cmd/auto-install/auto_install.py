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

# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.

"""AutoInstall main class and progress logging support."""

import linecache
import logging
import optparse
import os
import os.path
import random
import platform
import socket
import struct
import sys
import thread
import time
import traceback

import osol_install.errsvc as errsvc

from osol_install.liberrsvc import ES_DATA_EXCEPTION

from solaris_install import \
    ApplicationData, system_temp_path, post_install_logs_path, Popen
from solaris_install.auto_install import TRANSFER_FILES_CHECKPOINT
from solaris_install.auto_install.ai_instance import AIInstance
from solaris_install.auto_install.checkpoints.dmm import \
    DERIVED_MANIFEST_DATA, DerivedManifestData
from solaris_install.auto_install.checkpoints.target_selection import \
    SelectionError, TargetSelection
from solaris_install.auto_install.checkpoints.target_selection_zone import \
    TargetSelectionZone
from solaris_install.auto_install.checkpoints.ai_configuration import \
    AI_SERVICE_LIST_FILE, AIConfigurationError
from solaris_install.auto_install.utmpx import users_on_console
from solaris_install.boot import boot
from solaris_install.data_object import ParsingError, \
    DataObject, ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine import UnknownChkptError, UsageError, \
    RollbackError
from solaris_install.ict import initialize_smf, update_dumpadm, ips, \
    device_config, apply_sysconfig, boot_archive, transfer_files, \
    create_snapshot, setup_swap
from solaris_install.ict.apply_sysconfig import APPLY_SYSCONFIG_DICT, \
    APPLY_SYSCONFIG_PROFILE_KEY
from solaris_install.logger import FileHandler, ProgressHandler, MAX_INT
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.manifest.parser import ManifestError, \
    MANIFEST_PARSER_DATA
from solaris_install.target import Target, discovery, instantiation
from solaris_install.target.instantiation_zone import ALT_POOL_DATASET
from solaris_install.target.logical import BE, Logical
from solaris_install.transfer import create_checkpoint
from solaris_install.transfer.info import Software, Source, Destination, \
    Image, ImType, Dir, INSTALL, IPSSpec, CPIOSpec, SVR4Spec
from solaris_install.transfer.ips import AbstractIPS

ZPOOL = "/usr/sbin/zpool"


class AutoInstall(object):
    """
    AutoInstall master class
    """

    BE_LOG_DIR = post_install_logs_path("")
    INSTALL_LOG = "install_log"
    AI_EXIT_SUCCESS = 0
    AI_EXIT_FAILURE = 1
    AI_EXIT_AUTO_REBOOT = 64
    TRANSFER_ZPOOL_CACHE_CHECKPOINT = "transfer-zpool-cache"
    TARGET_INSTANTIATION_CHECKPOINT = 'target-instantiation'
    FIRST_TRANSFER_CHECKPOINT = 'first-transfer'
    MANIFEST_CHECKPOINTS = ["derived-manifest", "manifest-parser"]
    CHECKPOINTS_BEFORE_TI = ["target-discovery", "target-selection", \
        "ai-configuration", TARGET_INSTANTIATION_CHECKPOINT]
    CHECKPOINTS_BEFORE_TI.extend(MANIFEST_CHECKPOINTS)
    CHECKPOINTS_BEFORE_IPS = list(CHECKPOINTS_BEFORE_TI)
    INSTALLED_ROOT_DIR = "/a"

    def __init__(self, args=None):
        """
        Class constructor
        """
        self.installed_root_dir = self.INSTALLED_ROOT_DIR
        self.auto_reboot = False
        self.doc = None
        self.exitval = self.AI_EXIT_SUCCESS
        self.derived_script = None
        self.manifest = None

        # To remember the BE when we find it.
        self._be = None

        # Parse command line arguments
        self.options, self.args = self.parse_args(args)

        # Initialize Install Engine
        self.engine = InstallEngine(debug=True, stop_on_error=True)
        self.doc = self.engine.data_object_cache

        if self.options.zonename is not None:
            # If we're installing a zone root, generate a work_dir
            # location based on the current PID.
            work_dir = "/system/volatile/install." + str(os.getpid())

            # Add ApplicationData to the DOC
            self._app_data = ApplicationData("auto-install", work_dir=work_dir)
            self._app_data.data_dict[ALT_POOL_DATASET] = \
                self.options.alt_zpool_dataset

            # Set installed_root_dir to be based off work_dir
            self.installed_root_dir = work_dir + self.INSTALLED_ROOT_DIR
        else:
            # Add ApplicationData to the DOC
            self._app_data = ApplicationData("auto-install")

        # Add profile location to the ApplySysconfig checkpoint's data dict.
        if self.options.profile is not None:
            # Try to find the ApplySysconfig data dict from
            # the DOC in case it already exists.
            as_doc_dict = None
            as_doc_dict = self.doc.volatile.get_first_child( \
                name=APPLY_SYSCONFIG_DICT)

            if as_doc_dict is None:
                # Initialize new dictionary in DOC
                as_dict = {APPLY_SYSCONFIG_PROFILE_KEY: self.options.profile}
                as_doc_dict = DataObjectDict(APPLY_SYSCONFIG_DICT, as_dict)
                self.doc.volatile.insert_children(as_doc_dict)
            else:
                # Add to existing dictionary in DOC
                as_doc_dict.data_dict[APPLY_SYSCONFIG_PROFILE_KEY] = \
                    self.options.profile

        # Add service list file to ApplicationData
        if self.options.service_list_file is not None:
            self._app_data.data_dict[AI_SERVICE_LIST_FILE] = \
                self.options.service_list_file

        self.doc.persistent.insert_children(self._app_data)

        # Clear error service
        errsvc.clear_error_list()

        # Create Logger and setup logfiles
        self.install_log_fh = None
        self.logger = None
        self.progress_ph = None
        self.setup_logs()

        if not self.options.list_checkpoints:
            self.logger.info("Starting Automated Installation Service")

        if self.options.stop_checkpoint:
            self.logger.debug("Pausing AI install before checkpoint: %s" %
                (self.options.stop_checkpoint))

        if not self.options.list_checkpoints:
            if self.manifest:
                self.logger.info("Using XML Manifest: %s" % (self.manifest))

            if self.derived_script:
                self.logger.info("Using Derived Script: %s" %
                    (self.derived_script))

            if self.options.profile:
                self.logger.info("Using profile specification: %s" %
                    (self.options.profile))

            if self.options.service_list_file:
                self.logger.info("Using service list file: %s" %
                    (self.options.service_list_file))

            if self.options.zonename:
                self.logger.info("Installing zone image for: %s" %
                    (self.options.zonename))

            if self.options.alt_zpool_dataset:
                self.logger.info("Installing zone under dataset: %s" %
                    (self.options.alt_zpool_dataset))

            if self.options.dry_run:
                self.logger.info("Dry Run mode enabled")

    def parse_args(self, args):
        """
        Method to parse command line arguments
        """

        usage = "%prog -m|--manifest <manifest>\n" + \
            "\t[-c|--profile <profile/dir>]\n" + \
            "\t[-i|--break-before-ti | -I|--break-after-ti]\n" + \
            "\t[-n|--dry-run]\n" + \
            "\t[-r|--service-list-file <service_list_file>]\n" + \
            "\t[-Z|--alt-zpool-dataset <alternate_zpool_dataset>]\n" + \
            "\t[-z|--zonename <zonename>]"

        parser = optparse.OptionParser(usage=usage)

        parser.add_option("-m", "--manifest", dest="manifest",
            help="Specify script or XML manifest to use")

        parser.add_option("-c", "--profile", dest="profile",
            help="Specify a profile or directory of profiles")

        parser.add_option("-i", "--break-before-ti", dest="break_before_ti",
            action="store_true", default=False,
            help="Break execution before Target Instantiation, testing only")

        parser.add_option("-I", "--break-after-ti", dest="break_after_ti",
            action="store_true", default=False,
            help="Break execution after Target Instantiation, testing only")

        parser.add_option("-n", "--dry-run", dest="dry_run",
            action="store_true", default=False,
            help="Enable dry-run mode for testing")

        parser.add_option("-l", "--list-checkpoints", dest="list_checkpoints",
            action="store_true", default=False,
            help=optparse.SUPPRESS_HELP)

        parser.add_option("-s", "--stop-checkpoint", dest="stop_checkpoint",
            help=optparse.SUPPRESS_HELP)

        parser.add_option("-r", "--service-list-file",
            dest="service_list_file", help="Specify service list file")

        parser.add_option("-Z", "--alt-zpool-dataset",
            dest="alt_zpool_dataset",
            help="Specify alternate zpool dataset to install into")

        parser.add_option("-z", "--zonename", dest="zonename",
            help="Specify the zonename of the image being installed")

        (options, args) = parser.parse_args(args)

        # The zonename and alternate zpool dataset options must
        # be specified together.
        if options.zonename and not options.alt_zpool_dataset:
            parser.error("Must specify an alternate zpool dataset when "
                         "installing a zone")
        elif options.alt_zpool_dataset and not options.zonename:
            parser.error("Must specify a zonename when installing into an "
                         "alternate zpool dataset")

        # If manifest argument provided, determine if script or XML manifest
        if options.manifest:
            (self.derived_script, self.manifest) =  \
                self.determine_manifest_type(options.manifest)
            if not self.derived_script and not self.manifest:
                parser.error("Must specify manifest with -m option")

        # If specifying to list checkpoints, we can ignore all other semantics
        if not options.list_checkpoints:
            # Perform some parsing semantic validation
            # Must specify one of disk or manifest
            if options.manifest is None:
                parser.error("Must specify a manifest to use for installation")

        if options.break_before_ti and options.break_after_ti:
            parser.error("Cannot specify to stop installation before " + \
                "and after Target Installation")

        if (options.break_before_ti or options.break_after_ti) and \
            options.stop_checkpoint:
            parser.error("Cannot specify a stop checkpoint and to stop " + \
                "before/after target instantiation at same time")

        # Set stop_breakpoint to be before or after TI if requested
        if options.break_before_ti:
            options.stop_checkpoint = self.TARGET_INSTANTIATION_CHECKPOINT
        elif options.break_after_ti:
            options.stop_checkpoint = self.FIRST_TRANSFER_CHECKPOINT

        return (options, args)

    @staticmethod
    def determine_manifest_type(manifest):
        """
        Determine if manifest file argument is a script or xml manifest.
        Simply check reading first two characters of file for #!
        """
        derived_script = None
        xml_manifest = None

        if manifest is None:
            return None, None
        else:
            linecache.checkcache(manifest)
            if linecache.getline(manifest, 1)[:2] == "#!":
                derived_script = manifest
            else:
                xml_manifest = manifest

        return derived_script, xml_manifest

    def validate_stop_checkpoint(self):
        """
        Validate stop checkpoint argument is valid by comparing
        against list of registered checkpoints.
        """
        cp_data_list = self.engine.get_exec_list()

        if len(cp_data_list) == 0:
            self.logger.debug("No Checkpoints have been registered to run")
        else:
            for cp in cp_data_list:
                if str(cp) == self.options.stop_checkpoint:
                    return True
        return False

    def list_checkpoints(self):
        """
        print to stdout the current list of checkpoints registered to run.
        """
        cp_data_list = self.engine.get_exec_list()

        if len(cp_data_list) == 0:
            print "No Checkpoints have been registered to run."
        else:
            print "Checkpoints will be run in the following order:"
            if self.derived_script:
                print "	%s" % (str(self.MANIFEST_CHECKPOINTS[0]))
                print "	%s" % (str(self.MANIFEST_CHECKPOINTS[1]))
            elif self.manifest:
                print "	%s" % (str(self.MANIFEST_CHECKPOINTS[1]))
            for cp in cp_data_list:
                if self.options.stop_checkpoint and \
                    str(cp) == self.options.stop_checkpoint:
                    break
                print "	%s" % (str(cp))

    def setup_logs(self):
        """
        Create the logger instanace for AI and create simple and
        detailed log files to use.
        """

        # Create logger for AI
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

        # Log progress and info messages to the console.
        self.progress_ph = AIProgressHandler(self.logger,
            skip_console_msg=(self.options.list_checkpoints or \
                              self.options.alt_zpool_dataset))
        self.progress_ph.start_progress_server()
        self.logger.addHandler(self.progress_ph)

        # Only ever send debug info to the logs, use INFO for console
        self.progress_ph.removeFilter(self.logger._prog_filter)
        self.progress_ph.setLevel(logging.INFO)
        datefmt = "%H:%M:%S"
        formatter = AIScreenFormatter(datefmt=datefmt,
                hide_progress=self.options.list_checkpoints)
        self.progress_ph.setFormatter(formatter)

        # create a install_log file handler and add it to the ai_logger

        # set the logfile names
        install_log = os.path.join(self._app_data.work_dir, self.INSTALL_LOG)
        self.install_log_fh = FileHandler(install_log)

        self.install_log_fh.setLevel(logging.DEBUG)
        if not self.options.list_checkpoints:
            self.logger.info("Install Log: %s" % (install_log))
        self.logger.addHandler(self.install_log_fh)

    @property
    def be(self):
        if self._be is not None:
            return self._be

        new_be = None
        desired = self.doc.persistent.get_first_child(Target.DESIRED,
                                                      class_type=Target)

        if desired:
            try:
                new_be = desired.get_descendants(class_type=BE, max_count=1,
                                                 not_found_is_err=True)[0]
                self._be = new_be
            except ObjectNotFoundError:
                self.logger.error("Unable to locate new BE definition")

        return new_be

    def __cleanup_before_exit(self, error_val, success_printed=False):
        """Do some clean up and set exit code.
        """

        unmount_be = False

        self.exitval = error_val
        if not self.options.list_checkpoints:
            if error_val in [self.AI_EXIT_SUCCESS, self.AI_EXIT_AUTO_REBOOT]:
                if not success_printed:
                    self.logger.info("Automated Installation succeeded.")
                if self.options.alt_zpool_dataset is None:
                    if error_val == self.AI_EXIT_AUTO_REBOOT:
                        self.logger.info("System will be rebooted now")
                    else:
                        self.logger.info("You may wish to reboot the system "
                                         "at this time.")
                unmount_be = True
            else:
                # error_val == self.AI_EXIT_FAILURE:
                self.logger.info("Automated Installation Failed")
                self.logger.info("Please see logs for more information")

        # Close logger now since it holds a handle to the log on the BE, which
        # makes it impossible to unmount the BE
        self.progress_ph.stop_progress_server()
        self.logger.close()

        # Only attempt to unmount BE if Target Instantiation has completed
        if self.options.stop_checkpoint not in self.CHECKPOINTS_BEFORE_TI:
            # If we didn't fail unmount the BE now.
            if unmount_be:
                if self.be is not None:
                    try:
                        self.be.unmount(self.options.dry_run,
                            altpool=self.options.alt_zpool_dataset)
                    except RuntimeError as ex:
                        # Use print since logger is now closed.
                        print >> sys.stderr, str(ex)
                        self.exitval = self.AI_EXIT_FAILURE

    def import_preserved_zpools(self):
        '''
        Check if we are preserving Zpools in manifest.
        If we are ensure any referenced zpools are imported.
        If importing fails, exit
        '''
        from_manifest = self.doc.find_path(
            "//[@solaris_install.auto_install.ai_instance.AIInstance?2]"
            "//[@solaris_install.target.Target?2]")

        cmd = [ZPOOL, "list", "-H", "-o", "name"]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                             logger=INSTALL_LOGGER_NAME)

        zpool_list = p.stdout.splitlines()

        if from_manifest:
            # Check if all Targets have children
            targets_have_children = False
            if from_manifest:
                for target in from_manifest:
                    if target.has_children:
                        targets_have_children = True
                        break

            if targets_have_children:
                target = from_manifest[0]
                logical = target.get_first_child(class_type=Logical)

                # Should only every be one logical
                if logical:
                    for zpool in logical.children:
                        if zpool.action in TargetSelection.PRESERVED and \
                            zpool.name not in zpool_list:
                            # Zpool being preserved but not imported
                            # Attempt to import.
                            cmd = [ZPOOL, "import", "-f", zpool.name]
                            p = Popen.check_call(cmd, stdout=Popen.STORE,
                                                 stderr=Popen.STORE,
                                                 logger=INSTALL_LOGGER_NAME,
                                                 check_result=Popen.ANY,
                                                 stderr_loglevel=logging.DEBUG)
                            if p.returncode != 0:
                                # Import failed cannot preserve, so fail AI
                                self.logger.error("Zpool '%s' with action "
                                    "'%s' failed to import. AI is unable to "
                                    "preserve unavailable zpools." % \
                                    (zpool.name, zpool.action))
                                return False
        return True

    def perform_autoinstall(self):
        """
        Main control method for performing an Automated Installation
        """

        # Check if we need to register/run derived manifest/parser checkpoints
        # If manifest argument set or derived script argument set then
        # need to parse the manifest.
        if self.manifest or self.derived_script:
            if not self.register_parse_manifest():
                self.logger.error("Derived/Parse Manifest " + \
                                  "registration failed")
                self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
                return

            if not self.execute_parse_manifest():
                self.logger.error("Derived/Parse Manifest checkpoint failed")
                self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
                return

            if self.options.stop_checkpoint is not None:
                if self.options.stop_checkpoint in self.MANIFEST_CHECKPOINTS:
                    self.logger.debug("DOC: %s" % (str(self.doc)))
                    self.logger.debug("DOC XML: %s" % \
                        (str(self.doc.get_xml_tree_str())))
                    self.logger.info("Automated Installation paused at " + \
                        "checkpoint: %s" % (self.options.stop_checkpoint))
                    self.__cleanup_before_exit(self.AI_EXIT_SUCCESS)

                    return

        errors = errsvc.get_all_errors()
        if errors:
            errstr = "Following errors occured parsing manifest:\n %s" % \
                (str(errors[0]))
            self.logger.error(errstr)
            self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
            return

        # If we are to stop before target-discovery, then stop here
        # As target-discovery is the first checkpoint in the next
        # engine run. No need to call the engine.
        if self.options.stop_checkpoint is not None:
            if self.options.stop_checkpoint == "target-discovery":
                self.logger.debug("DOC: %s" % (str(self.doc)))
                self.logger.debug("DOC XML: %s" % \
                    (str(self.doc.get_xml_tree_str())))
                self.logger.info("Automated Installation paused at " + \
                    "checkpoint: %s" % (self.options.stop_checkpoint))
                self.__cleanup_before_exit(self.AI_EXIT_SUCCESS)
                return

        # Need to register all checkpoints
        if not self.configure_checkpoints():
            self.logger.error("Registering of checkpoints failed")
            self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
            return

        # Validate stop checkpoint if specified
        if self.options.stop_checkpoint:
            if not self.validate_stop_checkpoint():
                self.logger.error("Invalid stop checkpoint specified: %s" % \
                    (self.options.stop_checkpoint))
                self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
                return

        # If specifying to list checkpoints, do so then exit
        # List of checkpoints available depend on what has just been
        # registered.
        if self.options.list_checkpoints:
            self.list_checkpoints()
            self.__cleanup_before_exit(self.AI_EXIT_SUCCESS)
            return

        # Check auto_reboot and proxy in DOC and set local definition
        ai_instance = self.doc.volatile.get_first_child(class_type=AIInstance)

        if ai_instance:
            self.auto_reboot = ai_instance.auto_reboot

            if ai_instance.http_proxy is not None and \
               len(ai_instance.http_proxy) > 0:
                # Set the HTTP Proxy environment variable
                os.environ["http_proxy"] = ai_instance.http_proxy

        self.logger.debug("Auto Reboot set to: %s" % (self.auto_reboot))

        # Ensure preserved zpools are online (imported)
        if not self.import_preserved_zpools():
            self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
            return

        # Set resume_checkpoint to None, Engine will simply resume from
        # the next checkpoint that has not been run yet.
        # Specifying a resume_checkpoint you need to have ZFS dataset
        # containing a snapshot of where resumable checkpoint was paused.
        if self.execute_checkpoints(resume_checkpoint=None,
            pause_checkpoint=self.options.stop_checkpoint,
            dry_run=self.options.dry_run):

            if self.options.stop_checkpoint not in self.CHECKPOINTS_BEFORE_IPS:
                new_be = self.be
                if new_be is None:
                    self.logger.error(
                        "Unable to determine location to transfer logs to")
                    self.__cleanup_before_exit(self.AI_EXIT_FAILURE)
                else:
                    # Write success now, to ensure it's in the log before
                    # transfer.
                    self.logger.info("Automated Installation succeeded.")

                    # Now do actual transfer of logs
                    self.logger.debug("Transferring log to %s" %
                        (new_be.mountpoint + self.BE_LOG_DIR))
                    self.install_log_fh.transfer_log(
                        new_be.mountpoint + self.BE_LOG_DIR, isdir=True)

                    # And cleanup
                    if self.auto_reboot and \
                        self.options.alt_zpool_dataset is None:
                        self.__cleanup_before_exit(
                            self.AI_EXIT_AUTO_REBOOT, True)
                    else:
                        self.__cleanup_before_exit(
                            self.AI_EXIT_SUCCESS, True)

            # Successful Execution
            elif self.options.stop_checkpoint:
                self.logger.debug("DOC: %s" % (str(self.doc)))
                self.logger.debug("DOC XML: %s" % \
                    (str(self.doc.get_xml_tree_str())))
                self.logger.info("Automated Installation paused at " + \
                    "checkpoint: %s" % (self.options.stop_checkpoint))
                self.__cleanup_before_exit(self.AI_EXIT_SUCCESS)
            else:
                self.__cleanup_before_exit(self.AI_EXIT_SUCCESS)
        else:
            self.__cleanup_before_exit(self.AI_EXIT_FAILURE)

    def register_parse_manifest(self):
        """
        Method to parse the manifest

        If derived_script argument is provided, then Use Derived Manifest
        checkpoint. Derive the manifest to use for this automated install
        and parse it.  Otherwise just parse the manifest.

        Path of execution for Derived Manifest
        - Store Derived Script in DOC for DM checkpoint to read.
        - Register Derived Manifest Checkpoint (DM)
        - Register Manifest Parser Checkpoint (MP)
        """

        try:
            # Set default positional arguments for Manifest Parser Checkpoint
            args = None

            # Set common keyword args for ManifestParser
            kwargs = dict()
            kwargs["call_xinclude"] = True

            # Require the inclusion of DOC INFO in Manifest
            # This is needed to get defaults correctly set.
            kwargs["validate_from_docinfo"] = True

            if self.derived_script:
                if not self.options.list_checkpoints:
                    self.logger.info("Deriving manifest from: %s" % \
                        (self.derived_script))

                # Store Derived Script name into DOC for DM checkpoint to read.
                # Check if derived script path is on volatile doc
                dm = self.doc.volatile.get_first_child(
                    name=DERIVED_MANIFEST_DATA)

                if dm is not None:
                    # Just change it's value
                    dm.script = self.derived_script
                else:
                    # Insert a new child
                    dm = DerivedManifestData(DERIVED_MANIFEST_DATA, \
                        script=self.derived_script)
                    self.doc.volatile.insert_children(dm)

                if not self.options.list_checkpoints:
                    self.logger.info("Derived %s stored" % (dm.script))

                    # Register Derived Manifest checkpoint
                    self.logger.info("Registering Derived Manifest " \
                        "Module Checkpoint")

                self.engine.register_checkpoint("derived-manifest",
                    "solaris_install.auto_install.checkpoints.dmm",
                    "DerivedManifestModule", args=None, kwargs=None)
            elif self.manifest:
                # Set specific arguments for Manifest Parser Checkpoint
                kwargs['manifest'] = self.manifest
            else:
                # No manifest specified to parse
                return True

            if not self.options.list_checkpoints:
                self.logger.debug("Registering Manifest Parser Checkpoint")

            self.engine.register_checkpoint("manifest-parser",
                                    "solaris_install.manifest.parser",
                                    "ManifestParser", args=args, kwargs=kwargs)
            return True
        except Exception as ex:
            self.logger.debug("Uncaught exception parsing manifest: %s" % \
                (str(ex)))
            return False

    def execute_parse_manifest(self):
        """
        Execute derived or/and manifest pareser checkpoints
          - DM checkpoint will read script from DOC
          - DM will derive manifest and store final location in DOC
          - MP will read DOC for manifest to parse, if not passed any
            manifest as an explicit argument. (This is not implemented yet)
        """
        # Execute Checkpoints
        if not self.options.list_checkpoints:
            if self.derived_script:
                self.logger.debug("Executing Derived Manifest and Manifest " \
                        "Parser Checkpoints")
            else:
                self.logger.debug("Executing Manifest Parser Checkpoint")

        if self.options.stop_checkpoint in self.MANIFEST_CHECKPOINTS:
            pause_cp = self.options.stop_checkpoint
        else:
            pause_cp = None

        if not self.execute_checkpoints(pause_checkpoint=pause_cp, \
            dry_run=False):
            return False

        # If derived manifest run, read the stored manifest location
        # from pm.manifest.
        if self.derived_script:
            pm = self.doc.volatile.get_first_child(name=MANIFEST_PARSER_DATA)
            if pm is None or pm.manifest is None:
                self.logger.error("Derived Manifest Failed, manifest not set")
                return False

            # Ideal Path - We have a parsed manifest at this point
            self.logger.info("DM set manifest to: %s" % (pm.manifest))
            self.manifest = pm.manifest

        self.logger.info("Manifest %s successfully parsed" % (self.manifest))
        self.logger.debug("DOC (tree format):\n%s\n\n\n" %
            (str(self.engine.data_object_cache)))
        self.logger.debug("DOC (xml_format):\n%s\n\n\n" %
            (str(self.engine.data_object_cache.get_xml_tree_str())))

        return True

    def execute_checkpoints(self, resume_checkpoint=None,
        pause_checkpoint=None, dry_run=False):
        """
        Wrapper to the execute_checkpoint method
        """

        # Get execution list from engine to determine of any checkpoints
        # to run, if not return false
        if len(self.engine.get_exec_list(None, None)) == 0:
            self.logger.warning("No checkpoints to execute")
            return False

        self.logger.debug("Executing Engine Checkpoints...")
        if resume_checkpoint is not None:
            self.logger.debug("Resuming at checkpoint: %s" % \
                (resume_checkpoint))

        if pause_checkpoint is not None:
            self.logger.debug("Pausing before checkpoint: %s" %
                (pause_checkpoint))

        try:
            if resume_checkpoint is not None:
                (status, failed_cps) = self.engine.resume_execute_checkpoints(
                    resume_checkpoint, pause_before=pause_checkpoint,
                    dry_run=dry_run, callback=None)
            else:
                (status, failed_cps) = self.engine.execute_checkpoints(
                    start_from=None, pause_before=pause_checkpoint,
                    dry_run=dry_run, callback=None)
        except (ManifestError, ParsingError) as ex:
            self.logger.error("Manifest parser checkpoint error:")
            self.logger.error("\t%s" % (str(ex)))
            self.logger.debug(traceback.format_exc())
            return False
        except (SelectionError) as ex:
            self.logger.error("Target selection checkpoint error:")
            self.logger.error("\t%s" % (str(ex)))
            self.logger.debug(traceback.format_exc())
            return False
        except (ValueError) as ex:
            self.logger.error("Value errors occured:")
            self.logger.error("\t%s" % (str(ex)))
            self.logger.debug(traceback.format_exc())
            return False
        except (AIConfigurationError) as ex:
            self.logger.error("AI Configuration checkpoint error:")
            self.logger.error("\t%s" % (str(ex)))
            self.logger.debug(traceback.format_exc())
            return False
        except (RollbackError, UnknownChkptError, UsageError) as ex:
            self.logger.error("RollbackError, UnknownChkptError, UsageError:")
            self.logger.error("\t%s" % (str(ex)))
            self.logger.debug(traceback.format_exc())
            raise RuntimeError(str(ex))
        except Exception, ex:
            self.logger.debug("%s" % (traceback.format_exc()))
            raise RuntimeError(str(ex))

        self.logger.debug("Checkpoints Completed: DOC: \n%s\n\n" % \
                          (self.doc))
        self.logger.debug("Checkpoints Completed: "
                          "DOC (xml_format):\n%s\n\n\n" %
            (str(self.engine.data_object_cache.get_xml_tree_str())))

        if status != InstallEngine.EXEC_SUCCESS:
            self.logger.critical("Failed Checkpoints:")
            for failed_cp in failed_cps:
                err_data = errsvc.get_errors_by_mod_id(failed_cp)[0]
                self.logger.critical("\t%s" % (failed_cp))
                self.logger.exception(err_data.error_data[ES_DATA_EXCEPTION])
            return False
        else:
            return True

    def configure_checkpoints(self):
        """
        Wrapper to configure required checkpoints for performing an
        automated installation
        """
        # Need to set following Checkpoints for installation.  Checkpoints
        # marked with a 'G' are applicable when installing a global zone.
        # Checkpoings marked with a 'N' are application when installing a
        # non-global zone.
        #   GN -- Derived Manifest (If script passed as argument)
        #   GN -- Manifest Parser (If manifest passed or derived)
        #   G- -- Target Discovery
        #   G- -- Target Selection
        #   -N -- Target Selection Zone
        #   GN -- AI Configuration
        #   G- -- Device Driver Update - Install Root
        #   G- -- Target Instantiation
        #   -N -- Target Instantiation Zone
        #   GN -- Transfer
        #   GN -- Target Configuration
        #   G- -- Device Driver Update - New BE

        try:
            if not self.options.list_checkpoints:
                self.logger.info("Configuring Checkpoints")

            # Register TargetDiscovery
            if self.options.alt_zpool_dataset is None:
                self.engine.register_checkpoint("target-discovery",
                                "solaris_install.target.discovery",
                                "TargetDiscovery", args=None, kwargs=None)

            # Register TargetSelection
            if self.options.alt_zpool_dataset is None:
                self.logger.debug("Adding Target Selection Checkpoint")
                self.engine.register_checkpoint("target-selection",
                    "solaris_install.auto_install.checkpoints."
                    "target_selection", "TargetSelection", args=None,
                    kwargs=None)
            else:
                self.logger.debug("Adding Target Selection Zone Checkpoint")
                self.engine.register_checkpoint("target-selection",
                    "solaris_install.auto_install.checkpoints."
                    "target_selection_zone", "TargetSelectionZone", args=None,
                    kwargs={"be_mountpoint": self.installed_root_dir})

            # Register AIConfiguration
            self.logger.debug("Adding AI Configuration Checkpoint")
            self.engine.register_checkpoint("ai-configuration",
                "solaris_install.auto_install.checkpoints.ai_configuration",
                "AIConfiguration", args=None, kwargs=None)

            # Register TargetInstantiation
            if self.options.alt_zpool_dataset is None:
                self.logger.debug("Adding Target Instantiation Checkpoint")
                self.engine.register_checkpoint(
                                self.TARGET_INSTANTIATION_CHECKPOINT,
                                "solaris_install.target.instantiation",
                                "TargetInstantiation", args=None, kwargs=None)
            else:
                self.logger.debug("Adding Target Instantiation Zone "
                    "Checkpoint")
                self.engine.register_checkpoint("target-instantiation",
                                "solaris_install/target/instantiation_zone",
                                "TargetInstantiationZone", args=None,
                                kwargs=None)

            # Add destination for transfer nodes, and register checkpoints.
            sw_nodes = self.doc.volatile.get_descendants(class_type=Software)
            if not sw_nodes:
                # Fail now, something needs to be specified here!
                self.logger.error("No software has been specified to install. "
                    "Manifest must contain at least one <software> element "
                    "containing as <software_data> with the 'install' action.")
                return False

            image_action = AbstractIPS.CREATE  # For first IPS only
            transfer_count = 0  # For generating names if none provided
            for sw in sw_nodes:
                transfer_count += 1
                if sw.name is None or len(sw.name) == 0:
                    # Generate a name, setting internal attribute
                    sw._name = "generated-transfer-%d-%d" % \
                        (os.getpid(), transfer_count)

                # Add first transfer checkpoint name to list of checkpoints
                # to ensure -I option succeeds.
                if transfer_count == 1:
                    self.CHECKPOINTS_BEFORE_IPS.append(sw.name)
                    if self.options.stop_checkpoint is not None:
                        if self.options.stop_checkpoint == \
                            self.FIRST_TRANSFER_CHECKPOINT:
                            self.options.stop_checkpoint = sw.name

                # Ensure there is at least one software_data element with
                # Install action exists, and that all software_data elements
                # contain at least one 'name' sub element.
                found_install_sw_data = False
                tran_type = sw.tran_type.upper()
                for sw_child in sw.children:
                    found_sw_data = False
                    if tran_type == "IPS" and isinstance(sw_child, IPSSpec):
                        found_sw_data = True
                        if sw_child.action == IPSSpec.INSTALL:
                            found_install_sw_data = True
                    elif tran_type == "CPIO" and \
                        isinstance(sw_child, CPIOSpec):
                        found_sw_data = True
                        if sw_child.action == CPIOSpec.INSTALL:
                            found_install_sw_data = True
                    elif tran_type == "SVR4" and \
                        isinstance(sw_child, SVR4Spec):
                        found_sw_data = True
                        if sw_child.action == SVR4Spec.INSTALL:
                            found_install_sw_data = True
                    elif isinstance(sw_child, Source) or \
                         isinstance(sw_child, Destination):
                        # Skip these
                        continue
                    else:
                        self.logger.error("Unsupported transfer type: %s"
                            % (tran_type))
                        return False

                    if found_sw_data and len(sw_child.contents) == 0:
                        self.logger.error("Invalid manifest specification "
                            "for <software_data> element. Must specify at "
                            "least one package to install/uninstall.")
                        return False

                if not found_install_sw_data:
                    self.logger.error("No packages specified to install. "
                        "Manifest must contain at least one <software_data> "
                        "element with 'install' action.")
                    return False

                self.logger.debug("Setting destination for transfer: %s to %s"
                    % (sw.name, self.installed_root_dir))
                dst = sw.get_first_child(class_type=Destination)
                if dst is None:
                    dst = Destination()
                    if sw.tran_type.upper() == "IPS":
                        image = Image(self.installed_root_dir, image_action)

                        if self.options.zonename is None:
                            img_type = ImType("full", zone=False)
                        else:
                            img_type = ImType("full", zone=True)

                        image.insert_children(img_type)
                        dst.insert_children(image)
                        image_action = AbstractIPS.EXISTING
                    else:
                        directory = Dir(self.installed_root_dir)
                        dst.insert_children(directory)
                    sw.insert_children(dst)
                    # Next images are use_existing, not create.
                else:
                    self.logger.error(
                        "Unexpected destination in software node: %s" % \
                        (sw.name))
                    return False

                # Register a Transfer checkpoint suitable for the selected
                # Software node
                ckpt_info = create_checkpoint(sw)
                if ckpt_info is not None:
                    self.logger.debug("Adding Transfer Checkpoint: "
                        "%s, %s, %s" % ckpt_info)
                    if self.options.zonename:
                        # If we're installing a zone, append a kwarg
                        # specifying the zone's zonename to the transfer
                        # checkpoint
                        self.engine.register_checkpoint(*ckpt_info,
                            kwargs={"zonename": self.options.zonename})
                    else:
                        self.engine.register_checkpoint(*ckpt_info)
                else:
                    self.logger.error(
                        "Failed to register the softare install: %s"
                        % (sw.name))
                    return False

            # Register ICT Checkpoints
            #=========================
            # 1. Initialize SMF Repository
            if self.options.zonename is None:
                self.engine.register_checkpoint("initialize-smf",
                    "solaris_install.ict.initialize_smf",
                    "InitializeSMF", args=None, kwargs=None)
            else:
                self.engine.register_checkpoint("initialize-smf-zone",
                    "solaris_install.ict.initialize_smf",
                    "InitializeSMFZone", args=None, kwargs=None)

            # 2. Boot Configuration
            if self.options.zonename is None:
                self.engine.register_checkpoint("boot-configuration",
                    "solaris_install.boot.boot",
                    "SystemBootMenu", args=None, kwargs=None)

            # 3. Update dumpadm / Dump Configuration
            if self.options.zonename is None:
                self.engine.register_checkpoint("update-dump-adm",
                    "solaris_install.ict.update_dumpadm",
                    "UpdateDumpAdm", args=None, kwargs=None)

            # 4. Setup Swap in Vfstab
            self.engine.register_checkpoint("setup-swap",
                "solaris_install.ict.setup_swap",
                "SetupSwap", args=None, kwargs=None)

            # 5. Set Flush IPS Content Flag
            self.engine.register_checkpoint("set-flush-ips-content-cache",
                "solaris_install.ict.ips",
                "SetFlushContentCache", args=None, kwargs=None)

            # 6. Device Configuration / Create Device Namespace
            if self.options.zonename is None:
                self.engine.register_checkpoint("device-config",
                    "solaris_install.ict.device_config",
                    "DeviceConfig", args=None, kwargs=None)

            # 7. Transfer System Configuration To BE / ApplySysConfig
            if self.options.profile is not None:
                self.engine.register_checkpoint("apply-sysconfig",
                    "solaris_install.ict.apply_sysconfig",
                    "ApplySysConfig", args=None, kwargs=None)

            # 8. Transfer Zpool Cache and hostid (x86)
            if self.options.zonename is None:
                self.add_transfer_zpool_cache()
                self.engine.register_checkpoint(
                    self.TRANSFER_ZPOOL_CACHE_CHECKPOINT,
                    "solaris_install.ict.transfer_files",
                    "TransferFiles", args=None, kwargs=None)

            # 9. Boot Archive
            if self.options.zonename is None:
                self.engine.register_checkpoint("boot-archive",
                    "solaris_install.ict.boot_archive",
                    "BootArchive", args=None, kwargs=None)

            # 10. Transfer Files to New BE
            self.add_transfer_files()
            self.engine.register_checkpoint(TRANSFER_FILES_CHECKPOINT,
                "solaris_install.ict.transfer_files",
                "TransferFiles", args=None, kwargs=None)

            # 11. CreateSnapshot before reboot
            self.engine.register_checkpoint("create-snapshot",
                "solaris_install.ict.create_snapshot",
                "CreateSnapshot", args=None, kwargs=None)

        except Exception as ex:
            self.logger.debug(
                "An execption occurred registering checkpoints: %s\n%s" %
                (str(ex), traceback.format_exc()))
            return False

        return True

    def add_transfer_zpool_cache(self):
        """
            Create dataobjectdict dictionary containing src/dest
            pairs for zpool.cache and possibly hostid files to be transferred
            to the new boot environment.

            This is required to ensure all data pools created get imported
            automatically on reboot.

            This transfer must happen before the boot archive is updated
            otherwise the hostid will not get maintained on reboot.
        """
        # Check for existence of transfer-ai-files data object dictionary,
        # insert if not found
        tf_doc_dict = None
        tf_doc_dict = self.doc.volatile.get_first_child( \
            name=self.TRANSFER_ZPOOL_CACHE_CHECKPOINT)

        if tf_doc_dict is None:
            # Initialize dictionary in DOC
            tf_dict = dict()
            tf_doc_dict = DataObjectDict(self.TRANSFER_ZPOOL_CACHE_CHECKPOINT,
                tf_dict)
            self.doc.volatile.insert_children(tf_doc_dict)
        else:
            tf_dict = tf_doc_dict.data_dict

        # To ensure data pools get imported on boot we need to copy over
        # the zpool.cache to new BE.
        tf_dict['/etc/zfs/zpool.cache'] = 'etc/zfs/zpool.cache'

        # On X86 we need to transfer the hostid as well. This is not required
        # for sparc installs as hostid is maintained in NVRAM.
        if platform.processor() == "i386":
            tf_dict['/etc/hostid'] = 'etc/hostid'

        self.logger.debug("Zpool cache transfer list:\n%s" %
            (str(tf_dict)))

    def add_transfer_files(self):
        """
            Create dataobjectdict dictionary containing src/dest
            pairs for files that are to be transferred to the new
            boot environment.
        """
        # Check for existence of transfer-ai-files data object dictionary,
        # insert if not found
        tf_doc_dict = None
        tf_doc_dict = self.doc.volatile.get_first_child( \
            name=TRANSFER_FILES_CHECKPOINT)

        if tf_doc_dict is None:
            # Initialize dictionary in DOC
            tf_dict = dict()
            tf_doc_dict = DataObjectDict(TRANSFER_FILES_CHECKPOINT,
                tf_dict)
            self.doc.volatile.insert_children(tf_doc_dict)
        else:
            tf_dict = tf_doc_dict.data_dict

        # If using dmm, transfer script and derived manifest
        if self.derived_script:
            dm = self.doc.volatile.get_first_child(
                    name=DERIVED_MANIFEST_DATA)
            if dm is not None and dm.script is not None:
                tf_dict[dm.script] = \
                    post_install_logs_path('derived/manifest_script')

            mp = self.doc.volatile.get_first_child(name=MANIFEST_PARSER_DATA)
            if mp is not None and mp.manifest is not None:
                tf_dict[mp.manifest] = \
                    post_install_logs_path('derived/manifest.xml')
        # Else transfer the XML manifest passed in
        else:
            tf_dict[self.manifest] = post_install_logs_path('ai.xml')

        if not self.options.zonename:
            # Transfer smf logs
            tf_dict['/var/svc/log/application-auto-installer:default.log'] = \
                post_install_logs_path('application-auto-installer:default.log')
            tf_dict['/var/svc/log/application-manifest-locator:default.log'] = \
                post_install_logs_path(
                'application-manifest-locator:default.log')

            # Transfer AI Service Discovery Log
            tf_dict[system_temp_path('ai_sd_log')] = \
                post_install_logs_path('ai_sd_log')

            # Transfer /var/adm/messages
            tf_dict['/var/adm/messages'] = post_install_logs_path('messages')

        # Possibly copy contents of ApplicationData.work_dir, however
        # for standard AI install, this is /system/volatile, so not feasable
        # However for zones install, it would makes sense as work_dir in
        # that scenario would be unique to each AI instance and would have
        # limited number of files.
        # e.g.
        #  dest = post.install_logs_path(\
        #      os.path.basename(self._app_data.work_dir))
        #  tf_dict[self._app_data.work_dir] = dest

        self.logger.debug("Transfer files list:\n%s" %
            (str(tf_dict)))


class AIScreenFormatter(logging.Formatter):
    """ AI-Specific Formatter class. Suppresses traceback printing to
    the screen by overloading the format() method.

    Checks if log message is MAX_INT (Progress Log) or Normal log and
    formats message appropriately.
    """

    def __init__(self, fmt=None, datefmt=None, hide_progress=True):
        """Initialize formatter class.

           Consume hide_progress boolean for local processing.
        """
        self.hide_progress = hide_progress

        logging.Formatter.__init__(self, fmt, datefmt)

    def format(self, record):
        """ Overload method to prevent the traceback from being printed.
        """
        record.message = record.getMessage()
        record.asctime = self.formatTime(record, self.datefmt)

        formatted_str = ""
        fmt = None

        if self.hide_progress:
            # Don't output progress information for -l option
            if record.levelno != MAX_INT:
                fmt = "%(message)s"
        else:
            if record.levelno == MAX_INT:
                fmt = "%(asctime)-11s %(progress)s%% %(message)s"
            else:
                fmt = "%(asctime)-11s %(message)s"

        if fmt is not None:
            formatted_str = fmt % record.__dict__

        return formatted_str


class AIProgressHandler(ProgressHandler):
    """ AI-Specific ProgressHandler. """
    def __init__(self, logger, hostname=None, portno=None,
                 skip_console_msg=False):
        if hostname is not None:
            self.hostname = hostname
        else:
            self.hostname = 'localhost'

        self.engine_skt = None
        self.server_up = False
        self.logger = logger
        self.skip_console_msg = skip_console_msg

        # Get a port number
        self.skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if portno is not None:
            self.portno = portno
            try:
                self.skt.bind((self.hostname, self.portno))
                self.skt.listen(5)
            except socket.error:
                self.logger.error("AIProgresHandler init failed")
                self.logger.debug("%s" % (traceback.format_exc()))
                return None
        else:
            random.seed()
            # Continue looping until skt.listen(5) does not cause socket.error
            while True:
                try:
                    # Get a random port between 10000 and 30000
                    self.portno = random.randint(10000, 30000)
                    self.skt.bind((self.hostname, self.portno))
                    self.skt.listen(5)
                    break
                except socket.error, msg:
                    self.skt.close()
                    self.skt = None
                    continue

        ProgressHandler.__init__(self, self.hostname, self.portno)

    def start_progress_server(self):
        """ Starts the socket server stream to receive progress messages. """
        if not self.server_up:
            self.logger.debug("Starting up Progress Handler")
            self.server_up = True
            self.engine_skt, address = self.skt.accept()
            thread.start_new_thread(self.progress_server,
                (self.progress_receiver, ))
            time.sleep(1)

    def stop_progress_server(self):
        """ Stop the socket server stream. """
        if self.server_up:
            self.server_up = False
            self.logger.debug("Shutting down Progress Handler")

    def progress_server(self, cb):
        """ Actual spawned progress_server process. """
        try:
            while self.server_up:
                percentage, msg = self.parse_progress_msg(self.engine_skt, cb)
            self.engine_skt.close()
        except Exception, ex:
            self.logger.error("Progress Server Error")
            self.logger.debug("%s" % (str(ex)))

    @staticmethod
    def parse_progress_msg(skt, cb):
        """Parse the messages sent by the client."""
        total_len = 0
        total_data = list()
        size = sys.maxint
        size_data = sock_data = ''
        recv_size = 8192
        percent = None
        msg = None

        while total_len < size:
            sock_data = skt.recv(recv_size)
            if not total_data:
                if len(sock_data) > 4:
                    size_data += sock_data
                    size = struct.unpack('@i', size_data[:4])[0]
                    recv_size = size
                    if recv_size > 524288:
                        recv_size = 524288
                    total_data.append(size_data[4:])
                else:
                    size_data += sock_data
            else:
                total_data.append(sock_data)
            total_len = sum([len(i) for i in total_data])
            message = ''.join(total_data)
            if message:
                # This is a callback function that sends the message to
                # the receiver
                cb(message)
                percent, msg = message.split(' ', 1)
            break
        return percent, msg

    def progress_receiver(self, msg):
        """Receive a message, show on screen and/or console"""

        # Default to showing on stdout
        print "%s" % (msg)

        if not self.skip_console_msg and not users_on_console():
            # Also log to console if no-one is logged in there.
            try:
                with open("/dev/sysmsg", "w+") as fh:
                    fh.write("%s\n" % (msg))
            except IOError:
                # Quietly fail - can't log or we cause a repeating loop
                pass

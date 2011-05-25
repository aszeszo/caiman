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

'''
Class representing the Installation Execution Engine
'''

import decimal
import imp
import inspect
import logging
import os
import shutil
import string
import tempfile
import threading
import warnings

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc

from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET

from osol_install.install_utils import get_argspec
from solaris_install.data_object import DataObject
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.engine.checkpoint_data import CheckpointData
from solaris_install.logger import InstallLogger, LogInitError, \
    INSTALL_LOGGER_NAME
from solaris_install.target.logical import Filesystem

LOGGER = None


class EngineError(StandardError):
    '''Base class for engine specific errors'''
    pass


class RollbackError(EngineError):
    '''Error during an attempt to rollback'''
    _MSG = "Cannot rollback to '%s' checkpoint: %s"

    def __init__(self, cp_name, reason):
        msg = RollbackError._MSG % (cp_name, reason)
        self.checkpoint = cp_name
        EngineError.__init__(self, msg)


class SingletonError(EngineError):
    '''Occurs when one attempts to instantiate a second singleton'''
    pass


class UsageError(EngineError):
    '''General usage error for an engine call'''
    pass


class NoCacheError(RollbackError, IOError):
    '''Error during rollback - can't find the DOC'''
    def __init__(self, cp_name, cache_path):
        self.cache_path = cache_path
        RollbackError.__init__(self, cp_name,
                               "Cache does not exist at path: %s" % cache_path)


class ChkptRegistrationError(EngineError):
    '''Error occur while trying to register a checkpoint'''
    pass


class UnknownChkptError(UsageError):
    '''Error occurs when attempting to access a checkpoint that doesn't
    exist'''
    pass


class NoDatasetError(UsageError):
    '''ZFS dataset is not specified.'''
    pass


class FileNotFoundError(UsageError):
    ''' The specified zfs dataset is not found, or
        no DataObjectCache snapshot exist in the provided ZFS dataset.
    '''
    pass


class EngineData(DataObject):
    '''Root node below DataObjectCache for storing all install
       engine related data
    '''

    def __init__(self):
        DataObject.__init__(self, InstallEngine.ENGINE_DOC_ROOT)

    def to_xml(self):
        ''' This internal engine info node will not be saved to XML '''
        return None

    @classmethod
    def from_xml(cls, xml_node):
        ''' This internal engine info node will not be read from XML '''
        return None

    @classmethod
    def can_handle(cls, xml_node):
        ''' This internal engine info node will not be read from XML '''
        return False


class InstallEngine(object):
    ''' Install execution engine '''

    CP_THREAD = "CheckpointThread"
    EXEC_FAILED = "Execution Failed"
    EXEC_SUCCESS = "Execution Successful"
    EXEC_CANCELED = "Execution Canceled"
    CP_INIT_FAILED = "Checkpoint Initialization Failed"
    FATAL_INTERNAL = "InstallEngineInternal"
    TMP_CACHE_ENV = "TEMP_DOC_DIR"
    TMP_CACHE_PATH_ROOT_DEFAULT = "/var/run/install_engine"
    TMP_CACHE_PATH_PREFIX = "engine."
    CACHE_FILE_NAME_PREFIX = ".data_cache."
    CACHE_FILE_NAME = CACHE_FILE_NAME_PREFIX + "%(checkpoint)s"
    SNAPSHOT_NAME = ".step_%(checkpoint)s"
    ENGINE_DOC_ROOT = "Engine-DOC-Root-Node"

    #_LAST is the the engine internal checkpoint for keeping state
    _LAST = None
    _LAST_NAME = "latest"

    NUM_CALLBACK_ARGS = 2

    _instance = None

    class _PseudoThread(threading.Thread):
        ''' thread used for execute_checkpoints() for the blocking case '''
        start = threading.Thread.run

    def __new__(cls, loglevel=None, debug=False, dataset=None,
                stop_on_error=True):

        if InstallEngine._instance is None:
            return object.__new__(cls)
        else:
            raise SingletonError("InstallEngine instance already exists",
                                 InstallEngine._instance)

    def __init__(self, loglevel=None, debug=False, dataset=None,
                 stop_on_error=True):
        ''' Initializes the InstallEngine

        Input:
            - loglevel: Optional.  Defaults to None.
              Logging level to use for everything: application,
              engine and checkpoints.  This value is used while instantiating
              the logger.  If not specified, the default logging level for the
              logging service is used.

            - Debug: Optional.  Default to false.
              If true, copies of DataObjectCache snapshot will not be
              removed from the directory defined to store temporary snapshots
              of DataObjectCache.

            - Dataset: Optional.  Default to None.
              ZFS Dataset to be used by the engine to create ZFS snapshots
              and DataObjectCache snapshots for supporting stop and resume.
              This value can be set at a later time, if not set here.
              Value of ZFS dataset specified will not be validated here to
              ensure it exists.  If dataset does not exist at this point,
              it will not be created.

            - stop_on_error: Optional.  Default to True.
              This flag controls whether checkpoint execution should continue
              if a checkpoint fails.  This value can be set at a later time,
              if not set here.

        Output:
            None

        Raises:
            None
        '''
        InstallEngine._instance = self

        # Logging must be instantiated before instantiating the DataObjectCache
        # because data object cache might need to make logging calls.
        self._init_logging(loglevel)

        # The "latest" checkpoint is not really a "regular" checkpoint that
        # gets executed.  It's an internal mechanism that the engine uses
        # to keep track of the "latest" successful execution.  It is created
        # as a checkpoint so all the DOC and ZFS snapshot operations
        # for regular checkpoints can be done with this too.
        InstallEngine._LAST = CheckpointData(InstallEngine._LAST_NAME,
                                             InstallEngine._LAST_NAME, None,
                                             InstallEngine._LAST_NAME, 0,
                                             None, None)

        # initialize the data object cache
        self.data_object_cache = DataObjectCache()

        self.debug = debug
        self._dataset = None
        self.dataset = dataset
        self.stop_on_error = stop_on_error
        self.__currently_executing = None

        # Use 8 decimal precision for progress.  Using less precision
        # will cause problems when the estimated progress for some
        # checkpoints are drastically different than the others.
        # Always round down while calculating the progress ratios
        d_context = decimal.Context(prec=8, rounding=decimal.ROUND_DOWN)
        decimal.setcontext(d_context)
        self.__current_completed = decimal.Decimal("0")

        self.__blocking_results = None
        self.__resume_exec_cp_ok = True
        self._checkpoints = []
        self.checkpoint_thread = None
        self._tmp_cache_path = None
        self._checkpoint_lock = threading.Lock()
        self._cancel_event = threading.Event()

        # The following will be set to True anytime a ZFS snapshot call is made
        self.zfs_snapshots_modifed = False

    def __del__(self):
        if self._tmp_cache_path is not None and not self.debug:
            shutil.rmtree(self._tmp_cache_path, ignore_errors=True)
        self._tmp_cache_path = None

    def _init_logging(self, loglevel):
        ''' Initialize logging and set the loglevel if provided '''
        logging.setLoggerClass(InstallLogger)
        global LOGGER
        LOGGER = logging.getLogger(INSTALL_LOGGER_NAME)
        InstallLogger.ENGINE = self
        if loglevel is not None:
            LOGGER.setLevel(loglevel)
        if not isinstance(LOGGER, InstallLogger):
            # Occurs if some module has called logging.getLogger prior to
            # this function being run. As this means we don't have control
            # over the logger associated with INSTALL_LOGGER_NAME, there's
            # a programming error and we need to abort
            raise LogInitError("Wrong logger class: got %s, expected %s" %
                               (LOGGER.__class__, InstallLogger))

    @classmethod
    def get_instance(cls):
        '''Returns the InstallEngine singleton'''
        if cls._instance is None:
            raise SingletonError("%s not yet initialized" % cls)

        return cls._instance

    @property
    def dataset(self):
        ''' Returns the ZFS dataset to used for stop/resume '''
        return self._dataset

    @dataset.setter
    def dataset(self, dataset):
        ''' Sets the dataset to be used for stop/resume '''
        if dataset is not None and not isinstance(dataset, Filesystem):
            dataset = Filesystem(dataset)
        self._dataset = dataset

    def register_checkpoint(self, checkpoint_name, module_path,
                            checkpoint_class_name, insert_before=None,
                            loglevel=None, args=(), kwargs=None):
        '''Input:
            * checkpoint_name(required): Name used for referring to the
              checkpoint after registration.  This name must be unique among
              the list of registered checkpoints.  Furthermore,
              checkpoint names are restricted to have only
              ASCII letters, numbers, dots, dashes and underscore.
              Length of the name must be less than 256 characters.

            * module_path (required): Path of the module containing the
              checkpoint implementation.  Value provided will be used in the
              Python imp.find_module() call.  If a relative path is provided,
              it must be resolvable by the PYTHONPATH.  If a full path is
              provided and the path is outside of
              the python sys.path, the ImportWarning will be raised.

            * checkpoint_class_name(required): a string specifying the
              class name of the checkpoint object to be instantiated.

            * args (optional): One or more arguments can be specified for the
              constructor of the checkpoint object.  The order in which the
              arguments are specified will be the order in which they are
              passed.  By default, no arguments are passed.

            * insert_before(optional): Insert this checkpoint before the
              named checkpoint.  The named checkpoint must have been
              previously registered, and it must have not been executed.
              Even though this argument comes after the *args parameter,
              it will not be passed into the constructor of the checkpoint
              object.  Because Python does not allow keyword arguments to
              appear before arguments, it has to come after the args parameter.

            * Log level for checkpoint(optional): If the application wants to
              use a different log level for the checkpoint, it can specify
              it using the keyword argument loglevel=<log_level>.  The
              log level specified must be valid for the log service.
              The value specified in the loglevel keyword will be used by
              the engine as part of setup prior to a checkpoint's execution.
              The loglevel keyword argument will not get passed into the
              constructor of the checkpoint.

            * kwargs(optional): One or more keyword arguments can be
              specified for the constructor of the checkpoint object.
              The order in which the keyword arguments are specified will
              be the order in which they are passed.  By default, no keyword
              arguments are passed.

        Output:
            None

        Raise:
            * ImportError: Error in finding the specified module or
              checkpoint object in the module.

            * ChkptRegistrationError: This error will be raised for the
              any problem with registering the checkpoint.  The error message
              will indicate the exact cause of the problem.

            * UnknownChkptError: Name specified in insert_before argument
              is not found.

            * ChkptExecutedError: The checkpoint specified in the
              insert_before argument has been executed.

            * ValueError: Provided loglevel is not valid.

            * ImportWarning: The provide module path from which the module
              will be imported is outside of sys.path.
        '''

        # Checkpoint registration can not happen while checkpoint's execution
        # is in progress.  Make sure we are not in the middle of
        # executing checkpoints
        if self._is_executing_checkpoints():
            raise ChkptRegistrationError("Checkpoint registration is "
                "not allowed during checkpoint execution.")

        if checkpoint_name is None:
            raise ChkptRegistrationError("checkpoint_name must be specified.")

        if (len(checkpoint_name)) < 1 or (len(checkpoint_name) > 256):
            raise ChkptRegistrationError("Length of checkpoint_name must be "
                                         "between 1-256 characters.")

        # Verify checkpoint names are restricted to have only
        # ASCII letters, numbers, dots, dashes and underscore.
        allowed = set(string.ascii_letters + string.digits + '.' + '-' + '_')
        if set(checkpoint_name) > allowed:
            raise ChkptRegistrationError("checkpoint_name is restricted to "
                                         "have only ASCII letters, numbers, "
                                         "dots, dashes and underscore.")

        if (module_path is None) or (module_path == ""):
            raise ChkptRegistrationError("module_path must not be " +
                                         str(module_path))

        if (checkpoint_class_name is None) or (checkpoint_class_name == ""):
            raise ChkptRegistrationError("checkpoint_class_name must not be " +
                                         str(checkpoint_class_name))

        LOGGER.debug("Engine registering:")
        LOGGER.debug("name: " + str(checkpoint_name))
        LOGGER.debug("module_path: " + str(module_path))
        LOGGER.debug("checkpoint_class_name: " + str(checkpoint_class_name))
        LOGGER.debug("args: " + str(args))
        LOGGER.debug("kwargs: " + str(kwargs))
        LOGGER.debug("insert_before: " + str(insert_before))
        LOGGER.debug("log_level: " + str(loglevel))
        LOGGER.debug("=============================")

        if checkpoint_name == InstallEngine._LAST.name:
            raise ChkptRegistrationError("Checkpoint name '%s' is reserved" %
                                         InstallEngine._LAST.name)

        # Go through list of existing checkpoints, and make sure the name
        # has not already been used, and insert_before value, if defined,
        # has not been executed.

        insert_index = len(self._checkpoints)
        for cp in self._checkpoints:
            if (cp.name == checkpoint_name):
                raise ChkptRegistrationError(checkpoint_name +
                                             " has already been used.")

            if (cp.name == insert_before):
                if cp.completed:
                    raise ChkptRegistrationError(insert_before +
                                                 " has been executed.")
                else:
                    insert_index = self._checkpoints.index(cp)

        if (insert_before is not None and
            insert_index == len(self._checkpoints)):

            raise ChkptRegistrationError("insert_before checkpoint: " + \
                insert_before + "is not a valid checkpoint")

        if module_path.startswith('/'):
            mod_name = os.path.basename(module_path)
            mod_path = os.path.dirname(module_path)
        else:
            mod_name = module_path
            mod_path = None

        chkp_data = CheckpointData(checkpoint_name, mod_name, mod_path,
                                   checkpoint_class_name, loglevel,
                                   args, kwargs)

        chkp_data.validate_checkpoint_info()

        self._checkpoints.insert(insert_index, chkp_data)

        LOGGER.debug("Current checkpoint list:")
        if LOGGER.isEnabledFor(logging.DEBUG):
            for cp in self._checkpoints:
                LOGGER.debug("\t" + str(cp))

    def execute_checkpoints(self, start_from=None, pause_before=None,
                            dry_run=False, callback=None):
        ''' Execute all checkpoints in registration order, from start_from to
            pause_before.  The checkpoint specified at pause_before is not
            executed.

        Input:

            * start_from: optional.  name of the checkpoint to start
              execution from. If start_from is None or not specified,
              the engine will look up the first unexecuted checkpoint
              and start from there. If given, and start_from is a
              previously completed checkpoint, the engine will rollback
              to that state before execution (reverting both the persistent
              DOC and ZFS dataset, if set, in the process)

            * pause_before: optional.  Name of checkpoint to stop execution at.
              If pause_before is None or not specified, execution will
              continue until all registered checkpoints are executed.

            * dry_run: optional.  This flag will be passed to the execute()
              function of the checkpoint.  It is up to the checkpoint to
              interpret this flag.

            * Callback: optional.  function to call immediately before the
              thread executing checkpoints exits.  If a callback function is
              provided, execute_checkpoints() will return immediately after
              all preparation for executing checkpoints are completed.
              If a callback function is not provided, the execute_checkpoints()
              function will not return until the thread executing
              checkpoints exits.

        Output:
            * If a callback function is provided, this function
              returns nothing.  The provided callback
              function will be called with status and failed_checkpoint_list
              information as specified below.

            * A tuple (status, failed_checkpoint_list) is returned if
              a callback function is not provided when the function is called.

                > status: indicates whether all checkpoints are executed
                  successfully.  It will have a value of
                  InstallEngine.EXEC_SUCCESS, InstallEngine.EXEC_FAILED or
                  InstallEngine.EXEC_CANCELED or InstallEngine.CP_INIT_FAILED

                > failed_checkpoint_list: The name(s) of checkpoints failed
                  if status is InstallEngine.EXEC_FAILED or
                  InstallEngine.CP_INIT_FAILED. The
                  exception(s) raised by checkpoint's methods
                  are stored in the errsvc.  The application should look
                  up exception associated with the failed checkpoints using
                  the checkpoint name.

        Raise:
            * UnknownCheckpointError: Name specified in start_from or
              pause_before argument is not found

            * CheckpointOrderError: 2 conditions can cause this error:
              1) There are unexecuted checkpoints before the start_from
              checkpoint.
              2) start_from checkpoint is not before pause_at checkpoint.
        '''

        blocking = callback is None

        if blocking:
            callback = self.__blocking_callback
            thread_cls = InstallEngine._PseudoThread
        else:
            thread_cls = threading.Thread

        self._check_callback(callback)

        if (start_from and
            (self.get_cp_data(start_from) != self.get_first_incomplete())):
            self._rollback(start_from)
        checkpoint_data_list = self.get_exec_list(start_from, pause_before)

        if len(checkpoint_data_list) == 0:
            # unable to find any checkpoint to execute
            warnings.warn("No checkpoint will be executed based on "
                          "specified criteria.")
            return (InstallEngine.EXEC_SUCCESS, [])

        if LOGGER.isEnabledFor(DEBUG):
            LOGGER.debug("Engine will be executing following checkpoints:")
            for cp in checkpoint_data_list:
                LOGGER.debug("\t" + str(cp))

        (checkpoints, failed_init_cp) = self._load_checkpoints(
                                            checkpoint_data_list)

        if len(checkpoints) == 0:
            # one of the checkpoint must have failed to initialize, call the
            # callback function with the failure and return the
            # failures.
            LOGGER.debug(failed_init_cp + "checkpoint failed to initialize")
            if not blocking:
                callback(InstallEngine.CP_INIT_FAILED, [failed_init_cp])
            return (InstallEngine.CP_INIT_FAILED, [failed_init_cp])

        # Make sure to always start at 0 progress
        self.__current_completed = 0

        thread_args = (checkpoints, dry_run, callback)
        LOGGER.debug("Spawning InstallEngine execution thread")
        thread = thread_cls(target=self._execute_checkpoints,
                            name=InstallEngine.CP_THREAD,
                            args=thread_args)
        self.checkpoint_thread = thread
        thread.start()

        if not blocking:
            return

        if self.__blocking_results[0] == InstallEngine.FATAL_INTERNAL:
            errs = errsvc.get_errors_by_mod_id(InstallEngine.FATAL_INTERNAL)
            raise errs[0]

        self.checkpoint_thread = None
        return self.__blocking_results

    def resume_execute_checkpoints(self, start_from, pause_before=None,
                                   dry_run=False, callback=None):
        '''This function provides out-of-process resume functionality to
        applications. It will roll back the ZFS dataset and restore the DOC
        state to its condition just prior to the given "start_from" checkpoint.

        This function may only be run once per-process. Subsequent calls
        should be done via the execute_checkpoints() function, which allows
        for in-process resume.

        All parameters are identical to those from
        InstallEngine.execute_checkpoints.

        In addition to the exceptions from InstallEngine.exeucute_checkpoints,
        this function also raises the following exceptions.

        Raise:
            * RuntimeError: Unable to perform resume
            * UsageError: checkpoint specified is unresumable
        '''

        if not self.__resume_exec_cp_ok:
            raise RuntimeError("InstallEngine.resume_execute_checkpoints"
                               " may only be run once")

        if self.zfs_snapshots_modifed:
            raise RuntimeError("ZFS snapshot has been modified for this "
                              "session.  Unable to resume execute checkpoints")

        resumable = self.get_resumable_checkpoints()
        if start_from not in resumable:
            raise UsageError("'%s' is not a resumable checkpoint" % start_from)

        use_latest = (start_from == resumable[-1])
        self._rollback(start_from, use_latest)

        self.__resume_exec_cp_ok = False
        return self.execute_checkpoints(start_from=start_from, dry_run=dry_run,
                                        pause_before=pause_before,
                                        callback=callback)

    def get_resumable_checkpoints(self):
        ''' Description: InstallEngine.dataset property must be set
            before calling this function.  This function loads the
            DataObjectCache snapshot from the ZFS dataset, and determine
            which of the currently registered checkpoints are resumable.

        Output:
            List of checkpoint names that are resumable.  The order of the
            checkpoint names returned will be same as their registration order.

        Raise:
            * NoDatasetError: ZFS dataset is not specified.
            * FileNotFoundError: The specified zfs dataset is not found.
        '''

        resumable_cp = []

        if self.dataset is None:
            raise NoDatasetError("ZFS dataset must be specified to get "
                                 "list of resumable checkpoints")

        if not self.dataset.exists:
            raise FileNotFoundError("Specified dataset %s does not exist" %
                                    self.dataset)

        doc_path = self.get_cache_filename(InstallEngine._LAST.name)

        # rollback data object cache to latest snapshot.  Latest snapshot
        # should be first file on the list
        if os.path.exists(doc_path):
            LOGGER.debug("Creating temp DOC based off snapshot at: %s",
                         doc_path)
            temp_doc = DataObjectCache()
            temp_doc.load_from_snapshot(doc_path)

            name = InstallEngine.ENGINE_DOC_ROOT
            engine_doc_root = temp_doc.persistent.get_first_child(name=name)
        else:
            engine_doc_root = None

        prev_completed_cp = None
        if engine_doc_root is not None:
            # Get list of previously successfully executed checkpoints from doc
            prev_completed_cp = engine_doc_root.get_children()

        if prev_completed_cp is None:
            prev_completed_cp = []

        # Get list of zfs snapshots
        zfs_snapshots = self.dataset.snapshot_list

        # Determine which of the currently registered checkpoints
        # are resumeable.  The following rules are used:
        # 1) The checkpoint must be registered at exactly the same position
        #    in the checkpoint list as the previous invocation of the
        #    application.
        # 2) All checkpoint registration information must match between
        #    the previous and current invocation of the application.
        # 3) Resumable checkpoints must have associated DataObjectCache
        #    snapshots and ZFS snapshots.  For checkpoints that does not
        #    associated ZFS snapshots in previous execution, ZFS snapshots
        #    is not required for current execution.

        prev_idx = -1
        last_res_idx = None
        for (reg_cp, prev_cp) in zip(self._checkpoints, prev_completed_cp):
            if (reg_cp.cp_info != prev_cp):
                break

            reg_snapshot_path = self.get_zfs_snapshot_fullpath(reg_cp.name)

            if reg_snapshot_path in zfs_snapshots:
                idx = zfs_snapshots.index(reg_snapshot_path)
            else:
                idx = -1
            if idx >= prev_idx:
                prev_idx = idx
                if idx != -1:
                    resumable_cp.append(reg_cp.name)
                    last_res_idx = self._checkpoints.index(reg_cp)
            else:
                break

        # In addition to allowing resume from any completed checkpoint,
        # one may also resume from the first incomplete checkpoint.
        if last_res_idx is None:
            # didn't find anything resumable checkpoints from prev execution.
            if len(self._checkpoints) != 0:
                resumable_cp.append(self._checkpoints[0].name)
        else:
            if (len(self._checkpoints)) - 1 > last_res_idx:
                resumable_cp.append(self._checkpoints[last_res_idx + 1].name)

        return tuple(resumable_cp)

    def normalize_progress(self, cp_prog):
        '''
        Takes the percentage value provider by the InstallLogger,
        and applies the progress ratio for the executing checkpoint
        to calculate the overall completed percentage.

        Input:
            * cp_prog: progress percentage value provided by InstallLogger.

        Output:
            * normalized progress value

        Raise:
            None
        '''

        cp_data = self.get_cp_data(self.__currently_executing.name)
        cp_data.prog_reported = decimal.Decimal(cp_prog)
        normalized_prog = (int)(cp_prog * cp_data.prog_est_ratio)

        LOGGER.debug("progress: %s, reported %s, normalized %s, total=%s" %
                     (self.__currently_executing.name, cp_prog,
                     str(normalized_prog),
                     str(self.__current_completed + normalized_prog)))

        return(str(int(self.__current_completed + normalized_prog)))

    def __blocking_callback(self, status, failed_checkpoint_list):
        ''' Callback used for the blocking case of execute_checkpoints '''
        self.__blocking_results = (status, failed_checkpoint_list)

    def _check_callback(self, callback):
        '''Verifies that the callback function accepts the proper number
        of arguments, so that when called after execution, there won't be an
        exception from a mismatched function signature.

        The callback function must accept at least 2 parameters, and must not
        require more than 2 parameters. (e.g., a 3rd parameter is ok if it is
        an optional keyword argument). The parameters will be called with the
        first argument being a status indicator, and the second argument being
        the contents of the errsvc.
        '''

        if callback is None:
            return
        argspec = get_argspec(callback)
        LOGGER.log(5, "Examining function details for callback function with"
                   " signature: %s", argspec)

        num_args = len(argspec.args)
        if hasattr(callback, "im_self"):
            if callback.im_self is None:
                raise TypeError("Callback cannot be an unbound method")
            else:
                num_args -= 1   # First arg is the bound "self" arg

        if (not argspec.varargs and
            num_args < InstallEngine.NUM_CALLBACK_ARGS):
            raise TypeError("callback function must accept at least 2 args:"
                            " status & errsvc")

        if argspec.defaults:
            len_defaults = len(argspec.defaults)
        else:
            len_defaults = 0
        if num_args - len_defaults > InstallEngine.NUM_CALLBACK_ARGS:
            raise TypeError("The specified callback function requires more"
                            " than 2 arguments and will fail")

    def _execute_checkpoints(self, checkpoints, dry_run, callback):
        '''Runs the checkpoints. The public execute_checkpoints method will
        run this function in a separate thread.

        Errors occurring here will be trapped and added to the error service
        '''

        status = InstallEngine.EXEC_SUCCESS
        failed_checkpoint_list = []
        completed = False

        try:
            for checkpoint in checkpoints:
                with self._checkpoint_lock:
                    # Determine whether the execution has
                    # been canceled. (Acquire the lock to ensure that
                    # cancel_checkpoints() isn't attempting to cancel
                    # __currently_executing).
                    if self._cancel_event.is_set():
                        status = InstallEngine.EXEC_CANCELED
                        failed_checkpoint_list.append(
                            self.__currently_executing.name)
                        break
                    self.__currently_executing = checkpoint
                cp_data = self.get_cp_data(checkpoint.name)

                # Take a snapshot of the state before executing the checkpoint.
                # This snapshot, which is associated with the checkpoint's 
                # name, is for resuming at the named checkpoint.  
                if status is InstallEngine.EXEC_SUCCESS:
                    self.snapshot(cp_data)

                try:
                    LOGGER.debug("Executing %s checkpoint", checkpoint.name)
                    checkpoint.execute(dry_run)
                except BaseException as exception:
                    LOGGER.exception("Error occurred during execution "
                                     "of '%s' checkpoint." % checkpoint.name)
                    completed = False
                    error_info = errsvc.ErrorInfo(checkpoint.name,
                                                  liberrsvc.ES_ERR)
                    error_info.set_error_data(liberrsvc.ES_DATA_EXCEPTION,
                                              exception)
                    failed_checkpoint_list.append(checkpoint.name)
                    status = InstallEngine.EXEC_FAILED
                    if self.stop_on_error:
                        if (self.debug and
                            isinstance(self.checkpoint_thread,
                                       InstallEngine._PseudoThread)):
                            raise
                        else:
                            break
                else:
                    # Checkpoint completed successfully without exceptions
                    completed = True

                self._engine_doc_root.insert_children(cp_data.cp_info)
                cp_data.completed = completed

                # Inform logger that the checkpoint has completed.
                # This is to ensure that progress is being reported
                # even if checkpoints don't report progress themselves
                if cp_data.prog_reported < 100:
                    LOGGER.report_progress(msg=cp_data.name + " completed.",
                                           progress=100)

                # keep track of completed percentage
                self.__current_completed += cp_data.prog_est_ratio * 100

                # The "latest" snapshot is
                # taken to capture the latest successful state.  
                if status is InstallEngine.EXEC_SUCCESS:
                    self.snapshot(InstallEngine._LAST)

        except BaseException as exception:
            # Fatal error in InstallEngine - abort regardless of issue
            LOGGER.exception("Aborting: Internal error in InstallEngine")
            status = InstallEngine.FATAL_INTERNAL
            error_info = errsvc.ErrorInfo(status, liberrsvc.ES_ERR)
            error_info.set_error_data(liberrsvc.ES_DATA_EXCEPTION,
                                      exception)
            failed_checkpoint_list.insert(0, status)
            # If we're in the main thread, raise this fatal error up.
            if isinstance(self.checkpoint_thread,
                          InstallEngine._PseudoThread):
                raise
        finally:
            with self._checkpoint_lock:
                self.__currently_executing = None

        callback(status, failed_checkpoint_list)

    def snapshot(self, cp_data):
        '''Snapshots the current DOC state (and ZFS dataset, if it exists)'''
        filename = self.get_cache_filename(cp_data.name)
        LOGGER.debug("Snapshotting DOC to %s", filename)
        self.data_object_cache.take_snapshot(filename)
        cp_data.data_cache_path = filename

        if self.dataset is not None and self.dataset.exists:
            snap_name = self.get_zfs_snapshot_name(cp_data.name)
            LOGGER.debug("Taking zfs snapshot: %s", snap_name)
            self.dataset.snapshot(snap_name, overwrite=True)
            cp_data.zfs_snap = snap_name
            self.zfs_snapshots_modifed = True
        else:
            cp_data.zfs_snap = None

    def _load_checkpoints(self, checkpoint_data_list):
        '''Load checkpoint modules to get the executable checkpoints
 
           Input:
               checkpoint_data_list: list of checkpoints to be executed.  This
                                     is a list of CheckpointInfo objects.
           Output:
               * list of instantiated checkpoint objects, if no instantiation
                 failure occurred.
               * name of the checkpoint that failed to instantiate.  The
                 exact traceback from the failure is registered with the 
                 errsvc.

           Raises:
               * None
        '''

        if len(checkpoint_data_list) == 0:
            # to protect against an empty list being passed in.
            return([], None)

        execute_these = []
        total_estimate = decimal.Decimal('0')
        for cp_data in checkpoint_data_list:
            LOGGER.debug("Loading %s checkpoint", cp_data)
            try:
                checkpoint = cp_data.load_checkpoint()
                prog_est = checkpoint.get_progress_estimate()
            except BaseException as exception:
                LOGGER.exception("Uncaught exception from '%s' checkpoint init"
                                     % cp_data.name)
                error_info = errsvc.ErrorInfo(cp_data.name, liberrsvc.ES_ERR)
                error_info.set_error_data(liberrsvc.ES_DATA_EXCEPTION,
                                          exception)
                return ([], cp_data.name)

            if prog_est <= 0:
                # Take care of the case where get_progress_estimate() returning
                # invalid value
                prog_est = 1
            cp_data.prog_est = decimal.Decimal(str(prog_est))
            total_estimate += cp_data.prog_est
            execute_these.append(checkpoint)

        total_ratio = decimal.Decimal(0)
        for cp_data in checkpoint_data_list:
            cp_data.prog_est_ratio = cp_data.prog_est / total_estimate
            total_ratio += cp_data.prog_est_ratio
            LOGGER.debug("%s: prog est-%s, prog ratio-%s, total_ratio-%s" %
                        (cp_data.name, str(cp_data.prog_est),
                         str(cp_data.prog_est_ratio), str(total_ratio)))

        # Just in case the total ratio didn't add up to 100% because
        # of rounding down, adjust it in the last checkpoint
        checkpoint_data_list[-1].prog_est_ratio += \
            decimal.Decimal("1") - total_ratio
        LOGGER.debug("Last checkpoint, %s: prog ratio %s" %
                     (checkpoint_data_list[-1].name,
                     str(checkpoint_data_list[-1].prog_est_ratio)))

        return (execute_these, None)

    def get_exec_list(self, start_from=None, pause_before=None):
        '''Returns the list of checkpoints to execute based on the desired
        start/end checkpoint names

        Input:
            start_from: name of checkpoint to start execution.  Optional.
            pause_before: name of checkpoint to pause execution.  Optional.

        Output:
            List of checkpoints to be executed.

        Raises:
            UsageError: There are unexecuted checkpoints before the 
                        checkpoint specified to start execution from.
            UnknownChkptError: Name specified for start_from and pause_before
                               is not valid.
        '''

        exec_list = []

        if start_from is None:
            start_from_cp = self.get_first_incomplete()
            if start_from_cp is None:
                # All checkpoints completed, so continuing where the engine
                # left off is a no-op - return the empty list
                return exec_list
            else:
                start_from = start_from_cp.name
        LOGGER.debug("Retrieving checkpoint list from %s to %s", start_from,
                     pause_before)

        # Examine all checkpoints. For checkpoints prior to the one indicated
        # by start_from (while found_start is False), ensure that they've been
        # completed so that we only resume from a completed checkpoint.
        found_start = False
        for cp in self._checkpoints:
            if cp.name == start_from:
                # Found the start_from checkpoint - start adding
                # to the exec list
                found_start = True

            if found_start and cp.name == pause_before:
                # Pause before this checkpoint - stop adding checkpoints
                # to the exec_list
                if found_start:
                    break
                else:
                    raise UsageError("Specified pause_before checkpoint, %s, "
                                     "is registered after specified "
                                     "start_from checkpoint, %s" % 
                                     (pause_before, start_from))

            if found_start:
                exec_list.append(cp)
            elif not cp.completed:
                raise UsageError("Invalid start checkpoint. "
                                 "Previous checkpoint (%s) not completed." %
                                 cp.name)
        else:
            # After "found_start", keep adding checkpoints until pause_before.
            # If the pause_before checkpoint is not found, but pause_before
            # was specified, it's an error
            if not found_start:
                raise UnknownChkptError("'%s' is not a valid checkpoint"
                                        " to start execution from." %
                                          start_from)
            if pause_before is not None:
                raise UnknownChkptError("'%s' is not a valid checkpoint"
                                        " to pause execution at." %
                                          pause_before)
        return tuple(exec_list)

    def get_cp_data(self, name):
        '''Helper method for retrieving a CheckpointData object by name'''

        if name == InstallEngine._LAST.name:
            return InstallEngine._LAST

        for cp in self._checkpoints:
            if cp.name == name:
                return cp
        raise UnknownChkptError("'%s' is not a registered checkpoint" % name)

    def get_first_incomplete(self):
        '''Return the first checkpoint that has not yet been run'''
        for cp in self._checkpoints:
            if not cp.completed:
                return cp
        return None

    def get_cache_filename(self, cp_name):
        '''Returns the filename of the DOC dump for the given checkpoint'''
        if self.dataset is not None and self.dataset.exists:
            path = self.dataset.get("mountpoint")
        else:
            path = self._tmp_cache_path
            if path is None:
                path = self._gen_tmp_dir()

        filename = InstallEngine.CACHE_FILE_NAME % {"checkpoint": cp_name}
        full_path = os.path.join(path, filename)
        return full_path

    def _gen_tmp_dir(self):
        '''Determine where temporary DOC files should be stored'''

        # if the TEMP_DOC_DIR env variable is defined, use that value
        # for the temporary DOC directory.

        if InstallEngine.TMP_CACHE_ENV in os.environ:
            doc_path = os.environ[InstallEngine.TMP_CACHE_ENV]
            if not os.path.exists(doc_path):
                os.makedirs(doc_path)
        else:
            prefix = InstallEngine.TMP_CACHE_PATH_PREFIX
            doc_dir = InstallEngine.TMP_CACHE_PATH_ROOT_DEFAULT
            if not os.path.exists(doc_dir):
                os.makedirs(doc_dir)
            doc_path = tempfile.mkdtemp(prefix=prefix, dir=doc_dir)
        self._tmp_cache_path = doc_path
        return doc_path

    def get_zfs_snapshot_name(self, cp_name):
        '''Returns the ZFS snapshot name for the given checkpoint'''
        return InstallEngine.SNAPSHOT_NAME % {"checkpoint": cp_name}

    def get_zfs_snapshot_fullpath(self, cp_name):
        '''Returns the full ZFS snapshot path for the given checkpoint'''
        snap_name = self.get_zfs_snapshot_name(cp_name)
        return(self.dataset.snapname(snap_name))

    @property
    def doc(self):
        ''' return data object cache instantiated by the engine '''
        return self.data_object_cache

    @property
    def _engine_doc_root(self):
        ''' Returns the root node for storing engine related info in DOC '''
        name = InstallEngine.ENGINE_DOC_ROOT
        node = self.doc.persistent.get_first_child(name=name)
        if node is None:
            node = EngineData()
            self.doc.persistent.insert_children(node)
        return node

    def _rollback(self, before_cp, use_latest=False):
        '''Revert the engine to the given Checkpoint (by name):
            * If the checkpoint was snapshotted via ZFS, rollback to that
            * Additionally, rollback the DOC
        Raises:
            IOError: If the DOC snapshot can't be found or can't be read
            RollbackError: If the engine doesn't have a valid ZFS dataset
                           to do an out-of-process rollback from
        '''
        if use_latest:
            cp_data = InstallEngine._LAST
        else:
            cp_data = self.get_cp_data(before_cp)

        if cp_data.completed:
            # In-process resume
            cache_file = cp_data.data_cache_path
            snap_name = cp_data.zfs_snap
            if cache_file is None:
                raise RollbackError(before_cp, "Checkpoint has no data cache")
        else:
            # Out of process resume
            if self.dataset is None:
                # Application needs to set ZFS dataset before
                # calling InstallEngine.rollback(...)
                raise RollbackError(before_cp, "A ZFS dataset is required to "
                                    "rollback to this checkpoint")
            cache_file = self.get_cache_filename(cp_data.name)
            snap_name = self.get_zfs_snapshot_name(cp_data.name)
            long_snap_name = self.dataset.snapname(snap_name)

            if long_snap_name not in self.dataset.snapshot_list:
                raise RollbackError(before_cp, "Missing required ZFS snapshot"
                                    " [%s]" % long_snap_name)
        if snap_name is not None:
            self.dataset.rollback(snap_name, recursive=True)

        if not os.path.exists(cache_file):
            raise NoCacheError(before_cp, cache_file)

        self.doc.load_from_snapshot(cache_file)

        # Reset the 'completed' state of all registered checkpoints,
        # based on how far the engine was rolled back
        completed = True
        for checkpoint in self._checkpoints:
            if checkpoint.name == before_cp:
                completed = False
            checkpoint.completed = completed

    def cancel_checkpoints(self):
        '''Cancels currently executing checkpoints. If no checkpoints are
        currently running, this is a no-op.
        '''

        with self._checkpoint_lock:
            # Use the _checkpoint_lock to ensure that
            # __currently_executing doesn't change after being canceled.
            self._cancel_event.set()
            if self.__currently_executing is not None:
                self.__currently_executing.cancel()

        if self.checkpoint_thread is not None:
            self.checkpoint_thread.join()

        self._cancel_event.clear()

    def cleanup_checkpoints(self):
        ''' Removes ZFS and DataObjectCache snapshots associated with
            currently registered checkpoints.
        '''

        # Checkpoint cleanup can not happen while checkpoints execution
        # is in progress.  Make sure we are not in the middle of
        # executing checkpoints

        if self._is_executing_checkpoints():
            raise EngineError("Checkpoint cleanup is "
                              "not allowed during checkpoint execution.")

        if self.dataset is not None and self.dataset.exists:

            # Get list of zfs snapshots
            zfs_snapshots = self.dataset.snapshot_list

            for cp_data in self._checkpoints:
                # Will attempt to look for ZFS snapshots from
                # all checkpoints, including those that is not completed
                # in this process.  If a checkpoint exists, destroy it.
                # If it doesn't exist, continue on.
                snap_path = self.get_zfs_snapshot_fullpath(cp_data.name)
                if snap_path in zfs_snapshots:
                    snap_name = self.get_zfs_snapshot_name(cp_data.name)
                    self.dataset.destroy(dry_run=False, snapshot=snap_name)

            # Destroy the special engine-internal "last" dataset
            snap_path = \
                self.get_zfs_snapshot_fullpath(InstallEngine._LAST.name)
            if snap_path in zfs_snapshots:
                snap_name = \
                    self.get_zfs_snapshot_name(InstallEngine._LAST.name)
                self.dataset.destroy(snap_name)

        if self._tmp_cache_path is not None:
            shutil.rmtree(self._tmp_cache_path)
            self._tmp_cache_path = None

        # since all checkpoint DOC and/or ZFS snapshots are removed, unset
        # the completed flag for the checkpoints because they can no longer
        # be rolled back to.
        for cp_data in self._checkpoints:
            cp_data.completed = False

    def _is_executing_checkpoints(self):
        ''' determine whether the engine is currently executing checkpoints '''

        return ((self.checkpoint_thread is not None) and
                (self.checkpoint_thread.is_alive()))

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

# =============================================================================
# =============================================================================
"""
finalizer.py - Script driver.
Call queued scripts and programs
"""
# =============================================================================
# =============================================================================

import sys

import copy
import logging
import os
import socket
import stat
import subprocess

from install_utils import exec_cmd_outputs_to_log

class DCFinalizer(object):
    """Script driver.  Call queued scripts and programs.

    Register scripts and programs in advance.  Provides
    separate stdout and stderr logging for each script if desired.
    """

    # Finalizer maintains a list of scripts/programs to call.  The
    # same list holds changes to logging destinations which can occur
    # between calls.
    #
    # Type specifies the kind of queue item.  There are currently two kinds
    # of items:
    #	_TYPE_FUNC: for items specifying modules to execute
    #		The _FS_TYPE field of these items are set to _TYPE_FUNC.
    #	_TYPE_EXEC_PRM: for items specifying stdout and stderr routing
    #		The _EP_TYPE field of these items are set to
    #		_TYPE_EXEC_PRM
    #
    _TYPE_FUNC, _TYPE_EXEC_PRM = range(2)

    # Items specifying modules to execute have the following fields:
    #
    #   _FS_TYPE: Specifies the type of list item to be _TYPE_FUNC
    #
    #   _FS_MODULE: Name of the script or binary to run.
    #
    #   _FS_ARGLIST: list of arguments.  An empty list or None is acceptable
    #
    _FS_TYPE, _FS_MODULE, _FS_ARGLIST = range(3)

    #
    # Items specifying stdout and stderr rerouting have the following
    #	fields:
    #
    #   _EP_TYPE: Specifies the type of list item to be _TYPE_EXEC_PRM
    #
    #   _EP_OUT_FILENAME: Filename of output logfile.  "stdout" is
    #	acceptable and is the default.
    #
    #   _EP_ERR_FILENAME: Filename of error logfile.  "stderr" is
    #	acceptable and is the default.
    #
    #   _EP_STOP_ON_ERR: Boolean value which, when set, will have execute()
    #	return an error status and exception object right away if an
    #	error occurs.  When this value is clear, execute() attempts to
    #	run to completion and then returns an error status and
    #	exception object.
    #
    #   _EP_LOGGER_NAME: name of the logger to use.  When this is specified,
    #	_EP_OUT_FILENAME and _EP_ERR_FILENAME will be ignored, since
    #	all the output and error are logged to the logger
    #
    _EP_TYPE, _EP_OUT_FILENAME, _EP_ERR_FILENAME, _EP_STOP_ON_ERR, \
        _EP_LOGGER_NAME = range(5)
    #
    # Items regarding file descriptors and sockets
    #
    #   _file_fd: File descriptor
    #
    #   _file_name: Name of the file
    #
    #   _file_socket: Socket, if specified
    #
    _file_fd, _file_name, _file_socket = range(3)

    # Indices for _fileinfo
    STDOUT = 0
    STDERR = 1

    # Return statuses
    SUCCESS = 0
    GENERAL_ERR = 1


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, first_args=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor

        Args:
          first_args: List of args passed to all called scripts as
            their first args.  Arg 1 in the list will be arg 1 in
            each script.  List arg 2 = script arg 2, etc.  Each
            item in the list is assumed to be a string.  Numerics
            are quoted and treated as strings.  Not used if set to
            None, or not specified.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Instance variables:

        # The queue which holds items specifying modules to execute and
        # logging requests.
        self._execlist = []

        # Boolean flag which can cause immediate stop-on-error
        self._stop_on_err = False

        # Pointer to the first saved exception
        self._saved_exception = None

        # Name of the logger to use for stdout/stderr
        self._logger_name = None

        # List where stdout and stderr items are kept
        self._fileinfo = []

        out_info = []
        err_info = []

        # File descriptor of output file.  None signifies the console
        out_info.insert(DCFinalizer._file_fd, None)

        # Name of the file stdout goes to.  May be "stdout".
        out_info.insert(DCFinalizer._file_name, "stdout")

        # Output socket.
        out_info.insert(DCFinalizer._file_socket, None)

        self._fileinfo.insert(DCFinalizer.STDOUT, out_info)

        # File descriptor of error file.  None signifies the console
        err_info.insert(DCFinalizer._file_fd, None)

        # Name of the file stderr goes to.  May be "stderr".
        err_info.insert(DCFinalizer._file_name, "stderr")

        # Error socket.
        err_info.insert(DCFinalizer._file_socket, None)

        self._fileinfo.insert(DCFinalizer.STDERR, err_info)

        # Deepcopy to freeze the strings being copied..
        self._first_args = copy.deepcopy(first_args)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _set_file(self, filename, stdfile):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private function to reroute stdout or stderr
        Existing route is closed if it is a proper file.

        Args:
          filename: Name of new file to log to.  May be set same as stdfile.
                  May also be the "file"name of an AF_UNIX socket node.

          stdfile: "stdout" or "stderr"

        Returns:
          0: Success
          1: Error

        Raises: None, but passes along KeyboardInterrupt and SystemExit
                exceptions.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Assume success
        rval = DCFinalizer.SUCCESS
        err = None

        if (stdfile == "stdout"):
            index = DCFinalizer.STDOUT
        else:
            index = DCFinalizer.STDERR
        info = self._fileinfo[index]

        # Trying to set the same name
        if (filename == info[DCFinalizer._file_name]):
            return DCFinalizer.SUCCESS

        # Close previous file unless stdout or stderr.
        # info[DCFinalizer._file_fd] is None for stdout or stderr.
        # Ignore errors on close.
        if (info[DCFinalizer._file_fd] is not None):
            try:
                info[DCFinalizer._file_fd].close()
                if (info[DCFinalizer._file_socket] is not None):
                    info[DCFinalizer._file_socket].close()
                    info[DCFinalizer._file_socket] = None
            except (IOError, socket.error):
                pass
            except StandardError, err:
                print >> sys.__stderr__, ("Couldn't close fd " +
                                          str(info[DCFinalizer._file_fd]))
                print >> sys.__stderr__, str(err)

        # If new file is stdout or stderr, just return.
        # Calling function will open.
        if (filename == stdfile):
            info[DCFinalizer._file_name] = filename
            info[DCFinalizer._file_fd] = None
            return DCFinalizer.SUCCESS

        # Try opening the new file.  Change filename if successful.
        # Revert back to stdout if there were errors on open.
        stat_ok = False
        try:
            stat_result = os.stat(filename)
            stat_ok = True
        except OSError:
            pass
        except StandardError, err:	# Will probably never see this...
            print >> sys.__stderr__, ("set_file: stat error when checking " +
                                      "filetype")
            print >> sys.__stderr__, str(err)
            info[DCFinalizer._file_fd] = None
            info[DCFinalizer._file_name] = stdfile
            return DCFinalizer.GENERAL_ERR

        try:
            # Filename is a socket.  This handling is for a tool
            # which could open a socket to receive stdout and/or
            # stderr to display within itself.  Note: receiving
            # socket must be already setup at this point.
            if stat_ok and stat.S_ISSOCK(stat_result.st_mode):
                info[DCFinalizer._file_socket] = \
		    socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                info[DCFinalizer._file_socket].connect(filename)
                fd = info[DCFinalizer._file_socket].fileno()
                info[DCFinalizer._file_fd] = os.fdopen(fd, "w")
            else:
                # Open new file.  Can raise an IOError.
                info[DCFinalizer._file_fd] = open(filename, "a")
            info[DCFinalizer._file_name] = filename

        except socket.error, err:
            print >> sys.__stderr__, (("Error opening socket for " +
                                      "%s; socket is stale or otherwise " +
                                      "unusable") % filename)
            print >>sys.stderr, str(err)
            if (info[DCFinalizer._file_socket] is not None):
                info[DCFinalizer._file_socket].close()
                info[DCFinalizer._file_socket] = None
            rval = DCFinalizer.GENERAL_ERR

        except StandardError, err:
        # Includes OSError in case the file could not be opened

            rval = DCFinalizer.GENERAL_ERR

        if (rval == DCFinalizer.GENERAL_ERR):
            print >> sys.__stderr__, ("set_file: Error opening %s for writing" %
                  filename)
            print >> sys.__stderr__, str(err)
            info[DCFinalizer._file_fd] = None
            info[DCFinalizer._file_name] = stdfile

        return rval


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def change_exec_params(self, output=None, error=None, stop_on_err=None,
                           logger_name=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Queue up a change to stdout and/or stderr, and to set or
            clear the stop_on_err flag.

        Calls to this function may be interspersed with calls to
        register().  Scripts/programs queued with register() after a queued
        change to stdout and/or stderr will run with rerouted stdout
        and/or stderr

        Args:
          output: Name of file to route stdout to.  May be "stdout" to
            go to console.  May be the "file"name of an AF_UNIX
            socket node.  Passing None means no-change.

          error: Name of file to route stderr to.  May be "stderr" to
            go to console.  May be the "file"name of an AF_UNIX
            socket node.  Passing None means no-change.

          stop_on_err: Boolean flag.  True means stop immediately when
            execute() encounters an error.  False means continue
            through remaining modules.  Passing None means
            no-change.

          logger_name: Name of the logger to use.  Passing None means
                we don't want to do logging of the command's stdout/stderr

        Returns:
          0 if successful
          1 if arguments are invalid

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        epspec = []

        # Do some limited sanity argument typechecking
        if (((output is not None) and
            (not isinstance(output, basestring))) or
            ((error is not None) and
            (not isinstance(error, basestring))) or
            ((stop_on_err is not None) and
            (not isinstance(stop_on_err, bool))) or
            ((logger_name is not None) and
            (not isinstance(logger_name, basestring)))):
            return DCFinalizer.GENERAL_ERR

        # if a logger is specified, will not allow to specify
        # stdout and stderr
        if ((logger_name is not None) and
            ((output is not None) or (error is not None))):
            return DCFinalizer.GENERAL_ERR

        # Fill out and insert a new a queued element.
        epspec.insert(DCFinalizer._EP_TYPE, DCFinalizer._TYPE_EXEC_PRM)
        epspec.insert(DCFinalizer._EP_OUT_FILENAME, output)
        epspec.insert(DCFinalizer._EP_ERR_FILENAME, error)
        epspec.insert(DCFinalizer._EP_STOP_ON_ERR, stop_on_err)
        epspec.insert(DCFinalizer._EP_LOGGER_NAME, logger_name)
        self._execlist.append(epspec)
        return DCFinalizer.SUCCESS

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def register(self, module, arglist=()):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Queue up a module to call during finalization.
        Any request to setup stdout and stderr for this module's
        execution is assumed already made.

        Args:
          module: script or binary to invoke

          arglist: list of args to invoke module with.
            Can be an empty list, but must be specified.

        Returns:
          0 if successful
          1 if there is an error in the module specification
          1 if a shell script, shell interpreter, binary or
            python module are inaccessible

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        funcspec = []

        if module is None or module == "":
            return DCFinalizer.GENERAL_ERR

        # Check execute access.
        if (not (os.access(module, os.X_OK))):
            return DCFinalizer.GENERAL_ERR

        # Fill out and insert a new a queued element.
        funcspec.insert(DCFinalizer._FS_TYPE, DCFinalizer._TYPE_FUNC)
        funcspec.insert(DCFinalizer._FS_MODULE, module)
        funcspec.insert(DCFinalizer._FS_ARGLIST, arglist)
        self._execlist.append(funcspec)
        return DCFinalizer.SUCCESS


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _process_shell(self, item):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private function which runs a shell script

        Args:
          item: An item which describes what to execute, including the script
                (module) and arguments.

        Returns:
          0 if successful
          negative signal number if shell's child process terminated by signal
          positive errno value if an error occured or
          1 with the exception object saved in self._saved_exception if
                an exception occured when trying to start the shell

        Raises: None.
                Note though that errors get printed to the stderr logfile

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        shell_list = []

        shell_list.append(item[DCFinalizer._FS_MODULE])

        if (self._first_args is not None):
            for arg in self._first_args:
                shell_list.append(str(arg))

        for arg in item[DCFinalizer._FS_ARGLIST]:
            shell_list.append(str(arg))

        # Try running the shell with stdout and stderr specified.  Wait
        # for completion.  Catch exceptions which arise when the shell
        # cannot be started.
        out_fd = self._fileinfo [DCFinalizer.STDOUT][DCFinalizer._file_fd]
        err_fd = self._fileinfo [DCFinalizer.STDERR][DCFinalizer._file_fd]
        logger = None
        try:
            if (self._logger_name is not None):
                logger = logging.getLogger(self._logger_name)
                rval = exec_cmd_outputs_to_log(shell_list, logger)
            else:
                rval = (subprocess.Popen(shell_list,
                        shell=False, stdout=out_fd, stderr=err_fd).wait())
            if rval < 0:
                err_str = "Child was terminated by signal " + str(-rval)
                if (logger is not None):
                    logger.error(err_str)
                else:
                    print >> err_fd, (err_str)
            elif rval > 0:
                err_str = "Child returned err " + str(rval)
                if (logger is not None):
                    logger.error(err_str)
                else:
                    print >> err_fd, (err_str)
            if rval != 0:
                rval = DCFinalizer.GENERAL_ERR
        except OSError, exception_obj:
            err_str1 = "Error starting or running shell:" + str(exception_obj)
            err_str2 = "shell_list = " + str(shell_list)

            if (logger is not None):
                logger.error(err_str1)
                logger.error(err_str2)
            else:
                print >> err_fd, (err_str1)
                print >> err_fd, (err_str2)

            # Set rval to a non-zero value.  Save the first
            # exception we get, to make it easier to trace the pblm.
            rval = DCFinalizer.GENERAL_ERR
            if (self._saved_exception is None):
                self._saved_exception = exception_obj

        return rval


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def execute(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Set finalization into motion.  Starts working down the queue
        of requested module executions and logging requests

        Args: None

        Returns:
          0 if successful
          -signo if a signal was caught by a program or shell script
          errno if a program or shell script had an error
          1 if an exception was raised.  First caught exception is saved
            for retrieval by get_exception()

          If _stop_on_err is not set and multiple errors occur, the
            first error encountered is the one returned.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        saved_rval = DCFinalizer.SUCCESS

        # Work through the queue
        for item in self._execlist:
            # It's a module to execute.
            if item[DCFinalizer._FS_TYPE] == DCFinalizer._TYPE_FUNC:
                rval = self._process_shell(item)
                if (saved_rval == DCFinalizer.SUCCESS):
                    saved_rval = rval
                if (self._stop_on_err and rval !=
                    DCFinalizer.SUCCESS):
                    break
            elif (item[DCFinalizer._FS_TYPE] ==
                  DCFinalizer._TYPE_EXEC_PRM):
                if (item[DCFinalizer._EP_ERR_FILENAME] is not None):
                    self._set_file(item[DCFinalizer._EP_ERR_FILENAME],
                                   "stderr")
                if (item[DCFinalizer._EP_OUT_FILENAME] is not None):
                    self._set_file(item[DCFinalizer._EP_OUT_FILENAME],
                                   "stdout")
                if (item[DCFinalizer._EP_STOP_ON_ERR] is not None):
                    self._stop_on_err = item[DCFinalizer._EP_STOP_ON_ERR]

                if (item[DCFinalizer._EP_LOGGER_NAME] is not None):
                    self._logger_name = item[DCFinalizer._EP_LOGGER_NAME]

        # File pointers must be closed before sockets
        fileinfo = self._fileinfo[DCFinalizer.STDOUT]
        if (fileinfo[DCFinalizer._file_fd] is not None):
            fileinfo[DCFinalizer._file_fd].close()
        if (fileinfo[DCFinalizer._file_socket] is not None):
            fileinfo[DCFinalizer._file_socket].close()
        fileinfo = self._fileinfo[DCFinalizer.STDERR]
        if (fileinfo[DCFinalizer._file_fd] is not None):
            fileinfo[DCFinalizer._file_fd].close()
        if (fileinfo[DCFinalizer._file_socket] is not None):
            fileinfo[DCFinalizer._file_socket].close()

        return saved_rval


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_exception(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Retrieve a saved exception.

        Args: None

        Returns:
          Pointer to exception object if an exception has been raised
            during a previous call to execute()
          None if no exception has been raised during a previous call to
            execute()

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        return self._saved_exception

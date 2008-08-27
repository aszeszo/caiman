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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import os
import sys
import copy
import subprocess
import socket
import stat
import osol_install.install_utils

class DCFinalizer(object):
	"""Script driver.  Call queued scripts, programs and python functions

	Register scripts, programs and python functions in advance.  Provides
	separate stdout and stderr logging for each script if desired.
	"""

	# Finalizer maintains a list of functions/scripts/programs to call.  The
	# same list holds changes to logging destinations which can occur
	# between calls.
	#
	# Type specifies the kind of queue item.  There are currently two kinds
	# of items:
	#	_type_func: for items specifying modules to execute
	#		The _fs_type field of these items are set to _type_func.
	#	_type_exec_prm: for items specifying stdout and stderr routing
	#		The _ep_type field of these items are set to
	#		_type_exec_prm
	#
	_type_func, _type_exec_prm = range(2)

	# Items specifying modules to execute have the following fields:
	#
	#   _fs_type: Specifies the type of list item to be _type_func
	#
	#   _fs_module: A tuple which zeros in on exactly what is to be run.
	#	- For python function specification: tuple contains two items:
	#		1) Name of the module
	#		2) Name of the function
	#	- For all other specifications (script, binary): tuple contains
	#	    single item:
	#		Name of the script or binary to run
	#
	#   _fs_arglist: list of arguments.  An empty list or None is acceptable
	#
	_fs_type, _fs_module, _fs_arglist = range(3)

	#
	# Items specifying stdout and stderr rerouting have the following
	#	fields:
	#
	#   _ep_type: Specifies the type of list item to be _type_exec_prm
	#
	#   _ep_out_filename: Filename of output logfile.  "stdout" is
	#	acceptable and is the default.
	#
	#   _ep_err_filename: Filename of error logfile.  "stderr" is
	#	acceptable and is the default.
	#
	#   _ep_stop_on_err: Boolean value which, when set, will have execute()
	#	return an error status and exception object right away if an
	#	error occurs.  When this value is clear, execute() attempts to
	#	run to completion and then returns an error status and
	#	exception object.
	#
	_ep_type, _ep_out_filename, _ep_err_filename, _ep_stop_on_err = range(4)

	#
	# Item to run will be stored as a tuple.
	#	- Scripts and binaries have one item: their (module) name.
	#	- Python functions have two items: module and function
	_name_mod, _name_func = range(2)
	_python_func_len = 2

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
		"""Constructor

		Args:
		  first_args: List of args passed to all called scripts as
			their first args.  Arg 1 in the list will be arg 1 in
			each script.  List arg 2 = script arg 2, etc.  Each
			item in the list is assumed to be a string.  Numerics
			are quoted and treated as strings.  Not used if set to
			None, or not specified.

		Returns: N/A

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

		# Check that first_args' strings have no spaces in them.
		if (first_args != None):
	 		for i in (range(len(first_args))):
 				if (len(first_args[i].split()) > 1):
 					raise Exception, ("finalizer init: a " +
 					    "first_args string contains " +
 					    "whitespace")

		# Deepcopy to freeze the strings being copied..
		self._first_args = copy.deepcopy(first_args)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def _set_file(self, filename, stdfile):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Private function to reroute stdout or stderr
	# Existing route is closed if it is a proper file.
	#
	# Args:
	#   filename: Name of new file to log to.  May be set same as stdfile.
	#	May also be the "file"name of an AF_UNIX socket node.
	#
	#   stdfile: "stdout" or "stderr"
	#
	# Returns:
	#   0: Success
	#   1: Error
	#
	# Raises: None, but passes along KeyboardInterrupt and SystemExit
	#	exceptions.
	#
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		# Assume success
		rval = DCFinalizer.SUCCESS

		if (stdfile == "stdout"):
			index = DCFinalizer.STDOUT
		else:
			index = DCFinalizer.STDERR
		info = self._fileinfo[index]

		# Trying to set the same name
		if (filename == info[DCFinalizer._file_name]):
			return DCFinalizer.SUCCESS

		# Close previous file unless stdout or stderr.
		# info[DCFinalizer._file_fd] == None for stdout or stderr.
		# Ignore errors on close.
		if (info[DCFinalizer._file_fd] != None):
			try:
				info[DCFinalizer._file_fd].close()
				if (info[DCFinalizer._file_socket] != None):
					info[DCFinalizer._file_socket].close()
					info[DCFinalizer._file_socket] = None
			except IOError:
				pass
			except socket.error:
				pass
			except KeyboardInterrupt, SystemExit:
				raise
			except:
				print "Couldn't close fd " + str(
				    info[DCFinalizer._file_fd])

		# If new file is stdout or stderr, just return.
		# Calling function will open.
		if (filename == stdfile):
			info[DCFinalizer._file_name] = filename
			info[DCFinalizer._file_fd] = None
			return DCFinalizer.SUCCESS

		# Try opening the new file.  Change filename if successful.
		# Revert back to stdout if there were errors on open.
		stat_OK = False
		try:
			stat_result = os.stat(filename)
			stat_OK = True
		except OSError:
			pass
		except KeyboardInterrupt, SystemExit:
			raise
		except:			# Will probably never see this...
			print "set_file: stat error when checking filetype"
			info[DCFinalizer._file_fd] = None
			info[DCFinalizer._file_name] = stdfile
			return DCFinalizer.GENERAL_ERR

		try:
			# Filename is a socket.  This handling is for a tool
			# which could open a socket to receive stdout and/or
			# stderr to display within itself.  Note: receiving
			# socket must be already setup at this point.
			if stat_OK and stat.S_ISSOCK(stat_result.st_mode):
				info[DCFinalizer._file_socket] = socket.socket(
				    socket.AF_UNIX, socket.SOCK_STREAM)
				info[DCFinalizer._file_socket].connect(filename)
				fd = info[DCFinalizer._file_socket].fileno()
				info[DCFinalizer._file_fd] = os.fdopen(fd, "w")
			else:
				# Open new file.  Can raise an IOError.
				info[DCFinalizer._file_fd] = open(filename, "a")
			info[DCFinalizer._file_name] = filename

		except socket.error:
			print >>sys.__stderr__, ("Error opening socket for " +
			    "%s; socket is stale or otherwise unusable" %
			    filename)
			if (info[DCFinalizer._file_socket] != None):
				info[DCFinalizer._file_socket].close()
				info[DCFinalizer._file_socket] = None
			rval = DCFinalizer.GENERAL_ERR

		except KeyboardInterrupt, SystemExit:
			raise
		except:	# Includes OSError in case the file could not be opened
			rval = DCFinalizer.GENERAL_ERR

		if (rval == DCFinalizer.GENERAL_ERR):
			print("set_file: Error opening %s for writing" %
			    filename)
			info[DCFinalizer._file_fd] = None
			info[DCFinalizer._file_name] = stdfile

		return rval


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def change_exec_params(self, output=None, error=None, stop_on_err=None):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Queue up a change to stdout and/or stderr, and to set or
		clear the stop_on_err flag.

		Calls to this function may be interspersed with calls to
		register().  Functions queued with register() after a queued
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

		Returns:
		  0 if successful
		  1 if arguments are invalid

		Raises: None
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		epspec = []

		# Do some limited sanity argument typechecking
		if (((output != None) and
		    (not isinstance(output, basestring))) or
		    ((error != None) and
		    (not isinstance(error, basestring))) or
		    ((stop_on_err != None) and
		    (not isinstance(stop_on_err, bool)))):
			return DCFinalizer.GENERAL_ERR

		# Fill out and insert a new a queued element.
		epspec.insert(DCFinalizer._ep_type, DCFinalizer._type_exec_prm)
		epspec.insert(DCFinalizer._ep_out_filename, output)
		epspec.insert(DCFinalizer._ep_err_filename, error)
		epspec.insert(DCFinalizer._ep_stop_on_err, stop_on_err)
		self._execlist.append(epspec)
		return DCFinalizer.SUCCESS


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def register(self, module, arglist = ()):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Queue up a module to call during finalization.
		Any request to setup stdout and stderr for this module's
		execution is assumed already made.

		Args:
		  module: script or binary to invoke, or python-module:function
			to invoke.
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

		if module == None or module == "":
			return DCFinalizer.GENERAL_ERR

		# Check format of module string.
		mod_tuple = module.split(":")

		if (not (
		    # Script or binary with execute access.
		    ((len(mod_tuple) == 1) and
		    (os.access(mod_tuple[DCFinalizer._name_mod], os.X_OK))) or

		    # Module is string of format module:function.
		    # Python module:function with read access.
		    ((len(mod_tuple) == 2) and
		    (os.access(mod_tuple[DCFinalizer._name_mod], os.R_OK))))):
			return DCFinalizer.GENERAL_ERR

		# Fill out and insert a new a queued element.
		funcspec.insert(DCFinalizer._fs_type, DCFinalizer._type_func)
		funcspec.insert(DCFinalizer._fs_module, mod_tuple)
		funcspec.insert(DCFinalizer._fs_arglist, arglist)
		self._execlist.append(funcspec)
		return DCFinalizer.SUCCESS


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def _process_py(self, item):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Private function which processes python functions.
	# Functions run in their own namespace.
	# Doesn't return an error because the python interpreter which calls
	# this needs to continue to run
	#
	# Args:
	#   item: An item which describes what to execute, including the python
	#	module, function and arguments.
	#
	# Returns:
	#   0 if successful
	#   1 if an exception has occurred.
	#	In this case, the first exception will be saved in
	#	self._saved_exception
	#
	# Raises: None, but passes along KeyboardInterrupt and SystemExit
	#	exceptions.
	#
	#	Note though that errors get printed to the stderr logfile
	#	and first exception of the run is saved.
	#
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		module_no_py = item[DCFinalizer._fs_module][
		    DCFinalizer._name_mod].replace(".py", "")
		run_str = module_no_py + "." + str(
		    item[DCFinalizer._fs_module][DCFinalizer._name_func]) + '('

		# Build run_str, a string representing the function call with
		# arguments.

		first = True
		if (self._first_args != None):
			for arg in self._first_args:

				# Stringify and quote-envelope all args in
				# order to build command string.  Numerics are
				# passed to python (as to shells) as strings
				# for consistency among all scripts/programs
				# called.
				str_arg = "'" + str(arg) + "'"

				if not first:
					run_str += ","
				else:
					first = False

				run_str += str_arg

		# Now append args specified for individual scripts.
		for arg in item[DCFinalizer._fs_arglist]:

			# Stringify all args in order to build command string
			str_arg = str(arg)

			# Put quotes around all non-numeric arguments.  Here
			# numerics can be treated as such since only python
			# methods will be called with them and we don't have to
			# be consistent with shells here.
			if not install_utils.isnumber(str_arg):
				str_arg = "'" + str_arg + "'"

			if not first:
				run_str += ","
			else:
				first = False

			run_str += str_arg

		run_str += ")"

		# Build the string to compile on-the-fly.
		compstr = "import " + module_no_py
		compstr += "; " + run_str + "\n"

		# Set up proper stdout and stderr logging
		if (self._fileinfo[DCFinalizer.STDERR][DCFinalizer._file_fd] !=
		    None):
			sys.stderr = (self._fileinfo
			    [DCFinalizer.STDERR][DCFinalizer._file_fd])
		if (self._fileinfo[DCFinalizer.STDOUT][DCFinalizer._file_fd] !=
		    None):
			sys.stdout = (self._fileinfo
			    [DCFinalizer.STDOUT][DCFinalizer._file_fd])

		rval = DCFinalizer.SUCCESS

		# Compile.  Log any errors.
		exceptionOccurred = False
		try:
			bytecode = compile(compstr, run_str, "exec")
		except KeyboardInterrupt, SystemExit:
			raise
		except Exception, exceptionObj:
			if (self._saved_exception == None):
				self._saved_exception = exceptionObj
			rval = DCFinalizer.GENERAL_ERR	# Non-zero
			print >>sys.stderr, ("Error compiling to run python " +
			    "code string \"compstr\":")
			print >>sys.stderr, "    " + exceptionObj.__str__()
			exceptionOccurred = True

		# Import.  Log any errors.
		if not exceptionOccurred:
			try:
				import imp
				codeModule = imp.new_module(module_no_py)
			except KeyboardInterrupt, SystemExit:
				raise
			except Exception, exceptionObj:
				if (self._saved_exception == None):
					self._saved_exception = exceptionObj
				rval = DCFinalizer.GENERAL_ERR	# Non-zero
				print >>sys.stderr, ("Error importing " +
				    "module " + module_no_py + ":")
				print >>sys.stderr, ("    " +
				    exceptionObj.__str__())
				exceptionOccurred = True

		# Execute in its own namespace.  Log any errors.
		if not exceptionOccurred:
			try:
				exec bytecode in codeModule.__dict__
			except KeyboardInterrupt, SystemExit:
				raise
			except Exception, exceptionObj:
				if (self._saved_exception == None):
					self._saved_exception = exceptionObj
				rval = DCFinalizer.GENERAL_ERR	# Non-zero
				print >>sys.stderr,  ("Error running "
				    "function " + run_str + " in module " +
				    module_no_py + ":")
				print >>sys.stderr, ("    " +
				    exceptionObj.__str__())

		# Reset stdout and stderr before running code which should log
		# to standard output and error.
		sys.stderr = sys.__stderr__
		sys.stdout = sys.__stdout__

		return rval


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def _process_shell(self, item):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Private function which runs a shell script
	#
	# Args:
	#   item: An item which describes what to execute, including the script
	#	(module) and arguments.
	#
	# Returns:
	#   0 if successful
	#   negative signal number if shell's child process terminated by signal
	#   positive errno value if an error occured or
	#   1 with the exception object saved in self._saved_exception if
	#	an exception occured when trying to start the shell
	#
	# Raises: None.
	#	Note though that errors get printed to the stderr logfile
	#
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		shell_list = []

		shell_list.append(str(item[DCFinalizer._fs_module]
		    [DCFinalizer._name_mod]))

		if (self._first_args != None):
			for arg in self._first_args:
				shell_list.append(str(arg))

		for arg in item[DCFinalizer._fs_arglist]:
			shell_list.append(str(arg))

		# Try running the shell with stdout and stderr specified.  Wait
		# for completion.  Catch exceptions which arise when the shell
		# cannot be started.
		out_fd = self._fileinfo [DCFinalizer.STDOUT][
		    DCFinalizer._file_fd]
		err_fd = self._fileinfo [DCFinalizer.STDERR][
		    DCFinalizer._file_fd]
		try:
			rval = (subprocess.Popen(shell_list, shell=False,
			    stdout=out_fd, stderr=err_fd).wait())
			if rval < 0:
				print >> err_fd, (
				    "Child was terminated by signal" +
				    str(-rval))
			elif rval > 0:
				print >> err_fd, (
				    "Child returned err " + str(rval))
			if rval != 0:
				rval = DCFinalizer.GENERAL_ERR
		except OSError, exceptionObj:
			print >> err_fd, ("Error starting or running shell:" +
			    str(exceptionObj))
			print >> err_fd, ("shell_list = " + str(shell_list))

			# Set rval to a non-zero value.  Save the first
			# exception we get, to make it easier to trace the pblm.
			rval = DCFinalizer.GENERAL_ERR
			if (self._saved_exception == None):
				self._saved_exception = exceptionObj

		return rval


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def execute(self):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Set finalization into motion.  Starts working down the queue
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
			if item[DCFinalizer._fs_type] == DCFinalizer._type_func:
				if (len(item[DCFinalizer._fs_module]) ==
				    DCFinalizer._python_func_len):
					rval = self._process_py(item)
				else:
					rval = self._process_shell(item)
				if (saved_rval == DCFinalizer.SUCCESS):
					saved_rval = rval
				if (self._stop_on_err and rval !=
				    DCFinalizer.SUCCESS):
					break;
			elif (item[DCFinalizer._fs_type] ==
			    DCFinalizer._type_exec_prm):
				if (item[DCFinalizer._ep_err_filename] != None):
					self._set_file(item[
					    DCFinalizer._ep_err_filename],
					    "stderr")
				if (item[DCFinalizer._ep_out_filename] != None):
					self._set_file(item[
					    DCFinalizer._ep_out_filename],
					    "stdout")
				if (item[DCFinalizer._ep_stop_on_err] != None):
					self._stop_on_err = item[
					    DCFinalizer._ep_stop_on_err]

		# File pointers must be closed before sockets
		fileinfo = self._fileinfo[DCFinalizer.STDOUT]
		if (fileinfo[DCFinalizer._file_fd] != None):
			fileinfo[DCFinalizer._file_fd].close()
		if (fileinfo[DCFinalizer._file_socket] != None):
			fileinfo[DCFinalizer._file_socket].close()
		fileinfo = self._fileinfo[DCFinalizer.STDERR]
		if (fileinfo[DCFinalizer._file_fd] != None):
			fileinfo[DCFinalizer._file_fd].close()
		if (fileinfo[DCFinalizer._file_socket] != None):
			fileinfo[DCFinalizer._file_socket].close()

		return saved_rval


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_exception(self):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Retrieve a saved exception.

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

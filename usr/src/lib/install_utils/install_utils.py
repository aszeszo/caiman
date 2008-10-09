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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import os
import errno
import select
from subprocess import *
from logging import *

# =============================================================================
# =============================================================================
# Tracing section.
# =============================================================================
# =============================================================================

# =============================================================================
class Trace:
# =============================================================================
	"""Tracing facility.
	"""

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Constants
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Masks.  Add as needed, for different sections of the program.
	DEFVAL_MASK = 1<<0
	FINALIZER_MASK = 1<<1
	CHECKPOINT_MASK = 1<<2

	# Defaults.
	DEFAULT_LEVEL = 2
	DEFAULT_MASK = -1

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Classbound variables
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	master_level = DEFAULT_LEVEL
	master_mask = DEFAULT_MASK


	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def set_mask(new_mask):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Set a new mask for log to use for comparison.

		Args:
		  new_mask: New mask.

		Returns: N/A

		Raises: None
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		Trace.master_mask = new_mask


	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def set_level(new_level):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Set a new debug level for log to use for comparison.

		Args:
		  new_mask: New mask.

		Returns: N/A

		Raises: None
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		Trace.master_level = new_level

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def log(level, mask, formatstr, varargs=()):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Log a tracing message if level is numerically low enough and
		at least one bit of mask is set in master_mask.

		Args:
		  level: int level (priority) to print message.  The lower the
			number, the greater the likelihood the message will
			print.  Use lowest numbers for messages which always
			need to print, higher numbers for more detailed messages
			which are desired less frequently.

		  mask: bitmask used to categorize the message.  If message
			category isn't also set in the master_mask, the message
			won't print.

		  formatstr: format string, same as first arg to print.

		  varargs: tuple of args to pass to print after the format
			string and the subsequent "%" operator.  Defaults to an
			empty tuple if not provided.
		"""
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		if ((level <= Trace.master_level) and
		    ((mask & Trace.master_mask) != 0)):
			print formatstr % varargs


# =============================================================================
# =============================================================================
# Other utility functions
# =============================================================================
# =============================================================================

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def isnumber(arg):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Public function: does the (string) argument represent a number
	Hex, octal, decimal, floating point are all considered.
	Malformed numbers are considered not numeric.

	Test cases:
	  0x123, .123, 0x.1, 0x0x123, 12.2, 12..3, 12.,  1.2.3, 1.23, 12z4, abc,
	  0xabc, 0x1a2b3c4, 0xa2b3c4d, 0xabcdefg, 0xgabcdef, 0x123.

	Args:
	  String value to evaluate

	Returns:
	  True: string represents a number.
	  False: string does not represent a numeric value.

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	try:
		dummy = int(arg, 0)
		return True
	except ValueError:
		pass
	try:
		dummy = float(arg)
		return True
	except ValueError:
		pass
	return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def canaccess(filename, mode):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Test to see if can access filename with "mode" permissions

	If the file exists and can be accessed, just return.  Otherwise, throw
	an exception which contains appropriate errno value for proper error
	message.

	This method is needed because the chosen XML validator doesn't
	return an appropriate errno for its exit status, so file access needs
	to be checked independently.

	Args:
	  filename: Name of the file to test for access

	  mode: Character string mode, r=read, w=write, rw=read/write

	Returns: N/A

	Raises:
	  IOError with the appropriate errno: file doesn't exist or doesn't
		have the permissions required for the requested access.
	  IOError with errno = EINVAL: mode argument is invalid
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def canaccess(filename, mode):

	# Don't try opening file with mode "w", else file will be truncated.
	if (mode == "rw"):
		mode = "a+"
	elif (mode == "w"):
		mode = "a"
	elif (mode != "r"):
		raise IOError, (errno.EINVAL, os.strerror(errno.EINVAL) +
		    ": " + "mode")

	dummy = os.stat(filename)		# Check for file existance.
	dummy = open(filename, mode)		# Check for file permissions.
	dummy.close()				# Clean up if you get here.


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def comma_ws_split(input):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Split the input string, accounting for whitepspace and commas.
	User-friendly for lists in an XML doc.

	Args:
	  input: String to split.

	Returns:
	  list of items split out from the string, stripped of whitespace

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	intermediate_list = input.strip().split()
	out_list = []

	for s in intermediate_list:
		if (s.find(",") == -1):		# No comma
			out_list.append(s)	# Ready to go
	        else:
			# If last char is comma, next split will give a ""
			if (s[len(s) - 1] == ","):
				s = s[:len(s) - 1]
			if (len(s) > 0):
				out_list.extend(s.split(","))
	return out_list

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def exec_cmd_outputs_to_log(cmd, log,
    stdout_log_level=None, stderr_log_level=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Executes the given command and sends the stdout and stderr to log
	files.

	Args:
	  cmd: The command to execute.  The cmd is expected to have a suitable
	       format for calling Popen with shell=False, ie: the command and
	       its arguments should be in an array.
	  stdout_log_level: Logging level for the stdout of each command.  If not
               specified, it will be default to DEBUG
	  stderr_log_level: Logging level for the stderr of each command.  If not
               specified, it will be default to ERROR

	Returns:
	  The return value of the command executed.

	Raises: None
	"""

	if (stdout_log_level == None):
		stdout_log_level = DEBUG
	
	if (stderr_log_level == None):
		stderr_log_level = DEBUG

	#
	#number of bytes to read at once.  There's no particular
	#reason for picking this number, just pick a bigger
	#value so we don't need to have multiple reads for large output
	#
	buf_size=8192

	p = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=PIPE,
	    shell=False, close_fds=True)
	(child_stdout, child_stderr) = (p.stdout, p.stderr)

	out_fd = child_stdout.fileno()
	err_fd = child_stdout.fileno()

	while 1:
		ifd, ofd, efd = select.select([out_fd, err_fd], [],
		    [out_fd, err_fd])

		if out_fd in ifd:
			#something available from stdout of the command
			output = os.read(out_fd, buf_size)
			if not output:
				# process have terminated
				break;
			else:
				log.log(stdout_log_level, output)

		if err_fd in ifd:
			#something available from stderr of the command
			output = os.read(err_fd, buf_size)
			if not output:
				# process have terminated
				break;
			else:
				log.log(stderr_log_level, output)

	return (p.wait())

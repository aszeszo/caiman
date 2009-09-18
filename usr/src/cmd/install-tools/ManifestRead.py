#!/usr/bin/python2.4

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

# =============================================================================
# =============================================================================
# ManifestRead.py - Remote (AF-UNIX socket-based) XML data access
# 		    interface module commandline interface
# =============================================================================
# =============================================================================

import sys
import errno
import getopt
from osol_install.ManifestRead import ManifestRead

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def print_values(manifest_reader_obj, request_list, are_keys=False,
    force_req_print=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Given a list of requests, print the found values.

	Print values one per line.  Print the request next to the value, if
	more than one request is given, or if force_req_print is True.

	Args:
	  manifest_reader_obj: Manifest Reader which connects to the server to
		get the data.

	  request_list: List of requests to process.

	  are_keys: boolean: if True, the requests are interpreted as keys in
		the key_value_pairs section of the manifest.  In this case, the
		proper nodepath will be generated from each request and
		submitted.  If false, the requests are submitted for searching
		as provided.

	  force_req_print: if True, the request is printed next to the value
		when the request_list had only one request.  If False, the
		request is printed next to the value only when the request_list
		has multiple requests.

	Returns: None.  Output is printed to the screen.

	Raises:
	    Exceptions from get_value()
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	print_nodepath = ((len(request_list) > 1) or (force_req_print))
	for request in request_list:
		try:
			result_list = manifest_reader_obj.get_values(
			    request, are_keys)
		except Exception, err:
			raise
		if (print_nodepath):
			nodepath = request + " "
		else:
			nodepath = ""
		for result in result_list:
			print "%s%s" % (nodepath, result)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage(msg_fd):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Display commandline options and arguments.

	Args: msg_fd: file descriptor to write message to.

	Returns: None

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	print >>msg_fd, "Usage:"
	print >>msg_fd, ("  %s [-d] [-r] <socket name> <nodepath> " +
	    "[ ...<nodepath> ]") % (sys.argv[0])
	print >>msg_fd, (
	    "  %s [-d] [-r] [-k] <socket name> <key> [ ...<key> ]") % (
	    sys.argv[0])
	print >>msg_fd, "  %s [-h|-?]" % (sys.argv[0])
	print >>msg_fd, "where:"
	print >>msg_fd, "  -d: turn on debug output"
	print >>msg_fd, "  -h or -?: print this message"
	print >>msg_fd, "  -k: specify keys instead of nodepaths"
	print >>msg_fd, "  -r: Always print nodepath next to a value"
	print >>msg_fd, "      (even when only one nodepath is specified)"
	print >>msg_fd, ""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":

	# Initialize.
	err = None
	ret = 0
	debug = are_keys = force_req_print = False

	# Parse commandline into options and args.
	try:
		(opt_pairs, other_args) = getopt.getopt(sys.argv[1:], "dhkr?")
	except getopt.GetoptError, err:
		print >>sys.stderr, "ManifestRead: " + str(err)
	except IndexError, err:
		print >>sys.stderr, "ManifestRead: Insufficient arguments"
	if (err != None):
		usage(sys.stderr)
		sys.exit (errno.EINVAL)

	# Set option flags.
	for (opt, optarg) in opt_pairs:
		if (opt == "-d"):
			debug = True
		elif ((opt == "-h") or (opt == "-?")):
			usage(sys.stdout)
			sys.exit (0)
		elif (opt == "-k"):
			are_keys = True
		elif (opt == "-r"):
			force_req_print = True

	# Must have at least socket specified as first arg.
	if (len(other_args) < 1):
		usage(sys.stderr)
		sys.exit (errno.EINVAL)

	# Do the work.
	try:
		mrobj = ManifestRead(other_args[0])
		mrobj.set_debug(debug)
		print_values(mrobj, other_args[1:], are_keys, force_req_print)
	except (SystemExit, KeyboardInterrupt):
		pass
	except Exception, err:
		print >>sys.stderr, "Error running Manifest Reader"
	if (err):
		ret = err.args[0]
	sys.exit(ret)

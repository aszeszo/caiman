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
def usage():
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Display commandline options and arguments.

	Args: None

	Returns: None

	Raises: None
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	print ("Usage: %s [-d] [-h|-?] [-k] [-r] <socket name> <nodepath> " +
	    "[ ...<nodepath> ]") % (sys.argv[0])
	print "where:"
	print "  -d: turn on debug output"
	print "  -h or -?: print this message"
	print "  -k: specify keys instead of nodepaths"
	print "  -r: Always print nodepath next to a value"
	print "      (even when only one nodepath is specified)"
	print ""


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
		print "ManifestRead: " + str(err)
	except IndexError, err:
		print "ManifestRead: Insufficient arguments"
	if (err != None):
		usage()
		sys.exit (errno.EINVAL)

	# Set option flags.
	for (opt, optarg) in opt_pairs:
		if (opt == "-d"):
			debug = True
		elif ((opt == "-h") or (opt == "-?")):
			usage()
			sys.exit (0)
		elif (opt == "-k"):
			are_keys = True
		elif (opt == "-r"):
			force_req_print = True

	# Must have at least socket specified as first arg.
	if (len(other_args) < 1):
		usage()
		sys.exit (errno.EINVAL)

	# Do the work.
	try:
		mrobj = ManifestRead(other_args[0])
		mrobj.set_debug(debug)
		mrobj.print_values(other_args[1:], are_keys, force_req_print)
	except SystemExit:
		print "Caught SystemExit exception"
	except KeyboardInterrupt:
		print "Interrupted"
	except Exception, err:
		print "Exception caught:"
		print str(err)
	if (err):
		ret = err.args[0]
	sys.exit(ret)

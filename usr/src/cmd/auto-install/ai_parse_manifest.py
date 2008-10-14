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
import getopt
import sys
import os
from osol_install.ManifestServ import ManifestServ

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_verify_manifest_filename(manifest_file):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Verify that the specified manifest file is readable.
	Returns
	   0 - success
	  -1 on error
	"""
	try:
		file_name = open(manifest_file, "r")
	except (IOError):
	    	print "You have specified a file (%s) that is unable to " \
		    "be read." % name
		return -1
	file_name.close()
	return 0
	     
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_get_manifest_server_obj(manifest_file):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	err = ai_verify_manifest_filename(manifest_file)
	if err != 0: 
		return -1
	return  ManifestServ(manifest_file)
		

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_start_manifest_server(manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	manifest_server_obj.start_socket_server()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_stop_manifest_server(manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	manifest_server_obj.stop_socket_server()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_create_manifestserv(ai_manifest_file):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	try:
		# Create the object used to extract the data
		manifest_server_obj = \
			ai_get_manifest_server_obj(ai_manifest_file)

		# Start the socket server
		ai_start_manifest_server(manifest_server_obj)
	except:
		return

	# return the socket object that was created
	return (manifest_server_obj)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_lookup_manifest_values(manifest_server_obj, path):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    	""" Read the value of the path specified.
	This returns only the first value of the list

	Args:
	    manifest_server_obj: ManifestServ object
	    path: path to read

	Returns:
	    the first value found (as a string) if there is at least
	    one value to retrieve.
	    None: if no value is found

	Raises:
	    None
	"""

	node_list = manifest_server_obj.get_values(path, False)
  	if (len(node_list) > 0):
  		return (node_list)
  	return None

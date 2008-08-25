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
import osol_install.install_utils
from subprocess import *
import fnmatch
import osol_install.distro_const.DC_checkpoint


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_node(manifest_defs, node, parent=None):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Read the node specified.

	Args:
	   manifest_defs: An initialized TreeAcc instance
	   node: name of the node to read
	   parent: parent node

	Returns:
	   the node 

	Raises:
	   None
	"""

	return get_manifest_node_list(manifest_defs, node, parent)[0]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_value(manifest_defs, node, parent=None):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Read the value of the node specified.

	Args:
	   manifest_defs: An initialized TreeAcc instance
	   node: name of the node to read
	   parent: parent node

	Returns:
	   the value as a string

	Raises:
	   None
	"""

	return str(get_manifest_node(manifest_defs, node,
	    parent).get_value())

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_node_list(manifest_defs, node, parent=None):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Create a list of the nodes specified.

	Args:
	   manifest_defs: An initialized TreeAcc instance
	   node: name of the node to read
	   parent: parent node

	Returns:
	   A list of nodes 

	Raises:
	   None
	"""

	try:
		return manifest_defs.find_node(node, parent)
	except:
		print "Unable to find node " + node

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_list(manifest_defs, node, parent=None):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Create a list of the values of the node specified.

	Args:
	   manifest_defs: An initialized TreeAcc instance
	   node: name of the node to read
	   parent: parent node

	Returns:
	   A list of values 

	Raises:
	   None
	"""

	try:
		node_list = manifest_defs.find_node(node, parent)
	except:
		print "Unable to find node " + node

	lst = []
	index = 0
	for node in node_list:
		lst.append(str(node.get_value()))
		index += 1
	return lst

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_tmpdir():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Create a temporary directory in /tmp/distro_tool.<pid>
	Returns: directory created
		None on error
	Raises:
		None
	"""
	dir_name = 'distro_tool.' + str(os.getpid())

	for dirs in os.listdir('/tmp'):
		if fnmatch.fnmatch(dirs, dir_name):
			return os.path.join('/tmp', dir_name) 
		
	try:
		os.makedirs(os.path.join('/tmp',dir_name))
	except:
		return None 

	return os.path.join('/tmp', dir_name) 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanup_dir(mntpt):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Remove all files and directories underneath the mount point.
	Any errors are ignored since they aren't fatal.

	Input:
	   mntpt: mount point to remove files and directories from

	Returns:
	   None

	Raises:
	   None
	"""

	for root, dirs, files in os.walk(mntpt, topdown=False):
		for name in files:
			try:
				os.unlink(os.path.join(root,name))
			except:
				pass

		for dir in dirs:
			try:
				os.rmdir(os.path.join(root,dir))
			except:
				pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanup_tmpdir(mntpt):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""Remove all files and directories and the mount point.
	Any errors are ignored since they aren't fatal.

	Input:
	   mntpt: mount point to remove files and directories from

	Returns:
	   None

	Raises:
	   None
	"""


	cleanup_dir(mntpt);
	try:
		os.rmdir(mntpt)
	except:
		pass

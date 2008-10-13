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
# Module containing default calculating methods.
# =============================================================================
# =============================================================================

from time import strftime
from osol_install.TreeAcc import TreeAcc, TreeAccError
from osol_install.distro_const.DC_defs import DISTRO_NAME, USER, USER_UID
from osol_install.distro_const.DC_defs import OUTPUT_IMAGE

# =============================================================================
class DefaultsModule:
	""" Module containing default-setter methods, called by methods in the
	DefValProc.py module on the direction of the defval-manifest.

	Each method in this class takes a TreeAccNode of the parent of the node
	to validate, and returns a string which is the calculated default
	value for a new child node.  If the method should return a boolean
	value, the value must be in all lowercase letters to be compatible with
	XML.

	Note that through the node passed in, the method has access to the whole
	tree.  This allows the method to scan the tree for other relevant nodes
	and check their characteristics (in case the value being calculated
	needs to be based on some other node in the tree).
	"""
# =============================================================================

	# ------------------
	# General parameters
	# ------------------

	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def distro_name(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return a time string YYYYMMDD-HHmm
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		return strftime("%Y%m%d-%H%M")


	# ---------------------
	# Live image parameters
	# ---------------------

	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def root_direct_login(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return "true" if no users are defined, "false" otherwise.
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		tree = parent_node.get_tree()
		non_root_users = tree.find_node(USER)
		return (len(non_root_users) == 0)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def homedir(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return /export/home/<username>
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		parent_node_attrs = parent_node.get_attr_dict()
		username_str = parent_node_attrs["username"]
		return "/export/home/" + username_str


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __UID(self, parent_node, path):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Return a UID value which is not currently in use.
	#
	# The value returned may not necessarily be numerically higher
	# than all of those in use.
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

		# Default is to start counting at 1000.
		uid = 1000

		tree = parent_node.get_tree()

		# Get list of all UID nodes
		uid_nodes = tree.find_node(USER_UID)
		if (len(uid_nodes) == 0):
			return uid

		found = True

		# Keep looping thru all nodes until no match found.
		while (found):
			found = False
			# If find a match for current uid value, bump current
			# value and start over.
			for uid_node in uid_nodes:
				if (uid_node.get_value() == str(uid)):
					uid += 1
					del uid_node
					found = True
					break
		return uid


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def live_img_UID(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return a UID value which is not currently in use as a live
		image UID.

		The value returned may not necessarily be numerically higher
		than all of those in use for a live image.
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		return self.__UID(parent_node, USER_UID)

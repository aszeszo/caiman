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


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def logdir(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return /export/home/<distro_name>_log
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		tree = parent_node.get_tree()
		distro_name = tree.find_node("name")[0].get_value()
		return "/export/home/" + distro_name + "_log"


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
		non_root_users = tree.find_node("live_img_params/user")
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
	def proto_path(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return /export/home/<distro_name>/proto
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		tree = parent_node.get_tree()
		distro_name = tree.find_node("name")[0].get_value()
		return "/export/home/" + distro_name + "/proto"


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def out_img_path(self, parent_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return /export/home/<distro_name>/bootimage<num>
		where <num> gets incremented one past any existing instances
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

		# Build base string: all except the number at the end
		tree = parent_node.get_tree()
		distro_name = tree.find_node("name")[0].get_value()
		base_string = "/export/home/" + distro_name + "/bootimage"

		# Loop through all output image nodes, looking for names that
		# match the style of the default name

		output_imgs = tree.find_node("live_img_params/output_image")
		count = 0
		for i in range(len(output_imgs)):

			# Get the image name.
			pathname_node = tree.find_node(
			    "pathname", output_imgs[i])

			# Current output image has no pathname.
			if (len(pathname_node) == 0):
				continue

			# Find all pathnames starting with base_string.
			# Find the first unused number to append to the default
			# base_string to get a unique name.

			value = pathname_node[0].get_value()

			# The first part matches the base string.
			if (value.find(base_string) == 0):

				# Get the number (digit string) at end.
				num_str = value[len(base_string):]

				# Verify that it is a number.  If not, skip it.
				try:
					num_val = int(num_str, 0)
				except ValueError:
					continue

				# Count keeps track of first unused number.
				if (count <= num_val):
					count = num_val + 1

		# Return a string w/a number one higher than the greatest found.
		return "/export/home/" + distro_name + "/bootimage" + str(count)


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
		uid_nodes = tree.find_node("live_img_params/user/UID")
		if (len(uid_nodes) == 0):
			return uid

		found = True

		# Keep looping thru all nodes until no match found.
		while (found):
			found = False
			# If find a match for current uid value, bump current
			# value and start over.
			for i in range(len(uid_nodes)):
				if (uid_nodes[i].get_value() == str(uid)):
					uid += 1
					del uid_nodes[i]
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
		return self.__UID(parent_node, "live_img_params/user/UID")

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

from osol_install.libti import *
from osol_install.distro_const.dc_utils import *
from osol_install.distro_const.DC_checkpoint import *

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/DC_defs.py")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_ufs_dir(pathname):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Create a basic directory at the mountpoint specified.
	Input: pathname
	Return: 0 if the directory is created
		TI module error code if the create fails
	"""	
	status = ti_create_target({TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_UFS,
	    TI_ATTR_DC_UFS_DEST:pathname})
	if status:
		print "Unable to create directory " + pathname	
	return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_zfs_fs(zfs_dataset):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Create a zfs dataset with the specified name.
	The pool must already exist.
	Input: dataset name
	Return: 0 if the dataset is created
		transfer module error code if unable to create the dataset
	""" 
	zfs_dataset_lst = zfs_dataset.split('/',1)
	pool = zfs_dataset_lst[0]
	pathname = zfs_dataset_lst[1] 
	status = ti_create_target({TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_ZFS_FS,
	    TI_ATTR_ZFS_FS_POOL_NAME: pool,
	    TI_ATTR_ZFS_FS_NUM: 1,
	    TI_ATTR_ZFS_FS_NAMES: [pathname]})
	if status:
		print "Unable to create the zfs dataset %s. You may want " \
		    " to check that the pool %s exists. " % (pathname, pool)
	return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_pkg_image_area(cp, manifest_server_obj):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Create the pkg image area. This may be a normal directory or
	a zfs dataset. If the pkg image area isn't specified in the
	manifest file, create the area at:
	/export/home/<distribution_name>/proto.
	If it is specified and doesn't start with / a zfs dataset will attempt
	to be created. If it starts with a /, check to see if it's a zfs
	mountpoint.  If not, a normal directory (mkdir) will be created.
	Returns: -1 on failure 
		0 on Success
	"""

	# Check manifest file and existence of zfs to see if
	# checkpointing is possible.
	DC_determine_checkpointing_availability(cp, manifest_server_obj)

	pkg_image = get_manifest_value(manifest_server_obj,
	    PKG_IMAGE_AREA)
	if len(pkg_image) == 0:
		print PKG_IMAGE_AREA + " in the manifest file is" \
		    " invalid. Build aborted"
		return -1

	else:
		# Use specified value. First check to see
		# if there is a leading /
		if pkg_image.startswith('/'):
			# Leading /. See if this is a zfs mountpoint
			if cp.get_zfs_found():
				cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " \
				    + pkg_image
				try:
					mntpt = Popen(cmd, shell=True,
					    stdout=PIPE).communicate()[0].rstrip()
				except:
					print "Error determining if the " \
					    "package image area exists"
					return -1 

				# Need to find the dataset associated with
				# the mntpt
				cmd = "/usr/sbin/zfs list -H -o \"name\" " \
				    + pkg_image
				try:
					dataset = Popen(cmd, shell=True,
					    stdout=PIPE).communicate()[0].rstrip()
				except:
					print "Error finding the pkg image " \
					    "dataset"
					return -1 

				if dataset:
					if mntpt == pkg_image:
						cp.set_pkg_image_dataset(dataset)
						cp.set_pkg_image_mntpt(mntpt)
						return 0 
					elif mntpt:
						# create the sub directory 
						cp.set_checkpointing_avail(False)
						ret = DC_create_ufs_dir(pkg_image)
						if ret:
							print "Unable to create " + pkg_image
							return -1
						cp.set_pkg_image_dataset(pkg_image.replace('/','',1))
						cp.set_pkg_image_mntpt(pkg_image)
						return 0 
					

			# No zfs mountpoint, create a ufs style dir. 
			cp.set_checkpointing_avail(False)
			ret = DC_create_ufs_dir(pkg_image)
			if ret:
				print "Unable to create the package "\
				    "image area at " + pkg_image
				return -1 
			else:
				cp.set_pkg_image_mntpt(pkg_image)
				return 0 
		else:
			if not cp.get_zfs_found():
				print "ZFS dataset was specified for the " \
				    "pkg image area but zfs is not " \
				    "installed on the system"
				return -1 

			# create zfs fs
			ret = DC_create_zfs_fs(pkg_image)
			if ret:
				return -1 

			cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " \
			    + pkg_image
			try:
				mntpt = Popen(cmd, shell=True,
				    stdout=PIPE).communicate()[0].strip()
			except:
				print "Unable to get the mountpoint for " \
				    " the zfs dataset " + pkg_image
				return -1 

			cp.set_pkg_image_mntpt(mntpt)
			cp.set_pkg_image_dataset(pkg_image)
			return 0 

execfile("/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py")

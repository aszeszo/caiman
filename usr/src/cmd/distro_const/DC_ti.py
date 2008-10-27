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
import logging

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/" \
    "DC_defs.py")
execfile("/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py")

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
		dc_log = logging.getLogger(DC_LOGGER_NAME)
		dc_log.error("Unable to create directory " + pathname)
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
		dc_log = logging.getLogger(DC_LOGGER_NAME)
		dc_log.error("Unable to create the zfs dataset %s. " % pathname)
		dc_log.error("You may want to check that the pool %s exists."
		    % pool)
	return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_subdirs(cp):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Create the subdirectories for the build area. This means
	creating the build_data/pkg_image, media, logs, build_data/tmp,
	and build_data/bootroot directories.
	"""

	dc_log = logging.getLogger(DC_LOGGER_NAME)

	# If the build_area_dataset isn't set, we're using ufs so
	# make the subdirs ufs and the user won't be able to use checkpointing.
	dataset = cp.get_build_area_dataset()
	mntpt = cp.get_build_area_mntpt()
	if dataset is None: 
		ret = DC_create_ufs_dir(mntpt + PKG_IMAGE)
		if ret:
			dc_log.error("Unable to create " + mntpt + PKG_IMAGE)
			return -1
		ret = DC_create_ufs_dir(mntpt + BOOTROOT)
		if ret:
			dc_log.error("Unable to create " + mntpt + BOOTROOT)
			return -1
		ret = DC_create_ufs_dir(mntpt + MEDIA)
		if ret:
			dc_log.error("Unable to create " + mntpt + MEDIA)
			return -1
		ret = DC_create_ufs_dir(mntpt + LOGS)
		if ret:
			dc_log.error("Unable to create " + mntpt + LOGS)
			return -1
		ret = DC_create_ufs_dir(mntpt + TMP)
		if ret:
			dc_log.error("Unable to create " + mntpt + TMP)
			return -1
	else:
		# The build area dataset is set, so make build_data, media 
		# and log subdirs zfs datasets.
		ret = DC_create_zfs_fs(dataset + BUILD_DATA) 
		if ret:
			dc_log.error("Unable to create " + dataset + BUILD_DATA)
			return -1
		ret = DC_create_zfs_fs(dataset + MEDIA)
		if ret:
			dc_log.error("Unable to create " + dataset + MEDIA) 
			return -1
		ret = DC_create_zfs_fs(dataset + LOGS) 
		if ret:
			dc_log.error("Unable to create " + dataset + LOGS) 
			return -1

		# create the bootroot, pkg_image and tmp subdirs in the 
		# build_data dataset. Don't make them independent datasets
		# since we want to do 1 snapshot of build_data for data
		# consistency
		ret = DC_create_ufs_dir(mntpt + BOOTROOT)
		if ret:
			dc_log.error("Unable to create " + mntpt + BOOTROOT)
			return -1
		ret = DC_create_ufs_dir(mntpt + TMP)
		if ret:
			dc_log.error("Unable to create " + mntpt + TMP) 
			return -1
		ret = DC_create_ufs_dir(mntpt + PKG_IMAGE)
		if ret:
			dc_log.error("Unable to create " + mntpt + PKG_IMAGE) 
			return -1

	return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_build_area(cp, manifest_server_obj):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Create the build area. This may be a normal directory or
	a zfs dataset. If it is specified and doesn't start with / a
	zfs dataset will attempt to be created. If it starts with a /,
	check to see if it's a zfs mountpoint.  If not, a normal
	directory (mkdir) will be created. This is where all the sub
	working directories are created. This includes the pkg_image, logs,
	media and bootroot directories that reside under the build area.
	Returns: -1 on failure 
		0 on Success
	"""

	# Check manifest file and existence of zfs to see if
	# checkpointing is possible.
	DC_determine_checkpointing_availability(cp, manifest_server_obj)

	dc_log = logging.getLogger(DC_LOGGER_NAME)

	# Read the build_area from the manifest file. This can be either
	# a zfs dataset or a mountpoint.
	build_area = get_manifest_value(manifest_server_obj,
	    BUILD_AREA)
	if build_area == None:
		dc_log.error(BUILD_AREA + " in the manifest file is invalid " \
		    "or missing. Build aborted")
		return -1

	# First check build_area to see
	# if there is a leading /. If there isn't, it has to be a zfs dataset.
	if build_area.startswith('/'):
		# Leading /. build_area can be either a zfs mountpoint or
		# a ufs mountpoint.
		if cp.get_zfs_found():
			# zfs is on the system so it's at least possible
			# that build_area is a zfs mountpoint.

			# zfs list -o mountpoint <build_area> will return
			# the mountpoint for the build_area specified.
			cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " \
			    + build_area 
			try:
				mntpt = Popen(cmd, shell=True,
				    stdout=PIPE).communicate()[0].strip()
			except:
				dc_log.error("Error determining if the build " \
				    "area exists")
				return -1 

			# zfs list -H -o name <build_area> will return
			# the zfs dataset associated with build_area
			cmd = "/usr/sbin/zfs list -H -o \"name\" " \
			    + build_area 
			try:
				dataset = Popen(cmd, shell=True,
				    stdout=PIPE).communicate()[0].strip()
			except:
				dc_log.error("Error finding the build area " \
				    "dataset")
				return -1 

			# If we have found a dataset, check to see if
			# the mountpoint and the build_area are the same.
			# If so, the build_area that was specified is
			# a zfs mountpoint that directly correlates to
			# a zfs dataset. If the mountpoint and the build_area
			# are not the same, there is not a direct match
			# and we can't use checkpointing.
			if dataset:
				if mntpt == build_area:
					# We have a zfs dataset and
					# mountpoint so we don't have
					# to create one. Just save
					# the dataset and mountpoint ofr
					# later use and create the subdirs.
					cp.set_build_area_dataset(
					    dataset)
					cp.set_build_area_mntpt(mntpt)
						
					# And now create the subdirs
					# for pkg_image, media, logs,
					# tmp, and bootroot 
					ret = DC_create_subdirs(cp)
					if ret:
						return -1

					return 0 
				# We have a build area that doesn't
				# have a direct matchup to a mountpoint.
				# Checkpointing must not be used. If
				# we checkpoint, we run the risk of
				# rollinging back more data than would
				# be wise. ex. build area is
				# /export/home/someone but the mntpt
				# is /export/home.
				cp.set_checkpointing_avail(False)
				cp.set_build_area_mntpt(build_area)

				# And now create the subdirs
				# for pkg_image, media, logs,
				# tmp and bootroot 
				ret = DC_create_subdirs(cp)
				if ret:
					return -1
				return 0 
					
		# No zfs on the system or no zfs dataset that relates
		# to the build_area, create a ufs style dir. 
		cp.set_checkpointing_avail(False)
		ret = DC_create_ufs_dir(build_area)
		if ret:
			dc_log.error("Unable to create the build area at "
			    + build_area)
			return -1 
		else:
			cp.set_build_area_mntpt(build_area)
			return 0 

		# And now create the subdirs
		# for pkg_image, media, logs,
		# tmp and bootroot 
		ret = DC_create_subdirs(cp)
		if ret:
			return -1
	else:
		# build_area doesn't start with a /, thus it
		# has to be a zfs dataset.

		# Check to see if zfs is on the system. If
		# not we have an error since a zfs dataset
		# was specified.
		if not cp.get_zfs_found():
			dc_log.error("ZFS dataset was specified for the " \
			    "build area,") 
			dc_log.error("but zfs is not installed on the system.")
			return -1 

		# create zfs fs
		ret = DC_create_zfs_fs(build_area)
		if ret:
			return -1 

		# The zfs fs was created, get the associated mountpoint
		cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " \
		    + build_area 
		try:
			mntpt = Popen(cmd, shell=True,
			    stdout=PIPE).communicate()[0].strip()
		except:
			dc_log.error("Unable to get the mountpoint for the " \
			    "zfs dataset " + build_area)
			return -1 

		cp.set_build_area_mntpt(mntpt)
		cp.set_build_area_dataset(build_area)

		# And now create the subdirs
		# for pkg_image, media, logs,
		# tmp and bootroot 
		ret = DC_create_subdirs(cp)
		if ret:
			return -1
		return 0 

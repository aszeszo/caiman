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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
#

"""dc_ti.py - DC code to interface with the TI module. """

import logging
from subprocess import Popen, PIPE

import osol_install.libti as ti 
import osol_install.distro_const.dc_utils as dcu 
import osol_install.distro_const.dc_checkpoint as dc_ckp 

from osol_install.distro_const.dc_defs import DC_LOGGER_NAME, \
    BOOT_ARCHIVE, TMP, PKG_IMAGE, BUILD_DATA, MEDIA, LOGS, BUILD_AREA

from osol_install.ti_defs import TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_DC_UFS, \
    TI_ATTR_DC_UFS_DEST, TI_TARGET_TYPE_ZFS_FS, TI_ATTR_ZFS_FS_POOL_NAME, \
    TI_ATTR_ZFS_FS_NUM, TI_ATTR_ZFS_FS_NAMES
 

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_ufs_dir(pathname):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Create a basic directory at the mountpoint specified.
    Input: pathname
    Return: 0 if the directory is created
            TI module error code if the create fails

    """
    status = ti.ti_create_target({TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_UFS,
                                  TI_ATTR_DC_UFS_DEST:pathname})
    if status:
        dc_log = logging.getLogger(DC_LOGGER_NAME)
        dc_log.error("Unable to create directory " + pathname)
    return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_zfs_fs(zfs_dataset):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Create a zfs dataset with the specified name.
    The pool must already exist.
    Input: dataset name
    Return: 0 if the dataset is created
            transfer module error code if unable to create the dataset

    """
    zfs_dataset_lst = zfs_dataset.split('/', 1)
    pool = zfs_dataset_lst[0]
    pathname = zfs_dataset_lst[1]
    status = ti.ti_create_target({TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_ZFS_FS,
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
def create_bld_data_area_subdrs(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Create the build_data sub directories of pkg_image, tmp, and
    boot_archive.

    Args:
             mntpt - "root" where the subdirs are to be created

    Returns:
            -1 on Failure
             0 on Success

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    create_err = "Unable to create " + mntpt

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    ret = create_ufs_dir(mntpt + BOOT_ARCHIVE)
    if ret:
        dc_log.error(create_err + BOOT_ARCHIVE)
        return -1
    ret = create_ufs_dir(mntpt + TMP)
    if ret:
        dc_log.error(create_err + TMP)
        return -1

    ret = create_ufs_dir(mntpt + PKG_IMAGE)
    if ret:
        dc_log.error(create_err + PKG_IMAGE)
        return -1

    return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_zfs_build_data_area(ckp):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Create the build_data dataset and sub directories of pkg_image,
    tmp, and boot_archive.

    Args:
            ckp - checkpointing object

    Returns:
            -1 on Failure
             0 on Success

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    dataset = ckp.get_build_area_dataset()
    mntpt = ckp.get_build_area_mntpt()

    # Create the build_data zfs dataset
    ret = create_zfs_fs(dataset + BUILD_DATA)
    if ret:
        dc_log.error("Unable to create " + dataset + BUILD_DATA)
        return -1

    # create the boot_archive, pkg_image and tmp subdirs in the
    # build_data dataset. Don't make them independent datasets
    # since we will want to do 1 snapshot of build_data for data
    # consistency
    return create_bld_data_area_subdrs(mntpt)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_ufs_build_data_area(ckp):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Create the directories for the build_data area. This means
    creating the build_data/pkg_image, build_data/tmp,
    and build_data/boot_archive directories.

    Args:
            ckp - checkpointing object

    Returns:
            -1 on failure
             0 on success

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    mntpt = ckp.get_build_area_mntpt()

    # Create build data area.
    ret = create_ufs_dir(mntpt + BUILD_DATA)
    if (ret == -1):
        dc_log.error("Unable to create " + mntpt + BUILD_DATA)
        return -1

    # Create subdirs of build_data area.
    return create_bld_data_area_subdrs(mntpt)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_subdirs(ckp):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Create the subdirectories for the build area. This means
    creating the build_data/pkg_image, media, logs, build_data/tmp,
    and build_data/boot_archive directories.

    Args:
            ckp - checkpointing object

    Returns:
            -1 on failure
             0 on success

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # If the build_area_dataset isn't set, we're using ufs so
    # make the subdirs ufs and the user won't be able to use checkpointing.
    dataset = ckp.get_build_area_dataset()
    mntpt = ckp.get_build_area_mntpt()
    if dataset is None:
        # Create the build_data, build_data/pkg_image, build_data/tmp,
        # and build_data/boot_archive directories.
        ret = create_ufs_build_data_area(ckp)
        if ret:
            dc_log.error("Error creating the build_data area")
            return -1
        ret = create_ufs_dir(mntpt + MEDIA)
        if ret:
            dc_log.error("Unable to create " + mntpt + MEDIA)
            return -1
        ret = create_ufs_dir(mntpt + LOGS)
        if ret:
            dc_log.error("Unable to create " + mntpt + LOGS)
            return -1
    else:
        # The build area dataset is set, so make build_data, media
        # and log subdirs zfs datasets.
        ret = create_zfs_build_data_area(ckp)
        if ret:
            dc_log.error("Error creating the build_data area")
            return -1

        ret = create_zfs_fs(dataset + MEDIA)
        if ret:
            dc_log.error("Unable to create " + dataset + MEDIA)
            return -1
        ret = create_zfs_fs(dataset + LOGS)
        if ret:
            dc_log.error("Unable to create " + dataset + LOGS)
            return -1

    return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_build_area(ckp, manifest_server_obj):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Create the build area. This may be a normal directory or
    a zfs dataset. If it is specified and doesn't start with / a
    zfs dataset will attempt to be created. If it starts with a /,
    check to see if it's a zfs mountpoint.  If not, a normal
    directory (mkdir) will be created. This is where all the sub
    working directories are created. This includes the pkg_image, logs,
    media and boot_archive directories that reside under the build area.

    Args:
            ckp - checkpointing object

            manifest_server_obj: manifest data extraction object

    Returns:
            -1 on failure
             0 on success

    """

    # Check manifest file and existence of zfs to see if
    # checkpointing is possible.
    dc_ckp.determine_chckpnt_avail(ckp, manifest_server_obj)

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    # Read the build_area from the manifest file. This can be either
    # a zfs dataset or a mountpoint.
    build_area = dcu.get_manifest_value(manifest_server_obj,
                                        BUILD_AREA)
    if build_area is None:
        dc_log.error(BUILD_AREA + " in the manifest file is invalid " \
                     "or missing. Build aborted")
        return -1

    # First check build_area to see
    # if there is a leading /. If there isn't, it has to be a zfs dataset.
    if build_area.startswith('/'):
        # Leading /. build_area can be either a zfs mountpoint or
        # a ufs mountpoint.
        if ckp.get_zfs_found():
            # zfs is on the system so it's at least possible
            # that build_area is a zfs mountpoint.

            # zfs list -o mountpoint <build_area> will return
            # the mountpoint for the build_area specified.
            cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " \
                  + build_area
            try:
                mntpt = Popen(cmd, shell=True,
                              stdout=PIPE).communicate()[0].strip()
            except OSError:
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
            except OSError:
                dc_log.error("Error finding the build area dataset")
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
                    ckp.set_build_area_dataset(dataset)
                    ckp.set_build_area_mntpt(mntpt)

                    # And now create the subdirs
                    # for pkg_image, media, logs,
                    # tmp, and boot_archive
                    ret = create_subdirs(ckp)
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
                ckp.set_checkpointing_avail(False)
                ckp.set_build_area_mntpt(build_area)

                # And now create the subdirs
                # for pkg_image, media, logs,
                # tmp and boot_archive
                ret = create_subdirs(ckp)
                if ret:
                    return -1
                return 0

        # No zfs on the system or no zfs dataset that relates
        # to the build_area, create a ufs style dir.
        ckp.set_checkpointing_avail(False)
        ret = create_ufs_dir(build_area)
        if ret:
            dc_log.error("Unable to create the build area at "
                         + build_area)
            return -1
        else:
            ckp.set_build_area_mntpt(build_area)

        # And now create the subdirs
        # for pkg_image, media, logs,
        # tmp and boot_archive
        ret = create_subdirs(ckp)
        if ret:
            return -1
    else:
        # build_area doesn't start with a /, thus it
        # has to be a zfs dataset.

        # Check to see if zfs is on the system. If
        # not we have an error since a zfs dataset
        # was specified.
        if not ckp.get_zfs_found():
            dc_log.error("ZFS dataset was specified for the build area,")
            dc_log.error("but zfs is not installed on the system.")
            return -1

        # create zfs fs
        ret = create_zfs_fs(build_area)
        if ret:
            return -1

        # The zfs fs was created, get the associated mountpoint
        cmd = "/usr/sbin/zfs list -H -o \"mountpoint\" " + build_area
        try:
            mntpt = Popen(cmd, shell=True,
                          stdout=PIPE).communicate()[0].strip()
        except OSError:
            dc_log.error("Unable to get the mountpoint for the "
                         "zfs dataset " + build_area)
            return -1

        ckp.set_build_area_mntpt(mntpt)
        ckp.set_build_area_dataset(build_area)

        # And now create the subdirs
        # for pkg_image, media, logs,
        # tmp and boot_archive
        ret = create_subdirs(ckp)
        if ret:
            return -1
    return 0

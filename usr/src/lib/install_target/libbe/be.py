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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

import ctypes as C

from solaris_install.target.libbe import cfunc
from solaris_install.target.libbe import cstruct
from solaris_install.target.libbe import const
from solaris_install.target.libnvpair import nvl


def be_list(name=None):
    """ be_list() - function to list all BEs on the system

    name - optional argument.  If provided, only list the named BE
    """
    # create a new pointer to a pointer
    be_node_list = C.pointer(C.pointer(cstruct.BENodeList()))
    err = cfunc.be_list(name, be_node_list)
    if err == const.BE_ERR_BE_NOENT:
        # there are no BEs, so just return an empty list.
        return []
    elif err != 0:
        raise RuntimeError("be_list failed:  %s" % const.BE_ERRNO_MAP[err])

    # dereference both pointers
    node = be_node_list.contents.contents

    name_list = [
        (node.be_node_name,
         node.be_rpool,
         node.be_root_ds,
         node.be_active == True
        )
    ]
    while node.be_next_node:
        node = node.be_next_node.contents
        name_list.append(
            (node.be_node_name,
             node.be_rpool,
             node.be_root_ds,
             node.be_active == True
            )
        )

    # free the memory used by be_list
    cfunc.be_free_list(be_node_list.contents)

    return name_list


def be_init(new_be_name, new_be_pool, zfs_properties=None, nested_be=False,
        fs_list=None, fs_zfs_properties=None,
        shared_fs_list=None, shared_fs_zfs_properties=None,
        allow_auto_naming=True):
    """ be_init() - function to initialize a new BE layout.  Creates default
    zfs datasets as well.

    new_be_name - name for the new BE
    new_be_pool - pool to use for the BE layout
    zfs_properties - Options object representing properties applicable to the
                     BE's root dataset.
    nested_be - flag to specify if we're initializing a nested BE.
    fs_list - list of paths to convert to datasets within the BE.
    fs_zfs_properties - list of Options objects containing property settings
    shared_fs_list - list of paths to convert to datasets in the shared area.
    shared_fs_zfs_properties - list of Options objects containing property
                               settings
    allow_auto_naming - Ensures BE created will have a uniquely generated name.

    Returns - for BE's with allow_auto_naming enabled, the created name of the
              BE if different from the BE's original name. None otherwise.
    """
    # create a new NVList object
    nvlist = nvl.NVList()

    # Add BE name and pool.
    nvlist.add_string(const.BE_ATTR_NEW_BE_NAME, new_be_name)
    nvlist.add_string(const.BE_ATTR_NEW_BE_POOL, new_be_pool)

    # If zfs properties are provided for the BE, add them (these apply to
    # the root dataset of the BE.)
    if zfs_properties is not None:
        prop_nvlist = zfs_properties.get_nvlist()
        nvlist.add_nvlist(const.BE_ATTR_ZFS_PROPERTIES, prop_nvlist)

    # Add whether or not we're initializing a nested BE.
    nvlist.add_boolean_value(const.BE_ATTR_NEW_BE_NESTED_BE, nested_be)

    # Add whether or not to generate a unique BE name
    nvlist.add_boolean_value(const.BE_ATTR_NEW_BE_ALLOW_AUTO_NAMING,
        allow_auto_naming)

    # Add the BE datasets
    if fs_list is not None and len(fs_list) > 0:
        nvlist.add_uint16(const.BE_ATTR_FS_NUM, len(fs_list))
        nvlist.add_string_array(const.BE_ATTR_FS_NAMES, fs_list)

        if fs_zfs_properties is not None and len(fs_zfs_properties) > 0:
            fs_zfs_prop_array = list()
            for props in fs_zfs_properties:
                if props is not None:
                    prop_nvlist = props.get_nvlist()
                else:
                    prop_nvlist = nvl.NVList()
                fs_zfs_prop_array.append(prop_nvlist)
            nvlist.add_nvlist_array(const.BE_ATTR_FS_ZFS_PROPERTIES,
                                    fs_zfs_prop_array)

    # Add the shared datasets
    if shared_fs_list is not None and len(shared_fs_list) > 0:
        nvlist.add_uint16(const.BE_ATTR_SHARED_FS_NUM, len(shared_fs_list))
        nvlist.add_string_array(const.BE_ATTR_SHARED_FS_NAMES, shared_fs_list)

        if shared_fs_zfs_properties is not None and \
            len(shared_fs_zfs_properties) > 0:
            shared_fs_zfs_prop_array = list()
            for props in shared_fs_zfs_properties:
                if props is not None:
                    prop_nvlist = props.get_nvlist()
                else:
                    prop_nvlist = nvl.NVList()
                shared_fs_zfs_prop_array.append(prop_nvlist)
            nvlist.add_nvlist_array(const.BE_ATTR_SHARED_FS_ZFS_PROPERTIES,
                                    shared_fs_zfs_prop_array)

    # pylint: disable-msg=E1101
    err = cfunc.be_init(nvlist)
    if err != 0:
        raise RuntimeError("be_init failed:  %s" % const.BE_ERRNO_MAP[err])

    # If auto-naming is allowed, the initialized BE might have been created
    # with a different name than requested (it was auto named to something
    # else). If so, return new name.
    if allow_auto_naming:
        created_be_name = nvlist.lookup_string(const.BE_ATTR_NEW_BE_NAME)
        if (created_be_name != new_be_name):
            return created_be_name

    return None


def be_destroy(be_name):
    """ be_destroy() - function to destroy a BE

    be_name - BE to destroy
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    # pylint: disable-msg=E1101
    err = cfunc.be_destroy(nvlist)
    if err != 0:
        raise RuntimeError("be_destroy failed:  %s" % const.BE_ERRNO_MAP[err])


def be_activate(be_name):
    """ be_activate() - function to activate a BE

    be_name - BE to activate
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    # pylint: disable-msg=E1101
    err = cfunc.be_activate(nvlist)
    if err != 0:
        raise RuntimeError("be_activate failed:  %s" % const.BE_ERRNO_MAP[err])


def be_mount(be_name, mountpoint, altpool=None):
    """ be_mount() - function to mount a BE

    be_name - BE to mount
    mounpoint - where to mount the BE
    altpool - alternate pool area from which to find the BE
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    nvlist.add_string(const.BE_ATTR_MOUNTPOINT, mountpoint)
    if altpool is not None:
        nvlist.add_string(const.BE_ATTR_ALT_POOL, altpool)
    nvlist.add_uint16(const.BE_ATTR_MOUNT_FLAGS, 0)
    # pylint: disable-msg=E1101
    err = cfunc.be_mount(nvlist)
    if err != 0:
        raise RuntimeError("be_mount failed:  %s" % const.BE_ERRNO_MAP[err])


def be_unmount(be_name, altpool=None):
    """ be_unmount() - function to unmount a BE

    be_name - BE to unmount
    altpool - alternate pool area from which to find the BE
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    if altpool is not None:
        nvlist.add_string(const.BE_ATTR_ALT_POOL, altpool)
    # pylint: disable-msg=E1101
    err = cfunc.be_unmount(nvlist)
    if err != 0:
        raise RuntimeError("be_unmount failed:  %s" % const.BE_ERRNO_MAP[err])


def be_create_snapshot(be_name, snapshot_name, altpool=None):
    """ be_create_snapshot() - function to create a snapshot of the BE

    be_name - BE to snapshot
    snapshot_name - name of the snapshot to create
    altpool - alternate pool area from which to find the BE
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    nvlist.add_string(const.BE_ATTR_SNAP_NAME, snapshot_name)
    if altpool is not None:
        nvlist.add_string(const.BE_ATTR_ALT_POOL, altpool)
    # pylint: disable-msg=E1101
    err = cfunc.be_create_snapshot(nvlist)
    if err != 0:
        raise RuntimeError("be_create_snapshot failed:  %s"
                            % const.BE_ERRNO_MAP[err])

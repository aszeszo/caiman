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


def be_create(new_be_name=None, new_be_pool=None, fs_list=const.ZFS_FS_NAMES):
    """ be_create() - function to create a new BE layout.  Creates default zfs
    datasets as well.

    new_be_name - optional name for the new BE
    new_be_pool - optional pool to use for the BE layout
    fs_list - list of paths to convert to datasets within the BE.
    """
    # create a new NVList object
    nvlist = nvl.NVList()

    if new_be_name is not None:
        nvlist.add_string(const.BE_ATTR_NEW_BE_NAME, new_be_name)

    if new_be_pool is not None:
        nvlist.add_string(const.BE_ATTR_NEW_BE_POOL, new_be_pool)

    # add the BE datasets
    nvlist.add_uint16(const.BE_ATTR_FS_NUM, len(fs_list))
    nvlist.add_string_array(const.BE_ATTR_FS_NAMES, fs_list)
    nvlist.add_uint16(const.BE_ATTR_SHARED_FS_NUM,
        len(const.ZFS_SHARED_FS_NAMES))
    nvlist.add_string_array(const.BE_ATTR_SHARED_FS_NAMES,
        const.ZFS_SHARED_FS_NAMES)

    # pylint: disable-msg=E1101
    err = cfunc.be_init(nvlist)
    if err != 0:
        raise RuntimeError("be_create failed:  %s" % const.BE_ERRNO_MAP[err])


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


def be_mount(be_name, mountpoint):
    """ be_mount() - function to mount a BE

    be_name - BE to mount
    mounpoint - where to mount the BE
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    nvlist.add_string(const.BE_ATTR_MOUNTPOINT, mountpoint)
    nvlist.add_uint16(const.BE_ATTR_MOUNT_FLAGS, 0)
    # pylint: disable-msg=E1101
    err = cfunc.be_mount(nvlist)
    if err != 0:
        raise RuntimeError("be_mount failed:  %s" % const.BE_ERRNO_MAP[err])


def be_unmount(be_name):
    """ be_unmount() - function to unmount a BE

    be_name - BE to unmount
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    # pylint: disable-msg=E1101
    err = cfunc.be_unmount(nvlist)
    if err != 0:
        raise RuntimeError("be_unmount failed:  %s" % const.BE_ERRNO_MAP[err])


def be_create_snapshot(be_name, snapshot_name):
    """ be_create_snapshot() - function to create a snapshot of the BE

    be_name - BE to snapshot
    snapshot_name - name of the snapshot to create
    """
    # create a new NVList object
    nvlist = nvl.NVList()
    nvlist.add_string(const.BE_ATTR_ORIG_BE_NAME, be_name)
    nvlist.add_string(const.BE_ATTR_SNAP_NAME, snapshot_name)
    # pylint: disable-msg=E1101
    err = cfunc.be_create_snapshot(nvlist)
    if err != 0:
        raise RuntimeError("be_create_snapshot failed:  %s"
                            % const.BE_ERRNO_MAP[err])

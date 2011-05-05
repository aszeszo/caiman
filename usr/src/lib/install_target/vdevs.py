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
""" vdevs.py - private interface to /usr/lib/libzfs.so to retreive vdev
information from a given zpool.
"""
import ctypes as C

from solaris_install.target.libnvpair.cstruct import nvlistp
from solaris_install.target.libnvpair import nvl

# ctypes handle to libzfs.so
_LIBZFS = C.CDLL("/usr/lib/libzfs.so", use_errno=True)


# define an empty structure and pointer to use as return and argument types for
# libzfs functions.
# This is done because we are not interested in any particular element from the
# structure.  libzfs operates entirely on pointers to structures and Python's
# ctypes module assumes c_int() datatypes for anything not defined.
class NotUsed(C.Structure):
    pass
NotUsedp = C.POINTER(NotUsed)

# define mappings for needed libzfs functions
libzfs_init = _LIBZFS.libzfs_init
libzfs_init.restype = NotUsedp
libzfs_init.argstypes = None

zpool_open = _LIBZFS.zpool_open
zpool_open.restype = NotUsedp
zpool_open.argtypes = (NotUsedp, C.c_char_p)

# set the return type to NVList so we can easily traverse it
zpool_get_config = _LIBZFS.zpool_get_config
zpool_get_config.restype = nvl.NVList
zpool_get_config.argtypes = (NotUsedp, C.POINTER(nvlistp))

zpool_close = _LIBZFS.zpool_close
zpool_close.restype = None
zpool_close.argtypes = (NotUsedp,)

libzfs_fini = _LIBZFS.libzfs_fini
libzfs_fini.restype = None
libzfs_fini.argtypes = (NotUsedp,)

# NVList keys
SPARES = ("spares", "DATA_TYPE_NVLIST_ARRAY")
CACHE = ("l2cache", "DATA_TYPE_NVLIST_ARRAY")
CHILDREN = ("children", "DATA_TYPE_NVLIST_ARRAY")
IS_LOG = ("is_log", "DATA_TYPE_UINT64")


def traverse(vdev_map, child_list, vdev_label):
    """ traverse() - recursive function to update the vdev_dict as
    each vdev_tree is analyzed for children

    vdev_map - dictionary containing vdev mappings
    child_list - nvlist array of children from a vdev_tree nvlist
    vdev_label - vdev redundancy type to map the children to
    """
    for child in child_list:
        # look to see if this child has children of its own
        if CHILDREN in child:
            child_type = child.lookup_string("type")
            child_id = child.lookup_uint64("id")
            vdev_label = "%s-%d" % (child_type, child_id)

            traverse(vdev_map, child.lookup_nvlist_array("children"),
                     vdev_label)
        else:
            # look for is_log.  If it's a logging vdev, override the label
            if IS_LOG in child:
                if child.lookup_uint64("is_log") == 1:
                    vdev_label = "logs"

            vdev_map.setdefault(vdev_label, []).append(
                child.lookup_string("path"))


def _get_vdev_mapping(pool):
    """ _get_vdev_mapping() - private function to interface with libzfs.so for
    retrevial of vdev information

    pool - name of the zpool to access
    """
    # vdev mapping dictionary
    vdev_map = dict()

    # create a global libzfs handle
    g_zfs = libzfs_init()
    if g_zfs is None:
        return vdev_map

    try:
        # open the zpool and get the zpool configuration
        zpool_handle = zpool_open(g_zfs, pool)
        if zpool_handle is None:
            return vdev_map

        try:
            zpool_config = zpool_get_config(zpool_handle, None)
            root_vdev_tree = zpool_config.lookup_nvlist("vdev_tree")

            # check for spare vdevs
            if SPARES in root_vdev_tree:
                spares_list = root_vdev_tree.lookup_nvlist_array("spares")
                for spare in spares_list:
                    vdev_map.setdefault("spare", []).append(
                        spare.lookup_string("path"))

            # check for cache vdevs
            if CACHE in root_vdev_tree:
                cache_list = root_vdev_tree.lookup_nvlist_array("l2cache")
                for cache in cache_list:
                    vdev_map.setdefault("cache", []).append(
                        cache.lookup_string("path"))

            # traverse the children
            traverse(vdev_map, root_vdev_tree.lookup_nvlist_array("children"),
                     "none")

        finally:
            # close the zpool handle
            zpool_close(zpool_handle)

    finally:
        # close the global handle
        libzfs_fini(g_zfs)

    return vdev_map

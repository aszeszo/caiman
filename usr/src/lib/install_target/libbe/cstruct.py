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


class BEDatasetList(C.Structure):
    """ struct be_dataset_list_t from /usr/include/libbe.h
    """
    # due to the forward declaration of *be_next_dataset, _fields_ is populated
    # later
    pass

BEDatasetListp = C.POINTER(BEDatasetList)

BEDatasetList._fields_ = [
    ("be_ds_space_used", C.c_uint64),
    ("be_ds_mounted", C.c_int),
    ("be_dataset_name", C.c_char_p),
    ("be_ds_creation", C.c_long),  # Date/timestamp when created (time_t)
    ("be_ds_mntpt", C.c_char_p),
    ("be_ds_plcy_type", C.c_char_p),  # cleanup policy type
    ("be_next_dataset", BEDatasetListp)
]


class BESnapshotList(C.Structure):
    """ struct be_snapshot_list_t from /usr/include/libbe.h
    """
    # due to the forward declaration of *be_next_snapshot, _fields_ is
    # populated later
    pass

BESnapshotListp = C.POINTER(BESnapshotList)

BESnapshotList._fields_ = [
    ("be_snapshot_space_used", C.c_uint64),  # bytes of disk space used
    ("be_snapshot_name", C.c_char_p),
    ("be_snapshot_creation", C.c_long),  # Date/timestamp when created (time_t)
    ("be_snapshot_type", C.c_char_p),  # cleanup policy type
    ("be_next_snapshot", BESnapshotListp)
]


class BENodeList(C.Structure):
    """ struct be_node_list_t from /usr/include/libbe.h
    """
    # due to the forward declaration of *be_next_node, _fields_ is
    # populated later
    pass

BENodeListp = C.POINTER(BENodeList)

BENodeList._fields_ = [
    ("be_mounted", C.c_int),  # is BE currently mounted
    ("be_active_on_boot", C.c_int),  # is this BE active on boot
    ("be_active", C.c_int),  # is this BE active currently
    ("be_active_unbootable", C.c_int),  # is this BE potentially bootable
    ("be_space_used", C.c_uint64),
    ("be_node_name", C.c_char_p),
    ("be_rpool", C.c_char_p),
    ("be_root_ds", C.c_char_p),
    ("be_mntpt", C.c_char_p),
    ("be_policy_type", C.c_char_p),  # cleanup policy type
    ("be_uuid_str", C.c_char_p),  # string representation of uuid
    ("be_node_creation", C.c_long),  # Date/timestamp when created (time_t)
    ("be_node_datasets", BEDatasetListp),
    ("be_node_num_datasets", C.c_uint),
    ("be_node_snapshots", BESnapshotListp),
    ("be_node_num_snapshots", C.c_uint),
    ("be_next_node", BENodeListp)
]

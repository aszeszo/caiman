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
""" constants and enums from libnvpair.h
"""

NV_VERSION          = 0 # nvl implementation version

NV_ENCODE_NATIVE    = 0 # nvlist pack encoding
NV_ENCODE_XDR       = 1

NV_UNIQUE_NAME      = 0x1 # nvlist persistent unique name flags
NV_UNIQUE_NAME_TYPE = 0x2 # stored in nvl_nvflag

NV_FLAG_NOENTOK     = 0x1 # nvlist lookup pairs related flags

DATA_TYPE = ( \
    DATA_TYPE_UNKNOWN,
    DATA_TYPE_BOOLEAN,
    DATA_TYPE_BYTE,
    DATA_TYPE_INT16,
    DATA_TYPE_UINT16,
    DATA_TYPE_INT32,
    DATA_TYPE_UINT32,
    DATA_TYPE_INT64,
    DATA_TYPE_UINT64,
    DATA_TYPE_STRING,
    DATA_TYPE_BYTE_ARRAY,
    DATA_TYPE_INT16_ARRAY,
    DATA_TYPE_UINT16_ARRAY,
    DATA_TYPE_INT32_ARRAY,
    DATA_TYPE_UINT32_ARRAY,
    DATA_TYPE_INT64_ARRAY,
    DATA_TYPE_UINT64_ARRAY,
    DATA_TYPE_STRING_ARRAY,
    DATA_TYPE_HRTIME,
    DATA_TYPE_NVLIST,
    DATA_TYPE_NVLIST_ARRAY,
    DATA_TYPE_BOOLEAN_VALUE,
    DATA_TYPE_INT8,
    DATA_TYPE_UINT8,
    DATA_TYPE_BOOLEAN_ARRAY,
    DATA_TYPE_INT8_ARRAY,
    DATA_TYPE_UINT8_ARRAY,
    DATA_TYPE_DOUBLE,
) = xrange(28)

DATA_TYPE_MAP = {
    DATA_TYPE_UNKNOWN:        "DATA_TYPE_UNKNOWN",
    DATA_TYPE_BOOLEAN:        "DATA_TYPE_BOOLEAN",
    DATA_TYPE_BYTE:           "DATA_TYPE_BYTE",
    DATA_TYPE_INT16:          "DATA_TYPE_INT16",
    DATA_TYPE_UINT16:         "DATA_TYPE_UINT16",
    DATA_TYPE_INT32:          "DATA_TYPE_INT32",
    DATA_TYPE_UINT32:         "DATA_TYPE_UINT32",
    DATA_TYPE_INT64:          "DATA_TYPE_INT64",
    DATA_TYPE_UINT64:         "DATA_TYPE_UINT64",
    DATA_TYPE_STRING:         "DATA_TYPE_STRING",
    DATA_TYPE_BYTE_ARRAY:     "DATA_TYPE_BYTE_ARRAY",
    DATA_TYPE_INT16_ARRAY:    "DATA_TYPE_INT16_ARRAY",
    DATA_TYPE_UINT16_ARRAY:   "DATA_TYPE_UINT16_ARRAY",
    DATA_TYPE_INT32_ARRAY:    "DATA_TYPE_INT32_ARRAY",
    DATA_TYPE_UINT32_ARRAY:   "DATA_TYPE_UINT32_ARRAY",
    DATA_TYPE_INT64_ARRAY:    "DATA_TYPE_INT64_ARRAY",
    DATA_TYPE_UINT64_ARRAY:   "DATA_TYPE_UINT64_ARRAY",
    DATA_TYPE_STRING_ARRAY:   "DATA_TYPE_STRING_ARRAY",
    DATA_TYPE_HRTIME:         "DATA_TYPE_HRTIME",
    DATA_TYPE_NVLIST:         "DATA_TYPE_NVLIST",
    DATA_TYPE_NVLIST_ARRAY:   "DATA_TYPE_NVLIST_ARRAY",
    DATA_TYPE_BOOLEAN_VALUE:  "DATA_TYPE_BOOLEAN_VALUE",
    DATA_TYPE_INT8:           "DATA_TYPE_INT8",
    DATA_TYPE_UINT8:          "DATA_TYPE_UINT8",
    DATA_TYPE_BOOLEAN_ARRAY:  "DATA_TYPE_BOOLEAN_ARRAY",
    DATA_TYPE_INT8_ARRAY:     "DATA_TYPE_INT8_ARRAY",
    DATA_TYPE_UINT8_ARRAY:    "DATA_TYPE_UINT8_ARRAY",
    DATA_TYPE_DOUBLE:         "DATA_TYPE_DOUBLE",
    "DATA_TYPE_UNKNOWN":       DATA_TYPE_UNKNOWN,
    "DATA_TYPE_BOOLEAN":       DATA_TYPE_BOOLEAN,
    "DATA_TYPE_BYTE":          DATA_TYPE_BYTE,
    "DATA_TYPE_INT16":         DATA_TYPE_INT16,
    "DATA_TYPE_UINT16":        DATA_TYPE_UINT16,
    "DATA_TYPE_INT32":         DATA_TYPE_INT32,
    "DATA_TYPE_UINT32":        DATA_TYPE_UINT32,
    "DATA_TYPE_INT64":         DATA_TYPE_INT64,
    "DATA_TYPE_UINT64":        DATA_TYPE_UINT64,
    "DATA_TYPE_STRING":        DATA_TYPE_STRING,
    "DATA_TYPE_BYTE_ARRAY":    DATA_TYPE_BYTE_ARRAY,
    "DATA_TYPE_INT16_ARRAY":   DATA_TYPE_INT16_ARRAY,
    "DATA_TYPE_UINT16_ARRAY":  DATA_TYPE_UINT16_ARRAY,
    "DATA_TYPE_INT32_ARRAY":   DATA_TYPE_INT32_ARRAY,
    "DATA_TYPE_UINT32_ARRAY":  DATA_TYPE_UINT32_ARRAY,
    "DATA_TYPE_INT64_ARRAY":   DATA_TYPE_INT64_ARRAY,
    "DATA_TYPE_UINT64_ARRAY":  DATA_TYPE_UINT64_ARRAY,
    "DATA_TYPE_STRING_ARRAY":  DATA_TYPE_STRING_ARRAY,
    "DATA_TYPE_HRTIME":        DATA_TYPE_HRTIME,
    "DATA_TYPE_NVLIST":        DATA_TYPE_NVLIST,
    "DATA_TYPE_NVLIST_ARRAY":  DATA_TYPE_NVLIST_ARRAY,
    "DATA_TYPE_BOOLEAN_VALUE": DATA_TYPE_BOOLEAN_VALUE,
    "DATA_TYPE_INT8":          DATA_TYPE_INT8,
    "DATA_TYPE_UINT8":         DATA_TYPE_UINT8,
    "DATA_TYPE_BOOLEAN_ARRAY": DATA_TYPE_BOOLEAN_ARRAY,
    "DATA_TYPE_INT8_ARRAY":    DATA_TYPE_INT8_ARRAY,
    "DATA_TYPE_UINT8_ARRAY":   DATA_TYPE_UINT8_ARRAY,
    "DATA_TYPE_DOUBLE":        DATA_TYPE_DOUBLE,
}

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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#
""" C structures from libima.so
"""

import ctypes as C

from solaris_install.target.libima import const


class IMA_OID(C.Structure):
    """ IMA_OID struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("objectType", C.c_int),
        ("ownerId", C.c_uint),
        ("objectSequenceNumber", C.c_uint64)
    ]


class IMA_OID_LIST(C.Structure):
    """ IMA_OID_LIST struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("oidCount", C.c_uint),
        ("oids", IMA_OID * 1)
    ]


class IMA_CHAP_INITIATOR_AUTHPARMS(C.Structure):
    """ IMA_CHAP_INITIATOR_AUTHPARMS struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("retries", C.c_uint),
        ("name", C.c_byte * 512),
        ("nameLength", C.c_uint),
        ("minValueLength", C.c_uint),
        ("maxValueLength", C.c_uint),
        ("challengeSecret", C.c_byte * 256),
        ("challengeSecretLength", C.c_uint),
        ("reserved", C.c_ubyte * 512)
    ]


class IMA_SRP_INITIATOR_AUTHPARMS(C.Structure):
    """ IMA_SRP_INITIATOR_AUTHPARMS struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("userName", C.c_byte * 512),
        ("userNameLength", C.c_uint),
        ("reserved", C.c_ubyte * 512)
    ]


class IMA_KRB5_INITIATOR_AUTHPARMS(C.Structure):
    """ IMA_KRB5_INITIATOR_AUTHPARMS struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("clientKey", C.c_byte * 1024),
        ("clientKeyLength", C.c_uint),
        ("reserved", C.c_byte * 2048)
    ]


class IMA_SPKM_INITIATOR_AUTHPARMS(C.Structure):
    """ IMA_SPKM_INITIATOR_AUTHPARMS struct definition from /usr/include/ima.h
    """

    _fields_ = [
        ("privateKey", C.c_byte * 4096),
        ("privateKeyLength", C.c_uint),
        ("publicKey", C.c_byte * 4096),
        ("publicKeyLength", C.c_uint),
        ("reserved", C.c_byte * 4096)
    ]


class IMA_INITIATOR_AUTHPARMS(C.Union):
    """ IMA_INITIATOR_AUTHPARMS union definition from /usr/include/ima.h
    """

    _fields_ = [
        ("chapParms", IMA_CHAP_INITIATOR_AUTHPARMS),
        ("srpParms", IMA_SRP_INITIATOR_AUTHPARMS),
        ("kerberosParms", IMA_KRB5_INITIATOR_AUTHPARMS),
        ("skpmParms", IMA_SPKM_INITIATOR_AUTHPARMS)
    ]


class NodeName(C.Structure):
    """ node_name_t structure definition from
    uts/common/sys/scsi/adapaters/iscsi_if.h
    """

    _fields_ = [
        ("n_name", C.c_ubyte * const.ISCSI_MAX_NAME_LEN),
        ("n_len", C.c_int)
    ]


class IscsiAuthProps(C.Structure):
    """ iscsi_auth_props_t structure definition from
    uts/common/sys/scsi/adapaters/iscsi_if.h
    """

    _fields_ = [
        ("a_vers", C.c_uint32),
        ("a_oid", C.c_uint32),
        ("a_bi_auth", C.c_int),
        ("a_auth_method", C.c_int)
    ]


class ChapProps(C.Structure):
    """ iscsi_chap_props_t structure definition from
    uts/common/sys/scsi/adapaters/iscsi_if.h
    """

    _fields_ = [
        ("c_vers", C.c_uint32),
        ("c_retries", C.c_uint32),
        ("c_oid", C.c_uint32),
        ("c_user", C.c_ubyte * const.ISCSI_MAX_C_USER_LEN),
        ("c_user_len", C.c_uint32),
        ("c_secret", C.c_ubyte * 16),
        ("c_secret_len", C.c_uint32)
    ]


class IscsiBootProperty(C.Structure):
    """ iscsi_boot_property_t structure definition from
    uts/common/sys/scsi/adapaters/iscsi_if.h
    """

    _fields_ = [
        ("ini_name", NodeName),
        ("tgt_name", NodeName),
        ("auth", IscsiAuthProps),
        ("ini_chap", ChapProps),
        ("tgt_chap", ChapProps),
        ("iscsiboot", C.c_int),
        ("hba_mpxio_enabled", C.c_int)
    ]

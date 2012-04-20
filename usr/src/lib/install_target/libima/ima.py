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
""" ctypes wrapper for libima.so
"""

import ctypes as C
import fcntl
import os

from solaris_install.target.libima import cfunc, const, cstruct


def set_chap_password(chap_password):
    """ function to set the initiator CHAP password.
    """

    oid_list_p = C.POINTER(cstruct.IMA_OID_LIST)()
    try:
        status = cfunc.IMA_GetLhbaOidList(C.byref(oid_list_p))
        if status != 0:
            raise RuntimeError("IMA_GetLhbaOidList failed")
        if oid_list_p.contents.oidCount != 1:
            raise RuntimeError("More than one HBA in system")

        auth_params = cstruct.IMA_INITIATOR_AUTHPARMS()
        status = cfunc.IMA_GetInitiatorAuthParms(oid_list_p.contents.oids[0],
            const.IMA_AUTHMETHOD_MAP["IMA_AUTHMETHOD_CHAP"],
            C.byref(auth_params))
        if status != 0:
            raise RuntimeError("IMA_GetInitiatorAuthParms failed")

        chap_len = len(chap_password)
        for i in range(chap_len):
            auth_params.chapParms.challengeSecret[i] = ord(chap_password[i])
        auth_params.chapParms.challengeSecretLength = chap_len

        status = cfunc.IMA_SetInitiatorAuthParms(oid_list_p.contents.oids[0],
            const.IMA_AUTHMETHOD_MAP["IMA_AUTHMETHOD_CHAP"],
            C.byref(auth_params))
        if status != 0:
            raise RuntimeError("IMA_SetInitiatorAuthParms failed")
    finally:
        # always free the the oid_list pointer
        cfunc.IMA_FreeMemory(oid_list_p)


def is_iscsiboot():
    """ Python version of SUN_IMA_GetBootIscsi() from
    $SRC/cmd/iscsiadm/sun_ima.c
    """

    fd = None
    try:
        fd = os.open("/devices/iscsi:devctl", os.O_RDONLY)
        buf = cstruct.IscsiBootProperty()
        try:
            fcntl.ioctl(fd, const.ISCSI_BOOTPROP_GET, C.addressof(buf))
        except IOError:
            return False
        else:
            return bool(buf.iscsiboot)
    finally:
        if fd is not None:
            os.close(fd)

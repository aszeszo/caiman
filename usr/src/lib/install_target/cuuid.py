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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
""" C structures from libefi.so and libefi.h
"""

import ctypes as C
import struct
import sys
from uuid import UUID

#
# A UUID is just 16 bytes, and the module uuid has them as well.
# Unfortunately they didn't make theirs inherit from C.Structure so it is not
# directly usable with ctypes.
#
# Additionally the python uuid.UUID always stores the UUID in big-endian.
# This makes it easier to map to a string. But our libefi.so uses the C macro
# UUID_LE_CONVERT but always stores UUIDs in systems native byte order.
# Therefore cUUID will internally store its bytes as native too, but will
# always display as Little Endian.
#
# This code is intended to be as compatible as possible with uuid.UUID
#


class cUUID(C.Structure):
    """ struct uuid from /usr/include/sys/uuid.h
    """
    # Note we change field names that conflict with properties by
    # prefixing with an '_'.
    _fields_ = [
        ("_time_low",                 C.c_uint32),
        ("_time_mid",                 C.c_uint16),
        ("time_hi_and_version",       C.c_uint16),
        ("clock_seq_hi_and_reserved", C.c_uint8),
        ("_clock_seq_low",            C.c_uint8),
        ("node_addr",                 C.c_uint8 * 6)
    ]

    def __init__(self, hex=None, bytes=None, bytes_le=None, fields=None,
                       int=None):
        """Create a UUID for C from either a string of 32 hexadecimal digits,
        a string of 16 bytes as the 'bytes' argument, a string of 16 bytes
        in little-endian order as the 'bytes_le' argument, a tuple of six
        integers (32-bit time_low, 16-bit time_mid, 16-bit time_hi_version,
        8-bit clock_seq_hi_variant, 8-bit clock_seq_low, 48-bit node) as
        the 'fields' argument, or a single 128-bit integer as the 'int'
        argument.

        Basically just like uuid.UUID(). These expressions all yield the
        same cUUID:

        cUUID('{12345678-1234-5678-1234-567812345678}')
        cUUID('12345678123456781234567812345678')
        cUUID('urn:uuid:12345678-1234-5678-1234-567812345678')
        cUUID(bytes='\x12\x34\x56\x78'*4)
        cUUID(bytes_le='\x78\x56\x34\x12\x34\x12\x78\x56' +
                       '\x12\x34\x56\x78\x12\x34\x56\x78')
        cUUID(fields=(0x12345678, 0x1234, 0x5678, 0x12, 0x34, 0x567812345678))
        cUUID(int=0x12345678123456781234567812345678)
        """
        u = UUID(hex=hex, bytes=bytes, bytes_le=bytes_le, fields=fields,
                 int=int)

        # if that worked we can grab its bytes and put it into the cstructure.
        if sys.byteorder == "little":
            C.memmove(C.addressof(self), u.bytes_le, 16)
        else:
            C.memmove(C.addressof(self), u.bytes, 16)

    @property
    def bytes(self):
        """16 bytes of UUID as buffer (big-endian)"""
        native = C.string_at(C.byref(self), 16)
        if sys.byteorder == "big":
            return native
        else:
            return (native[3] + native[2] + native[1] + native[0] +
                    native[5] + native[4] + native[7] + native[6] +
                    native[8:])

    @property
    def bytes_le(self):
        """16 bytes of UUID as buffer (little-endian)"""
        native = C.string_at(C.byref(self), 16)
        if sys.byteorder == "little":
            return native
        else:
            return (native[3] + native[2] + native[1] + native[0] +
                    native[5] + native[4] + native[7] + native[6] +
                    native[8:])

    @property
    def fields(self):
        return (self.time_low, self.time_mid, self.time_hi_version,
                self.clock_seq_hi_variant, self.clock_seq_low, self.node)

    @property
    def time_low(self):
        """closed interval of bytes [0:3] of the UUID (as int)"""
        return self._time_low

    @property
    def time_mid(self):
        """closed interval of bytes [4:5] of the UUID (as int)"""
        return self._time_mid

    @property
    def time_hi_version(self):
        """closed interval of bytes [6:7] of the UUID (as int)"""
        return self.time_hi_and_version

    @property
    def clock_seq_hi_variant(self):
        """byte 8 of the UUID (as int)"""
        return self.clock_seq_hi_and_reserved

    @property
    def clock_seq_low(self):
        """byte 9 of the UUID (as int)"""
        return self._clock_seq_low

    @property
    def node(self):
        """closed interval of bytes [10:15] of the UUID (as long)"""
        x = long(0)
        for idx, shift in zip(range(6), range(40, -8, -8)):
            x |= self.node_addr[idx] << shift
        return x

    @property
    def hex(self):
        """the UUID as a 32-character hexadecimal string"""
        return "%032x" % (self.int)

    @property
    def int(self):
        """the UUID as a 128-bit long"""
        val = long(0)
        byte = self.bytes
        for idx, shift in zip(range(16), range(120, -8, -8)):
            val |= ord(byte[idx]) << shift
        return val

    @property
    def urn(self):
        """the UUID as a URN as specified in RFC 4122"""
        return 'urn:uuid:' + str(self)

    @property
    def time(self):
        """the 60-bit timestamp of the UUID"""
        return (((self.time_hi_version & 0x0fffL) << 48L) |
                (self.time_mid << 32L) | self.time_low)

    @property
    def clock_seq(self):
        """the 14-bit sequence number of the UUID"""
        return (((self.clock_seq_hi_variant & 0x3fL) << 8L) |
                self.clock_seq_low)

    def __cmp__(self, other):
        if isinstance(other, cUUID):
            return cmp(self.int, other.int)
        return NotImplemented  # XXX

    def __hash__(self):
        return hash(self.int)

    def __str__(self):
        hex = "%032x" % (self.int)
        return '%s-%s-%s-%s-%s' % \
               (hex[:8], hex[8:12], hex[12:16], hex[16:20], hex[20:])

    def __repr__(self):
        return 'UUID(%r)' % str(self)


def cUUID2UUID(cuuid):
    """convert cUUID to a uuid.UUID"""
    return UUID(cuuid.urn)


def UUID2cUUID(uuid):
    """convert uuid.UUID to a cUUID"""
    return cUUID(uuid.urn)

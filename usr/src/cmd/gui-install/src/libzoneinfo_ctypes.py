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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
ctypes interfaces to libzoneinfo APIs, as defined in
/usr/include/libzoneinfo.h
'''

import ctypes as C

_LIBZONEINFO = C.CDLL("/usr/lib/libzoneinfo.so", use_errno=True)

_TZBUFLEN = 128
_CCBUFLEN = 32


class TZ_COORD(C.Structure):
    """ struct tz_coord """
    _fields_ = [
        ("lat_sign", C.c_int),
        ("lat_degree", C.c_uint),
        ("lat_minute", C.c_uint),
        ("lat_second", C.c_uint),
        ("long_sign", C.c_int),
        ("long_degree", C.c_uint),
        ("long_minute", C.c_uint),
        ("long_second", C.c_uint)
    ]


class TZ_TIMEZONE(C.Structure):
    """ struct tz_timezone """
    pass

TZ_TIMEZONE._fields_ = [
    ("tz_name", C.c_char * _TZBUFLEN),
    ("tz_oname", C.c_char * _TZBUFLEN),
    ("tz_id_desc", C.c_char_p),
    ("tz_display_desc", C.c_char_p),
    ("tz_coord", TZ_COORD),
    ("tz_next", C.POINTER(TZ_TIMEZONE)),
    ("tz_reserved", C.c_void_p)
]


class TZ_CONTINENT(C.Structure):
    """ struct tz_continent """
    pass

TZ_CONTINENT._fields_ = [
    ("ctnt_name", C.c_char * _TZBUFLEN),
    ("ctnt_id_desc", C.c_char_p),
    ("ctnt_display_desc", C.c_char_p),
    ("ctnt_next", C.POINTER(TZ_CONTINENT)),
    ("ctnt_reserved", C.c_void_p)
]


class TZ_COUNTRY(C.Structure):
    """ struct tz_country from /usr/include/libzoneinfo.h
    """
    pass

TZ_COUNTRY._fields_ = [
    ("ctry_code", C.c_char * _CCBUFLEN),
    ("ctry_id_desc", C.c_char_p),
    ("ctry_display_desc", C.c_char_p),
    ("ctry_status", C.c_int),
    ("ctry_next", C.POINTER(TZ_COUNTRY)),
    ("ctry_reserved", C.c_void_p)
]

libzoneinfo_get_tz_continents = _LIBZONEINFO.get_tz_continents
libzoneinfo_get_tz_continents.restype = C.c_int
libzoneinfo_get_tz_continents.argtypes = [C.POINTER(C.POINTER(TZ_CONTINENT))]

libzoneinfo_get_tz_countries = _LIBZONEINFO.get_tz_countries
libzoneinfo_get_tz_countries.restype = C.c_int
libzoneinfo_get_tz_countries.argtypes = [
    C.POINTER(C.POINTER(TZ_COUNTRY)), C.POINTER(TZ_CONTINENT)]

libzoneinfo_get_timezones_by_country = _LIBZONEINFO.get_timezones_by_country
libzoneinfo_get_timezones_by_country.restype = C.c_int
libzoneinfo_get_timezones_by_country.argtypes = [
    C.POINTER(C.POINTER(TZ_TIMEZONE)), C.POINTER(TZ_COUNTRY)]

libzoneinfo_free_tz_continents = _LIBZONEINFO.free_tz_continents
libzoneinfo_free_tz_continents.restype = C.c_int
libzoneinfo_free_tz_continents.argtypes = [C.POINTER(TZ_CONTINENT)]

libzoneinfo_free_tz_countries = _LIBZONEINFO.free_tz_countries
libzoneinfo_free_tz_countries.restype = C.c_int
libzoneinfo_free_tz_countries.argtypes = [C.POINTER(TZ_COUNTRY)]

libzoneinfo_free_timezones = _LIBZONEINFO.free_timezones
libzoneinfo_free_timezones.restype = C.c_int
libzoneinfo_free_timezones.argtypes = [C.POINTER(TZ_TIMEZONE)]

libzoneinfo_conv_gmt = _LIBZONEINFO.conv_gmt
libzoneinfo_conv_gmt.restype = C.c_char_p
libzoneinfo_conv_gmt.argtypes = [C.c_int, C.c_int]

libzoneinfo_get_system_tz = _LIBZONEINFO.get_system_tz
libzoneinfo_get_system_tz.restype = C.c_char_p
libzoneinfo_get_system_tz.argtypes = [C.c_char_p]

libzoneinfo_set_system_tz = _LIBZONEINFO.set_system_tz
libzoneinfo_set_system_tz.restype = C.c_int
libzoneinfo_set_system_tz.argtypes = [C.c_char_p, C.c_char_p]

libzoneinfo_isvalid_tz = _LIBZONEINFO.isvalid_tz
libzoneinfo_isvalid_tz.restype = C.c_int
libzoneinfo_isvalid_tz.argtypes = [C.c_char_p, C.c_char_p, C.c_int]

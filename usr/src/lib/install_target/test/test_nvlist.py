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
""" Test module for solaris_install.target.libnvpair
"""
import sys
import unittest

from solaris_install.target.libnvpair.const import *
from solaris_install.target.libnvpair.nvl import NVList, NVKey
from solaris_install.target.cgc import CTypesStructureRef


class TestGC(unittest.TestCase):
    """ This is to test that our finalizer gets called.

    If this fails there will be loads of memory leaks...
    """
    GC_REF_COUNT = 0

    def test_nvlist_gc(self):
        """A simple test of cgc on NVListA"""
        # It is perfectly OK to add an extra tracker to nvlist
        nvlist = NVList(NV_UNIQUE_NAME)
        TestGC.GC_REF_COUNT += 1

        def verify(nvlist):
            """a custom finalizer that shows the NVList was freed"""
            TestGC.GC_REF_COUNT -= 1

        CTypesStructureRef(nvlist, verify)

        # remove from namespace, it should be collected now
        del nvlist
        self.assertEqual(TestGC.GC_REF_COUNT, 0)


class TestNVLBase(unittest.TestCase):
    """Base class for tests that creates a p_nvlist to use to test"""
    def setUp(self):
        """run setup code, creating nvlist to use in tests"""
        self.nvlist = NVList(NV_UNIQUE_NAME)

    def tearDown(self):
        """run teardown code"""
        self.nvlist = None


class GoodScalarValues(TestNVLBase):
    """Class to verify good boundary values work with nvlist
    While Python doesn't size integers (well int vs. long) C does.

    Use the collections.MutableMap interface, that is dictionary
    access. This tests the individual add_*() and lookup_*()
    methods as well as the __getitem__() __setitem__() methods.
    """

    def _set_get_helper(self, key, value):
        """test assigning min/max values to datatype"""
        # Set
        try:
            self.nvlist[key] = value
        except Exception, err:
            self.fail("unable to set %s = %s\n%s" % (key, str(value), err))

        # Get
        self.assertEqual(self.nvlist[key], value)

        # remove from the list
        del self.nvlist[key]

    def test_boolean(self):
        """verify we can set boolean (this one is True by existence)"""
        kmin = NVKey("good min boolean", DATA_TYPE_BOOLEAN)
        kmax = NVKey("good max boolean", DATA_TYPE_BOOLEAN)
        vmin = False
        vmax = True
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_boolean_value(self):
        """verify good boundary values for datatype boolean value"""
        # OK Boolean isn't exactly integer but it has very specific
        # good/bad values.
        kmin = NVKey("good min boolean value", DATA_TYPE_BOOLEAN_VALUE)
        kmax = NVKey("good max boolean value", DATA_TYPE_BOOLEAN_VALUE)
        vmin = False
        vmax = True
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_byte(self):
        """verify good boundary values for datatype byte"""
        kmin = NVKey("good min byte", DATA_TYPE_BYTE)
        kmax = NVKey("good max byte", DATA_TYPE_BYTE)
        vmin = 0
        vmax = 2 ** 8 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_int8(self):
        """verify good boundary values for datatype int8"""
        kmin = NVKey("good min int8", DATA_TYPE_INT8)
        kmax = NVKey("good max int8", DATA_TYPE_INT8)
        vmin = -(2 ** 7)
        vmax = 2 ** 7 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_uint8(self):
        """verify good boundary values for datatype uint8"""
        kmin = NVKey("good min uint8", DATA_TYPE_UINT8)
        kmax = NVKey("good max uint8", DATA_TYPE_UINT8)
        vmin = 0
        vmax = 2 ** 8 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_int16(self):
        """verify good boundary values for datatype int16"""
        kmin = NVKey("good min int16", DATA_TYPE_INT16)
        kmax = NVKey("good max int16", DATA_TYPE_INT16)
        vmin = -(2 ** 15)
        vmax = 2 ** 15 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_uint16(self):
        """verify good boundary values for datatype uint16"""
        kmin = NVKey("good min uint16", DATA_TYPE_UINT16)
        kmax = NVKey("good max uint16", DATA_TYPE_UINT16)
        vmin = 0
        vmax = 2 ** 16 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_int32(self):
        """verify good boundary values for datatype int32"""
        kmin = NVKey("good min int32", DATA_TYPE_INT32)
        kmax = NVKey("good max int32", DATA_TYPE_INT32)
        vmin = -(2 ** 31)
        vmax = 2 ** 31 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_uint32(self):
        """verify good boundary values for datatype uint32"""
        kmin = NVKey("good min uint32", DATA_TYPE_UINT32)
        kmax = NVKey("good max uint32", DATA_TYPE_UINT32)
        vmin = 0
        vmax = 2 ** 32 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_int64(self):
        """verify good boundary values for datatype int64"""
        kmin = NVKey("good min int64", DATA_TYPE_INT64)
        kmax = NVKey("good max int64", DATA_TYPE_INT64)
        vmin = -(2 ** 63)
        vmax = 2 ** 63 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_uint64(self):
        """verify good boundary values for datatype uint64"""
        kmin = NVKey("good min uint64", DATA_TYPE_UINT64)
        kmax = NVKey("good max uint64", DATA_TYPE_UINT64)
        vmin = 0
        vmax = 2 ** 64 - 1
        self._set_get_helper(kmin, vmin)
        self._set_get_helper(kmax, vmax)

    def test_string(self):
        """verify good "boundary" values for datatype str"""
        key = NVKey("good string", DATA_TYPE_STRING)
        value = "Hello, World"
        self._set_get_helper(key, value)

    def test_double(self):
        """very good boundary values for datatype double"""
        key = NVKey("good double", DATA_TYPE_DOUBLE)
        value = 1.0 / 2.0
        self._set_get_helper(key, value)


class BadScalarValues(TestNVLBase):
    """Class to verify bad boundary values raise exceptions with nvlist
    """

    # This is more testing cint decorators than the actual interface
    # to libnvpair(3LIB) via ctypes. Because ctypes doesn't verify
    # numeric values are in range we do.

    def _numeric_helper(self, key, value):
        """test the function giving it the values provided plus float and str
        values"""
        try:
            self.nvlist[key] = value
        except ValueError:
            # pass the test
            pass
        else:
            self.fail("%s should have raised ValueError with %d" % \
                      (key, value))

        try:
            # string is not numeric
            self.nvlist[key] = str(value)
            self.fail('%s should have raised ValueError with "%s"' % \
                      (key, str(value)))
        except TypeError:
            # pass the test
            pass

    def test_boolean_value(self):
        """verify bad boundary values for datatype boolean value"""
        key = NVKey("bad boolean value", DATA_TYPE_BOOLEAN_VALUE)
        value = True
        try:
            self.nvlist[key] = str(value)
            self.fail('%s should have raised ValueError with "%s"' % \
                      (key, str(value)))
        except TypeError:
            # pass the test
            pass

    def test_byte(self):
        """verify bad boundary values for datatype byte"""
        kmin = NVKey("bad min byte", DATA_TYPE_BYTE)
        kmax = NVKey("bad max byte", DATA_TYPE_BYTE)
        vmin = -1
        vmax = 2 ** 8
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_int8(self):
        """verify bad boundary values for datatype int8"""
        kmin = NVKey("bad min int8", DATA_TYPE_INT8)
        kmax = NVKey("bad max int8", DATA_TYPE_INT8)
        vmin = -(2 ** 7) - 1
        vmax = 2 ** 7
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_uint8(self):
        """verify bad boundary values for datatype uint8"""
        kmin = NVKey("bad min uint8", DATA_TYPE_UINT8)
        kmax = NVKey("bad max uint8", DATA_TYPE_UINT8)
        vmin = -1
        vmax = 2 ** 8
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_int16(self):
        """verify bad boundary values for datatype int16"""
        kmin = NVKey("bad min int16", DATA_TYPE_INT16)
        kmax = NVKey("bad max int16", DATA_TYPE_INT16)
        vmin = -(2 ** 15) - 1
        vmax = 2 ** 15
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_uint16(self):
        """verify bad boundary values for datatype uint16"""
        kmin = NVKey("bad min uint16", DATA_TYPE_UINT16)
        kmax = NVKey("bad max uint16", DATA_TYPE_UINT16)
        vmin = -1
        vmax = 2 ** 16
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_int32(self):
        """verify bad boundary values for datatype int32"""
        kmin = NVKey("bad min int32", DATA_TYPE_INT32)
        kmax = NVKey("bad max int32", DATA_TYPE_INT32)
        vmin = -(2 ** 31) - 1
        vmax = 2 ** 31
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_uint32(self):
        """verify bad boundary values for datatype uint32"""
        kmin = NVKey("bad min uint32", DATA_TYPE_UINT32)
        kmax = NVKey("bad max uint32", DATA_TYPE_UINT32)
        vmin = -1
        vmax = 2 ** 32
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_int64(self):
        """verify bad boundary values for datatype int64"""
        kmin = NVKey("bad min int64", DATA_TYPE_INT64)
        kmax = NVKey("bad max int64", DATA_TYPE_INT64)
        vmin = -(2 ** 63) - 1
        vmax = 2 ** 63
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_uint64(self):
        """verify bad boundary values for datatype uint64"""
        kmin = NVKey("bad min uint64", DATA_TYPE_UINT64)
        kmax = NVKey("bad max uint64", DATA_TYPE_UINT64)
        vmin = -1
        vmax = 2 ** 64
        self._numeric_helper(kmin, vmin)
        self._numeric_helper(kmax, vmax)

    def test_string(self):
        """verify bad "boundary" values for datatype str"""
        key = NVKey("bad string", DATA_TYPE_STRING)
        # Unicode should fail
        value = u"Hello, World"
        try:
            self.nvlist[key] = value
        except TypeError:
            # pass the test
            pass
        else:
            self.fail('%s should have raised ValueError with "%s"' % \
                      (key, str(value)))

    def test_double(self):
        """verify bad "boundary" values for datatype double"""
        key = NVKey("bad double", DATA_TYPE_DOUBLE)
        value = "a string"
        try:
            self.nvlist[key] = value
        except TypeError:
            # pass the test
            pass
        else:
            self.fail('%s should have raised ValueError with "%s"' % \
                      (key, str(value)))


class GoodArrayValues(TestNVLBase):
    """Class to verify good array values work"""

    # Good array values are arrays of proper datatype.
    # We test array of size 0 (NULL), 1, 2.
    def _int_set_get_helper(self, dtstr, vmin, vmax):
        """
        Try various good array values by making three tuples:
            0 element: tuple()
            1 element: (vmin, )
            2 element: (vmin, vmax)
        """
        keys = (NVKey("empty %s array" % dtstr,     dtstr),
                NVKey("1 element %s array" % dtstr, dtstr),
                NVKey("2 element %s array" % dtstr, dtstr))
        values = (tuple(), (vmin, ), (vmin, vmax))
        for key, value in zip(keys, values):
            # Set
            try:
                self.nvlist[key] = value
            except Exception, err:
                self.fail("unable to set %s = %s\n%s" % (key, str(value), err))

            # Get
            self.assertEqual(self.nvlist[key], value)

            # remove from the list
            del self.nvlist[key]

    def test_boolean_value_array(self):
        """verify good array values for datatype boolean value"""
        dtstr = "DATA_TYPE_BOOLEAN_ARRAY"
        vmin = False
        vmax = True
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_byte_array(self):
        """verify good array values for datatype byte"""
        dtstr = "DATA_TYPE_BYTE_ARRAY"
        vmin = 0
        vmax = 2 ** 8 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_int8_array(self):
        """verify good array values for datatype int8"""
        dtstr = "DATA_TYPE_INT8_ARRAY"
        vmin = -(2 ** 7)
        vmax = 2 ** 7 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_uint8_array(self):
        """verify good array values for datatype uint8"""
        dtstr = "DATA_TYPE_UINT8_ARRAY"
        vmin = 0
        vmax = 2 ** 8 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_int16_array(self):
        """verify good array values for datatype int16"""
        dtstr = "DATA_TYPE_INT16_ARRAY"
        vmin = -(2 ** 15)
        vmax = 2 ** 15 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_uint16_array(self):
        """verify good array values for datatype uint16"""
        dtstr = "DATA_TYPE_UINT16_ARRAY"
        vmin = 0
        vmax = 2 ** 16 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_int32_array(self):
        """verify good array values for datatype int32"""
        dtstr = "DATA_TYPE_INT32_ARRAY"
        vmin = -(2 ** 31)
        vmax = 2 ** 31 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_uint32_array(self):
        """verify good array values for datatype uint32"""
        dtstr = "DATA_TYPE_UINT32_ARRAY"
        vmin = 0
        vmax = 2 ** 32 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_int64_array(self):
        """verify good array values for datatype int64"""
        dtstr = "DATA_TYPE_INT64_ARRAY"
        vmin = -(2 ** 63)
        vmax = 2 ** 63 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

    def test_uint64_array(self):
        """verify good array values for datatype uint64"""
        dtstr = "DATA_TYPE_UINT64_ARRAY"
        vmin = 0
        vmax = 2 ** 64 - 1
        self._int_set_get_helper(dtstr, vmin, vmax)

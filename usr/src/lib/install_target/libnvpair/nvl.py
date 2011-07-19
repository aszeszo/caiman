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
""" Python wrapper for struct nvlist_t from libnvpair(3LIB).

Provides NVList and NVKey classes.
"""

# Sadly collections.MutableMap.register() is not the same as inheriting, and we
# don't get the ABC checks. At least not in current version of Python.

# Under most every function you see a call to setattr which uses MethodType.
# That is just making a function a method on a class (so "self" is
# automatically passed as first arg). This is used because ctypes.POINTER
# doesn't give you a way to define the class as you normally would.

import collections
import ctypes as C
import errno
import functools
import numbers
import os

from types import MethodType as _MT

from solaris_install.target.cgc import CTypesStructureRef
from solaris_install.target.libnvpair import const, cfunc, cstruct


ENOTSUP = 48  # errno should have this.


class NVPair(C.POINTER(cstruct.nvpair)):
    """ctypes pointer to nvpair_t with methods"""
    _type_ = cstruct.nvpairp

    @property
    def name(self):
        """name of this NVPair, always an ASCII str"""
        return cfunc.nvpair_name(self)

    @property
    def datatype(self):
        """datatype of this NVPair, an int in data_type_enum"""
        return cfunc.nvpair_type(self)

    @property
    def datatype_str(self):
        """datatype of this NVPair represented as a str"""
        return const.DATA_TYPE_MAP[self.datatype]

    @property
    def value(self):
        """value stored in NVPair"""
        # This is huge to make it magically return the right Python thing

        def raise_not_implemented(nvpair):
            """raise error as the datatype is not yet implemented"""
            typestr = const.DATA_TYPE_MAP[self.datatype]
            raise NotImplementedError(typestr)

        class ScalarValue(object):
            """decorator for getting a scalar value from an NVPair."""
            def __init__(self, cfunction):
                """initialize decorator"""
                self.cfunction = cfunction

            def __call__(self, pyfunction):
                """return function that calls cfunction with correct
                   datatype"""
                def scalar_value_wrapper(nvpair):
                    """wrapper function"""
                    # The datatype is the second arg to the cfunction stored in
                    # argtypes as a C.POINTER
                    value = self.cfunction.argtypes[1]._type_()
                    err = self.cfunction(nvpair, C.byref(value))
                    # possible errors are EINVAL or ENOTSUP, neither should
                    # happen because we have hidden the ability to call the
                    # wrong value function from the user.
                    if err != 0:
                        raise OSError(err, "NVPair.value(): %s" %
                                      (os.strerror(err)))
                    return value.value
                return scalar_value_wrapper

        def return_true(nvpair):
            """return_true(NVPair) -> True"""
            return True

        def value_boolean_value(nvpair):
            """value_boolean_value(NVPair) -> bool"""
            val = C.c_int()
            err = cfunc.nvpair_value_boolean_value(nvpair, C.byref(val))
            if err != 0:
                raise OSError(err, "NVPair.value(): %s" % (os.strerror(err)))
            return val.value == 1  # turn it into a bool

        @ScalarValue(cfunc.nvpair_value_byte)
        def value_byte(nvpair):
            """value_byte(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_int8)
        def value_int8(nvpair):
            """value_int8(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_uint8)
        def value_uint8(nvpair):
            """value_uint8(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_int16)
        def value_int16(nvpair):
            """value_int16(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_uint16)
        def value_uint16(nvpair):
            """value_uint16(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_int32)
        def value_int32(nvpair):
            """value_int32(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_uint32)
        def value_uint32(nvpair):
            """value_uint32(NVPair) -> int"""

        @ScalarValue(cfunc.nvpair_value_int64)
        def value_int64(nvpair):
            """value_int64(NVPair) -> long"""

        @ScalarValue(cfunc.nvpair_value_uint64)
        def value_uint64(nvpair):
            """value_uint64(NVPair) -> long"""

        @ScalarValue(cfunc.nvpair_value_string)
        def value_string(nvpair):
            """value_string(NVPair) -> str"""

        @ScalarValue(cfunc.nvpair_value_double)
        def value_double(nvpair):
            """value_double(NVPair) -> float"""

        def value_nvlist(nvpair):
            """value_nvlist(NVPair) -> NVList"""
            val = NVList.__new__(NVList)
            err = cfunc.nvpair_value_nvlist(nvpair, C.byref(val))
            if err != 0:
                raise OSError(err, "NVPair.value(): %s" % (os.strerror(err)))
            # GC ALERT: must add ref to original nvlist (which nvpair better
            #           have)
            val._ref = nvpair._ref
            return val

        class ArrayValue(object):
            """decorator for getting an array value from an NVPair."""
            def __init__(self, cfunction):
                """initialize decorator"""
                self.cfunction = cfunction

            def __call__(self, pyfunction):
                """return function that calls cfunction with correct
                   datatype"""
                def array_value_wrapper(nvpair):
                    """wrapper function"""
                    # The datatype is the second arg to the cfunction stored in
                    # argtypes as a C.POINTER
                    nelem = C.c_uint()
                    pvalue = self.cfunction.argtypes[1]._type_()
                    err = self.cfunction(nvpair, C.byref(pvalue),
                                         C.byref(nelem))
                    # possible errors are EINVAL or ENOTSUP, neither should
                    # happen because we have hidden the ability to call the
                    # wrong value function from the user.
                    if err != 0:
                        raise OSError(err, "NVPair.value(): %s" %
                                      (os.strerror(err)))
                    rlist = list()
                    for idx in xrange(nelem.value):
                        rlist.append(pvalue[idx])
                    return tuple(rlist)
                return array_value_wrapper

        def value_boolean_array(nvpair):
            """value_boolean_array(NVPair) -> tuple of bool"""
            nelem = C.c_uint()
            pvalue = C.POINTER(C.c_int)()
            err = cfunc.nvpair_value_boolean_array(nvpair,
                                                   C.byref(pvalue),
                                                   C.byref(nelem))
            if err != 0:
                raise OSError(err, "NVPair.value(): %s" % (os.strerror(err)))
            rlist = list()
            for idx in xrange(nelem.value):
                rlist.append(pvalue[idx] == 1)  # why we can't use decorator
            return tuple(rlist)

        @ArrayValue(cfunc.nvpair_value_byte_array)
        def value_byte_array(nvpair):
            """value_byte_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_int8_array)
        def value_int8_array(nvpair):
            """value_int8_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_uint8_array)
        def value_uint8_array(nvpair):
            """value_uint8_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_int16_array)
        def value_int16_array(nvpair):
            """value_int16_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_uint16_array)
        def value_uint16_array(nvpair):
            """value_uint16_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_int32_array)
        def value_int32_array(nvpair):
            """value_int32_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_uint32_array)
        def value_uint32_array(nvpair):
            """value_uint32_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_int64_array)
        def value_int64_array(nvpair):
            """value_int64_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_uint64_array)
        def value_uint64_array(nvpair):
            """value_uint64_array(NVPair) -> tuple of int"""

        @ArrayValue(cfunc.nvpair_value_string_array)
        def value_string_array(nvpair):
            """value_string_array(NVPair) -> tuple of str"""

        def value_nvlist_array(nvpair):
            """value_nvlist_array(NVPair) -> tuple of NVList"""
            nelem = C.c_uint()
            pvalue = C.POINTER(NVList)()

            # correct the arg type from nvlistp to NVList
            oarg = cfunc.nvpair_value_nvlist_array.argtypes
            narg = list(oarg)
            narg[1] = C.POINTER(C.POINTER(NVList))
            cfunc.nvpair_value_nvlist_array.argtypes = narg

            err = cfunc.nvpair_value_nvlist_array(nvpair,
                                                  C.byref(pvalue),
                                                  C.byref(nelem))
            if err != 0:
                raise OSError(err, "NVPair.value(): %s" % (os.strerror(err)))
            rlist = list()
            # GC ALERT: must add ref to original nvlist (which nvpair better
            #           have)
            for idx in xrange(nelem.value):
                pvalue[idx]._ref = nvpair._ref  # why we can't use decorator
                rlist.append(pvalue[idx])
            return tuple(rlist)

        value_function = { \
            const.DATA_TYPE_BOOLEAN:       return_true,  # exist means True
            const.DATA_TYPE_BOOLEAN_VALUE: value_boolean_value,
            const.DATA_TYPE_BYTE:          value_byte,
            const.DATA_TYPE_INT8:          value_int8,
            const.DATA_TYPE_UINT8:         value_uint8,
            const.DATA_TYPE_INT16:         value_int16,
            const.DATA_TYPE_UINT16:        value_uint16,
            const.DATA_TYPE_INT32:         value_int32,
            const.DATA_TYPE_UINT32:        value_uint32,
            const.DATA_TYPE_INT64:         value_int64,
            const.DATA_TYPE_UINT64:        value_uint64,
            const.DATA_TYPE_STRING:        value_string,
            const.DATA_TYPE_NVLIST:        value_nvlist,
            const.DATA_TYPE_BOOLEAN_ARRAY: value_boolean_array,
            const.DATA_TYPE_BYTE_ARRAY:    value_byte_array,
            const.DATA_TYPE_INT8_ARRAY:    value_int8_array,
            const.DATA_TYPE_UINT8_ARRAY:   value_uint8_array,
            const.DATA_TYPE_INT16_ARRAY:   value_int16_array,
            const.DATA_TYPE_UINT16_ARRAY:  value_uint16_array,
            const.DATA_TYPE_INT32_ARRAY:   value_int32_array,
            const.DATA_TYPE_UINT32_ARRAY:  value_uint32_array,
            const.DATA_TYPE_INT64_ARRAY:   value_int64_array,
            const.DATA_TYPE_UINT64_ARRAY:  value_uint64_array,
            const.DATA_TYPE_STRING_ARRAY:  value_string_array,
            const.DATA_TYPE_NVLIST_ARRAY:  value_nvlist_array,
            const.DATA_TYPE_DOUBLE:        value_double,
            #const.DATA_TYPE_HRTIME:       None, # value_hrtime
        }.get(self.datatype, raise_not_implemented)

        return value_function(self)

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return "NVPair: %s <%s> = %s" % (self.name,
                                         self.datatype_str,
                                         self.value)

# Fix a couple of function return types.
# Think of  this as casting them to return NVPair
# A NVPair is-a cstruct.nvpairp so perfectly safe.
# Only Because it is a returned value is this necessary.

_nvlist_next_nvpair = cfunc.nvlist_next_nvpair
_nvlist_next_nvpair.restype = NVPair
_nvlist_prev_nvpair = cfunc.nvlist_prev_nvpair
_nvlist_prev_nvpair.restype = NVPair


class NVKey(collections.Iterable):
    """
    An NVKey is just a tuple of name and datatype.
    By making it a class we can enforce good datatype values.

    NVKey(str, int or str) -> NVKey object
    """
    def __init__(self, name, datatype):
        """verify name and datatype and store them together"""
        if not isinstance(name, str):
            raise TypeError("name: '%s' object is not str" %
                            (name.__class__.__name__))

        if datatype not in const.DATA_TYPE_MAP.keys() or \
            datatype == const.DATA_TYPE_UNKNOWN or \
            datatype == "DATA_TYPE_UNKNOWN":
            raise ValueError("datatype: '%s' not a valid datatype" %
                             (str(datatype)))

        if not isinstance(datatype, numbers.Integral):
            datatype = const.DATA_TYPE_MAP[datatype]

        self._name, self._datatype = (name, datatype)

    @property
    def name(self):
        """key name"""
        return self._name

    @property
    def datatype(self):
        """key datatype"""
        return self._datatype

    def __iter__(self):
        """x.__iter__() <==> iter(x)"""
        return iter((self.name, self.datatype))

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return "(%s, %s=%d)" % (self.name,
                                const.DATA_TYPE_MAP[self.datatype],
                                self.datatype)


class _AddScalar(object):
    """decorator for adding a scalar value to an NVList."""
    def __init__(dself, cfunction):
        """initialize decorator"""
        dself.cfunction = cfunction

    def __call__(dself, pyfunction):
        """return function that calls cfunction with correct datatype"""
        @functools.wraps(pyfunction)
        def add_scalar_wrapper(self, name, val):
            """wrapper function"""
            pyfunction(self, name, val)  # call original for type check
            err = dself.cfunction(self, name, val)
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                if err == errno.ENOMEM:
                    raise MemoryError("insufficient memory")
                raise OSError(err, os.strerror(err))
        return add_scalar_wrapper


class _LookupScalar(object):
    """decorator for looking up a scalar value in an NVList."""
    def __init__(dself, cfunction):
        """initialize decorator"""
        dself.cfunction = cfunction

    def __call__(dself, pyfunction):
        """return function that calls cfunction with correct datatype"""
        @functools.wraps(pyfunction)
        def lookup_scalar_wrapper(self, name):
            """wrapper function"""
            # The datatype is the third arg to the cfunction stored in
            # argtypes as a C.POINTER
            val = dself.cfunction.argtypes[2]._type_()
            err = dself.cfunction(self, name, C.byref(val))
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                if err == errno.ENOENT:
                    raise KeyError(name)
                raise OSError(err, os.strerror(err))
            return val.value
        return lookup_scalar_wrapper


class _AddArray(object):
    """decorator for adding an array value to an NVList."""
    def __init__(dself, cfunction):
        """initialize decorator"""
        dself.cfunction = cfunction

    def __call__(dself, pyfunction):
        """return function that calls cfunction with correct datatype"""
        @functools.wraps(pyfunction)
        def add_array_wrapper(self, name, itr):
            """wrapper function"""
            if not isinstance(itr, collections.Iterable):
                raise TypeError("itr: '%s' object is not iterable" %
                                (itr.__class__.__name__))

            # Allow pyfunction to check original values and return tuple
            ituple = pyfunction(self, name, itr)

            # The datatype is the third arg to the cfunction stored in
            # argtypes as a C.POINTER
            nelem = len(ituple)
            carray = dself.cfunction.argtypes[2]._type_ * nelem
            err = dself.cfunction(self, name, carray(*ituple), nelem)
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                if err == errno.ENOMEM:
                    raise MemoryError("insufficient memory")
                raise OSError(err, os.strerror(err))
        return add_array_wrapper


class _LookupArray(object):
    """decorator for looking up an array (tuple) in an NVList."""
    def __init__(dself, cfunction):
        """initialize decorator"""
        dself.cfunction = cfunction

    def __call__(dself, pyfunction):
        """return function that calls cfunction with correct datatype"""
        @functools.wraps(pyfunction)
        def lookup_array_wrapper(self, name):
            """wrapper function"""
            # The datatype is the third arg to the cfunction stored in
            # argtypes as a C.POINTER
            nelem = C.c_uint()
            val = dself.cfunction.argtypes[2]._type_()
            err = dself.cfunction(self, name, C.byref(val), C.byref(nelem))
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                if err == errno.ENOENT:
                    raise KeyError(name)
                raise OSError(err, os.strerror(err))
            retl = list()
            for idx in xrange(nelem.value):
                retl.append(val[idx])
            return tuple(retl)
        return lookup_array_wrapper


class _NVPairIter(collections.Iterator):
    """class to manage iterating over the _NVPair objects in an NVList."""
    def __init__(self, nvl, forward=True):
        self._nvlist = nvl
        self._nvpair = None
        if forward == True:
            self._cfunc = _nvlist_next_nvpair
        else:
            self._cfunc = _nvlist_prev_nvpair

    def next(self):
        """x.next() -> the next value, or raise StopIteration"""
        self._nvpair = self._cfunc(self._nvlist, self._nvpair)
        if not self._nvpair:
            raise StopIteration()  # Python way of saying we are done.
        self._nvpair._ref = self._nvlist  # GC protection
        return self._nvpair


class _NVKeysIter(_NVPairIter):
    """class to manage iterating over the keys in an NVList."""
    def next(self):
        """x.next() -> the next value, or raise StopIteration"""
        nvp = _NVPairIter.next(self)
        return NVKey(nvp.name, nvp.datatype)


class NVList(C.POINTER(cstruct.nvlist)):
    """
    ctypes pointer to nvlist_t with methods

    An NVList behaves like a dict object but requires NVKey objects
    for all of its keys.

    Additionally an NVList can be given to any C library via ctypes
    that expects a pointer to struct nvlist.
    """
    _type_ = cstruct.nvlistp

    def __new__(cls, *args, **kwargs):
        """allocate space for new NVList"""
        return NVList._type_.__new__(cls, *args, **kwargs)

    def __init__(self, flags=const.NV_UNIQUE_NAME):
        """NVList(int) -> NVList object"""
        err = cfunc.nvlist_alloc(C.byref(self), flags, 0)
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            raise OSError(err, "nvlist_alloc: %s" % (os.strerror(err)))

        # free memory when this goes away
        CTypesStructureRef(self, cfunc.nvlist_free)

    ###
    # SECTION: NVList miscellaneous
    ##
    @property
    def nvflags(self):
        """allocation flags for this NVList"""
        #return self.contents.nvl_nvflag
        return self.contents.contents.nvl_nvflag

    def exists(self, name):
        """exists(str) -> bool"""
        return cfunc.nvlist_exists(self, name) == 1

    def empty(self):
        """empty() -> bool"""
        return cfunc.nvlist_empty(self) == 1

    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        # This is kind of a slow function, but its mostly for
        # debugging. Which means speed isn't as essential as readable.
        result = ["NVList (%d):\n" % (id(self))]
        nmlen = len("NAME")
        dtlen = len("TYPE")
        vals = list()
        for nvkey, nvval in self.iteritems():
            nmlen = max(nmlen, len(nvkey.name))
            sname = const.DATA_TYPE_MAP[nvkey.datatype]
            dtlen = max(dtlen, len(sname))
            # Don't follow other NVList down
            if nvkey.datatype == const.DATA_TYPE_NVLIST:
                vals.append((nvkey.name, sname, "NVList"))
            elif nvkey.datatype == const.DATA_TYPE_NVLIST_ARRAY:
                vals.append((nvkey.name, sname, "NVList Array"))
            else:
                vals.append((nvkey.name, sname, nvval))

        fmt = "%%-%ds %%-%ds %%s" % (nmlen, dtlen)
        result.append(fmt % ("NAME", "TYPE", "VALUE"))
        result.append("-" * (nmlen + dtlen + 7))
        for name, datatype, value in vals:
            result.append(fmt % (name, datatype, str(value)))
        return "\n".join(result)

    ###
    # SECTION: add/lookup scalar
    ##
    def add_nvpair(self, nvp):
        """add_nvpair(libnvpair.NVPair) -> add NVPair to this NVList"""
        if not isinstance(nvp, NVPair):
            raise TypeError("nvp: '%s' object is not NVPair" %
                            (nvp.__class__.__name__))
        err = cfunc.nvlist_add_nvpair(self, nvp)
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            raise OSError(err, os.strerror(err))

    def lookup_nvpair(self, name):
        """lookup_nvpair(str) -> NVPair"""
        val = NVPair()
        err = cfunc.nvlist_lookup_nvpair(self, name, C.byref(val))
        if err != 0:
            if err == errno.ENOENT:
                raise KeyError(name)
            if err == ENOTSUP:
                raise TypeError("NVList.nvflags does not have NV_UNIQUE_NAME.")
            raise OSError(err, "lookup_nvpair: %s" % (os.strerror(err)))
        val._ref = self  # GC ALERT: must add ref to original nvlist
        return val  # don't use val.value, this is the right thing.

    def add_boolean(self, name, val=True):
        """add_boolean(str) -> name added if val is True, otherwise removed"""
        if not isinstance(val, bool):
            raise TypeError("val: '%s' object is not bool" %
                            (val.__class__.__name__))
        if val is True:
            err = cfunc.nvlist_add_boolean(self, name)
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                if err == errno.ENOMEM:
                    raise MemoryError("insufficient memory")
                raise OSError(err, os.strerror(err))
        else:
            # The key may not exist, so that is like setting a False to False.
            # perfectly legal.
            try:
                del self[NVKey(name, const.DATA_TYPE_BOOLEAN)]
            except KeyError:
                pass

    def lookup_boolean(self, name):
        """lookup_boolean(str) -> bool"""
        err = cfunc.nvlist_lookup_boolean(self, name)
        if err == 0:
            return True
        if err == errno.ENOENT:
            return False  # ENOENT means False
        if err == errno.EINVAL:
            raise ValueError("invalid argument")
        raise OSError(err, "lookup_boolean: %s" % (os.strerror(err)))

    def add_boolean_value(self, name, val):
        """add_boolean_value(str, bool) -> name/bool added to NVList"""
        if not isinstance(val, bool):
            raise TypeError("val: '%s' object is not bool" %
                            (val.__class__.__name__))
        err = cfunc.nvlist_add_boolean_value(self,
                                             name,
                                             val is True and 1 or 0)
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            raise OSError(err, os.strerror(err))

    def lookup_boolean_value(self, name):
        """lookup_boolean_value(str) -> bool"""
        val = C.c_int()
        err = cfunc.nvlist_lookup_boolean_value(self, name, C.byref(val))
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOENT:
                raise KeyError(name)
            raise OSError(err, "lookup_boolean_value: %s" % (os.strerror(err)))
        return val.value == 1  # turn it into a bool

    @_AddScalar(cfunc.nvlist_add_byte)
    def add_byte(self, name, val):
        """add_byte(str, byte) -> name/byte added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in range(256)" %
                            (val.__class__.__name__))
        if val < 0 or val > 255:
            raise ValueError("val: %d not in range(256)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_byte)
    def lookup_byte(self, name):
        """lookup_byte(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_int8)
    def add_int8(self, name, val):
        """add_int8(str, int) -> name/int8 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(-128,128)" % (val.__class__.__name__))
        if val < -128 or val > 127:
            raise ValueError("val: %d not in range(-128,128)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_int8)
    def lookup_int8(self, name):
        """lookup_int8(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_uint8)
    def add_uint8(self, name, val):
        """add_uint8(str, int) -> name/uint8 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in range(256)" %
                            (val.__class__.__name__))
        if val < 0 or val > 255:
            raise ValueError("val: %d not in range(256)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_uint8)
    def lookup_uint8(self, name):
        """lookup_uint8(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_int16)
    def add_int16(self, name, val):
        """add_int16(str, int) -> name/int16 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(-32768, 32768)" % (val.__class__.__name__))
        if val < -32768 or val > 32767:
            raise ValueError("val: %d not in range(-32768, 32768)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_int16)
    def lookup_int16(self, name):
        """lookup_int16(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_uint16)
    def add_uint16(self, name, val):
        """add_uint16(str, int) -> name/uint16 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in range(65536)" %
                            (val.__class__.__name__))
        if val < 0 or val > 65535:
            raise ValueError("val: %d not in range(65536)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_uint16)
    def lookup_uint16(self, name):
        """lookup_uint16(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_int32)
    def add_int32(self, name, val):
        """add_int32(str, int) -> name/int32 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(-2147483648, 2147483648)" %
                            (val.__class__.__name__))
        if val < -2147483648 or val > 2147483647:
            raise ValueError("val: %d not in range(-2147483648, 2147483648)"
                              % (val))

    @_LookupScalar(cfunc.nvlist_lookup_int32)
    def lookup_int32(self, name):
        """lookup_int32(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_uint32)
    def add_uint32(self, name, val):
        """add_uint32(str, int) -> name/uint32 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(4294967296)" %
                            (val.__class__.__name__))
        if val < 0 or val > 4294967295:
            raise ValueError("val: %d not in range(4294967296)" % (val))

    @_LookupScalar(cfunc.nvlist_lookup_uint32)
    def lookup_uint32(self, name):
        """lookup_uint32(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_int64)
    def add_int64(self, name, val):
        """add_int64(str, int) -> name/int64 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(-9223372036854775808, 9223372036854775808)"
                             % (val.__class__.__name__))
        if val < -9223372036854775808 or val > 9223372036854775807:
            raise ValueError("name: %d not in range"
                            "(-9223372036854775808, 9223372036854775808)"
                            % (val))

    @_LookupScalar(cfunc.nvlist_lookup_int64)
    def lookup_int64(self, name):
        """lookup_int64(str) -> long"""

    @_AddScalar(cfunc.nvlist_add_uint64)
    def add_uint64(self, name, val):
        """add_uint64(str, int) -> name/uint64 added to NVList"""
        if not isinstance(val, numbers.Integral):
            raise TypeError("val: '%s' object not integer in "
                            "range(18446744073709551616)" %
                            (val.__class__.__name__))
        if val < 0 or val > 18446744073709551615:
            raise ValueError("val: %d not in range(18446744073709551616)" %
                            (val))

    @_LookupScalar(cfunc.nvlist_lookup_uint64)
    def lookup_uint64(self, name):
        """lookup_uint64(str) -> int"""

    @_AddScalar(cfunc.nvlist_add_string)
    def add_string(self, name, val):
        """add_string(str, str) -> name/str added to NVList"""
        if not isinstance(val, str):
            raise TypeError("val: '%s' object not str" %
                            (val.__class__.__name__))

    @_LookupScalar(cfunc.nvlist_lookup_string)
    def lookup_string(self, name):
        """lookup_string(str) -> str"""

    @_AddScalar(cfunc.nvlist_add_nvlist)
    def add_nvlist(self, name, val):
        """add_nvlist(str, NVList) -> name/NVList added to NVList"""
        if not isinstance(val, NVList):
            raise TypeError("val: '%s' object not NVList" %
                            (val.__class__.__name__))

    @_LookupScalar(cfunc.nvlist_lookup_double)
    def lookup_double(self, name):
        """lookup_double(str) -> float"""

    @_AddScalar(cfunc.nvlist_add_double)
    def add_double(self, name, val):
        """add_double(str, float) -> name/float added to NVList"""
        if not isinstance(val, numbers.Real):
            raise TypeError("val: '%s' object not float" %
                            (val.__class__.__name__))

    ###
    # SECTION: add/lookup array
    ##

    @_AddArray(cfunc.nvlist_add_boolean_array)
    def add_boolean_array(self, name, itr):
        """add_boolean_array(str, iterable of bool) ->
        name/bool array added to NVList"""
        ilist = list()
        idx = 0
        for val in itr:
            if not isinstance(val, bool):
                print val
                raise TypeError("itr[%d]: '%s' object is not bool" %
                                (idx, val.__class__.__name__))
            ilist.append(val is True and 1 or 0)
            idx += 1
        return tuple(ilist)

    def lookup_boolean_array(self, name):
        """lookup_boolean_array(str) -> list of bool"""
        nelem = C.c_uint()
        val = C.POINTER(C.c_int)()
        err = cfunc.nvlist_lookup_boolean_array(self,
                                                name,
                                                C.byref(val),
                                                C.byref(nelem))
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOENT:
                raise KeyError(name)
            raise OSError(err, os.strerror(err))
        retl = list()
        for idx in xrange(nelem.value):
            retl.append(val[idx] == 1)  # Turn into a bool
        return tuple(retl)

    @_AddArray(cfunc.nvlist_add_byte_array)
    def add_byte_array(self, name, itr):
        """add_byte_array(str, iterable of byte) ->
        name/byte array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(256)" % (idx, val.__class__.__name__))
            if val < 0 or val > 255:
                raise ValueError("itr[%d]: %d not in range(256)" % (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_byte_array)
    def lookup_byte_array(self, name):
        """lookup_byte_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_int8_array)
    def add_int8_array(self, name, itr):
        """add_int8_array(str, iterable of int8) ->
        name/int8 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(-128, 128)" %
                                (idx, val.__class__.__name__))
            if val < -128 or val > 127:
                raise ValueError("itr[%d]: %d not in range(-128, 128)" %
                                 (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_int8_array)
    def lookup_int8_array(self, name):
        """lookup_int8_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_uint8_array)
    def add_uint8_array(self, name, itr):
        """add_uint8_array(str, iterable of uint8) ->
        name/uint8 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(256)" % (idx, val.__class__.__name__))
            if val < 0 or val > 255:
                raise ValueError("itr[%d]: %d not in range(256)" % (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_uint8_array)
    def lookup_uint8_array(self, name):
        """lookup_uint8_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_int16_array)
    def add_int16_array(self, name, itr):
        """add_int16_array(str, iterable of int16) ->
        name/int16 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(-32768, 32768)" % \
                                (idx, val.__class__.__name__))
            if val < -32768 or val > 32767:
                raise ValueError("itr[%d]: %d not in range(-32768, 32768)" %
                                (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_int16_array)
    def lookup_int16_array(self, name):
        """lookup_int16_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_uint16_array)
    def add_uint16_array(self, name, itr):
        """add_uint16_array(str, iterable of uint16) ->
        name/uint16 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(65536)" % \
                                (idx, val.__class__.__name__))
            if val < 0 or val > 65535:
                raise ValueError("itr[%d]: %d not in range(65536)" %
                                 (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_uint16_array)
    def lookup_uint16_array(self, name):
        """lookup_uint16_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_int32_array)
    def add_int32_array(self, name, itr):
        """add_int32_array(str, iterable of int32) ->
        name/int32 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(-2147483648, 2147483648)" %
                                (idx, val.__class__.__name__))
            if val < -2147483648 or val > 2147483647:
                raise ValueError("itr[%d]: %d not in "
                                 "range(-2147483648, 2147483648)" % (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_int32_array)
    def lookup_int32_array(self, name):
        """lookup_int32_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_uint32_array)
    def add_uint32_array(self, name, itr):
        """add_uint32_array(str, iterable of uint32) ->
        name/uint32 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(4294967296)" %
                                (idx, val.__class__.__name__))
            if val < 0 or val > 4294967295:
                raise ValueError("itr[%d]: %d not in range(4294967296)" %
                                (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_uint32_array)
    def lookup_uint32_array(self, name):
        """lookup_uint32_array(str) -> list of int"""

    @_AddArray(cfunc.nvlist_add_int64_array)
    def add_int64_array(self, name, itr):
        """add_int64_array(str, iterable of int64) ->
        name/int64 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(-9223372036854775808, "
                                "9223372036854775808)" %
                                (idx, val.__class__.__name__))
            if val < -9223372036854775808 or val > 9223372036854775807:
                raise ValueError("itr[%d]: %d not in "
                                 "range(-9223372036854775808, "
                                 "9223372036854775808)" % (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_int64_array)
    def lookup_int64_array(self, name):
        """lookup_int64_array(str) -> list of long"""

    @_AddArray(cfunc.nvlist_add_uint64_array)
    def add_uint64_array(self, name, itr):
        """add_uint64_array(str, iterable of uint64) ->
        name/uint64 array added to NVList"""
        ituple = tuple(itr)
        for idx, val in enumerate(ituple):
            if not isinstance(val, numbers.Integral):
                raise TypeError("itr[%d]: '%s' object not integer in "
                                "range(18446744073709551616)" %
                                (idx, val.__class__.__name__))
            if val < 0 or val > 18446744073709551615:
                raise ValueError("itr[%d]: %d not in "
                                 "range(18446744073709551616)" % (idx, val))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_uint64_array)
    def lookup_uint64_array(self, name):
        """lookup_uint64_array(str) -> list of long"""

    @_AddArray(cfunc.nvlist_add_string_array)
    def add_string_array(self, name, itr):
        """add_string_array(str, iterable of str) ->
        name/str array added to NVList"""
        # NOTE: strings are themselves iterable but that may be what user
        # wants.
        ituple = tuple(itr)  # we will need len
        for idx, val in enumerate(ituple):
            if not isinstance(val, str):
                raise TypeError("itr[%d]: '%s' object not str" %
                                (idx, val.__class__.__name__))
        return ituple

    @_LookupArray(cfunc.nvlist_lookup_string_array)
    def lookup_string_array(self, name):
        """lookup_string_array(str) -> list of str"""

    @_AddArray(cfunc.nvlist_add_nvlist_array)
    def add_nvlist_array(self, name, itr):
        """add_nvlist_array(str, iterable of NVList) ->
        name/NVList array added to NVList"""
        ituple = tuple(itr)  # we will need len
        for idx, val in enumerate(ituple):
            if not isinstance(val, NVList):
                raise TypeError("itr[%d]: '%s' object not NVList" %
                                (idx, val.__class__.__name__))
        return ituple

    def lookup_nvlist_array(self, name):
        """lookup_nvlist_array(str) -> list of nvlist"""
        nelem = C.c_uint()
        val = C.POINTER(NVList)()

        # correct the arg type from nvlistp to NVList
        oarg = cfunc.nvlist_lookup_nvlist_array.argtypes
        narg = list(oarg)
        narg[2] = C.POINTER(C.POINTER(NVList))
        cfunc.nvlist_lookup_nvlist_array.argtypes = narg

        err = cfunc.nvlist_lookup_nvlist_array(
            self, name, C.byref(val), C.byref(nelem))
        cfunc.nvlist_lookup_nvlist_array.argtypes = oarg
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOENT:
                raise KeyError(name)
            raise OSError(err, os.strerror(err))
        retl = list()
        for idx in xrange(nelem.value):
            val[idx]._ref = self  # GC ALERT
            retl.append(val[idx])
        return tuple(retl)

    ###
    # SECTION: MutableMapping
    #          Remaining methods required for NVList to qualify as a
    #          MutableMapping (dictionary).
    ##
    def __setitem__(self, key, item):
        """__setitem__(x, key, item) -> x[key] = item"""

        if not isinstance(key, NVKey):
            try:
                nkey = NVKey(*key)  # can try turning key into NVKey
                key = nkey
            except (TypeError, ValueError):
                # TypeError if key isn't sequence either
                raise TypeError("key: '%s' object is not NVKey" %
                                (key.__class__.__name__))

        # For any datatype not yet implemented this will be called.
        def raise_not_implemented(name, itr):
            """raise error as the datatype is not yet implemented"""
            typestr = const.DATA_TYPE_MAP[key.datatype]
            raise NotImplementedError(typestr)

        # The big lookup table.
        add_function = { \
            const.DATA_TYPE_BOOLEAN:       self.add_boolean,
            const.DATA_TYPE_BOOLEAN_VALUE: self.add_boolean_value,
            const.DATA_TYPE_BYTE:          self.add_byte,
            const.DATA_TYPE_INT8:          self.add_int8,
            const.DATA_TYPE_UINT8:         self.add_uint8,
            const.DATA_TYPE_INT16:         self.add_int16,
            const.DATA_TYPE_UINT16:        self.add_uint16,
            const.DATA_TYPE_INT32:         self.add_int32,
            const.DATA_TYPE_UINT32:        self.add_uint32,
            const.DATA_TYPE_INT64:         self.add_int64,
            const.DATA_TYPE_UINT64:        self.add_uint64,
            const.DATA_TYPE_STRING:        self.add_string,
            const.DATA_TYPE_NVLIST:        self.add_nvlist,
            const.DATA_TYPE_BOOLEAN_ARRAY: self.add_boolean_array,
            const.DATA_TYPE_BYTE_ARRAY:    self.add_byte_array,
            const.DATA_TYPE_INT8_ARRAY:    self.add_int8_array,
            const.DATA_TYPE_UINT8_ARRAY:   self.add_uint8_array,
            const.DATA_TYPE_INT16_ARRAY:   self.add_int16_array,
            const.DATA_TYPE_UINT16_ARRAY:  self.add_uint16_array,
            const.DATA_TYPE_INT32_ARRAY:   self.add_int32_array,
            const.DATA_TYPE_UINT32_ARRAY:  self.add_uint32_array,
            const.DATA_TYPE_INT64_ARRAY:   self.add_int64_array,
            const.DATA_TYPE_UINT64_ARRAY:  self.add_uint64_array,
            const.DATA_TYPE_STRING_ARRAY:  self.add_string_array,
            const.DATA_TYPE_NVLIST_ARRAY:  self.add_nvlist_array,
            const.DATA_TYPE_DOUBLE:        self.add_double,
            #const.DATA_TYPE_HRTIME:        None, # nvlist_add_hrtime
        }.get(key.datatype, raise_not_implemented)

        add_function(key.name, item)

    def __iter__(self):
        """x.__iter__() <==> iter(x)"""
        return _NVKeysIter(self)

    def __reversed__(self):
        """x.__reversed__() <==> reversed(x)"""
        return _NVKeysIter(self, forward=False)

    def __getitem__(self, key):
        """x.__getitem__(y) <==> x[y]"""
        if not isinstance(key, NVKey):
            try:
                nkey = NVKey(*key)  # can try turning key into NVKey
                key = nkey
            except (TypeError, ValueError):
                # TypeError if key isn't sequence either
                raise TypeError("key: '%s' object is not NVKey" %
                                (key.__class__.__name__))

        # For any datatype not yet implemented this will be called.
        def raise_not_implemented(name):
            """raise error as the datatype is not yet implemented"""
            typestr = const.DATA_TYPE_MAP[key.datatype]
            raise NotImplementedError(typestr)

        # The big lookup table.
        lookup_function = { \
            const.DATA_TYPE_BOOLEAN:       self.lookup_boolean,
            const.DATA_TYPE_BOOLEAN_VALUE: self.lookup_boolean_value,
            const.DATA_TYPE_BYTE:          self.lookup_byte,
            const.DATA_TYPE_INT8:          self.lookup_int8,
            const.DATA_TYPE_UINT8:         self.lookup_uint8,
            const.DATA_TYPE_INT16:         self.lookup_int16,
            const.DATA_TYPE_UINT16:        self.lookup_uint16,
            const.DATA_TYPE_INT32:         self.lookup_int32,
            const.DATA_TYPE_UINT32:        self.lookup_uint32,
            const.DATA_TYPE_INT64:         self.lookup_int64,
            const.DATA_TYPE_UINT64:        self.lookup_uint64,
            const.DATA_TYPE_STRING:        self.lookup_string,
            const.DATA_TYPE_NVLIST:        self.lookup_nvlist,
            const.DATA_TYPE_BOOLEAN_ARRAY: self.lookup_boolean_array,
            const.DATA_TYPE_BYTE_ARRAY:    self.lookup_byte_array,
            const.DATA_TYPE_INT8_ARRAY:    self.lookup_int8_array,
            const.DATA_TYPE_UINT8_ARRAY:   self.lookup_uint8_array,
            const.DATA_TYPE_INT16_ARRAY:   self.lookup_int16_array,
            const.DATA_TYPE_UINT16_ARRAY:  self.lookup_uint16_array,
            const.DATA_TYPE_INT32_ARRAY:   self.lookup_int32_array,
            const.DATA_TYPE_UINT32_ARRAY:  self.lookup_uint32_array,
            const.DATA_TYPE_INT64_ARRAY:   self.lookup_int64_array,
            const.DATA_TYPE_UINT64_ARRAY:  self.lookup_uint64_array,
            const.DATA_TYPE_STRING_ARRAY:  self.lookup_string_array,
            const.DATA_TYPE_NVLIST_ARRAY:  self.lookup_nvlist_array,
            const.DATA_TYPE_DOUBLE:        self.lookup_double,
            #const.DATA_TYPE_HRTIME:       # self.lookup_hrtime,
        }.get(key.datatype, raise_not_implemented)

        return lookup_function(key.name)

    def get(self, key, default=None):
        """D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None."""
        try:
            return self[key]
        except KeyError:
            return default

    def __contains__(self, key):
        """D.__contains__(k) -> True if D has a key k, else False"""
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def __eq__(self, other):
        """x.__eq__(other) <==> x == other"""
        # Remember, in Python "==" means they are equivalent.
        # If you want to see if the objects are identical (same
        # pointer) use "is".
        return isinstance(other, collections.Mapping) and \
               dict(self.items()) == dict(other.items())

    def __ne__(self, other):
        """x.__ne__(other) <==> x != other"""
        return not (self == other)

    def __delitem__(self, key):
        """x.__delitem__(y) <==> del x[y]"""
        if not isinstance(key, NVKey):
            try:
                nkey = NVKey(*key)  # can try turning key into NVKey
                key = nkey
            except (TypeError, ValueError):
                # TypeError if key isn't sequence either
                raise TypeError("key: '%s' object is not NVKey" %
                                (key.__class__.__name__))
        err = cfunc.nvlist_remove(self, key.name, key.datatype)
        if err != 0:
            if err == errno.EINVAL:
                raise ValueError("invalid argument")
            if err == errno.ENOENT:
                # In general this is a KeyError, but not for boolean, where
                # lack of data means False.
                if key.datatype == const.DATA_TYPE_BOOLEAN:
                    return  # no error
                raise KeyError("%s" % (key))
            raise OSError(err, "nvlist_delitem: %s" % (os.strerror(err)))

    def iterkeys(self):
        """D.iterkeys() -> an iterator over the keys of D"""
        return iter(self)

    def itervalues(self):
        """D.itervalues() -> an iterator over the values of D"""
        class NVListValuesIter(_NVPairIter):
            """class to manage iterating over the values in an NVList."""
            def next(self):
                """x.next() -> the next value, or raise StopIteration"""
                nvp = _NVPairIter.next(self)
                return nvp.value()
        return NVListValuesIter(self)

    def iteritems(self):
        """D.iteritems() -> an iterator over the (key, value) items of D"""
        class NVKeysValuesIter(_NVPairIter):
            """class to manage iterating over the (key, value) pairs in an
            NVList."""
            def next(self):
                """x.next() -> the next value, or raise StopIteration"""
                nvp = _NVPairIter.next(self)
                return (NVKey(nvp.name, nvp.datatype), nvp.value)
        return NVKeysValuesIter(self)

    def keys(self):
        """D.keys() -> list of D's keys"""
        return list(self)

    def items(self):
        """D.items() -> list of D's (key, value) pairs, as 2-tuples"""
        return [(key, val) for key, val in self.iteritems()]

    def values(self):
        """D.values() -> list of D's values"""
        return [val for val in self.itervalues()]

    def __len__(self):
        """x.__len__() <==> len(x)"""
        return len(self.values())

    __marker = object()  # used for pop()

    def pop(self, key, default=__marker):
        """
        D.pop(k[,d]) -> v, remove specified key and return the corresponding
        value.  If key is not found, d is returned if given, otherwise
        KeyError is raised
        """
        try:
            value = self[key]
        except KeyError:
            if default is NVList.__marker:
                raise  # no default passed in
            return default
        else:
            del self[key]
            return value

    def popitem(self):
        """
        D.popitem() -> (k, v), remove and return some (key, value) pair as a
        2-tuple; but raise KeyError if D is empty.
        """
        try:
            key = next(iter(self))  # self.iteritems() ?
        except StopIteration:
            raise KeyError
        value = self[key]
        del self[key]
        return key, value

    def clear(self):
        """D.clear() -> None.  Remove all items from D."""
        # The most reliable way to go about this is to iterate over NVPairs.
        # And directly call nvlist_remove() on the NVPair.
        itr = _nvlist_next_nvpair(None)
        while itr:
            nxt = _nvlist_next_nvpair(itr)
            err = cfunc.nvlist_remove_nvpair(self, itr)
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                else:
                    raise OSError(err, "clear: %s" % (os.strerror(err)))
            itr = nxt

    def update(self, other=(), **kwds):
        """
        D.update(E, **F) -> None.  Update D from dict/iterable E and F.
        If E has a .keys() method, does:     for k in E: D[k] = E[k]
        If E lacks .keys() method, does:     for (k, v) in E: D[k] = v
        In either case, this is followed by: for k in F: D[k] = F[k]
        """

        # one speedup is the case of other being another NVList, in which
        # case we will let the C code handle it.

        # Keep in mind this could raise a KeyError if the other
        # Mapping doesn't have keys that are compatible with NVKey
        # So it isn't very likely to work with average dictionary.
        # But it could...
        if isinstance(other, NVList):
            err = cfunc.nvlist_merge(self, other, 0)
            if err != 0:
                if err == errno.EINVAL:
                    raise ValueError("invalid argument")
                else:
                    raise OSError(err, "update: %s" % (os.strerror(err)))
        elif isinstance(other, collections.Mapping):
            for key in other:
                self[key] = other[key]
        elif hasattr(other, "keys") and callable(other.keys):
            for key in other.keys():
                self[key] = other[key]
        else:
            for key, value in other:
                self[key] = value

        for key, value in kwds.items():
            self[key] = value

    def setdefault(self, key, default=None):
        """D.setdefault(k[,d]) -> D.get(k,d), also set D[k]=d if k not in D"""
        try:
            return self[key]
        except KeyError:
            self[key] = default  # will raise TypeError for bad key.
        return default


def lookup_nvlist(self, name):
    """lookup_nvlist(str) -> NVList"""
    val = NVList.__new__(NVList)
    err = cfunc.nvlist_lookup_nvlist(self, name, C.byref(val))
    if err != 0:
        if err == errno.EINVAL:
            raise ValueError("invalid argument")
        if err == errno.ENOENT:
            raise KeyError(name)
        raise OSError(err, os.strerror(err))
    val.ref = self  # GC alert
    CTypesStructureRef(val, cfunc.nvlist_free)
    return val

setattr(NVList, "lookup_nvlist", _MT(lookup_nvlist, None, NVList))

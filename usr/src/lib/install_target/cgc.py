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

"""
cgc module for "ctypes garbage collection" with finalization.

This module provides CTypesStructureRef, a class whose sole purpose is
cleaning up after a ctypes.Structure (or ctypes.POINTER to ctypes.Structure)
is reaped by the Python garbage collector (or due to reference count).

__del__ is not safe and introduces its own problems so use this instead.

Basic use is to simply create a CTypesStructureRef. For example:

    >>> import ctypes as C
    >>> from pysol.cgc import CTypesStructureRef
    >>> def fin(o): print "done!"
    ...
    >>> class Foo(C.Structure): pass # opaque
    ...
    >>> f = Foo()
    >>> CTypesStructureRef(f, fin)
    <weakref at 81033ec; to 'Foo' at 80fb6ec>
    >>> del f
    done!

This only works for ctypes objects.
This will call your finalizer with an equivalent object (it points to
the same memory) but not the exact Python object.
"""

import ctypes as C
import weakref

# __del__ in Python leads to the garbage collector not being able
#         to collect cycles. That's bad.
#
# weak references on the other hand don't upset the GC.
# And weakrefs can be given a function to call when the *referenced*
# object has been collected by GC.
#
# So the trick is to put weakrefs onto a dictionary (so they do not
# get GC-ed themselves) which have information to recreate the
# original ctypes object and give it to a finalizer (which can free
# memory for example).
#
# With ctypes we just use addressof() on the Structure or POINTER
# object. This address along with type information allow us to
# recreate the object using the "from_address" method of Structure.
#
# Note that from_address() calls __new__() and not __init__() on
# the class.

_PointerType = type(C.POINTER(C.c_void_p))
_WEAK_REFS = dict()  # The first level dictionary


class CTypesStructureRef(weakref.ref):
    """A class for finalizing structures and pointers"""

    @staticmethod
    def _auto_finalizer(ref):
        """
        _auto_finalizer(CTypesStructureRef) -> None

        Look up address ref points to and recreat the ctypes object
        then call ref.finalizer() on it.
        """
        subdict = _WEAK_REFS[ref.klass]
        del subdict[id(ref)]

        # Need to recreate the same type, so for each level of indirection
        # wrap in a pointer
        obj = ref.klass.from_address(ref.address)
        while ref.level != 0:
            obj = C.pointer(obj)
            ref.level -= 1

        try:
            # call users finalizer with a ctypes object.
            ref.finalizer(obj)
        except:
            # ignore any exceptions
            pass

    def __new__(cls, obj, finalizer):
        weak = weakref.ref.__new__(cls, obj,
                                   CTypesStructureRef._auto_finalizer)
        return weak

    def __init__(self, obj, finalizer):
        """CTypesStructureRef(obj, finalizer) -> CTypesStructureRef object"""

        # We need to follow the pointer (if it is a _ctypes.PointerType)
        level = 0

        # dereference pointers until the data is found
        while isinstance(obj._type_, _PointerType):
            obj = obj.contents
            level += 1

        self.klass = type(obj)  # the real data
        self.address = C.addressof(obj)
        self.level = level
        self.finalizer = finalizer

        if self.klass in _WEAK_REFS:
            kdict = _WEAK_REFS[self.klass]
        else:
            kdict = _WEAK_REFS[self.klass] = dict()

        # So this isn't destroyed.
        kdict[id(self)] = self


class CTypesSimpleTypeRef(weakref.ref):
    """
    A class for finalizing ctypes types (like c_int).

    It may seem strange, but with the opaque descriptor of libdiskmgt.so
    for example we need this ability.
    """

    @staticmethod
    def _auto_finalizer(ref):
        """
        _auto_finalizer(CtypesTypeRef) -> None

        Recreate the object and call ref.finalizer() on it.
        """
        subdict = _WEAK_REFS[ref.klass]
        del subdict[id(ref)]
        try:
            # call users finalizer with a ctypes object.
            obj = ref.klass(obj.value)
            ref.finalizer(obj)
        except:
            # ignore any exceptions
            pass

    def __new__(cls, obj, finalizer):
        weak = weakref.ref.__new__(cls, obj,
            CTypesSimpleTypeRef._auto_finalizer)
        return weak

    def __init__(self, obj, finalizer):
        """CTypesSimpleTypeRef(obj, finalizer) -> CTypesSimpleTypeRef object"""
        self.klass = type(obj)
        self.value = obj.value
        self.finalizer = finalizer

        if self.klass in _WEAK_REFS:
            kdict = _WEAK_REFS[self.klass]
        else:
            kdict = _WEAK_REFS[self.klass] = dict()

        # So this isn't destroyed.
        kdict[id(self)] = self

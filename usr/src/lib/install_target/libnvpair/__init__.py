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
"""Python package with ctypes wrapper for libnvpair(3LIB).

An nvlist_t is often returned from other C libraries.
This package, and module nvl in particular, provide access to nvlist_t.

nvl.NVList is a collections.MutableMapping and acts, as much as it
can, like a dictionary.

Of course all the C getter/setter functions are available too.
But for more Python code you should set up keys and access an NVList
like a dictionary. If you make the keys global you have only one place
to change the Python code if the C code changes from a C int16_t to
a int32_t. If you used add_*() and lookup_*() routines you will have
to search through all of your code.

If you are implementing another C library, you may need to add the NVList
you return to the special Garbage Collection References. This is done
with cgc.CTypesStructureRef class.

For example:

    from solaris_install.target.cgc import CTypesStructureRef
    from solaris_install.target.libnvpair.nvl import NVList
    # you need just one function to clean up an nvlist:
    from solaris_install.target.libnvpair.cfunc import nvlist_free
    import ctypes as C

    _MYLIB = C.CDLL("/usr/lib/libmylib.so", use_errno=True)

    def myfinalizer(nvlist):
        print "death to this NVList!"
        print nvlist
        nvlist_free(nvlist)

    _MYLIB.foo.restype = C.c_int
    _MYLIB.foo.argtypes = (C.POINTER(nvl.NVList),)
    def foo():
        nvlist = nvl.NVList__new__() # very important you use __new__()
        err = _MYLIB.foo(C.byref(nvlist))
        CTypesStructureRef(nvlist) # now memory will be garbage collected.
        return nvlist

Users of foo() no longer need to worry about the resources allocated by
foo(), the Python GC will now take care of it.
"""

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
The base class that just forwards everything to its shadow.

collections.MutableSequence = class MutableSequence(Sequence)
 |  Method resolution order:
 |      MutableSequence
 |      Sequence
 |      Sized
 |      Iterable
 |      Container
 |      __builtin__.object

But we only have to implement the abstract interfaces.
See http://docs.python.org/library/collections.html

ShadowList provides the basics for any other specialty list class.

NOTE: you could have ShadowList derive from both 'MutableSequence'
      and 'list'. It doesn't really buy you anything but complexity
      (and hiding the list as self).
"""
import copy

from collections import MutableSequence

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc


class ShadowList(MutableSequence):
    """
    ShadowList() -> new list
    ShadowList(sequence) -> new list initialized from sequence's items
    """
    def __init__(self, *args):
        arglen = len(args)
        if arglen > 1:
            # Mimic error list() gives
            raise TypeError("ShadowList() takes at most 1 argument " + \
                            "(%d given)" % arglen)
        if arglen == 1:
            # will raise exception if not a sequence
            itr = iter(*args)
            del itr

        self._shadow = list(*args)

    # MutableSequence abstract method(s)
    def __setitem__(self, index, value):
        """x.__setitem__(i, y) <==> x[i]=y"""
        self._shadow.__setitem__(index, value)

    def __delitem__(self, index):
        """x.__delitem__(y) <==> del x[y]"""
        self._shadow.__delitem__(index)

    def insert(self, index, value):
        """L.insert(index, object) -- insert object before index"""
        self._shadow.insert(index, value)

    # Sequence abstract method(s)
    def __getitem__(self, index):
        """x.__getitem__(y) <==> x[y]"""
        if isinstance(index, slice):
            typ = self.__class__
            return typ(self._shadow.__getitem__(index))
        else:
            return self._shadow.__getitem__(index)

    # Iterable abstract method(s)
    def __iter__(self):
        """x.__iter__() <==> iter(x)"""
        return self._shadow.__iter__()

    # Container abstract method(s)
    def __contains__(self, value):
        """x.__contains__(y) <==> y in x"""
        return self._shadow.__contains__(value)

    # Sized abstract methods(s)
    def __len__(self):
        """x.__len__() <==> len(x)"""
        return self._shadow.__len__()

    # And additional interfaces that should be there...
    def __repr__(self):
        """x.__repr__() <==> repr(x)"""
        return self._shadow.__repr__()

    def __copy__(self):
        s = ShadowList()
        s._shadow = copy.copy(self._shadow)
        return s

    def set_error(self, exception):
        # pylint: disable-msg=E1101
        error = errsvc.ErrorInfo(self.mod_id, liberrsvc.ES_ERR)
        error.set_error_data(liberrsvc.ES_DATA_EXCEPTION, exception)


class ShadowExceptionBase(Exception):
    """
        Base exception class to contain str for printing
        error data values
    """
    def __init__(self):
        self.value = None

    def __str__(self):
        return self.value

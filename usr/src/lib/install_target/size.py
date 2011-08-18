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
Size library for install applications and libraries
"""

import re

size_re = re.compile("([\d+\.]+)(\w+)?")


class Size(object):
    """ Translation mapping class for converting number of sectors to/from
    human readable values.
    """
    byte_units = "b"
    s_units = "s"
    sector_units = "secs"
    k_units = "k"
    kb_units = "kb"
    m_units = "m"
    mb_units = "mb"
    g_units = "g"
    gb_units = "gb"
    t_units = "t"
    tb_units = "tb"
    p_units = "p"
    pb_units = "pb"
    e_units = "e"
    eb_units = "eb"
    z_units = "z"
    zb_units = "zb"

    units = dict([
        (k_units, 2 ** 10),
        (kb_units, 2 ** 10),
        (2 ** 10, kb_units),
        (m_units, 2 ** 20),
        (mb_units, 2 ** 20),
        (2 ** 20, mb_units),
        (g_units, 2 ** 30),
        (gb_units, 2 ** 30),
        (2 ** 30, gb_units),
        (t_units, 2 ** 40),
        (tb_units, 2 ** 40),
        (2 ** 40, tb_units),
        (p_units, 2 ** 50),
        (pb_units, 2 ** 50),
        (2 ** 50, pb_units),
        (e_units, 2 ** 60),
        (eb_units, 2 ** 60),
        (2 ** 60, eb_units),
        (z_units, 2 ** 70),
        (zb_units, 2 ** 70),
        (2 ** 70, zb_units),
    ])

    # create a list of valid units strings
    valid_units = filter(lambda x: isinstance(x, str), units)
    valid_units.extend([byte_units, sector_units, s_units])

    def __init__(self, humanreadable, blocksize=512):
        self.humanreadable = humanreadable
        self.blocksize = blocksize

        # attempt to split the humanreadable string into a value and suffix
        size_test = size_re.match(self.humanreadable)
        if size_test is not None:
            # First try to cast the string to an int.  If the int cast fails,
            # switch to casting to a float.  If the cast to a float fails,
            # bubble the error up to the engine.
            try:
                value = int(size_test.group(1))
            except ValueError:
                value = float(size_test.group(1))

            # set the suffix, if it matched.  If it didn't match, raise an
            # exception
            if size_test.group(2) is None:
                raise ValueError("no units specified for a size value " \
                                  "of '%s'" % self.humanreadable)
            else:
                suffix = size_test.group(2)
        else:
            raise ValueError("unable to process a size value of '%s'" % \
                             self.humanreadable)

        if suffix.lower() not in Size.valid_units:
            raise ValueError("invalid suffix for a size value of '%s'" % \
                             self.humanreadable)

        if suffix == Size.byte_units:
            self.byte_value = long(value)
        elif suffix in [Size.sector_units, Size.s_units]:
            self.byte_value = long(value * self.blocksize)
        else:
            self.byte_value = long(value * Size.units[suffix.lower()])

    @property
    def sectors(self):
        """ class property to allow fast conversion to sector units
        """
        return self.get(self.sector_units)

    def get(self, units=byte_units):
        """ get() - method to return the size in a unit specified

        units - text string representing what to convert the size to
        """
        # ensure units is in lower-case
        units = units.lower()

        if units == Size.byte_units:
            return self.byte_value
        elif units == Size.sector_units:
            return self.byte_value / self.blocksize
        else:
            return self.byte_value / float(Size.units[units])

    def __repr__(self):
        """ return a humanreadable value which can be used to recreate the
        object.
        """
        return "Size(" + str(self.get(Size.byte_units)) + "b" + ")"

    def __str__(self):
        if self.byte_value >= Size.units[Size.zb_units]:
            s = '%.2fzb' % self.get(Size.zb_units)
        elif self.byte_value >= Size.units[Size.eb_units]:
            s = '%.2feb' % self.get(Size.eb_units)
        elif self.byte_value >= Size.units[Size.pb_units]:
            s = '%.2fpb' % self.get(Size.pb_units)
        elif self.byte_value >= Size.units[Size.tb_units]:
            s = '%.2ftb' % self.get(Size.tb_units)
        elif self.byte_value >= Size.units[Size.gb_units]:
            s = '%.2fgb' % self.get(Size.gb_units)
        elif self.byte_value >= Size.units[Size.mb_units]:
            s = '%.2fmb' % self.get(Size.mb_units)
        elif self.byte_value >= Size.units[Size.kb_units]:
            s = '%.2fkb' % self.get(Size.kb_units)
        else:
            s = '%.2fb' % float(self.byte_value)
        return s

    def __cmp__(self, other):
        if self.get(units=Size.byte_units) < other.get(units=Size.byte_units):
            return -1
        elif self.get(units=Size.byte_units) > \
             other.get(units=Size.byte_units):
            return 1
        elif self.get(units=Size.byte_units) == \
             other.get(units=Size.byte_units):
            return 0

        raise TypeError("Size value is being compared to non-Size value")

    def __add__(self, other):
        """ eumulated method for adding two Size objects
        """
        return Size(str(self.byte_value + other.byte_value) + Size.byte_units)

    def __sub__(self, other):
        """ eumulated method for subtracting two Size objects
        """
        return Size(str(self.byte_value - other.byte_value) + Size.byte_units)

    def __iadd__(self, other):
        """ eumulated method for the augmented assignment for +=
        """
        self.byte_value += other.byte_value
        return self

#!/usr/bin/python2.6
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#


class ProfileData(object):
    """Contains the contents of a jumpstart profile"""

    def __init__(self, name):
        self._name = name
        self._data = {}
        self._conv_report = None

    @property
    def name(self):
        """Name of this profile"""
        return self._name

    @property
    def data(self):
        """Dictionary of keys & values contained in profile.  May be None
        if the profile could not be read.  The key is the line # in the file
        """
        return self._data

    @property
    def conversion_report(self):
        """Report of all errors encountered during processing"""
        return self._conv_report

    @conversion_report.setter
    def conversion_report(self, report):
        """Set the conversion report"""
        self._conv_report = report


class KeyValues(object):
    """Key/Value object"""

    def __init__(self, key, values, line_num):
        self._key = key
        self._values = values
        self._line_num = line_num

    @property
    def key(self):
        """Return string, key identifer for object"""
        return self._key

    @property
    def values(self):
        """Return List of string of the values associated with the key"""
        return self._values

    @property
    def line_num(self):
        """Return the line # that this rule key value combination was in the
        rule file
        """
        return self._line_num

    def __str__(self):
        return "line " + str(self.line_num) + ", key=" + str(self.key) +\
            ", values: " + str(self.values)


class ConversionReport(object):
    """Contains the error counts that occurred during the various phases of
    the conversion process.
    process errors refers to errors that occur when the various entities are
    read in
    conversion errors refers to errors that occur when converting items from
    the Solaris 10 nomiclature to Solaris 11
    unsupported items refers to items that can not be converted.

    NOTE: conversion errors and unsupported items will
    have a value of None if there is a processing error that prevents
    the file from being read
    """

    def __init__(self, process_errs=0, conversion_errs=0, unsupported_items=0):
        self._process_errs = process_errs
        self._conversion_errs = conversion_errs
        self._unsupported_items = unsupported_items

    def add_process_error(self):
        """Increments the # of processing errors by 1"""
        if self._process_errs is None:
            self._process_errs = 1
        else:
            self._process_errs += 1

    def add_conversion_error(self):
        """Increments the # of conversion errors by 1"""
        if self._conversion_errs is None:
            self._conversion_errs = 1
        else:
            self._conversion_errs += 1

    def add_unsupported_item(self):
        """Increments the # of unsupported items by 1"""
        if self._unsupported_items is None:
            self._unsupported_items = 1
        else:
            self._unsupported_items += 1

    @property
    def process_errors(self):
        """Returns the # of process errors"""
        return self._process_errs

    @property
    def conversion_errors(self):
        """Returns the # of conversion errors"""
        return self._conversion_errs

    @property
    def unsupported_items(self):
        """Returns the # of unsupported items"""
        return self._unsupported_items

    @process_errors.setter
    def process_errors(self, error_count):
        """Set the # of processing errors to error_count"""
        self._process_errs = error_count

    @conversion_errors.setter
    def conversion_errors(self, error_count):
        """Set the # of conversion errors to error_count"""
        self._conversion_errs = error_count

    @unsupported_items.setter
    def unsupported_items(self, unsupported):
        """Set the # of unsupported items to unsupported"""
        self._unsupported_items = unsupported

    def error_count(self):
        """Return the # of errors associate with this report"""
        errs = 0
        if self._process_errs is not None:
            errs = self._process_errs
        if self._conversion_errs is not None:
            errs += self._conversion_errs
        if self._unsupported_items is not None:
            errs += self._unsupported_items
        return errs

    def has_errors(self):
        """Returns boolean, True if there are any process errors, conversion
        errors, or unsupported items
        """
        if self._process_errs or self._conversion_errs \
            or self._unsupported_items:
            return True
        else:
            return False

    def __str__(self):
        return "process errors:  %d, " % self.process_errors + \
               "conversion errors:  %s, " % str(self.conversion_errors) + \
               "unsupported items:  %s" % str(self.unsupported_items)

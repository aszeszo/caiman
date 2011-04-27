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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

''' CUD Error Handler Library and Object Types '''

import liberrsvc

VALID_ERROR_TYPES = [liberrsvc.ES_ERR, \
    liberrsvc.ES_CLEANUP_ERR, \
    liberrsvc.ES_REPAIRED_ERR]

INTEGER_DATA_TYPES = [liberrsvc.ES_DATA_ERR_NUM]

STRING_DATA_TYPES = [liberrsvc.ES_DATA_OP_STR, \
    liberrsvc.ES_DATA_FIXIT_STR, \
    liberrsvc.ES_DATA_FAILED_AT, \
    liberrsvc.ES_DATA_FAILED_STR]

EXCEPTION_DATA_TYPES = [liberrsvc.ES_DATA_EXCEPTION]

# Declare the list to store the errors.
# @type _ERRORS list
_ERRORS = []


class ErrorInfo(object):
    """
    The ErrorInfo class is used to store an error that has occurred in
    a module. There are serveral types of errors:
        ES_ERR
        ES_CLEANUP_ERR
        ES_REPAIRED_ERR

    and each in turn has some associated data, to provide information about
    that error.
    """
    def __init__(self, mod_id, error_type):
        """ Initialize with a specific module id string and error type """
        if (error_type not in VALID_ERROR_TYPES):
            raise ValueError("Invalid error_type parameter: [%s]" % error_type)
        if (mod_id == ""):
            raise ValueError("Invalid mod_id parameter: [%s]" % mod_id)
        self._mod_id = mod_id
        self._error_type = error_type
        # use a simple dictionary for the data
        self.error_data = {}
        # append this object to the internal list of errors
        _ERRORS.append(self)

    def get_mod_id(self):
        """ Return the module id string """
        return self._mod_id

    def get_error_type(self):
        """ Return the error type """
        return self._error_type

    def set_error_data(self, error_data_type, error_value):
        """
        Add some error data to the ErrorInfo, by putting it in the
        error_data dictionary.
        The error_value param must be of the correct object type
        relating to error_data_type.
        Raises:
          RuntimeError for type mismatch in error_value parameter
          ValueError for invalid error_data_type paramater
        Returns 1 if the data was set, 0 otherwise.
        """
        if (error_data_type in INTEGER_DATA_TYPES):
            if (not isinstance(error_value, int)):
                raise RuntimeError("Invalid integer for ErrorInfo data: [%s]" %
                      error_value)
        elif (error_data_type in STRING_DATA_TYPES):
            if (not isinstance(error_value, str)):
                raise RuntimeError("Invalid string for ErrorInfo data: [%s]" %
                      error_value)
        elif (error_data_type in EXCEPTION_DATA_TYPES):
            if (not isinstance(error_value, BaseException)):
                raise RuntimeError("Invalid exception for ErrorInfo data: [%s]" 
                      % str(error_value))
        else:
            raise ValueError("Invalid error_data_type parameter: [%s]" %
                  error_data_type)

        self.error_data[error_data_type] = error_value

    def get_error_data_by_type(self, error_data_type):
        """ Get the error data value for the given data type """
        if (error_data_type in self.error_data):
            return self.error_data[error_data_type]
        else:
            return None

    def __str__(self):
        """Provide a human-readable version of this object."""
        ret_str = "==================================\n"
        ret_str += "Mod Id    = %s\n" % self._mod_id
        ret_str += "Err Type  = %d\n" % self._error_type
        ret_str += "Err Data  = \n"
        for key in self.error_data.keys():
            ret_str += "    ---------------------------------\n"
            ret_str += "    elem_type  = %s\n" % key
            ret_str += "    error_value  = %s\n" % self.error_data[key]
            ret_str += "    ---------------------------------\n"
        ret_str += "==================================\n"
        return ret_str

    # mod_id is a read-only property whose getter function is get_mod_id()
    mod_id = property(get_mod_id)

    # error_type is a read-only property whose getter function is
    # get_error_type()
    error_type = property(get_error_type)

# The best way to implement a Singleton in Python is to simply use the
# module it self, with function definitions, since it's the only way to
# absolutely ensure that there is 1, and only 1, instance if the data.


def get_all_errors():
    """
    Get a list of all the ErrorInfo objs currently known to the error service.
    """
    return _ERRORS


def clear_error_list():
    """
    Clear the current list of errors in the error service.
    """
    # pylint: disable-msg=W0603
    global _ERRORS
    _ERRORS = []


def clear_error_list_by_mod_id(mod_id):
    """
    Clear the current list of errors that have the given module id.
    """
    global _ERRORS
    _ERRORS = filter(lambda x: x.mod_id != mod_id, _ERRORS)


def get_errors_by_type(error_type):
    """
    Returns a list of ErrorInfo objects that have the given error_type
    """
    new_list = []
    for elem in _ERRORS:
        if (elem.error_type == error_type):
            new_list.append(elem)
    return new_list


def get_errors_by_mod_id(mod_id):
    """
    Returns a list of ErrorInfo objects that have the given module id.
    """
    new_list = []
    for elem in _ERRORS:
        if (elem.mod_id == mod_id):
            new_list.append(elem)
    return new_list


def __dump_all_errors__():
    """ Dump to stdout a human readable version of all errors known """
    errs = get_all_errors()
    # @type errs list
    if (errs):
        for err in errs:
            print err
    else:
        print "No Errors"

if __name__ == "__main__":
    # Create some ErrorInfo, and dump it.
    # pylint: disable-msg=C0103
    test_err = ErrorInfo("mod1", liberrsvc.ES_ERR)
    test_err.set_error_data(liberrsvc.ES_DATA_ERR_NUM, 13)
    test_err.set_error_data(liberrsvc.ES_DATA_FAILED_STR, "Failed here")
    test_err = ErrorInfo("mod2", liberrsvc.ES_CLEANUP_ERR)
    test_err.set_error_data(liberrsvc.ES_DATA_ERR_NUM, 1)
    test_err.set_error_data(liberrsvc.ES_DATA_FAILED_STR,
        "Do some cleanup here")
    test_err = ErrorInfo("mod2", liberrsvc.ES_REPAIRED_ERR)
    test_err.set_error_data(liberrsvc.ES_DATA_ERR_NUM, 2)
    test_err.set_error_data(liberrsvc.ES_DATA_FAILED_STR, "Repaired here")
    test_err.set_error_data(liberrsvc.ES_DATA_EXCEPTION,
                            TypeError("TestError"))

    __dump_all_errors__()
    print "Getting ES_REPAIRED_ERR errors:"
    for err in get_errors_by_type(liberrsvc.ES_REPAIRED_ERR):
        print err.__str__()

    print "Getting mod2 related errors:"
    for err in get_errors_by_mod_id("mod2"):
        print err.__str__()

    print "\nClearing error list..."
    clear_error_list()
    __dump_all_errors__()

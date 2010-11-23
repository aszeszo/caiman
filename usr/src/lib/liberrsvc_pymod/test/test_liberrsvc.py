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

# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.

''' Test code for unit testing of the errsvc module.  '''

import sys
import platform
import unittest

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc


class error_service(unittest.TestCase):
    '''This class tests the functions of module errsvc.'''

    def setUp(self):
        self.mod_id = 'mod1'
        self.error_types = [liberrsvc.ES_ERR,
                           liberrsvc.ES_CLEANUP_ERR,
                           liberrsvc.ES_REPAIRED_ERR]
        self.num_err_types = len(self.error_types)

    def test_create_error_info(self):                                          
        '''Testing: ErrorInfo instantiation.'''

        for error_type in self.error_types:
            test_error = errsvc.ErrorInfo(self.mod_id, error_type)
            self.assertEqual(test_error.get_mod_id(), self.mod_id)
            self.assertEqual(test_error.get_error_type(), error_type)

    def test_get_all_errors(self):
        '''Testing: get_all_errors().'''

        errsvc.clear_error_list()
        for error_type in self.error_types:
            errsvc.ErrorInfo(self.mod_id, error_type)

        errors = errsvc.get_all_errors()

        for error in errors:
            mod_id = error.get_mod_id()
            error_type = error.get_error_type()
            self.assertEqual(mod_id, self.mod_id)
            self.assertEqual(error_type, self.error_types[error_type])

    def test_clear_error_list(self):
        '''Testing: clear_error_list().'''

        # Make sure there is some error stored,
        errsvc.ErrorInfo(self.mod_id, self.error_types[0])

        # before clearing the error list.
        errsvc.clear_error_list()
        errors = errsvc.get_all_errors()

        self.assertEqual(len(errors), 0)

    def test_get_errors_by_type(self):
        '''Testing: get_errors_by_type(error_type).'''

        # Test if it returns the error/s expected, by creating three
        # errors of each error type and testing each step.
        errsvc.clear_error_list()
        for c in range(self.num_err_types):
            for n in range(self.num_err_types):
                errsvc.ErrorInfo(self.mod_id, self.error_types[c])
                errors = errsvc.get_errors_by_type(self.error_types[c])

                self.assertEqual(len(errors), n+1)

        # Test if it returns an empty list if there are no errors. 
        errsvc.clear_error_list()
        errors = errsvc.get_errors_by_type(self.error_types)

        self.assertEqual(len(errors), 0)

    def test_get_errors_by_mod_id(self):
        '''Testing: get_errors_by_mod_id(mod_id).'''

        # Test if it returns the error/s expected, by creating three
        # errors with same mod_id and testing each step.
        errsvc.clear_error_list()
        for c in range(self.num_err_types):
            errsvc.ErrorInfo(self.mod_id, self.error_types[c])
            errors = errsvc.get_errors_by_mod_id(self.mod_id)
 
            self.assertEqual(len(errors), c+1)

        # Test if it returns an empty list if there are no errors. 
        errsvc.clear_error_list()
        errors = errsvc.get_errors_by_type(self.error_types)

        self.assertEqual(len(errors), 0)


class error_info(unittest.TestCase):
    '''
    This class tests the functions of the class ErrorInfo in 
    module errsvc.
    '''

    def setUp(self):
        self.mod_id = 'mod1'
        self.error_type = liberrsvc.ES_ERR
        self.test_error = errsvc.ErrorInfo(self.mod_id, 
                                                   self.error_type)
        self.err_data_type = liberrsvc.ES_DATA_OP_STR
        self.error_value = 'testing data'

    def test_get_mod_id(self):
        '''Testing: get_mod_id().'''

        mod_id = self.test_error.get_mod_id()
        self.assertEqual(mod_id, self.mod_id)

    def test_get_error_type(self):
        '''Testing: get_error_type().'''

        err_type = self.test_error.get_error_type()
        self.assertEqual(err_type, self.error_type)

    def test_error_data(self):
        '''
        Testing: set_error_data(error_data_type, error_value) 
                 and get_error_data_by_type(error_data_type).
        '''

        self.test_error.set_error_data(self.err_data_type, self.error_value)
        err_value = self.test_error.get_error_data_by_type(self.err_data_type)

        self.assertEqual(err_value, self.error_value)
 

if __name__ == "__main__":
    unittest.main()   

#!/usr/bin/python2.6
#
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''Some unit tests to cover engine functionality'''

import unittest

from osol_install.install_utils import get_argspec


class InstallCommonTest(unittest.TestCase):

    ''' Test utility functions used by the engine ''' 
    
    def test_get_argspec_not_callable(self):
        '''Tests get_argspec raise TypeError for non-callable'''
        
        self.assertRaises(TypeError, get_argspec, None)
    
    def test_get_argspec_function(self):
        '''Tests get_argspec returns an ArgSpec for functions'''
        
        def basic_function(myarg, mykwarg=None, *args, **kwargs):
            ''' basic function for testing '''
            pass
        
        lambda_func = lambda x: x * 2
        
        try:
            get_argspec(basic_function)
        except TypeError as err:
            self.fail("basic_function check failed:"
                      " get_argspec raised '%s'" % err)
        
        try:
            get_argspec(lambda_func)
        except TypeError as err:
            self.fail("lamda check failed: get_argspec"
                      " raised '%s'" % err)
    
    def test_get_argspec_class_object(self):
        '''Tests get_argspec returns an ArgSpec for class constructors'''
        class BasicClass(object):
            ''' basic class for testing '''
            def __init__(self, myarg, mykwarg=None, *args, **kwargs):
                ''' Instantiates the BasicClass class '''
                pass
        
        try:
            get_argspec(BasicClass)
        except TypeError as err:
            self.fail("Class check failed: get_argspec" " raised '%s'" % err)
    
    def test_getargspec_callable_class(self):
        '''Tests get_argspec returns an ArgSpec for callable class instances'''
        
        class CallableClass(object):
            ''' CallableClass used for testing '''
            def __call__(self, myarg, mykwarg=None, *args, **kwargs):
                pass
        
        instance = CallableClass()
        
        try:
            get_argspec(instance)
        except TypeError as err:
            self.fail("Callable class check failed: get_argspec"
                      " raised '%s'" % err)


if __name__ == '__main__':
    unittest.main()

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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#


'''
Representation of a user on the system
'''

import os
from osol_install.install_utils import encrypt_password

class UserInfo(object):
    '''Describes a single user's login data'''
    
    MAX_PASS_LEN = os.sysconf('SC_PASS_MAX')
    MAX_USERNAME_LEN = os.sysconf('SC_LOGNAME_MAX')

    def __init__(self, real_name=None, login_name=None, password=None,
                 encrypted=False, is_role=False):
        self.real_name = real_name
        self.login_name = login_name
        self._password = None
        self.passlen = None
        self.set_password(password, encrypted=encrypted)
        self.is_role = is_role
    
    def is_valid(self):
        '''This UserInfo is valid if and only if both the username
        and password are valid
        
        '''
        return self.is_username_valid() and self.is_password_valid()
    
    def is_username_valid(self):
        '''Returns True if self.login_name is a non-empty string'''
        return bool(self.login_name)
    
    def get_password(self):
        '''Returns the (encrypted) password'''
        return self._password
    
    def set_password(self, password, encrypted=False):
        '''Set the password, encrypting it unless this function
        is explicitly called with encrypted=True
        
        '''
        if password is None:
            self._password = None
            self.passlen = 0
            return
        
        if not encrypted:
            self._password = encrypt_password(password)
            self.passlen = len(password)
        else:
            self._password = password
            self.passlen = 16
    
    password = property(get_password, set_password)
    
    def is_password_valid(self):
        '''Empty string is valid; 'None' indicates that password 
        needs to be set first
        
        '''
        return (self._password is not None)
    
    def __str__(self):
        result = ["User Info(%s):" % self.login_name]
        result.append("Real name: %s" % self.real_name)
        result.append("Login name: %s" % self.login_name)
        result.append("Is Role: %s" % str(self.is_role))
        return "\n".join(result)

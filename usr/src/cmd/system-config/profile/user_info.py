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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#


'''
Representation of a user on the system
'''

import os
import pwd
import re

from osol_install.install_utils import encrypt_password
from solaris_install.sysconfig import _
from solaris_install.sysconfig.profile import SMFConfig, SMFInstance, \
                                              SMFPropertyGroup, USER_LABEL

'''UserInfo exceptions'''


class PasswordInvalid(StandardError):
    ''' Raised if password is not valid'''
    pass


class UsernameInvalid(StandardError):
    ''' Raised if user name does not validate'''
    pass


class LoginInvalid(StandardError):
    ''' Raised if user login is not valid'''
    pass


class UserInfoContainer(SMFConfig):
    '''Container for root and user accounts'''

    LABEL = USER_LABEL

    def __init__(self, root_account=None, user_account=None):
        super(UserInfoContainer, self).__init__(self.LABEL)
        
        self.root = root_account
        self.user = user_account

    def to_xml(self):
        smf_svc_config = SMFConfig('system/config-user')
        smf_svc_config_default = SMFInstance('default')
        smf_svc_config.insert_children(smf_svc_config_default)
        smf_svc_config_default.insert_children(self.root)
        smf_svc_config_default.insert_children(self.user)

        return [smf_svc_config.get_xml_tree()]


class UserInfo(SMFPropertyGroup):
    '''Describes a single user's login data'''
    
    MAX_PASS_LEN = os.sysconf('SC_PASS_MAX')
    MAX_USERNAME_LEN = os.sysconf('SC_LOGNAME_MAX')
    
    LABEL = USER_LABEL
    
    def __init__(self, real_name=None, login_name=None, password=None,
                 encrypted=False, gid=None, shell=None, is_role=False,
                 roles=None, profiles=None, sudoers=None,
                 autohome=None, expire=None):
        super(UserInfo, self).__init__(self.LABEL)
        
        self.real_name = real_name
        self.login_name = login_name
        self._password = None
        self.passlen = None
        self.set_password(password, encrypted=encrypted)
        self.is_role = is_role
        self.gid = gid
        self.shell = shell
        self.roles = roles
        self.profiles = profiles
        self.sudoers = sudoers
        self.autohome = autohome
        self.expire = expire
    
    def is_configured(self):
        '''This UserInfo is valid if and only if both the username
        and password are valid
        
        '''
        return self.is_username_configured() and self.is_password_configured()
    
    def is_username_configured(self):
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
    
    def is_password_configured(self):
        '''Empty string is valid; 'None' indicates that password
        needs to be set first
        
        '''
        return (self._password is not None)
    
    def __repr__(self):
        result = ["User Info(%s):" % self.login_name]
        result.append("Real name: %s" % self.real_name)
        result.append("Login name: %s" % self.login_name)
        result.append("Is Role: %s" % str(self.is_role))
        if self.expire is not None:
            result.append("Is Expired: %s" % self.expire)
        return "\n".join(result)
    
    def to_xml(self):
        self.delete_children()

        #
        # If user or root account was not configured, do not generate
        # related XML portion in SC manifest.
        #
        if not self.is_configured():
            return None
        
        if self.is_role:
            type_ = "role"
        else:
            type_ = "normal"

        if self.login_name == "root":
            self.pg_name = "root_account"
            self.add_props(login=self.login_name, password=self.password,
                           type=type_)

            # Expire
            if self.expire is not None:
                self.add_props(expire=str(self.expire))
        else:
            self.pg_name = "user_account"
            #
            # Some parameters are not explicitly specified. Instead
            # they are automatically determined during first boot of
            # installed system:
            #
            #  user ID - useradd(1m) determines the default value
            #  mountpoint of home directory
            #  name of home directory ZFS dataset
            #
            self.add_props(login=self.login_name, password=self.password,
                           type=type_)

            # Expire
            if self.expire is not None:
                self.add_props(expire=str(self.expire))

            # Description
            if self.real_name:
                self.add_props(description=self.real_name)

            # Group ID
            if self.gid:
                self.add_props(gid=self.gid)

            # User's shell
            if self.shell:
                self.add_props(shell=self.shell)

            # roles
            if self.roles:
                self.add_props(roles=self.roles)

            # profiles
            if self.profiles:
                self.add_props(profiles=self.profiles)

            # entry in sudoers(4) file
            if self.sudoers:
                self.add_props(sudoers=self.sudoers)

            # entry in /etc/auto_home file
            if self.autohome:
                self.add_props(autohome=self.autohome)

        return super(UserInfo, self).to_xml()
    
    @classmethod
    def from_xml(cls, xml_node):
        return None
    
    @classmethod
    def can_handle(cls, xml_node):
        return False


def validate_username(user_str, blank_ok=True):
    '''Ensure username complies with following rules
       - username can contain characters from set of alphabetic characters,
         numeric characters, period (.), underscore (_), and hyphen (-).
       - username starts with a letter.

    Raises UsernameInvalid if provided user name is not valid,
    otherwise returns True'''

    #
    # consider empty string as a valid value, since it serves
    # as an indicator that user account will not be created
    #
    if blank_ok and not user_str:
        return True

    if not user_str:
        raise UsernameInvalid(_("Username must not be blank"))

    # verify that username starts with alphabetic character
    if not user_str[0].isalpha():
        raise UsernameInvalid(_("Username must start with a letter"))

    # verify that username contains only allowed characters
    if re.search(r"^[a-zA-Z][\w\-.]*$", user_str) is None:
        raise UsernameInvalid(_("Invalid character"))
    return True


def validate_login(login_str):
    '''Ensure the username is not one of the names already in /etc/passwd
    Raises LoginInvalid if login_str is an already existent user (e.g.,
    'root' or 'nobody') otherwise returns True
    
    '''
    forbidden_logins = ['nobody', 'noaccess', 'nobody4']
    try:
        uid = pwd.getpwnam(login_str).pw_uid
        if uid <= 99 or login_str in forbidden_logins:
            # We are trying to add existing system user or we are trying
            # to add nobody, noaccess or nobody4
            raise LoginInvalid("'%s' cannot be used" % login_str)
        else:
            return True
    except KeyError:
        # KeyError raised if the given user doesn't exist; in which
        # case, it's safe to apply
        return True


def validate_password(password):
    '''validates the password entered'''
    # check the length
    if not password or len(password) <= 0:
        raise PasswordInvalid(_('Password must be entered.'))
    elif len(password) < 6:
        raise PasswordInvalid(_('Password must contain at least 6 '
                                'characters.'))
    else:
        # check that the password contains characters
        # and digit or special characters
        has_char = has_digit = has_special = False
        for char in password:
            if char.isalpha():
                has_char = True
            elif char.isdigit():
                has_digit = True
            else:
                has_special = True
        if not has_char:
            raise PasswordInvalid(_('Password must contain 1 alphabetical '
                                    'character.'))
        elif not has_digit and not has_special:
            raise PasswordInvalid(_('Password must contain 1 digit/special '
                                    'character.'))

    return True

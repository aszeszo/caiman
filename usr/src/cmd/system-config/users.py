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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Set root password and primary user data
'''

import logging

from solaris_install import CalledProcessError, run
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig import _, SCI_HELP
import solaris_install.sysconfig.profile
from solaris_install.sysconfig.profile.user_info import LoginInvalid, \
     PasswordInvalid, UserInfo, UserInfoContainer, UsernameInvalid, \
     validate_login, validate_username, validate_password
from terminalui.base_screen import BaseScreen, UIMessage
from terminalui.edit_field import EditField, PasswordField
from terminalui.error_window import ErrorWindow
from terminalui.list_item import ListItem
from terminalui.window_area import WindowArea
from terminalui.i18n import textwidth


LOGGER = None

# Consumed CLIs
ZFS = "/usr/sbin/zfs"


class UserScreen(BaseScreen):
    '''Allow user to set:
    - root password
    - user real name
    - user login
    - user password
    
    '''
    
    HEADER_TEXT = _("Users")
    INTRO_SHOW_USER = _("Define a root password for the system and user "
                        "account for yourself.")
    INTRO_HIDE_USER = _("Define a root password for the system. Creation "
                        "of user account is disabled. See Help for "
                        "additional information.")
    ROOT_TEXT = _("System Root Password")
    ROOT_LABEL = _("Root password:")
    CONFIRM_LABEL = _("Confirm password:")
    USER_TEXT = _("Create a user account")
    NAME_LABEL = _("Your real name:")
    USERNAME_LABEL = _("Username:")
    USER_PASS_LABEL = _("User password:")
    
    HELP_DATA = (SCI_HELP + "/%s/users.txt", _("Users"))
    
    PASS_SCREEN_LEN = 16  # also used as column width for user input
    ITEM_OFFSET = 2
    
    def __init__(self, main_win, show_user_account=None):
        global LOGGER
        if LOGGER is None:
            LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
        
        super(UserScreen, self).__init__(main_win)
        self.max_text_len = (self.win_size_x - UserScreen.PASS_SCREEN_LEN -
                             UserScreen.ITEM_OFFSET) / 2
        max_field = max(textwidth(UserScreen.ROOT_LABEL),
                        textwidth(UserScreen.CONFIRM_LABEL),
                        textwidth(UserScreen.NAME_LABEL),
                        textwidth(UserScreen.USERNAME_LABEL),
                        textwidth(UserScreen.USER_PASS_LABEL))
        self.text_len = min(max_field + 1, self.max_text_len)
        self.list_area = WindowArea(1, self.text_len, 0,
                                    UserScreen.ITEM_OFFSET)
        scrollable_columns = UserInfo.MAX_PASS_LEN + 1
        self.edit_area = WindowArea(1, UserScreen.PASS_SCREEN_LEN + 1,
                                    0, self.text_len,
                                    scrollable_columns=scrollable_columns)
        self.username_edit_area = WindowArea(1, UserScreen.PASS_SCREEN_LEN + 1,
                              0, self.text_len,
                              scrollable_columns=UserInfo.MAX_USERNAME_LEN + 1)
        err_x_loc = 2 * self.max_text_len - self.text_len
        err_width = (self.text_len + UserScreen.PASS_SCREEN_LEN)
        self.error_area = WindowArea(1, err_width, 0, err_x_loc)
        self.root = None
        self.user = None
        self.root_pass_list = None
        self.root_pass_edit = None
        self.root_pass_err = None
        self.root_confirm_err = None
        self.root_confirm_list = None
        self.root_confirm_edit = None
        self.real_name_err = None
        self.real_name_list = None
        self.real_name_edit = None
        self.username_err = None
        self.username_list = None
        self.username_edit = None
        self.user_pass_err = None
        self.user_pass_list = None
        self.user_pass_edit = None
        self.user_confirm_err = None
        self.user_confirm_list = None
        self.user_confirm_edit = None

        #
        # If show_user_account is True, complete Users screen will be
        # displayed (root password edit fields as well as widgets related
        # to creating initial user account). Otherwise, widgets for initial
        # user account are hidden.
        #
        # If not initialized explicitly by caller (e.g. text installer),
        # show_user_account is set to True only if all conditions needed
        # for successful creation of user account are met.
        #
        # In particular, existence of parent of home ZFS dataset is checked,
        # since if parent of home ZFS dataset was missing, then
        # svc:/system/config-user smf service (responsible for configuring
        # root and user accounts) would fail to create user account. As
        # a result of that, the whole system would end up in maintenance mode.
        #
        self.show_user_account = show_user_account
        if self.show_user_account is None:
            self.show_user_account = self.home_zfs_parent_exists()

    def _show(self):
        '''Display the user name, real name, and password fields'''
        
        sc_profile = solaris_install.sysconfig.profile.from_engine()

        #
        # Create UserInfo instances holding information about root and user
        # accounts.
        #
        if sc_profile.users is None:
            #
            # Assume root is a normal account. It will be changed to a role
            # if the user account is created.
            #
            root = UserInfo(login_name="root", is_role=False)

            #
            # Initialize attributes of user account which can't be configured
            # on screens.
            #
            user = UserInfo(gid=10, shell="/usr/bin/bash", roles="root",
                            profiles="System Administrator",
                            sudoers="ALL=(ALL) ALL")
            sc_profile.users = UserInfoContainer(root, user)

        self.root = sc_profile.users.root
        self.user = sc_profile.users.user
        
        LOGGER.debug("Root: %s", self.root)
        LOGGER.debug("User: %s", self.user)
        
        root_set = (self.root.passlen != 0)
        user_set = (self.user.passlen != 0)
        
        y_loc = 1
        
        if self.show_user_account:
            intro_text = UserScreen.INTRO_SHOW_USER
        else:
            intro_text = UserScreen.INTRO_HIDE_USER

        self.center_win.add_paragraph(intro_text, y_loc, 1,
                                      y_loc + 2, self.win_size_x - 1)
        
        y_loc += 3
        self.center_win.add_text(UserScreen.ROOT_TEXT, y_loc, 1,
                                 self.win_size_x - 1)
        
        y_loc += 2
        self.error_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        self.root_pass_err = ErrorWindow(self.error_area,
                                         window=self.center_win)
        self.root_pass_list = ListItem(self.list_area, window=self.center_win,
                                       text=UserScreen.ROOT_LABEL)
        self.root_pass_edit = PasswordField(self.edit_area,
                                            window=self.root_pass_list,
                                            error_win=self.root_pass_err,
                                            fill=root_set)
        
        y_loc += 1
        self.error_area.y_loc = y_loc
        self.list_area.y_loc = y_loc
        self.root_confirm_err = ErrorWindow(self.error_area,
                                            window=self.center_win)
        self.root_confirm_list = ListItem(self.list_area,
                                          window=self.center_win,
                                          text=UserScreen.CONFIRM_LABEL)
        self.root_confirm_edit = PasswordField(self.edit_area,
                                               window=self.root_confirm_list,
                                               fill=root_set,
                                               on_exit=pass_match,
                                               error_win=self.root_confirm_err)
        rc_edit_kwargs = {"linked_win": self.root_pass_edit}
        self.root_confirm_edit.on_exit_kwargs = rc_edit_kwargs

        # User account disabled, do not display related widgets.
        if not self.show_user_account:
            self.main_win.do_update()
            self.center_win.activate_object(self.root_pass_list)
            return

        y_loc += 2
        self.center_win.add_text(UserScreen.USER_TEXT, y_loc, 1,
                                 self.win_size_x - 1)
        
        y_loc += 2
        self.list_area.y_loc = y_loc
        self.error_area.y_loc = y_loc
        self.real_name_err = ErrorWindow(self.error_area,
                                         window=self.center_win)
        self.real_name_list = ListItem(self.list_area, window=self.center_win,
                                       text=UserScreen.NAME_LABEL)
        self.real_name_edit = EditField(self.edit_area,
                                        window=self.real_name_list,
                                        error_win=self.real_name_err,
                                        text=self.user.real_name)
        
        y_loc += 1
        self.list_area.y_loc = y_loc
        self.error_area.y_loc = y_loc
        self.username_err = ErrorWindow(self.error_area,
                                        window=self.center_win)
        self.username_list = ListItem(self.list_area,
                                      window=self.center_win,
                                      text=UserScreen.USERNAME_LABEL)
        self.username_edit = EditField(self.username_edit_area,
                                       window=self.username_list,
                                       validate=username_valid,
                                       error_win=self.username_err,
                                       on_exit=login_valid,
                                       text=self.user.login_name)
        
        y_loc += 1
        self.list_area.y_loc = y_loc
        self.error_area.y_loc = y_loc
        self.user_pass_err = ErrorWindow(self.error_area,
                                         window=self.center_win)
        self.user_pass_list = ListItem(self.list_area, window=self.center_win,
                                       text=UserScreen.USER_PASS_LABEL)
        self.user_pass_edit = PasswordField(self.edit_area,
                                            window=self.user_pass_list,
                                            error_win=self.user_pass_err,
                                            fill=user_set)
        
        y_loc += 1
        self.list_area.y_loc = y_loc
        self.error_area.y_loc = y_loc
        self.user_confirm_err = ErrorWindow(self.error_area,
                                            window=self.center_win)
        self.user_confirm_list = ListItem(self.list_area,
                                          window=self.center_win,
                                          text=UserScreen.CONFIRM_LABEL)
        self.user_confirm_edit = PasswordField(self.edit_area,
                                               window=self.user_confirm_list,
                                               on_exit=pass_match,
                                               error_win=self.user_confirm_err,
                                               fill=user_set)
        uc_edit_kwargs = {"linked_win": self.user_pass_edit}
        self.user_confirm_edit.on_exit_kwargs = uc_edit_kwargs
        
        self.main_win.do_update()
        self.center_win.activate_object(self.root_pass_list)
    
    def on_change_screen(self):
        '''Store entered information into data object cache.'''

        if self.root_pass_edit.modified:
            if self.root_pass_edit.compare(self.root_confirm_edit):
                self.root.password = self.root_pass_edit.get_text()
            else:
                self.root.password = ""
        
        if self.root.password is None:
            self.root.password = ""
        
        self.root_pass_edit.clear_text()
        self.root_confirm_edit.clear_text()

        #
        # User account disabled, do not store related info into data object
        # cache.
        #
        if not self.show_user_account:
            return

        self.user.real_name = self.real_name_edit.get_text()
        self.user.login_name = self.username_edit.get_text()

        # If user account is to be created, configure root account as a role.
        self.root.is_role = bool(self.user.login_name)
        
        if self.user_pass_edit.modified:
            if self.user_pass_edit.compare(self.user_confirm_edit):
                self.user.password = self.user_pass_edit.get_text()
            else:
                self.user.password = ""
        
        if self.user.password is None:
            self.user.password = ""
        
        self.user_pass_edit.clear_text()
        self.user_confirm_edit.clear_text()
    
    def validate(self):
        '''Check for mismatched passwords, bad login names, etc.'''
        # Note: the Root and User password fields may be filled with
        # asterisks if the user previously invoked this screen.  Therefore,
        # if not empty we check their modified flags before validating the
        # contents.

        if self.root_pass_edit.modified:
            root_pass_set = bool(self.root_pass_edit.get_text())
        else:
            root_pass_set = (self.root.passlen != 0)      

        # Root password is mandatory and, if modified, must be valid
        if not root_pass_set or self.root_pass_edit.modified:
            pass_valid(self.root_pass_edit,
                msg_prefix=UserScreen.ROOT_LABEL + " ")
        # Root password confirmation must match original Root password
        if not self.root_pass_edit.compare(self.root_confirm_edit):
            raise UIMessage(_("Root passwords don't match"))

        # User account disabled, skip related validation steps.
        if not self.show_user_account:
            return

        if self.user_pass_edit.modified:
            user_pass_set = bool(self.user_pass_edit.get_text())
        else:
            user_pass_set = (self.user.passlen != 0)
        
        login_name = self.username_edit.get_text()
        LOGGER.debug("login_name=%s", login_name)
        real_name = self.real_name_edit.get_text()
        LOGGER.debug("real_name=%s", real_name)
        
        # Username (if specified) must be valid
        login_valid(self.username_edit)

        if login_name:
            # If Username was entered then:
            # - User password is mandatory and, if modified, must be valid
            # - User password confirmation must match original User password
            if not user_pass_set or self.user_pass_edit.modified:
                pass_valid(self.user_pass_edit,
                    msg_prefix=UserScreen.USER_PASS_LABEL + " ")
            if not self.user_pass_edit.compare(self.user_confirm_edit):
                raise UIMessage(_("User passwords don't match"))
        else:
            # If either Real name or User password are specified then
            # Username must also be specified
            if real_name or user_pass_set:
                raise UIMessage(_("Enter username or clear all user "
                                  "account fields"))

    def home_zfs_parent_exists(self):
        '''Return True if parent of to-be-created home ZFS dataset exists.
        Otherwise, return False.

        Home ZFS dataset is created in form of <root_pool>/export/home/<login>
        with mountpoint /export/home/<login> inherited from parent dataset.

        The check verifies that ZFS dataset with to-be-inherited /export/home
        mountpoint exists.
        '''

        # obtain mountpoints for all existing ZFS datasets
        cmd = [ZFS, "list", "-H", "-o", "mountpoint"]
        try:
            stdout_stderr = run(cmd, logger=LOGGER)
        except CalledProcessError:
            LOGGER.warn("Could not determine if parent of home ZFS dataset "
                        "exists.")
            return False

        mountpoint_set = set(stdout_stderr.stdout.splitlines())
        # Account for ZFS mountpoints with as well as without trailing slash.
        if mountpoint_set.isdisjoint(set(["/export/home", "/export/home/"])):
            LOGGER.info("Parent of home ZFS dataset does not exist, creation "
                         "of user account disabled.")
            return False

        LOGGER.info("Parent of home ZFS dataset exists, creation of user "
                     "account enabled.")
        return True


def username_valid(edit_field):
    '''Validate username'''
    try:
        validate_username(edit_field.get_text())
    except UsernameInvalid, reason:
        raise UIMessage(reason[0])
    return True


def login_valid(edit_field):
    '''Validate login name'''
    try:
        validate_login(edit_field.get_text())
    except LoginInvalid, reason:
        raise UIMessage(reason[0])
    return True


def pass_valid(edit_field, msg_prefix=""):
    '''Validate password'''
    try:
        validate_password(edit_field.get_text())
    except PasswordInvalid, reason:
        raise UIMessage(msg_prefix + reason[0])
    return True


def pass_match(pw_field, linked_win=None):
    '''Make sure passwords match'''
    if linked_win is None or pw_field.compare(linked_win):
        return True
    else:
        pw_field.clear_text()
        linked_win.clear_text()
        raise UIMessage(_("Passwords don't match"))

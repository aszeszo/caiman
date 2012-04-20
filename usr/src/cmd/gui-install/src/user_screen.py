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
User Screen for GUI Install app
'''

import atk
import gtk
import string

from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.gui_install_common import modal_dialog, \
    GLADE_ERROR_MSG
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.sysconfig.profile.user_info import UsernameInvalid, \
    LoginInvalid, PasswordInvalid, validate_username, validate_login, \
    validate_password


class UserScreen(BaseScreen):
    '''User Screen class'''
    MAXHOSTNAMELEN = 256

    def __init__(self, builder):
        '''Initialize the User Screen class'''
        super(UserScreen, self).__init__(builder)
        self.name = "User Screen"

        self.saved_msg = None
        self.validation_occurring = False
        self.saved_msg_type = None

        self.user_name = self.builder.get_object("usernameentry")
        self.login_name = self.builder.get_object("loginnameentry")
        self.password = self.builder.get_object("userpassword1entry")
        self.verify = self.builder.get_object("userpassword2entry")
        self.hostname = self.builder.get_object("hostnameentry")
        self.loginnameinfoimage = self.builder.get_object(
            "loginnameinfoimage")
        self.loginnameinfolabel = self.builder.get_object(
            "loginnameinfolabel")
        self.userpasswordinfoimage = self.builder.get_object(
            "userpasswordinfoimage")
        self.userpasswordinfolabel = self.builder.get_object(
            "userpasswordinfolabel")
        self.hostnameinfoimage = self.builder.get_object(
            "hostnameinfoimage")
        self.hostnameinfolabel = self.builder.get_object(
            "hostnameinfolabel")
        loginnamelabel = self.builder.get_object("loginnamelabel")
        userpasswordlabel1 = self.builder.get_object("userpassword1label")
        userpasswordlabel2 = self.builder.get_object("userpassword2label")
        userpasswordentry = self.builder.get_object("userpassword2entry")
        hostnamelabel = self.builder.get_object("hostnamelabel")

        if None in [self.user_name, self.login_name, self.password,
            self.verify, self.hostname, self.loginnameinfoimage,
            self.loginnameinfolabel, self.userpasswordinfoimage,
            self.userpasswordinfolabel, self.hostnameinfoimage,
            self.hostnameinfolabel, loginnamelabel, userpasswordlabel1,
            userpasswordlabel2, userpasswordentry, hostnamelabel]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        # Setup Accessibility relationship for the loginname
        atk_loginnamelabel = loginnamelabel.get_accessible()
        self.atk_loginnameinfolabel = self.loginnameinfolabel.get_accessible()
        atk_parent = self.login_name.get_accessible()

        relation_set = atk_parent.ref_relation_set()
        relation = atk.Relation(
                       (atk_loginnamelabel, self.atk_loginnameinfolabel,),
                       atk.RELATION_LABELLED_BY)
        relation_set.add(relation)

        # Setup Accessibility relationship for the password
        self.atk_passwordinfolabel = \
            self.userpasswordinfolabel.get_accessible()
        atk_userpasswordlabel = userpasswordlabel1.get_accessible()
        atk_parent = self.password.get_accessible()

        relation_set = atk_parent.ref_relation_set()
        relation = atk.Relation(
                       (atk_userpasswordlabel, self.atk_passwordinfolabel,),
                       atk.RELATION_LABELLED_BY)
        relation_set.add(relation)

        atk_userpasswordlabel = userpasswordlabel2.get_accessible()
        atk_parent = userpasswordentry.get_accessible()

        relation_set = atk_parent.ref_relation_set()
        relation = atk.Relation(
                       (atk_userpasswordlabel, self.atk_passwordinfolabel,),
                       atk.RELATION_LABELLED_BY)
        relation_set.add(relation)

        # Setup Accessibility relationship for the hostname
        self.atk_hostnameinfolabel = self.hostnameinfolabel.get_accessible()
        atk_hostnamelabel = hostnamelabel.get_accessible()
        atk_parent = self.hostname.get_accessible()

        relation_set = atk_parent.ref_relation_set()
        relation = atk.Relation(
                       (atk_hostnamelabel, self.atk_hostnameinfolabel,),
                       atk.RELATION_LABELLED_BY)
        relation_set.add(relation)

    def enter(self):
        '''Called when the user enters the screen by pressing the appropriate
           button (Next, Back)'''
        toplevel = self.set_main_window_content("userstoplevel")

        # Screen-specific configuration
        self.activate_stage_label("userstagelabel")

        self.user_name.grab_focus()

        self.login_name.connect("changed", self.loginname_entry_changed, None)
        self.login_name.connect("focus-out-event", self.loginname_focus_out,
                           None)

        self.password.connect("changed", self.password_changed,
                              (self.password, self.verify))
        self.password.connect("focus-out-event", self.password_focus_out,
                              (self.password, self.verify))
        self.verify.connect("focus-out-event", self.password_focus_out,
                            (self.password, self.verify))
        self.verify.connect("changed", self.password_changed,
                            (self.password, self.verify))

        self.hostname.connect("changed", self.hostname_changed, None)
        self.hostname.connect("focus-out-event", self.hostname_focus_out,
            None)

        self.set_titles(_("Users"), _(" "), None)

        self.set_back_next(back_sensitive=True, next_sensitive=True)

        toplevel.show_all()

        # hide the various error widgets
        self.loginnameinfoimage.hide_all()
        self.userpasswordinfoimage.hide_all()
        self.userpasswordinfolabel.hide_all()
        self.hostnameinfoimage.hide_all()

        return False

    def loginname_entry_changed(self, widget=None, data=None):
        '''callback for the loginname entry change event'''
        self.saved_msg = self.saved_msg_type = None

        self.loginnameinfoimage.hide_all()
        self.loginnameinfolabel.set_text('')

    def loginname_focus_out(self, widget, event, data=None):
        '''callback for the loginname focus out events, used to validate
           the loginname
        '''
        self.saved_msg = self.saved_msg_type = None

        # get the user entered value for the log-in name entry
        username = widget.get_text()

        try:
            if validate_username(username, blank_ok=False):
                self.loginnameinfoimage.hide_all()
                self.loginnameinfolabel.hide_all()
                self.atk_loginnameinfolabel.set_description('')
        except UsernameInvalid, err:
            self.loginnameinfolabel.set_markup(str(err))
            self.atk_loginnameinfolabel.set_description(str(err))
            self.saved_msg = err
            self.saved_msg_type = 'account'
            self.loginnameinfoimage.show_all()

    def password_changed(self, widget=None, data=None):
        '''callback for the user password change events'''
        self.saved_msg = self.saved_msg_type = None

        # update the label and hide the error image
        self.userpasswordinfolabel.set_text(
            _('Re-enter to check for typing errors.'))
        self.userpasswordinfolabel.show_all()
        self.userpasswordinfoimage.hide_all()

    def password_focus_out(self, widget, event, data=None):
        '''callback for the user password focus out events for the user
           password and confirm password entries.'''
        # validation might be occurring, if it is then simply return
        if self.validation_occurring:
            return

        # check if final validation is occurring
        self.saved_msg = self.saved_msg_type = None

        # data contains the user password and check password
        # widgets as a tuple
        if data is None:
            return

        user_password = data[0]
        check_password = data[1]

        if widget == user_password:
            # validate the user password
            password = user_password.get_text()
            try:
                if validate_password(password):
                    # update the label message
                    msg = _('Re-enter to check for typing errors.')
                    self.userpasswordinfolabel.set_markup(msg)
                    self.atk_passwordinfolabel.set_description(msg)
                    self.userpasswordinfolabel.show_all()
                    self.userpasswordinfoimage.hide_all()
            except PasswordInvalid, err:
                print 'Password Invalid', err
                self.saved_msg = str(err)
                self.saved_msg_type = 'password'
                self.userpasswordinfoimage.show_all()
                self.userpasswordinfolabel.set_markup(self.saved_msg)
                self.atk_passwordinfolabel.set_description(self.saved_msg)
                self.userpasswordinfolabel.show_all()
        elif widget == check_password:
            # validate that the passwords are the same
            original_password = user_password.get_text()
            verify = check_password.get_text()
            msg = None
            if not verify or len(verify) == 0:
                msg = _('Re-enter to check for typing errors.')
            elif original_password != verify:
                msg = _('The two user passwords do not match.')
            self.saved_msg = msg
            self.saved_msg_type = 'password'

            if msg:
                # passwords differ, clear the passwords and start over
                user_password.set_text('')
                check_password.set_text('')

                # update the label message with the error
                self.userpasswordinfolabel.set_markup(msg)
                self.userpasswordinfolabel.show_all()
                self.atk_passwordinfolabel.set_description(msg)

                self.saved_msg = msg
                self.saved_msg_type = 'password'

                # show the error image
                self.userpasswordinfoimage.show_all()
            else:
                # no error, so hide the label and error image
                self.userpasswordinfolabel.hide_all()
                self.userpasswordinfoimage.hide_all()
                self.atk_passwordinfolabel.set_description('')

    def hostname_changed(self, widget, data):
        '''callback for hostname change events'''
        self.saved_msg = self.saved_msg_type = None

        # hide the hostname label and error image
        self.hostnameinfolabel.hide_all()
        self.hostnameinfoimage.hide_all()

    def hostname_focus_out(self, widget, event, data):
        '''callback for hostname focus out events'''
        self.saved_msg = self.saved_msg_type = None

        # get the host name
        hostname = widget.get_text()

        # validate the hostname
        msg = self.validate_hostname(hostname, widget)
        if not msg:
            # host name is valid, no needed message
            self.hostnameinfolabel.hide_all()
            self.hostnameinfoimage.hide_all()
        else:
            # update the label message with the error
            self.hostnameinfolabel.set_markup(msg)
            self.hostnameinfolabel.show_all()
            self.hostnameinfoimage.show_all()

            self.saved_msg = msg
            self.saved_msg_type = 'host'

    def go_back(self):
        '''method from the super that deals with
           the back button being pressed'''
        pass

    def validate_hostname(self, hostname, widget):
        '''validates the hostname'''
        def valid_hostname_characters(hostname):
            '''validates the hostname characters,
               ensuring that the hostname meets the following characteristics:
                   o is alphabetic, digits, '-', '_' or '.'
               returns True if the characteristics are met or False if not
            '''
            viable = string.letters + string.digits + "-_."
            if " " in hostname or hostname.translate(None, viable):
                return False
            return True

        msg = None
        if len(hostname) == 0:
            widget.set_text('solaris')
            msg = _('<b>Error:</b> A computer name is required.')
        elif len(hostname) > self.MAXHOSTNAMELEN:
            msg = _('<b>Error:</b> Computer name exceeds maximum length.')
        elif not valid_hostname_characters(hostname):
            msg = _('<b>Error:</b> Computer name contains invalid characters.')
        elif hostname[-1] == '-' or hostname[-1] == '_' or hostname[-1] == '.':
            msg = _('<b>Error:</b> Computer name ends with invalid character.')

        return msg

    def validate(self):
        '''method from the super that deals with validating every field'''
        def error_dialog(type_msg=None, error_msg=None):
            '''displays an error dialog during validation prior to
               next screen
            '''
            msg_dict = {'account': [_('Invalid User Account'),
                                     _('Enter a Log-in name.')],
                        'password': [_('Invalid User Account'),
                                     _('Enter a user password.')],
                        'host': [_('Invalid Computer Name'),
                                     _('Enter a computer name.')],
                        'internal': [_('Internal Error'),
                                     ''],
                        'unknown': [_('Unknown'),
                                     _('Recheck entries.')]}

            message = gtk.MessageDialog(None, gtk.DIALOG_MODAL,
                                        gtk.MESSAGE_ERROR, gtk.BUTTONS_OK)

            if type_msg not in msg_dict:
                type_msg = 'unknown'
            msg = '<b>%s</b>\n\n%s\n%s' % (msg_dict[type_msg][0], error_msg,
                                           msg_dict[type_msg][1])
            message.set_markup(msg)

            # display the dialog
            message.run()
            message.destroy()

        self.validation_occurring = True
        username = self.user_name.get_text()

        if self.saved_msg:
            error_dialog(self.saved_msg_type, self.saved_msg)
            raise NotOkToProceedError(self.saved_msg)

        loginname = self.login_name.get_text()
        msg = None
        if loginname != 'jack':
            try:
                if validate_username(loginname, blank_ok=False):
                    validate_login(loginname)
            except UsernameInvalid, err:
                msg = str(err)
            except LoginInvalid, err:
                msg = str(err)
        if msg:
            self.login_name.grab_focus()
            error_dialog('account', msg)
            self.validation_occurring = False
            raise NotOkToProceedError(msg)

        password = self.password.get_text()
        verify = self.verify.get_text()
        msg = None
        try:
            if validate_password(password):
                if not verify or len(verify) == 0:
                    msg = _('Re-enter to check for typing errors.')
                if password != verify:
                    msg = _('The two user passwords do not match.')
        except PasswordInvalid, err:
            msg = str(err)
        if msg:
            self.password.grab_focus()
            self.saved_msg = msg
            self.saved_msg_type = 'password'
            error_dialog('password', msg)
            self.validation_occurring = False
            raise NotOkToProceedError(msg)

        hostname = self.hostname.get_text()
        hostname_msg = self.validate_hostname(hostname, self.hostname)
        if hostname_msg:
            self.hostname.grab_focus()
            error_dialog('host', hostname_msg)
            self.validation_occurring = False
            raise NotOkToProceedError(hostname_msg)

        # done validating
        self.validation_occurring = False

        # Save the user-entered details to the DOC
        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache
        profile = doc.volatile.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)

        if profile is not None:
            profile.set_user_data(username, loginname, password, hostname)
        else:
            internal = _('Internal error occurred creating profile')
            error_dialog('profile', internal)
            raise NotOkToProceedError(internal)

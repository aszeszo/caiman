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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Welcome Screen for GUI Install app
'''

from gnome.ui import url_show_on_screen
from threading import Timer

from solaris_install import Popen
from solaris_install.gui_install.base_screen import BaseScreen
from solaris_install.gui_install.gui_install_common import \
    modal_dialog, GLADE_ERROR_MSG, RELEASE

# ReleaseNotes Timeout
RELEASENOTES_TIMEOUT_SECONDS=0.25


class WelcomeScreen(BaseScreen):
    '''Welcome Screen Class'''
    RELEASENOTESURL = "http://docs.sun.com/doc/821-1479"

    def __init__(self, builder):
        super(WelcomeScreen, self).__init__(builder)
        self.name = "Welcome Screen"
        self.widget = None

        self.releasenotesbutton = self.builder.get_object('releasenotesbutton')

        if None in [self.releasenotesbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    def enter(self):
        '''enter method for the progress screen'''
        toplevel = self.set_main_window_content("welcomescreenvbox")

        # Screen-specific configuration
        self.activate_stage_label("welcomestagelabel")

        self.set_titles(_("Welcome"), RELEASE, None)

        self.set_back_next(back_sensitive=False, next_sensitive=True)

        self.releasenotesbutton.connect('clicked',
                              self.on_releasenotesbutton_clicked, None)

        toplevel.show_all()

        return False

    def releasenotes_cb(self):
        '''timer callback to show the release notes outside the
           main thread.
        '''
        firefox_cmd = '/usr/bin/firefox %s' % self.RELEASENOTESURL
        cmd = firefox_cmd.split()
        Popen.check_call(cmd, check_result=Popen.ANY)

    def on_releasenotesbutton_clicked(self, widget, data=None):
        '''callback for "clicked" event on release notes button'''
        timer = Timer(RELEASENOTES_TIMEOUT_SECONDS, self.releasenotes_cb)
        timer.start()

    def go_back(self):
        '''method from the super that deals with
           the back button being pressed'''
        pass

    def validate(self):
        '''method from the super that deals with the update
           button being pressed'''
        pass

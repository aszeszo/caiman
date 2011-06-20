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
Failure Screen for GUI Install app
'''

from solaris_install.gui_install.base_screen import BaseScreen
from solaris_install.gui_install.gui_install_common import modal_dialog, \
    GLADE_ERROR_MSG
from solaris_install.gui_install.textview_dialog import TextViewDialog


class FailureScreen(BaseScreen):
    '''Failure Screen Class'''
    def __init__(self, builder, logname, quitapp):
        super(FailureScreen, self).__init__(builder)
        self.name = "Failure Screen"

        self.textview_dialog = None
        self.logname = logname
        self.quitapp = quitapp

        self.nextbutton = None
        self.installbutton = None

    def enter(self):
        '''enter method for the progress screen'''
        toplevel = self.set_main_window_content("failurewindowtable")

        # Screen-specific configuration
        self.activate_stage_label("finishstagelabel")

        logbutton = self.builder.get_object("failurelogbutton")
        quitbutton = self.builder.get_object("quitbutton")
        self.nextbutton = self.builder.get_object("nextbutton")
        self.installbutton = self.builder.get_object("installbutton")

        if None in [logbutton, quitbutton, self.nextbutton,
            self.installbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        logbutton.connect("clicked", self.logbutton_callback, None)
        quitbutton.set_sensitive(True)
        self.installbutton.hide_all()
        self.nextbutton.show_all()

        self.set_titles(_("Failure"), _(" "), None)

        self.set_back_next(back_sensitive=False, next_sensitive=False)

        toplevel.show_all()

        return False

    def logbutton_callback(self, widget, data):
        '''calback for the logbutton being clicked'''
        if not self.textview_dialog:
            self.textview_dialog = TextViewDialog(self.builder, self.logname,
                                                  self.quitapp)

        self.textview_dialog.display()

    def go_back(self):
        '''method from the super that deals with
           the back button being pressed'''
        pass

    def validate(self):
        '''method from the super that deals with the update
           button being pressed'''
        pass

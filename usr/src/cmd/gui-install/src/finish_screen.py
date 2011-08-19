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
Finish Screen for GUI Install app
'''

import logging
import os
import shutil

from solaris_install import Popen, CalledProcessError, StderrCalledProcessError
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen
from solaris_install.gui_install.gui_install_common import modal_dialog, \
    GLADE_ERROR_MSG
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.gui_install.textview_dialog import TextViewDialog
from solaris_install.logger import INSTALL_LOGGER_NAME

# command used to reboot the system
REBOOT = "/usr/sbin/reboot -f"


class FinishScreen(BaseScreen):
    '''Progress Screen Class'''
    def __init__(self, builder, logname, quitapp):
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

        super(FinishScreen, self).__init__(builder)
        self.name = "Finish Screen"

        self.textview_dialog = None
        self.logname = logname
        self.quitapp = quitapp

        self.logbutton = self.builder.get_object("finishlogbutton")
        self.quitbutton = self.builder.get_object("quitbutton")
        self.rebootbutton = self.builder.get_object("rebootbutton")
        self.installbutton = self.builder.get_object("installbutton")

        if None in [self.logbutton, self.quitbutton, self.rebootbutton,
            self.installbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    def enter(self):
        '''enter method for the finish screen'''
        toplevel = self.set_main_window_content("finishbox")

        # Screen-specific configuration
        self.activate_stage_label("finishstagelabel")

        self.logbutton.connect("clicked", self.logbutton_callback, None)
        self.logbutton.grab_focus()
        self.quitbutton.set_sensitive(True)
        self.installbutton.hide_all()
        self.rebootbutton.show_all()

        self.set_titles(_("Finished"), _(" "), None)

        self.set_back_next(back_sensitive=False, next_sensitive=False)

        toplevel.show_all()

        return False

    def logbutton_callback(self, widget, data):
        '''log button callback which shows the dialog'''
        if not self.textview_dialog:
            self.textview_dialog = TextViewDialog(self.builder, self.logname,
                                                  self.quitapp)

        self.textview_dialog.display()

    def go_back(self):
        '''method from the super that deals with
           the back button being pressed'''
        pass

    def validate(self):
        ''' Deals with the Reboot button being pressed.
            Defines abstract method from superclass.
        '''
        eng = InstallEngine.get_instance()
        profile = eng.data_object_cache.persistent.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        dest = os.path.join('/a', profile.log_final)
        if os.path.exists(os.path.dirname(dest)):
            self.logger.info("Rebooting...")
            self.logger.info("**** END ****")
            self.logger.close()
            shutil.copyfile(profile.log_location, dest)

        try:
            cmd = REBOOT.split()
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                             logger=self.logger)
        except (CalledProcessError, StderrCalledProcessError):
            self.logger.warn("Reboot failed:\n\t'%s'", " ".join(cmd))
        else:
            self.logger.warn("Reboot failed:\n\t'%s'.\nWill attempt"
                        " standard reboot", " ".join([REBOOT]))
        self.logger.close()

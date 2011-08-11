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
TextView dialog for GUI Install app to show the install log
'''

import pygtk
pygtk.require('2.0')

import os

import gtk

from solaris_install.gui_install.gui_install_common import modal_dialog, \
    DEFAULT_LOG_LOCATION, GLADE_ERROR_MSG


class TextViewDialog(object):
    '''TextViewDialog class'''
    def __init__(self, builder, logname, quitapp):
        '''initialize the textview dialog'''
        self.builder = builder
        self.logname = logname
        self.quitapp = quitapp

        self.textviewdialog = self.builder.get_object("textviewdialog")
        self.textview = self.builder.get_object("textview")
        quitbutton = self.builder.get_object("textviewclosebutton")

        if None in [self.textviewdialog, self.textview, quitbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        self.textviewdialog.set_title(_("Installation Log"))
        self.textviewdialog.connect("delete_event", self.destroy_event)

        # setup the close button clicked callback
        quitbutton.connect("clicked", self.textview_close_callback, None)

    def display(self):
        '''show the helpdialog and update the help text'''

        window = self.textviewdialog.window
        if window:
            window.set_functions(gtk.gdk.FUNC_CLOSE)

        # read the log file
        if self.logname:
            path = self.logname
        else:
            path = DEFAULT_LOG_LOCATION
        msg = None
        if os.path.exists(path):
            # read the entire DEFAULT_LOG_LOCATION
            with open(path) as fp:
                msg = fp.read()
        else:
            msg = _('Error:No log file found')

        # update the text buffer with the log text
        text_buffer = self.textview.get_buffer()
        text_buffer.set_text(msg)

        self.textviewdialog.show_all()
        self.quitapp.append(self.textviewdialog)

    def destroy_event(self, widget, event):
        '''catches delete events on the window
        '''
        self.textviewdialog.hide_all()

        return True

    def textview_close_callback(self, widget, data):
        '''Close button callback which hides the dialog'''
        if len(self.quitapp) == 1:
            gtk.main_quit()
        else:
            self.textviewdialog.hide_all()
            self.quitapp.pop()

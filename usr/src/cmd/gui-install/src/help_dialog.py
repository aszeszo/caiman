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
Help Dialog for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import os

import g11nsvc
import gtk
import pango

from solaris_install.gui_install.gui_install_common import modal_dialog, \
    GLADE_DIR, GLADE_ERROR_MSG

# The HELPFILES list will need to be reordered once the UPGRADE panel(s)
# are completed.
HELPFILES = ['WELCOME_PANEL.txt',
             'INSTALL_DISK_DISCOVERY_PANEL.txt',
             'INSTALL_DISK_PANEL.txt',
             'INSTALL_TIMEZONE_PANEL.txt',
             'INSTALL_USERS_PANEL.txt',
             'INSTALL_SUPPORT_PANEL.txt',
             'INSTALL_REVIEW_PANEL.txt',
             'INSTALL_PROGRESS_PANEL.txt',
             'FINISH_PANEL.txt',
             'INSTALL_FAILURE_PANEL.txt']


class HelpDialog(object):
    '''HelpDialog class'''
    def __init__(self, builder):
        '''initialize the helpdialog'''
        self.builder = builder

        self.helpdialog = self.builder.get_object("helpdialog")
        self.textview = self.builder.get_object("helptextview")
        closebutton = self.builder.get_object("helpclosebutton")

        if None in [self.helpdialog, self.textview, closebutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        self.helpdialog.connect("delete_event", self.destroy_event)
        if self.helpdialog.window:
            self.helpdialog.window.set_functions(gtk.gdk.FUNC_CLOSE)

        # add bold and underline tags to the text buffer
        text_buffer = self.textview.get_buffer()
        if text_buffer:
            text_buffer.create_tag("bold",
                                   weight=pango.WEIGHT_BOLD)
            text_buffer.create_tag("underline",
                                   underline=pango.UNDERLINE_SINGLE)

        # setup the close button clicked callback
        if closebutton:
            closebutton.connect("clicked", self.closebutton_callback, None)

    def destroy_event(self, widget, event):
        '''catches delete events on the window
        '''
        self.helpdialog.hide_all()

        return True

    def undisplay(self):
        '''convience method to hide the dialog'''
        self.helpdialog.hide_all()

    def display(self, screen):
        '''show the helpdialog and update the help text'''
        self.helpdialog.show_all()

        self.update_help(screen)

    def closebutton_callback(self, widget, data):
        '''Close button callback which hides the dialog'''
        self.helpdialog.hide_all()

    def update_help(self, screen_index):
        '''update the helpdialog text view to match the screen'''
        # ensure that the screen index is not larger then the
        # length of the HELPFILES list
        if screen_index >= len(HELPFILES):
            return

        # get the current locale
        locale_ops = g11nsvc.G11NSvcLocaleOperations()
        locale = locale_ops.getlocale()

        # read the localized help file that matches the current screen
        path = os.path.join(GLADE_DIR, os.path.join('help',
               os.path.join(locale, HELPFILES[screen_index])))
        msg = None
        if os.path.exists(path):
            # the current locale has help text available
            with open(path) as fp:
                msg = fp.read()
        else:
            # try to use the 'C' locale
            path = os.path.join(GLADE_DIR, os.path.join('help',
                   os.path.join('C', HELPFILES[screen_index])))
            if os.path.exists(path):
                # the 'C' locale has help text available
                with open(path) as fp:
                    msg = fp.read()
            else:
                msg = _('Internal Error\n\nNo help available')

        # update the text buffer with the screen's help text
        text_buffer = self.textview.get_buffer()

        # make the first line of text be the title for the help
        first_line_end = msg.find('\n')
        first_line = msg[:first_line_end + 1] + '\n'
        other_lines = msg[first_line_end + 1:]

        # insert the first line of text and make it bold and underlined
        text_buffer.set_text(first_line)
        (text_start, text_end) = text_buffer.get_bounds()
        text_buffer.apply_tag_by_name('bold', text_start, text_end)
        text_buffer.apply_tag_by_name('underline', text_start, text_end)

        # insert the rest of the text
        text_buffer.insert(text_end, other_lines)

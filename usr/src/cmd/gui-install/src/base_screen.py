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
Base class for the GUI Install app's screens.
'''

from abc import ABCMeta, abstractmethod

from solaris_install.gui_install.gui_install_common import \
    empty_container, modal_dialog, GLADE_ERROR_MSG, N_


class NotOkToProceedError(Exception):
    ''' Exception raised to prevent user leaving a screen. '''
    pass


class BaseScreen(object):
    '''
        Base class for the GUI Install app's screens.
    '''

    __metaclass__ = ABCMeta

    # Markup text for screen titles
    __TITLE_MARKUP = '<span font_desc="Bold" size="x-large" ' \
        'foreground="#587993">%s</span>'
    __SUBTITLE1_MARKUP = '<span font_desc="Bold">%s</span>'
    __SUBTITLE2_MARKUP = "%s"

    # Dictionary for the install "stage" labels shown down
    # the left-hand-side of the screen.  The key is the Glade
    # widget id, the value is the text to be displayed.
    # NOTE: These labels cannot be pre-translated at init time and so are
    # marked with the 'N_()' function here, for delayed translation.  This
    # text will later be wrapped with the gettext macro, '_()', when
    # referenced at run time
    __STAGE_LABELS = {
        "welcomestagelabel": N_("Welcome"),
        "diskdiscoverystagelabel": N_("Disk Discovery"),
        "diskselectionstagelabel": N_("Disk Selection"),
        "diskstagelabel": N_("Disk"),
        "timezonestagelabel": N_("Time Zone"),
        "userstagelabel": N_("Users"),
        "supportstagelabel": N_("Support"),
        "installationstagelabel": N_("Installation"),
        "finishstagelabel": N_("Finish"),
    }
    # Markup for showing which stage is currently active.
    __SIDEBAR_ACTIVE_MARKUP = '<span font_desc="Bold" ' \
        'foreground="#587993">%s</span>'
    __SIDEBAR_INACTIVE_MARKUP = '<span font_desc="Bold" ' \
        'foreground="#595A5E">%s</span>'

    def __init__(self, builder):
        self.builder = builder

        self.screencontentvbox = self.builder.get_object("screencontentvbox")
        self.screentitlelabel = self.builder.get_object("screentitlelabel")
        self.screentitlesublabel1 = self.builder.get_object(
            "screentitlesublabel1")
        self.screentitlesublabel2 = self.builder.get_object(
            "screentitlesublabel2")
        self.backbutton = self.builder.get_object("backbutton")
        self.nextbutton = self.builder.get_object("nextbutton")

        if None in [self.screencontentvbox, self.screentitlelabel,
            self.screentitlesublabel1, self.screentitlesublabel2,
            self.backbutton, self.nextbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    @abstractmethod
    def enter(self):
        '''
            Sub-classes must define this method.

            Called when the user tries to enter the screen by
            pressing the appropriate button (Next, Back, Install, etc).

            Sub-classes should raise NotOkToProceedError if this
            operation is being prevented for any reason.
        '''
        pass

    @abstractmethod
    def go_back(self):
        '''
            Sub-classes must define this method.

            Called when the user tries to leave the screen by
            pressing the Back button.

            Sub-classes should raise NotOkToProceedError if this
            operation is being prevented for any reason.
        '''
        pass

    @abstractmethod
    def validate(self):
        '''
            Sub-classes must define this method.

            Called when the user tries to leave the screen and
            advance to the next screen.

            Sub-classes should raise NotOkToProceedError if this
            operation is being prevented due to a validation error.
        '''
        pass

    def set_main_window_content(self, object_name):
        '''
            Empties the main window's content vbox and fills it
            with 'object_name' from Glade.

            Returns:
            widget corresponding to object_name
        '''

        new_content = self.builder.get_object(object_name)

        if new_content is None:
            return None

        empty_container(self.screencontentvbox)
        new_content.unparent()
        self.screencontentvbox.pack_start(new_content,
            expand=True, fill=True, padding=0)

        return new_content

    def activate_stage_label(self, label_name):
        '''
            Activate (ie display in a different color) the label in
            the left-hand-side "stage" list which corresponds to
            Glade widget id 'label_name'.
            Inactivate (ie display in normal color) all the other
            labels.
        '''

        for stage_label_name in BaseScreen.__STAGE_LABELS:
            label = self.builder.get_object(stage_label_name)
            if label is not None:
                if stage_label_name == label_name:
                    text = BaseScreen.__SIDEBAR_ACTIVE_MARKUP % \
                        _(BaseScreen.__STAGE_LABELS[stage_label_name])
                else:
                    text = BaseScreen.__SIDEBAR_INACTIVE_MARKUP % \
                        _(BaseScreen.__STAGE_LABELS[stage_label_name])

                label.set_label(text)
                label.show()

    def set_titles(self, title, subtitle1, subtitle2):
        '''
            Set the titles over the main area.  There are
            three title which can be set:

                title
                subtitle1               subtitle2

            The specified text for each title is wrapped in the
            appropriate markup before being displayed.  If None
            is passed in for any title, it will be removed (hidden).
        '''

        if title is None:
            self.screentitlelabel.hide()
        else:
            text = BaseScreen.__TITLE_MARKUP % title
            self.screentitlelabel.set_label(text)
            self.screentitlelabel.show()

        if subtitle1 is None:
            self.screentitlesublabel1.hide()
        else:
            text = BaseScreen.__SUBTITLE1_MARKUP % subtitle1
            self.screentitlesublabel1.set_label(text)
            self.screentitlesublabel1.show()

        if subtitle2 is None:
            self.screentitlesublabel2.hide()
        else:
            text = BaseScreen.__SUBTITLE2_MARKUP % subtitle2
            self.screentitlesublabel2.set_text(text)
            self.screentitlesublabel2.show()

    def set_back_next(self, back_sensitive=True, next_sensitive=True):
        ''' Sets the sensitivity of the Back and Next buttons. '''

        self.backbutton.set_sensitive(back_sensitive)
        self.nextbutton.set_sensitive(next_sensitive)

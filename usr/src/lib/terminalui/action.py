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
Contains the 'Action' class
'''


class Action(object):
    '''An Action represents the combination of F# key, descriptive text,
    and, in some cases, an associated arbitrary function.

    '''

    def _do_action(self, screen=None):
        '''Private default function assigned to do_action'''
        raise NotImplementedError("Must override do_action before use")

    def __init__(self, key, text, do_action=None):
        '''
        Constructor

        key (required): An integer corresponding to a function key.
        When the function key is pressed and handled by a MainWindow,
        do_action will be invoked with the current screen as its sole
        parameter.

        For example, key=curses.KEY_F2 would imply this action is
        associated with F2 (and Esc-2)

        text (required): A string description of the action. This is displayed
        in the footer. Keep it short - only 80 characters are available for all
        actions, and it must be assumed that the 'long notation' of
        ESC-#_<description> is printed for each action.

        do_action (optional): If supplied, this parameter should be a
        function that accepts a single parameter. The function will be
        passed the current screen as the parameter, and should return the
        next screen to be shown. If not supplied, the corresponding F# key
        MUST be caught in a subwindow.

        '''

        self.key = key
        self.text = text
        if do_action is not None:
            self.do_action = do_action
        else:
            self.do_action = self._do_action

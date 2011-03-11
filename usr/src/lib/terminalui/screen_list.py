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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Manage the UI state as two lists of screens:
(1) The list of screens that could be visited, in the order they should
be visited
(2) The list of screens that has been visited
'''


import terminalui


class ScreenList(object):
    '''Manage the screen lists'''
    
    def __init__(self):
        self.screen_list = []
        self.visited_list = []
        self.help = None
    
    def get_next(self, current=None, skipped=False):
        '''Add the current screen to the visited list (unless skipped == True)
        and return the next screen
        
        '''
        if current is not None:
            if not skipped:
                self.visited_list.append(current)
            current_index = self.screen_list.index(current) + 1
            if current_index < len(self.screen_list):
                return self.screen_list[current_index]
            else:
                return None
        else:
            return self.screen_list[0]
    
    def previous_screen(self, dummy=None):
        '''Return the previous screen.
        Note that there is no protection against popping from an empty list.
        This is intentional - the F3_Back action should be removed from the
        action dictionary of the first screen.
        
        '''
        return self.visited_list.pop()
    
    def peek_last(self):
        '''Peek at the last visited screen. This function can be used to
        determine if the user is moving forward or backward
        (see BaseScreen.validate_loop)
        
        '''
        if len(self.visited_list) == 0:
            return None
        else:
            return self.visited_list[-1]
    
    @staticmethod
    def quit(dummy=None):
        '''Immediately return None (causing an exit)'''
        terminalui.LOGGER.debug("screen_list.quit triggered")
        return None

    def show_help(self, current=None):
        '''Return the screen registered as the Help Screen.
        
        current is appended to the visited_list, unless the current screen
        is also the help screen.
        
        '''
        terminalui.LOGGER.debug("show_help: current=%s", current)
        if (current != self.help):
            self.visited_list.append(current)
        self.help.screen = current.__class__.__name__ + current.instance
        return self.help

#!/usr/bin/python2.6
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


'''sample_runner: This is a "runner" for the other files in this sample
directory. To see samples in action, do the following:

* Build the gate (a proto area populated with terminalui files is required)
* Set your PYTHONPATH ($ROOT is the path to your proto area,
        e.g. "/export/ws/slim_source/proto/root_i386"):
    export PYTHONPATH=${ROOT}/usr/snadm/lib:\
        ${ROOT}/usr/lib/python2.6/vendor-packages/:${ROOT}/usr/lib/installadm
* cd into this directory
* Run one of the following commands:
    o To see the samples for hello_world, lists, edits, saving_state, and
        validation, run:
            $ python sample_runner.py
    o To see the samples for selectors.py, run:
            $ python sample_runner.py flow

'''


_ = lambda x: x


import curses
import locale
import sys

import terminalui
from terminalui import LOG_LEVEL_INPUT, LOG_NAME_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen
from terminalui.help_screen import HelpScreen
from terminalui.i18n import get_encoding, set_wrap_on_whitespace
from terminalui.main_window import MainWindow
from terminalui.screen_list import ScreenList


from hello_world import HelloWorld
from lists import ListSample
from edits import EditSample
from saving_state import StateSample
from selectors import get_selector_screens
from validation import ValidSample


def basic_screens(main_win):
    '''Initializes a full set of screens'''
    
    result = [HelloWorld(main_win),
              ListSample(main_win),
              EditSample(main_win),
              StateSample(main_win),
              ValidSample(main_win)]
    return result


def _show_screens(group):
    with terminalui as initscr:
        win_size_y, win_size_x = initscr.getmaxyx()
        if win_size_y < 24 or win_size_x < 80:
            msg = ("     Terminal too small. Min size is 80x24."
                   " Current size is %(x)ix%(y)i." %
                   {'x': win_size_x, 'y': win_size_y})
            sys.exit(msg)
        screen_list = ScreenList()
        
        actions = [Action(curses.KEY_F2, "Continue", screen_list.get_next),
                   Action(curses.KEY_F3, "Back",
                          screen_list.previous_screen),
                   Action(curses.KEY_F6, "Help", screen_list.show_help),
                   Action(curses.KEY_F9, "Quit", screen_list.quit)]
        
        main_win = MainWindow(initscr, screen_list, actions)
        screen_list.help = HelpScreen(main_win, "Help Topics",
                                      "Help Index",
                                      "Select a topic and press Continue.")
        
        if group == "flow":
            win_list = get_selector_screens(main_win)
        else:
            win_list = basic_screens(main_win)
        screen_list.help.setup_help_data(win_list)
        screen_list.screen_list = win_list
        screen = screen_list.get_next()
        
        while screen is not None:
            screen = screen.show()


def _init_locale():
    locale.setlocale(locale.LC_ALL, "")
    set_wrap_on_whitespace("True")
    BaseScreen.set_default_quit_text("Confirm: Quit?",
                                     "Do you really want to quit?",
                                     "Cancel",
                                     "Quit")


def _init_logging():
    terminalui.init_logging("sample")
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass
    terminalui.LOGGER.addHandler(NullHandler())



if __name__ == '__main__':
    _init_locale()
    terminalui.init_logging("sample")
    _show_screens(sys.argv[-1])

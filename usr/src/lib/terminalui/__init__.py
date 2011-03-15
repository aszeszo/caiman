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


'''Set the ESCDELAY environment variable, if it's not yet set
(n)curses will wait ESCDELAY milliseconds after receiving an
ESC key as input before processing the input. It defaults to 1000 ms
(1 sec), which causes function and arrow keys to react very slowly, so
we default to 200 instead. (Settings under ~200 can interfere with
tipline esc-sequences)

'''

__all__ = ["action", "base_screen", "color_theme", "edit_field",
           "error_window", "i18n", "inner_window", "list_item", "screen_list",
           "scroll_window"]

import curses
import logging
import os
os.environ.setdefault("ESCDELAY", "200")

LOG_NAME_INPUT = "INPUT"
LOG_LEVEL_INPUT = 5
logging.addLevelName(LOG_LEVEL_INPUT, LOG_NAME_INPUT)
LOGGER = None


def setup_curses():
    '''Initialize the curses module'''
    initscr = curses.initscr()
    if curses.has_colors():
        curses.start_color()
    curses.noecho()
    curses.cbreak()
    curses.meta(1)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    return initscr


def cleanup_curses():
    '''Return the console to a usable state'''
    curses.echo()
    curses.nocbreak()
    curses.endwin()
    os.system("/usr/bin/clear")


def init_logging(basename):
    global LOGGER
    LOGGER = logging.getLogger(basename + ".terminalui")


# Defining __enter__ and __exit__ allows this module to be
# used in a 'with' statement, e.g.:
#
# with terminalui as initscr:
#     do_stuff()
#
__enter__ = setup_curses


def __exit__(exc_type, exc_val, exc_tb):
    '''Cleanup the same way whether or not an exception occurred'''
    cleanup_curses()

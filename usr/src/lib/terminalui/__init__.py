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
import gettext
import logging
import os
os.environ.setdefault("ESCDELAY", "200")

_ = gettext.translation("terminalui", "/usr/share/locale",
                        fallback=True).ugettext
LOG_NAME_INPUT = "INPUT"
LOG_LEVEL_INPUT = 5
logging.addLevelName(LOG_LEVEL_INPUT, LOG_NAME_INPUT)
LOGGER = None

KEY_ESC = 27


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


class EscapeSeq(object):
    '''Process input escape sequences'''
    def __init__(self):
        self._esc_seq = None  # escape sequence accumulator
        self._key_fn = False  # True when ESC+[1-9] typed

    def input(self, input_key):
        '''Process an input character
        Arg: input_key - the input character
            Returns:
                input_key
i                   if not in an escape sequence
                    if an invalid character for the escape sequence
                else None if input_key is not an escape sequence terminator
                else return curses code for the escape sequence
            Effects:
                accumulates escape sequences
                sets _key_fn True if ESC+[1-9] typed
        '''
        global LOGGER
        self._key_fn = False
        if self._esc_seq:
            if curses.ascii.isdigit(input_key):
                if len(self._esc_seq) > 1:
                    if self._esc_seq[1] == '[':  # ESC[<number>~
                        self._esc_seq += chr(input_key)  # accumulate
                        return None
                else:
                    self._esc_seq = None
                    self._key_fn = True
                    LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_FN")
                    return input_key - ord('0') + curses.KEY_F0
            elif curses.ascii.isalpha(input_key):
                if len(self._esc_seq) > 1:
                    if self._esc_seq[1] == 'O':  # terminate ESC_O<A-Z>
                        if input_key == ord('F'):
                            self._esc_seq = None
                            LOGGER.log(LOG_LEVEL_INPUT,
                                "Valid esc-sequence, converting to KEY_END")
                            return curses.KEY_END
                        if input_key == ord('H'):
                            self._esc_seq = None
                            LOGGER.log(LOG_LEVEL_INPUT,
                                "Valid esc-sequence, converting to KEY_HOME")
                            return curses.KEY_HOME
                        if input_key == ord('Q'):  # F2 for xterm-color
                            self._esc_seq = None
                            LOGGER.log(LOG_LEVEL_INPUT,
                                "Valid esc-sequence, converting to KEY_F2")
                            return curses.KEY_F2
                        if input_key == ord('R'):  # F3 for xterm-color
                            self._esc_seq = None
                            LOGGER.log(LOG_LEVEL_INPUT,
                                "Valid esc-sequence, converting to KEY_F3")
                            return curses.KEY_F3
                elif input_key == ord('O'):  # ESC_O<A-Z>
                    self._esc_seq += chr(input_key)  # accumulate
                    return None
            elif input_key == ord('~'):  # terminate ESC[<number>~
                if len(self._esc_seq) > 2:
                    if self._esc_seq[2] == '5':  # PgUp
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_PPAGE")
                        return curses.KEY_PPAGE
                    elif self._esc_seq[2] == '6':  # PgDown
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_NPAGE")
                        return curses.KEY_NPAGE
                    elif self._esc_seq[2:4] == '12':  # PuTTY
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_F2")
                        return curses.KEY_F2
                    elif self._esc_seq[2:4] == '13':  # PuTTY
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_F3")
                        return curses.KEY_F3
                    elif self._esc_seq[2:4] == '17':
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_F6")
                        return curses.KEY_F6
                    elif self._esc_seq[2:4] == '20':
                        self._esc_seq = None
                        LOGGER.log(LOG_LEVEL_INPUT,
                            "Valid esc-sequence, converting to KEY_F9")
                        return curses.KEY_F9
            elif input_key == ord('['):  # ESC_[<number>~
                if len(self._esc_seq) == 1:
                    self._esc_seq += chr(input_key)  # accumulate
                    return None
            # not handled, treat as invalid escape sequence
            if input_key:   
                LOGGER.log(LOG_LEVEL_INPUT,
                           "Invalid character in escape sequence=%s code %s "
                           "accumulated %s",
                           chr(input_key), input_key, self._esc_seq)
                self._esc_seq = None
                LOGGER.log(LOG_LEVEL_INPUT,
                           "Invalid esc-sequence, returning None")
                return None
        elif input_key == KEY_ESC:
            LOGGER.log(LOG_LEVEL_INPUT, "Beginning esc-sequence")
            self._esc_seq = chr(KEY_ESC)  # start accumulating
            return None
        return input_key

    def is_key_fn(self):
        return self._key_fn

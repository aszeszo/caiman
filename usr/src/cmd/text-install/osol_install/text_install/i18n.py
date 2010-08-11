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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

''' methods for internationalized text processing, which
counts "columns" in applicable cases, rather than assuming
columns are same as characters or bytes.

'''

import locale
from unicodedata import east_asian_width
from osol_install.text_install import _

# for specifying justification in fit_text_truncate()
LEFT = "left"
RIGHT = "right"
CENTER = "center"

def get_encoding():
        ''' Get encoding of current locale
        '''
        enc = locale.getlocale(locale.LC_CTYPE)[1]
        if enc is None:
            enc = locale.getpreferredencoding()

        return enc

def charwidth(c):
        ''' Count column width needed for given Unicode character
        '''
        if isinstance(c, str):
            c = c.decode(get_encoding())
        width_class = east_asian_width(c)

        if width_class == "F" or width_class == "W":
            return 2
        else:
            return 1

def textwidth(text):
        ''' Count column width needed for given string.
        '''
        if isinstance(text, str):
            text = text.decode(get_encoding())
        text = text.expandtabs(4)

        width_total = 0

        for char in text:
            width_total += charwidth(char)

        return width_total

def if_wrap_on_whitespace():
        ''' Get information on whether wrapping text should be done on
        white space or on arbitrary position. Default is True as in English.
        '''
        val = _("DONT_TRANSLATE_BUT_REPLACE_msgstr_WITH_True_OR_False: "
                "Should wrap text on whitespace in this language")

        if val == "False":
            return False
        else:
            return True

def fit_text_truncate(text, max_width, just="", fillchar=u" "):
        ''' Fit a text in max_width columns, by truncating the text if needed.
        If just is one of LEFT, RIGHT, or CENTER, justify text
        and fill unused room with fillchar.
        '''
        if isinstance(text, str):
            text = text.decode(get_encoding())

        text = text.expandtabs(4)

        if fillchar is None:
            fillchar = u" "
        if isinstance(fillchar, str):
            fillchar = fillchar.decode(get_encoding())
        if charwidth(fillchar) != 1:
            raise ValueError('Cannot use multi-column character "%c" as '
                             'fillchar.' % fillchar)

        fitted_text = u""
        width_total = 0

        for char in text:
            width = charwidth(char)
            if width_total + width > max_width:
                break
            fitted_text += char
            width_total += width

        npad = max_width - width_total

        if just and npad > 0:
            if just == LEFT:
                fitted_text = fitted_text + fillchar * npad
            elif just == RIGHT:
                fitted_text = fillchar * npad + fitted_text
            elif just == CENTER:
                nleft = npad // 2
                nright = npad - nleft
                fitted_text = fillchar * nleft + fitted_text + fillchar * nright
            else:
                raise ValueError("Unknown just=%s" % just)

        return fitted_text

def ljust_columns(text, max_width, fillchar=u" "):
    ''' alternative to ljust(); counts multicolumn characters correctly
    '''
    return fit_text_truncate(text, max_width, just=LEFT, fillchar=fillchar)

def rjust_columns(text, max_width, fillchar=u" "):
    ''' alternative to rjust(); counts multicolumn characters correctly
    '''
    return fit_text_truncate(text, max_width, just=RIGHT, fillchar=fillchar)

def center_columns(text, max_width, fillchar=u" "):
    ''' alternative to center(); counts multicolumn characters correctly
    '''
    return fit_text_truncate(text, max_width, just=CENTER, fillchar=fillchar)

def convert_paragraph(text, max_chars):
    '''Break a paragraph of text up into chunks that will each
    fit within max_chars. Splits on whitespace (if wrapping on
    whitespace is used in current language) and newlines.
    
    max_chars defaults to the size of this window.
    
    '''
    wrap_on_whitespace = if_wrap_on_whitespace()

    if isinstance(text, str):
        text = text.decode(get_encoding())

    text_lines = text.expandtabs(4).splitlines()
    paragraphed_lines = []

    for line in text_lines:
        width_total = 0
        last_whitespace = None
        width_upto_last_whitespace = None
        start_pt = 0
        for i, c in enumerate(line):
            width = charwidth(c)
            if width_total + width > max_chars:
                if wrap_on_whitespace and last_whitespace is not None :
                    # put upto last white space
                    end_pt = last_whitespace + 1
                    paragraphed_lines.append(line[start_pt:end_pt].lstrip())
                    # next line will start at char next to the white space
                    start_pt = last_whitespace + 1
                    width_total -= width_upto_last_whitespace
                    # forget last white space
                    last_whitespace = None
                    width_upto_last_whitespace = None
                else:
                    # white space didn't appear; put upto last char
                    end_pt = i
                    paragraphed_lines.append(line[start_pt:end_pt].lstrip())
                    # next line will start at current char
                    start_pt = i
                    width_total = 0
            width_total += width
            if c == u' ':
                if i == start_pt:
                    # not count leading white space
                    width_total -= width
                else:
                    last_whitespace = i
                    width_upto_last_whitespace = width_total
        # flush last part of "line" (each item of text_lines)
        paragraphed_lines.append(line[start_pt:].lstrip())
    return paragraphed_lines


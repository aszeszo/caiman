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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

import unittest
import locale

import terminalui
from terminalui.i18n import get_encoding, \
                            if_wrap_on_whitespace, \
                            charwidth, \
                            textwidth, \
                            fit_text_truncate, \
                            convert_paragraph, \
                            LEFT, \
                            RIGHT, \
                            CENTER


terminalui.init_logging("test")


class I18nTestCase(unittest.TestCase):
    def setUp(self):
        # save current locale
        self.save_locale = locale.getlocale(locale.LC_ALL)
        # set locale
        locale.setlocale(locale.LC_ALL, "")
        # if not in UTF-8 locale, fallback to en_US.UTF-8
        enc = locale.getlocale(locale.LC_CTYPE)[1]
        if enc is None or enc.upper() != "UTF-8" and enc.upper() != "UTF8":
            print "This test script uses hard-coded Unicode characters and "
            print "needs to run in a UTF-8 locale. Fallback to en_US.UTF-8."
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

    def tearDown(self):
        # restore locale
        try:
            locale.setlocale(locale.LC_ALL, self.save_locale)
        except locale.Error:
            # self.save_locale may sometimes be invalid -
            # locale.getlocale() does not always return something
            # that locale.setlocale() considers valid)
            locale.setlocale(locale.LC_ALL, "C")

    def test_charwidth(self):
        ''' test charwidth() '''
        # example of 1-column character (ASCII)
        self.assertEqual(charwidth(u'A'), 1)
        self.assertEqual(charwidth(u'A'.encode(get_encoding())), 1)
        # example of 1-column character (non-ASCII)
        self.assertEqual(charwidth(u'\u00c0'), 1)
        self.assertEqual(charwidth(u'\u00c0'.encode(get_encoding())), 1)
        # example of 2-column character
        self.assertEqual(charwidth(u'\u3042'), 2)
        self.assertEqual(charwidth(u'\u3042'.encode(get_encoding())), 2)

    def test_textwidth(self):
        ''' test textwidth() '''
        # without tab
        self.assertEqual(textwidth(u'A\u00c0\u3042'), 1 + 1 + 2)
        self.assertEqual(textwidth(u'A\u00c0\u3042'.encode(get_encoding())),
                         1 + 1 + 2)
        # with tab
        self.assertEqual(textwidth(u'\tA\u00c0\u3042'), 4 + 1 + 1 + 2)
        self.assertEqual(textwidth(u'\tA\u00c0\u3042'.encode(get_encoding())),
                         4 + 1 + 1 + 2)

    def test_fit_text_truncate(self):
        ''' test fit_text_truncate() '''
        c0 = u'\u3042' # 2 columns
        c1 = u'\u3044' # 2 columns
        c2 = u'\u3046' # 2 columns
        c3 = u'\u3048' # 2 columns
        s = c0 + c1 + c2 + c3
        # no justification
        self.assertEqual(fit_text_truncate(s, 9), s[:4])
        self.assertEqual(fit_text_truncate(s, 8), s[:4])
        self.assertEqual(fit_text_truncate(s, 7), s[:3])
        self.assertEqual(fit_text_truncate(s, 6), s[:3])
        self.assertEqual(fit_text_truncate(s, 5), s[:2])
        self.assertEqual(fit_text_truncate(s, 4), s[:2])
        self.assertEqual(fit_text_truncate(s, 3), s[:1])
        self.assertEqual(fit_text_truncate(s, 2), s[:1])
        self.assertEqual(fit_text_truncate(s, 1), s[:0])
        self.assertEqual(fit_text_truncate(s, 0), s[:0])
        # justify to left
        self.assertEqual(fit_text_truncate(s, 9, just=LEFT), s[:4] + u' ')
        self.assertEqual(fit_text_truncate(s, 8, just=LEFT), s[:4])
        self.assertEqual(fit_text_truncate(s, 7, just=LEFT), s[:3] + u' ')
        self.assertEqual(fit_text_truncate(s, 6, just=LEFT), s[:3])
        self.assertEqual(fit_text_truncate(s, 5, just=LEFT), s[:2] + u' ')
        self.assertEqual(fit_text_truncate(s, 4, just=LEFT), s[:2])
        self.assertEqual(fit_text_truncate(s, 3, just=LEFT), s[:1] + u' ')
        self.assertEqual(fit_text_truncate(s, 2, just=LEFT), s[:1])
        self.assertEqual(fit_text_truncate(s, 1, just=LEFT), s[:0] + u' ')
        self.assertEqual(fit_text_truncate(s, 0, just=LEFT), s[:0])
        # justify to right
        self.assertEqual(fit_text_truncate(s, 9, just=RIGHT), u' ' + s[:4])
        self.assertEqual(fit_text_truncate(s, 8, just=RIGHT), s[:4])
        self.assertEqual(fit_text_truncate(s, 7, just=RIGHT), u' ' + s[:3])
        self.assertEqual(fit_text_truncate(s, 6, just=RIGHT), s[:3])
        self.assertEqual(fit_text_truncate(s, 5, just=RIGHT), u' ' + s[:2])
        self.assertEqual(fit_text_truncate(s, 4, just=RIGHT), s[:2])
        self.assertEqual(fit_text_truncate(s, 3, just=RIGHT), u' ' + s[:1])
        self.assertEqual(fit_text_truncate(s, 2, just=RIGHT), s[:1])
        self.assertEqual(fit_text_truncate(s, 1, just=RIGHT), u' ' + s[:0])
        self.assertEqual(fit_text_truncate(s, 0, just=RIGHT), s[:0])
        # justify to center
        self.assertEqual(fit_text_truncate(s, 12, just=CENTER),
                         u' ' * 2 + s[:4] + u' ' * 2)
        self.assertEqual(fit_text_truncate(s, 11, just=CENTER),
                         u' ' + s[:4] + u' ' * 2)
        self.assertEqual(fit_text_truncate(s, 10, just=CENTER),
                         u' ' + s[:4] + u' ')
        self.assertEqual(fit_text_truncate(s, 9, just=CENTER), s[:4] + u' ')
        self.assertEqual(fit_text_truncate(s, 8, just=CENTER), s[:4])
        self.assertEqual(fit_text_truncate(s, 7, just=CENTER), s[:3] + u' ')
        self.assertEqual(fit_text_truncate(s, 6, just=CENTER), s[:3])
        self.assertEqual(fit_text_truncate(s, 5, just=CENTER), s[:2] + u' ')
        self.assertEqual(fit_text_truncate(s, 4, just=CENTER), s[:2])
        self.assertEqual(fit_text_truncate(s, 3, just=CENTER), s[:1] + u' ')
        self.assertEqual(fit_text_truncate(s, 2, just=CENTER), s[:1])
        self.assertEqual(fit_text_truncate(s, 1, just=CENTER), s[:0] + u' ')
        self.assertEqual(fit_text_truncate(s, 0, just=CENTER), s[:0])

    def test_fit_text_truncate_multicolumn_fillchar(self):
        ''' test fit_text_truncate() with specifying multicolumn fillchar,
            expecting ValueError is raised
        '''
        self.assertRaises(ValueError, fit_text_truncate,
                          u"\u3042", 9, just=LEFT, fillchar=u'\u3042')
        self.assertRaises(ValueError, fit_text_truncate,
                          u"\u3042", 9, just=RIGHT, fillchar=u'\u3042')
        self.assertRaises(ValueError, fit_text_truncate,
                          u"\u3042", 9, just=CENTER, fillchar=u'\u3042')

    def test_convert_paragraph(self):
        ''' test convert_paragraph() '''
        c0 = u'\u3042' # 2 columns
        c1 = u'\u3044' # 2 columns
        c2 = u' ' # 1 column (white space)
        c3 = u'\u3046' # 2 columns
        c4 = u'\u3048' # 2 columns
        s = c0 + c1 + c2 + c3 + c4

        if if_wrap_on_whitespace():
            self.assertEqual(convert_paragraph(s, 10), [s])
            self.assertEqual(convert_paragraph(s, 9), [s])
            self.assertEqual(convert_paragraph(s, 8), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 7), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 6), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 5), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 4), [s[:2], s[2:].lstrip()])
        else:
            self.assertEqual(convert_paragraph(s, 10), [s])
            self.assertEqual(convert_paragraph(s, 9), [s])
            self.assertEqual(convert_paragraph(s, 8), [s[:4], s[4:].lstrip()])
            self.assertEqual(convert_paragraph(s, 7), [s[:4], s[4:].lstrip()])
            self.assertEqual(convert_paragraph(s, 6), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 5), [s[:3], s[3:].lstrip()])
            self.assertEqual(convert_paragraph(s, 4), [s[:2], s[2:].lstrip()])

if __name__ == '__main__':
    unittest.main()

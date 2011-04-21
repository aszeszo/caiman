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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
Test functionality of the process_dtd module.

Create a DTD to demo many test cases, and verify that the tables created by the
process_dtd module are correct.
'''

import unittest
import tempfile
import os
from solaris_install.manifest_input.process_dtd import SchemaData

# pylint: disable-msg=C0111,C0103


class TestProcessDTD(unittest.TestCase):
    '''
    Test functionality of the process_dtd module.
    '''

    table = None

    @classmethod
    def create_dtd(cls):
        '''
        Create the DTD and return its filename.
        '''

        fd, dtd_filename = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as dtd_fd:
            dtd_fd.write('<!ELEMENT ' +
                      'A (a*, b?, c*, d+, e*, f, (g|h*|i?|j+), k)>\n')
            dtd_fd.write('<!ELEMENT ' +
                      'B (a?, b*, c?, d+, e?, f, (g|h*|i?|j+), k)>\n')
            dtd_fd.write('<!ELEMENT ' +
                      'C (a+, b*, c+, d?, e+, f, (g|h*|i?|j+), k)>\n')
            dtd_fd.write('<!ELEMENT ' +
                      'D (a, b*, c, d?, e, f+, (g|h*|i?|j+), k)>\n')
            dtd_fd.write('<!ELEMENT E ((a|b*|c?|d+), (e|f?|g+|h*))>\n')
            dtd_fd.write('<!ELEMENT F ((a|b*|c?|d+), e?, f)>\n')
            dtd_fd.write('<!ELEMENT G ((a|b*|c?|d+), e?)>\n')
            dtd_fd.write('<!ELEMENT H (((a|b*|c?|d+)), e+)>\n')
            dtd_fd.write('<!ELEMENT I (((a,b*,c?,d+)), e+)>\n')
            dtd_fd.write('<!ELEMENT J (a, b?, (c|d*|e?|f+), g, h)>\n')
            dtd_fd.write('<!ELEMENT '
                         'K (a, b?, (c|d*|e?|f+), g, (h|i?|j), k)>\n')
            dtd_fd.write('<!ELEMENT L (a, b?, (c|d*|e?|f+), (h|i?|j), k)>\n')
            dtd_fd.write('\n')
            dtd_fd.write('<!ELEMENT a EMPTY>\n')
            dtd_fd.write('<!ELEMENT b EMPTY>\n')
            dtd_fd.write('<!ELEMENT c EMPTY>\n')
            dtd_fd.write('<!ELEMENT d EMPTY>\n')
            dtd_fd.write('<!ELEMENT e EMPTY>\n')
            dtd_fd.write('<!ELEMENT f EMPTY>\n')
            dtd_fd.write('<!ELEMENT g EMPTY>\n')
            dtd_fd.write('<!ELEMENT h EMPTY>\n')
            dtd_fd.write('<!ELEMENT i EMPTY>\n')
            dtd_fd.write('<!ELEMENT j EMPTY>\n')
            dtd_fd.write('<!ELEMENT k EMPTY>\n')
            dtd_fd.write('<!ELEMENT l EMPTY>\n')
        return dtd_filename

    def checkit(self, parent, element, put_before, mults_ok):

        # Do one-time initialization the first time through.
        if not TestProcessDTD.table:
            dtd_filename = self.create_dtd()
            TestProcessDTD.table = SchemaData(dtd_filename)

        (put_before_ret, mults_ok_ret) = \
            TestProcessDTD.table.find_element_info(parent, element)
        if ((put_before_ret == put_before) and (mults_ok_ret == mults_ok)):
            return

        if (mults_ok_ret != mults_ok):
            mults_ok_str = "yes" if mults_ok else "no"
            mults_ok_ret_str = "yes" if mults_ok_ret else "no"
            print "parent:%s, element:%s, mults_ok: expected:%s, got:%s\n" % (
                parent, element, mults_ok_str, mults_ok_ret_str)

        if (put_before_ret != put_before):
            print "element %s can go before: " + str(put_before)
            print "...  but module returned: " + str(put_before_ret)

        self.assertTrue((put_before_ret == put_before) and
            (mults_ok_ret == mults_ok))

    def test_process_dtd_A_a(self):
        self.checkit("A", "a", ['b', 'c'], True)

    def test_process_dtd_A_b(self):
        self.checkit("A", "b", ['c'], False)

    def test_process_dtd_A_c(self):
        self.checkit("A", "c", ['d'], True)

    def test_process_dtd_A_d(self):
        self.checkit("A", "d", ['e'], True)

    def test_process_dtd_A_e(self):
        self.checkit("A", "e", ['f'], True)

    def test_process_dtd_A_f(self):
        self.checkit("A", "f", ['g', 'h', 'i', 'j', 'k'], False)

    def test_process_dtd_A_g(self):
        self.checkit("A", "g", ['k'], False)

    def test_process_dtd_A_h(self):
        self.checkit("A", "h", ['k'], True)

    def test_process_dtd_A_i(self):
        self.checkit("A", "i", ['k'], False)

    def test_process_dtd_A_j(self):
        self.checkit("A", "j", ['k'], True)

    def test_process_dtd_A_k(self):
        self.checkit("A", "k", [], False)

    def test_process_dtd_A_l(self):
        self.checkit("A", "l", None, False)

    def test_process_dtd_B_a(self):
        self.checkit("B", "a", ['b'], False)

    def test_process_dtd_B_b(self):
        self.checkit("B", "b", ['c', 'd'], True)

    def test_process_dtd_B_c(self):
        self.checkit("B", "c", ['d'], False)

    def test_process_dtd_B_d(self):
        self.checkit("B", "d", ['e', 'f'], True)

    def test_process_dtd_B_e(self):
        self.checkit("B", "e", ['f'], False)

    def test_process_dtd_B_f(self):
        self.checkit("B", "f", ['g', 'h', 'i', 'j', 'k'], False)

    def test_process_dtd_B_g(self):
        self.checkit("B", "g", ['k'], False)

    def test_process_dtd_B_h(self):
        self.checkit("B", "h", ['k'], True)

    def test_process_dtd_B_i(self):
        self.checkit("B", "i", ['k'], False)

    def test_process_dtd_B_j(self):
        self.checkit("B", "j", ['k'], True)

    def test_process_dtd_B_k(self):
        self.checkit("B", "k", [], False)

    def test_process_dtd_B_l(self):
        self.checkit("B", "l", None, False)

    def test_process_dtd_C_a(self):
        self.checkit("C", "a", ['b'], True)

    def test_process_dtd_C_b(self):
        self.checkit("C", "b", ['c'], True)

    def test_process_dtd_C_c(self):
        self.checkit("C", "c", ['d', 'e'], True)

    def test_process_dtd_C_d(self):
        self.checkit("C", "d", ['e'], False)

    def test_process_dtd_C_e(self):
        self.checkit("C", "e", ['f'], True)

    def test_process_dtd_C_f(self):
        self.checkit("C", "f", ['g', 'h', 'i', 'j', 'k'], False)

    def test_process_dtd_C_g(self):
        self.checkit("C", "g", ['k'], False)

    def test_process_dtd_C_h(self):
        self.checkit("C", "h", ['k'], True)

    def test_process_dtd_C_i(self):
        self.checkit("C", "i", ['k'], False)

    def test_process_dtd_C_j(self):
        self.checkit("C", "j", ['k'], True)

    def test_process_dtd_C_k(self):
        self.checkit("C", "k", [], False)

    def test_process_dtd_C_l(self):
        self.checkit("C", "l", None, False)

    def test_process_dtd_D_a(self):
        self.checkit("D", "a", ['b'], False)

    def test_process_dtd_D_b(self):
        self.checkit("D", "b", ['c'], True)

    def test_process_dtd_D_c(self):
        self.checkit("D", "c", ['d', 'e'], False)

    def test_process_dtd_D_d(self):
        self.checkit("D", "d", ['e'], False)

    def test_process_dtd_D_e(self):
        self.checkit("D", "e", ['f'], False)

    def test_process_dtd_D_f(self):
        self.checkit("D", "f", ['g', 'h', 'i', 'j', 'k'], True)

    def test_process_dtd_D_g(self):
        self.checkit("D", "g", ['k'], False)

    def test_process_dtd_D_h(self):
        self.checkit("D", "h", ['k'], True)

    def test_process_dtd_D_i(self):
        self.checkit("D", "i", ['k'], False)

    def test_process_dtd_D_j(self):
        self.checkit("D", "j", ['k'], True)

    def test_process_dtd_D_k(self):
        self.checkit("D", "k", [], False)

    def test_process_dtd_D_l(self):
        self.checkit("D", "l", None, False)

    def test_process_dtd_E_a(self):
        self.checkit("E", "a", ['e', 'f', 'g', 'h'], False)

    def test_process_dtd_E_b(self):
        self.checkit("E", "b", ['e', 'f', 'g', 'h'], True)

    def test_process_dtd_E_c(self):
        self.checkit("E", "c", ['e', 'f', 'g', 'h'], False)

    def test_process_dtd_E_d(self):
        self.checkit("E", "d", ['e', 'f', 'g', 'h'], True)

    def test_process_dtd_E_e(self):
        self.checkit("E", "e", [], False)

    def test_process_dtd_E_f(self):
        self.checkit("E", "f", [], False)

    def test_process_dtd_E_g(self):
        self.checkit("E", "g", [], True)

    def test_process_dtd_E_h(self):
        self.checkit("E", "h", [], True)

    def test_process_dtd_E_i(self):
        self.checkit("E", "i", None, False)

    def test_process_dtd_E_j(self):
        self.checkit("E", "j", None, False)

    def test_process_dtd_E_k(self):
        self.checkit("E", "k", None, False)

    def test_process_dtd_E_l(self):
        self.checkit("E", "l", None, False)

    def test_process_dtd_F_a(self):
        self.checkit("F", "a", ['e', 'f'], False)

    def test_process_dtd_F_b(self):
        self.checkit("F", "b", ['e', 'f'], True)

    def test_process_dtd_F_c(self):
        self.checkit("F", "c", ['e', 'f'], False)

    def test_process_dtd_F_d(self):
        self.checkit("F", "d", ['e', 'f'], True)

    def test_process_dtd_F_e(self):
        self.checkit("F", "e", ['f'], False)

    def test_process_dtd_F_f(self):
        self.checkit("F", "f", [], False)

    def test_process_dtd_F_g(self):
        self.checkit("F", "g", None, False)

    def test_process_dtd_F_h(self):
        self.checkit("F", "h", None, False)

    def test_process_dtd_F_i(self):
        self.checkit("F", "i", None, False)

    def test_process_dtd_F_j(self):
        self.checkit("F", "j", None, False)

    def test_process_dtd_F_k(self):
        self.checkit("F", "k", None, False)

    def test_process_dtd_F_l(self):
        self.checkit("F", "l", None, False)

    def test_process_dtd_G_a(self):
        self.checkit("G", "a", ['e'], False)

    def test_process_dtd_G_b(self):
        self.checkit("G", "b", ['e'], True)

    def test_process_dtd_G_c(self):
        self.checkit("G", "c", ['e'], False)

    def test_process_dtd_G_d(self):
        self.checkit("G", "d", ['e'], True)

    def test_process_dtd_G_e(self):
        self.checkit("G", "e", [], False)

    def test_process_dtd_G_f(self):
        self.checkit("G", "f", None, False)

    def test_process_dtd_G_g(self):
        self.checkit("G", "g", None, False)

    def test_process_dtd_G_h(self):
        self.checkit("G", "h", None, False)

    def test_process_dtd_G_i(self):
        self.checkit("G", "i", None, False)

    def test_process_dtd_G_j(self):
        self.checkit("G", "j", None, False)

    def test_process_dtd_G_k(self):
        self.checkit("G", "k", None, False)

    def test_process_dtd_G_l(self):
        self.checkit("G", "l", None, False)

    def test_process_dtd_H_a(self):
        self.checkit("H", "a", ['e'], False)

    def test_process_dtd_H_b(self):
        self.checkit("H", "b", ['e'], True)

    def test_process_dtd_H_c(self):
        self.checkit("H", "c", ['e'], False)

    def test_process_dtd_H_d(self):
        self.checkit("H", "d", ['e'], True)

    def test_process_dtd_H_e(self):
        self.checkit("H", "e", [], True)

    def test_process_dtd_H_f(self):
        self.checkit("H", "f", None, False)

    def test_process_dtd_H_g(self):
        self.checkit("H", "g", None, False)

    def test_process_dtd_H_h(self):
        self.checkit("H", "h", None, False)

    def test_process_dtd_H_i(self):
        self.checkit("H", "i", None, False)

    def test_process_dtd_H_j(self):
        self.checkit("H", "j", None, False)

    def test_process_dtd_H_k(self):
        self.checkit("H", "k", None, False)

    def test_process_dtd_H_l(self):
        self.checkit("H", "l", None, False)

    def test_process_dtd_I_a(self):
        self.checkit("I", "a", ['b'], False)

    def test_process_dtd_I_b(self):
        self.checkit("I", "b", ['c', 'd'], True)

    def test_process_dtd_I_c(self):
        self.checkit("I", "c", ['d'], False)

    def test_process_dtd_I_d(self):
        self.checkit("I", "d", ['e'], True)

    def test_process_dtd_I_e(self):
        self.checkit("I", "e", [], True)

    def test_process_dtd_I_f(self):
        self.checkit("I", "f", None, False)

    def test_process_dtd_I_g(self):
        self.checkit("I", "g", None, False)

    def test_process_dtd_I_h(self):
        self.checkit("I", "h", None, False)

    def test_process_dtd_I_i(self):
        self.checkit("I", "i", None, False)

    def test_process_dtd_I_j(self):
        self.checkit("I", "j", None, False)

    def test_process_dtd_I_k(self):
        self.checkit("I", "k", None, False)

    def test_process_dtd_I_l(self):
        self.checkit("I", "l", None, False)

    def test_process_dtd_J_a(self):
        self.checkit("J", "a", ['b', 'c', 'd', 'e', 'f', 'g'], False)

    def test_process_dtd_J_b(self):
        self.checkit("J", "b", ['c', 'd', 'e', 'f', 'g'], False)

    def test_process_dtd_J_c(self):
        self.checkit("J", "c", ['g'], False)

    def test_process_dtd_J_d(self):
        self.checkit("J", "d", ['g'], True)

    def test_process_dtd_J_e(self):
        self.checkit("J", "e", ['g'], False)

    def test_process_dtd_J_f(self):
        self.checkit("J", "f", ['g'], True)

    def test_process_dtd_J_g(self):
        self.checkit("J", "g", ['h'], False)

    def test_process_dtd_J_h(self):
        self.checkit("J", "h", [], False)

    def test_process_dtd_J_i(self):
        self.checkit("J", "i", None, False)

    def test_process_dtd_J_j(self):
        self.checkit("J", "j", None, False)

    def test_process_dtd_J_k(self):
        self.checkit("J", "k", None, False)

    def test_process_dtd_J_l(self):
        self.checkit("J", "l", None, False)

    def test_process_dtd_K_a(self):
        self.checkit("K", "a", ['b', 'c', 'd', 'e', 'f', 'g'], False)

    def test_process_dtd_K_b(self):
        self.checkit("K", "b", ['c', 'd', 'e', 'f', 'g'], False)

    def test_process_dtd_K_c(self):
        self.checkit("K", "c", ['g'], False)

    def test_process_dtd_K_d(self):
        self.checkit("K", "d", ['g'], True)

    def test_process_dtd_K_e(self):
        self.checkit("K", "e", ['g'], False)

    def test_process_dtd_K_f(self):
        self.checkit("K", "f", ['g'], True)

    def test_process_dtd_K_g(self):
        self.checkit("K", "g", ['h', 'i', 'j', 'k'], False)

    def test_process_dtd_K_h(self):
        self.checkit("K", "h", ['k'], False)

    def test_process_dtd_K_i(self):
        self.checkit("K", "i", ['k'], False)

    def test_process_dtd_K_j(self):
        self.checkit("K", "j", ['k'], False)

    def test_process_dtd_K_k(self):
        self.checkit("K", "k", [], False)

    def test_process_dtd_K_l(self):
        self.checkit("K", "l", None, False)

    def test_process_dtd_L_a(self):
        self.checkit("L", "a", ['b', 'c', 'd', 'e', 'f', 'h', 'i', 'j', 'k'],
                     False)

    def test_process_dtd_L_b(self):
        self.checkit("L", "b", ['c', 'd', 'e', 'f', 'h', 'i', 'j', 'k'], False)

    def test_process_dtd_L_c(self):
        self.checkit("L", "c", ['h', 'i', 'j', 'k'], False)

    def test_process_dtd_L_d(self):
        self.checkit("L", "d", ['h', 'i', 'j', 'k'], True)

    def test_process_dtd_L_e(self):
        self.checkit("L", "e", ['h', 'i', 'j', 'k'], False)

    def test_process_dtd_L_f(self):
        self.checkit("L", "f", ['h', 'i', 'j', 'k'], True)

    def test_process_dtd_L_g(self):
        self.checkit("L", "g", None, False)

    def test_process_dtd_L_h(self):
        self.checkit("L", "h", ['k'], False)

    def test_process_dtd_L_i(self):
        self.checkit("L", "i", ['k'], False)

    def test_process_dtd_L_j(self):
        self.checkit("L", "j", ['k'], False)

    def test_process_dtd_L_k(self):
        self.checkit("L", "k", [], False)

    def test_process_dtd_L_l(self):
        self.checkit("L", "l", None, False)

if __name__ == "__main__":
    unittest.main()

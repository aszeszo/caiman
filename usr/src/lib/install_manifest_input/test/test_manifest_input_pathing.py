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
Module containing tests for pathing.
'''

import os
import unittest

import solaris_install.manifest_input.mim as mim
import solaris_install.manifest_input as milib


# Disable warnings of unused args returned from mim functions.
#pylint: disable-msg=W0612
class TestMIMPathing(unittest.TestCase):
    '''Tests for XML xpath-like path processing.'''

    MIM_TEST_XML_FILENAME = "/tmp/mim_test.xml"

    # Eventually bring names into convention.
    #pylint: disable-msg=C0103
    def setUp(self):
        '''
        Create an XML file used for all tests, and set up environment.
        '''
        # Create test XML file.
        # This will be used for get / path-processing tests.
        with open(self.MIM_TEST_XML_FILENAME, "w") as test_xml:

            # Create/modify the file here.
            test_xml.write('<a>\n')
            test_xml.write('  aval\n')
            test_xml.write('  <b battr="b1attr" bbattr="bb1attrval">\n')
            test_xml.write('    bval1\n')
            test_xml.write('    <c cattr="c1attr">\n')
            test_xml.write('      cval1\n')
            test_xml.write('      <d dattr="d1attr">')
            test_xml.write('        dval1\n')
            test_xml.write('        <e>')
            test_xml.write('          eval1\n')
            test_xml.write('        </e>')
            test_xml.write('      </d>\n')
            test_xml.write('    </c>\n')
            test_xml.write('  </b>\n')
            test_xml.write('  <b battr="b2attr" bbattr="bb2attrval">\n')
            test_xml.write('    bval2\n')
            test_xml.write('    <c cattr="c2attr">\n')
            test_xml.write('      cval2\n')
            test_xml.write('      <d dattr="d2attr">')
            test_xml.write('        dval2\n')
            test_xml.write('      </d>\n')
            test_xml.write('    </c>\n')
            test_xml.write('  </b>\n')
            test_xml.write('</a>\n')

        os.environ["AIM_MANIFEST"] = self.MIM_TEST_XML_FILENAME

        # Note: while a valid DTD must be passed in, it is not used for this
        # suite of tests.  Indeed, the above xml file does not match it at all.
        root = os.environ["ROOT"]
        self.mim_obj = mim.ManifestInput("dummy", root +
                                         "/usr/share/install/ai.dtd")
        self.mim_obj.load(self.MIM_TEST_XML_FILENAME)

    def tearDown(self):
        if os.path.exists(self.MIM_TEST_XML_FILENAME):
            os.unlink(self.MIM_TEST_XML_FILENAME)

    def test_path_1(self):
        '''Access item w/simple path'''
        rval, path = self.mim_obj.get("/a")
        self.assertEqual(rval, "aval",
            "get(\"/a\") returned incorrect value: \"%s\"!" % rval)

    def test_path_2(self):
        '''Access item w/simple multi-branch path'''
        rval, path = self.mim_obj.get("/a/b/c/d/e")
        self.assertEqual(rval, "eval1",
            "get(\"/a/b/c/d/e\") " +
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_3(self):
        '''Access item w/path containing name="value" branch'''
        rval, path = self.mim_obj.get("/a/b=\"bval1\"/c")
        self.assertEqual(rval, "cval1",
            "get(\"/a/b=\"bval1\"/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_4(self):
        '''Access item w/path containing name[@attr="value"] branch'''
        rval, path = self.mim_obj.get("/a/b[@battr=\"b1attr\"]/c")
        self.assertEqual(rval, "cval1",
            "get(\"/a/b[@battr=\"b1attr\"]/c\") " +
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_5(self):
        '''Access item w/path containing name[@attr=value] branch'''
        rval, path = self.mim_obj.get("/a/b[@battr=b1attr]/c")
        self.assertEqual(rval, "cval1",
            "get(\"/a/b[@battr=b1attr]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_6(self):
        '''Access item w/path containing name[subname="value"] leaf'''
        rval, path = self.mim_obj.get("/a/b[c=\"cval1\"]")
        self.assertEqual(rval, "bval1",
            "get(\"/a/b[c=\"cval1\"]\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_7(self):
        '''Access item w/path containing name[subname=value] leaft'''
        rval, path = self.mim_obj.get("/a/b[c=cval1]")
        self.assertEqual(rval, "bval1",
            "get(\"/a/b[c=cval1]\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_8(self):
        '''Access item w/path containing name[subname="value"] branch'''
        rval, path = self.mim_obj.get("/a/b[c=\"cval2\"]/c")
        self.assertEqual(rval, "cval2",
            "get(\"/a/b[c=\"cval2\"]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_9(self):
        '''Access item w/path containing name[subname=value] branch'''
        rval, path = self.mim_obj.get("/a/b[c=cval2]/c")
        self.assertEqual(rval, "cval2",
            "get(\"/a/b[c=cval2]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_10(self):
        '''Access item w/path containing name[subname@attr="value"] leaf'''
        rval, path = self.mim_obj.get("/a/b[c@cattr=\"c2attr\"]")
        self.assertEqual(rval, "bval2",
            "get(\"/a/b[c@cattr=\"c2attr\"]\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_11(self):
        '''Access item w/path containing name[subname@attr=value] leaf'''
        rval, path = self.mim_obj.get("/a/b[c@cattr=c2attr]")
        self.assertEqual(rval, "bval2",
            "get(\"/a/b[c@cattr=c2attr]\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_12(self):
        '''Access item w/path containing name[subname@attr="value"] branch'''
        rval, path = self.mim_obj.get("/a/b[c@cattr=\"c2attr\"]/c/d")
        self.assertEqual(rval, "dval2",
            "get(\"/a/b[c@cattr=\"c2attr\"]/c/d\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_13(self):
        '''Access item w/path containing name[subname@attr=value] branch'''
        rval, path = self.mim_obj.get("/a/b[c@cattr=c2attr]/c/d")
        self.assertEqual(rval, "dval2",
            "get(\"/a/b[c@cattr=c2attr]/c/d\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_14(self):
        '''Access item w/path containing name[subpath="value"] branch'''
        rval, path = self.mim_obj.get("/a/b[c/d=\"dval2\"]/c")
        self.assertEqual(rval, "cval2",
            "get(\"/a/b[c/d=\"dval2\"]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_15(self):
        '''Access item w/path containing name[subpath=value] branch'''
        rval, path = self.mim_obj.get("/a/b[c/d=dval2]/c")
        self.assertEqual(rval, "cval2",
            "get(\"/a/b[c/d=dval2]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_16(self):
        '''Access item w/path containing name[subpath@attr="value"] branch'''
        rval, path = self.mim_obj.get("/a/b[c/d@dattr=\"d1attr\"]/c")
        self.assertEqual(rval, "cval1",
            "get(\"/a/b[c/d@dattr=\"d1attr\"]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_17(self):
        '''Access item w/path containing name[subpath@attr=value] branch'''
        rval, path = self.mim_obj.get("/a/b[c/d@dattr=d1attr]/c")
        self.assertEqual(rval, "cval1",
            "get(\"/a/b[c/d@dattr=d1attr]/c\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_18(self):
        '''Access an attr by specifying another quoted attr of same element.'''
        rval, path = self.mim_obj.get("/a/b[@battr=\"b2attr\"]@bbattr")
        self.assertEqual(rval, "bb2attrval",
            "get(\"/a/b[@battr=\"b2attr\"]@bbattr\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_19(self):
        '''Access an attr by specifying another attr of same element.'''
        rval, path = self.mim_obj.get("/a/b[@battr=b2attr]@bbattr")
        self.assertEqual(rval, "bb2attrval",
            "get(\"/a/b[@battr=\"b2attr\"]@bbattr\") "
            "returned incorrect value: \"%s\"!" % rval)

    def test_path_20(self):
        '''Try to access an item that doesn't exist (off end of tree)'''
        self.assertRaises(milib.MimMatchError,
            self.mim_obj.get, "/a/b/c/d/e/f")

    def test_path_21(self):
        '''Try to access an item that doesn't exist (deadend mid-tree)'''
        self.assertRaises(milib.MimMatchError,
            self.mim_obj.get, "/a/b/z")

    def test_path_22(self):
        '''Try to access an item that doesn't exist (deadend mid-tree)'''
        self.assertRaises(milib.MimMatchError,
            self.mim_obj.get, "/a/b/c")

    def test_path_23(self):
        '''Specify a path which matches more than one item'''
        self.assertRaises(milib.MimMatchError,
            self.mim_obj.get, "/a/b/c")

    def test_path_24(self):
        '''Specify a path with mismatching quotes (single vs double)'''
        self.assertRaises(milib.MimInvalidError,
            self.mim_obj.get, "/a/b[@battr=\'b1attr\"]")

    def test_path_25(self):
        '''Specify a path with mismatching quotes (uneven nesting)'''
        self.assertRaises(milib.MimInvalidError,
            self.mim_obj.get, "/a/b[@battr=\"b1attr]")

    def test_path_26(self):
        '''Specify a path with mismatching brackets (1)'''
        self.assertRaises(milib.MimInvalidError,
            self.mim_obj.get, "/a/b[@battr=\"b1attr\"")

    def test_path_27(self):
        '''Specify a path with mismatching brackets (2)'''
        self.assertRaises(milib.MimInvalidError,
            self.mim_obj.get, "/a/b@battr=\"b1attr\"]")

    def test_path_28(self):
        '''Specify a bogus path with invalid characters'''
        self.assertRaises(milib.MimInvalidError,
            self.mim_obj.get, "/a/b@b@a=ttr=\"b1attr\"]")

if __name__ == "__main__":
    unittest.main()

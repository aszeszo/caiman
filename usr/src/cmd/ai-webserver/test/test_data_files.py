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

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import gettext
import lxml.etree
import os
import unittest

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.data_files as df
import osol_install.libaiscf as smf

# Eventually rename variables per convention
# pylint: disable-msg=C0103

# Disable unused-arg warnings as this file is full of dummy routines.
# pylint: disable-msg=W0613

gettext.install("ai-test")


def do_nothing(*args, **kwargs):
    '''does nothing'''
    pass


class MockGetManNames(object):
    '''Class for mock AIdb.getManNames '''
    def __init__(self, man_name="noname"):
        self.name = man_name

    def __call__(self, queue):
        return self.name


class MockGetCriteria(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.crit_stripped = ["arch", "mem", "ipv4", "mac"]
        self.crit_unstripped = ["MINmem", "MINipv4", "MINmac",
                                "MAXmem", "MAXipv4", "MAXmac", "arch"]

    def __call__(self, queue, table=AIdb.MANIFESTS_TABLE, onlyUsed=False,
        strip=False):
        if strip:
            return self.crit_stripped
        else:
            return self.crit_unstripped


class MockDataFiles(object):
    '''Class for mock DataFiles'''
    def __init__(self):
        self.criteria = None
        self.database = MockDataBase()


class MockQuery(object):
    '''Class for mock query '''

    # Disable "method could be a function" warnings: inapprop for dummy methods
    # pylint: disable-msg=R0201
    def __init__(self):
        self.query = None

    def __call__(self, query, commit=False):
        self.query = query
        return self

    def waitAns(self):
        '''Dummy waitAns routine'''
        return

    def getResponse(self):
        '''Dummy getResponse routine'''
        return


class MockQueue(object):
    '''Class for mock database '''

    # Disable "method could be a function" warnings: inapprop for dummy methods
    # pylint: disable-msg=R0201
    def __init__(self):
        self.criteria = None

    def put(self, query):
        '''Dummy put routine'''
        return


class MockDataBase(object):
    '''Class for mock database '''
    def __init__(self):
        self.queue = MockQueue()

    def getQueue(self):
        '''Dummy getQueue routine'''
        return self.queue


class MockGetManifestCriteria(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.criteria = {"arch": "sparc",
                         "MINmem": None, "MAXmem": None, "MINipv4": None,
                         "MAXipv4": None, "MINmac": None, "MAXmac": None}

    def __call__(self, name, instance, queue, humanOutput=False,
                 onlyUsed=True):
        return self.criteria


class MockAIservice(object):
    '''Class for mock AIservice'''
    KEYERROR = False

    def __init__(self, *args, **kwargs):
        if MockAIservice.KEYERROR:
            raise KeyError()


class MockAISCF(object):
    '''Class for mock AISCF '''
    def __init__(self, *args, **kwargs):
        pass


class MockAIRoot(object):
    '''Class for mock AI_root'''
    def __init__(self, tag="auto_install", name=None):
        # name is value of name attribute in manifest
        if name:
            self.root = lxml.etree.Element(tag, name=name)
        else:
            self.root = lxml.etree.Element(tag)

    def getroot(self, *args, **kwargs):
        '''Dummy getroot routine'''
        return self.root

    def find(self, *args, **kwargs):
        '''Dummy find routine'''
        return self.root


class Manifest_Name(unittest.TestCase):
    '''Tests for manifest_name property'''

    def setUp(self):
        '''unit test set up'''
        self.smfDtd_save = df.DataFiles.smfDtd
        df.DataFiles.smfDtd = "/tmp"
        self.criteriaSchema_save = df.DataFiles.criteriaSchema
        protoroot = os.environ["ROOT"]
        crit_schema = protoroot + df.DataFiles.criteriaSchema
        df.DataFiles.criteriaSchema = crit_schema
        self.AI_schema = df.DataFiles.AI_schema
        df.DataFiles.AI_schema = None
        self.find_SC_from_manifest =  \
            df.DataFiles.find_SC_from_manifest
        df.DataFiles.find_SC_from_manifest = do_nothing
        self.verify_AI_manifest = \
            df.DataFiles.verify_AI_manifest
        df.DataFiles.verify_AI_manifest = do_nothing
        self.find_SC_from_manifest = \
            df.DataFiles.find_SC_from_manifest
        df.DataFiles.find_SC_from_manifest = do_nothing
        self.get_manifest_path = df.DataFiles.get_manifest_path
        df.DataFiles.get_manifest_path = do_nothing
        self.lxml_etree_DTD = lxml.etree.DTD
        lxml.etree.DTD = do_nothing

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        df.DataFiles.smfDtd = self.smfDtd_save
        df.DataFiles.criteriaSchema = self.criteriaSchema_save
        df.DataFiles.AI_schema = self.AI_schema
        df.DataFiles.find_SC_from_manifest = \
            self.find_SC_from_manifest
        df.DataFiles.verify_AI_manifest = \
            self.verify_AI_manifest
        df.DataFiles.find_SC_from_manifest = \
            self.find_SC_from_manifest
        df.DataFiles.get_manifest_path = self.get_manifest_path
        df.DataFiles.AI_root = None
        lxml.etree.DTD = self.lxml_etree_DTD

    def test_name_from_command_line_wins(self):
        '''Ensure manifest name from command line highest precedence'''
        attribute_name = "name_set_by_attribute"
        df.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=attribute_name)
        cmdline_name = "name_on_cmd_line"
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        dfiles = df.DataFiles(manifest_file=myfile,
                                            manifest_name=cmdline_name)
        os.unlink(myfile)
        self.assertEquals(cmdline_name, dfiles.manifest_name)

    def test_name_from_attribute_wins(self):
        '''Ensure manifest name from attribute second highest precedence'''
        attribute_name = "name_set_by_attribute"
        df.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=attribute_name)
        cmdline_name = None
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        dfiles = df.DataFiles(manifest_file=myfile,
                                            manifest_name=cmdline_name)
        os.unlink(myfile)
        self.assertEquals(attribute_name, dfiles.manifest_name)

    def test_name_from_filename(self):
        '''Ensure manifest name from filename set properly'''
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        df.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=None)
        dfiles = df.DataFiles(manifest_file=myfile,
                                            manifest_name=None)
        print "basename(myfile) = %s, dfiles:%s\n" % (
            os.path.basename(myfile), dfiles.manifest_name)
        os.unlink(myfile)
        self.assertEquals(os.path.basename(myfile), dfiles.manifest_name)

    def test_name_from_old_manifest(self):
        '''Ensure manifest name from old style manifest set properly'''
        attribute_name = "oldstylename"
        myfile = "/tmp/fake_manifest"
        f = open(myfile, "w")
        f.close()
        df.DataFiles.AI_root = MockAIRoot(tag="ai_manifest",
                                                         name=attribute_name)
        dfiles = df.DataFiles(manifest_file=myfile)
        os.unlink(myfile)
        self.assertEquals(attribute_name, dfiles.manifest_name)

    def test_no_identifying_tag(self):
        '''Ensure exception thrown if unable to identify manifest type'''
        myname = "lil_old_me"
        df.DataFiles.AI_root = MockAIRoot(tag="foobar",
                                                         name=myname)
        myfile = "/tmp/fake_manifest"
        f = open(myfile, "w")
        f.close()
        dfiles = df.DataFiles(manifest_file=myfile)
        os.unlink(myfile)
        self.assertRaises(SystemExit,
                          df.DataFiles.manifest_name.fget,
                          dfiles)

    def test_identify_python_script(self):
        '''Identify a python script as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/python")
        self.assertTrue(
            df.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_ksh93_script(self):
        '''Identify a ksh93 script as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/ksh93")
        self.assertTrue(
            df.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_xml_manifest(self):
        '''Identify an XML file as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("<?xml \"version=1.0\" encoding=\"UTF-8\"?>")
        self.assertFalse(
            df.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_bad_manifest(self):
        '''Identify a bad manifest file as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/csh")
        self.assertRaises(SystemExit,
                          df.DataFiles.manifest_is_a_script,
                          myfile)
        os.unlink(myfile)


if __name__ == '__main__':
    unittest.main()

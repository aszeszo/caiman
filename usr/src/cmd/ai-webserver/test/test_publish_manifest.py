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

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import gettext
import lxml.etree
import os
import tempfile
import unittest

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.publish_manifest as publish_manifest
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


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options. Some tests correctly output usage msg'''

    def setUp(self):
        '''unit test set up'''
        self.smf_AIservice = smf.AIservice
        smf.AIservice = MockAIservice
        self.smf_AISCF = smf.AISCF
        smf.AISCF = MockAISCF

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        smf.AIservice = self.smf_AIservice
        smf.AISCF = self.smf_AISCF

    def test_parse_no_options(self):
        '''Ensure no options caught'''
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, [])
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["mysvc", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)

        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, [])
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)
        myargs = ["manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)
        myargs = ["mysvc", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)

    def test_parse_invalid_options(self):
        '''Ensure invalid option flagged'''
        myargs = ["-n", "mysvc", "-m", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["-n", "mysvc", "-f", "manifest", "-u"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)

        myargs = ["-n", "mysvc", "-m", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)
        myargs = ["-n", "mysvc", "-f", "manifest", "-u"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n", "mysvc", "-f", "manifest", "-c"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["-n", "mysvc", "-f", "manifest", "-C"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["-n", "-f", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)
        myargs = ["-n", "mysvc", "-f"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)

        myargs = ["-n", "-f", "manifest"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)
        myargs = ["-n", "mysvc", "-f"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_UPDATE, myargs)

    def test_parse_minusC_nosuchfile(self):
        '''Ensure -C with no such file caught'''
        myargs = ["-n", "mysvc", "-f", "manifest", "-C", tempfile.mktemp()]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)

    def test_parse_mutually_exclusive(self):
        '''Ensure mutually exclusive -c and -C options caught'''
        myargs = ["-n", "mysvc", "-f", "manifest", "-c", "arch=i86pc", "-C",
                  tempfile.mktemp()]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)

    def test_parse_no_such_service(self):
        '''Ensure no such service is caught'''
        MockAIservice.KEYERROR = True
        myargs = ["-n", "mysvc", "-f", "manifest", "-c", "arch=i86pc"]
        self.assertRaises(SystemExit, publish_manifest.parse_options,
            publish_manifest.DO_ADD, myargs)


class CriteriaToDict(unittest.TestCase):
    '''Tests for criteria_to_dict'''

    def test_case_conversion(self):
        '''Ensure keys and converted to lower case, values kept as input'''
        criteria = ['ARCH=Sparc']
        cri_dict = publish_manifest.criteria_to_dict(criteria)
        self.assertEquals(len(cri_dict), 1)
        self.assertEquals(cri_dict['arch'], 'Sparc')

    def test_range_values(self):
        '''Ensure ranges saved correctly'''
        criteria = ['mem=1048-2096']
        cri_dict = publish_manifest.criteria_to_dict(criteria)
        self.assertEquals(len(cri_dict), 1)
        self.assertTrue(cri_dict['mem'], '1048-2096')

    def test_list_values(self):
        '''Ensure lists are saved correctly'''
        criteria = ['zonename="z1 z2 Z3"']
        cri_dict = publish_manifest.criteria_to_dict(criteria)
        self.assertEquals(len(cri_dict), 1)
        self.assertTrue(cri_dict['zonename'], 'z1 z2 Z3')

    def test_multiple_entries(self):
        '''Ensure multiple criteria handled correctly'''
        criteria = ['ARCH=i86pc', 'MEM=1024', 'IPV4=129.224.45.185',
                  'PLATFORM=SUNW,Sun-Fire-T1000',
                  'MAC=0:14:4F:20:53:94-0:14:4F:20:53:A0']
        cri_dict = publish_manifest.criteria_to_dict(criteria)
        self.assertEquals(len(cri_dict), 5)
        self.assertTrue(cri_dict['arch'], 'i86pc')
        self.assertTrue(cri_dict['mem'], '1024')
        self.assertTrue(cri_dict['ipv4'], '129.224.45.185')
        self.assertTrue(cri_dict['platform'], 'sunw,sun-fire-t1000')
        self.assertTrue(cri_dict['mac'], '0:14:4f:20:53:94-0:14:4f:20:53:a0')

    def test_dupicate_criteria_detected(self):
        '''Ensure duplicate criteria are detected'''
        criteria = ['ARCH=SPARC', 'arch=i386']
        self.assertRaises(ValueError, publish_manifest.criteria_to_dict,
                          criteria)

    def test_missing_equals(self):
        '''Ensure missing equals sign is detected'''
        criteria = ['mem2048']
        self.assertRaises(ValueError, publish_manifest.criteria_to_dict,
                          criteria)

    def test_missing_value(self):
        '''Ensure missing value is detected'''
        criteria = ['arch=']
        self.assertRaises(ValueError, publish_manifest.criteria_to_dict,
                          criteria)

    def test_missing_criteria(self):
        '''Ensure missing criteria is detected'''
        criteria = ['=i386pc']
        self.assertRaises(ValueError, publish_manifest.criteria_to_dict,
                          criteria)

    def test_no_criteria(self):
        '''Ensure case of no criteria is handled'''
        criteria = []
        cri_dict = publish_manifest.criteria_to_dict(criteria)
        self.assertEquals(len(cri_dict), 0)
        self.assertTrue(isinstance(cri_dict, dict))


class FindCollidingManifests(unittest.TestCase):
    '''Tests for find_colliding_manifests'''

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.aidb_getCriteria = AIdb.getCriteria
        self.aidb_getManifestCriteria = AIdb.getManifestCriteria
        AIdb.DBrequest = MockQuery()
        AIdb.getCriteria = MockGetCriteria()
        AIdb.getManifestCriteria = MockGetManifestCriteria()
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        AIdb.getCriteria = self.aidb_getCriteria
        AIdb.getManifestCriteria = self.aidb_getManifestCriteria

    def test_find_colliding_with_append(self):
        '''Ensure collsions found with append'''
        criteria = {'arch': ['sparc'], 'mem': None, 'ipv4': None, 'mac': None}
        collisions = {(u'nosuchmanifest.xml', 0): 'MINipv4,MAXipv4,'}
        self.assertRaises(SystemExit,
                          publish_manifest.find_colliding_manifests,
                          criteria, self.files.database, collisions,
                          append_manifest="appendmanifest")


class FindCollidingCriteria(unittest.TestCase):
    '''Tests for find_colliding_criteria'''

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.aidb_getCriteria = AIdb.getCriteria
        self.aidb_getManifestCriteria = AIdb.getManifestCriteria
        AIdb.DBrequest = MockQuery()
        AIdb.getCriteria = MockGetCriteria()
        AIdb.getManifestCriteria = MockGetManifestCriteria()
        self.files = MockDataFiles()

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        AIdb.getCriteria = self.aidb_getCriteria
        AIdb.getManifestCriteria = self.aidb_getManifestCriteria

    def test_criteria_max_greater_than_min(self):
        '''Catch MAX < MIN criteria'''
        criteria = {'mem': ['2048', '1024']}
        self.assertRaises(SystemExit,
                          publish_manifest.find_colliding_criteria,
                          criteria, self.files.database)

    def test_criteria_min_and_max_unbounded(self):
        '''Catch MIN and MAX unbounded'''
        criteria = {'mem': ['0', long(str(0xFFFFFFFFFFFFFFFF))]}
        self.assertRaises(SystemExit,
                          publish_manifest.find_colliding_criteria,
                          criteria, self.files.database)


class Manifest_Name(unittest.TestCase):
    '''Tests for manifest_name property'''

    def setUp(self):
        '''unit test set up'''
        self.smfDtd_save = publish_manifest.DataFiles.smfDtd
        publish_manifest.DataFiles.smfDtd = "/tmp"
        self.criteriaSchema_save = publish_manifest.DataFiles.criteriaSchema
        protoroot = os.environ["ROOT"]
        crit_schema = protoroot + publish_manifest.DataFiles.criteriaSchema
        publish_manifest.DataFiles.criteriaSchema = crit_schema
        self.AI_schema = publish_manifest.DataFiles.AI_schema
        publish_manifest.DataFiles.AI_schema = None
        self.find_SC_from_manifest =  \
            publish_manifest.DataFiles.find_SC_from_manifest
        publish_manifest.DataFiles.find_SC_from_manifest = do_nothing
        self.verify_AI_manifest = \
            publish_manifest.DataFiles.verify_AI_manifest
        publish_manifest.DataFiles.verify_AI_manifest = do_nothing
        self.find_SC_from_manifest = \
            publish_manifest.DataFiles.find_SC_from_manifest
        publish_manifest.DataFiles.find_SC_from_manifest = do_nothing
        self.get_manifest_path = publish_manifest.DataFiles.get_manifest_path
        publish_manifest.DataFiles.get_manifest_path = do_nothing
        self.lxml_etree_DTD = lxml.etree.DTD
        lxml.etree.DTD = do_nothing

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        publish_manifest.DataFiles.smfDtd = self.smfDtd_save
        publish_manifest.DataFiles.criteriaSchema = self.criteriaSchema_save
        publish_manifest.DataFiles.AI_schema = self.AI_schema
        publish_manifest.DataFiles.find_SC_from_manifest = \
            self.find_SC_from_manifest
        publish_manifest.DataFiles.verify_AI_manifest = \
            self.verify_AI_manifest
        publish_manifest.DataFiles.find_SC_from_manifest = \
            self.find_SC_from_manifest
        publish_manifest.DataFiles.get_manifest_path = self.get_manifest_path
        publish_manifest.DataFiles.AI_root = None
        lxml.etree.DTD = self.lxml_etree_DTD

    def test_name_from_command_line_wins(self):
        '''Ensure manifest name from command line highest precedence'''
        attribute_name = "name_set_by_attribute"
        publish_manifest.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=attribute_name)
        cmdline_name = "name_on_cmd_line"
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        dfiles = publish_manifest.DataFiles(manifest_file=myfile,
                                            manifest_name=cmdline_name)
        os.unlink(myfile)
        self.assertEquals(cmdline_name, dfiles.manifest_name)

    def test_name_from_attribute_wins(self):
        '''Ensure manifest name from attribute second highest precedence'''
        attribute_name = "name_set_by_attribute"
        publish_manifest.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=attribute_name)
        cmdline_name = None
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        dfiles = publish_manifest.DataFiles(manifest_file=myfile,
                                            manifest_name=cmdline_name)
        os.unlink(myfile)
        self.assertEquals(attribute_name, dfiles.manifest_name)

    def test_name_from_filename(self):
        '''Ensure manifest name from filename set properly'''
        myfile = "/tmp/file_name"
        f = open(myfile, "w")
        f.close()
        publish_manifest.DataFiles.AI_root = MockAIRoot(tag="auto_install",
                                                         name=None)
        dfiles = publish_manifest.DataFiles(manifest_file=myfile,
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
        publish_manifest.DataFiles.AI_root = MockAIRoot(tag="ai_manifest",
                                                         name=attribute_name)
        dfiles = publish_manifest.DataFiles(manifest_file=myfile)
        os.unlink(myfile)
        self.assertEquals(attribute_name, dfiles.manifest_name)

    def test_no_identifying_tag(self):
        '''Ensure exception thrown if unable to identify manifest type'''
        myname = "lil_old_me"
        publish_manifest.DataFiles.AI_root = MockAIRoot(tag="foobar",
                                                         name=myname)
        myfile = "/tmp/fake_manifest"
        f = open(myfile, "w")
        f.close()
        dfiles = publish_manifest.DataFiles(manifest_file=myfile)
        os.unlink(myfile)
        self.assertRaises(SystemExit,
                          publish_manifest.DataFiles.manifest_name.fget,
                          dfiles)

    def test_identify_python_script(self):
        '''Identify a python script as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/python")
        self.assertTrue(
            publish_manifest.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_ksh93_script(self):
        '''Identify a ksh93 script as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/ksh93")
        self.assertTrue(
            publish_manifest.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_xml_manifest(self):
        '''Identify an XML file as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("<?xml \"version=1.0\" encoding=\"UTF-8\"?>")
        self.assertFalse(
            publish_manifest.DataFiles.manifest_is_a_script(myfile))
        os.unlink(myfile)

    def test_identify_bad_manifest(self):
        '''Identify a bad manifest file as such'''
        myfile = "/tmp/fake_manifest"
        with open(myfile, "w") as f:
            f.write("#!/bin/csh")
        self.assertRaises(SystemExit,
                          publish_manifest.DataFiles.manifest_is_a_script,
                          myfile)
        os.unlink(myfile)


if __name__ == '__main__':
    unittest.main()

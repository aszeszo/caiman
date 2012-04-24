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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import gettext
import lxml.etree
import os
import shutil
import tempfile
import unittest
from pwd import getpwnam
from sqlite3 import dbapi2 as sqlite3

import osol_install.auto_install.common_profile as com
import osol_install.auto_install.create_profile as create_profile
import osol_install.auto_install.publish_manifest as publish_manifest
import osol_install.auto_install.service as svc
import osol_install.auto_install.service_config as config
import osol_install.libaiscf as smf

gettext.install("create-profile-test")


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

    def __call__(self, queue, table, onlyUsed=False, strip=False):
        if strip:
            return self.crit_stripped
        else:
            return self.crit_unstripped


class MockGetColumns(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.crit_stripped = ["arch", "mem", "ipv4", "mac"]
        self.crit_unstripped = ["MINmem", "MINipv4", "MINmac",
                                "MAXmem", "MAXipv4", "MAXmac", "arch"]

    def __call__(self, queue, table, onlyUsed=False, strip=False):
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
    def __init__(self):
        self.query = None

    def __call__(self, query, commit=False):
        self.query = query
        return self

    def waitAns(self):
        return

    def getResponse(self):
        return


class MockQueue(object):
    '''Class for mock database '''
    def __init__(self):
        self.criteria = None

    def put(self, query):
        return


class MockDataBase(object):
    '''Class for mock database '''
    def __init__(self):
        self.queue = MockQueue()

    def getQueue(self):
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


class MockAIService(object):
    '''Class for mock AIService'''

    database_path = None
    image = None

    def __init__(self, name=None):
        if name is not None:
            self.name = name


class MockAIRoot(object):
    '''Class for mock _AI_root'''
    def __init__(self, tag="auto_install", name=None):
        # name is value of name attribute in manifest
        if name:
            self.root = lxml.etree.Element(tag, name=name)
        else:
            self.root = lxml.etree.Element(tag)

    def getroot(self, *args, **kwargs):
        return self.root

    def find(self, *args, **kwargs):
        return self.root


class MockIsService(object):
    '''Class for mock is_service '''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, name):
        return True


class MockInstallAdmImage(object):
    '''Class for mock InstallAdmImage class'''

    path = None

    def __init__(self, *args, **kwargs):
        pass


class MockEuid(object):
    '''Class for mock geteuid() '''

    @classmethod
    def geteuid(cls):
        '''return non root uid'''
        return 1


class MockSetUIDasEUID(object):
    '''Class for mock SetUIDasEUID class '''

    def __enter__(self):
        ''' do nothing '''
        pass

    def __exit__(self, *exc_info):
        ''' do nothing '''
        pass


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
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, [])
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)
        myargs = ["profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)
        myargs = ["mysvc", "profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)

        self.assertRaises(SystemExit, create_profile.parse_options,
            create_profile.DO_UPDATE, [])
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)
        myargs = ["profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)
        myargs = ["mysvc", "profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)

    def test_parse_invalid_options(self):
        '''Ensure invalid option flagged'''
        myargs = ["-n", "mysvc", "-p", "profile", "-u"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)
        myargs = ["-n", "mysvc", "-p", "profile", "-a"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)

        myargs = ["-n", "mysvc", "-p", "profile", "-u"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)
        myargs = ["-n", "mysvc", "-p", "profile", "-a"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)

    def test_parse_options_novalue(self):
        '''Ensure options with missing value caught'''
        myargs = ["-n", "mysvc", "-p", "profile", "-c"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)
        myargs = ["-n", "-f", "profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)
        myargs = ["-n", "mysvc", "-p"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_CREATE, myargs)

        myargs = ["-n", "mysvc", "-p", "profile", "-f"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)
        myargs = ["-n", "-f", "profile"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)
        myargs = ["-n", "mysvc", "-p"]
        self.assertRaises(SystemExit, create_profile.parse_options,
                create_profile.DO_UPDATE, myargs)


class CriteriaToDict(unittest.TestCase):
    '''Tests for criteria_to_dict'''
    def setUp(self):
        '''unit test set up'''
        self.config_is_service = config.is_service
        config.is_service = MockIsService

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        config.is_service = self.config_is_service

    def test_case_conversion(self):
        '''Ensure keys converted to lower case, values kept as input'''
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

    def test_duplicate_criteria_detected(self):
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

    def test_parse_multi_options(self):
        '''Ensure multiple profiles processed'''
        myargs = ["-n", "mysvc", "-f", "profile", "-f", "profile2"]
        options = create_profile.parse_options(create_profile.DO_CREATE,
                myargs)
        self.assertEquals(options.profile_file, ["profile", "profile2"])

    def test_perform_templating(self):
        '''Test SC profile templating'''
        # load template variables for translation
        template_dict = {'AI_ARCH': 'sparc', 'AI_MAC': '0a:0:0:0:0:0'}
        # provide template to test
        tmpl_str = "{{AI_ARCH}} {{AI_MAC}}"
        # do the templating
        profile = com.perform_templating(tmpl_str, template_dict)
        # check for expected results
        self.assertNotEquals(profile.find('sparc'), -1)
        self.assertNotEquals(profile.find('0A:0:0:0:0:0'), -1)  # to upper
        # simulate situation in which criteria are missing
        self.assertRaises(KeyError, com.perform_templating,
                          tmpl_str + " {{FOO_BAR}}")
        # test zone case where only criterion is zone name
        zone_dict = {'AI_ZONENAME': 'myzone'}
        profile = com.perform_templating("{{AI_ZONENAME}}", zone_dict)
        self.assertNotEquals(profile.find('myzone'), -1)


class DoUpdateProfile(unittest.TestCase):
    '''Tests for do_update_profile '''

    def setUp(self):
        '''unit test set up'''

        # create a temporary directory for db and files
        self.tmp_dir = tempfile.mkdtemp()

        # create profile file
        orig_prof = [
                '<?xml version="1.0"?>\n',
                '<!DOCTYPE service_bundle SYSTEM '
                '"/usr/share/lib/xml/dtd/service_bundle.dtd.1">\n',
                '<service_bundle type="profile" name="sysconfig">\n',
                '<service name="system/identity" version="1"'
                '    type="service">\n',
                '   <instance name="node" enabled="true">\n',
                '    <property_group name="config" type="application">\n',
                '        <propval name="nodename" value="client"/>\n',
                '    </property_group>\n',
                '    <property_group name="install_ipv4_interface"'
                '        type="application">\n',
                '       <propval name="name" value="net0/v4"/>\n',
                '       <propval name="address_type" value="static"/>\n',
                '      <propval name="static_address" type="net_address_v4"'
                '       value="10.0.0.0/8"/>\n',
                '    </property_group>\n',
                '   </instance>\n',
                '</service>\n',
                '</service_bundle>\n']
        old_prof = tempfile.NamedTemporaryFile(dir=self.tmp_dir, delete=False)
        self.old_file = old_prof.name
        old_prof.writelines(orig_prof)
        old_prof.close()

        #create dummy db and populate it with temporary profile
        dbfile = tempfile.NamedTemporaryFile(dir=self.tmp_dir, delete=False)
        self.dbpath = dbfile.name
        dbcon = sqlite3.connect(self.dbpath, isolation_level=None)
        dbcon.execute("CREATE TABLE profiles (name TEXT, file TEXT,"
                    "arch TEXT, hostname TEXT, MINmac INTEGER, MAXmac INTEGER,"
                    "MINipv4 INTEGER, MAXipv4 INTEGER, cpu TEXT,"
                    "platform TEXT, MINnetwork INTEGER, MAXnetwork INTEGER,"
                    "MINmem INTEGER, MAXmem INTEGER, zonename TEXT)")

        dbcon.execute("CREATE TABLE manifests (name TEXT, instance INTEGER, "
                    "arch TEXT, MINmac INTEGER, MAXmac INTEGER,"
                    "MINipv4 INTEGER, MAXipv4 INTEGER, cpu TEXT,"
                    "platform TEXT, MINnetwork INTEGER, MAXnetwork INTEGER,"
                    "MINmem INTEGER, MAXmem INTEGER, zonename TEXT)")

        q_insert = "INSERT INTO profiles VALUES('profile1','%s', NULL, NULL, "\
                    "NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, "\
                    "NULL, NULL)" % (self.old_file,)

        dbcon.execute(q_insert)
        dbcon.close()

        # initialize service and dbpath
        self.service_AIService = svc.AIService
        create_profile.AIService = MockAIService
        MockAIService.database_path = self.dbpath
        MockAIService.image = MockInstallAdmImage()

        self.config_is_service = config.is_service
        config.is_service = MockIsService

        self.sc_profile_dir = com.INTERNAL_PROFILE_DIRECTORY
        com.INTERNAL_PROFILE_DIRECTORY = self.tmp_dir

        # set "webservd" uid and gid to user's, allowing user
        # to perform chown on profile file
        self.sc_uid = com.WEBSERVD_UID
        self.sc_gid = com.WEBSERVD_GID
        com.WEBSERVD_UID = getpwnam(os.environ.get("USER"))[2]
        com.WEBSERVD_GID = getpwnam(os.environ.get("USER"))[3]

        self.os_geteuid = os.geteuid
        os.geteuid = MockEuid.geteuid

        self.check_auth_and_euid = create_profile.check_auth_and_euid
        create_profile.check_auth_and_euid = do_nothing

        self.SetUIDasEUID = com.SetUIDasEUID
        com.SetUIDasEUID = MockSetUIDasEUID

    def tearDown(self):
        '''unit test tear down'''

        com.WEBSERVD_UID = self.sc_uid
        com.WEBSERVD_GID = self.sc_gid
        com.INTERNAL_PROFILE_DIRECTORY = self.sc_profile_dir
        config.is_service = self.config_is_service
        svc.AIService = self.service_AIService
        os.geteuid = self.os_geteuid
        shutil.rmtree(self.tmp_dir)
        create_profile.check_auth_and_euid = self.check_auth_and_euid
        com.SetUIDasEUID = self.SetUIDasEUID

    def test_profile(self):
        ''' test update profile'''

        change_prof = [
                '<?xml version="1.0"?>\n',
                '<!DOCTYPE service_bundle SYSTEM '
                '       "/usr/share/lib/xml/dtd/service_bundle.dtd.1">\n',
                '<service_bundle type="profile" name="sysconfig">\n',
                '<service name="system/identity" version="1"'
                '       type="service">\n',
                '   <instance name="node" enabled="true">\n',
                '    <property_group name="config" type="application">\n',
                '        <propval name="nodename" value="ai-client"/>\n',
                '    </property_group>\n',
                '    <property_group name="install_ipv4_interface"'
                '       type="application">\n',
                '       <propval name="name" value="net1/v4"/>\n',
                '       <propval name="address_type" value="static"/>\n',
                '      <propval name="static_address" type="net_address_v4"'
                '       value="10.0.0.0/8"/>\n',
                '    </property_group>\n',
                '   </instance>\n',
                '</service>\n',
                '</service_bundle>\n']

        new_prof = tempfile.NamedTemporaryFile(dir=self.tmp_dir, delete=False)
        new_prof.writelines(change_prof)
        new_prof.close()

        cmd_options = ["-n", "svc", "-f", new_prof.name, "-p", "profile1"]
        create_profile.do_update_profile(cmd_options)

        # read old file and new file in list and make sure they are equal
        prof_file = open(self.old_file, "r")
        profile = prof_file.readlines()
        prof_file.close()

        self.assertEqual(profile, change_prof)


if __name__ == '__main__':
    unittest.main()

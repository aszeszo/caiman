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
'''test_cgi_get_manifest runs tests on the cgi_get_manifest.py cgi-bin script
'''
import cgi
import gettext
import os
import sys
import unittest

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.service as service
import osol_install.auto_install.service_config as config
import osol_install.libaiscf as smf
import osol_install.libaimdns as libaimdns

import cgi_get_manifest


class RedirectedOutput(object):
    '''Class for capturing output from standard interfaces.
    '''
    def __init__(self):
        self.output = []

    def __repr__(self):
        '''return the representation of self.output as a string
        '''
        string = ''
        for i in range(len(self.output)):
            string += self.output[i]
        return string

    def __len__(self):
        '''return the length of self.output
        '''
        astr = self.__repr__()
        return len(astr)

    def write(self, string):
        '''capture the output into self.output
        '''
        self.output.append(string)

    def clear(self):
        '''reset self.output
        '''
        self.output = []

    def startswith(self, string):
        '''returns the output startswith string
        '''
        astr = self.__repr__()
        return astr.startswith(string)


class MockDataBase(object):
    '''Class for mock database '''
    def __init__(self):
        self.queue = MockQueue()

    def getQueue(self):
        return self.queue


class MockverifyDBStructure(object):
    '''Class for mock verifyDBStructure'''
    def __init__(self):
        return

    def __call__(self):
        return


class MockQueue(object):
    '''Class for mock database '''
    def __init__(self):
        self.criteria = None

    def put(self, query):
        return


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


class MockGetCriteria(object):
    '''Class for mock getCriteria '''
    def __init__(self):
        self.crit_stripped = ["arch", "mem", "ipv4", "mac"]
        self.crit_unstripped = ["MINmem", "MINipv4", "MINmac",
                                "MAXmem", "MAXipv4", "MAXmac", "arch"]

    def __call__(self, queue, onlyUsed=False, strip=False):
        if strip:
            return self.crit_stripped
        else:
            return self.crit_unstripped


class MockMiniFieldStorage(object):
    def __init__(self, name, value):
        """Constructor from field name and value."""
        self.name = name
        self.value = value


class MockFieldStorage(object):
    '''Class for mock cgi'''
    def __init__(self, version='1.0', service='someservice',
                       no_default='False', postdata='arch=i86pc'):
        self.version = MockMiniFieldStorage('version', version)
        self.service = MockMiniFieldStorage('service', service)
        self.no_default = MockMiniFieldStorage('no_default', no_default)
        self.postdata = MockMiniFieldStorage('postdata', postdata)
        self.dict = {'version': self.version,
                     'service': self.service,
                     'no_default': self.no_default,
                     'postData': self.postdata}

    def __call__(self):
        return self.dict

    def __contains__(self, something):
        return something in self.dict

    def __getitem__(self, key):
        return self.dict[key]


class MockEnviron(object):
    '''Class for mock environment'''
    def __init__(self, method='POST', port=5555):
        self.method = method
        self.port = port
        self.dict = {'REQUEST_METHOD': method, 'SERVER_PORT': port}

    def __call__(self):
        return self.dict

    def __getitem__(self, key):
        return self.dict[key]


class MockDataFiles(object):
    '''Class for mock DataFiles'''
    def __init__(self):
        self.criteria = None
        self.database = MockDataBase()


class MockGetAllServiceNames(object):
    '''Class for mock get_all_service_names'''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self):
        return ['aservice']


class MockGetServicePort(object):
    '''Class for mock get_service_port'''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, service):
        return 5555


class MockVersion(object):
    '''Class for mock version '''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self):
        return service.AIService.EARLIEST_VERSION


class MockAIService(object):
    '''Class for mock AIService '''
    def __init__(self):
        self.database_path = ""

    def version(self):
        return 3


class MockAISCF(object):
    '''Class for mock AISCF class'''
    def __init__(self):
        pass

    def __call__(self, FMRI):
        return self


class MockGetInteger(object):
    '''Class to Mock libaimdns.getinteger_property'''
    def __init__(self, srvinst, prop):
        self.prop = 5555

    def __getitem__(self, srvinst, prop):
        return self.prop


class testGetParameters(unittest.TestCase):
    '''Tests for get_parameters'''
    # Version value unique to the old services
    OLD_VERSION = '0.5'

    # Version value unique to the 1.0 services
    VERSION_1_0 = '1.0'

    # Parameters used within both services
    SERVICE = 'aservice'
    NO_DEFAULT = 'True'
    POSTDATA = 'arch=i86pc;mac=080027138669;ipv4=010000002015;mem=1967'

    def test_compatibility_get_parameters(self):
        '''validate get_parameters for compatibility test'''
        field = MockFieldStorage(version=self.OLD_VERSION,
                                        service=self.SERVICE,
                                        postdata=self.POSTDATA)
        (version, servicename, no_default, postData) = \
                                    cgi_get_manifest.get_parameters(field)

        assert version == self.OLD_VERSION, \
               'wrong version for compatibility test'
        assert servicename == self.SERVICE, \
               'servicename incorrect for compatibility test'
        # old services would not be passed the 'no_default' parameter from
        # the client, so that should have been set to false.
        assert no_default == False, \
               'no_default incorrect for compatibility test'
        assert postData == self.POSTDATA, \
               'postData incorrect for compatibility test'

    def test_1_0_get_parameters(self):
        '''validate get_parameters for version 1.0 test'''
        field = MockFieldStorage(version=self.VERSION_1_0,
                                 service=self.SERVICE,
                                 no_default=self.NO_DEFAULT,
                                 postdata=self.POSTDATA)
        (version, servicename, no_default, postData) = \
                                    cgi_get_manifest.get_parameters(field)

        assert version == self.VERSION_1_0, \
               'wrong version for 1.0 service test'
        assert servicename == self.SERVICE, \
               'servicename incorrect for 1.0 service test'
        assert str(no_default).lower() == self.NO_DEFAULT.lower(), \
               'no_default incorrect for 1.0 service test'
        assert postData == self.POSTDATA, \
               'postData incorrect for 1.0 service test'


class testGetEnvironment(unittest.TestCase):
    '''Tests for get_environment'''
    # Data method for both must be POST
    METHOD = 'POST'

    # Some port
    PORT = 56789

    def setUp(self):
        '''unit test set up'''
        self.osenv_orig = os.environ
        self.mockosenv = MockEnviron(method=self.METHOD, port=self.PORT)
        os.environ = self.mockosenv

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        os.environ = self.osenv_orig

    def test_get_environment_information(self):
        '''validate get_environment_information for compatibility test'''
        (method, port) = cgi_get_manifest.get_environment_information()

        assert method == self.METHOD, 'method incorrect test'
        assert port == self.PORT, 'port incorrect test'


class testSendCriteria(unittest.TestCase):
    '''Tests for send_criteria'''
    PORT = 46502
    SERVICE = 'aservice'

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery
        self.files = MockDataFiles()

        self.redirected = RedirectedOutput()
        self.stdout_orig = sys.stdout
        sys.stdout = self.redirected

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        sys.stdout = self.stdout_orig

    def test_send_needed_criteria(self):
        '''validate send_needed_criteria test for compatibility test'''
        cgi_get_manifest.send_needed_criteria(int(self.PORT))
        sys.stdout = self.stdout_orig
        assert self.redirected.startswith("Content-Type: text/html"), \
                'unexpected output for send_needed_criteria'


class testListCriteria(unittest.TestCase):
    '''Tests for list_criteria'''
    SERVICE = 'aservice'

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery
        self.files = MockDataFiles()

        self.config_get_all_service_names = config.get_all_service_names
        config.get_all_service_names = MockGetAllServiceNames()
        self.config_get_service_port = config.get_service_port
        config.get_service_port = MockGetServicePort()

        self.aiscf_orig = smf.AISCF
        self.mockaiscf = MockAISCF()
        smf.AISCF = self.mockaiscf

        self.getint_orig = libaimdns.getinteger_property
        self.getinteger_property = MockGetInteger
        libaimdns.getinteger_property = self.getinteger_property

        self.stdout_orig = sys.stdout
        self.redirected = RedirectedOutput()
        sys.stdout = self.redirected

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        sys.stdout = self.stdout_orig
        libaimdns.getinteger_property = self.getint_orig
        config.get_all_service_names = self.config_get_all_service_names
        config.get_service_port = self.config_get_service_port 

    def test_list_manifests(self):
        '''validate list_manifests test'''

        cgi_get_manifest.list_manifests(self.SERVICE)
        sys.stdout = self.stdout_orig

        assert self.redirected.startswith('Content-Type: text/html'), \
                'expected html output'
        assert self.SERVICE in str(self.redirected), \
               'service (%s) was not in output' % self.SERVICE
        assert 'not found' in str(self.redirected), \
                'service (%s) not was found' % self.SERVICE


class testSendManifest(unittest.TestCase):
    '''Tests for send_manifest'''
    SERVICE = 'aservice'
    POSTDATA = 'arch=i86pc;mac=080027138669;ipv4=010000002015;mem=1967'
    PORT = 56789

    def setUp(self):
        '''unit test set up'''
        self.aidb_DBrequest = AIdb.DBrequest
        self.mockquery = MockQuery()
        AIdb.DBrequest = self.mockquery
        self.files = MockDataFiles()

        self.aiservice = service.AIService
        self.AIService = MockAIService()
        service.AIService.version = MockVersion()

        self.config_get_all_service_names = config.get_all_service_names
        config.get_all_service_names = MockGetAllServiceNames()
        self.config_get_service_port = config.get_service_port
        config.get_service_port = MockGetServicePort()

        self.stdout_orig = sys.stdout
        self.redirected = RedirectedOutput()
        sys.stdout = self.redirected

    def tearDown(self):
        '''unit test tear down
        Functions originally saved in setUp are restored to their
        original values.
        '''
        AIdb.DBrequest = self.aidb_DBrequest
        service.AIService = self.aiservice
        sys.stdout = self.stdout_orig
        config.get_all_service_names = self.config_get_all_service_names
        config.get_service_port = self.config_get_service_port 

    def test_send_manifest(self):
        '''validate send_manifest test'''
        cgi_get_manifest.send_manifest(form_data=self.POSTDATA,
                                       port=self.PORT,
                                       servicename=self.SERVICE)
        sys.stdout = self.stdout_orig
        assert self.redirected.startswith('Content-Type: text/html'), \
                   'send_manifest expected text/html content'
        assert 'unable to find' in str(self.redirected), \
                   'service (%s) was found' % self.SERVICE


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    unittest.main()

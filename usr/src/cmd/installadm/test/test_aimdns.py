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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''Testcase for aimdns

To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''
import gettext
import sys
import unittest

import pybonjour as pyb

import osol_install.auto_install.aimdns_mod as aimdns
import osol_install.auto_install.installadm_common as common

from nose.plugins.skip import SkipTest

from solaris_install import CalledProcessError, Popen


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


class TestRegCallback(unittest.TestCase):
    '''Class TestRegCallback - class to test the register_callback
       functionality
    '''
    name = 'nonsense-service'
    regtype = 'nonsense-regtype'
    domain = 'nonsense-domain'

    def test_registration_callback(self):
        '''test registration callback output
        '''
        gettext.install("ai", "/usr/lib/locale")
        redirected = RedirectedOutput()
        mdns = aimdns.AImDNS()
        sys.stdout = redirected
        mdns._register_callback(None, None, pyb.kDNSServiceErr_NoError,
                           self.name, self.regtype, self.domain)
        sys.stdout = sys.__stdout__
        assert len(redirected) == 0, 'unexpected output'

        redirected.clear()
        mdns.verbose = True
        sys.stdout = redirected
        mdns._register_callback(None, None, pyb.kDNSServiceErr_NoError,
                           self.name, self.regtype, self.domain)
        sys.stdout = sys.__stdout__
        assert len(redirected) != 0, 'expected output'

        compare = RedirectedOutput()
        sys.stdout = compare
        print _('Registered service:')
        print _('\tname    = %s') % self.name
        print _('\tregtype = %s') % self.regtype
        print _('\tdomain  = %s') % self.domain
        sys.stdout = sys.__stdout__
        assert str(redirected) == str(compare), 'not equal'


class TestBrowseCallback(unittest.TestCase):
    '''Class TestBrowseCallback - class to test _browse_callback functionality
    '''
    name = 'nonsense-service'
    regtype = '_OSInstall._tcp'
    domain = 'local'

    def test_browse_callback(self):
        '''test browse callback
        '''
        # Ensure system/install/server SMF service is available
        check_install_SMF()

        mdns = aimdns.AImDNS()
        rtn = mdns._browse_callback(None, None, 0, pyb.kDNSServiceErr_Unknown,
                            self.name, self.regtype, self.domain)
        assert rtn == None, 'error not recognized'

        mdns.servicename = 'something'
        mdns._lookup = True
        rtn = mdns._browse_callback(None, None, 0, pyb.kDNSServiceErr_NoError,
                            self.name, self.regtype, self.domain)
        assert rtn == None, 'servicename recognized'

        redirected = RedirectedOutput()
        mdns.servicename = self.name
        mdns.timeout = 1
        sys.stderr = redirected
        # _ needs to get instantiated within the redirected output
        gettext.install("ai", "/usr/lib/locale")
        mdns._resolved = list()
        mdns._browse_callback(None, None, 0, pyb.kDNSServiceErr_NoError,
                            self.name, self.regtype, self.domain)
        sys.stderr = sys.__stderr__
        assert str(redirected).startswith(_('warning')), \
            'no warning, unexpected output'


class TestCompareIPv4(unittest.TestCase):
    '''Class TestCompareIPv4 - class to test compare_ipv4 functionality
    '''
    tests = [
              {'ip1':'192.168.168.10/24',
               'ip2':'192.168.168.10',
               'result':True,
               'name':'three octets mask'},
              {'ip1':'192.168.168.9',
               'ip2':'192.168.10.9',
               'result':False,
               'name':'no match mask'},
              {'ip1':'192.168.0.1/32',
               'ip2':'192.168.0.1',
               'result':True,
               'name':'all octets mask'},
              {'ip1':'192.168.0.1/0',
               'ip2':'192.168.0.1',
               'result':True,
               'name':'zero mask'}
            ]

    def test_compare_ipv4(self):
        '''test compare_ipv4 returns valid results
        '''
        for i in range(len(self.tests)):
            ip1 = self.tests[i]['ip1']
            ip2 = self.tests[i]['ip2']
            result = self.tests[i]['result']
            assert common.compare_ipv4(ip1, ip2) == result, \
                    "compare_ipv4 failed %s test" % self.tests[i]['name']

            assert not common.compare_ipv4('10.0.100.1', '10.0.15.5/48'), \
                    "compare_ipv4 failed for invalid CIDR mask"

            assert common.compare_ipv4('10.0.15.10', '10.0.15.10/32'), \
                    "compare_ipv4 failed for & mask"

            assert common.compare_ipv4('10.0.15.10', '10.0.15.10'), \
                    "compare_ipv4 failed for identical IP address"

    def test_in_network(self):
        '''test in_network returns valid results
        '''
        for i in range(len(self.tests)):
            ip1 = self.tests[i]['ip1']
            ip2 = self.tests[i]['ip2']
            result = self.tests[i]['result']
            assert common.in_networks(ip1, [ip2]) == result, \
                    "in_network failed %s test" % self.tests[i]['name']

    def test_convert_cidr_mask(self):
        '''test _convert_cidr_mask returns something reasonable
        '''
        assert not common._convert_cidr_mask(48), \
                "_convert_cidr_mask failed for edge case cidr > 32"
        assert common._convert_cidr_mask(0) == '0.0.0.0', \
                "_convert_cidr_mask failed for 0 cidr mask"
        assert common._convert_cidr_mask(24) == '255.255.255.0', \
                "_convert_cidr_mask failed for 24 cidr mask"
        assert common._convert_cidr_mask(8) == '255.0.0.0', \
                "_convert_cidr_mask failed for 8 cidr mask"


def check_install_SMF():
    ''' Check if install/server SMF services is available.
        returning True if available and False if not.
    '''
    # Ensure system/install/server SMF service is available and online
    cmd = ["/usr/bin/svcs", "svc:/system/install/server"]
    try:
        output = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        if output.stdout.split()[3] != 'online':
            raise SkipTest("svc:/system/install/server not enabled")
    except CalledProcessError:
        # This system does not have the service so skip the test
        raise SkipTest("svc:/system/install/server not installed")


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    unittest.main()

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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
'''Testcase for aimdns

To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''
import gettext
import subprocess
import sys
import time
import threading
import unittest

import pybonjour as pyb

import aimdns
import osol_install.auto_install.installadm_common as common


class RegisterAPI(unittest.TestCase):
    '''Class: RegisterAPI - used to test the AImDNS class
    '''
    bogussvc = "self-registration-test-svc"

    class Register(threading.Thread):
        '''Class to register a mDNS record in a thread
        '''

        def __init__(self, mdns_obj, servicename, port, comments):
            '''
            Call register on the provided mdns_obj
            '''
            threading.Thread.__init__(self)
            self.mdns = mdns_obj
            self.servicename = servicename
            self.port = port
            self.comments = comments

        def run(self):
            '''Method to actually register the mDNS record
            '''
            self.mdns.register(servicename=self.servicename,
                               port=self.port, comments=self.comments)

        def __del__(self):
            '''Method to clear all registrations
            '''
            # del(mdns) does not work for the test as it is not called
            # immediately thus the service is still registered
            self.mdns.__del__()

    def test_register(self):
        '''Test the AImDNS().register() method
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        reg = self.Register(mdns, self.bogussvc,
                            port=9999, comments="bar=foo")
        reg.start()
        time.sleep(2)

        # manual output to stdout for debugging
        # dns_sd = "/bin/dns-sd"
        # proc = subprocess.Popen([dns_sd, "-B", common.REGTYPE, mdns.domain],
        #                            stdout=None,
        #                            stderr=subprocess.STDOUT)
        # time.sleep(2)
        # proc.terminate()

        # ensure service exists
        mdns2 = aimdns.AImDNS()
        mdns2.timeout = 2
        assert mdns2.find(servicename=self.bogussvc) == True, \
               "Did not find unique service: %s!" % self.bogussvc

        # ensure service goes away with module
        # del(reg) does not work for the test as it is not called
        # immediately thus the service is still registered causing
        # the mdns2.find() to fail
        reg.__del__()
        time.sleep(0.5)

        mdns2.reset()
        # negative test -- ensure service nolonger exists
        assert mdns2.find(servicename=self.bogussvc) == False, \
               "Still finding unique service: %s!" % self.bogussvc


class FindAPI(unittest.TestCase):
    '''Class: FindAPI - class to test the find method of the AImDNS class
    '''
    bogussvc = "not_likely_to_exist_service"

    class BogusService(object):
        '''Class to start and teardown a bogus service.
        '''
        dns_sd = "/bin/dns-sd"

        def __init__(self, name, svc_type, domain):
            '''
            Start a dns-sd process advertising a service with name, type with
            svc_type in the domain provided
            '''
            self.proc = subprocess.Popen([self.dns_sd, "-R", name,
                                          svc_type, domain, "9999",
                                          "foo=bar"],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT)

        def __del__(self):
            '''
            Kill process on object deletion -- remember to hold object in a
            variable or this will get called right after creation
            '''
            self.proc.terminate()
            # wait for dns-sd to die
            time.sleep(0.5)

    def test_find(self):
        '''Test AImDNS().find() returns True when service is found and False
           when not found
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        # negative test
        assert mdns.find(servicename=self.bogussvc) == False, \
               "Found bogus service: %s!" % self.bogussvc

        # start-up service for a positive test
        # pylint: disable-msg=W0212
        bogosvc = self.BogusService(self.bogussvc, common.REGTYPE, mdns.domain)
        # pylint: enable-msg=W0212
        assert mdns.find(self.bogussvc) == True, \
               "Failed to find unique service: %s!" % self.bogussvc
        del(bogosvc)

    def test_browse(self):
        '''Test that AImDNS().browse returns True upon finding a service
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        # start up a service to test browse
        # pylint: disable-msg=W0212
        bogosvc = self.BogusService(self.bogussvc, common.REGTYPE, mdns.domain)
        # pylint: enable-msg=W0212
        assert mdns.browse() == True, "Did not find any services!"
        del(bogosvc)

    def test_interfaces(self):
        '''Verify a unique service shows up for all interfaces listed
        (since dns-sd publishes on all iterfaces) when doing an
        AImDNS().browse()
        '''
        def _in_network(inter_ipv4, networks):
            '''Ensures that the interface's address is in networks
            '''
            # iterate over the network list
            for network in networks:
                # check if the interface's IPv4 address is in the network
                if aimdns.compare_ipv4(inter_ipv4, network):
                    return True
            return False

        # services dictionary looks like:
        #{'e1000g0': [
        #    {'domain': u'local', 'hosttarget': u'jumprope.local.',
        #     'comments': 'aiwebserver=10.10.44.5:46501',
        #     'servicename': u'install_test_ai_x86',
        #     'flags': True, 'port': 46501},
        #    {'domain': u'local', 'hosttarget': u'jumprope.local.',
        #     'comments': 'foo=bar', 'flags': True, 'port': 9999,
        #     'servicename': u'not_likely_to_exist_service'}
        #]}

        mdns = aimdns.AImDNS()
        mdns.timeout = 2

        # start up a service to test browse
        # pylint: disable-msg=W0212
        bogosvc = self.BogusService(self.bogussvc, common.REGTYPE, mdns.domain)
        # pylint: enable-msg=W0212

        assert mdns.browse() == True, "Did not find any services!"
        for interface in mdns.services:
            in_net = _in_network(mdns.interfaces[interface], mdns.networks)
            if (in_net and not mdns.exclude) or (not in_net and mdns.exclude):
                assert any([svc for svc in mdns.services[interface] if
                        svc['servicename'] == self.bogussvc]), \
                        "Unable to find unique service on interface: %s" % \
                        interface
        del(bogosvc)


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
    '''Class TestBrowseCallback - class to test _browse_callback functionatilty
    '''
    name = 'nonsense-service'
    regtype = '_OSInstall._tcp'
    domain = 'local'

    def test_browse_callback(self):
        '''test browse callback
        '''
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
        mdns.servicename = name
        mdns.timeout = 1
        sys.stderr = redirected
        # _ needs to get instantiated within the redirected output
        gettext.install("ai", "/usr/lib/locale")
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
            assert aimdns.compare_ipv4(ip1, ip2) == result, \
                    "compare_ipv4 failed %s test" % self.tests[i]['name']

            assert not aimdns.compare_ipv4('10.0.100.1', '10.0.15.5/48'), \
                    "compare_ipv4 failed for invalid CIDR mask"

            assert aimdns.compare_ipv4('10.0.15.10', '10.0.15.10/32'), \
                    "compare_ipv4 failed for & mask"

            assert aimdns.compare_ipv4('10.0.15.10', '10.0.15.10'), \
                    "compare_ipv4 failed for identical IP address"

    def test_in_network(self):
        '''test in_network returns valid results
        '''
        for i in range(len(self.tests)):
            ip1 = self.tests[i]['ip1']
            ip2 = self.tests[i]['ip2']
            result = self.tests[i]['result']
            assert aimdns.in_networks(ip1, [ip2]) == result, \
                    "in_network failed %s test" % self.tests[i]['name']

    def test_convert_cidr_mask(self):
        '''test _convert_cidr_mask returns something reasonable
        '''
        assert not aimdns._convert_cidr_mask(48), \
                "_convert_cidr_mask failed for edge case cidr > 32"
        assert aimdns._convert_cidr_mask(0) == '0.0.0.0', \
                "_convert_cidr_mask failed for 0 cidr mask"
        assert aimdns._convert_cidr_mask(24) == '255.255.255.0', \
                "_convert_cidr_mask failed for 24 cidr mask"
        assert aimdns._convert_cidr_mask(8) == '255.0.0.0', \
                "_convert_cidr_mask failed for 8 cidr mask"


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    unittest.main()

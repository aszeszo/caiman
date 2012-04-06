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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''Manual Testcase for aimdns

These tests are deemed manual due to the 10 second TTL DNS timeout
setup for registration of a service.  This is deemed too excessive
for automatic tests.

To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
'''
import gettext
import subprocess
import time
import threading
import unittest

import osol_install.auto_install.aimdns_mod as aimdns
import osol_install.auto_install.installadm_common as common

from nose.plugins.skip import SkipTest

from solaris_install import CalledProcessError, Popen


class Register(threading.Thread):
    '''Class to register a mDNS record in a thread
    '''

    def __init__(self, mdns_obj, servicename, port, comments):
        '''Call register on the provided mdns_obj
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


class RegisterAPI(unittest.TestCase):
    '''Class: RegisterAPI - used to test the AImDNS class
    '''
    bogussvc = "self-registration-test-svc"

    def test_register(self):
        '''Test the AImDNS().register() method
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        reg = Register(mdns, self.bogussvc, port=9999, comments="bar=foo")
        reg.start()
        time.sleep(2)

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
        # Default TTL (Time-To-Live) for DNS records is 120 seconds.
        # aimdns_mod.py resets the TTL to 10 seconds via an
        # DNSServiceUpdateRecord() call.  Therefore, pause for 10
        # seconds to allow the mdns daemon cache to clear.
        time.sleep(10)
        assert mdns2.find(servicename=self.bogussvc) == False, \
               "Still finding unique service: %s!" % self.bogussvc


class FindAPI(unittest.TestCase):
    '''Class: FindAPI - class to test the find method of the AImDNS class
    '''
    bogussvc = "bogus_service"
    bogus_find_svc = "bogus_find_service"

    class BogusService(object):
        '''Class to start and teardown a bogus service.
        '''
        def __init__(self, name, svc_type, domain):
            '''
            Use the AImDNS class to create a fake mdns service.
            '''
            mdns = aimdns.AImDNS()
            mdns.timeout = 2
            reg = Register(mdns, name, port=9999, comments="bar=foo")
            reg.start()

    def test_find(self):
        '''Test AImDNS().find() returns True when service is found and False
           when not found
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        # negative test
        assert mdns.find(servicename=self.bogus_find_svc) == False, \
               "Found bogus service: %s!" % self.bogussvc

        # start-up service for a positive test
        # pylint: disable-msg=W0212
        bogosvc = self.BogusService(self.bogus_find_svc, common.REGTYPE,
                                    mdns.domain)
        # pylint: enable-msg=W0212
        assert mdns.find(self.bogus_find_svc) == True, \
               "Failed to find unique service: %s!" % self.bogussvc
        del(bogosvc)

    def test_browse(self):
        '''Test that AImDNS().browse returns True upon finding a service
        '''
        mdns = aimdns.AImDNS()
        mdns.timeout = 2
        # start up a service to test browse
        # pylint: disable-msg=W0212
        bogosvc = self.BogusService(self.bogussvc, common.REGTYPE,
                                    mdns.domain)
        # pylint: enable-msg=W0212
        assert mdns.browse() == True, "Did not find any services!"
        del(bogosvc)
        # Default TTL (Time-To-Live) for DNS records is 120 seconds.
        # aimdns_mod.py resets the TTL to 10 seconds via an
        # DNSServiceUpdateRecord() call.  Therefore, pause for 10
        # seconds to allow the mdns daemon cache to clear.
        time.sleep(10)

    def test_interfaces(self):
        '''Verify a unique service shows up for all interfaces listed
        when doing an AImDNS().browse()
        '''
        def _in_network(inter_ipv4, networks):
            '''Ensures that the interface's address is in networks
            '''
            # iterate over the network list
            for network in networks:
                # check if the interface's IPv4 address is in the network
                if common.compare_ipv4(inter_ipv4, network):
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


def check_install_SMF():
    ''' Check if install/server SMF services is available.
        returning True if available and False if not.
    '''
    # Ensure system/install/server SMF service is available
    cmd = ["/usr/bin/svcs", "svc:/system/install/server"]
    try:
        Popen.check_call(cmd, stdout=Popen.DEVNULL, stderr=Popen.DEVNULL)
    except CalledProcessError:
        # This system does not have the service so skip the test
        raise SkipTest("svc:/system/install/server not installed")


# Ensure system/install/server SMF service is available
check_install_SMF()

if __name__ == '__main__':
    gettext.install("solaris_install_installadm", "/usr/share/locale")
    unittest.main()

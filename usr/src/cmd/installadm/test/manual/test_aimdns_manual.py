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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''Manual Testcase for aimdns

These tests are deemed manual due to the 120 second TTL DNS timeout.
This is deemed too excessive for automatic tests.

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
        # Default TTL (Time-To-Live) for DNS records is 120 seconds
        # To change the 120 second TTL, would require a re-architecture of the
        # aimdns' records. Instead of doing a default DNSServceRegister we
        # would need to create a DNS connection, create a record and then
        # register it with a shorter TTL value. The default value which can not
        # be modified is 120 seconds.
        time.sleep(120)
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
        # Default TTL (Time-To-Live) for DNS records is 120 seconds
        # To change the 120 second TTL, would require a re-architecture of the
        # aimdns' records. Instead of doing a default DNSServceRegister we
        # would need to create a DNS connection, create a record and then
        # register it with a shorter TTL value. The default value which can not
        # be modified is 120 seconds.
        time.sleep(120)

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
    gettext.install("ai", "/usr/lib/locale")
    unittest.main()

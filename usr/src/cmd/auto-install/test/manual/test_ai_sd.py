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
# test_ai_sd - test for AI Service Discovery Engine
#
# These tests are deemed better run as manual tests as they require
# the machine to be configured as an AI server, and as per TTL DNS
# defaults require 120 second timeouts which is too long for an automatic
# test to wait around.
#
""" test AI Service Discovery Engine
"""

import gettext
import subprocess
import time
import unittest

from nose.plugins.skip import SkipTest

from solaris_install import Popen
from solaris_install.auto_install import ai_sd


class TestAISD(unittest.TestCase):
    '''tests for ai_sd'''

    class BogusService(object):
        '''Class to start and teardown a bogus service.
        '''
        dns_sd = "/bin/dns-sd"

        def __init__(self, name, svc_type, domain, port, text):
            '''
            Start a dns-sd process advertising a service with name, type with
            svc_type in the domain provided
            '''
            self.proc = subprocess.Popen([self.dns_sd, "-R", name,
                                          svc_type, domain, port,
                                          text],
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

    TIMEOUT = 2
    SERVICE_NAME = 'bogus_service'
    DEFAULT_SERVICE = '_default'
    REGTYPE = '_OSInstall._tcp'
    DOMAIN = 'local'
    PORT = "5555"
    TEXT_REC = 'aiwebserver=' + SERVICE_NAME + ':' + PORT

    def setUp(self):
        # Before running any tests, ensure Multicast DNS SMF is enabled.
        cmd = ["/usr/bin/svcs", "-H", "-o", "STATE",
               "svc:/network/dns/multicast:default"]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        if p.stdout.strip() != "online":
            raise SkipTest("Unable to run FindAPI tests - enable SMF service "
                           "svc:/network/dns/multicast:default")
        self.bogosvc = None

    def tearDown(self):
        if self.bogosvc:
            del(self.bogosvc)

    def test_no_aiservice(self):
        '''test covers when there is not an AIService'''
        # Default TTL (Time-To-Live) for DNS records is 120 seconds
        # To change the 120 second TTL, would require a re-architecture of the
        # aimdns' records. Instead of doing a default DNSServceRegister we
        # would need to create a DNS connection, create a record and then
        # register it with a shorter TTL value. The default value which can not
        # be modified is 120 seconds.
        time.sleep(120)
        aisvc = ai_sd.AIService(self.SERVICE_NAME, self.TIMEOUT)
        assert aisvc.lookup() == -1, 'lookup succeeded'
        assert aisvc.found == False, 'found bogus service'

    def test_aiservice(self):
        '''test covers when there is an AIService'''
        self.bogosvc = self.BogusService(self.SERVICE_NAME,
                                    self.REGTYPE,
                                    self.DOMAIN,
                                    self.PORT,
                                    self.TEXT_REC)

        # uncomment out the following lines to see if the service
        # is actually running.
        # dns_sd = "/bin/dns-sd"
        # proc = subprocess.Popen([dns_sd, "-B", self.REGTYPE, self.DOMAIN],
        #                            stdout=None,
        #                            stderr=subprocess.STDOUT)
        # time.sleep(2)
        # proc.terminate()

        aisvc = ai_sd.AIService(self.SERVICE_NAME, self.TIMEOUT)
        assert aisvc.lookup() == 0, \
                'lookup did not succeed for service (%s)' % self.SERVICE_NAME
        assert aisvc.lookup() != -1, \
                'lookup did not succeed for service (%s)' % self.SERVICE_NAME
        assert aisvc.found == True, \
                'did not find service (%s)' % self.SERVICE_NAME

if __name__ == '__main__':
    gettext.install("solaris_install_autoinstall", "/usr/share/locale")
    unittest.main()

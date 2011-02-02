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
# test_ai_sd - test for AI Service Discovery Engine
#
""" test AI Service Discovery Engine
"""

import gettext
import subprocess
import time
import unittest

import ai_sd


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
        self.bogosvc = None

    def tearDown(self):
        if self.bogosvc:
            del(self.bogosvc)

    def test_no_aiservice(self):
        '''test covers when there is not an AIService'''
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

        aisvc = ai_sd.AIService(self.DEFAULT_SERVICE, self.TIMEOUT)
        assert aisvc.lookup() == 0, \
                'lookup did not succeed for default service'
        assert aisvc.found == True, \
                'did not find default service'
        assert aisvc.get_txt_rec() == self.TEXT_REC, \
                "found service's text record does not match"


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    unittest.main()

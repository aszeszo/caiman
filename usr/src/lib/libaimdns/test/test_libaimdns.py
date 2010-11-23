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
'''Testcase for libaimdns interfaces

To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.
For the libaimdns SCF tests the user must have privilege to modify the
configuration of a service (see smf_security(5) for details).
'''
import os
import subprocess
import unittest
from osol_install.netif import if_nameindex

from osol_install.libaimdns import getstring_property, getstrings_property, \
                                   getboolean_property, getinteger_property, \
                                   getifaddrs, aiMDNSError


class TestLibaimdnsSCF(unittest.TestCase):
    '''Class: TestLibaimdnsSCF - tests the libaimdns SCF interfaces
    '''
    svc = 'svc:/system/install/server:default'
    svccfg = '/usr/sbin/svccfg'
    bogus_svc = 'svc:/system/install/server2:default'
    bogus_prop = 'config/dummy'

    class SetSCFValue(object):
        '''Class SetSCFValue - sets the SCF property value via svccfg
        '''
        svc = 'svc:/system/install/server:default'
        svccfg = '/usr/sbin/svccfg'

        def __init__(self, props):
            self.cmdsname = '/tmp/svctest.cmds'

            cmds = open(self.cmdsname, 'w+')
            cmds.write('addpg test application\n')
            for prop in props:
                cmds.write('%s\n' % prop)
            cmds.close()
            proc = subprocess.Popen([self.svccfg, "-s", self.svc,
                                     "-f", self.cmdsname],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
            stderr = proc.communicate()[1]
            if stderr:
                print 'Error:', stderr

        def __del__(self):
            proc = subprocess.Popen([self.svccfg, "-s", self.svc,
                                    'delpg test'])
            stderr = proc.communicate()[1]
            if stderr:
                print 'Error:', stderr
            os.remove(self.cmdsname)

    def test_getstring(self):
        '''test libaimdns.getstring_property interface
        '''
        prop = 'test/astr'
        value = 'howdy'
        setprop = 'setprop %s = astring: "%s"' % (prop, value)
        newvalues = self.SetSCFValue([setprop])
        assert getstring_property(self.svc, prop) == value, \
                'string does not match failure'
        del(newvalues)

	try:
            assert getstring_property(self.bogus_svc, prop) == None, \
                   'string returned for bogus_svc'
	except aiMDNSError:
            pass

        try:
            assert getstring_property(self.svc, self.bogus_prop) == None, \
                    'string returned for bogus_prop'
        except aiMDNSError:
            pass

    def test_getstrings(self):
        '''test libaimdns.getstrings_property interface
        '''
        prop = 'test/strs'
        value = ['first', 'second']
        setprop = ['addpropvalue %s astring: "%s"' % (prop, value[0])]
        setprop.append('addpropvalue %s "%s"' % (prop, value[1]))
        newvalues = self.SetSCFValue(setprop)
        assert getstrings_property(self.svc, prop) == value, \
                'strings value does not match failure'
        del(newvalues)

	try:
            assert getstrings_property(self.bogus_svc, prop) == None, \
                   'strings returned for bogus_svc'
	except aiMDNSError:
            pass

        try:
            assert getstrings_property(self.svc, self.bogus_prop) == None, \
                    'strings returned for bogus_prop'
        except aiMDNSError:
            pass

    def test_getboolean(self):
        '''test libaimdns.getboolean_property interface
        '''
        prop = 'test/bool'
        value = True
        setprop = 'setprop %s = boolean: %s' % (prop, str(value).lower())
        newvalues = self.SetSCFValue([setprop])
        assert getboolean_property(self.svc, prop) == value, \
                'boolean property does not match'
        del(newvalues)

	try:
            rtn = getboolean_property(self.bogus_svc, prop) 
	except aiMDNSError, err:
            assert err == 'entity not found', \
                   'boolean returned for bogus_svc'

        try:
            rtn = getboolean_property(self.svc, self.bogus_prop)
        except aiMDNSError, err:
           assert err == 'entity not found', \
                   'boolean returned a bogus_prop'

    def test_getinteger(self):
        '''test libaimdns.getinteger_property interface
        '''
        prop = 'test/anint'
        value = 1
        setprop = 'setprop %s = integer: %d' % (prop, value)
        newvalues = self.SetSCFValue([setprop])
        assert getinteger_property(self.svc, prop) == value, \
                'integer property does not match'
        del(newvalues)

	try:
            assert getinteger_property(self.bogus_svc, prop), \
                   'integer returned for bogus_svc'
	except aiMDNSError:
            pass

        try:
            assert getinteger_property(self.svc, self.bogus_prop), \
                    'integer returned for bogus_prop'
        except aiMDNSError:
            pass



class TestLibaimdnsGetifaddrs(unittest.TestCase):
    '''Class: TestLibaimdnsGetifaddrs - tests the libaimdns getifaddrs
       interface
    '''
    # pylint: disable-msg=R0201
    def test_getifaddrs(self):
        '''test libaimdns.getifaddrs interface
        '''
        inter = if_nameindex()
        # note: getifaddrs() skips loopback and point-to-point,
        #       therefore, test only that the getifaddrs interfaces
        #       are in the if_nameindex interfaces
        ifaddrs = getifaddrs()
        for ifaddr in ifaddrs:
            assert ifaddr in inter.values(), \
                'Unable to find %s interface' % ifaddr
    # pylint: enable-msg=R0201


if __name__ == '__main__':
    unittest.main()

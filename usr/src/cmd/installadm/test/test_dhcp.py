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
# Copyright (c) 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
To run these tests, see the instructions in usr/src/tools/tests/README.
Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import os
import osol_install.auto_install.dhcp as dhcp
import shutil
import tempfile
import unittest
from nose.plugins.skip import SkipTest
from solaris_install import Popen


class DHCPServerTest(unittest.TestCase):
    '''Tests for interaction with ISC DHCP server.'''

    def setUp(self):
        '''Create test instance of dhcp SMF service'''

        # save the original svc name of dhcp SMF service instance
        self.dhcp_srv_orig = dhcp.DHCP_SERVER_IPV4_SVC
        self.dhcp_srv = "svc:/network/dhcp/server"
        # First check whether dhcp SMF service is available on test machine
        # using svcs svc:/network/dhcp/server
        cmd = [dhcp.SVCS, self.dhcp_srv]
        try:
            Popen.check_call(cmd)
        except:  # If svcs command fails from any reason skip this test
            raise SkipTest("DHCP SMF service not available")

        # name of our test instance
        self.instance_name = "ai-unittest"
        self.dhcp_srv_inst = self.dhcp_srv + ':' + self.instance_name
        self.dhcp_dir = tempfile.mkdtemp(dir="/tmp")

        # redefine DHCP_SERVER_IPV4_SVC to our test SMF service
        dhcp.DHCP_SERVER_IPV4_SVC = self.dhcp_srv_inst
        # construct list of svccfg commands
        cmds = list()
        # create new instance of dhcp service
        cmds.append([dhcp.SVCCFG, "-s", self.dhcp_srv,
            "add", self.instance_name])
        svccmd = [dhcp.SVCCFG, "-s", self.dhcp_srv_inst]
        # add config property group
        cmds.append(svccmd + ["addpg config application"])
        # set test config file
        cmds.append(svccmd + ["setprop config/config_file = astring: " +
            self.dhcp_dir + "/dhcpd4.conf"])
        # set lease file
        cmds.append(svccmd + ["setprop config/lease_file = astring: " +
            self.dhcp_dir + "/dhcpd4.leases"])
        # general/complete must be set-up
        cmds.append(svccmd + ["addpg general framework"])
        cmds.append(svccmd + ['setprop general/complete = astring: ""'])
        # disable service
        cmds.append([dhcp.SVCADM, "disable", self.dhcp_srv_inst])

        for cmd in cmds:
            Popen.check_call(cmd)

    def tearDown(self):
        '''Delete test instance of dhcp SMF service'''
        cmd = [dhcp.SVCCFG, "delete", self.dhcp_srv_inst]
        Popen.check_call(cmd)
        dhcp.DHCP_SERVER_IPV4_SVC = self.dhcp_srv_orig
        if os.path.exists(self.dhcp_dir):
            shutil.rmtree(self.dhcp_dir)

    def test_permissions(self):
        '''Test correct permissions of dhcpd4.conf'''

        dhcpsrv = dhcp.DHCPServer()
        dhcpsrv.add_arch_class('i386',
            [('00:00', 'bios', 'some-test-string')])
        # save original umask
        orig_umask = os.umask(0022)
        # set too restrictive and too open umask
        for mask in (0066, 0000):
            os.umask(mask)
            dhcpsrv.update_bootfile_for_arch('i386',
                [('00:07', 'uefi', 'some-other-test-string')])
            mode = os.stat(self.dhcp_dir + '/' + 'dhcpd4.conf').st_mode
            self.assertEqual(mode, 0100644)
        # return umask to the original value
        os.umask(orig_umask)

if __name__ == '__main__':
    unittest.main()

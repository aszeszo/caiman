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

import os
import osol_install.auto_install.create_service as create_service
import osol_install.auto_install.dhcp as dhcp
import osol_install.auto_install.grub as grub
import osol_install.auto_install.installadm_common as com
import shutil
import tempfile
import unittest


class ParseOptions(unittest.TestCase):
    '''Tests for parse_options.'''

    @classmethod
    def setUpClass(cls):
        '''Class-level set up
           We want to sub out the is_multihomed() function from
           installadm_common because it calls into the installadm-common.sh
           script which is part of the installadm pkg and that pkg may not
           be installed on the system running the unit tests.
        '''
        cls.com_ismultihomed = com.is_multihomed
        com.is_multihomed = lambda: False

    @classmethod
    def tearDownClass(cls):
        '''Class-level teardown'''
        com.is_multihomed = cls.com_ismultihomed

    def test_parse_one_arg(self):
        '''Ensure one args caught'''
        myargs = ["mysvc"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_invalid_servicename(self):
        '''Ensure invalid servicename caught'''

        myargs = ["-n", "new=svc"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_parse_alias_bad_options(self):
        '''Ensure invalid options combinations caught'''

        myargs = ["-t", "aliasof_name", "-s", "/tmp/myiso.iso"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-d", "/tmp/myimage"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-c", "5"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-t", "aliasof_name", "-i", "10.100.100.100"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_alias_has_name(self):
        '''Ensure if creating alias, name is provided'''

        myargs = ["-t", "myalias"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_no_default_arch(self):
        '''Ensure default arch can't be created as service'''

        myargs = ["-n", "default-i386"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)
        myargs = ["-n", "default-sparc"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

    def test_publisher_syntax(self):
        '''Ensure publisher string is of form 'publisher=uri' '''

        myargs = ["-p", "solarishttp://www.example.com:10000"]
        self.assertRaises(SystemExit, create_service.parse_options, myargs)

        myargs = ["-p", "solaris=http://www.example.com:10000"]
        options = create_service.parse_options(myargs)
        self.assertEquals(options.publisher[0], "solaris")
        self.assertEquals(options.publisher[1], "http://www.example.com:10000")

    def test_parse_no_errors(self):
        '''Ensure successful command parsing'''

        myargs = ["-n", "myservice", "-s", "/tmp/myiso.iso"]
        options = create_service.parse_options(myargs)
        self.assertEquals(options.svcname, "myservice")
        self.assertEquals(options.srcimage, "/tmp/myiso.iso")

        # Make sure passing no options is ok
        myargs = list()
        options = create_service.parse_options(myargs)
        self.assertEquals(options.srcimage,
                          "pkg:/install-image/solaris-auto-install")


class CreateTestService(unittest.TestCase):
    '''Tests for install service set up.'''

    def setUp(self):
        '''unit test set up'''
        self.svc_name = 'my-test-service'
        self.image_path = tempfile.mkdtemp(dir="/tmp")
        self.image_info = {'image_version': '3.0', 'grub_min_mem64': '0',
                           'service_name': 'solaris11u1-i386-05',
                           'grub_do_safe_default': 'true',
                           'grub_title': 'Oracle Solaris 11',
                           'image_size': '744619',
                           'no_install_grub_title': 'Oracle Solaris 11'}
        self.srv_address = '$serverIP:5555'
        self.menu_path = self.image_path
        self.bootargs = ''

    def tearDown(self):
        '''teardown'''
        if os.path.exists(self.image_path):
            shutil.rmtree(self.image_path)

    def test_menu_permissions(self):
        '''Ensure that menu.lst is created with correct permissions'''

        # save original umask
        orig_umask = os.umask(0022)
        # set too restrictive and too open umask
        for mask in (0066, 0000):
            os.umask(mask)
            grub.setup_grub(self.svc_name, self.image_path, self.image_info,
                self.srv_address, self.menu_path, self.bootargs)
            mode = os.stat(self.menu_path + '/' + 'menu.lst').st_mode
            self.assertEqual(mode, 0100644)
        # return umask to the original value
        os.umask(orig_umask)


class DHCPServerTest(unittest.TestCase):
    '''Tests for interaction with ISC DHCP server.'''

    def setUp(self):
        '''Create test instance of dhcp SMF service'''

        # save the original svc name of dhcp SMF service instance
        self.dhcp_srv_orig = dhcp.DHCP_SERVER_IPV4_SVC
        self.dhcp_srv = "svc:/network/dhcp/server"
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
        dhcpsrv.add_arch_class('i386', 'some-test-string')
        # save original umask
        orig_umask = os.umask(0022)
        # set too restrictive and too open umask
        for mask in (0066, 0000):
            os.umask(mask)
            dhcpsrv.update_bootfile_for_arch('i386', 'some-other-test-string')
            mode = os.stat(self.dhcp_dir + '/' + 'dhcpd4.conf').st_mode
            self.assertEqual(mode, 0100644)
        # return umask to the original value
        os.umask(orig_umask)

if __name__ == '__main__':
    unittest.main()

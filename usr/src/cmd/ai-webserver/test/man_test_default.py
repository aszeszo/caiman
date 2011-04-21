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

'''
In order to NOT create new services on the build server, tests in this module
must be run manually.

Remember that since the proto area is used for the PYTHONPATH, the gate
must be rebuilt for these tests to pick up any changes in the tested code.

'''

import os
import unittest

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.properties as properties
import osol_install.libaiscf as smf

from solaris_install import _


# Eventually bring names into convention.
# pylint: disable-msg=C0103
class TestDefault(unittest.TestCase):
    '''Tests for verifying management of default manifests.'''

    service_name = "UTest_Service"
    image_path = "/tmp/UTest_Service_Path"
    manifest_name = None
    smf_instance = None

    def test_default_set_get(self):
        '''Set up service rudiments so default handling can be tested'''

        try:
            self.smf_instance = smf.AISCF(FMRI="system/install/server")
        except KeyError:
            raise SystemExit(_("Error:\tThe system/install/server SMF "
                               "service is not running."))

        # If the service exists, exit.  We don't want to romp on it.
        if self.service_name in self.smf_instance.services.keys():
            raise SystemExit(_("Error: The service %s already exists!!!") %
                               self.service_name)

        service_data = {aismf.PROP_SERVICE_NAME: self.service_name,
                        aismf.PROP_IMAGE_PATH: self.image_path,
                        aismf.PROP_BOOT_FILE: "dummy_boot",
                        aismf.PROP_TXT_RECORD:
                            com.AIWEBSERVER + "hostname:45123",
                        aismf.PROP_STATUS: aismf.STATUS_OFF}

        aismf.create_pg(self.service_name, service_data)

        self.manifest_name = "temp_mfest_name_%d" % os.getpid()

        properties.set_default(self.service_name, self.manifest_name,
            properties.SKIP_MANIFEST_CHECK)
        self.assertEqual(self.manifest_name,
                         properties.get_default(self.service_name))

    def tearDown(self):
        '''Take down test environment'''
        if (self.service_name is not None and self.smf_instance is not None and
            aismf.is_pg(self.service_name)):
            service = smf.AIservice(self.smf_instance, self.service_name)
            # pylint: disable-msg=E1101
            service.instance.del_service(service.serviceName)


if __name__ == '__main__':
    unittest.main()

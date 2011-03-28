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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''test_init_smf
   Test program for initialize_smf
'''

import os
import os.path
import shutil
import tempfile
import unittest

from common_create_simple_doc import CreateSimpleDataObjectCache
from solaris_install.ict.initialize_smf import InitializeSMF
from solaris_install.engine.test.engine_test_utils import reset_engine


class TestInitializeSMF(unittest.TestCase):
    '''test the functionality for InitializeSMF Class'''

    def setUp(self):

        # Set up the Target directory
        self.test_target = tempfile.mkdtemp(dir="/tmp/",
                                            prefix="ict_test_")
        os.chmod(self.test_target, 0777)

        # Create a data object to hold the required data
        self.simple = CreateSimpleDataObjectCache(test_target=self.test_target)

        # Instantiate the checkpoint
        self.smf = InitializeSMF("IS")

        self.smf_filelist = ['lib/svc/seed/global.db',
                             'etc/svc/profile/generic_limited_net.xml',
                             'etc/svc/profile/ns_dns.xml',
                             'etc/svc/profile/inetd_generic.xml',
                             'etc/svc/profile/sc_profile.xml']

        self.sys_profile_dict = {'generic_limited_net.xml':
                                 os.path.join(self.test_target,
                                              'etc/svc/profile/generic.xml'),
                                 'ns_dns.xml': os.path.join(self.test_target,
                                           'etc/svc/profile/name_service.xml'),
                                 'inetd_generic.xml':
                                  os.path.join(self.test_target,
                                         'etc/svc/profile/inetd_services.xml'),
                                 'sc_profile.xml':
                                  os.path.join(self.test_target,
                                              'etc/svc/profile/site.xml')}

        for smf_file in self.smf_filelist:
            # create the directory if it doesn't exist
            if not os.path.exists(os.path.join(self.test_target,
                                               os.path.dirname(smf_file))):
                os.makedirs(os.path.join(self.test_target,
                                         os.path.dirname(smf_file)))

            # touch the file
            with open(os.path.join(self.test_target, smf_file), "w+") as fh:
                pass

        for key, value in self.sys_profile_dict.items():
            os.symlink(key, value)

    def tearDown(self):
        reset_engine()
        self.simple.doc = None

        if os.path.exists(self.test_target):
            shutil.rmtree(self.test_target)

    def test_initialize_smf(self):
        '''Test initializing smf'''

        # Call the execute command for the checkpoint
        self.smf.execute()

        self.assert_(os.path.isfile(os.path.join(self.test_target,
                                    'etc/svc/repository.db')))

        for key, value in self.sys_profile_dict.items():
            self.assert_(os.path.islink(value))

    def test_initialize_smf_dry(self):
        '''Test initializing smf dry run'''

        # Call the execute command for the checkpoint
        # with dry_run set to true.
        try:
            self.smf.execute(dry_run=True)
        except Exception as e:
            self.fail(str(e))

        # Check to see if the test dumpadm.conf file exists
        self.assertFalse(os.path.isfile(os.path.join(self.test_target,
                                        'etc/svc/repository.db')))

    def test_get_progress_estimate(self):
        '''Test get progress estimate return value'''

        # Check the return value for the progress estimate
        self.assertEquals(self.smf.get_progress_estimate(), 1)


if __name__ == '__main__':
    unittest.main()

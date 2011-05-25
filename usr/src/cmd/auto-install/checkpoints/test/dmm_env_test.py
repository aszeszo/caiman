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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
Test environment setup for running Derived Manifest Module scripts
'''

import os
import logging
import unittest

from solaris_install.auto_install.checkpoints.dmm import DerivedManifestModule
from solaris_install.engine.test import engine_test_utils


class DMMEnvTest(unittest.TestCase):
    '''
    Test environment setup for running Derived Manifest Module scripts
    '''

    SCRIPT = "/tmp/dmm_env_test.ksh"
    LOGFILE = "/tmp/dmm_env_test.out"

    # Same as the default manifest defined in the DMM checkpoint.
    MANIFEST = "/tmp/manifest.xml"

    def create_script_file(self):
        '''
        "Create a script that dumps all environment variables.
        '''
        with open(self.SCRIPT, "w") as script:
            script.write("#!/bin/ksh93\n")
            script.write("\n")
            script.write("trap handler ERR\n")
            script.write("\n")
            script.write("function handler\n")
            script.write("{\n")
            script.write("	exit $?\n")
            script.write("}\n")
            script.write("\n")
            script.write("print \"SI_MODEL: $SI_MODEL\"\n")
            script.write("print \"SI_PLATFORM: $SI_PLATFORM\"\n")
            script.write("print \"SI_MEMSIZE: $SI_MEMSIZE\"\n")
            script.write("print \"SI_INSTALL_SERVICE: $SI_INSTALL_SERVICE\"\n")
            script.write("print \"SI_MANIFEST_SCRIPT: $SI_MANIFEST_SCRIPT\"\n")
            script.write("print \"SI_NATISA: $SI_NATISA\"\n")
            script.write("print \"SI_NETWORK: $SI_NETWORK\"\n")
            script.write("print \"SI_ARCH: $SI_ARCH\"\n")
            script.write("print \"SI_CPU: $SI_CPU\"\n")
            script.write("print \"SI_HOSTNAME: $SI_HOSTNAME\"\n")
            script.write("print \"SI_KARCH: $SI_KARCH\"\n")
            script.write("print \"SI_HOSTADDRESS: $SI_HOSTADDRESS\"\n")
            script.write("\n")
            script.write("for ((count = 1; count <= $SI_NUMDISKS; count++)) ; "
                         "do\n")
            script.write("	eval "
                         "curr_disk_name=\"$\"SI_DISKNAME_${count}\n")
            script.write("	eval "
                         "curr_disk_size=\"$\"SI_DISKSIZE_${count}\n")
            script.write("	print "
                         "\"SI_DISKNAME_$count: $curr_disk_name\"\n")
            script.write("	print "
                         "\"SI_DISKSIZE_$count: $curr_disk_size\"\n")
            script.write("done\n")
            script.write("\n")
            script.write("print\n")
            script.write("print \"AIM_MANIFEST: $AIM_MANIFEST\"\n")
            script.write("print \"AIM_LOGFILE: $AIM_LOGFILE\"\n")
            script.write("print \"Done!\"\n")
        os.chmod(self.SCRIPT, 0555)

    #pylint: disable-msg=C0103
    def setUp(self):
        '''
        Set up enough of an environment to run in, and create script.
        '''

        if os.path.exists(self.LOGFILE):
            os.unlink(self.LOGFILE)

        self.engine = engine_test_utils.get_new_engine_instance()
        self.logger = logging.getLogger()
        self.logger.addHandler(logging.StreamHandler())
        self.file_handler = logging.FileHandler(self.LOGFILE)
        self.logger.addHandler(self.file_handler)

        self.create_script_file()

        if os.path.exists(self.MANIFEST):
            os.unlink(self.MANIFEST)

    def tearDown(self):
        '''
        Tear down test environment
        '''

        # Cleans up engine and logging
        engine_test_utils.reset_engine()

        os.unlink(self.SCRIPT)
        os.unlink(self.LOGFILE)

    def test_env_setup(self):
        '''
        Run the associated dmm_env_test script, then verify.

        Checks that the script completed successfully and that the
        resulting manifest validation fails (because the script does not really
        create a manifest).

        One must visually inspect the output at the logfile
        as each system will be different.
        '''

        try:
            dmm_cp = DerivedManifestModule("Derived Manifest Module",
                                           self.SCRIPT)
        except StandardError, err:
            self.fail("Error during instantiation: " + str(err))

        try:
            dmm_cp.execute()
        except StandardError, err:

            # Control gets here due to the expected validation error.
            # Check a few things in the output.

            self.file_handler.close()
            test_ok = False
            with open(self.LOGFILE) as logfile:
                contents = logfile.read()
                if (("Derived Manifest Module: script completed successfull" in
                    contents) and
                   ("Derived Manifest Module: Final manifest "
                    "failed XML validation" in contents)):
                    test_ok = True
            if not test_ok:
                self.fail("Unexpected error during execution.  See %s" %
                          self.LOGFILE)

if __name__ == '__main__':
    unittest.main()

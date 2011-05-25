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
Test Derived Manifest Module logging of aimanifest commands.
'''

import os
import logging
import unittest

from solaris_install.auto_install.checkpoints.dmm import DerivedManifestModule
from solaris_install.engine.test import engine_test_utils


class DMMLogTest(unittest.TestCase):
    '''
    Test environment setup for running Derived Manifest Module scripts
    '''

    SCRIPT = "/tmp/dmm_log_test.ksh"
    LOGFILE = "/tmp/dmm_log_test.out"

    # Same as the default manifest defined in the DMM checkpoint.
    ROOT = os.environ.get("ROOT", "/")
    MANIFEST = ROOT + "/usr/share/auto_install/default.xml"

    def create_script_file(self):
        '''
        "Create a script that runs a few aimanifest commands.
        '''
        with open(self.SCRIPT, "w") as script:
            script.write("#!/bin/ksh93\n")
            script.write("\n")

            # A good aimanifest command.
            script.write("$ROOT/usr/bin/aimanifest get "
                         "/auto_install/ai_instance@name\n")

            # An errant aimanifest command.
            script.write("$ROOT/usr/bin/aimanifest get "
                         "/auto_install/ai_instance@BOGUS\n")
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

    def tearDown(self):
        '''
        Tear down test environment
        '''

        # Cleans up engine and logging
        engine_test_utils.reset_engine()

        os.unlink(self.SCRIPT)
        os.unlink(self.LOGFILE)

    @staticmethod
    def check_output(lines, index, expected):
        '''
        Compare a line of logfile output with an expected result.
        '''
        if expected not in lines[index]:
            print "Expected:%s\nGot:     %s\n" % (expected, lines[index])
            return False
        return True

    def test_log_setup(self):
        '''
        Run the associated dmm_log_test script, then verify.

        Checks that the script completed successfully and that the
        resulting manifest validation fails (because the script does not really
        create a manifest).

        One must visually inspect the output at the logfile
        as each system will be different.
        '''

        try:
            dmm_cp = DerivedManifestModule("Derived Manifest Module",
                                           self.SCRIPT, self.MANIFEST)
        except StandardError, err:
            self.fail("Error during DMM instantiation: " + str(err))

        try:
            dmm_cp.execute()
        except StandardError, err:
            self.fail("Error during DMM execution: " + str(err))

        self.file_handler.close()
        logfile = open(self.LOGFILE)

        # Get logfile lines which have "aimanifest" in them.
        aimanifest_lines = [line for line in logfile.readlines() if
                            "aimanifest" in line]
        test_ok = True
        if not (self.check_output(aimanifest_lines, 0,
                "Derived Manifest Module: aimanifest "
                "logfile output follows:")):
            test_ok = False
        elif not (self.check_output(aimanifest_lines, 1,
                  ": aimanifest: INFO: command:get, "
                  "path:/auto_install/ai_instance@name")):
            test_ok = False
        elif not (self.check_output(aimanifest_lines, 2,
                  ": aimanifest: INFO: successful: returns value:default, "
                  "path:/auto_install[1]/ai_instance[1]@name")):
            test_ok = False
        elif not (self.check_output(aimanifest_lines, 3,
                  ": aimanifest: INFO: command:get, "
                  "path:/auto_install/ai_instance@BOGUS")):
            test_ok = False
        elif not (self.check_output(aimanifest_lines, 4,
                  ": aimanifest: ERROR: Error: Path matches no attributes")):
            test_ok = False

        if not test_ok:
            self.fail("Unexpected error during execution.  See %s" %
                      self.LOGFILE)

if __name__ == '__main__':
    unittest.main()

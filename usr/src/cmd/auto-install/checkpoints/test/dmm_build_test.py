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
Build a manifest from a script run inside the Derived Manifest Module.
'''

import logging
import os
import tempfile
import unittest

from lxml import etree

from solaris_install.auto_install.checkpoints.dmm import DerivedManifestModule
from solaris_install.engine.test import engine_test_utils


class DMMBuildTest(unittest.TestCase):
    '''
    Build a manifest from a script run inside the Derived Manifest Module.
    '''

    # This environment variable defines the start of the gate's proto area.
    ROOT = os.environ.get("ROOT", "/")

    LOGFILE = "/var/run/dmm_buildtest.out"

    BASE_MANIFEST = "/usr/share/auto_install/default.xml"

    # Script run in the DMM
    SCRIPT = "/tmp/dmm_buildtest_script"

    # Names of the XML files which hold one section apiece.
    SC_EMB_MAN_XML = "/tmp/test_sc_embedded_manifest.xml"
    SOFTWARE_XML = "/tmp/test_software.xml"
    ADD_DRIVER_XML = "/tmp/test_add_drivers.xml"

    # Paths to roots of each of the three sections.
    SC_EMB_SUBTREE = "/auto_install/ai_instance/sc_embedded_manifests"
    SOFTWARE_SUBTREE = "/auto_install/ai_instance/software"
    ADD_DRIVER_SUBTREE = "/auto_install/ai_instance/add_drivers"

    def prune(self, subtree):
        '''
        Prune the part of the main tree given by the subtree argument.
        '''
        for tag in self.tree.xpath(subtree):
            tag.getparent().remove(tag)

    @staticmethod
    def strip_blank_lines(filename):
        '''
        Get rid of all lines in a file, which have only white space in them.
        '''
        outfile_fd, temp_file_name = tempfile.mkstemp(text=True)
        outfile = os.fdopen(outfile_fd, 'w')
        with open(filename, 'r') as infile:
            for line in infile:
                if not line.strip():
                    continue
                outfile.write(line)
        outfile.close()
        os.rename(temp_file_name, filename)

    #pylint: disable-msg=C0103
    def setUp(self):
        '''
        Set up enough of an environment to run in.  Set up files.
        '''

        if os.path.exists(self.LOGFILE):
            os.unlink(self.LOGFILE)

        self.engine = engine_test_utils.get_new_engine_instance()
        self.logger = logging.getLogger()
        self.logger.addHandler(logging.StreamHandler())
        self.file_handler = logging.FileHandler(self.LOGFILE)
        self.logger.addHandler(self.file_handler)

        # Assume the manifest used has separate sibling sections for
        # add_drivers, software and sc_embedded_manifest, and no others.
        # Create three files, each with one of the sections.

        # Read in base manifest, and write it out, stripping whitespace lines.
        self.tree = etree.parse(self.BASE_MANIFEST)

        # Generate the three files with subsections.
        self.prune(self.ADD_DRIVER_SUBTREE)
        self.prune(self.SOFTWARE_SUBTREE)
        self.tree.write(self.SC_EMB_MAN_XML, pretty_print=True)

        self.tree = etree.parse(self.BASE_MANIFEST)
        self.prune(self.ADD_DRIVER_SUBTREE)
        self.prune(self.SC_EMB_SUBTREE)
        self.tree.write(self.SOFTWARE_XML, pretty_print=True)

        self.tree = etree.parse(self.BASE_MANIFEST)
        self.prune(self.SC_EMB_SUBTREE)
        self.prune(self.SOFTWARE_SUBTREE)
        self.tree.write(self.ADD_DRIVER_XML, pretty_print=True)

        # Create a script to run inside the DMM.
        # Note that when the script runs, the first load will overwrite any
        # existing manifest.
        with open(self.SCRIPT, "w") as script:
            script.write("#!/bin/ksh93\n")
            script.write("\n")
            script.write("${ROOT}/usr/bin/aimanifest load %s\n" %
                         self.SOFTWARE_XML)
            script.write("${ROOT}/usr/bin/aimanifest load -i %s\n" %
                         self.ADD_DRIVER_XML)
            script.write("${ROOT}/usr/bin/aimanifest load -i %s\n" %
                         self.SC_EMB_MAN_XML)
            script.write("${ROOT}/usr/bin/aimanifest validate\n")
            script.write("print \"Validated manifest is "
                         "at $AIM_MANIFEST !!!\"\n")
        os.chmod(self.SCRIPT, 0555)

    def tearDown(self):
        '''
        Tear down test environment
        '''

        # Cleans up engine and logging
        engine_test_utils.reset_engine()

    def test_env_setup(self):
        '''
        Run the script, then verify.
        '''

        try:
            dmm_cp = DerivedManifestModule("Derived Manifest Module",
                                           self.SCRIPT)
        except StandardError as err:
            self.fail("Error during instantiation: " + str(err))

        try:
            dmm_cp.execute()
        except StandardError as err:
            self.fail("Error during execution/validation: " + str(err))

        self.file_handler.close()
        with open(self.LOGFILE) as logfile:
            contents = logfile.read()
            if (("Derived Manifest Module: script completed successfull" not in
                contents) or
               ("Derived Manifest Module: Final manifest "
                "failed XML validation" in contents)):
                self.fail("Unexpected logfile output")

if __name__ == '__main__':
    unittest.main()

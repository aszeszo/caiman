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

import array
import fcntl
import solaris_install.ict as ICT
import os
import shutil

from solaris_install.data_object.data_dict import DataObjectDict


class GenerateSCProfile(ICT.ICTBaseClass):
    '''ICT checkpoint assembles a system configuration profile'''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the checkpoint.
        '''
        super(GenerateSCProfile, self).__init__(name)

        # Set the default system configuration template used to assemble
        # system configuration profile
        self.sc_template = ICT.SC_TEMPLATE

        # Set the default system configuration profile target
        self.target_sc_profile = ICT.SC_PROFILE

        # Set the keyboard parameters used to get the keyboard layout
        self.kbd_device = ICT.KBD_DEV
        self.kbd_layout_file = ICT.KBD_LAYOUT_FILE
        self.keyboard_layout = ''

    def _get_keyboard_layout(self):
        '''Gets the keyboard layout for the system'''

        # Obtain ioctl codes taken from /usr/include/sys/kbio.h
        kioc = ord('k') << 8
        kioclayout = kioc | 20

        with open(self.kbd_device, "r") as fhndl:
            kbd_array = array.array('i', [0])
            # Get the requested keyboard layout
            fcntl.ioctl(fhndl, kioclayout, kbd_array, 1)
            # Convert the output to a list
            kbd_layout = kbd_array.tolist()[0]

        # Set the keyboard_layout parameter to the requested layout
        kbd_layout_name = ''
        with open(self.kbd_layout_file, "r") as fhndl:
            # Read the file until keyboard layout number matches
            # what has been requested.
            for line in fhndl:
                if line.startswith('#') or '=' not in line:
                    continue
                (kbd_layout_name, num) = line.split('=')
                if int(num) == kbd_layout:
                    keyboard_layout = kbd_layout_name
                    break

        if keyboard_layout == '':
            self.logger.debug('Keyboard layout has not been identified')
            self.logger.debug('It will be configured to', ICT.KBD_DEFAULT)
            keyboard_layout = ICT.KBD_DEFAULT
        else:
            self.logger.debug('Detected [%s] keyboard layout '
                              % keyboard_layout)
        return keyboard_layout

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Take template SMF profile, set value of keymap/layout SMF property
            to the requested value. If no value is requested, the default is
            configured as 'US-English' in the template. Store the SMF profile
            into the profile directory, /etc/svc/profile.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''

        # The optional configuration source and destination
        sc_profile_src = None
        sc_profile_dst = None

        self.logger.debug('ICT current task: generating the system '
                          'configuration profile')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Perform a check to see if a configuration source or destination
        # has been provided in the DOC
        # Get the checkpoint info from the DOC
        gen_sc_dict = self.doc.persistent.get_descendants(name=self.name,
                                                          class_type=DataObjectDict)

        # Check that there is not more than one entry for sc configuration
        if gen_sc_dict:
            if len(gen_sc_dict) > 1:
                raise ValueError("Only one value for a system configuration "
                                 "profile node can be specified with name ",
                                 self.name)

            # If there is a configuration entry, replace the default target
            # profile or source with the one provided in the DOC
            for sc_dict in gen_sc_dict:
                if len(sc_dict.data_dict) > 1:
                    raise ValueError("Only one source and destination may "
                                     "be specified")

                for source, dest in sc_dict.data_dict.items():
                    if self.sc_template != source:
                        self.sc_template = source
                    if self.target_sc_profile != dest:
                        self.target_sc_profile = dest

        sc_profile_src = os.path.join(self.target_dir,
                                      self.sc_template)
        sc_profile_dst = os.path.join(self.target_dir,
                                      self.target_sc_profile)

        # Get the keyboard layout for the system
        self.keyboard_layout = self._get_keyboard_layout()

        if not dry_run:
            # copy the source data base to the destination data base
            if not os.path.exists(os.path.dirname(sc_profile_dst)):
                os.makedirs(os.path.dirname(sc_profile_dst))

            if self.keyboard_layout == ICT.KBD_DEFAULT:
                shutil.copy2(sc_profile_src, sc_profile_dst)
            else:
                with open(sc_profile_dst, "w+")as dst_hndl:
                    with open(sc_profile_src, "r+") as fhndl:
                        for line in fhndl:
                            if ICT.KBD_DEFAULT in line and \
                               self.keyboard_layout != ICT.KBD_DEFAULT:
                                line = line.replace(ICT.KBD_DEFAULT,
                                                    self.keyboard_layout)
                            dst_hndl.write(line)

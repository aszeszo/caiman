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

import os
import shutil
import sys

import solaris_install.ict as ICT

from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import CPIOSpec
from solaris_install.transfer.info import Software


class TransferFiles(ICT.ICTBaseClass):
    '''
       The TransferFiles checkpoint transfers files that are related to
       an installation that the application wants to preserve
       Files to be transferred are stored in a DataObjectDict in the
       volatile section of the Data Object Cache. Each element of the
       dictionary is a source, destination pair.

       Where source and destination are either two ordinary files or two
       directories.

       The checkpoint performs the following actions when the execute method
       is called:

       - For ordinary files, copy the specified source file to the specified
         destination.
       - For directories, copy all files contained in the source directory to
         to the specified destination directory.
    '''
    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
        '''
        super(TransferFiles, self).__init__(name)

    def copy_file(self, source, dest):
        '''
            Class method to physically copy a file from source to dest
            only if the file exists.

            Parameters:
            - source : Source file to be copied
            - dest : destination directory to copy to

            Returns:
            - Nothing
        '''
        self.logger.debug("Executing: Copy file %s to %s", source, dest)
        # Copy the file, if it exists.
        if os.access(source, os.F_OK):
            shutil.copy2(source, dest)
        else:
            self.logger.debug('%s not found -- skipping', source)

    def copy_dir(self, source, dest):
        '''
            Class method to copy a source directory to a destination
            only if the source directory exists.  This method uses
            shutil.copytree() to copy the directory, so the desitnation
            must not already exist.

            Paramters:
            - source : Source directory to be copied
            - dest : destination directory to copy to

            Returns:
            - Nothing
        '''
        self.logger.debug("Executing: Copy dir %s to %s", source, dest)
        # Copy the directory, if it exists.
        if os.path.isdir(source):
            shutil.copytree(source, dest)
        else:
            self.logger.debug('%s not found -- skipping', source)

    def execute(self, dry_run=False):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            Parameters:
            - the dry_run keyword paramater. The default value is False.
              If set to True, the log message describes the checkpoint tasks.

            Returns:
            - Nothing
              On failure, errors raised are managed by the engine.
        '''

        # Initialize to None
        tf_dict = None

        self.logger.debug('ICT current task: Transfer Files')

        # parse_doc populates variables necessary to execute the checkpoint
        self.parse_doc()

        # Get the list of any additional files that need to be copied.
        tf_dict = self.doc.volatile.get_first_child(name=self.name)
        if tf_dict is None:
            # No files have been specified
            self.logger.debug('No files specified for transfer')
            return

        for source, dest in tf_dict.data_dict.items():
            dest = os.path.join(self.target_dir, dest.lstrip("/"))
            if not dry_run:

                # Check for source dir, if so copy entire contents
                if os.path.isdir(source):
                    self.copy_dir(source, dest)
                else:
                    # Create the destination if it does not exist.
                    if not os.access(os.path.dirname(dest), os.F_OK):
                        os.makedirs(os.path.dirname(dest))
                    self.copy_file(source, dest)

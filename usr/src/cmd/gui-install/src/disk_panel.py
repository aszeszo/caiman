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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Disk partitioning panel abstract base class for GUI Install app
'''

import abc


class DiskPanel(object):
    ''' Abstract base class for disk partitioning panels.
        Widgets that perform custom disk partitioning are required
        to inherit from this object and implement the methods
        defined.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, builder):
        ''' Initializer method. Called from the constructor.

            Params:
            - builder, a GtkBuilder object used to retrieve widgets
              from the Glade XML files

            Returns: nothing
        '''
        super(DiskPanel, self).__init__()

    @abc.abstractproperty
    def toplevel(self):
        ''' Instance property to return the toplevel widget of the
            DiskPanel subclass object
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def display(self, disk, target_controller):
        ''' Show the custom disk partitioning panel for the given Disk.

            Params:
            - disk, the Disk object that is being displayed/modified
            - target_controller, the TargetController object used to
              refetch the disk's previous layout, if Reset is pressed.

            Returns: nothing
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def finalize(self):
        ''' Tidies up the currently selected disk, so that it is
            ready for validation.

            Returns: nothing
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def validate(self):
        ''' Validate the user selections before proceeding.

            Perform a series of validations on the selected
            disk and the selected partitions, if appropriate.

            If the Disk and/or Partitions are not suitable for the install,
            then display an error dialog and raise an exception.

            Raises: NotOkToProceedError
        '''
        raise NotImplementedError

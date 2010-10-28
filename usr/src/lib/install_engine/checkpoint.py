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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
AbstractCheckpoint.  This class should be parent-class of all checkpoints
that want to be run by the engine
'''

import abc
import threading
import logging
from solaris_install.logger import INSTALL_LOGGER_NAME

class AbstractCheckpoint(object):
    ''' AbstractCheckpoint class to be parent class of all checkpoints '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, name):
        ''' Instantiates logger instance for the checkpoint.  The logger
            instance is a child of the instance instantiated by the install
            engine.

        Input:
            name: name of the checkpoint
        Output:
            None
        Raise:
            None
        '''
        self._cancel_requested = threading.Event()
        self.name = name
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME + "." + name)

    @abc.abstractmethod
    def get_progress_estimate(self):
        ''' This function is required to be implemented by all subclasses.
            The function should return the number of seconds it takes to
            execute the checkpoint as measured by the wall-clock, on
            a standardized machine.  If a checkpoint takes less than
            1 second to complete, it should return 1 second as its
            progress estimate.  The engine will always round up to the
            next integer if a decimal is provided as the weight.

        Input:
            None
        Output:
            The number of seconds it takes to execute the checkpoint.
        Raise:
            None
        '''

        raise NotImplementedError

    @abc.abstractmethod
    def execute(self, dry_run=False):
        ''' This function is required to be implemented by all subclasses

        Input:
            dry_run(optional): The application has requested to do dry run.
                               It's up to the checkpoint implementation to
                               implement the required dry_run functionality.
        Output:
            None

        Raise:
            Dependent on the checkpoint.  All raised exceptions will be
            passed back to the application.
        '''
        raise NotImplementedError

    def cancel(self):
        '''The default implementation is to set the _cancel_requested
           threading Event variable to true.  Checkpoints that uses the
           default implementation of the cancel() function should check
           the value of the _cancel_requested variable periodically, and
           end execution as appropriate.

        Input:
            None
        Output:
            None
        Raise:
            None
        '''
        self._cancel_requested.set()

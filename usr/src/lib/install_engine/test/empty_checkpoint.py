#!/usr/bin/python
#
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

''' Checkpoint to used for all the test cases '''

from solaris_install.engine.checkpoint import AbstractCheckpoint
import time

class EmptyCheckpoint(AbstractCheckpoint):
    
    ''' Checkpoint used for most test cases '''
    def __init__(self, cp_name, wait_for_cancel=False):
        ''' Class initializer method '''
        AbstractCheckpoint.__init__(self, cp_name)
        self.wait_for_cancel = wait_for_cancel
    
    def get_progress_estimate(self):
        ''' required to be implemented by AbstractCheckpoint, just return
            a value.  This value is not used by any test cases.
        '''
        return 0
    
    def execute(self, dry_run=False):
        ''' required to be implemented execute method '''
        if not dry_run:
            self.logger.info("Executing EmptyCheckpoint '%s' (dry_run=%s)" % \
                             (self.name, dry_run))

        if self.wait_for_cancel:
            # check the cancel variable, if it is set, then, exit.  Otherwise,
            # wait for that variable to be set 
            while True:
                if self._cancel_requested.is_set():
                    break
                else:
                    time.sleep(2)

class FailureEmptyCheckpoint(AbstractCheckpoint):

    ''' A checkpoint that will throw exception in execute '''
    
    def __init__(self, cp_name):
        ''' Class initializer method '''
        AbstractCheckpoint.__init__(self, cp_name)
    
    def get_progress_estimate(self):
        ''' required to be implemented by AbstractCheckpoint, just return
            a value.  This value is not used by any test cases.
        '''
        return 0
    
    def execute(self, dry_run=False):
        ''' Throw an exception '''
        raise RuntimeError("Exception from FailureEmptyCheckpoint.")

class InitFailureEmptyCheckpoint(EmptyCheckpoint):

    ''' A checkpoint that will throw exception in init '''
    
    def __init__(self, cp_name):
        ''' Class initializer method '''
        AbstractCheckpoint.__init__(self, cp_name)

        raise RuntimeError("Exception from InitFailureEmptyCheckpoint.")
    
class EmptyCheckpointWithArgs(EmptyCheckpoint):
    
    ''' A checkpoint that requires 1 argument to instantiate '''

    def __init__(self, cp_name, required_arg1):
        ''' Class initializer method '''
        EmptyCheckpoint.__init__(self, cp_name)
    
class EmptyCheckpointWithMultipleArgs(EmptyCheckpoint):

    ''' A checkpoint that requires 2 arguments to instantiate '''
    
    def __init__(self, cp_name, required_arg1, required_arg2):
        ''' Class initializer method '''
        EmptyCheckpoint.__init__(self, cp_name)

class EmptyCheckpointWithKWArgs(EmptyCheckpoint):

    ''' A checkpoint that accepts 1 keyword argument to instantiate '''
    
    def __init__(self, cp_name, kw1=None):
        ''' Class initializer method '''
        EmptyCheckpoint.__init__(self, cp_name)

class EmptyCheckpointWithMultipleKWArgs(EmptyCheckpoint):

    ''' A checkpoint that accepts 2 keyword argument to instantiate '''
    
    def __init__(self, cp_name, kw1=None, kw2=None):
        ''' Class initializer method '''
        EmptyCheckpoint.__init__(self, cp_name)

class EmptyCheckpointWithArgsAndKW(EmptyCheckpoint):

    ''' A checkpoint that requires 2 arguments and accepts 2 keyword arguments
        in it's initializer method 
    '''
    
    def __init__(self, cp_name, required_arg1, required_arg2,
                 kw1=None, kw2=None):
        ''' Class initializer method '''
        EmptyCheckpoint.__init__(self, cp_name)

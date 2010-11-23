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
# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
#
''' AI SCF Library and Object Types

This module implements an SMF to Python bridge primarily for AutoInstall
components

Example usages:
---------------------
To load the module, one runs
import libaiscf

Then to create an SMF instance object, one can run
(for svc:/system/install/server:default)
instance=libaiscf.AISCF()
(for svc:/system/install/server:someThingElse)
instance=libaiscf.AISCF(instance="someThingElse")

To view an instance's state (online, offline, maintenance, etc.) one can query
the state property. For example:
> > > libaiscf.AISCF().state
'online'

One can change the state too. Supported states are:
CLEAR, DEGRADE, DISABLE, ENABLE, MAINTENANCE, RESTART, RESTORE, REFRESH
For example:
> > > libaiscf.AISCF().state="DISABLE"
[wait a bit (~5 sec), or it'll still be transitioning]
> > > libaiscf.AISCF().state
'offline'

Further, to create an AI service object, one runs:
(For clarification, this is just an SMF property group representation)

service=libaiscf.AIservice(instance,"serviceName")

To see a property key under the service, one can do:
service['boot-dir'] (which returns the string value or a KeyError as a
                     dictionary would if the key doesn't exist)
To set or change a property under the service, one can do:
service['boot-dir']="/var/ai/service1_image"

All actions query SMF and no data is cached in case something changes under
the consumer. All actions are handed to SMF when executed.
'''

import _libaiscf

class AISCF(_libaiscf._AISCF):
    '''
    Class representing an AI SMF instance
    '''
    @property
    def services(self):
        '''
        Return a dictionary associating service names and AIservice objects
        associated with an SMF instance
        '''
        # Strip the AI prefix off the returned property group names and make a
        # dictionary mapping service name to AIservice objects

        # store services as they may change out from under us if we call this
        # multiple times
        services = [svc.replace("AI", "", 1) for svc in
            super(AISCF, self).services()]

        # loop catching KeyError (as it means the service went away)
        ret = {}
        for svc in services:
            try:
                val = AIservice(self, svc)
            # AIservice() will throw a KeyError if the service does not exist
            except KeyError:
                continue
            ret.update({svc: val})
        return ret

    def new_service(self, service_name):
        '''
        Create an AI service associated with the SMF instance
        '''
        return (AIservice(super(AISCF, self).new_service(self, service_name)))


class AIservice(_libaiscf._AIservice):
    '''
    Class representing an AI SMF service
    '''
    def values(self):
        '''
        Return the property values of an AI service
        '''
        return((self.as_dict()).values())
    def keys(self):
        '''
        Return the properties of an AI service
        '''
        return((self.as_dict()).keys())

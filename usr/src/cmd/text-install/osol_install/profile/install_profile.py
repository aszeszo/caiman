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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Represent all details of an installation in a single Python object,
including the disk target, netwrok configuration, system details (such as
timezone and locale), users, and zpool / zfs datasets.
'''


from solaris_install.data_object import DataObject


INSTALL_PROF_LABEL = "install_profile"


class InstallProfile(DataObject):
    '''
    Represents an entire installation profile
    '''
    
    LABEL = INSTALL_PROF_LABEL

    # pylint: disable-msg=E1003
    def __init__(self, disk=None, zpool=None):
        super(DataObject, self).__init__(InstallProfile.LABEL)
        self.disk = disk
        self.zpool = zpool
        self.install_succeeded = False
    
    def __str__(self):
        result = ["Install Profile:"]
        result.append("Install Completed - %s" % self.install_succeeded)
        result.append(str(self.disk))
        result.append(str(self.zpool))
        return "\n".join(result)
    
    ## InstallProfile not intended for long term use as a DataObject
    ## It's expected that this will be replaced with formal DataObject
    ## structures as the Text Installer transitions to use the InstallEngine
    ## and DOC more completely.
    def to_xml(self):
        return None
    
    @classmethod
    def from_xml(cls, xml_node):
        return None
    
    @classmethod
    def can_handle(cls, xml_node):
        return False
    
    def __getstate__(self):
        '''Do not 'pickle' InstallProfiles'''
        return None

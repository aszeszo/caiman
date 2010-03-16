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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
Represent all details of an installation in a single Python object,
including the disk target, netwrok configuration, system details (such as
timezone and locale), users, and zpool / zfs datasets.
'''


class InstallProfile(object):
    '''
    Represents an entire installation profile
    '''
    
    TAG = "install_profile"
    
    def __init__(self, disk=None, nic=None, system=None, users=None,
                 zpool=None):
        self.disk = disk
        self.nic = nic
        self.system = system
        if users is None:
            users = []
        self.users = users
        self.zpool = zpool
    
    def __str__(self):
        result = ["Install Profile:"]
        result.append(str(self.disk))
        result.append(str(self.nic))
        result.append(str(self.system))
        for user in self.users:
            result.append(str(user))
        result.append(str(self.zpool))
        return "\n".join(result)

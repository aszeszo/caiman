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
Utility functions
'''


class InstallationError(Exception):
    '''Some sort of error occurred during installation.  The exact
       cause of the error should have been logged.  So, this
       just indicates that something is wrong

    '''
    pass


class InstallationCanceledError(Exception):
    '''User selected to cancel the installation.

    '''
    pass


class InstallData(object):
    '''
    This object is used for storing information that need to be
    shared between different components of the Text Installer
    '''

    def __init__(self):
        self.install_succeeded = False
        self.log_location = None
        self.log_final = None
        self.no_install_mode = False

    def __str__(self):
        result = ["Install Data:"]
        result.append("Install Completed - %s" % str(self.install_succeeded))
        result.append("Log Location - %s" % str(self.log_location))
        result.append("Log Final - %s" % str(self.log_final))
        result.append("No Install Mode - %s" % (self.no_install_mode))
        return "\n".join(result)

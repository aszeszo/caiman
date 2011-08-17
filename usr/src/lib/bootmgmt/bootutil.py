#! /usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
Various support code for the bootmgmt package
"""

import inspect
import logging
import os
import platform

from . import BootmgmtNotSupportedError


def get_current_arch_string():
    proc = platform.processor()
    if proc == 'i386':
        return 'x86'
    elif proc == 'sparc':
        return 'sparc'
    raise BootmgmtNotSupportedError('Unsupported platform: ' + proc)


class LoggerMixin(object):

    logger = logging.getLogger('bootmgmt')
    debug_enabled = os.environ.get('BOOTMGMT_DEBUG', None) is not None

    if debug_enabled:
        logging.basicConfig(level=logging.DEBUG)

    @classmethod
    def _debug(cls, log_msg):
        if not cls.debug_enabled:
            return
        func = inspect.stack()[1][3]
        LoggerMixin.logger.debug(cls.__name__ + '.' + func + ': ' + log_msg)

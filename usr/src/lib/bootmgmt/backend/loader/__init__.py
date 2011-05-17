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
Various bootloader interfaces for pybootmgmt
"""

import sys
from ...bootutil import LoggerMixin

boot_loader_backends = ['grub2', 'legacygrub', 'sbb']


class BackendBootLoaderFactory(LoggerMixin):
    @classmethod
    def get(cls, bootconfig):
        """Returns an instance of bootloader.BootLoader appropriate for the
        system identified by the keyword arguments passed in.  Invokes a
        probe function for each boot loader backend, and returns the loader
        whose probe function returned the highest weight value.  If multiple
        boot loaders' probe functions succeed, a reference to the
        lower-weighted (deprecated) loader is stored in the higher-weighted
        loader's old_loader member (only two loaders can be linked in this
        manner).
        """
        loaderlist = []
        loader_instance = None

        for loader in boot_loader_backends:
            blmod = __name__ + '.' + loader
            __import__(blmod, level=0)
            ns = sys.modules[blmod]
            for loaderclass in ns.bootloader_classes():
                loaderinst, loaderwt = loaderclass.probe(bootconfig=bootconfig)
                if not loaderinst is None:
                    loaderlist.append((loaderinst, loaderwt))

        # Sort the loader list by weight:
        loaderlist.sort(key=(lambda t: t[1]))

        cls._debug('loaderlist => ' + str(loaderlist))

        if len(loaderlist) > 0:
            loader_instance = loaderlist[-1][0]
        if len(loaderlist) > 1:
            loader_instance.old_loader = loaderlist[-2][0]

        return loader_instance        

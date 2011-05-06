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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

import sys

from lxml import etree

from solaris_install.data_object import ParsingError
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.simple import SimpleXmlHandlerBase

""" distro_spec

 Distro object class for handling the <distro> elements
 in the manifest.

"""


class Distro(SimpleXmlHandlerBase):
    TAG_NAME = "distro"
    NAME_LABEL = "name"
    ADD_TIMESTAMP_LABEL = "add_timestamp"
    HTTP_PROXY_LABEL = "http_proxy"

    def __init__(self, name):
        super(Distro, self).__init__(name)

        self.add_timestamp = None
        self.http_proxy = None

    def to_xml(self):
        element = etree.Element(Distro.TAG_NAME)
        element.set(Distro.NAME_LABEL, self.name)
        if self.add_timestamp is not None:
            element.set(Distro.ADD_TIMESTAMP_LABEL, self.add_timestamp)

        if self.http_proxy is not None:
            element.set(Distro.HTTP_PROXY_LABEL, self.http_proxy)

        return element

    @classmethod
    def can_handle(cls, element):
        '''
        Returns True if element has:
        - the tag 'distro'
        - a name attribute

        Otherwise returns False
        '''
        if element.tag != cls.TAG_NAME:
            return False

        if element.get(cls.NAME_LABEL) is None:
            return False

        return True

    @classmethod
    def from_xml(cls, element):
        name = element.get(cls.NAME_LABEL)
        add_timestamp = \
            element.get(cls.ADD_TIMESTAMP_LABEL)
        http_proxy = element.get(cls.HTTP_PROXY_LABEL)

        # mkisofs(8) requires the volume ID be no longer than 32 characters in
        # length (specified by the -V option to mkisofs)
        if len(name) > 32:
            raise ParsingError("distribution name must be less than 32 "
                               "characters:  %s" % name)

        distro = Distro(name)
        if add_timestamp is not None:
            distro.add_timestamp = add_timestamp
        if http_proxy is not None:
            distro.http_proxy = http_proxy

        return distro


class DistroSpec(SimpleXmlHandlerBase):
    TAG_NAME = "distro_spec"


class IMGParams(SimpleXmlHandlerBase):
    TAG_NAME = "img_params"


class MediaIM(SimpleXmlHandlerBase):
    TAG_NAME = "media_im"


class VMIM(SimpleXmlHandlerBase):
    TAG_NAME = "vm_im"


class MaxSize(SimpleXmlHandlerBase):
    TAG_NAME = "max_size"

# register all the classes with the DOC
DataObjectCache.register_class(sys.modules[__name__])

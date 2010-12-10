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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
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

class GrubMods(SimpleXmlHandlerBase):
    TAG_NAME = "grub_mods"
    MIN_MEM_LABEL = "min_mem"
    TITLE_LABEL = "title"
    DEFAULT_ENTRY_LABEL = "default_entry"
    TIMEOUT_LABEL = "timeout"

    def __init__(self, name):
        super(GrubMods, self).__init__(name)
        self.min_mem = None
        self.title = None
        self.default_entry = None
        self.timeout = None

    def to_xml(self):
        element = etree.Element(GrubMods.TAG_NAME)

        if self.min_mem is not None:
            element.set(GrubMods.MIN_MEM_LABEL, self.min_mem)
        if self.title is not None:
            element.set(GrubMods.TITLE_LABEL, self.title)
        if self.default_entry is not None:
            element.set(GrubMods.DEFAULT_ENTRY_LABEL, self.default_entry)
        if self.timeout is not None:
            element.set(GrubMods.TIMEOUT_LABEL, self.timeout)

        return element

    @classmethod
    def can_handle(cls, element):
        if element.tag == cls.TAG_NAME:
            return True
        return False    

    @classmethod
    def from_xml(cls, element):
        min_mem = element.get(cls.MIN_MEM_LABEL)
        title = element.get(cls.TITLE_LABEL)
        default_entry = element.get(cls.DEFAULT_ENTRY_LABEL)
        timeout = element.get(cls.TIMEOUT_LABEL)

        grub_mods = GrubMods(cls.TAG_NAME)
        if min_mem is not None:
            grub_mods.min_mem = min_mem
        if title is not None:
            grub_mods.title = title
        if default_entry is not None:
            grub_mods.default_entry = default_entry
        if timeout is not None:
            grub_mods.timeout = timeout

        return grub_mods


class GrubEntry(SimpleXmlHandlerBase):
    TAG_NAME = "grub_entry"
    POSITION_LABEL = "position"
    TITLE_SUFFIX_LABEL = "title_suffix"
    LINE_LABEL = "line"

    def __init__(self, name):
        super(GrubEntry, self).__init__(name)
        self.position = None
        self.title_suffix = None
        self.lines = None

    def to_xml(self):
        element = etree.Element(GrubEntry.TAG_NAME)
        if self.position is not None:
            element.set(GrubEntry.POSITION_LABEL, self.position)
        if self.title_suffix is not None:
            title_element = etree.SubElement(element,
                GrubEntry.TITLE_SUFFIX_LABEL)
            title_element.text = self.title_suffix
        if self.lines is not None:
            for entry in self.lines:
                line_element = etree.SubElement(element, GrubEntry.LINE_LABEL)
                line_element.text = entry

        return element

    @classmethod
    def can_handle(cls, element):
        '''
        Returns True if element has:
        - the tag 'grub_entry'
        - a title_suffix element
        - a line element

        Otherwise returns False
        '''
        if element.tag != cls.TAG_NAME:
            return False

        title_suffix = None
        line = None

        for subelement in element.iterchildren():
            if subelement.tag == cls.TITLE_SUFFIX_LABEL:
                title_suffix = subelement.text

            if subelement.tag == cls.LINE_LABEL:
                line = subelement.text

        return True

    @classmethod
    def from_xml(cls, element):
        title_suffix = None
        lines = []

        position = element.get(cls.POSITION_LABEL)

        for subelement in element.iterchildren():
            if subelement.tag == cls.TITLE_SUFFIX_LABEL:
                title_suffix = subelement.text

            if subelement.tag == cls.LINE_LABEL:
                lines.append(subelement.text)

        grub_entry = GrubEntry(cls.TAG_NAME)
        if position is not None:
            grub_entry.position = position
        if title_suffix is not None:
            grub_entry.title_suffix = title_suffix
        if lines:
            grub_entry.lines = lines

        return grub_entry


class MaxSize(SimpleXmlHandlerBase):
    TAG_NAME = "max_size"

# register all the classes with the DOC
DataObjectCache.register_class(sys.modules[__name__])

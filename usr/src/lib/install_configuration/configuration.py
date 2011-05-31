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

""" configuration

 Configuration object class for handling the <configuration> elements
 in the manifest.

"""

import subprocess
import sys
import os.path
import urllib

from lxml import etree

from solaris_install.data_object import ParsingError
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.simple import SimpleXmlHandlerBase

_NULL = open("/dev/null", "r+")


class Configuration(SimpleXmlHandlerBase):
    TAG_NAME = "configuration"
    NAME_LABEL = "name"
    SOURCE_LABEL = "source"
    TYPE_LABEL = "type"
    DEST_LABEL = "dest"
    VALIDATION_LABEL = "validation"
    PATH_LABEL = "path"
    ARGS_LABEL = "args"
    ON_ERROR_LABEL = "on_error"

    TYPE_VALUE_NETWORK = "network"
    TYPE_VALUE_USER = "user"
    TYPE_VALUE_SYSCONF = "sysconf"
    TYPE_VALUE_ZONE = "zone"

    def __init__(self, name):
        super(Configuration, self).__init__(name)

        self.source = None
        self.dest = None
        self.type = None
        self.validation = None

    def to_xml(self):
        element = etree.Element(Configuration.TAG_NAME)

        element.set(Configuration.NAME_LABEL, self.name)
        element.set(Configuration.SOURCE_LABEL, self.source)

        if self.type is not None:
            element.set(Configuration.TYPE_LABEL, self.type)

        if self.dest is not None:
            element.set(Configuration.DEST_LABEL, self.dest)

        if self.validation is not None:
            validation_element = etree.SubElement(element,
                Configuration.VALIDATION_LABEL)
            for (key, value) in self.validation.items():
                validation_element.set(key, value)
                validation_element.set(key, value)

        return element

    @classmethod
    def can_handle(cls, element):
        '''
        Returns True if element has:
        - the tag 'configuration'
        - a name attribute
        - a source attribute

        Otherwise returns False
        '''
        if element.tag != cls.TAG_NAME:
            return False

        for entry in [cls.NAME_LABEL, cls.SOURCE_LABEL]:
            if element.get(entry) is None:
                return False

        return True

    @classmethod
    def from_xml(cls, element):
        validation = {}

        name = element.get(cls.NAME_LABEL)
        source = element.get(cls.SOURCE_LABEL)
        dest = element.get(cls.DEST_LABEL)
        type = element.get(cls.TYPE_LABEL)
        path = None
        args = None

        # supported source formats are a local file path that starts with a
        # leading slash, or URI strings that start with 'http', 'file', or 'ftp
        if "://" not in source and not source.startswith("file:/"):
            # source is a file path:
            if not os.path.exists(source):
                raise ParsingError("Invalid element specified in "
                                   "the %s section " % cls.NAME_LABEL +
                                   "of the manifest.  "
                                   "source does not exist: %s" % source)
        else:
            try:
                fileobj = urllib.urlopen(source)
            except (IOError), e:
                raise ParsingError("Invalid element specified in "
                                   "the %s section " % cls.NAME_LABEL +
                                   "of the manifest.  "
                                   "Unable to open source (%s): %s" % \
                                   (source, e))


        for subelement in element.iterchildren():
            if subelement.tag == cls.VALIDATION_LABEL:
                path = subelement.get(cls.PATH_LABEL)
                args = subelement.get(cls.ARGS_LABEL)
                on_error = subelement.get(cls.ON_ERROR_LABEL)
                if path is not None:
                    if os.path.exists(path):
                        validation[cls.PATH_LABEL] = path
                    else:
                        raise ParsingError("Invalid element specified in "
                            "the %s section of " % cls.NAME_LABEL +
                            "the manifest. validation path does not exist: "
                            "%s" % path)
                if args is not None:
                    validation[cls.ARGS_LABEL] = args
                if on_error is not None:
                    validation[cls.ON_ERROR_LABEL] = on_error

        # validate the 'source' if a validation path was specified
        if path is not None:
            try:
                if args is not None:
                    cmd = [path, args, source]
                else:
                    cmd = [path, source]
                subprocess.check_call(cmd, stdout=_NULL, stderr=_NULL)
            except subprocess.CalledProcessError:
                raise ParsingError("Error reading %s " % cls.NAME_LABEL +
                    "element from the source manifest. source manifest "
                    "specified could not be validated: %s" % source)

        configuration = Configuration(name)
        configuration.source = source
        if dest is not None:
            configuration.dest = dest
        if type is not None:
            configuration.type = type
        configuration.validation = validation

        return configuration

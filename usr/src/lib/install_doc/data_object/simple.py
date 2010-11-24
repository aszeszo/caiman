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
'''Defines the SimpleXmlHandlerBase class to convert simple XML to DataObject
'''

from lxml import etree

from solaris_install.data_object import DataObject, ParsingError


class SimpleXmlHandlerBase(DataObject):
    '''Simple XML handling DataObject base-class.

       Not to be instantiated directly, should be sub-classed.

       Converts a simple xml tag (e.g. <tag>) to a DataObject, if there is a
       name attribute in the tag, then it will be used as the name of the
       DataObject.

       To make it work, you need to sub-class it and redefine the value of
       TAG_NAME to match the XML tag, e.g.:

            from solaris_install.data_object.simple import SimpleXmlHandlerBase

            # Define the class
            class MyTag(SimpleXmlHandlerBase):
                TAG_NAME="mytag"

            # Register with DOC so that it will be used.
            DataObjectCache.register_class(MyTag)

       and that's it, this will take an XML tag like the following:

           <mytag>
              ...
           </mytag>

       and generate a DataObject for storage in the Data Object Cache.

       The main reason you might do this is to place a set of sub-tags into a
       specific location in the DOC.

    '''

    TAG_NAME = None

    def __init__(self, name=None):
        if self.TAG_NAME is None:
            raise ValueError("TAG_NAME should not be None.")

        super(DataObject, self).__init__(name)

    def to_xml(self):
        '''Generate XML'''
        elem = etree.Element(self.TAG_NAME)
        if self.name and self.name != self.TAG_NAME:
            # We got a name on import, so set it on export
            elem.set("name", self.name)

        return(elem)

    @classmethod
    def can_handle(cls, element):
        '''Check if XML tag matches TAG_NAME'''
        if element.tag != cls.TAG_NAME:
            return False
        return True

    @classmethod
    def from_xml(cls, element):
        '''Convert XML tag to a DataObject.

           If there is a name attribute in the XML tag, then we will use that
           as the name of the object for insertion in the the Data Object
           Cache.
        '''

        if element.tag != cls.TAG_NAME:
            raise ParsingError("Tag name %s != %s" %
                (element.tag, cls.TAG_NAME))

        # See if there is a name attribute, if so use it.
        name = element.get("name")
        if not name:
            name = cls.TAG_NAME

        return cls(name)

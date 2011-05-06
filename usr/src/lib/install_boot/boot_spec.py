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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
""" boot_spec.py -- library containing class definitions for boot DOC objects,
    including BootMods and BootEntry.
"""

from lxml import etree

from solaris_install.data_object import DataObject


class BootMods(DataObject):
    """ Subclass of DataObject to contain the boot_mods
        information in the Data Object Cache.
    """
    BOOT_MODS_LABEL = "boot_mods"
    TITLE_LABEL = "title"
    TIMEOUT_LABEL = "timeout"

    def __init__(self, name):
        """ Initialize the DataObject object with name.
        """
        super(BootMods, self).__init__(name)
        self.title = None
        self.timeout = None

    def __repr__(self):
        """ String representation of a BootMods object.
        """
        rep = "BootMods: "
        if self.title is not None:
            rep += 'title="%s"; ' % self.title
        if self.timeout is not None:
            rep += 'timeout=%d' % self.timeout
        return rep

    def to_xml(self):
        """ Method to create the xml boot_mods element.
        """
        element = etree.Element(BootMods.BOOT_MODS_LABEL)

        if self.title is not None:
            element.set(BootMods.TITLE_LABEL, self.title)

        if self.timeout is not None:
            element.set(BootMods.TIMEOUT_LABEL, str(self.timeout))

        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has tag: "boot_mods".
            Returns False otherwise.
        """
        if element.tag == BootMods.BOOT_MODS_LABEL:
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        """ Method to create the DOC boot_mods element.
        """
        title = element.get(BootMods.TITLE_LABEL)
        timeout = element.get(BootMods.TIMEOUT_LABEL)
        boot_mods = BootMods(BootMods.BOOT_MODS_LABEL)

        if title is not None:
            boot_mods.title = title
        if timeout is not None:
            boot_mods.timeout = int(timeout)

        return boot_mods


class BootEntry(DataObject):
    """ Subclass of DataObject to contain a boot_entry objects
        information in the Data Object Cache.
    """
    BOOT_ENTRY_LABEL = "boot_entry"
    DEFAULT_ENTRY_LABEL = "default_entry"
    INSERT_AT_LABEL = "insert_at"
    TITLE_SUFFIX_LABEL = "title_suffix"
    KERNEL_ARGS_LABEL = "kernel_args"

    def __init__(self, name):
        """ Initialize the DataObject object with name.
        """
        super(BootEntry, self).__init__(name)
        self.default_entry = None
        self.insert_at = None
        self.title_suffix = None
        self.kernel_args = None

    def __repr__(self):
        """ String representation of a BootEntry object.
        """
        rep = 'BootEntry: '
        if self.title_suffix is not None:
            rep += 'title_suffix="%s"; ' % self.title_suffix
        if self.default_entry is not None:
            rep += 'default=%s; ' % self.default_entry
        if self.insert_at is not None:
            rep += 'insert_at=%s; ' % self.insert_at
        if self.kernel_args is not None:
            rep += 'kernel_args="%s"' % self.kernel_args
        return rep

    def to_xml(self):
        """ Method to create the xml boot_entry element.
        """
        element = etree.Element(BootEntry.BOOT_ENTRY_LABEL)

        if self.default_entry is not None:
            element.set(BootEntry.DEFAULT_ENTRY_LABEL,
                        (str(self.default_entry).lower()))
        if self.insert_at is not None:
            element.set(BootEntry.INSERT_AT_LABEL, self.insert_at)

        if self.title_suffix is not None:
            title_element = etree.SubElement(element,
                BootEntry.TITLE_SUFFIX_LABEL)
            title_element.text = self.title_suffix
        if self.kernel_args is not None:
            kargs_element = etree.SubElement(element,
                                             BootEntry.KERNEL_ARGS_LABEL)
            kargs_element.text = self.kernel_args

        return element

    @classmethod
    def can_handle(cls, element):
        """ Returns True if element has the tag "boot_entry",
            and a sub-elemenent that has the tag: "title_suffix".
            Returns False otherwise.
        """
        if element.tag != BootEntry.BOOT_ENTRY_LABEL:
            return False

        title_suffix = None

        for subelement in element.iterchildren():
            if subelement.tag == BootEntry.TITLE_SUFFIX_LABEL:
                title_suffix = subelement.text

        if title_suffix is None:
            return False

        return True

    @classmethod
    def from_xml(cls, element):
        """ Method to create a DOC boot_entry element.
        """
        title_suffix = None
        kernel_args = None
        default_entry = element.get(BootEntry.DEFAULT_ENTRY_LABEL)
        insert_at = element.get(BootEntry.INSERT_AT_LABEL)

        for subelement in element.iterchildren():
            if subelement.tag == BootEntry.TITLE_SUFFIX_LABEL:
                title_suffix = subelement.text

            if subelement.tag == BootEntry.KERNEL_ARGS_LABEL:
                kernel_args = subelement.text

        boot_entry = BootEntry(BootEntry.BOOT_ENTRY_LABEL)
        if insert_at is not None:
            boot_entry.insert_at = insert_at
        if title_suffix is not None:
            boot_entry.title_suffix = title_suffix
        if kernel_args is not None:
            boot_entry.kernel_args = kernel_args
        if default_entry is not None:
            if default_entry.lower() == "true":
                boot_entry.default_entry = True
            elif default_entry.lower() == "false":
                boot_entry.default_entry = False

        return boot_entry

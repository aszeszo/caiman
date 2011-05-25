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

from lxml import etree

from solaris_install.data_object import DataObject


class AIInstance(DataObject):
    """
    ai_instance xml tag handler class
    """
    def __init__(self, name):
        """
        Class constructor
        """
        super(AIInstance, self).__init__(name)
        self.auto_reboot = False
        self.http_proxy = None

    def to_xml(self):
        """
        Convert DataObject DOM to XML
        """
        ai_instance = etree.Element("ai_instance")
        if self.auto_reboot:
            ai_instance.set("auto_reboot", "true")
        else:
            ai_instance.set("auto_reboot", "false")

        if self.name is not None:
            ai_instance.set("name", self.name)

        if self.http_proxy:
            ai_instance.set("http_proxy", self.http_proxy)

        return ai_instance

    @classmethod
    def can_handle(cls, element):
        """
        can_handle notification method for ai_instance tags
        """
        if element.tag == "ai_instance":
            return True
        return False

    @classmethod
    def from_xml(cls, element):
        """
        Convert from xml for DOM for DataObject storage
        """
        # Parse name, no validation required
        ai_name = element.get("name")

        ai_instance = AIInstance(ai_name)

        # Parse auto_reboot, validate set to true or false
        auto_reboot = element.get("auto_reboot")
        if auto_reboot is not None:
            # Convert to lowercase, to simplify tests
            auto_reboot = auto_reboot.lower()
            if auto_reboot == "true":
                ai_instance.auto_reboot = True
            elif auto_reboot == "false":
                ai_instance.auto_reboot = False
        else:
            ai_instance.auto_reboot = False

        # Parse http_proxy
        ai_instance.http_proxy = element.get("http_proxy")

        return ai_instance

    def __repr__(self):
        return "ai_instance: name='%s' auto_reboot=%s; http_proxy='%s'" % \
            (self.name, str(self.auto_reboot), self.http_proxy)

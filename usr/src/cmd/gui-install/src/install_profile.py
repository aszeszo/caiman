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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Store the non-Disk related details for the installation
'''

from solaris_install.data_object import DataObject


class InstallProfile(DataObject):
    '''
        This class stores the non-Disk related details which
        the user enters as they progress through the screens
        of the GUI Install application.

        The Disk releated details are stored in the "desired
        targets" area of the DOC, as that is where the
        TargetInstantiation (TI) checkpoint expects to find them.

        The details in this class are passed into various
        ICT checkpoints after TI has completed.
    '''

    def __init__(self, name):
        super(InstallProfile, self).__init__(name)

        self.continent = None
        self.country = None
        self.timezone = None
        self.languages = list()
        self.locales = list()
        self.default_locale = None
        self.username = None
        self.loginname = None
        self.userpassword = None
        self.hostname = None
        self.log_final = None
        self.log_location = None
        self.install_size = None

    def to_xml(self):
        ''' Abstract method which must be defined in DataObject
            sub-classes.  This class does not relate to manifests
            and so does not import or export XML.'''
        return None

    @classmethod
    def can_handle(self, xml_node):
        ''' Abstract method which must be defined in DataObject
            sub-classes.  This class does not relate to manifests
            and so does not import or export XML.'''
        return False

    @classmethod
    def from_xml(self, xml_node):
        ''' Abstract method which must be defined in DataObject
            sub-classes.  This class does not relate to manifests
            and so does not import or export XML.'''
        return None

    # Convenience methods for setting the data gathered from each screen
    def set_timezone_data(self, continent, country, timezone):
        self.continent = continent
        self.country = country
        self.timezone = timezone

    def set_locale_data(self, languages, locales, default_locale):
        self.languages = languages
        self.locales = locales
        self.default_locale = default_locale

    def set_user_data(self, username, loginname, userpassword, hostname):
        self.username = username
        self.loginname = loginname
        self.userpassword = userpassword
        self.hostname = hostname

    def set_disk_data(self, install_size):
        self.install_size = install_size

    def set_log(self, log_location, log_final):
        self.log_location = log_location
        self.log_final = log_final

    def __str__(self):
        prof = "Install Profile:\n"
        prof += "\tContinent: [%s]\n" % self.continent
        prof += "\tCountry: [%s]\n" % self.country
        prof += "\tTimezone: [%s]\n" % self.timezone
        prof += "\tLanguages:\n"
        for lang in self.languages:
            prof += "\t\t[%s]\n" % lang
        prof += "\tLocales:\n"
        for locale in self.locales:
            prof += "\t\t[%s]\n" % locale
        prof += "\tDefault locale: [%s]\n" % self.default_locale
        prof += "\tUsername: [%s]\n" % self.username
        prof += "\tLogin Name: [%s]\n" % self.loginname
        prof += "\tUser Password: [%s]\n" % self.userpassword
        prof += "\tHostname: [%s]\n" % self.hostname
        prof += "\tInstall size: [%s]\n" % self.install_size
        prof += "\tLog Location: [%s]\n" % self.log_location
        prof += "\tLog Final: [%s]\n" % self.log_final

        return prof

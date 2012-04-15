#!/usr/bin/python2.6
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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#
"""
AI List Services
"""
import gettext
import os
import sys
import signal

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.auto_install.service import AIService, VersionError

# FDICT contains the width of each field that gets printed
FDICT = {
    'arch': 6,
    'cadd': 18,
    'status': 7,
}

STATUS_WORDS = [_('Status'), _('Default'), _('Inactive')]

# Find the width of Status column
STWIDTH = max([len(item) for item in STATUS_WORDS]) + 1

DEFAULT = _("Default")
IGNORED = _("Ignored")
INACTIVE = _("Inactive")

_WARNED_ABOUT = set()

ARCH_UNKNOWN = _('* - Architecture unknown, service image does '
                 'not exist or is inaccessible.\n')


class SigpipeHandler(object):
    """ SigpipeHandler - context manager for modifying 'SIGPIPE' signal
    handling which is set to SIG_IGN by python.
    """
    def __enter__(self):
        """set the python's SIGPIPE handling behaviour
        to SIG_DFL.
        """
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    def __exit__(self, *exc_info):
        """reset the python's SIGPIPE behaviour
        to SIG_IGN.
        """
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)


class PrintObject(object):
    '''
    Class containing basic accessor utility functions and functions common
    for all descendants (criteria, manifests and profiles)
    '''

    @classmethod
    def get_header_len(cls):
        '''
        Returns
            length of header
        '''
        return len(cls.header)

    def get_max_crit_len(self):
        '''
        Returns
            length of the longest criteria name
        '''
        return self.max_crit_len

    def get_has_crit(self):
        '''
        Returns
            True if some criteria is non-empty, otherwise return False
        '''
        return self.has_crit


class CriteriaPrintObject(PrintObject):
    '''
    Class representing set of criteria
    Class constructor reads criteria from database.
    '''

    # header is common for all instances of this class
    header = _('Criteria')

    def order_criteria_list(self):
        '''
        Sorts the list of criteria in order in which criteria are printed.

        Returns
            ordered list of criteria - always contain arch, mac, ipv4
        Raises
            None
        '''
        ordered_keys = ['arch', 'mac', 'ipv4']
        keys = self.crit.keys()
        keys.sort()
        for crit in keys:
            if crit not in ordered_keys:
                ordered_keys.append(crit)

        return ordered_keys

    @classmethod
    def get_header(cls, indent, cwidth):
        '''
        Args
            indent = string which should be printed before header
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        return indent + cls.header.ljust(cwidth) + '\n'

    @classmethod
    def get_underline(cls, indent, cwidth):
        '''
        Args
            indent = string which should be printed before underline
            cwidth = width of criteria names

        Returns
            formatted string which should underline the header
        '''
        return indent + ('-' * len(cls.header)).ljust(cwidth) + '\n'

    def get_lines(self, first_line_indent, other_lines_indent, width=None):
        '''
        Args
            first_line_indent = string which should be printed before first
                                criteria line
            other_lines_indent = string which should be printed before other
                                 lines
            width = width of criteria names

        Returns
            string containing formatted criteria
        '''

        # If width is not set justify to longest criteria
        if width is None:
            width = self.max_crit_len

        line = ''
        first = True

        # Always print criteria in the same order
        ordered_keys = self.order_criteria_list()
        for akey in ordered_keys:
            val = self.crit.get(akey, '')
            if val != '':
                if first:
                    indent = first_line_indent
                    first = False
                else:
                    indent = other_lines_indent
                line += indent + akey.ljust(width) + ' = ' + val + '\n'

        if first:  # we didn't print anything so we must print at least None
            line = first_line_indent + _('None') + '\n'

        return line

    def get_criteria_info(self, crit_dict):
        '''
        Iterates over the criteria which consists of a dictionary with
        possibly arch, min memory, max memory, min ipv4, max ipv4, min mac,
        max mac, cpu, platform, min network, max network and zonename
        converting it into a dictionary with arch, mem, ipv4, mac, cpu,
        platform, network and zonename.  Any min/max attributes are stored as
        a range within the new dictionary.

        Args
            crit_dict = dictionary of the criteria

        Returns
            None

        Raises
            None
        '''

        self.crit = dict()
        self.max_crit_len = 0

        if crit_dict is None:
            return

        # self.criteria values are formatted strings, with possible endings
        # such as MB.

        for key in crit_dict.keys():
            if key == 'service':
                continue
            is_range_crit = key.startswith('MIN') or key.startswith('MAX')
            # strip off the MAX or MIN for a new keyname
            if is_range_crit:
                keyname = key[3:]  # strip off the MAX or MIN for a new keyname
            else:
                keyname = key
            self.crit.setdefault(keyname, '')
            db_value = crit_dict[key]
            if not db_value and not is_range_crit:
                # For non-range (value) criteria, None means it isn't set.
                # For range criteria, None means unbounded if the other
                # criteria in the MIN/MAX pair is set.
                continue    # value criteria not set
            self.max_crit_len = max(self.max_crit_len, len(keyname))
            fmt_value = AIdb.formatValue(key, db_value)
            if is_range_crit:
                if not db_value:
                    fmt_value = "unbounded"
                if self.crit[keyname] != '':
                    if self.crit[keyname] != fmt_value:  # dealing with range
                        if key.startswith('MAX'):
                            self.crit[keyname] = self.crit[keyname] + \
                                                 ' - ' + fmt_value
                        else:
                            self.crit[keyname] = fmt_value + ' - ' + \
                                                 self.crit[keyname]
                    elif self.crit[keyname] == "unbounded":
                        # MIN and MAX both unbounded, which means neither is
                        # set in db. Clear crit value.
                        self.crit[keyname] = ''   # no values for range
                else:  # first value, not range yet
                    self.crit[keyname] = fmt_value
                    # if the partner MIN/MAX criterion is not set in the db,
                    # handle now because otherwise it won't be processed.
                    if key.startswith('MIN'):
                        if 'MAX' + keyname not in crit_dict.keys():
                            if fmt_value == "unbounded":
                                self.crit[keyname] = ''
                            else:
                                self.crit[keyname] = self.crit[keyname] + \
                                                     ' - unbounded'
                    else:
                        if 'MIN' + keyname not in crit_dict.keys():
                            if fmt_value == "unbounded":
                                self.crit[keyname] = ''
                            else:
                                self.crit[keyname] = 'unbounded - ' + \
                                                     self.crit[keyname]
            else:
                self.crit[keyname] = fmt_value

    def __init__(self, aiqueue, name, instance, dbtable):
        '''
        Reads criteria from database and stores them into class attribute

        Args:
            aiqueue = database request queue

            name = either the name of the manifest or the name of
                   the profile to which this set of criteria belongs

            instance = instance number

            dbtable = database table, distinguishing manifests from profiles
                Assumed to be one of AIdb.MANIFESTS_TABLE or
                AIdb.PROFILES_TABLE
        '''
        # Set to True if there is at least one non-empty criteria
        self.has_crit = False
        # Store criteria in dictionary
        self.crit = dict()
        # Initialize length of the longest criteria to length of 'None' word
        self.max_crit_len = len(_('None'))
        # We need non-human output to be able to distiguish empty criteria
        criteria = AIdb.getTableCriteria(name, instance, aiqueue, dbtable,
                                         humanOutput=False, onlyUsed=True)
        if criteria is not None:
            for key in criteria.keys():
                if criteria[key] is not None:
                    self.has_crit = True
                break
            if self.has_crit:
                # We need criteria in human readable form to be able to
                # print it
                hrcrit = AIdb.getTableCriteria(name, instance, aiqueue,
                                               dbtable,
                                               humanOutput=True,
                                               onlyUsed=True)
                # convert criteria into printable values
                self.get_criteria_info(hrcrit)


class ManifestPrintObject(PrintObject):
    '''
    Class representing a manifest. This class also contains a list of criteria
    associated with this manifest
    '''

    header = _('Manifest')

    def __init__(self, aiqueue, name, default=False):
        '''
        Reads manifest from database

        Args:
            aiqueue = database request queue

            name = name of the manifest

            default = boolean whether this manifest is default or not
        '''
        # Save manifest name
        self.name = name
        # Manifest itself don't know whether it is default for its service so
        # this information should be passed in constructor
        self.default = default
        # Each manifest can have several sets of criteria - put them into list
        self.criteria = list()
        # Length of the longest criteria
        self.max_crit_len = 0
        # One manifest can have associated more sets of criteria
        instances = AIdb.numInstances(name, aiqueue)
        for instance in range(0, instances):
            self.criteria.append(CriteriaPrintObject(aiqueue, name, instance,
                                          AIdb.MANIFESTS_TABLE))
        # Check whether this manifest has at least one active criteria
        # and find the longest one
        self.has_crit = False
        for crit in self.criteria:
            self.has_crit = crit.get_has_crit()
            if crit.get_max_crit_len() > self.max_crit_len:
                self.max_crit_len = crit.get_max_crit_len()
        # Set status
        if self.default:
            self.status = DEFAULT
        else:
            if not self.has_crit:
                # It is not default and doesn't have criteria - it is Inactive
                self.status = INACTIVE
            else:
                self.status = ''

    @classmethod
    def get_header(cls, indent, mwidth, cwidth):
        '''
        Args
            indent = string which should be printed before header
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        hdr = indent + cls.header.ljust(mwidth) + \
              _('Status').ljust(STWIDTH)

        # Print just header of the first criteria
        return CriteriaPrintObject.get_header(hdr, cwidth)

    @classmethod
    def get_underline(cls, indent, mwidth, cwidth):
        '''
        Args
            indent = string which should be printed before underline
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        hdr = indent + ('-' * len(cls.header)).ljust(mwidth) + \
              ('-' * len(_('Status'))).ljust(STWIDTH)
        return CriteriaPrintObject.get_underline(hdr, cwidth)

    def get_lines(self, first_line_indent, other_lines_indent,
                       delim='\n', mwidth=None, cwidth=None):
        '''
        Args
            first_line_indent = string which should be printed before first
                                line of output
            other_lines_indent = string which should be printed before other
                                 lines of output
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            string containing formatted manifest together with it's associated
            criteria
        '''
        if mwidth is None:
            mwidth = len(self.name)

        if cwidth is None:
            cwidth = self.max_crit_len

        fl = first_line_indent + self.name.ljust(mwidth) + \
             self.status.ljust(STWIDTH)
        ol = other_lines_indent + ''.ljust(mwidth) + ''.ljust(STWIDTH)

        line = ''
        first = True
        for crit in self.criteria:
            # Print delimiter before each line except the first one
            if not first:
                line += delim
            # If default manifest has criteria, print Ignored before them
            if self.default and self.has_crit:
                line += fl + '(' + IGNORED + ':' + '\n'
                fl = ol
            line += crit.get_lines(fl, ol, width=cwidth)
            if self.default and self.has_crit:
                # Insert the right bracket before the last character (\n)
                line = line[0:-1] + ')' + line[-1]
            fl = ol
            first = False
        return line


class ProfilePrintObject(PrintObject):
    '''
    Class representing a profile. This class also contains criteria
    associated with this profile
    '''

    header = _('Profile')

    def __init__(self, aiqueue, name):
        '''
        Reads profile from database

        Args:
            aiqueue = database request queue

            name = name of the profile
        '''
        # Save profile name
        self.name = name
        self.criteria = CriteriaPrintObject(aiqueue, name, None,
                                            AIdb.PROFILES_TABLE)
        self.max_crit_len = self.criteria.get_max_crit_len()
        self.has_crit = self.criteria.get_has_crit()

    def get_lines(self, first_line_indent, other_lines_indent,
                       pwidth=None, cwidth=None):
        '''
        Args
            first_line_indent = string which should be printed before first
                                criteria line
            other_lines_indent = string which should be printed before other
                                 lines
            pwidth = profile names width
            cwidth = width of criteria names

        Returns
            string containing formatted profile together with it's associated
            criteria
        '''
        if pwidth is None:
            pwidth = len(self.name)

        if cwidth is None:
            cwidth = len(self.max_crit_len)

        fl = first_line_indent + self.name.ljust(pwidth)
        ol = other_lines_indent + ' '.ljust(pwidth)
        return self.criteria.get_lines(fl, ol, width=cwidth)

    @classmethod
    def get_header(cls, indent, pwidth, cwidth):
        '''
        Args
            indent = string which should be printed before header
            pwidth = profile name width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        hdr = indent + cls.header.ljust(pwidth)
        return CriteriaPrintObject.get_header(hdr, cwidth)

    @classmethod
    def get_underline(cls, indent, pwidth, cwidth):
        '''
        Args
            indent = string which should be printed before underline
            pwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        hdr = indent + ('-' * len(cls.header)).ljust(pwidth)
        return CriteriaPrintObject.get_underline(hdr, cwidth)


class ServicePrintObject(PrintObject):
    '''
    Common base class for classes representing one service
    '''

    def __init__(self, sname):
        '''
        Opens database for given service and sets database request queue
        '''
        self.name = sname
        try:
            self.service = AIService(sname)

        except VersionError as err:
            warn_version(err)
            raise

        path = self.service.database_path

        if os.path.exists(path):
            try:
                maisql = AIdb.DB(path)
                maisql.verifyDBStructure()
                self.aiqueue = maisql.getQueue()

            except StandardError as err:
                sys.stderr.write(_('Error: AI database access error\n%s\n')
                                    % err)
                raise
        else:
            sys.stderr.write(_('Error: unable to locate AI database for "%s" '
                               'on server\n') % sname)
            # I can't read from service database and I should raise an error
            # for this condition.
            raise StandardError

    def get_max_profman_len(self):
        '''
        Returns
            length of the longest manifest/profile name
        '''
        return self.max_profman_len

    def get_name(self):
        '''
        Returns
            name of the service
        '''
        return self.name

    def __str__(self):
        if self.non_empty():
            return self.print_header() + self.get_lines()
        else:
            return self.empty_msg % self.name


class ServiceProfilePrint(ServicePrintObject):
    '''
    Class representing one service and its associated profiles
    '''

    empty_msg = _('There are no profiles configured for local service '
                  '"%s".\n')

    def __init__(self, sname):
        '''
        Reads profile names associated with this service from database,
        creates objects for them and stores these objects into instance
        attributes
        '''
        ServicePrintObject.__init__(self, sname)

        self.profiles = list()
        self.max_profman_len = 0
        self.max_crit_len = 0

        try:
            # Read all profiles for this service
            for name in AIdb.getNames(self.aiqueue, AIdb.PROFILES_TABLE):
                # Record the longest profile name
                if self.max_profman_len < len(name):
                    self.max_profman_len = len(name)
                profile = ProfilePrintObject(self.aiqueue, name)
                # Record the longest criteria in this service
                if profile.get_max_crit_len() > self.max_crit_len:
                    self.max_crit_len = profile.get_max_crit_len()
                self.profiles.append(profile)

        except StandardError as err:
            sys.stderr.write(_('Error: AI database access error\n%s\n')
                                % err)
            raise

    @staticmethod
    def get_header(indent, pwidth, cwidth):
        '''
        Args
            indent = string which should be printed before header
            pwidth = profile name width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        return ProfilePrintObject.get_header(indent, pwidth, cwidth)

    @staticmethod
    def get_underline(indent, pwidth, cwidth):
        '''
        Args
            indent = string which should be printed before underline
            pwidth = profile name width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        return ProfilePrintObject.get_underline(indent, pwidth, cwidth)

    def print_header(self):
        '''
        Returns underlined header justified according to length of header and
        length of the longest printed profile and criteria

        Returns
            formatted underline string suitable for printing
        '''
        plen = max(ProfilePrintObject.get_header_len(), self.max_profman_len)
        clen = max(CriteriaPrintObject.get_header_len(), self.max_crit_len)

        line = self.get_header('', plen + 2, clen)
        line += self.get_underline('', plen + 2, clen)

        return line

    def get_lines(self, first_line_indent='',
                   other_lines_indent='', pwidth=None, cwidth=None):
        '''
        Args
            first_line_indent = string which should be printed before first
                                line
            other_lines_indent = string which should be printed before other
                                 lines
            pwidth = profile names width
            cwidth = width of criteria names

        Returns
            string containing formatted profiles together with their associated
            criteria
        '''
        if pwidth is None:
            # We want 2 spaces between columns
            pwidth = self.max_profman_len + 2

        if cwidth is None:
            cwidth = self.max_crit_len

        line = ''
        fl = first_line_indent
        ol = other_lines_indent
        for prof in self.profiles:
            line += prof.get_lines(fl, ol, pwidth=pwidth, cwidth=cwidth)
            fl = ol

        return line

    def non_empty(self):
        '''
        Returns
            True if this service has at least one profile, otherwise returns
            False
        '''
        if self.profiles:
            return True
        else:
            return False


class ServiceManifestPrint(ServicePrintObject):
    '''
    Class representing one service and its associated manifests
    '''

    def __init__(self, sname):
        '''
        Reads manifest names associated with this service from database,
        creates objects for them and stores these objects into instance
        attributes. Manifests are sorted into 3 groups - Active, Inactive
        and Default.
        '''
        ServicePrintObject.__init__(self, sname)

        try:
            default_mname = self.service.get_default_manifest()
        except StandardError:
            default_mname = ""

        self.default_manifest = None
        self.active_manifests = list()
        self.inactive_manifests = list()
        self.max_profman_len = 0
        self.max_crit_len = 0

        try:
            # Read all manifests for this service
            for name in AIdb.getNames(self.aiqueue, AIdb.MANIFESTS_TABLE):
                if self.max_profman_len < len(name):
                    self.max_profman_len = len(name)
                if name == default_mname:
                    manifest = ManifestPrintObject(self.aiqueue, name,
                                             default=True)
                    self.default_manifest = manifest
                else:
                    manifest = ManifestPrintObject(self.aiqueue, name)
                    if manifest.get_has_crit():
                        self.active_manifests.append(manifest)
                    else:
                        self.inactive_manifests.append(manifest)
                if manifest.get_max_crit_len() > self.max_crit_len:
                    self.max_crit_len = manifest.get_max_crit_len()

        except StandardError as err:
            sys.stderr.write(_('Error: AI database access error\n%s\n')
                                % err)
            raise

    @staticmethod
    def get_header(indent, mwidth, cwidth):
        '''
        Args
            indent = string which should be printed before header
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        return ManifestPrintObject.get_header(indent, mwidth, cwidth)

    @staticmethod
    def get_underline(indent, mwidth, cwidth):
        '''
        Args
            indent = string which should be printed before underline
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        return ManifestPrintObject.get_underline(indent, mwidth, cwidth)

    def print_header(self):
        '''
        Returns underlined header justified according to length of header and
        length of the longest printed manifest and criteria

        Returns
            formatted underline string suitable for printing
        '''
        plen = max(ManifestPrintObject.get_header_len(), self.max_profman_len)
        clen = max(CriteriaPrintObject.get_header_len(), self.max_crit_len)

        return self.get_header('', plen + 2, clen) + \
               self.get_underline('', plen + 2, clen)

    def get_lines(self, first_line_indent='',
                   other_lines_indent='', mwidth=None, cwidth=None):
        '''
        Args
            first_line_indent = string which should be printed before first
                                line
            other_lines_indent = string which should be printed before other
                                 lines
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            string containing formatted manifests together with their
            associated criteria
        '''
        if mwidth is None:
            # We want 2 spaces between columns
            mwidth = self.max_profman_len + 2

        if cwidth is None:
            cwidth = self.max_crit_len

        line = ''
        fl = first_line_indent
        ol = other_lines_indent
        # Print active manifests first
        for manifest in self.active_manifests:
            line += manifest.get_lines(fl, ol, mwidth=mwidth,
                                                cwidth=cwidth)
            fl = ol

        # Then print default manifest
        if self.default_manifest:
            line += self.default_manifest.get_lines(fl, ol, mwidth=mwidth,
                                                     cwidth=cwidth)
            fl = ol

        # Print inactive manifests last
        for manifest in self.inactive_manifests:
            line += manifest.get_lines(fl, ol, mwidth=mwidth,
                                                cwidth=cwidth)
            fl = ol

        return line

    def non_empty(self):
        '''
        Returns
            True because each service has at least one Default manifest
        '''
        return True


class ServicesList(PrintObject):
    '''
    Base class for list of services
    '''

    def get_lines(self, indent='', delim='\n',
                    width=None, cwidth=None):
        '''
        '''
        line = ''
        first = True
        for s in self.services:
            # Print just services containing some profiles/manifests
            if s.non_empty():
                if not first:
                    line += delim
                line += s.get_name() + '\n'
                line += s.get_lines(indent, indent, width, cwidth)
                first = False

        return line

    def __str__(self):
        '''
        '''
        if not self.services:
            return self.empty_msg

        ind = '   '

        # Count the width of manifests/profiles column
        j = max(self.max_name_len, len(ind) + self.max_profman_len,
                self.get_header_len()) + 2
        return self.get_header(j, self.max_crit_len) + \
               self.get_underline(j, self.max_crit_len) + \
               self.get_lines(ind, '\n', j - len(ind), self.max_crit_len)


class ServicesManifestList(ServicesList):
    '''
    Class representing list of services. Services contain manifests
    '''

    # Message printed in case that there are no services configured
    # (each service should have at least Default profile
    empty_msg = _('There are no manifests configured for local services.\n')
    header = _('Service/Manifest Name')

    def __init__(self, srvcs, name=None):
        '''
        Reads dictionary of services and creates list of service objects

        Args:
            srvcs = dictionary of service properties
        '''
        self.services = list()
        self.max_crit_len = 0
        self.max_profman_len = 0
        if name:
            # We are going to print only one service
            srvlist = [name]
            self.max_name_len = len(name)
        else:
            self.max_name_len = len(max(srvcs.keys(), key=len))
            srvlist = srvcs.keys()
            srvlist.sort()
        for s in srvlist:
            try:
                service = ServiceManifestPrint(s)
            except (StandardError, VersionError):
                # Ignore these errors and just skip these services
                # Errors/Warnings should be already printed
                pass
            else:
                if self.max_crit_len < service.get_max_crit_len():
                    self.max_crit_len = service.get_max_crit_len()
                if self.max_profman_len < service.get_max_profman_len():
                    self.max_profman_len = service.get_max_profman_len()

                if service.non_empty():
                    self.services.append(service)

    @classmethod
    def get_header(cls, mwidth, cwidth):
        '''
        Args
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        hdr = cls.header.ljust(mwidth) + _('Status').ljust(STWIDTH)
        return CriteriaPrintObject.get_header(hdr, cwidth)

    @classmethod
    def get_underline(cls, mwidth, cwidth):
        '''
        Args
            mwidth = manifest name width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        hdr = ('-' * len(cls.header)).ljust(mwidth) +\
              ('-' * len(_('Status'))).ljust(STWIDTH)
        return CriteriaPrintObject.get_underline(hdr, cwidth)


class ServicesProfileList(ServicesList):
    '''
    Class representing list of services. Services contain profiles
    '''

    empty_msg = _('There are no profiles configured for local services.\n')
    header = _('Service/Profile Name')

    def __init__(self, srvcs, name=None):
        '''
        '''
        self.services = list()
        self.max_crit_len = 0
        self.max_profman_len = 0
        if name:
            srvlist = [name]
            self.max_name_len = len(name)
            # There is different error msg if we are printing just one service
            self.empty_msg = ServiceProfilePrint.empty_msg % name
        else:
            self.max_name_len = len(max(srvcs.keys(), key=len))
            srvlist = srvcs.keys()
            srvlist.sort()
        for s in srvlist:
            try:
                service = ServiceProfilePrint(s)
            except (StandardError, VersionError):
                # Ignore these errors and just skip these services
                # Errors/Warnings should be already printed
                pass
            else:
                if self.max_crit_len < service.get_max_crit_len():
                    self.max_crit_len = service.get_max_crit_len()
                if self.max_profman_len < service.get_max_profman_len():
                    self.max_profman_len = service.get_max_profman_len()

                if service.non_empty():
                    self.services.append(service)

    @staticmethod
    def get_header(pwidth, cwidth):
        '''
        Args
            pwidth = profile width
            cwidth = width of criteria names

        Returns
            formatted header string suitable for printing
        '''
        hdr = ServicesProfileList.header.ljust(pwidth)
        return CriteriaPrintObject.get_header(hdr, cwidth)

    @staticmethod
    def get_underline(pwidth, cwidth):
        '''
        Args
            pwidth = profile width
            cwidth = width of criteria names

        Returns
            formatted underline string suitable for printing
        '''
        hdr = ('-' * len(ServicesProfileList.header)).ljust(pwidth)
        return CriteriaPrintObject.get_underline(hdr, cwidth)


def warn_version(version_err):
    '''Prints a short warning about version incompatibility to stderr
    for a given service. For any one invocation of "installadm list"
    the warning will only be printed once.

    '''
    if version_err.service_name not in _WARNED_ABOUT:
        print >> sys.stderr, version_err.short_str()
        _WARNED_ABOUT.add(version_err.service_name)
        return True
    else:
        return False


def get_usage():
    ''' get usage for list'''
    return _("list\t[-n|--service <svcname>] [-c|--client] "
              "[-m|--manifest] [-p|--profile]")


def parse_options(cmd_options=None):
    """
    Parses and validate options

    Args
        None

    Returns
        a dictionary of the valid options

            { 'client':Bol, 'service':None/SName, 'manifest':Bol }

    Raises
        None

    """
    desc = _("Lists all enabled installation services on a system. "
             "Or, with -n option, lists a specific installation service. "
             "Or, with -c option, lists information about clients "
             "of installation services. "
             "Or, with -m option, lists the manifest information.")
    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage, description=desc)

    parser.add_option("-n", "--service", dest="service", default=None,
                      type="string",
                      help=_("list information about named service"))
    parser.add_option("-c", "--client", dest="client", default=False,
                      action="store_true",
                      help=_("list client information"))
    parser.add_option("-m", "--manifest", dest="manifest", default=False,
                      action="store_true",
                      help=_("list manifest information"))
    parser.add_option("-p", "--profile", dest="profile", default=False,
                      action="store_true",
                      help=_("list profile information"))

    (loptions, args) = parser.parse_args(cmd_options)

    if args:
        parser.error(_('Unexpected argument(s): %s') % args)

    return loptions


def which_arch(service):
    """
    Looks to see if the platform of the service is i386 or sparc.
    If the service.image does not exist then we are unable to determine the
    architecture.

    Args
        service - service object to query

    Returns
        *       if service.arch is None
        otherwise return the value service.arch

    Raises
        None
    """
    if service.arch is None:
        return '*'

    return service.arch


def print_local_services(sdict, width, awidth):
    """
    Iterates over the local service dictionary and prints out
    service name, aliasof, status, architecture, and image path.
    All fields are left justified according to FDICT[field], width,
    awidth or simply printed in the case of path.

    The service dictionary looks like:

        {
            service1:
              [
                { 'status':on1, 'path':path1, 'arch':arch1 },
                ...
              ],
            ...
        }

    Args
        sdict = service dictionary
        width = length of longest service name
        awidth = length of longest aliasof service name

    Returns
        None

    Raises
        None
    """
    tkeys = sdict.keys()
    tkeys.sort()
    missing_image = False
    for aservice in tkeys:
        firstone = True
        for info in sdict[aservice]:
            if firstone == True:
                print aservice.ljust(width),
                firstone = False
            else:
                print ' ' * width
            print info['aliasof'].ljust(awidth),
            print info['status'].ljust(FDICT['status']),
            print info['arch'].ljust(FDICT['arch']),
            # If the architecture can't be identified, either the image is
            # missing or not accessible.
            if info['arch'] == "*":
                missing_image = True
            print info['path']

    if missing_image:
        print cw(ARCH_UNKNOWN)
    print


def find_clients(lservices, sname=None):
    """
    find_clients() returns a dictionary that contains a list of
    dictionaries.

    The service name is the key for the main dictionary and the
    client, image path, and arch are members of the subdictionary,
    as follows:

        {
          'service1': [
                { 'ipath':<path1>, 'client':<client1>, 'arch': <arch>},
                ....
                      ],
          ....
        }

    Args
        lservices = config.get_all_service_props()
        sname - service name, if only interesetd in clients of a
                specific service

    Returns
        dictionary of a list of dictionaries

    Raises
        None

    """
    sdict = dict()
    for servicename in lservices.keys():
        if sname and sname != servicename:
            continue
        try:
            service = AIService(servicename)
        except VersionError as version_err:
            warn_version(version_err)
            continue
        arch = which_arch(service)
        image_path = [service.image.path]
        client_info = config.get_clients(servicename)
        for clientkey in client_info:
            # strip off the leading '01' and reinsert ':'s
            client = AIdb.formatValue('mac', clientkey[2:])
            tdict = {'client': client, 'ipath': image_path, 'arch': arch}
            if servicename in sdict:  # existing service name
                slist = sdict[servicename]
                slist.extend([tdict])
                sdict[servicename] = slist
            else:  # new service name key
                sdict[servicename] = [tdict]
    return sdict


def do_header(lol):
    """
    Iterates over a list of list of the headers to print.
    The list of lists looks like:

        [
            [ 'field1', width1 ],
            ...
        ]
    Then it prints the resulting header and underlines based
    upon the widths.  The output looks like:

        Field1       Field2
        ------       ------

    The spacing between the fields is based upon the width.
    The underline is based upon the field name length.

    Args
        lol = list of lists

    Returns
        None

    Raises
        None
    """
    header = "\n"
    line = ""
    for part in lol:
        fname = part[0]
        header = header + fname[0:part[1]].ljust(part[1] + 1)
        line = line + "-" * len(fname[0:part[1]])
        line += ' ' * (part[1] - len(fname[0:part[1]]) + 1)
    print header
    print line


def get_local_services(services, sname=None):
    """
    Iterates over the local services on a host creating a dictionary
    with the service name as the key and status, path, architecture,
    and aliasof as the value.  If name is not None then it ensures
    that only the named service is retrieved.

    Args
        services = config.get_all_service_props()
        name = service name

    Returns
        a service dictionary made up of a list of dictionary of services.

        {
        service1:
          [
            {'status':on1, 'path':path1, 'arch':arch1, 'aliasof':aliasof1},
            ...
          ],
        ...
        }

        the width of the longest service name
        the width of the longest aliasof name

    Raises
        None
    """
    width = 0
    aliasofwidth = 1
    sdict = dict()
    for akey in services:
        serv = services[akey]
        servicename = akey
        # ensure that the current service has the keys we need.
        # if not, print error, but continue listing other services
        try:
            config.verify_key_properties(akey, serv)
        except config.ServiceCfgError as err:
            print >> sys.stderr, err
            continue
        try:
            service = AIService(servicename)
        except VersionError as err:
            warn_version(err)
            continue
        if config.PROP_ALIAS_OF in serv:
            image_path = service.image.path
            serv[config.PROP_IMAGE_PATH] = image_path

        info = dict()
        # if a service name is passed in then
        # ensure it matches the current name
        if not sname or sname == servicename:
            width = max(len(servicename), width)
            info['status'] = serv[config.PROP_STATUS]
            info['path'] = serv[config.PROP_IMAGE_PATH]
            info['arch'] = which_arch(service)
            if config.PROP_ALIAS_OF in serv:
                # have an alias
                aliasof = serv[config.PROP_ALIAS_OF]
            else:
                aliasof = '-'
            info['aliasof'] = aliasof
            aliasofwidth = max(len(aliasof), aliasofwidth)
            if servicename in sdict:
                slist = sdict[servicename]
                slist.extend([info])
                sdict[servicename] = slist
            else:
                sdict[servicename] = [info]

    return sdict, width, aliasofwidth


def list_local_services(services, name=None):
    """
    Lists the local services for a host.  If name is not
    None then it prints only the named service.

    Args
        services = config.get_all_service_props()
        name = service name

    Returns
        None

    Raises
        None

    """
    sdict, width, awidth = get_local_services(services, sname=name)

    width = max(width, len(_('Service Name')))
    awidth = max(awidth, len(_('Alias Of')))
    fields = [[_('Service Name'), width]]
    fields.extend([[_('Alias Of'), awidth]])
    fields.extend([[_('Status'), FDICT['status']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_local_services(sdict, width, awidth)


def list_local_clients(lservices, name=None):
    """
    Lists the local clients for a host or for a service
    if name is not None.

    Args
        lservices = config.get_all_service_props()
        service name

    Returns
        None

    Raises
        None
    """
    def get_clients(lservices, sname=None):
        """
        Gets the clients (x86 and Sparc) for the services of a local host.
        If a service name is passed in, then only get the clients for the
        named service on the local host.

        Args
            lservices = services on a host (config.get_all_service_props())
            sname = a named service

        Returns
            a service dictionary of both x86 and Sparc clients

                {
                    'service1': [
                                  {
                                    'ipath':[path1, path2],
                                    'client':client1,
                                    'arch':arch1
                                  },
                                ....
                                ],
                    ....
                }

        Raises
            None

        """

        allclients = find_clients(lservices, sname=sname)
        # get width of largest service name
        if allclients:
            width = max(map(len, allclients))
        else:
            width = 0

        return allclients, width

    def print_clients(width, sdict):
        """
        Iterates over a dictionary of service clients printing
        information about each one.

        Args
            width = widest service name
            sdict = service dictionary of clients
                    (same as in get_clients() description)

        Returns
            None

        Raises
            None
        """
        # sort the keys so that the service names are in alphabetic order.
        tkeys = sdict.keys()
        tkeys.sort()
        missing_image = False
        for aservice in tkeys:
            service_firstone = True
            for aclient in sdict[aservice]:
                if service_firstone == True:
                    print aservice.ljust(width),
                    service_firstone = False
                else:
                    print ' ' * width,
                print aclient['client'].ljust(FDICT['cadd']),
                print aclient['arch'].ljust(FDICT['arch']),
                # If the architecture can't be identified, either the image is
                # missing or not accessible.
                if aclient['arch'] == '*':
                    missing_image = True
                path_firstone = True
                cpaths = list()
                for cpath in aclient['ipath']:
                    if cpath not in cpaths:
                        if path_firstone == False:
                            spaces = width + FDICT['cadd'] + FDICT['arch'] + 2
                            print ' '.ljust(spaces),
                        else:
                            path_firstone = False
                        print cpath
                    cpaths.insert(0, cpath)
            if missing_image:
                print cw(ARCH_UNKNOWN)

    # start of list_local_clients
    sdict, width = get_clients(lservices, sname=name)
    if not sdict:
        if not name:
            print _('There are no clients configured for local services.\n')
        else:
            print _('There are no clients configured for local service, '
                    '"%s".\n') % name
        return

    width = max(width, len(_('Service Name')))
    fields = [[_('Service Name'), width]]
    fields.extend([[_('Client Address'), FDICT['cadd']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_clients(width, sdict)
    print


def do_list(cmd_options=None):
    '''
    List information about AI services, clients, and manifests.
        -n option, lists a specific install service.
        -c option, lists information about clients
            of install services.
        -m option, lists the manifest information.
        -p options, lists profiles

    '''
    options = parse_options(cmd_options)

    services = config.get_all_service_props()
    if not services:
        if options.service:
            raise SystemExit(_('Error: Service does not exist: "%s".\n') %
                               options.service)
        else:
            output = _('There are no services configured on this server.\n')
            sys.stdout.write(output)
            raise SystemExit(0)

    if options.service and options.service not in services:
        raise SystemExit(_('Error: Service does not exist: "%s".\n') %
                           options.service)

    # list
    if not options.client and not options.manifest and not options.profile:
        try:
            list_local_services(services, name=options.service)
        except (config.ServiceCfgError, ValueError) as err:
            raise SystemExit(err)
    else:
        # list -c
        if options.client:
            list_local_clients(services, name=options.service)
        # list -m
        if options.manifest:
            if options.client:
                print
            print ServicesManifestList(services, name=options.service)
        # list -p
        if options.profile:
            if options.client or options.manifest:
                print
            print ServicesProfileList(services, name=options.service)


if __name__ == '__main__':
    # initialize gettext
    gettext.install("solaris_install_installadm", "/usr/share/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_list()

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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
"""Conversion routines used to Solaris 10 convert rules and profile files to
the xml format used by the Solaris installer

"""

import common
import gettext
import itertools
import logging
import os.path
import re

import pkg.client.api as api
import pkg.client.api_errors as apx
import os

from common import _
from common import fetch_xpath_node
from common import RULES_FILENAME
from default_xml import DEFAULT_XML_EMPTY
from lxml import etree
from StringIO import StringIO

# This is defined here since we can't collect this information from the
# pkg api. This is needed to make the calls into the pkg api.
CLIENT_API_VERSION = 57

# These validation patterns were taken directly from the jumpstart
# check script

# Disk Patterns
# SPARC: cwtxdysz or cxdysz (c0t0d0s0 or c0d0s0)
# x86: cwtxdy or cxdy (c0t0d0 or c0d0)

# DISK1_PATTERN covers cxtydz (c0t0d0)
DISK1_PATTERN = re.compile("c[0-9][0-9]*t[0-9][0-9]*.*d[0-9][0-9]*$")
# DISK2_PATTERN covers cxdy (c0d0)
DISK2_PATTERN = re.compile("c[0-9][0-9]*.*d[0-9][0-9]*$")

# Slice Patterns: cwtxdysz or cxdysz (c0t0d0s0 or c0d0s0)
SLICE1_PATTERN = re.compile("(c[0-9][0-9]*t[0-9][0-9]*.*d[0-9][0-9]*)s[0-7]$")
SLICE2_PATTERN = re.compile("(c[0-9][0-9]*.*d[0-9][0-9]*)s[0-7]$")

NUM_PATTERN = re.compile("[0-9][0-9]*$")
SIZE_PATTERN = re.compile("([0-9][0-9]*)([g|m]?)$")

FILESYSTEM_ARG_PATTERN = re.compile("..*:/..*")

DEFAULT_POOL_NAME = "rpool"

SOFTWARE_INSTALL = "install"
SOFTWARE_UNINSTALL = "uninstall"

# Follow the same name scheme used for mirror pools using the old jumpstart
# scripts.  When not specified mirror names start with the letter "d" followed
# by a number between 0 and 127
DEFAULT_MIRROR_POOL_NAME = "d"


class XMLRuleData(object):
    """This object holds all the data read in from the rules file.  This data
    is converted into an xml document which then can be manipluated as needed.

    """

    def __init__(self, line_num, rule_dict, report, logger):

        if logger is None:
            logger = logging.getLogger("js2ai")
        self.logger = logger
        self.rule_line_num = line_num
        self._root = None
        self._report = report
        self.rule_dict = rule_dict
        self.__process_rule()

    @property
    def report(self):
        """Conversion report associated with the object"""
        return self._report

    @property
    def root(self):
        """The xml root element"""
        return self._root

    def __unsupported_keyword(self, line_num, keyword, values):
        """Generate an unsupported keyword error message"""
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "keyword: %(key)s") % \
                            {"file": RULES_FILENAME,
                             "lineno": line_num, \
                             "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_negation(self, line_num):
        """Generate an unsupported negation error message"""
        self.logger.error(_("%(file)s: line %(lineno)d: negation "
                            "'!' not supported in manifests") % \
                            {"file": RULES_FILENAME,
                             "lineno": line_num})
        self._report.add_unsupported_item()

    def __invalid_syntax(self, line_num, keyword):
        """Generate an invalid syntax error message"""
        self.logger.error(_("%(file)s: line %(lineno)d: invalid syntax for "
                            "keyword '%(key)s' specified") % \
                            {"file": RULES_FILENAME,
                             "lineno": line_num, "key": keyword})
        self._report.add_process_error()

    def __convert_common(self, line_num, keyword, values):
        """Converts the specified keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self._root,
                                         common.ELEMENT_AI_CRITERIA)
        try:
            criteria_name.set(common.ATTRIBUTE_NAME,
                              self.rule_keywd_conv_dict[keyword])
        except KeyError:
            self.__unsupported_keyword(line_num, keyword, values)
            # since we've already added an element to the tree we need to
            # cleanup that element due to the exception.
            self._root.remove(criteria_name)
            return
        crit_value = etree.SubElement(criteria_name, common.ELEMENT_VALUE)
        crit_value.text = values[0]

    def __convert_memsize(self, line_num, keyword, values):
        """Converts memsize value from the form 'value1-value2' to
        'value1 value2' and outputs the range node to the criteria file

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self._root,
                                         common.ELEMENT_AI_CRITERIA)
        criteria_name.set(common.ATTRIBUTE_NAME, "mem")
        if "-" in values[0]:
            crit_range = etree.SubElement(criteria_name, common.ELEMENT_RANGE)
            crit_range.text = values[0].replace("-", " ")
        else:
            crit_value = etree.SubElement(criteria_name, common.ELEMENT_VALUE)
            crit_value.text = values[0]

    def __convert_network(self, line_num, keyword, values):
        """Converts the network keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self._root,
                                         common.ELEMENT_AI_CRITERIA)
        criteria_name.set(common.ATTRIBUTE_NAME, "ipv4")
        try:
            addr_a, addr_b, addr_c, remainder = values[0].split(".", 3)
        except ValueError:
            self.__invalid_syntax(line_num, keyword)
            self._root.remove(criteria_name)
            # since we've already added an element to the tree we need to
            # cleanup that element due to the exception.
            return

        crit_range = etree.SubElement(criteria_name, common.ELEMENT_RANGE)
        net_range = ("%s %s.%s.%s.255") % (values[0], addr_a, addr_b, addr_c)
        crit_range.text = net_range

    def __process_rule(self):
        """Process the rules dictionary entries and convert to an xml doc"""
        if self.rule_dict is None:
            # There's nothing to convert.  This is a valid condition
            # for example if the file couldn't be read
            self._report.conversion_errors = 0
            self._report.unsupported_items = 0
            self._root = None
            return

        if self._root is not None:
            return

        self._root = etree.Element(common.ELEMENT_AI_CRITERIA_MANIFEST)

        count = 0
        key_dict = self.rule_dict.key_values_dict
        for key_values in key_dict.iterkeys():
            keyword = key_dict[key_values].key
            values = key_dict[key_values].values
            line_num = key_dict[key_values].line_num
            if line_num is None or values is None or keyword is None:
                raise ValueError
            if "!" in keyword:
                self.__unsupported_negation(line_num)
                continue
            try:
                function_to_call = self.rule_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(line_num, keyword, values)
            else:
                function_to_call(self, line_num, keyword, values)
                count += 1
        if count == 0:
            self._root = None

    rule_conversion_dict = {
        "any": __unsupported_keyword,
        "arch": __convert_common,
        "disksize": __unsupported_keyword,
        "domainname": __unsupported_keyword,
        "hostaddress": __convert_common,
        "hostname": __unsupported_keyword,
        "installed": __unsupported_keyword,
        "karch": __convert_common,
        "memsize": __convert_memsize,
        "model": __convert_common,
        "network": __convert_network,
        "osname": __unsupported_keyword,
        "probe": __unsupported_keyword,
        "totaldisk": __unsupported_keyword,
        }

    rule_keywd_conv_dict = {
        "arch": "cpu",
        "hostaddress": "ipv4",
        "karch": "arch",
        "model": "platform",
        }


class XMLProfileData(object):
    """This object takes the profile data and converts it to an xml document"""

    def __init__(self, name, prof_dict, report, default_tree, local, logger):

        if logger is None:
            logger = logging.getLogger("js2ai")
        self.logger = logger
        self.profile_name = name
        self._report = report
        if default_tree is None:
            default_tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
        self._tree = default_tree
        self._root = self._tree.getroot()
        self._ai_instance_default = None
        self._local = local
        self.inst_type = "ips"
        self.prof_dict = prof_dict
        self._boot_device = None
        self._root_device = None
        #
        # _rootdisk will be used to hold to Jumpstart rootdisk keyword.
        # We won't be able to determine this automatically but we can follow
        # the initial priority rules as outlined in the
        # How JumpStart Determines a System's Root Disk (Initial Installation)
        #
        # 1. If the root_device keyword is specified in the profile, the
        #    JumpStart program sets rootdisk to the root device.
        # 2. If rootdisk is not set and the boot_device keyword is specified
        #    in the profile, the JumpStart program sets rootdisk to the boot
        #    device.
        # 3. If rootdisk is not set and a filesys cwtxdysz size / entry is
        #    specified in the profile, the JumpStart program sets rootdisk to
        #    the disk that is specified in the entry.
        #
        self._rootdisk = None
        self._rootdisk_set_by_keyword = None
        self._root_pool = None
        self._root_pool_create_via_keyword = None
        self.__process_profile()

    def __device_name_conversion(self, device):
        """Takes a device and if that device is a slice specified device
        removes the slice portion of the device and returns the new device
        name.  If the device passed in is not a slice device it returns the
        original device passed in

        """
        match_pattern = SLICE1_PATTERN.match(device)
        if match_pattern:
            device = match_pattern.group(1)
        else:
            match_pattern = SLICE2_PATTERN.match(device)
            if match_pattern:
                device = match_pattern.group(1)
        return device

    def __duplicate_keyword(self, line_num, keyword, values):
        """Log a duplicate keyword error and add a process error to report"""
        self.logger.error(_("%(file)s: line %(lineno)d: invalid entry, "
                            "duplicate keyword encountered: %(key)s") % \
                            {"file": self.profile_name,
                             "lineno": line_num, \
                             "key": keyword})
        self._report.add_process_error()

    def __is_valid_device_name(self, device):
        """ Validate the disk name based on the regexp used by the check script

         The disk name is either cXtXdX or cXdX
         For world wide name(MPXIO), disk is of the form
         cXtX[combination of alpha numeric characters]dX
         c[0-9][0-9]*t[0-9][0-9]*.*d[0-9][0-9]*$
         c[0-9][0-9]*.*d[0-9][0-9]*$

         Returns: True if valid, False otherwise

         """
        match_pattern = DISK1_PATTERN.match(device)
        if not match_pattern:
            match_pattern = DISK2_PATTERN.match(device)
            if not match_pattern:
                return False
        return True

    def __is_valid_device(self, device):
        """ Validate the disk name based on the regexp used by the check script

        A valid device is a string that is either a) a
        string that starts with /dev/dsk/ and ends with a
        valid slice name, or b) a valid slice name.

        Returns: True if valid, False otherwise

        """
        if device.startswith("/dev/dsk"):
            device = os.path.basename(device)
        return self.__is_valid_slice(device)

    def __is_valid_slice(self, slice_name):
        """Validate the slice name based on the regexp used by the check script

        The slice name is either cXtXdXsX or cXdXsX
        For world wide name(MPXIO), disk is of the form
        cXtX[combination of alpha numeric characters]dXsX

        Returns: True if valid, False otherwise

        """
        if not SLICE1_PATTERN.match(slice_name):
            if not SLICE2_PATTERN.match(slice_name):
                return False
        return True

    @property
    def conversion_report(self):
        """Return the converstion report associated with this object"""
        return self._report

    def __invalid_syntax(self, line_num, keyword):
        """Generate invalid keyword error"""
        self.logger.error(_("%(file)s: line %(lineno)d: invalid syntax "
                            "for keyword '%(key)s' specified") % \
                            {"file": self.profile_name, \
                             "lineno": line_num, "key": keyword})
        self._report.add_process_error()

    def __unsupported_keyword(self, line_num, keyword, values):
        """Generate unsupported keyword error"""
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "keyword: %(key)s") % \
                            {"file": self.profile_name, "lineno": line_num, \
                             "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_value(self, line_num, keyword, value):
        """Generate unsupported value error"""
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported value "
                            "for '%(key)s' specified: %(val)s ") % \
                            {"file": self.profile_name, "lineno": line_num, \
                             "val": value, "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_syntax(self, line_num, keyword, msg):
        """Generate unsupported syntax error"""
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported syntax "
                            "for '%(key)s' specified: %(msg)s") % \
                            {"file": self.profile_name, "lineno": line_num, \
                             "key": keyword, "msg": msg})
        self._report.add_unsupported_item()

    def __fetch_pool(self, pool_name):
        """Retrieve the pool with the specified name if it exists.  If it does
        not exist create it with the specified name

        """
        target_device = None
        target = self._ai_instance_default.find(common.ELEMENT_TARGET)
        if target is not None:
            target_device = target.find(common.ELEMENT_TARGET_DEVICE)
            if target_device is not None:
                for zpool in target_device.findall(common.ELEMENT_ZPOOL):
                    if zpool.get(common.ATTRIBUTE_NAME, "") == pool_name:
                        return zpool
        if target is None:
            target = etree.Element(common.ELEMENT_TARGET)
            self._ai_instance_default.insert(0, target)
        if target_device is None:
            target_device = etree.SubElement(target,
                                             common.ELEMENT_TARGET_DEVICE)

        zpool = etree.SubElement(target_device, common.ELEMENT_ZPOOL)
        zpool.set(common.ATTRIBUTE_NAME, pool_name)
        return zpool

    def __root_pool_exists(self, line_num, keyword):
        """Check whether root pool has been created and generate error if the
        root pool already exists.  If exists adds a conversion error to report.
        Return True if exists, False otherwise

        """
        if self._root_pool is not None:
            # If the root pool already exists we reject the entry
            self.logger.error(_("%(file)s: line %(lineno)d: the ZFS root pool "
                                "was already created using the "
                                "'%(created_by)s' keyword, ignoring "
                                "'%(keyword)s' definition") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, \
                                 "keyword": keyword,
                                 "created_by":
                                 self._root_pool_create_via_keyword})
            self._report.add_conversion_error()
            return True
        return False

    def __create_root_pool(self, created_by_keyword,
                           pool_name=DEFAULT_POOL_NAME):
        """Tests to see if a root pool currently exists.  If it exists a
        the existing root pool is returned. If no root pool exists the
        pool will be created with the specified pool name.

        Arguments:
        created_by_keyword - the keyword to associate with the creation of
                   the root pool.  This will be used in the error generation
                   for root pool already exists messages
        pool_name - the name to assign to the root pool

        """
        if self._root_pool is not None:
            return self._root_pool

        target = self._ai_instance_default.find(common.ELEMENT_TARGET)
        if target is not None:
            target_device = target.find(common.ELEMENT_TARGET_DEVICE)
            if target_device is not None:
                xpath = "./zpool[@is_root='true']"
                zpool = fetch_xpath_node(self._tree, xpath)
                if zpool:
                    # If we found an existing root pool in our default profile
                    # delete it as we are now getting ready to overwrite it
                    target_device.remove(zpool)
        else:
            target_device = None

        if target is None:
            target = etree.Element(common.ELEMENT_TARGET)
            self._ai_instance_default.insert(0, target)
        if target_device is None:
            target_device = etree.SubElement(target,
                                             common.ELEMENT_TARGET_DEVICE)

        zpool = etree.SubElement(target_device, common.ELEMENT_ZPOOL)
        zpool.set(common.ATTRIBUTE_NAME, pool_name)

        self._root_pool = zpool
        self._root_pool.set(common.ATTRIBUTE_IS_ROOT, "true")
        self._root_pool_create_via_keyword = created_by_keyword
        return self._root_pool

    def __fetch_slice_node(self, disk, slice_name):
        """Returns the slice node with the name 'slice_name' that is a child of
           disk"""
        for disk_slice in disk.findall(common.ELEMENT_SLICE):
            if disk_slice.get(common.ATTRIBUTE_NAME, "") == slice_name:
                return disk_slice
        return None

    def __create_slice_node(self, disk, slice_name):
        """Create the slice node with the name 'slice_name'"""
        slice_node = etree.SubElement(disk, common.ELEMENT_SLICE)
        slice_node.set(common.ATTRIBUTE_NAME, slice_name)
        return slice_node

    def __fetch_diskname_node(self, vdev, disk_name):
        """Returns the diskname node with the name 'disk_name' that is a
        grandchild of vdev

        """
        disk = vdev.find(common.ELEMENT_DISK)
        if disk is None:
            return None
        for node in disk.findall(common.ELEMENT_DISK_NAME):
            if node.get(common.ATTRIBUTE_NAME, "") == disk_name:
                return node
        return None

    def __create_diskname_node(self, vdev, disk_name):
        """Create the diskname node with the name 'disk_name' that is
        a grandchild of vdev

        """
        disk = vdev.find(common.ELEMENT_DISK)
        if disk is None:
            disk = etree.SubElement(vdev, common.ELEMENT_DISK)
        node = etree.SubElement(disk, common.ELEMENT_DISK_NAME)
        node.set(common.ATTRIBUTE_NAME, disk_name)
        match_pattern = DISK1_PATTERN.match(disk_name)
        if match_pattern:
            disk_type = "ctd"
        else:
            disk_type = "cd"
        node.set(common.ATTRIBUTE_NAME_TYPE, disk_type)
        return node

    def __add_device(self, vdev, device):
        """Added device to the vdev xml hierachy"""
        try:
            disk, disk_slice = device.split("s")
        except ValueError:
            disk = device
            disk_slice = None
        disk_node = self.__fetch_diskname_node(vdev, disk)
        if disk_node is None:
            disk_node = self.__create_diskname_node(vdev, disk)
        # TODO: Target code for disk and slice is changing.  For now
        # comment this out, till this is finalized.
        #if disk_slice is not None:
        #    slice_node = self.__fetch_slice_node(disk_node, disk_slice)
        #    if slice_node is None:
        #        slice_node = self.__create_slice_node(disk_node, disk_slice)
        return disk_node

    def __add_software_data(self, line_num, package, action):
        """Create a <name>$package</name> node and add it to the existing
        <software_data> node for the specified action.  If the node does not
        exist, create it and add it as a child of the specified parent node.

        Arguments:
        line_num - the line # that in the file that is being processed
        package - the name of the package element to add as a
            <name>$package</name> child node of <software_data>
        action - install or uninstall the package

        """
        orig_pwd = os.getcwd()
        api_inst = api.ImageInterface("/", CLIENT_API_VERSION, None, \
            None, "js2ai")
        pkg_query = ":legacy:legacy_pkg:" + package
        query = [api.Query(pkg_query, False, True)]
        gettext.install("pkg", "/usr/share/locale")
        search_remote = api_inst.remote_search(query, servers=None, \
             prune_versions=True)
        search_local = api_inst.local_search(query)
        pkg_name = None
        # Remote search is the default since this will often have a more
        # complete package catalog than that on an installed system.
        if not self._local:
            try:
                pkg_name = self.__do_pkg_search(search_remote, line_num)
            except Exception:
                # setting local so we'll retry with the local search
                self._local = True
                pkg_name = None
            if pkg_name != None:
                package = pkg_name

        if self._local and not pkg_name:
            try:
                pkg_name = self.__do_pkg_search(search_local, line_num)
            except Exception, msg:
                self.logger.error(_("%(file)s: line %(lineno)d: package name "
                                    "translation failed for '%(packge)s'"
                                    ": %(message)s") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num, "package": package, \
                                     "message": msg})
                self._report.add_conversion_error()
            if pkg_name != None:
                package = pkg_name

        # Because the pkg api call can change the working directory we need to
        # set it back to it's original directory.
        os.chdir(orig_pwd)

        software = self._ai_instance_default.find(common.ELEMENT_SOFTWARE)
        if software is None:
            software = etree.SubElement(self._ai_instance_default,
                                        common.ELEMENT_SOFTWARE)
        if pkg_name not in ["SUNWcs", "SUNWcsd"]:
            package = "pkg:/" + package
        xpath = "./software_data[@action='%s'][@type='IPS']"
        software_uninstall = fetch_xpath_node(software,
                                              xpath % SOFTWARE_UNINSTALL)
        software_install = fetch_xpath_node(software,
                                            xpath % SOFTWARE_INSTALL)

        # If we are doing an install and the package is listed as
        # in the uninstall list we want to remove it.  Vic version if we
        # are doing an uninstall
        if action == SOFTWARE_INSTALL:
            search = software_uninstall
        else:
            search = software_install

        if search is not None:
            match_node = None
            for child in search:
                if child.text == package:
                    # Found an entry
                    match_node = child
                    break
            if match_node is not None:
                # Remove the entry we found
                search.remove(match_node)

        if action == SOFTWARE_INSTALL:
            software_data = software_install
        else:
            software_data = software_uninstall

        if software_data is None:
            software_data = etree.SubElement(software,
                                             common.ELEMENT_SOFTWARE_DATA,
                                             action=action,
                                             type="IPS")

        name = etree.SubElement(software_data, common.ELEMENT_NAME)
        name.text = package

    def __do_pkg_search(self, search, line_num):
        """Grab the new package name returned from the ipkg search"""
        pkg_name = None
        search_values = itertools.chain(search)
        if search_values is not None:
            try:
                for raw_value in search_values:
                    query_num, pub, (value, return_type, pkg_info) = raw_value
                    pfmri = pkg_info[0]
                    pkg_name = pfmri.get_name()
                    # We ignore SUNWcs and SUNWcsd since these are system
                    # packages that can show up in the query due to
                    # dependecies.
                    if pkg_name in ["SUNWcs", "SUNWcsd"]:
                        continue
                    if pkg_name != None:
                        self.inst_type = "ips"
                        return pkg_name
            except apx.SlowSearchUsed, msg:
                self.logger.warning(
                    _("%(file)s: line %(lineno)d: WARNING: package "
                      "name lookup returned error: %(message)s") % \
                      {"file": self.profile_name, "lineno": line_num, \
                       "message": msg})
        return pkg_name

    def __rootdisk_disk_conflict_check(self, disk):
        """Checks the specified disk to see if it conflicts with the
        root_device or boot_device settings that may have been specified
        by the profile.  Returns True if conflict found, false otherwise

        """
        if self._rootdisk is None:
            return False
        if self._root_device is not None:
            # root_disk is slice based, convert to disk for comparison
            # Currently _rootdisk = _root_device
            cmp_disk = self.__device_name_conversion(self._rootdisk)
        else:
            # boot_disk is already in the correct form
            # Currently _rootdisk = _boot_device
            cmp_disk = self._rootdisk
        if cmp_disk != disk:
            return True
        return False

    def __rootdisk_slice_conflict_check(self, disk_slice):
        """Checks the specified slice to see if it conflicts with the
        root_device or boot_device settings that may have been specified
        by the profile.  Returns True if conflict found, false otherwise

        """
        if self._rootdisk is None:
            return False
        if self._root_device is not None:
            # Both root_disk and are slice are have the same format
            # a direct comparision should be performed
            cmp_device = disk_slice
        else:
            # root_disk wasn't set but boot_device was so our comparision
            # has to be made at the disk level instead of the slice level
            cmp_device = self.__device_name_conversion(disk_slice)
        if cmp_device != self._rootdisk:
            return True
        return False

    def __rootdisk_device_conversion(self, device, line_num):
        """Checks the device for the present of 'rootdisk."  if found
        and the root disk has been determined the 'rootdisk.' will be
        replaced with the name of the root disk

        """
        if device.startswith("rootdisk."):
            # We can only support the rootdisk keyword if
            # root_device, boot_device, pool, or  filesys /
            # has been specified in the profile
            # If filesys / is used then it must proceed rootdisk usage
            # in order for this substitution to suceed
            if self._rootdisk is None:
                self.logger.error(_("%(file)s: line %(linenum)d: "
                    "unsupported syntax: '%(device)s' is only "
                    "supported if root_device or boot_disk was "
                    "defined in profile") % \
                    {"file": self.profile_name,
                    "linenum": line_num,
                    "device": device})
                self._report.add_unsupported_item()
                return None
            # The root device specification has a slice associated with it
            # we need to strip this off before we substitute "rootdisk."
            # with it
            disk = self.__device_name_conversion(self._rootdisk)
            device = device.replace("rootdisk.", disk, 1)
        return device

    def __convert_fdisk_entry(self, line_num, keyword, values):
        """Converts the fdisk keyword/values from the profile into the
        new xml format

        """

        # fdisk <diskname> <type> <size>
        if len(values) != 3:
            self.__invalid_syntax(line_num, keyword)
            return

        # check <diskname> syntax
        # valid values:         rootdisk
        #                       all
        #                       cx[ty]dz
        disk_name = values[0].lower()
        if disk_name == "all":
            self.__unsupported_value(line_num, _("<diskname>"), "all")
            return

        disk_name = self.__rootdisk_device_conversion(disk_name, line_num)
        if disk_name is None:
            return

        if not self.__is_valid_device_name(disk_name):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "device specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "device": values[0]})
            self._report.add_conversion_error()
            return

        # check <type> syntax
        # valid values:         solaris
        #                       dosprimary
        #                       x86boot
        #                       ###
        fdisk_type = values[1]
        if fdisk_type != "solaris":
            self.__unsupported_value(line_num, _("<type>"), fdisk_type)
            return

        # check <size> syntax for non-x86boot partitions
        # valid values:         all
        #                       delete
        #                       maxfree
        #                       ###
        size = values[2].lower()
        if size not in ["all", "maxfree", "delete"]:
            match_pattern = NUM_PATTERN.match(size)
            if not match_pattern:
                self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                    "fdisk <size> specified: %(size)s") % \
                                    {"file": self.profile_name,
                                     "line_num": line_num,
                                     "size": size})
                self._report.add_conversion_error()
                return

        if self.__root_pool_exists(line_num, keyword):
            return

        if self._rootdisk is not None:
            # fdisk will be in the form cx[ty]dz
            if self.__rootdisk_disk_conflict_check(disk_name):
                # If we have a conflict we don't override root_disk or
                # boot_disk setting.  Those setting have priority over
                # fdisk
                self.logger.error(_("%(file)s: line %(lineno)d: conflicting "
                                    "ZFS root pool definition: "
                                    "'%(rd_kw)s=%(rootdisk)s', ignoring "
                                    "fdisk entry") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "rd_kw": self._rootdisk_set_by_keyword,
                                     "rootdisk": self._rootdisk})
                self._report.add_conversion_error()
                return

        zpool = self.__create_root_pool(keyword)
        vdev = etree.SubElement(zpool, common.ELEMENT_VDEV)

        disk = self.__add_device(vdev, disk_name)
        partition = etree.SubElement(disk, common.ELEMENT_PARTITION)
        partition.set(common.ATTRIBUTE_NAME, "1")
        if size == "delete" or size == "0":
            partition.set(common.ATTRIBUTE_ACTION, "delete")
            return

        partition.set(common.ATTRIBUTE_ACTION, "create")

        if size not in ["all", "maxfree"]:
            # the fdisk size specified is in Mbytes
            size_node = etree.SubElement(partition, common.ELEMENT_SIZE)
            size_node.set(common.ATTRIBUTE_VAL, size + "mb")

    def __convert_filesystem_entry(self, line_num, keyword, values):
        """Converts the filesystem keyword/values from the profile into
        the new xml format

        """
        # filesys                 any 60 swap
        # filesys                 s_ref:/usr/share/man - /usr/share/man ro
        # filesys                 s_ref:/usr/openwin/share/man -  \
        #                             /usr/openwin/share/man ro,quota
        #                           /usr/openwin/share/man ro,quota
        # filesys                 rootdisk.s0 6144  /
        # filesys                 rootdisk.s1 1024  swap

        # Use the regex pattern '..*:/..*' to determine the # of expressions
        # we have.   If the count greater than 0 then this is a remote
        # filesystem, otherwise we have a local filesystem
        if FILESYSTEM_ARG_PATTERN.match(values[0]):
            # Remote Filesystem supports 3-4 args
            #
            #       filesys <remote> <ip_addr>|"-" [ <mount> ] [ <mntopts> ]
            #
            # Currently not support remote filesystem so reject entire entry
            self.__unsupported_syntax(line_num, keyword,
                _("remote filesystem are not supported"))
            return

        # We've got a local file system.

        # Invalidate anything with too many or too little args
        length = len(values)
        if length == 1 or length > 6:
            self.__invalid_syntax(line_num, keyword)
            return
        #
        # filesys
        #    [<mirror:[name]>] <device> [<device>] [<size> <mount>] [<mntopts>]
        #
        # filesys <device> <size> [ <mount> [ <fsoptions> ] ]
        #                                   [ preserve [ <mntopts> ]
        #                                   [ <mntopts> ]
        #
        mirror = False
        if values[0].startswith("mirror"):
            if length < 4:
                self.__invalid_syntax(line_num, keyword)
                return
            mirror_name = values[0]
            device1 = values[1]
            device2 = self.__rootdisk_device_conversion(values[2], line_num)
            if device2 is None:
                return
            if device2 == "any":
                self.__unsupported_value(line_num, _("<device>"), "any")
                return
            if not self.__is_valid_slice(device2):
                # 2nd parameter is not a disk.  Therefore mark it
                # as unsupported
                self.logger.error(_("%(file)s: line %(linenum)d: invalid"
                                   " slice specified: %(device)s ") % \
                                   {"file": self.profile_name,
                                   "linenum": line_num,
                                   "device": device2})
                self._report.add_conversion_error()
                return
            # Size is currently not used
            # size = values[3]
            if length >= 5:
                mount = values[4]
            else:
                # From the Solaris 10 jumpstart documentation
                # If file_system is not specified, unnamed is set by default
                mount = "unamed"
            mirror = True
        else:
            if length < 2:
                self.__invalid_syntax(line_num, keyword)
                return
            device1 = values[0]
            device2 = None
            # size = values[1]
            if length >= 3:
                mount = values[2]
            else:
                # From the Solaris 10 jumpstart documentation
                # If file_system is not specified, unnamed is set by default
                mount = "unamed"

        if mount != "/":
            # We reject everything except for '/'
            self.__unsupported_syntax(line_num, keyword,
                _("filesystems mount points other than '/' are not supported"))
            return

        device1 = self.__rootdisk_device_conversion(device1, line_num)
        if device1 is None:
            return

        if device1 == "any":
            self.__unsupported_value(line_num, _("<device>"), "any")
            return
        if not self.__is_valid_slice(device1):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "slice specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, \
                                 "device": device1})
            self._report.add_conversion_error()
            return

        if self.__root_pool_exists(line_num, keyword):
            return

        # If we have a mirror check to make sure 2 devices have been
        # specified and that those diffices are unique.  All other mirror
        # types are not supported
        if mirror:
            if device1 == device2:
                self.__unsupported_syntax(line_num, keyword,
                    _("mirror devices are not unique"))
                return
            if self._rootdisk is not None:
                # We've got a condition like
                #
                # root_device cxtxdxs1
                # filesys mirror c1t0d0s0 c1t0d0s2 all /
                #
                # A mirror has two disks so if root device is defined there's
                # going to be a conflict no matter what.
                #
                self.logger.error(_("%(file)s: line %(lineno)d: conflicting "
                                    "ZFS root pool definition: filesys / "
                                    "mirrored definition will be used instead"
                                    " of '%(rd_kw)s=%(rootdisk)s'") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "rd_kw": self._rootdisk_set_by_keyword,
                                     "rootdisk": self._rootdisk})
                self._report.add_conversion_error()

            if mirror_name != "mirror":
                try:
                    mirror, pool_name = values[0].split(":")
                except ValueError:
                    self.__invalid_syntax(line_num, keyword)
                    return
        elif self._rootdisk is not None:
            # We got a condition like
            #
            # root_device cxtxdxsx
            # filesys cxtxdxsx 20 /
            #
            # or
            #
            # boot_device cxtxdx
            # filesys cxtxdxsx 20 /
            #
            # Check for conflicts
            #
            if self.__rootdisk_slice_conflict_check(device1):
                self.logger.error(_("%(file)s: line %(lineno)d: conflicting "
                                    "ZFS root pool definition: filesys keyword"
                                    " device definition of '%(device)s' "
                                    "will be used instead of '%(rd_kw)s="
                                    "%(rootdisk)s'") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "device": device1,
                                     "rd_kw": self._rootdisk_set_by_keyword,
                                     "rootdisk": self._rootdisk})
                self._report.add_conversion_error()
            else:
                # Update the device1 with the rootdisk setting
                # If the user used root_device this will refine the ZFS
                # root pool so it agrees with that setting too
                # This would be equivalent to us processing the root_device
                # line and adding the slice entry to the pool
                device1 = self._rootdisk

        zpool = self.__create_root_pool(keyword)
        vdev = zpool.find(common.ELEMENT_VDEV)
        if vdev is None:
            vdev = etree.SubElement(zpool, common.ELEMENT_VDEV)

        self.__add_device(vdev, device1)

        if mirror:
            vdev.set(common.ATTRIBUTE_REDUNDANCY, "mirror")
            self.__add_device(vdev, device2)
        elif self._rootdisk is None:
            # How JumpStart Determines a System's Root Disk
            # 3. If rootdisk is not set and a filesys cwtxdysz size / entry is
            #    specified in the profile, the JumpStart program sets rootdisk
            #    to the disk that is specified in the entry.
            self._root_device = device1
            self._rootdisk = self._root_device
            self._rootdisk_set_by_keyword = keyword

    def __convert_install_type_entry(self, line_num, keyword, values):
        """Converts the filesystem keyword/values from the profile into
        the new xml format

        """
        # We've check the install type up front so there's nothing to do here
        pass

    def __convert_package_entry(self, line_num, keyword, values):
        """Converts the package keyword/values from the profile into
        the new xml format

        """
        # Input:        package <package_name> <add|delete> <arg1> <arg2> ...

        package = values[0]
        if len(values) == 2:
            action = values[1].lower()
        elif len(values) < 2:
            action = "add"
        else:
            # If the remote (nfs or http) or local (local_device or local_file)
            # directory option is used we can't support this entry. Log it
            # and return.
            self.__unsupported_syntax(line_num, keyword,
                _("package install from specified locations is not supported "
                "for SVR4 packages"))
            return
        if (action != "add" and action != "delete"):
            self.__invalid_syntax(line_num, keyword)
            return
        if action == "add":
            self.__add_software_data(line_num,
                                     package,
                                     SOFTWARE_INSTALL)
        elif action == "delete":
            self.__add_software_data(line_num,
                                     package,
                                     SOFTWARE_UNINSTALL)

    def __convert_pool_entry(self, line_num, keyword, values):
        """Converts the partition keyword/values from the profile into
        the new xml format

        """
        # pool <pool name> <pool size> <swap size> <dump size>
        #                                       <slice> | mirror [<slice>]+
        #
        # Input:        ${1}    - pool name
        #               ${2}    - pool size (num, all, auto)
        #               ${3}    - swap size (num, auto)
        #               ${4}    - dump size (num, auto)
        #               ${5}    - (mirror, <slice>, rootdisk.s??, any)
        #                .      - (<slice>, rootdisk.s??, any)
        length = len(values)
        if length < 5:
            self.__invalid_syntax(line_num, keyword)
            return

        pool_name = values[0]
        # Pool name must be between 0-30 characters
        name_length = len(pool_name)
        if name_length == 0 or name_length > 30:
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "pool name of '%(pool)s': must be at least 1 "
                                "character and no more than 30 characters "
                                "in length") % \
                                {"file": self.profile_name, "lineno": line_num,
                                "pool": pool_name})
            self._report.add_conversion_error()
            return

        pool_size = values[1].lower()
        match_pattern = SIZE_PATTERN.match(pool_size)
        if match_pattern:
            if match_pattern.group(2) == "":
                # No size specified.  Default size is assumed to be in MB
                pool_size += "mb"
        elif pool_size not in ["auto", "all"]:
            # Validate the size
            if not SIZE_PATTERN.match(pool_size):
                self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                    "size '%(val)s' specified for pool") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "val": values[1]})
                self._report.add_conversion_error()
                return

        swap_size = values[2].lower()
        match_pattern = SIZE_PATTERN.match(swap_size)
        if match_pattern:
            if match_pattern.group(2) == "":
                # No size specified.  Default size is assumed to be in MB
                swap_size += "mb"
        elif swap_size != "auto":
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "size '%(val)s' specified for swap") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, \
                                 "val": values[2]})
            self._report.add_conversion_error()
            return

        dump_size = values[3].lower()
        match_pattern = SIZE_PATTERN.match(dump_size)
        if match_pattern:
            if match_pattern.group(2) == "":
                # No size specified.  Default size is assumed to be in MB
                dump_size += "mb"
        elif dump_size != "auto":
            self.logger.error(_("%(file)s: line %(lineno)d: invalid size "
                                "'%(val)s' specified for dump") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, "val": values[3]})
            self._report.add_conversion_error()
            return

        if values[4] == "mirror":
            # Mirror must have at least 2 slices
            mirror = True
            if length < 6:
                self.__invalid_syntax(line_num, keyword)
                return
            devices = values[5:]
        else:
            mirror = False

            # Non mirror can only have 1 slice specified
            if length > 5:
                self.__invalid_syntax(line_num, keyword)
                return
            devices = values[4:]

        # If mirror == False then there is only 1 device
        for device in devices:
            if device == "any":
                if not mirror:
                    if self._rootdisk is not None:
                        # NOTE: we don't do this check earlier since
                        # rootdisk could be the value held in boot_device
                        # which isn't sliced based and if we subsituted this
                        # and then tried to process it we'd fail the slice
                        # check that occurs below
                        devices[0] = self._rootdisk
                        continue
                    self.logger.error(_("%(file)s: line %(lineno)d: "
                                        "unsupported pool definition, the "
                                        "device 'any' can not be converted to "
                                        "a physical device. The installer by "
                                        "default will automatically create "
                                        "the root pool based on the devices "
                                        "it finds. ") % \
                                        {"file": self.profile_name, \
                                         "lineno": line_num})
                    self._report.add_unsupported_item()
                else:
                    self.logger.error(_("%(file)s: line %(lineno)d: "
                                        "use of the device entry 'any' is not "
                                        "supported when a mirrored pool is "
                                        "specified") % \
                                        {"file": self.profile_name, \
                                         "lineno": line_num})
                    self._report.add_unsupported_item()
                return

            device = self.__rootdisk_device_conversion(device, line_num)
            if not self.__is_valid_slice(device):
                self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                    "slice specified: %(device)s") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num, \
                                     "device": device})
                self._report.add_conversion_error()
                return

        # Check for any conflicts with root_device and boot_device
        # pool will always override these settings
        if mirror and self._rootdisk is not None:
            # We've got a conditions like
            #
            # root_device cxtxdxs1
            # pool newpool auto auto auto mirror cxtxdxs0 cxtxdxs1
            #
            # A mirror has two disks so if root device is defined there's
            # going to be a conflict no matter what.
            #
            self.logger.error(_("%(file)s: line %(lineno)d: conflicting "
                                "ZFS root pool definition: mirrored pool "
                                "definition will be used instead of "
                                "'%(rd_kw)s=%(rootdisk)s'") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "rd_kw": self._rootdisk_set_by_keyword,
                                 "rootdisk": self._rootdisk})
            self._report.add_conversion_error()
        else:
            # We've got a condition like
            #
            # root_device cxtxdxsx
            # pool p_abc auto auto auto cxtxdxsx
            #
            # or
            #
            # boot_device cxtxdx
            # pool p_abc auto auto auto cxtxdxsx
            #
            if self.__rootdisk_slice_conflict_check(devices[0]):
                self.logger.error(_("%(file)s: line %(lineno)d: "
                                    "conflicting ZFS root pool definition: "
                                    "pool keyword device definition of "
                                    "'%(device)s' will be used instead of "
                                    "'%(rd_kw)s=%(rootdisk)s'") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "device": devices[0],
                                     "rd_kw":
                                     self._rootdisk_set_by_keyword,
                                     "rootdisk": self._rootdisk})
                self._report.add_conversion_error()

        zpool = self.__create_root_pool(keyword, pool_name)
        vdev = etree.SubElement(zpool, common.ELEMENT_VDEV)
        if mirror:
            vdev.set(common.ATTRIBUTE_REDUNDANCY, "mirror")

        for device in devices:
            self.__add_device(vdev, device)

        target = self._ai_instance_default.find(common.ELEMENT_TARGET)
        # No need to check for None on target since we know it's there
        # since create_root_pool would of created it if it didn't exist
        swap = etree.SubElement(target, common.ELEMENT_SWAP)
        zvol = etree.SubElement(swap, common.ELEMENT_ZVOL)
        zvol.set(common.ATTRIBUTE_ACTION, "create")
        zvol.set(common.ATTRIBUTE_NAME, "swap")
        if swap_size != "auto":
            size = etree.SubElement(zvol, common.ELEMENT_SIZE)
            size.set(common.ATTRIBUTE_VAL, swap_size)

        dump = etree.SubElement(target, common.ELEMENT_DUMP)
        zvol = etree.SubElement(dump, common.ELEMENT_ZVOL)
        zvol.set(common.ATTRIBUTE_ACTION, "create")
        zvol.set(common.ATTRIBUTE_NAME, "dump")
        if dump_size != "auto":
            size = etree.SubElement(zvol, common.ELEMENT_SIZE)
            size.set(common.ATTRIBUTE_VAL, dump_size)
        if not mirror:
            if self._rootdisk is None:
                # Based on how we process things the pool keyword is where
                # we don't follow the basic steps of "How JumpStart Determines"
                # " a System's Root Disk (Initial Installation)"
                #
                # Since rootdisk has not been set via root_disk or boot_device
                # we now want to use the device specified by pool as our
                # root_device.
                self._root_device = devices[0]
                self._rootdisk = self._root_device
                self._rootdisk_set_by_keyword = keyword

    def __store_boot_device_entry(self, line_num, keyword, values):
        """Converts the boot device keyword/values from the profile into the
        new xml format
        """

        # The supported syntax in Solaris 10 was
        #
        # boot_device <device> <eeprom>
        # valid values:
        #       <device>:
        #                       c#[t#]d#s# - SPARC
        #                       c#[t#]d#   - X86
        #                       existing
        #                       any
        #       <eeprom>:
        #                       preserve
        #                       update
        #
        if self._boot_device is not None:
            self.__duplicate_keyword(line_num, keyword, values)
            return
        length = len(values)
        if length > 2 or length == 0:
            self.__invalid_syntax(line_num, keyword)
            return

        device = values[0].lower()
        if device == "any" or device == "existing":
            self.__unsupported_value(line_num, _("<device>"), device)
            return

        if not self.__is_valid_device_name(device) and \
           not self.__is_valid_slice(device):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid device "
                                "specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, \
                                 "device": device})
            self._report.add_conversion_error()
            return

        if length == 2:
            eeprom = values[1].lower()
            if eeprom == "preserve":
                # No action since this says keep it as is
                pass
            elif eeprom == "update":
                # Technically only the preserve value is supported
                # on x86 but since we are ignoring the update value
                # this message is sufficient
                self.logger.error(_("%(file)s: line %(lineno)d: ignoring "
                                    "eeprom 'update' setting, as this action "
                                    "is not supported") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num})
                self._report.add_conversion_error()
            else:
                self.__invalid_syntax(line_num, keyword)
                return
        if self._root_device is not None:
            # If we follow how jumpstart determines which disk to use for
            # the root disk the root_device keyword has a higher priority
            # than the boot_device keyword.  If the devices specified
            # are different then flag it as a conflict, but use root_device
            # defintion.
            #
            # root_device c1t0d0s1
            # boot_device c0t0d0 update

            cmp_device = self.__device_name_conversion(self._root_device)
            if cmp_device != device:
                self.logger.error(_("%(file)s: line %(lineno)d: conflicting "
                                    "definition: root_device previously "
                                    "defined as '%(root_device)s', ignoring "
                                    "boot_device entry '%(boot_device)s'") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "root_device": self._root_device,
                                     "boot_device": device})
                self._report.add_conversion_error()
                return
        else:
            self._rootdisk = device
            self._rootdisk_set_by_keyword = keyword
        self._boot_device = device

    def  __store_root_device_entry(self, line_num, keyword, values):
        """Set the profile rootdevice value that we'll use if rootdevice
        is specified by the user

        """
        # root_device <slice>
        if self._root_device is not None:
            self.__duplicate_keyword(line_num, keyword, values)
            return
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        if not self.__is_valid_slice(values[0]):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "device specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "device": values[0]})
            self._report.add_conversion_error()
            return

        self._root_device = values[0]
        if self._boot_device is not None:
            # Do we have a conflict?
            cmp_device = self.__device_name_conversion(self._root_device)
            if self._root_device != cmp_device:
                self.logger.error(_("%(file)s: line %(lineno)d: translation "
                                    "conflict between devices specified for "
                                    "boot_device and root_device, using "
                                    "root_device define of '%(root_device)s', "
                                    "ignoring define of boot_device "
                                    "of '%(boot_device)s'") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num,
                                     "root_device": self._root_device,
                                     "boot_device": self._boot_device})
                self._report.add_conversion_error()
        self._rootdisk = self._root_device
        self._rootdisk_set_by_keyword = keyword

    def __convert_usedisk_entry(self, line_num, keyword, values):
        """Converts the usedisk keyword/values from the profile into
        the new xml format

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        if self.__is_valid_device_name(values[0]):
            if self._root_device == None:
                # Storing this in root_device for use if and only if no
                # other disk related jumpstart keywords are used in the
                # profile. Only the first instance of the usedisk keyword
                # will be used in this way.
                self._root_device = values[0]
                self.__unsupported_keyword(line_num, keyword, values)
            else:
                self.__unsupported_keyword(line_num, keyword, values)
        else:
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "device specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "device": values[0]})
            self._report.add_conversion_error()

    def __is_valid_install_type(self, line_num, keyword, values):
        """The only profiles that are supported are install profiles
        The jumpstart scripts require it as the first keyword in the
        file.  If the install_type is not initial_install reject
        the entire profile

        """
        if keyword != "install_type":
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "profile, first  specified "
                                "keyword must be install_type, "
                                "got '%(keyword)s'") % \
                                {"file": self.profile_name,
                                 "lineno": line_num,
                                 "keyword": keyword})
            self._report.add_process_error()
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            self._root = None
            return False
        install_type = values[0].lower()
        if install_type in ["upgrade",
                            "flash_install", "flash_upgrade"]:
            self.__unsupported_value(line_num, keyword, values[0])
            self._report.conversion_errors = None
            self._root = None
            return False
        if install_type != "initial_install":
            self.__invalid_syntax(line_num, keyword)
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            self._root = None
            return False
        return True

    profile_conversion_dict = {
        "boot_device": None,
        "bootenv": __unsupported_keyword,
        "client_arch": __unsupported_keyword,
        "client_swap": __unsupported_keyword,
        "cluster": __unsupported_keyword,
        "dontuse": __unsupported_keyword,
        "fdisk": __convert_fdisk_entry,
        "filesys": __convert_filesystem_entry,
        "geo": __unsupported_keyword,
        "install_type": __convert_install_type_entry,
        "locale": __unsupported_keyword,
        "num_clients": __unsupported_keyword,
        "package": __convert_package_entry,
        "partitioning": __unsupported_keyword,
        "pool": __convert_pool_entry,
        "root_device": None,
        "system_type": __unsupported_keyword,
        "usedisk": __convert_usedisk_entry,
        }

    @property
    def tree(self):
        """Returns the xml tree associated with this object"""
        return self._tree

    def __process_profile(self):
        """Process the profile by taking all keyword/values pairs and
        generating the associated xml for the key value pairs

        """
        if self.prof_dict is None:
            # There's nothing to convert.  This is a valid condition if
            # the file couldn't of been read for example
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            return

        xpath = "/auto_install/ai_instance[@name='default']"
        self._ai_instance_default = fetch_xpath_node(self._tree, xpath)

        if self._ai_instance_default is None:
            tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
            expected_layout = etree.tostring(tree, pretty_print=True,
                        encoding="UTF-8")
            raise ValueError(_("Specified default xml file does not conform to"
                               " the expected layout of:\n%(layout)s") %
                               {"layout": expected_layout})

        check_for_install_type = True
        pool_obj = None
        # Sort the keys based on the line #
        keys = sorted(self.prof_dict.keys())
        #
        # The keywords for the profile are processed in 3 different phases.
        #
        # Phase  Actions Performed
        # -----  -------------------------------------------------------------
        #   1    o Check to ensure that "install_type" is the first keyword
        #          in the profile.
        #        o Check the entire profile for "root_device" and "boot_device"
        #          keywords for the generation of the "rootdisk".  This
        #          duplicates the first 2 steps that Jumpstart does when it
        #          determines what disk to use for the System's Root Disk
        #   2    o Process the pool keyword.  If used this is the closest
        #          parallel to how the new installer uses so we give this
        #          the highest priority in what we use to generate the ZFS
        #          root pool
        #   3    o Process the remaining keywords in the profile
        #
        for key in keys:
            key_value_obj = self.prof_dict[key]
            if key_value_obj is None:
                raise ValueError

            keyword = key_value_obj.key
            values = key_value_obj.values
            line_num = key_value_obj.line_num

            if line_num is None or values is None or keyword is None:
                raise ValueError

            if check_for_install_type:
                # The 1st keyword in the profile must be install_type,
                # if it's not we reject the profile
                if not self.__is_valid_install_type(line_num, keyword, values):
                    return
                del self.prof_dict[key]
                check_for_install_type = False
            #
            # Scan all the keyword for root_device and boot_device
            # These keywords are special since they allow us to emulate
            # the initial 2 stages in the process of
            #       How JumpStart Determines a System's Root Disk
            #
            # 1. If the root_device keyword is specified in the profile, the
            #    JumpStart program sets rootdisk to the root device.
            # 2. If rootdisk is not set and the boot_device keyword is
            #    specified in the profile, the JumpStart program sets rootdisk
            #    to the boot device.
            if keyword == "root_device":
                self.__store_root_device_entry(line_num, keyword, values)
                del self.prof_dict[key]
            elif keyword == "boot_device":
                self.__store_boot_device_entry(line_num, keyword, values)
                del self.prof_dict[key]
            elif keyword == "pool":
                del self.prof_dict[key]
                if pool_obj is not None:
                    self.__duplicate_keyword(line_num, keyword, values)
                else:
                    pool_obj = key_value_obj

        # Next create the zfs pool if the pool keyword was encountered
        # With the new installer we only support creating a single zfs
        # root pool.  The pool keyword takes precidence over any other
        # settings the user may have made
        if pool_obj is not None:
            self.__convert_pool_entry(pool_obj.line_num, pool_obj.key,
                                     pool_obj.values)

        # Now process the remaining keys
        keys = sorted(self.prof_dict.keys())
        for key in keys:
            key_value_obj = self.prof_dict[key]
            keyword = key_value_obj.key.lower()
            values = key_value_obj.values
            line_num = key_value_obj.line_num
            try:
                function_to_call = self.profile_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(line_num, keyword, values)
            else:
                if function_to_call is not None:
                    function_to_call(self, line_num, keyword, values)

        # If the user specified a root_device or boot_disk but didn't create a
        # root pool via filesys, fdisk or pool create one now and add the
        # specified root_device as that disk for that pool
        if self._rootdisk and self._root_pool is None:
            zpool = self.__create_root_pool(self._rootdisk_set_by_keyword,
                                            DEFAULT_POOL_NAME)
            if zpool is not None:
                vdev = zpool.find(common.ELEMENT_VDEV)
                if vdev is None:
                    vdev = etree.SubElement(zpool, common.ELEMENT_VDEV)

                self.__add_device(vdev, self._rootdisk)

        # Check to determine if we have any children nodes
        # If we don't and we have errors then clear the xml
        # tree so we don't have a empty tree hierachy that
        # results in a <auto_install/>
        # Conversely though if all that's in the file is
        # initial_install and we have no errors then we should
        # create a file even if it's just <auto_install/>
        # That technically won't have any meaning to the new jumpstart
        # engine though
        children = list(self._root)
        if not children and self._report.has_errors():
            self._root = None

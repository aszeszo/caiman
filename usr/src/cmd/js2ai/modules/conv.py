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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

import gettext
import itertools
import logging
import re
import sys

import pkg.client.api as api
import pkg.client.api_errors as apx
import pkg.client.image as image
import os

from common import KeyValues
from common import ConversionReport
from lxml import etree

# This is defined here since we can't collect this information from the
# pkg api. This is needed to make the calls into the pkg api.
CLIENT_API_VERSION = 46

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

ELEMENT_AI_CRITERIA = "ai_criteria"
ELEMENT_AI_CRITERIA_MANIFEST = "ai_criteria_manifest"
ELEMENT_AI_DEVICE_PARTITIONING = "ai_device_partition"
ELEMENT_AUTO_INSTALL = "auto_install"
ELEMENT_DISK = "disk"
ELEMENT_DISK_NAME = "disk_name"
ELEMENT_DUMP = "dump"
ELEMENT_NAME = "name"
ELEMENT_PARTITION = "partition"
ELEMENT_RANGE = "range"
ELEMENT_SIZE = "size"
ELEMENT_SOFTWARE_DATA = "software_data"
ELEMENT_SWAP = "swap"
ELEMENT_TARGET = "target"
ELEMENT_TARGET_DEVICE = "target_device"
ELEMENT_VALUE = "value"
ELEMENT_VDEV = "vdev"
ELEMENT_ZPOOL = "zpool"
ELEMENT_ZVOL = "zvol"

ATTRIBUTE_ACTION = "action"
ATTRIBUTE_IS_ROOT = "is_root"
ATTRIBUTE_NAME = "name"
ATTRIBUTE_NAME_TYPE = "name_type"
ATTRIBUTE_REDUNDANCY = "redundancy"
ATTRIBUTE_TYPE = "type"
ATTRIBUTE_VAL = "val"

DEFAULT_POOL_NAME = "rpool"

# Follow the same name scheme used for mirror pools using the old jumpstart
# scripts.  When not specified mirror names start with the letter "d" followed
# by a number between 0 and 127
DEFAULT_MIRROR_POOL_NAME = "d"

_ = gettext.translation("js2ai", "/usr/share/locale",
                        fallback=True).gettext


class XMLRuleData(object):

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
        return self._report

    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, newroot):
        self._root = newroot

    def __unsupported_keyword(self, line_num, keyword, values):
        self.logger.error(_("rules: line %(lineno)d: unsupported "
                            "keyword: %(key)s") % \
                            {"lineno": line_num, \
                             "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_negation(self, line_num):
        self.logger.error(_("rules: line %(lineno)d: negation "
                            "'!' not supported in manifests") % \
                            {"lineno": line_num})
        self._report.add_unsupported_item()

    def __invalid_syntax(self, line_num, keyword):
        self.logger.error(_("rules: line %(lineno)d: invalid syntax for "
                            "keyword '%(key)s' specified") % \
                            {"lineno": line_num, "key": keyword})
        self._report.add_process_error()

    def __convert_common(self, line_num, keyword, values):
        """Converts the specified keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self.root, ELEMENT_AI_CRITERIA)
        try:
            criteria_name.set(ATTRIBUTE_NAME,
                              self.rule_keywd_conv_dict[keyword])
        except KeyError:
            self.__unsupported_keyword(line_num, keyword, values)
            # since we've already added an element to the tree we need to
            # cleanup that element due to the exception.
            self.root.remove(criteria_name)
            return
        crit_value = etree.SubElement(criteria_name, ELEMENT_VALUE)
        crit_value.text = values[0]

    def __convert_memsize(self, line_num, keyword, values):
        """Converts memsize value from the form 'value1-value2' to
        'value1 value2' and outputs the range node to the criteria file

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self.root, ELEMENT_AI_CRITERIA)
        criteria_name.set(ATTRIBUTE_NAME, "mem")
        if "-" in values[0]:
            crit_range = etree.SubElement(criteria_name, ELEMENT_RANGE)
            crit_range.text = values[0].replace("-", " ")
        else:
            crit_value = etree.SubElement(criteria_name, ELEMENT_VALUE)
            crit_value.text = values[0]

    def __convert_network(self, line_num, keyword, values):
        """Converts the network keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        criteria_name = etree.SubElement(self.root, ELEMENT_AI_CRITERIA)
        criteria_name.set(ATTRIBUTE_NAME, "ipv4")
        try:
            addrA, addrB, addrC, addrD = values[0].split(".", 3)
        except ValueError:
            self.__invalid_syntax(line_num, keyword)
            self.root.remove(criteria_name)
            # since we've already added an element to the tree we need to
            # cleanup that element due to the exception.
            return

        crit_range = etree.SubElement(criteria_name, ELEMENT_RANGE)
        net_range = ("%s %s.%s.%s.255") % (values[0], addrA, addrB, addrC)
        crit_range.text = net_range

    def __process_rule(self):
        if self.rule_dict is None:
            # There's nothing to convert.  This is a valid condition
            # for example if the file couldn't be read
            self._report.conversion_errors = 0
            self._report.unsupported_items = 0
            self.root = None
            return

        if self.root is not None:
            return

        self.root = etree.Element(ELEMENT_AI_CRITERIA_MANIFEST)

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
            self.root = None

    def write_to_file(self, name):
        """Write out the xml document to a file"""
        try:
            with open(name, "w+") as fh:
                fh.write(etree.tostring(self.root, pretty_print=True))
        except IOError, msg:
            sys.stderr.write(_("Can't open file: %s: ") % filename + msg)
            sys.exit(-1)

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
    mirror_name_index = 1

    def __init__(self, name, prof_dict, report, local, logger):

        if logger is None:
            logger = logging.getLogger("js2ai")
        self.logger = logger
        self.profile_name = name
        self._report = report
        self._root = None
        self._local = local
        self.inst_type = "ips"
        self.prof_dict = prof_dict
        self._root_device = None
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

    def __is_valid_device_name(self, line_num, device):
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

    def __is_valid_device(self, line_num, device):
        """ Validate the disk name based on the regexp used by the check script

        A valid device is a string that is either a) a
        string that starts with /dev/dsk/ and ends with a
        valid slice name, or b) a valid slice name.

        Returns: True if valid, False otherwise

        """
        if device.startswith("/dev/dsk"):
            device = os.path.basename(device)
        return self.__is_valid_slice(line_num, device)

    def __is_valid_slice(self, line_num, slice_name):
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
        return self._report

    @property
    def local(self):
        return self._local

    @local.setter
    def local(self, newlocal):
        self._local = newlocal

    def __invalid_syntax(self, line_num, keyword):
        self.logger.error(_("%(file)s: line %(lineno)d: invalid syntax "
                            "for keyword '%(key)s' specified") % \
                            {"file": self.profile_name, \
                             "lineno": line_num, "key": keyword})
        self._report.add_process_error()

    def __unsupported_keyword(self, line_num, keyword, values):
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported "
                            "keyword: %(key)s") % \
                            {"file": self.profile_name, "lineno": line_num, \
                             "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_value(self, line_num, keyword, value):
        self.logger.error(_("%(file)s: line %(lineno)d: unsupported value "
                            "for '%(key)s' specified: %(val)s ") % \
                            {"file": self.profile_name, "lineno": line_num, \
                             "val": value, "key": keyword})
        self._report.add_unsupported_item()

    def __unsupported_syntax(self, line_num, keyword, msg):
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
        target = self.root.find(ELEMENT_TARGET)
        if target is not None:
            target_device = target.find(ELEMENT_TARGET_DEVICE)
            if target_device is not None:
                for zpool in target_device.findall(ELEMENT_ZPOOL):
                    if zpool.get(ATTRIBUTE_NAME, "") == pool_name:
                        return zpool

        if target is None:
            target = etree.SubElement(self.root, ELEMENT_TARGET)

        if target_device is None:
            target_device = etree.SubElement(target, ELEMENT_TARGET_DEVICE)

        zpool = etree.SubElement(target_device, ELEMENT_ZPOOL)
        zpool.set(ATTRIBUTE_NAME, pool_name)
        return zpool

    def __create_root_pool(self, line_num, pool_name=DEFAULT_POOL_NAME,
                           err_if_found=True):
        """Tests to see if a root pool currently exists.  If it exists None
        is returned.  If no root pool exists the pool will be created with the
        specified pool name.  If err_if_found is set to True a conversion
        error will be generated, if False no error will be generated.

        Arguments:
        line_num - the line # that in the file that is being processed
        pool_name - the name to assign to the root pool

        """
        target_device = None
        target = self.root.find(ELEMENT_TARGET)
        if target is not None:
            target_device = target.find(ELEMENT_TARGET_DEVICE)
            if target_device is not None:
                # Find the root pool
                # Typically there will only be one zpool but it's
                # possible too have more than one pool.  Thus we
                # need to search for the root pool if it exists
                for zpool in target_device.findall(ELEMENT_ZPOOL):
                    if zpool.get(ATTRIBUTE_IS_ROOT, "") == "true":
                        # A root pool exists.  Don't allow operation
                        if err_if_found:
                            self.logger.error(_("%(file)s: line %(linenum)d: "
                                           "conflicting root pool definitions."
                                           " Root pool already defined. "
                                           "Ignoring definition" % \
                                            {"file": self.profile_name,
                                             "linenum": line_num}))
                            self._report.add_conversion_error()
                        return None

        if target is None:
            target = etree.SubElement(self.root, ELEMENT_TARGET)

        if target_device is None:
            target_device = etree.SubElement(target, ELEMENT_TARGET_DEVICE)

        zpool = etree.SubElement(target_device, ELEMENT_ZPOOL)
        zpool.set(ATTRIBUTE_NAME, pool_name)
        zpool.set(ATTRIBUTE_IS_ROOT, "true")
        return zpool

    def __delete_root_pool(self):
        """Delete the root zpool entry and it's associated parent nodes
        if appropriate.  If the root pool is the only entry in the xml
        hierachy the parent nodes of zpool will be deleted.

        """
        target_device = None
        target = self.root.find(ELEMENT_TARGET)
        if target is not None:
            target_device = target.find(ELEMENT_TARGET_DEVICE)
            if target_device is not None:
                pools = target_device.findall(ELEMENT_ZPOOL)
                # Find the root pool
                # Typically there will only be one zpool but it's
                # possible too have more than one pool.  Thus we
                # need to search for the root pool if it exists
                for zpool in pools:
                    if zpool.get(ATTRIBUTE_IS_ROOT, "").lower() == "true":
                        # A root pool exists.  Now we need to determine
                        # whether we need to just delete the root pool
                        # or whether we need to delete the node hieracy
                        # that we create when we create the root pool
                        #
                        # <target>
                        #   <target_device>
                        #       <zpool ..>
                        #
                        # If <target_device> has only 1 child
                        # then we know we need to delete the entire structure
                        # If however, it has more than 1 child then we only
                        # want to delete the <zpool> entry for the root node
                        target_device.remove(zpool)
                        if not list(target_device):
                            # <target_device> has no children so we want
                            # to delete <target><target_device/></target>
                            # hierachy
                            self.root.remove(target)
                        break

    def __fetch_disk_node(self, vdev, disk_name):
        """Returns the disk node with the name 'disk_name' that is a child of
           vdev"""
        for disk in vdev.findall(ELEMENT_DISK):
            disk_name_node = disk.find(ELEMENT_DISK_NAME)
            if disk_name_node is None:
                continue
            if disk_name_node.get(ATTRIBUTE_NAME, "") == disk_name:
                return disk
        return None

    def __create_disk_node(self, vdev, disk_name):
        """Create the disk node with the name 'disk_name'"""
        disk = etree.SubElement(vdev, ELEMENT_DISK)
        disk_name_node = etree.SubElement(disk, ELEMENT_DISK_NAME)
        disk_name_node.set(ATTRIBUTE_NAME, disk_name)
        disk_name_node.set(ATTRIBUTE_NAME_TYPE, "ctd")
        return disk

    def __add_software_data_package_node(self, line_num, package, action):
        """Create a <name>$package</name> node and add it to the existing
        <software_data> node for the specified action.  If the node does not
        exist, create it and add it as a child of the specified parent node.

        Arguments:
        line_num - the line # that in the file that is being processed
        package - the name of the package element to add as a
            <name>$package</name> child node of <software_data>
        action - install or uninstall the package

        """
        if package is None or action is None:
            raise valueError

        orig_pwd = os.environ["PWD"]
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
        if not self.local:
            try:
                pkg_name = self.__do_pkg_search(search_remote, line_num)
            except Exception:
                # setting local so we'll retry with the local search
                self.local = True
                pkg_name = None
            if pkg_name != None:
                    package = pkg_name

        if self.local and not pkg_name:
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

        # Search for the the software data node with the action uninstall
        software_data = None
        for element in self.root.findall(ELEMENT_SOFTWARE_DATA):
            if element.get(ATTRIBUTE_ACTION, "") == action and \
                element.get(ATTRIBUTE_TYPE, "") == self.inst_type:
                software_data = element
                break

        if software_data is not None:
            # Walk through all the existing extries and look for the entry
            # we are attempting to add.  ie don't allow duplicates
            for element in software_data:
                if element.text == package:
                    # Duplicate.  Nothing to do
                    return

        if software_data == None:
            software_data = etree.SubElement(self.root, ELEMENT_SOFTWARE_DATA)
            software_data.set(ATTRIBUTE_ACTION, action)
            software_data.set(ATTRIBUTE_TYPE, self.inst_type)
        name = etree.SubElement(software_data, ELEMENT_NAME)
        name.text = package

    def __do_pkg_search(self, search, line_num):
        # Grab the new package name returned from the ipkg search
        pkg_name = None
        search_values = itertools.chain(search)
        if search_values is not None:
            try:
                for raw_value in search_values:
                    query_num, pub, (v, return_type, pkg_info) = raw_value
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

    def __convert_boot_device_entry(self, line_num, keyword, values):
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
        length = len(values)
        if length > 2 or length == 0:
            self.__invalid_syntax(line_num, keyword)
            return

        device = values[0].lower()
        if device == "any" or device == "existing":
            self.__unsupported_value(line_num, _("<device>"), device)
            return

        if not self.__is_valid_device_name(line_num, device) and \
           not self.__is_valid_slice(line_num, device):
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
        zpool = self.__create_root_pool(line_num)
        if zpool is None:
            # A root pool was already defined
            return

        vdev = zpool.find(ELEMENT_VDEV)
        if vdev is None:
            vdev = etree.SubElement(zpool, ELEMENT_VDEV)
        if self.__fetch_disk_node(vdev, device) is None:
            self.__create_disk_node(vdev, device)

    def __rootdisk_device_conversion(self, keyword, device, line_num):

        if device.startswith("rootdisk."):
            # We can only support the rootdisk keyword if it's been used
            # in combination with root_device
            if self._root_device is None:
                self.logger.error(_("%(file)s: line %(linenum)d: "
                    "unsupported syntax: '%(device)s' is only "
                    "supported if root_device was previously defined in "
                    "profile") % \
                    {"file": self.profile_name,
                    "linenum": line_num,
                    "device": device})
                self._report.add_unsupported_item()
                return None
            # The root device specification has a slice associated with it
            # we need to strip this off before we substitute "rootdisk."
            # with it
            disk = self.__device_name_conversion(self._root_device)
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

        disk_name = self.__rootdisk_device_conversion(keyword,
                                                     disk_name, line_num)
        if disk_name is None:
            return

        if not self.__is_valid_device_name(line_num, disk_name):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "device specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "device": disk_name})
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

        zpool = self.__create_root_pool(line_num)
        if zpool is None:
            # A root pool was already defined
            return

        vdev = zpool.find(ELEMENT_VDEV)
        if vdev is None:
            vdev = etree.SubElement(zpool, ELEMENT_VDEV)

        disk = self.__fetch_disk_node(vdev, disk_name)
        if disk is None:
            disk = self.__create_disk_node(vdev, disk_name)

        disk_name_node = disk.find(ELEMENT_DISK_NAME)
        partition = etree.SubElement(disk_name_node, ELEMENT_PARTITION)
        partition.set(ATTRIBUTE_NAME, "1")
        if size == "delete" or size == "0":
            partition.set(ATTRIBUTE_ACTION, "delete")
            return

        partition.set(ATTRIBUTE_ACTION, "create")

        if size not in ["all", "maxfree"]:
            # the fdisk size specified is in Mbytes
            size_node = etree.SubElement(partition, ELEMENT_SIZE)
            size_node.set(ATTRIBUTE_VAL, size + "mb")

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
        pool_name = DEFAULT_POOL_NAME
        mirror = False
        if values[0].startswith("mirror"):
            if length < 4:
                self.__invalid_syntax(line_num, keyword)
                return
            mirror_name = values[0]
            device1 = values[1]
            device2 = self.__rootdisk_device_conversion(keyword,
                                                       values[2], line_num)
            if device2 is None:
                return
            if device2 == "any":
                self.__unsupported_value(line_num, _("<device>"), "any")
                return
            if not self.__is_valid_slice(line_num, device2):
                # 2nd parameter is not a disk.  Therefore mark it
                # as unsupported
                self.logger.error(_("%(file)s: line %(linenum)d: invalid"
                                   " slice specified: %(device)s ") % \
                                   {"file": self.profile_name,
                                   "linenum": line_num,
                                   "device": device2})
                self._report.add_conversion_error()
                return
            size = values[3]
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
            size = values[1]
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

        device1 = self.__rootdisk_device_conversion(keyword, device1, line_num)
        if device1 is None:
            return

        if device1 == "any":
            self.__unsupported_value(line_num, _("<device>"), "any")
            return
        if not self.__is_valid_slice(line_num, device1):
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "slice specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, \
                                 "device": device1})
            self._report.add_conversion_error()
            return

        # If we have a mirror check to make sure 2 devices have been
        # specified and that those diffices are unique.  All other mirror
        # types are not supported
        if mirror:
            if device1 == device2:
                self.__unsupported_syntax(line_num, keyword,
                    _("mirror devices are not unique"))
                return

            if mirror_name != "mirror":
                try:
                    mirror, pool_name = values[0].split(":")
                except ValueError:
                    self.__invalid_syntax(line_num, keyword)
                    return

        zpool = self.__create_root_pool(line_num, pool_name, True)
        if zpool is None:
            # A root pool was already defined
            return

        vdev = zpool.find(ELEMENT_VDEV)
        if vdev is None:
            vdev = etree.SubElement(zpool, ELEMENT_VDEV)

        disk = self.__fetch_disk_node(vdev, device1)
        if disk is None:
            disk = self.__create_disk_node(vdev, device1)

        if device2 is not None:
            vdev = etree.SubElement(zpool, ELEMENT_VDEV)
            vdev.set(ATTRIBUTE_REDUNDANCY, "mirror")
            disk = self.__create_disk_node(vdev, device2)

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
            self.__add_software_data_package_node(line_num, package, "install")
        elif action == "delete":
            self.__add_software_data_package_node(line_num,
                                                 package, "uninstall")

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
            self.logger.error(_("%s(file)s: line %(lineno)d: invalid size "
                                "'%(val)s' specified for dump") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num, "val": values[3]})
            self._report.add_conversion_error()
            return

        if values[4] == "mirror":
            # Mirror must have at least 2 slices
            if length < 6:
                self.__invalid_syntax(line_num, keyword)
                return
        else:
            if values[4] == "any":
                self.logger.error(_("%(file)s: line %(lineno)d: ignoring "
                                 "specified device entry 'any' as this is "
                                 "the default behavior for pool creation" %\
                                 {"file": self.profile_name, \
                                  "lineno": line_num}))
                self._report.add_unsupported_item()
                return

            # Non mirror can only have 1 slice specified
            if length > 5:
                self.__invalid_syntax(line_num, keyword)
                return

        zpool = self.__create_root_pool(line_num, pool_name, True)
        if zpool is None:
            # A root pool was already defined
            return

        vdev = etree.SubElement(zpool, ELEMENT_VDEV)
        if values[4] == "mirror":
            vdev.set(ATTRIBUTE_REDUNDANCY, "mirror")
            start = 5
        else:
            start = 4

        for device in values[start:]:
            if device == "any":
                self.logger.error(_("%(file)s: line %(lineno)d: ignoring "
                                 "specified device entry 'any' as this is "
                                 "the default behavior for pool creation" %\
                                 {"file": self.profile_name, \
                                  "lineno": line_num}))
                self._report.add_conversion_error()
                self.__delete_root_pool()
                return
            device = self.__rootdisk_device_conversion(keyword,
                                                       device, line_num)
            if not self.__is_valid_slice(line_num, device):
                self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                    "slice specified: %(device)s") % \
                                    {"file": self.profile_name, \
                                     "lineno": line_num, \
                                     "device": device})
                self._report.add_conversion_error()
                self.__delete_root_pool()
                return
            self.__create_disk_node(vdev, device)

        target = self.root.find(ELEMENT_TARGET)
        # No need to check for None on target since we know it's there
        # since create_root_pool would of created it if it didn't exist
        swap = etree.SubElement(target, ELEMENT_SWAP)
        zvol = etree.SubElement(swap, ELEMENT_ZVOL)
        zvol.set(ATTRIBUTE_ACTION, "create")
        zvol.set(ATTRIBUTE_NAME, "swap")
        if swap_size != "auto":
            size = etree.SubElement(zvol, ELEMENT_SIZE)
            size.set(ATTRIBUTE_VAL, swap_size)

        dump = etree.SubElement(target, ELEMENT_DUMP)
        zvol = etree.SubElement(dump, ELEMENT_ZVOL)
        zvol.set(ATTRIBUTE_ACTION, "create")
        zvol.set(ATTRIBUTE_NAME, "dump")
        if dump_size != "auto":
            size = etree.SubElement(zvol, ELEMENT_SIZE)
            size.set(ATTRIBUTE_VAL, dump_size)

    def  __store_root_device(self, line_num, keyword, values):
        """Set the profile rootdevice value that we'll use if rootdevice
        is specified by the user

        """
        # root_device <slice>
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        if self.__is_valid_slice(line_num, values[0]):
            self._root_device = values[0]
        else:
            self.logger.error(_("%(file)s: line %(lineno)d: invalid "
                                "device specified: %(device)s") % \
                                {"file": self.profile_name, \
                                 "lineno": line_num,
                                 "device": values[0]})
            self._report.add_conversion_error()

    def __convert_usedisk_entry(self, line_num, keyword, values):
        """Converts the usedisk keyword/values from the profile into
        the new xml format

        """
        if len(values) != 1:
            self.__invalid_syntax(line_num, keyword)
            return
        if self.__is_valid_device_name(line_num, values[0]):
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

    profile_conversion_dict = {
        "boot_device": __convert_boot_device_entry,
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
        "root_device": __store_root_device,
        "system_type": __unsupported_keyword,
        "usedisk": __convert_usedisk_entry,
        }

    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, newroot):
        self._root = newroot

    def __process_profile(self):
        """Process the profile by taking all keyword/values pairs and
        generating the associated xml for the key value pairs

        """
        if self.prof_dict is None:
            # There's nothing to convert.  This is a valid condition if
            # the file couldn't of been read for example
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            self.root = None
            return

        if self.root:
            return

        self.root = etree.Element(ELEMENT_AUTO_INSTALL)

        check_for_install_type = True
        # We can sort the keys in this case since they are integers
        # This allows us to ensure that the first line we process is
        # the install_type.
        keys = sorted(self.prof_dict.keys())
        for key in keys:
            key_value_obj = self.prof_dict[key]
            if key_value_obj is None:
                raise ValueError

            keyword = key_value_obj.key.lower()
            value = key_value_obj.values
            line_num = key_value_obj.line_num

            if line_num is None or value is None or keyword is None:
                raise ValueError

            if check_for_install_type:
                # The only profiles that are supported are install profiles
                # The jumpstart scripts require it as the first keyword in the
                # file.  If the install_type is not initial_install reject
                # the entire profile
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
                    self.root = None
                    return
                install_type = value[0].lower()
                if install_type in ["upgrade",
                                       "flash_install", "flash_upgrade"]:
                    self.__unsupported_value(line_num, keyword, value[0])
                    self._report.conversion_errors = None
                    self.root = None
                    return
                if install_type != "initial_install":
                    self.__invalid_syntax(line_num, keyword)
                    self._report.conversion_errors = None
                    self._report.unsupported_items = None
                    self.root = None
                    return
                check_for_install_type = False

            try:
                function_to_call = self.profile_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(line_num, keyword, value)
            else:
                function_to_call(self, line_num, keyword, value)

        # If the user specified a root_device but didn't create a root
        # pool via filesys, fdisk or pool create one now and add the
        # specified root_device as that disk for that pool
        if self._root_device:
            zpool = self.__create_root_pool(line_num, DEFAULT_POOL_NAME, False)
            if zpool is not None:
                vdev = zpool.find(ELEMENT_VDEV)
                if vdev is None:
                    vdev = etree.SubElement(zpool, ELEMENT_VDEV)

                disk = self.__fetch_disk_node(vdev, self._root_device)
                if disk is None:
                    disk = self.__create_disk_node(vdev, self._root_device)

        # Check to determine if we have any children nodes
        # If we don't and we have errors then clear the xml
        # tree so we don't have a empty tree hierachy that
        # results in a <auto_install/>
        # Conversely though if all that's in the file is
        # initial_install and we have no errors then we should
        # create a file even if it's just <auto_install/>
        # That technically won't have any meaning to the new jumpstart
        # engine though
        children = list(self.root)
        if not children and self._report.has_errors():
            self.root = None

    def write_to_file(self, name):
        """Write out the xml document to a file"""
        try:
            with open(name, "w") as fh:
                fh.write(etree.tostring(self.root, pretty_print=True))
        except IOError, msg:
            sys.stderr.write(_("Can't open file: %s: ") % filename + msg)
            sys.exit(-1)

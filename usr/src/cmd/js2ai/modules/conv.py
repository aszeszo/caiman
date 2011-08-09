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
import os.path
import re
import sys

import pkg.client.api as api
import pkg.client.api_errors as apx
import pkg.client.progress as progress
import os

from common import _
from common import fetch_xpath_node
from common import generate_error
from common import LOG_KEY_FILE, LOG_KEY_LINE_NUM
from common import LVL_CONVERSION, LVL_PROCESS
from common import LVL_UNSUPPORTED, LVL_WARNING
from common import RULES_FILENAME
from default_xml import DEFAULT_XML_EMPTY
from lxml import etree
from StringIO import StringIO

from solaris_install import PKG5_API_VERSION


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

FILESYS_ARG_PATTERN = re.compile("..*:/..*")

DEFAULT_POOL_NAME = "rpool"
DEFAULT_VDEV_NAME = "rpool_vdev"
VDEV_SUFFIX = "_vdev"

DEFAULT_SWAP_POOL_NAME = "swap_pool"

# The text form when adding a localization facet
# in a manifest
# <software name="ips" type="IPS">
#      <destination>
#        <image>
#          <facet set="false">facet.locale.*</facet>
#          ....
#
FACET_LOCALE_FORM = "facet.locale.%s"

SOFTWARE_INSTALL = "install"
SOFTWARE_UNINSTALL = "uninstall"

REDUNDANCY_NONE = "none"
REDUNDANCY_MIRROR = "mirror"

DEVICE_ANY = "any"
SIZE_ALL = "all"
SIZE_AUTO = "auto"
SIZE_DELETE = "delete"
SIZE_EXISTING = "existing"
SIZE_FREE = "free"
SIZE_MAXFREE = "maxfree"

PARTITIONING_DEFAULT = "default"
PARTITIONING_EXPLICIT = "explicit"

# Prefix for keyword operations like fdisk that specify the <device> as
# rootdisk.
#
# fdisk rootdisk <type> <size>
#
PREFIX_ROOTDISK = "rootdisk"


# Prefix for keyword operations like filesys that specify the <slice> as
# a rootdisk slice.
#
# filesys rootdisk.s1 10000 swap
#
PREFIX_ROOTDISK_DOT = "rootdisk."

FILESYS_DEFAULT_MOUNT_POINT = "unnamed"

# Follow the same name scheme used for mirror pools using the old jumpstart
# scripts.  When not specified mirror names start with the letter "d" followed
# by a number between 0 and 127
DEFAULT_MIRROR_POOL_NAME = "d"


class XMLRuleData(object):
    """This object holds all the data read in from the rules file.  This data
    is converted into an xml document which then can be manipluated as needed.

    """

    def __init__(self, rule_dict, report):
        """Initialize the object

        Arguments:
        rule_dict - a dictionary containing the key values pairs read
                in from the rule file
        report - the error report

        """
        self._root = None
        self._report = report
        self.rule_dict = rule_dict
        self._extra_log_params = {LOG_KEY_FILE: RULES_FILENAME,
                                  LOG_KEY_LINE_NUM: 0}
        self.__process_rule()

    def __gen_err(self, lvl, message):
        """Log the specified error message at the specified level and
           increment the error count associated with that log level in
           the conversion report by 1

        """
        generate_error(lvl, self._report, message, self._extra_log_params)

    @property
    def report(self):
        """Conversion report associated with the object"""
        return self._report

    @property
    def root(self):
        """The xml root element"""
        return self._root

    def __unsupported_keyword(self, keyword, values):
        """Generate an unsupported keyword error message"""
        self.__gen_err(LVL_UNSUPPORTED,
                       _("unsupported keyword: %(key)s") % {"key": keyword})

    def __unsupported_negation(self):
        """Generate an unsupported negation error message"""
        self.__gen_err(LVL_UNSUPPORTED,
                       _("negation '!' not supported in manifests"))

    def __invalid_syntax(self, keyword):
        """Generate an invalid syntax error message"""
        self.__gen_err(LVL_PROCESS,
                       _("invalid syntax for keyword '%(key)s' "
                         "specified") % {"key": keyword})

    def __convert_arch(self, keyword, values):
        """Converts arch keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        if values[0] == "sun4u":
            self.__gen_err(LVL_UNSUPPORTED,
                           _("Solaris 11 does not support the specified "
                             "arch '%(arch)s'") % {"arch": values[0]})
            return
        self.__convert_common(keyword, values)

    def __convert_common(self, keyword, values):
        """Converts the specified keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        criteria_name = etree.SubElement(self._root,
                                         common.ELEMENT_AI_CRITERIA)
        try:
            criteria_name.set(common.ATTRIBUTE_NAME,
                              self.rule_keywd_conv_dict[keyword])
        except KeyError:
            self.__unsupported_keyword(keyword, values)
            # since we've already added an element to the tree we need to
            # cleanup that element due to the exception.
            self._root.remove(criteria_name)
            return
        crit_value = etree.SubElement(criteria_name, common.ELEMENT_VALUE)
        crit_value.text = values[0]

    def __convert_memsize(self, keyword, values):
        """Converts memsize value from the form 'value1-value2' to
        'value1 value2' and outputs the range node to the criteria file

        """
        if len(values) != 1:
            self.__invalid_syntax(keyword)
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

    def __convert_network(self, keyword, values):
        """Converts the network keyword and value from a line in the
        rules file into the xml format for outputting into the
        criteria file.

        """
        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        criteria_name = etree.SubElement(self._root,
                                         common.ELEMENT_AI_CRITERIA)
        criteria_name.set(common.ATTRIBUTE_NAME, "ipv4")
        try:
            addr_a, addr_b, addr_c, remainder = values[0].split(".", 3)
        except ValueError:
            self.__invalid_syntax(keyword)
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

        key_dict = self.rule_dict.key_values_dict
        for key_values in key_dict.iterkeys():
            keyword = key_dict[key_values].key
            values = key_dict[key_values].values
            line_num = key_dict[key_values].line_num
            if line_num is None or values is None or keyword is None:
                raise ValueError
            self._extra_log_params[LOG_KEY_LINE_NUM] = line_num
            if "!" in keyword:
                self.__unsupported_negation()
                continue
            try:
                function_to_call = self.rule_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(keyword, values)
            else:
                function_to_call(self, keyword, values)
        children = list(self._root)
        if len(children) == 0:
            self._root = None

    rule_conversion_dict = {
        "any": __unsupported_keyword,
        "arch": __convert_arch,
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

    def __init__(self, name, prof_dict, report, default_xml, local):
        """Initialize the object

        Arguments:
        name - the name of the profile
        prof_dict - a dictionary containing the key values pairs read
                in from the profile
        report - the error report
        default_xml - the XMLDefaultData object containing the xml tree
                hierachy that the prof_dict data will be merged into
        local - boolean flag for where package name looks is local only
        """
        self.profile_name = name
        self._report = report
        if default_xml is None:
            default_tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
        else:
            default_tree = common.tree_copy(default_xml.tree)
        self._tree = default_tree
        self._root = self._tree.getroot()

        xpath = "/auto_install/ai_instance"
        self._ai_instance = fetch_xpath_node(self._tree, xpath)
        if self._ai_instance is None:
            tree = etree.parse(StringIO(DEFAULT_XML_EMPTY))
            sys.stderr.write(etree.tostring(self._tree, pretty_print=True))
            expected_layout = etree.tostring(tree, pretty_print=True)
            raise ValueError(_("<ai_instance> node not found. "
                               "%(filename)s does not conform to the expected "
                               "layout of:\n\n%(layout)s") %
                               {"filename": default_xml.name, \
                                "layout": expected_layout})

        self._extra_log_params = {LOG_KEY_FILE: self.profile_name,
                                  LOG_KEY_LINE_NUM: 0}
        self._target = None
        self._image_node = None
        self._local = local
        self.inst_type = "ips"
        self.prof_dict = prof_dict
        self._partitioning = None
        self._usedisk = list()
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
        self._rootdisk_size = SIZE_ALL
        self._root_pool = None
        self._root_pool_create_via_keyword = None
        self._root_pool_name = DEFAULT_POOL_NAME
        self._arch = common.ARCH_GENERIC
        self.__process_profile()

    def __gen_err(self, lvl, message):
        """Log the specified error message at the specified level and
           increment the error count associated with that log level in
           the conversion report by 1

        """
        generate_error(lvl, self._report, message, self._extra_log_params)

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

    def __duplicate_keyword(self, keyword, values):
        """Log a duplicate keyword error and add a process error to report"""
        self.__gen_err(LVL_PROCESS,
                       _("invalid entry, duplicate keyword encountered: "
                         "%(key)s") % {"key": keyword})

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

    def __is_valid_mirror(self, keyword, devices, size,
                          root_conflict_check):
        """Check the devices that will make up the mirror to ensure there
        are no conflicts

        Arguments:
        line_num - the line being processed
        keyword - the keyword being processed
        devices - list of devices
        size - the size to assign to the mirror
        root_conflict_check - perform check to see if devices conflict with
                root_disk setting.  This should only be done if creating
                a root pool mirror
        """
        if DEVICE_ANY in devices:
            self.__gen_err(LVL_UNSUPPORTED,
                           _("use of the device entry 'any' is not "
                             "supported when a mirrored %(keyword)s is "
                             "specified") % {"keyword": keyword})
            return
        unique = set(devices)
        if len(unique) != len(devices):
            self.__gen_err(LVL_CONVERSION,
                           _("invalid syntax: mirror devices are not unique"))
            return False
        if size == SIZE_ALL:
            # When the size is all (entire disk) the underlining disk
            # associated with each slice must be unique
            unique = []
            for disk_slice in devices:
                disk, slice_num = disk_slice.split("s")
                if disk in unique:
                    self.__gen_err(LVL_CONVERSION,
                                   _("invalid syntax: duplicate device "
                                     "%(disk)s found, underlying devices for "
                                     "mirror be different when a size of "
                                     "'all' is specified.") % {"disk": disk})
                    return False
                unique.append(disk)
        if root_conflict_check:
            for device in devices:
                # Check for conflict.
                if self.__rootdisk_slice_conflict_check(keyword, device):
                    # We've got a conditions like
                    #
                    # root_device cxtxdxs1
                    # pool newpool auto auto auto mirror cxtxdxs0 cxtxdxs1
                    #
                    # Warning message has been outputed
                    break
        return True

    @property
    def conversion_report(self):
        """Return the converstion report associated with this object"""
        return self._report

    @property
    def architecture(self):
        """Return the architecture for this profile.  A value of NONE
        indicates the architecture is unknown.  If known a value of
        common.ARCH_X86 or common.ARCH_SPARC will be returned"""
        return self._arch

    def __change_arch(self, arch):
        """Change the architecture setting that this profile is
           being generated for.  Check for the one possible conflict
           condition and update error report appropriately.  Returns True
           if change represents no conflict, False otherwise

        """
        if self._arch == common.ARCH_GENERIC:
            self._arch = arch
        elif arch == self._arch:
            # Already set
            return True
        else:
            # Error we've got a profile that is mixing x86 and sparc syntax
            # There only one way this can happen.
            self.__gen_err(LVL_CONVERSION,
                           _("architecuture conflict detected. fdisk is an "
                             "x86 only keyword operation. This conflicts "
                             "with 'boot_device %(dev)s' which was "
                             "specified using the SPARC device syntax "
                             "instead of the x86 device syntax of cwtxdy "
                             "or cxdy") % {"dev": self._boot_device})
            return False
        return True

    def __invalid_syntax(self, keyword):
        """Generate invalid keyword error"""
        self.__gen_err(LVL_PROCESS,
                       _("invalid syntax for keyword '%(key)s' specified") % \
                         {"key": keyword})

    def __unsupported_keyword(self, keyword, values):
        """Generate unsupported keyword error"""
        self.__gen_err(LVL_UNSUPPORTED,
                       _("unsupported keyword: %(key)s") % {"key": keyword})

    def __unsupported_value(self, keyword, value):
        """Generate unsupported value error"""
        self.__gen_err(LVL_UNSUPPORTED,
                        _("unsupported value for '%(key)s' specified: "
                          "%(val)s ") % {"val": value, "key": keyword})

    def __unsupported_syntax(self, keyword, msg):
        """Generate unsupported syntax error"""
        self.__gen_err(LVL_UNSUPPORTED,
                       _("unsupported syntax for '%(key)s' specified: "
                         "%(msg)s") % {"key": keyword, "msg": msg})

    def __root_pool_exists(self, keyword):
        """Check whether root pool has been created and generate error if the
        root pool already exists.  If exists adds a conversion error to report.
        Return True if exists, False otherwise

        """
        if self._root_pool is not None:
            # If the root pool already exists we reject the entry
            self.__gen_err(LVL_CONVERSION,
                           _("the ZFS root pool was already created using "
                             "the '%(created_by)s' keyword, ignoring "
                             "'%(keyword)s' definition") % \
                             {"keyword": keyword,
                              "created_by":
                              self._root_pool_create_via_keyword})
            return True
        return False

    def __create_logical(self, noswap, nodump):
        """Create the <logical noswap=$noswap nodump=$nodump> node"""
        logical = etree.SubElement(self._target,
                                         common.ELEMENT_LOGICAL)
        logical.set(common.ATTRIBUTE_NOSWAP, noswap)
        logical.set(common.ATTRIBUTE_NODUMP, nodump)
        return logical

    def __create_root_pool(self, created_by_keyword,
                           pool_name=DEFAULT_POOL_NAME,
                           noswap="false", nodump="true"):
        """Tests to see if a root pool currently exists.  If it exists a
        the existing root pool is returned. If no root pool exists the
        pool will be created with the specified pool name.

        Arguments:
        created_by_keyword - the keyword to associate with the creation of
                   the root pool.  This will be used in the error generation
                   for root pool already exists messages
        pool_name - the name to assign to the root pool
        noswap - noswap for logical component zpool resides in.
                 Expected value is "true"/"false"
        nodump - nodump for logical component zpool resides in.
                 Expected value is "true"/"false"

        """
        if self._root_pool is not None:
            return self._root_pool

        if self._target is None:
            self._target = etree.Element(common.ELEMENT_TARGET)
            self._ai_instance.insert(0, self._target)
        logical = self._target.find(common.ELEMENT_LOGICAL)
        if logical is None:
            logical = self.__create_logical(noswap, nodump)
        self._root_pool = self.__create_zfs_pool(pool_name)
        self._root_pool.set(common.ATTRIBUTE_IS_ROOT, "true")
        self._root_pool_create_via_keyword = created_by_keyword
        return self._root_pool

    def __create_vdev(self, parent, redundancy="none", name=DEFAULT_VDEV_NAME):
        """Tests to see if a vdev with the specified name currently exists.
        If it exists the existing vdev is returned. If no vdev exists the
        vdev will be created with the specified name and redundancy.

        Arguments:
        parent - the parent node of the vdev to create
        name - the name of the vdev
        redundancy - the vdev redundancy

        """
        xpath = "./vdev[@name='%s']" % name
        vdev = fetch_xpath_node(parent, xpath)
        if vdev is None:
            vdev = etree.SubElement(parent, common.ELEMENT_VDEV)
        vdev.set(common.ATTRIBUTE_NAME, name)
        vdev.set(common.ATTRIBUTE_REDUNDANCY, redundancy)

    def __create_zvol(self, parent, name, use, zvol_size):
        """Creates a zvol with the specifed name, size, and use.

        Arguments:
        parent - the parent node to create the vzol under
        name - the name of the vpool to create
        use - the use to specify for the zvol
        vpool_size - the size for the zvol.  Size should include measurement
                like mb, gb, etc

        """
        vpool = etree.SubElement(parent, common.ELEMENT_ZVOL)
        vpool.set(common.ATTRIBUTE_NAME, name)
        vpool.set(common.ATTRIBUTE_USE, use)
        size = etree.SubElement(vpool, common.ELEMENT_SIZE)
        size.set(common.ATTRIBUTE_VAL, zvol_size)

        # Depending on the use specified adjust the parents parent nodes
        # (<logical> node) attributes to indicate that a swap or dump
        # volume is available
        logical = parent.getparent()
        if logical is not None:
            if use == "swap":
                logical.set(common.ATTRIBUTE_NOSWAP, "false")
            elif use == "dump":
                logical.set(common.ATTRIBUTE_NODUMP, "false")

    def __create_zfs_pool(self, pool_name):
        """Create the <zpool> xml structure"""

        logical = self._target.find(common.ELEMENT_LOGICAL)
        if logical is None:
            logical = self.__create_logical(noswap="false", nodump="true")

        zpool = etree.SubElement(logical, common.ELEMENT_ZPOOL)
        zpool.set(common.ATTRIBUTE_NAME, pool_name)
        return zpool

    def __create_disk_node(self, disk_name, whole_disk):
        """Create the <disk><disk_name></disk> structure used to represent a
           disk in the system

           <disk whole_disk="true">
               <disk_name name="${disk_name}"/>
           </disk>

        """
        disk = etree.Element(common.ELEMENT_DISK)
        self._target.insert(0, disk)
        diskname_node = etree.SubElement(disk, common.ELEMENT_DISK_NAME)
        diskname_node.set(common.ATTRIBUTE_NAME, disk_name)
        diskname_node.set(common.ATTRIBUTE_NAME_TYPE, "ctd")
        if whole_disk:
            disk.set(common.ATTRIBUTE_WHOLE_DISK, "true")
        return disk

    def __add_device(self, device, size=None,
                     in_pool=DEFAULT_POOL_NAME,
                     in_vdev=DEFAULT_VDEV_NAME, is_swap=None):
        """Added device to the target xml hierachy

           Arguments:
           device - the device/slice to add.  "any" may be specified
           size = #size or all or none
           in_pool - the root pool to associate the device with if any.
           in_vdev - the vdev the the device is placed in
           is_swap - Indicates the device is a non ZFS swap device
                     May not be mixed with in_pool or in_vdev

        """
        if device == DEVICE_ANY:
            # We don't generate any structure for any
            # This tells the AI to automatically discover the root disk to use
            return
        if size == SIZE_ALL:
            delete_existing = True
        else:
            delete_existing = False
        try:
            disk_name, slice_num = device.split("s")
        except ValueError:
            disk_name = device
            # For Solaris 11 we default to s0 if no slice is specified
            slice_num = "0"
            delete_existing = True

        # Check to make sure that the device we are adding isn't in the
        # usedisk list.  If it is remove it so we don't try to use it later
        if self._usedisk.count(disk_name):
            self._usedisk.remove(disk_name)
            if self._partitioning == PARTITIONING_DEFAULT:
                delete_existing = True

        disk_node = self.__fetch_disk_node(disk_name)
        if disk_node is None:
            if self._arch == common.ARCH_GENERIC:
                # The architecture of the manifest represented by the xml tree
                # associated with this object is currently set as GENERIC.
                # The Jumpstart profile operation (via keyword) now being
                # processed cannot be performed in a generic fashion.  As such
                # when completed it will be necessary to generate 2 different
                # manifests.  One for SPARC and one for x86.  We accomplish
                # this by setting the _arch flag to None and then internally
                # generating the manifest as an x86 tree. The None value for
                # architecture returned via conv.arch() tells the caller
                # (in this case, __init__.py convert_profile()) that a call
                # to fetch both trees (x86, SPARC) via fetch_tree(arch)
                # will be necessary
                if not self.__change_arch(None):
                    return

            disk = self.__create_disk_node(disk_name, delete_existing)
            if self._arch == common.ARCH_SPARC:
                slice_parent_node = disk
            else:
                slice_parent_node = self.__add_partition(disk)
        else:
            if self._arch in [None, common.ARCH_X86]:
                # We return the partition
                xpath = "./partition[@action='create'][@part_type='191']"
                slice_parent_node = fetch_xpath_node(disk_node, xpath)
            else:
                slice_parent_node = disk_node
            if not self.__is_valid_to_add_slice(device, size):
                return
        self.__add_slice(slice_parent_node, slice_num, "create", size,
                         in_pool, in_vdev, is_swap)

    def __slice_exists(self, slice_node_parent,
                            device, slice_num):
        """Checks whether the specified slice can be added to structure
        If the slice already exists and error will be outputed

        """
        xpath = "./slice[@name='%s'][@action='create']" % slice_num
        slice_node = fetch_xpath_node(slice_node_parent, xpath)
        if slice_node is not None:
            # Slice already exists
            self.__gen_err(LVL_CONVERSION,
                           _("%(device)ss%(slice)s already exists") %
                             {"device": device, "slice": slice_num})
            return True
        return False

    def __is_valid_to_add_slice(self, device, size):
        """Perform some basic checks to prevent an invalid manifest from
        being generated.

        """
        disk_name, slice_num = device.split("s")
        diskname_node = self.__fetch_diskname_node(disk_name)
        if diskname_node is None:
            return True

        if self._arch is None or self._arch == common.ARCH_X86:
            # partition node node is only present on x86
            slice_node_parent = \
                diskname_node.getparent().find(common.ELEMENT_PARTITION)
            if slice_node_parent is None:
                return True
        else:
            slice_node_parent = diskname_node

        if self.__slice_exists(slice_node_parent,
                               disk_name, slice_num):
            return False

        # 2. If we are creating adding a slice to a disk with an
        #    existing slice make sure the slice size specification is
        #    compatible with the existing slice definition.  All though
        #    there may be multiple slices the 1st slice will give us
        #    all the data we need

        xpath = "./slice[@action='create']"
        slice_node = fetch_xpath_node(slice_node_parent, xpath)
        if slice_node is not None:
            size_node = slice_node.find(common.ELEMENT_SIZE)
            if  size_node is None:
                if size not in [SIZE_AUTO, SIZE_ALL, None]:
                    self.__gen_err(LVL_CONVERSION,
                                   _("can not create %(device)ss%(slice1)s. "
                                     "Conflicts with %(device)ss%(slice2)s "
                                     "that was created earlier via keyword "
                                     "'%(rp_kw)s' without a specified "
                                     "numeric size.") %
                                     {"device": disk_name,
                                      "slice1": slice_num,
                                      "slice2":
                                      slice_node.get(common.ATTRIBUTE_NAME),
                                      "rp_kw":
                                      self._root_pool_create_via_keyword})
                    return False
            elif size in [SIZE_AUTO, SIZE_ALL, None]:
                self.__gen_err(LVL_CONVERSION,
                               _("can not create %(device)ss%(slice1)s"
                                 " with a size of '%(size)s'. "
                                 "Conflicts with %(device)ss%(slice2)s "
                                 "that was created earlier via keyword "
                                 "'%(rp_kw)s' with a size of "
                                 "%(rp_size)s.") %
                                 {"device": disk_name,
                                  "slice1": slice_num,
                                  "slice2":
                                  slice_node.get(common.ATTRIBUTE_NAME),
                                  "size": size,
                                  "rp_kw": self._root_pool_create_via_keyword,
                                  "rp_size":
                                  size_node.get(common.ATTRIBUTE_VAL)})
                return False
        return True

    def __add_slice(self, parent, slice_num, action, size=None, in_pool=None,
                    in_vdev=None, is_swap=None):
        """Add the <slice> node with the specified attributes as a child
        of parent

        """
        # We can't mix in_pool or in_vdev with is_swap.  is_swap is only
        # for non ZFS swap
        if (in_vdev or in_pool) and is_swap:
            raise ValueError(_("is_swap can not be mixed with in_vdev or "
                               "in_pool"))
        slice_node = etree.SubElement(parent, common.ELEMENT_SLICE)
        slice_node.set(common.ATTRIBUTE_NAME, slice_num)
        slice_node.set(common.ATTRIBUTE_ACTION, action)
        slice_node.set(common.ATTRIBUTE_FORCE, "true")
        if in_pool is not None:
            slice_node.set(common.ATTRIBUTE_IN_ZPOOL, in_pool)
        if in_vdev is not None:
            slice_node.set(common.ATTRIBUTE_IN_VDEV, in_vdev)
        if is_swap is not None:
            slice_node.set(common.ATTRIBUTE_IS_SWAP, is_swap)
        if size not in [None, SIZE_AUTO, SIZE_ALL]:
            size_node = etree.SubElement(slice_node,
                                         common.ELEMENT_SIZE)
            size_node.set(common.ATTRIBUTE_VAL, size)

    def __add_partition(self, parent, name="1", part_type="191",
                        action="create"):
        """Add <partitition> node as a child of parent"""
        partition_node = parent.find(common.ELEMENT_PARTITION)
        if partition_node is None:
            partition_node = etree.SubElement(parent, common.ELEMENT_PARTITION)
            partition_node.set(common.ATTRIBUTE_ACTION, action)
            partition_node.set(common.ATTRIBUTE_NAME, name)
            partition_node.set(common.ATTRIBUTE_PART_TYPE, part_type)
        return partition_node

    def __fetch_solaris_software_node(self):
        """Fetch the software publisher node instance in the xml tree"""
        xpath = "./software[@type='IPS']/source/publisher[@name='solaris']"
        publisher = fetch_xpath_node(self._ai_instance, xpath)
        if publisher is not None:
            # We found the proper node
            # Return handle to software node
            return publisher.getparent().getparent()

        # Check to see if there is an software node with a publisher
        # If no publisher is specified it will default to solaris

        for software in self._ai_instance.findall(common.ELEMENT_SOFTWARE):
            if not software.find(common.ELEMENT_SOURCE):
                # We found our match
                return software

        # No match found create it
        software = etree.SubElement(self._ai_instance,
                                    common.ELEMENT_SOFTWARE)
        software.set(common.ATTRIBUTE_TYPE, "IPS")
        return software

    def __add_software_data(self, package, action):
        """Create a <name>$package</name> node and add it to the existing
        <software_data> node for the specified action.  If the node does not
        exist, create it and add it as a child of the specified parent node.

        Arguments:
        package - the name of the package element to add as a
            <name>$package</name> child node of <software_data>
        action - install or uninstall the package

        """
        orig_pwd = os.getcwd()
        prog_tracker = progress.CommandLineProgressTracker()
        api_inst = api.ImageInterface("/", PKG5_API_VERSION,
                                      prog_tracker, False, "js2ai")
        pkg_query = ":legacy:legacy_pkg:" + package
        query = [api.Query(pkg_query, False, True)]
        gettext.install("pkg", "/usr/share/locale")
        search_remote = api_inst.remote_search(query, servers=None,
                                               prune_versions=True)
        search_local = api_inst.local_search(query)
        pkg_name = None
        # Remote search is the default since this will often have a more
        # complete package catalog than that on an installed system.
        if not self._local:
            try:
                pkg_name = self.__do_pkg_search(search_remote)
            except Exception:
                # setting local so we'll retry with the local search
                self._local = True
                pkg_name = None
            if pkg_name != None:
                package = pkg_name

        if self._local and not pkg_name:
            try:
                pkg_name = self.__do_pkg_search(search_local)
            except Exception, msg:
                self.__gen_err(LVL_CONVERSION,
                               _("package name translation failed for "
                                 "'%(packge)s': %(message)s") % \
                                 {"package": package, \
                                  "message": msg})
            if pkg_name != None:
                package = pkg_name

        # Because the pkg api call can change the working directory we need to
        # set it back to it's original directory.
        os.chdir(orig_pwd)

        software = self.__fetch_solaris_software_node()
        if pkg_name not in ["SUNWcs", "SUNWcsd"]:
            package = "pkg:/" + package
        xpath = "./software_data[@action='%s']"
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
                                             action=action)

        name = etree.SubElement(software_data, common.ELEMENT_NAME)
        name.text = package

    def __do_pkg_search(self, search):
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
                self.__gen_err(LVL_WARNING,
                               _("package name lookup returned error: "
                                 "%(message)s") % {"message": msg})
        return pkg_name

    def __rootdisk_slice_conflict_check(self, keyword, disk_slice):
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
            if self._rootdisk_set_by_keyword == "fdisk":
                # fdisk keyword never represents a conflict
                # it may be overriden by any keyword that causes rootdisk
                # to be set
                return

            # root_disk wasn't set but boot_device was so our comparision
            # has to be made at the disk level instead of the slice level
            cmp_device = self.__device_name_conversion(disk_slice)
        if cmp_device != self._rootdisk:
            self.__gen_err(LVL_CONVERSION,
                           _("conflicting ZFS root pool definition: "
                             "%(keyword)s definition will be used instead of "
                             "'%(rd_kw)s %(rootdisk)s'") % \
                             {"keyword": keyword,
                              "rd_kw": self._rootdisk_set_by_keyword,
                              "rootdisk": str(self._rootdisk)})
            return True
        return False

    def __rootdisk_conversion(self, device, prefix):
        """Checks the 'device' for the presence of 'prefix'  if found
        and the root disk has been determined the 'prefix' will be
        replaced with the name of the root disk

        """
        # Jumpstart profiles may have commands in the format
        #
        # filesys rootdisk.s0 size mount_point
        # fdisk solaris rootdisk all
        #
        # This routines simply looks for that pattern in the device
        # and substitutes it for the rootdisk if we've determined
        # what that rootdisk is
        #
        if device is not None and device.startswith(prefix):
            # We can only support the rootdisk keyword if
            # root_device, boot_device, pool, or  filesys /
            # has been specified in the profile
            # If filesys / is used then it must proceed rootdisk usage
            # in order for this substitution to suceed
            if self._rootdisk is None:
                self.__gen_err(LVL_CONVERSION,
                               _("unable to convert '%(device)s'.  Replace"
                                 "'%(prefix)s' with actual device name") % \
                                 {"device": device,
                                  "prefix": prefix})
                return None
            # The root device specification has a slice associated with it
            # we need to strip this off before we substitute "rootdisk."
            # with it
            disk = self.__device_name_conversion(self._rootdisk)
            device = device.replace(prefix, disk, 1)
        return device

    def __convert_fdisk_entry(self, keyword, values):
        """Processes the fdisk keyword/values from the profile

        """

        # fdisk <diskname> <type> <size>
        if len(values) != 3:
            self.__invalid_syntax(keyword)
            return

        # check <diskname> syntax
        # valid values:         rootdisk
        #                       all
        #                       cx[ty]dz
        disk_name = values[0].lower()
        if disk_name == SIZE_ALL:
            # AI doesn't provide with the ability that says initialize
            # all disks discovered on a system.  We therefore have to
            # mark this as unsupported
            self.__unsupported_value(_("<diskname>"), disk_name)
            return

        disk_name = self.__rootdisk_conversion(disk_name,
                                               PREFIX_ROOTDISK)
        if disk_name is None:
            return

        if not self.__is_valid_device_name(disk_name):
            self.__gen_err(LVL_CONVERSION,
                           _("invalid device specified: %(device)s") % \
                             {"device": values[0]})
            return

        # check <type> syntax
        # valid values:         solaris
        #                       dosprimary
        #                       x86boot
        #                       ###
        fdisk_type = values[1]
        if fdisk_type != "solaris":
            self.__unsupported_value(_("<type>"), fdisk_type)
            return

        # check <size> syntax for non-x86boot partitions
        # valid values:         all
        #                       delete
        #                       maxfree
        #                       ###
        size = values[2].lower()
        if size in [SIZE_MAXFREE, SIZE_DELETE, "0"]:
            # maxfree - An fdisk partition is created in the largest
            #           contiguous free space on the specified disk. If an
            #           fdisk partition of the specified type already exists
            #           on the disk, the existing fdisk partition is used.
            #           A new fdisk partition is not created on the disk.
            #           There's no support, mark it as unsupported
            # delete -  All fdisk partitions of the specified type are deleted
            #           on the specified disk.  Although we can technically
            #           support the delete keyword we are going to mark this
            #           as unsupported because the disk handling is so
            #           different in this go around and we are only supporting
            #           the a single root pool creation
            self.__unsupported_value(_("<size>"), size)
            return
        if size != SIZE_ALL:
            size = self.__size_conversion(keyword, size)
            if size is None:
                return

        if self._root_pool is None and \
          self._partitioning == PARTITIONING_DEFAULT and \
          self._rootdisk is None:
            # Only set rootdisk to the value held by fdisk if
            # "partitioning = default".  A value of explicit implies
            # the user is going to specify the layout
            self._rootdisk = disk_name
            if size != SIZE_ALL:
                self._rootdisk_size = size
            self._rootdisk_set_by_keyword = "fdisk"

        # Go ahead and create entry for partition
        disk_node = self.__fetch_disk_node(disk_name)
        if disk_node is None:
            disk_node = self.__create_disk_node(disk_name, size == SIZE_ALL)
        else:
            if size == SIZE_ALL:
                disk_node.set(common.ATTRIBUTE_WHOLE_DISK, "true")
        part_node = self.__add_partition(disk_node)
        size_node = part_node.find(common.ELEMENT_SIZE)
        if size != SIZE_ALL:
            if size_node is None:
                size_node = etree.Element(common.ELEMENT_SIZE)
                part_node.insert(0, size_node)
                size_node.set(common.ATTRIBUTE_VAL, size)
            else:
                spec_size = size_node.get(common.ATTRIBUTE_VAL)
                if size != spec_size:
                    self.__gen_err(LVL_CONVERSION,
                                   _("conflicting fdisk <size> specified: "
                                     "size was previously defined as "
                                     "%(size)s. Ignoring entry") % \
                                     {"size": spec_size})

    def __is_valid_filesys_mount(self, mount):
        """Check whether this is a valid supported mount point.  Return True
           if supported. Otherwise return False

        """
        if mount not in ["/", "swap"]:
            # We reject everything except for '/' and swap
            self.__gen_err(LVL_UNSUPPORTED,
                           _("unsupported mount point of '%(mount)s' "
                             "specified, mount points other than '/' and "
                             "'swap' are not supported") % {"mount": mount})
            return False
        return True

    def __swap_force_root_pool_creation(self):
        """Force the creation of root pool since it doesn't exist.  Return
           True if pool can be created.  False otherwise.

        """
        if self._root_pool is None:
            # We've got a filesys swap entry but we don't have a root
            # pool created yet.  Do we have enough data to create one?
            if self._rootdisk is None:
                # No we don't have enough information to create a root pool
                self.__gen_err(LVL_UNSUPPORTED,
                               _("swap mount is only supported when preceded "
                                 "by a entry that causes the root pool "
                                 "to be created. For example root_device, "
                                 "boot_device, pool, or filesys with a mount "
                                 "point of '/'"))
                return False
            if self._rootdisk == DEVICE_ANY:
                self._rootdisk = self.__pop_usedisk_entry(DEVICE_ANY)
            zpool = self.__create_root_pool(self._rootdisk_set_by_keyword)
            self.__create_vdev(zpool)
            self.__add_device(self._rootdisk,
                              self._rootdisk_size, self._root_pool_name)
            return True

    def __device_conversion(self, device, allow_any_value,
                            use_rootdisk):
        """Perform conversion on the device specified if necessary.  Return
           None if an error condition occurs (device invalid, device could
           not be converted)

           Arguments:
           device - the device being converted
           allow_any_value - boolean to indicate whether to allow of "any"
                    to be returned
           use_rootdisk - indicates whether to translate "any" using rootdisk
                    if rootdisk is set

        """
        if device == DEVICE_ANY:
            if use_rootdisk:
                device = self.__fetch_rootdisk_slice()
                if device is None:
                    device = DEVICE_ANY
            else:
                device = self.__pop_usedisk__slice_entry(DEVICE_ANY)
            if device == DEVICE_ANY:
                if allow_any_value:
                    return device
                else:
                    self.__gen_err(LVL_CONVERSION,
                                   _("unable to convert 'any' device to "
                                     "physical device. Replace 'any' with "
                                     "actual device name"))
                    return None
        else:
            device = self.__rootdisk_conversion(device,
                                                PREFIX_ROOTDISK_DOT)
            if device is None:
                return None

        if not self.__is_valid_slice(device):
            self.__gen_err(LVL_CONVERSION,
                           _("invalid slice specified: %(device)s ") % \
                             {"device": device})
            return None
        return device

    def __size_conversion(self, keyword, size):
        """Perform the necessary conversion for fileys size.  Returns None
           and generates error if not a valid numeric size.

        """
        match_pattern = SIZE_PATTERN.match(size)
        if match_pattern:
            if match_pattern.group(2) == "":
                # No size specified.  Default size is assumed to be in MB
                size += "mb"
            else:
                # Jumpstart uses m and g not mb and gb like installer wants
                size += "b"
        else:
            self.__gen_err(LVL_CONVERSION,
                           _("invalid size '%(size)s' specified for "
                             "%(key)s") % {"key": keyword, "size": size})
            size = None
        return size

    def __convert_filesys_mirror_entry(self, keyword, values):
        """Perform conversion of filesys mirror entry"""
        length = len(values)
        if length < 4:
            self.__invalid_syntax(keyword)
            return

        mirror_name = values[0]
        if length > 4:
            mount = values[4].lower()
        else:
            #
            # From the Solaris 10 jumpstart documentation
            # If file_system is not specified, unnamed is set by default
            # use this as our default value
            mount = FILESYS_DEFAULT_MOUNT_POINT
        pool_name = DEFAULT_POOL_NAME
        if mount == "swap":
            pool_name += "_swap"
        if mirror_name != "mirror":
            try:
                mirror, pool_name = values[0].split(":")
            except ValueError:
                self.__invalid_syntax(keyword)
                return
        device1 = values[1]
        device2 = values[2]
        size = values[3].lower()

        if length >= 6:
            self.__gen_err(LVL_CONVERSION,
                           _("ignoring optional filesys parameters: "
                             "%(params)s") % {"params": values[5:]})

        if not self.__is_valid_filesys_mount(mount):
            return

        device1 = self.__device_conversion(device=device1,
                                           allow_any_value=False,
                                           use_rootdisk=False)
        if device1 is None:
            return

        device2 = self.__device_conversion(device=device2,
                                           allow_any_value=False,
                                           use_rootdisk=False)
        if device2 is None:
            return

        if size in [SIZE_FREE, SIZE_EXISTING, SIZE_ALL, SIZE_AUTO]:
            self.__unsupported_syntax(keyword,
                                      _("sizes other than a number are not "
                                        "supported for filesys mirror swap"))
            return None

        size = self.__size_conversion(keyword, size)
        if size is None:
            return

        if mount == "/" and self.__root_pool_exists(keyword):
            return

        if not self.__is_valid_mirror(keyword,
                                      [device1, device2], size, mount == "/"):
            return

        if mount == "swap":
            self.__create_filesys_mirrored_swap(pool_name,
                                                device1, device2, size)
            return

        if self._rootdisk is not None:
            # Unset roodisk value since we can't translate a mirror pool
            # rootdisk into the a single device for rootdisk.s0 subsitutions
            self._rootdisk = None
            self._rootdisk = None
            self._rootdisk_set_by_keyword = None

        vdev_name = pool_name + VDEV_SUFFIX
        self.__add_device(device=device1, size=size,
                          in_pool=pool_name,
                          in_vdev=vdev_name, is_swap=None)
        self.__add_device(device=device2, size=size,
                          in_pool=pool_name,
                          in_vdev=vdev_name, is_swap=None)
        zpool = self.__create_root_pool(keyword, pool_name)
        self.__create_vdev(zpool, REDUNDANCY_MIRROR, vdev_name)

    def __convert_filesys_entry(self, keyword, values):
        """Converts the filesys keyword/values from the profile into
        the new xml format

        """
        if self._partitioning == "existing":
            self.__unsupported_syntax(keyword,
                                      _("filesys keyword not supported "
                                        "when partition_type is set to "
                                        "'existing'"))
            return

        #
        # Use the regex pattern '..*:/..*' to determine the # of expressions
        # we have.   If the count greater than 0 then this is a remote
        # file system, otherwise we have a local file system
        if FILESYS_ARG_PATTERN.match(values[0]):
            # Mounting of remote file sys
            #
            # filesys server:path server_address mount_pt_name mount_options
            #
            # Currently not support remote file system so reject entire entry
            self.__unsupported_syntax(keyword,
                                      _("remote file systems are not "
                                        "supported"))
            return

        # We've got a local file system or a mirror (RAID-1) setup
        #
        # filesys slice size file_system optional_parameters
        # filesys mirror[:name]slice [slice] size file_system opt_parameters

        # Invalidate anything with too many or too little args
        length = len(values)
        if length < 2:
            self.__invalid_syntax(keyword)
            return

        if values[0].startswith("mirror"):
            self.__convert_filesys_mirror_entry(keyword, values)
            return

        device = values[0]
        size = values[1].lower()
        if length >= 3:
            mount = values[2].lower()
        else:
            # From the Solaris 10 jumpstart documentation
            # If file_system is not specified, unnamed is set by default
            # use this as our default value
            mount = FILESYS_DEFAULT_MOUNT_POINT
        if length >= 4:
            self.__gen_err(LVL_CONVERSION,
                           _("ignoring optional filesys parameters: "
                             "%(params)s") % {"params": values[3:]})
        if not self.__is_valid_filesys_mount(mount):
            return

        device = self.__device_conversion(device=device,
                                          allow_any_value=(size == SIZE_ALL),
                                          use_rootdisk=(mount == "/"))
        if device is None:
            return

        if size in [SIZE_FREE, SIZE_EXISTING, SIZE_AUTO]:
            self.__unsupported_syntax(keyword,
                                      _("sizes other than a number or all are "
                                        "not supported"))
            return None
        if size != SIZE_ALL:
            size = self.__size_conversion(keyword, size)
            if size is None:
                return

        if mount == "swap":
            self.__create_filesys_swap(device, size)
            return

        if self.__root_pool_exists(keyword):
            return

        if self._rootdisk is not None:
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
            if not self.__rootdisk_slice_conflict_check(keyword, device):
                # Update the device with the rootdisk setting
                # If the user used root_device this will refine the ZFS
                # root pool so it agrees with that setting too
                # This would be equivalent to us processing the root_device
                # line and adding the slice entry to the pool
                self._rootdisk = None

        if self._rootdisk is None:
            # How JumpStart Determines a System's Root Disk
            # 3. If rootdisk is not set and a filesys cwtxdysz size / entry
            #    is specified in the profile, the JumpStart program sets
            #    rootdisk to the disk that is specified in the entry.
            self._root_device = device
            self._rootdisk = self._root_device
            self._rootdisk_set_by_keyword = keyword

        self.__create_root_pool(keyword, DEFAULT_POOL_NAME)
        self.__add_device(device, size, self._root_pool_name)

    def __create_filesys_swap(self, device, size):
        """Create a non ZFS SWAP device"""
        if self._rootdisk == DEVICE_ANY:
            self.__gen_err(LVL_CONVERSION,
                           _("unable to to use specified swap for device "
                             "since the device 'any' was used to create "
                             "the root pool via keyword %(rd_kw)s. Replace "
                             "'any' with actual device name") % \
                             {"rd_kw": self._rootdisk_set_by_keyword})
            return None

        # <disk>
        #   <disk_name name="c6t1d0" name_type="ctd"/>
        #   <slice action="create" name="0" is_swap="true" >
        #       <size value="35000mb" />
        #   </slice>
        # <disk>
        self.__add_device(device=device, size=size,
                          in_pool=None, in_vdev=None, is_swap="true")

    def __create_filesys_mirrored_swap(self, pool_name,
                                       device1, device2, size):
        """Create a mirror swap for devices specified by user"""

        # Check device2 up front.  Since add_device will do this same
        # check for device1 and we want to fail if either device is not
        # valid
        if not self.__is_valid_to_add_slice(device2, size):
            return
        if size == SIZE_ALL:
            self.__gen_err(LVL_CONVERSION,
                           _("filesys mirror with a mount of swap and all is "
                             "not supported. Change size to actual swap size "
                             "desired"))
            return
        vdev_name = pool_name + VDEV_SUFFIX
        self.__add_device(device=device1, size=size,
                          in_pool=pool_name,
                          in_vdev=vdev_name, is_swap=None)
        self.__add_device(device=device2, size=size,
                          in_pool=pool_name,
                          in_vdev=vdev_name, is_swap=None)
        zpool = self.__create_zfs_pool(pool_name)
        self.__create_vdev(zpool, REDUNDANCY_MIRROR, vdev_name)
        if size not in [SIZE_ALL, SIZE_AUTO]:
            self.__create_zvol(parent=zpool, name="swap", use="swap",
                               zvol_size=size)

    def __convert_install_type_entry(self, keyword, values):
        """Converts the install_type keyword/values from the profile into
        the new xml format

        """
        # We've check the install type up front so there's nothing to do here
        pass

    def __convert_locale_entry(self, keyword, values):
        """Converts the install_type keyword/values from the profile into
        the new xml format

        """
        # Convert
        #   locale locale_name
        #
        # to
        #
        # <software name="ips" type="IPS">
        #  <destination>
        #   <image>
        #     <facet set="false">facet.locale.*</facet>
        #     <facet set="true">facet.locale.${locale_name}</facet>
        #     <facet set="true">facet.locale.de_DE</facet>
        #     <facet set="true">facet.locale.en</facet>
        #     <facet set="true">facet.locale.en_US</facet>
        #     <facet set="true">facet.locale.es</facet>
        #   </image>
        #  </destination>
        #  ...
        # </software

        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        if self._image_node is None:
            # We haven't done a local setting operation yet.
            #
            # Find the local settings and delete all the child nodes if
            # they exist, otherwise create the initial structure needed
            #
            software = self.__fetch_solaris_software_node()
            dest = software.find(common.ELEMENT_DESTINATION)
            if dest is None:
                dest = etree.Element(common.ELEMENT_DESTINATION)
                software.insert(0, dest)
            else:
                image = dest.find(common.ELEMENT_IMAGE)
                if image is not None:
                    dest.remove(image)
            self._image_node = etree.SubElement(dest, common.ELEMENT_IMAGE)

            # <facet set="false">facet.locale.*</facet>
            facet = etree.SubElement(self._image_node, common.ELEMENT_FACET)
            facet.set(common.ATTRIBUTE_SET, "false")
            facet.text = FACET_LOCALE_FORM % "*"

        # <facet set="true">facet.locale.${locale}</facet>
        facet = etree.SubElement(self._image_node, common.ELEMENT_FACET)
        facet.set(common.ATTRIBUTE_SET, "true")
        facet.text = FACET_LOCALE_FORM % values[0]

    def __convert_package_entry(self, keyword, values):
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
            self.__unsupported_syntax(keyword,
                _("package install from specified locations is not supported "
                "for SVR4 packages"))
            return
        if (action != "add" and action != "delete"):
            self.__invalid_syntax(keyword)
            return
        if action == "add":
            self.__add_software_data(package,
                                     SOFTWARE_INSTALL)
        elif action == "delete":
            self.__add_software_data(package,
                                     SOFTWARE_UNINSTALL)

    def __convert_pool_entry(self, keyword, values):
        """Converts the pool keyword/values from the profile into
        the new xml format

        """
        # pool <pool name> <pool size> <swap size> <dump size>
        #                                       <slice> | mirror [<slice>]+
        #
        # Input:        ${1}    - pool name
        #               ${2}    - pool size (num, existing, auto)
        #               ${3}    - swap size (num, auto)
        #               ${4}    - dump size (num, auto)
        #               ${5}    - (mirror, <slice>, rootdisk.s??, any)
        #                .      - (<slice>, rootdisk.s??, any)
        length = len(values)
        if length < 5:
            self.__invalid_syntax(keyword)
            return

        pool_name = values[0]
        # Pool name must be between 0-30 characters
        name_length = len(pool_name)
        if name_length == 0 or name_length > 30:
            self.__gen_err(LVL_CONVERSION,
                           _("invalid pool name of '%(pool)s': must be at "
                             "least 1 character and no more than 30 "
                             "characters in length") % {"pool": pool_name})
            return
        # Update the name that we are using for the root pool
        self._root_pool_name = pool_name

        pool_size = values[1].lower()
        if pool_size == SIZE_EXISTING:
            self.__unsupported_syntax(keyword,
                                      _("pool sizes other than a number or "
                                        "auto are not supported"))
            return None
        elif pool_size != SIZE_AUTO:
            pool_size = self.__size_conversion("<pool_size>", pool_size)
            if pool_size is None:
                return

        swap_size = values[2].lower()
        noswap = "false"
        if swap_size == "0":
            swap_size = None
            noswap = "true"
        elif swap_size != SIZE_AUTO:
            swap_size = self.__size_conversion("<swap_size>", swap_size)
            if swap_size is None:
                return

        dump_size = values[3].lower()
        nodump = "false"
        if dump_size == "0":
            dump_size = None
            nodump = "true"
        elif dump_size != SIZE_AUTO:
            dump_size = self.__size_conversion("<dump_size>", dump_size)
            if dump_size is None:
                return

        if values[4] == "mirror":
            # Mirror must have at least 2 slices
            mirror = True
            if length < 6:
                self.__invalid_syntax(keyword)
                return
            redundancy = "mirror"
            devices = values[5:]
        else:
            mirror = False

            # Non mirror can only have 1 slice specified
            if length > 5:
                self.__invalid_syntax(keyword)
                return
            redundancy = "none"
            devices = values[4:]

        updated_list = list()
        for device in devices:
            allow_any = mirror == False and pool_size == SIZE_AUTO
            update_device = \
                self.__device_conversion(device=device,
                                         allow_any_value=allow_any,
                                         use_rootdisk=(mirror == False))
            if update_device is None:
                return
            updated_list.append(update_device)
        devices = updated_list

        # Check for any conflicts with root_device and boot_device
        # pool will always override these settings
        if mirror:
            if not self.__is_valid_mirror(keyword, devices, pool_size, True):
                return
        else:
            # Check for conditions like
            #
            # root_device cxtxdxsx
            # pool p_abc auto auto auto cxtxdxsx
            #
            # or
            #
            # boot_device cxtxdx
            # pool p_abc auto auto auto cxtxdxsx
            #
            # Warning message has been outputed
            self.__rootdisk_slice_conflict_check(keyword, devices[0])

        zpool = self.__create_root_pool(keyword, self._root_pool_name,
                                        noswap, nodump)
        self.__create_vdev(zpool, redundancy)
        for device in devices:
            self.__add_device(device, pool_size, self._root_pool_name)

        if swap_size is not None and swap_size != SIZE_AUTO:
            self.__create_zvol(parent=zpool, name="swap", use="swap",
                                zvol_size=swap_size)
        if dump_size is not None and dump_size != SIZE_AUTO:
            self.__create_zvol(parent=zpool, name="dump", use="dump",
                                zvol_size=dump_size)
        if not mirror and self._rootdisk is None:
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

    def __convert_system_type_entry(self, keyword, values):
        """Processes the system_type entry in profile and flags any
        value other than standalone as unsupported value

        """
        length = len(values)
        if length > 1 or length == 0:
            self.__invalid_syntax(keyword)
            return
        if values[0] != "standalone":
            self.__unsupported_value(keyword, values[0])

    def __fetch_disk_node(self, disk_name):
        """Returns the <disk> node for the disk 'disk_name'"""
        diskname_node = self.__fetch_diskname_node(disk_name)
        if diskname_node is None:
            return None
        return diskname_node.getparent()

    def __fetch_diskname_node(self, disk_name):
        """Returns the diskname node with the disk_name of 'disk_name'"""
        xpath = "./disk/disk_name[@name='%s']"
        return fetch_xpath_node(self._target, xpath % disk_name)

    def __fetch_pool(self, pool_name):
        """Fetch the ZFS pool with the specified name if it exists"""
        xpath = "./logical/zpool[@name='%s']" % pool_name
        return fetch_xpath_node(self._target, xpath)

    def __fetch_root_pool(self):
        """Fetch the ZFS root pool"""
        xpath = "./logical/zpool[@is_root='true']"
        return fetch_xpath_node(self._target, xpath)

    def __fetch_rootdisk(self):
        """Fetch the rootdisk device value"""
        if self._rootdisk is not None:
            if self._rootdisk == DEVICE_ANY:
                self._rootdisk = self.__pop_usedisk_entry(DEVICE_ANY)
        return self._rootdisk

    def __fetch_rootdisk_slice(self):
        """Fetch the rootdisk device value.  Convert it to slice form if not
           currently in the slice form.

        """
        slice_name = self.__fetch_rootdisk()
        if slice_name not in [None, DEVICE_ANY]:
            # rootdisk may or may not be in the slice form already
            if not self.__is_valid_slice(slice_name):
                return slice_name + "s0"
        return slice_name

    def __fetch_slice_insertion_point(self, disk_name):
        """Return the insertion point for adding slices to the specified
           disk.  On sparc this is <disk> on x86 this is <partition>
           Returns None is disk doesn't exist.

        """
        disk_node = self.__fetch_disk_node(disk_name)
        if disk_node is None:
            return None
        if self._arch in [None, common.ARCH_X86]:
            # We return the partition
            xpath = "./partition[@action='create'][@type='191']"
            return fetch_xpath_node(disk_node, xpath)
        return disk_node

    def __pop_usedisk_entry(self, default_value=None):
        """Return the 1st device off the usedisk stack if one exists.
           Otherwise return default_value

        """
        if len(self._usedisk):
            return self._usedisk.pop(0)
        return default_value

    def __pop_usedisk__slice_entry(self, default_value=None):
        """Return the 1st device off the usedisk stack in slice form
           if one exists. Otherwise return default_value

        """
        if len(self._usedisk):
            return self._usedisk.pop(0) + "s0"
        return default_value

    def __store_boot_device_entry(self, keyword, values):
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
            self.__duplicate_keyword(keyword, values)
            return
        length = len(values)
        if length > 2 or length == 0:
            self.__invalid_syntax(keyword)
            return

        device = values[0].lower()
        if device == "existing":
            self.__unsupported_value(_("<device>"), device)
            return

        if device != DEVICE_ANY:
            if not self.__is_valid_device_name(device) and \
               not self.__is_valid_slice(device):
                self.__gen_err(LVL_CONVERSION,
                               _("invalid device specified: %(device)s") % \
                                 {"device": device})
                return

            # The device specified is valid.  Set the architecure for the
            # device based on the device value specified. If a valid slice is
            # specified for boot device the architecuture is SPARC.
            # Otherwise it's x86
            if self.__is_valid_slice(device):
                if not self.__change_arch(common.ARCH_SPARC):
                    return
            else:
                if not self.__change_arch(common.ARCH_X86):
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
                self.__gen_err(LVL_UNSUPPORTED,
                               _("ignoring eeprom 'update' setting, as "
                                 "this action is not supported"))
            else:
                self.__invalid_syntax(keyword)
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
                self.__gen_err(LVL_CONVERSION,
                               _("conflicting definition: rootdisk previously "
                                 "defined as '%(root_device)s' via keyword "
                                 "'%(rd_kw)s', ignoring entry") % \
                                 {"root_device": self._root_device,
                                  "rd_kw": self._rootdisk_set_by_keyword})
                return
        else:
            self._rootdisk = device
        self._rootdisk_set_by_keyword = keyword
        self._boot_device = device

    def  __store_root_device_entry(self, keyword, values):
        """Set the profile root device value that we'll use if root device
        is specified by the user

        """
        # root_device <slice>
        if self._root_device is not None:
            self.__duplicate_keyword(keyword, values)
            return
        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        if not self.__is_valid_slice(values[0]):
            self.__gen_err(LVL_CONVERSION,
                           _("invalid device specified: %(device)s") % \
                             {"device": values[0]})
            return

        self._root_device = values[0]
        if self._boot_device is not None:
            # Do we have a conflict?
            cmp_device = self.__device_name_conversion(self._boot_device)
            if self._root_device != cmp_device:
                self.__gen_err(LVL_CONVERSION,
                               _("translation conflict between devices "
                                 "specified for boot_device and root_device, "
                                 "using root_device define of "
                                 "'%(root_device)s', ignoring define of "
                                 "boot_device of '%(boot_device)s'") % \
                                 {"root_device": self._root_device,
                                  "boot_device": self._boot_device})
        self._rootdisk = self._root_device
        self._rootdisk_set_by_keyword = keyword

    def  __store_partitioning_entry(self, keyword, values):
        """Set the profile partitioning value that we'll use if fdisk all
        or usedisk is specified by the user later

        """
        # partitioning <type> where type is default, existing or explicit
        if self._partitioning is not None:
            self.__duplicate_keyword(keyword, values)
            return
        if len(values) != 1:
            self.__invalid_syntax(keyword)
            return
        self._partitioning = values[0].lower()
        if self._partitioning not in [PARTITIONING_DEFAULT,
                                      PARTITIONING_EXPLICIT]:
            self.__gen_err(LVL_UNSUPPORTED,
                           _("unsupported profile, partitioning must be "
                             "'default' or 'explicit'"))
            self._report.conversion_errors = None
            self._tree = None
            raise ValueError

    def __store_usedisk_entry(self, keyword, values):
        """Store the usedisk devices specified by the user.  We'll use these
        to create the root pool if paritioning default is specified.

        """
        #
        # usedisk <device> [<device]
        if len(values) == 0 or len(values) > 2:
            self.__invalid_syntax(keyword)
            return
        for value in values:
            if self.__is_valid_device_name(value):
                self._usedisk.append(value)
            else:
                self.__gen_err(LVL_CONVERSION,
                               _("invalid device specified: %(device)s") % \
                                 {"device": value})
                return

    def __is_valid_install_type(self, keyword, values):
        """The only profiles that are supported are install profiles
        The jumpstart scripts require it as the first keyword in the
        file.  If the install_type is not initial_install reject
        the entire profile

        """
        if keyword != "install_type":
            self.__gen_err(LVL_PROCESS,
                           _("invalid profile, first specified keyword must "
                             "be install_type, got '%(keyword)s'") % \
                             {"keyword": keyword})
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            self._tree = None
            return False
        install_type = values[0].lower()
        if install_type in ["upgrade",
                            "flash_install", "flash_upgrade"]:
            self.__unsupported_value(keyword, values[0])
            self._report.conversion_errors = None
            self._tree = None
            return False
        if install_type != "initial_install":
            self.__invalid_syntax(keyword)
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            self._tree = None
            return False
        return True

    @property
    def tree(self):
        """Returns the xml tree associated with this object"""
        return self._tree

    def fetch_tree(self, arch):
        """Convert the current tree to the specified architecute

        Supported architecutres are:
            common.ARCH_GENERIC
            common.ARCH_SPARC
            common.ARCH_X86

        Conversion not support:
            SPARC to X86

        """
        if arch not in [common.ARCH_GENERIC, common.ARCH_X86,
                         common.ARCH_SPARC]:
            # Programming error
            raise ValueError(-("unsupported architecture specified"))
        if arch == self._arch or self._arch == common.ARCH_GENERIC:
            # Tree is in the proper format for the architecture requested
            return self._tree
        if arch == common.ARCH_X86:
            if self._arch in [None, common.ARCH_X86]:
                # Tree is in the proper format for the architecture requested
                return self._tree
        if arch == common.ARCH_SPARC:
            if self._arch in [None, common.ARCH_X86]:
                # Tree is not in the proper format.  A conversion is necessary
                return self.__fetch_sparc_from_x86_tree(self._tree)

        # Programming error
        raise ValueError(_("Conversion from architecute %(req_arch) to "
                           "%(cur_arch)s is not supported") %
                               {"req_arch": arch,
                                "cur_arch": self._arch})

    def __fetch_sparc_from_x86_tree(self, tree):
        """Converts a x86 manifest xml tree to a sparc manifest xml tree"""
        clone = common.tree_copy(tree)
        # The only difference between an x86 based xml tree and a sparc
        # tree is currently the <partition> node.  Look for the
        # <partition> node and remove it, if it exists.
        xpath = "/auto_install/ai_instance/target"
        target = fetch_xpath_node(clone, xpath)
        for disk in target.findall(common.ELEMENT_DISK):
            # To convert a x86 manifest profile to a sparc we're simply
            # going to take the children slices of the partition and move
            # them up as a child of <disk> and then delete the <partition>
            # node
            partition = disk.find(common.ELEMENT_PARTITION)
            if partition is not None:
                for slice_node in partition.findall(common.ELEMENT_SLICE):
                    partition.remove(slice_node)
                    disk.append(slice_node)
                disk.remove(partition)
        return clone

    def __fetch_keys(self):
        """Fetch the keys that we need to process from the profile dictionary

        """
        if self.prof_dict is None:
            keys = {}
        else:
            # Sort the keys based on the line #
            keys = sorted(self.prof_dict.keys())
        if len(keys) == 0:
            # There's nothing to convert.  This is a valid condition if
            # the file couldn't of been read for example
            self._report.conversion_errors = None
            self._report.unsupported_items = None
            return None
        return keys

    def __find_xml_entry_points(self):
        """Find and set the global xml entry points"""
        self._target = self._ai_instance.find(common.ELEMENT_TARGET)
        if self._target is not None:
            # Delete the target entry from the default manifest
            self._ai_instance.remove(self._target)

        # Create <target> and insert immediately after
        # <ai_instance> node
        self._target = etree.Element(common.ELEMENT_TARGET)
        self._ai_instance.insert(0, self._target)

    profile_conversion_dict = {
        "boot_device": None,
        "bootenv": __unsupported_keyword,
        "client_arch": __unsupported_keyword,
        "client_swap": __unsupported_keyword,
        "cluster": __unsupported_keyword,
        "dontuse": __unsupported_keyword,
        "fdisk": __convert_fdisk_entry,
        "filesys": __convert_filesys_entry,
        "geo": __unsupported_keyword,
        "install_type": __convert_install_type_entry,
        "locale": __convert_locale_entry,
        "num_clients": __unsupported_keyword,
        "package": __convert_package_entry,
        "partitioning": __store_partitioning_entry,
        "pool": __convert_pool_entry,
        "root_device": None,
        "system_type": __convert_system_type_entry,
        "usedisk": None
        }

    def __process_profile(self):
        """Process the profile by taking all keyword/values pairs and
        generating the associated xml for the key value pairs

        """

        keys = self.__fetch_keys()
        if keys is None:
            self._tree = None
            return

        check_for_install_type = True
        pool_obj = None
        line_num = 0
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
        #        o Check for the keyword "partitioning" and store for later use
        #        o Check for keyword "usedisk" and store for later use
        #   2    o Process the pool keyword.  If used this is the closest
        #          parallel to how the new installer uses so we give this
        #          the highest priority in what we use to generate the ZFS
        #          root pool
        #   3    o If partition value is "default" create ZFS root pool
        #   4    o Process the remaining keywords in the profile
        #
        for key in keys:
            key_value_obj = self.prof_dict[key]
            if key_value_obj is None:
                raise KeyError

            keyword = key_value_obj.key
            values = key_value_obj.values
            line_num = key_value_obj.line_num

            if line_num is None or values is None or keyword is None:
                raise KeyError(_("Got None value, line_num=%(lineno)s "
                               "values=%(values)s keyword=%(keywords)s") %
                               {"lineno": str(line_num),
                                "values": str(values),
                                "keyword": str(keyword)})

            self._extra_log_params[LOG_KEY_LINE_NUM] = line_num
            if check_for_install_type:
                # The 1st keyword in the profile must be install_type,
                # if it's not we reject the profile
                if not self.__is_valid_install_type(keyword, values):
                    self._tree = None
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
                self.__store_root_device_entry(keyword, values)
                del self.prof_dict[key]
            elif keyword == "boot_device":
                self.__store_boot_device_entry(keyword, values)
                del self.prof_dict[key]
            elif keyword == "pool":
                del self.prof_dict[key]
                if pool_obj is not None:
                    self.__duplicate_keyword(keyword, values)
                else:
                    pool_obj = key_value_obj
            elif keyword == "partitioning":
                try:
                    self.__store_partitioning_entry(keyword, values)
                    del self.prof_dict[key]
                except ValueError:
                    return
            elif keyword == "usedisk":
                self.__store_usedisk_entry(keyword, values)
                del self.prof_dict[key]
            elif keyword == "fdisk":
                if not self.__change_arch(common.ARCH_X86):
                    return

        self.__find_xml_entry_points()

        # Next create the zfs pool if the pool keyword was encountered
        # With the new installer we only support creating a single zfs
        # root pool.  The pool keyword takes precidence over any other
        # settings the user may have made
        if pool_obj is not None:
            self._extra_log_params[LOG_KEY_LINE_NUM] = pool_obj.line_num
            self.__convert_pool_entry(pool_obj.key, pool_obj.values)

        # Now process the remaining keys
        keys = sorted(self.prof_dict.keys())
        for key in keys:
            key_value_obj = self.prof_dict[key]
            keyword = key_value_obj.key.lower()
            values = key_value_obj.values
            self._extra_log_params[LOG_KEY_LINE_NUM] = key_value_obj.line_num
            try:
                function_to_call = self.profile_conversion_dict[keyword]
            except KeyError:
                self.__unsupported_keyword(keyword, values)
            else:
                if function_to_call is not None:
                    function_to_call(self, keyword, values)

        # If the root pool is not created attempt to create it now
        if self._root_pool is None:
            if self._rootdisk is not None:
                # rootdisk is set create the pool using the specified rootdisk
                zpool = self.__create_root_pool(self._rootdisk_set_by_keyword)
                self.__create_vdev(zpool)
                self.__add_device(self._rootdisk,
                                  self._rootdisk_size, self._root_pool_name)

            elif self._partitioning is not None and \
                 self._partitioning == PARTITIONING_DEFAULT:
                # Root pool doesn't exist.  User specified partitioning
                # default.  Go ahead and create it now
                zpool = self.__create_root_pool("partitioning")
                self.__create_vdev(zpool)
                if len(self._usedisk) == 0:
                    # No usedisk entries where specified.  Add device
                    # based on "any"
                    self.__add_device(DEVICE_ANY)

        if self._root_pool is not None:
            # Add any additional disks that the user may of told use to
            # use to the root pool as long as it's not a mirrored pool
            xpath = "./vdev[@redundancy='mirror']"
            vdev_mirror = fetch_xpath_node(self._root_pool, xpath)
            if vdev_mirror is None:
                for device in self._usedisk:
                    self.__add_device(device, None, self._root_pool_name)

        # Since we auto create the <target> node by default we want
        # to make sure the node has children before we finish up.
        # If there are no children then we want to delete the node
        if len(self._target) == 0:
            # No children.  Delete target node
            self._ai_instance.remove(self._target)

        # Check to determine if we have any children nodes
        # If we don't and we have errors then clear the xml
        # tree so we don't have a empty tree hierachy that
        # results in a <auto_install/>
        # Conversely though if all that's in the file is
        # initial_install and we have no errors then we should
        # create a file even if it's just <auto_install/>
        # That technically won't have any meaning to the new jumpstart
        # engine though
        if len(self._ai_instance) == 0 and self._report.has_errors():
            self._tree = None
        elif self._root_pool is None:
            if line_num is None:
                line_num = 1
            else:
                line_num += 1
            self._extra_log_params[LOG_KEY_LINE_NUM] = line_num
            # Create the root pool, but tell AI to choose the disk
            zpool = self.__create_root_pool("default")

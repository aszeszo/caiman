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
"""
Utility class

"""

import gettext
import logging
import os
import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from lxml import etree
from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser
from xml.dom import minidom


ATTRIBUTE_ACTION = "action"
ATTRIBUTE_ENABLED = "enabled"
ATTRIBUTE_IS_ROOT = "is_root"
ATTRIBUTE_NAME = "name"
ATTRIBUTE_NAME_TYPE = "name_type"
ATTRIBUTE_REDUNDANCY = "redundancy"
ATTRIBUTE_TYPE = "type"
ATTRIBUTE_VAL = "val"
ATTRIBUTE_VALUE = "value"
ATTRIBUTE_VERSION = "version"

ELEMENT_AI_CRITERIA = "ai_criteria"
ELEMENT_AI_CRITERIA_MANIFEST = "ai_criteria_manifest"
ELEMENT_AI_DEVICE_PARTITIONING = "ai_device_partition"
ELEMENT_AUTO_INSTALL = "auto_install"
ELEMENT_DISK = "disk"
ELEMENT_DISK_NAME = "disk_name"
ELEMENT_DUMP = "dump"
ELEMENT_INSTANCE = "instance"
ELEMENT_NAME = "name"
ELEMENT_PARTITION = "partition"
ELEMENT_PROPERTY = "property"
ELEMENT_PROPERTY_GROUP = "property_group"
ELEMENT_PROPVAL = "propval"
ELEMENT_RANGE = "range"
ELEMENT_SC_EMBEDDED_MANIFEST = "sc_embedded_manifest"
ELEMENT_SERVICE_BUNDLE = "service_bundle"
ELEMENT_SERVICE = "service"
ELEMENT_SIZE = "size"
ELEMENT_SLICE = "slice"
ELEMENT_SOFTWARE = "software"
ELEMENT_SOFTWARE_DATA = "software_data"
ELEMENT_SWAP = "swap"
ELEMENT_TARGET = "target"
ELEMENT_TARGET_DEVICE = "target_device"
ELEMENT_VALUE = "value"
ELEMENT_VALUE_NODE = "value_node"
ELEMENT_VDEV = "vdev"
ELEMENT_ZPOOL = "zpool"
ELEMENT_ZVOL = "zvol"

DEFAULT_XML_FILENAME = "/usr/share/auto_install/default.xml"
DEFAULT_DTD_FILENAME = "/usr/share/auto_install/ai.dtd"
RULES_FILENAME = "rules"
SYSIDCFG_FILENAME = "sysidcfg"

ERR_VAL_MODID = "js2ai-validation"

_ = gettext.translation("js2ai", "/usr/share/locale", fallback=True).gettext


def fetch_xpath_node(start_node, path):
    """Perform a xpath search from start_node and return first node found.
    Returns None if none found

    """
    nodes = start_node.xpath(path)
    if len(nodes) != 0:
        return nodes[0]
    return None


def pretty_print(tree):
    """Pretty print the xml tree"""
    #
    # For some reason the tree we are generating will not output
    # correctly with etree.tostring(pretty_print).  This appears to be
    # related to the embedded commented xml doc contained within the document
    # The resulting document will only be partically pretty printed and will
    # contain a large block of unseperated entries like:
    #
    #  <node1><node2><node3 name="xxx" is_root="true">
    #
    # To solve this issue we reparse the document with minidom
    #
    rough_string = etree.tostring(tree, pretty_print=True)
    reparsed = minidom.parseString(rough_string)
    rough_string = reparsed.toprettyxml(indent="  ", encoding="utf-8")

    # After we reparse it with the mini dom, the new xml document will contain
    # a bunch of unwanted blank lines.  Strip them out.   This will have
    # the side effect of stripping out any blank lines in the comment sections
    return os.linesep.join([s for s in rough_string.splitlines() if s.strip()])


def write_xml_data(xml_tree, dest_dir, filename):
    """Write out the xml document to a file"""
    if dest_dir is not None:
        output_file = os.path.join(dest_dir, filename)
        if not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir)
            except IOError as msg:
                raise IOError(_("Failed to create directory: %s\n" % msg))
    else:
        output_file = filename
    with open(output_file, "w") as file_handle:
        if xml_tree is not None:
            file_handle.write(pretty_print(xml_tree))


def validate_manifest(profile_name, manifest_path, manifest_filename,
                      conversion_report, verbose):
    """Validate the generated manifest based on the default dtd"""
    is_valid = True

    if verbose:
        print _("Validating manifest %(manifest)s" % \
              {"manifest": manifest_filename})
    try:
        # set up then parse the manifest and the allow the manifest
        # parser to validate the generated manifest based on the default dtd.
        if os.access(manifest_path, os.F_OK):
            manifest = os.path.join(manifest_path, manifest_filename)
            mani_parser = ManifestParser("manifest-parser", manifest,
                                         validate_from_docinfo=False,
                                         dtd_file=DEFAULT_DTD_FILENAME)
            logging.raiseExceptions = False
            mani_parser.parse(doc=None)
            logging.raiseExceptions = True
        else:
            raise IOError(
                _("manifest file does not exist: %s\n") % manifest)

    except ManifestError, err:
        is_valid = False
        log_name, ending = manifest_filename.rsplit(".", 1)
        log_name += "_validation" + ".log"
        log_file = os.path.join(manifest_path, log_name)
        err_lines = str(err).split(" : ")
        try:
            if os.access(log_file, os.F_OK):
                os.remove(log_file)
            with open(log_file, "w+") as f_handle:
                f_handle.write(_("NOTE: The errors outputed in this file must "
                                 "be manually corrected before the resulting "
                                 "manifest file can be used by the Solaris "
                                 "automated installer. For information on the "
                                 "generated errors see installadm(1M) man "
                                 "page.\n\nOnce the errors have been corrected"
                                 " you can validate your changes via:\n\n"
                                 "# js2ai -V %(manifest_file)s\n\n") % \
                                 {"manifest_file": manifest})
                f_handle.write(_("Validation Errors:\n"))
                for line in err_lines:
                    conversion_report.add_validation_error()
                    f_handle.write(("%s\n") % line)
        except IOError:
            # We failed to create the log file, print the errors to the screen
            err(_("failed to create log file: %(logfile)" % \
                 {"logfile": logfile}))
            sys.stderr.write(_("Manifest validation failed:\n"))
            for line in err_lines:
                sys.stderr.write(line)

    if not is_valid:
        # Store the error information in the error service
        error_info = errsvc.ErrorInfo(ERR_VAL_MODID, liberrsvc.ES_ERR)
        error_info.set_error_data(liberrsvc.ES_DATA_FAILED_AT,
                                  "ManifestParser")
        error_info.set_error_data(liberrsvc.ES_DATA_FAILED_STR,
                                 (_("%(profile)s: manifest validation of "
                                    "%(manifest)s failed. For details see "
                                    "%(logf)s\n") % \
                                    {"profile": profile_name,
                                     "manifest": manifest,
                                     "logf": log_file}))

    return is_valid


class ProfileData(object):
    """Contains the contents of a jumpstart profile"""

    def __init__(self, name):
        self._name = name
        self._data = {}
        self._conv_report = None

    @property
    def name(self):
        """Name of this profile"""
        return self._name

    @property
    def data(self):
        """Dictionary of keys & values contained in profile.  May be None
        if the profile could not be read.  The key is the line # in the file
        """
        return self._data

    @property
    def conversion_report(self):
        """Report of all errors encountered during processing"""
        return self._conv_report

    @conversion_report.setter
    def conversion_report(self, report):
        """Set the conversion report"""
        self._conv_report = report

    def __str__(self):
        """Return object in print friendly form"""
        return "name " + str(self.name) + ", data=" + str(self.data) +\
            ", values: " + str(self.conversion_report)


class KeyValues(object):
    """Key/Value object"""

    def __init__(self, key, values, line_num):
        self._key = key
        self._values = values
        self._line_num = line_num

    @property
    def key(self):
        """Return string, key identifer for object"""
        return self._key

    @property
    def values(self):
        """Return List of string of the values associated with the key"""
        return self._values

    @property
    def line_num(self):
        """Return the line # that this rule key value combination was in the
        rule file
        """
        return self._line_num

    def __str__(self):
        """Return object in print friendly form"""
        return "line " + str(self.line_num) + ", key=" + str(self.key) +\
            ", values: " + str(self.values)


class ConversionReport(object):
    """Contains the error counts that occurred during the various phases of
    the conversion process.
    process errors refers to errors that occur when the various entities are
    read in
    conversion errors refers to errors that occur when converting items from
    the Solaris 10 nomiclature to Solaris 11
    unsupported items refers to items that can not be converted.

    NOTE: conversion errors and unsupported items will
    have a value of None if there is a processing error that prevents
    the file from being read
    """

    def __init__(self, process_errs=0, conversion_errs=0, unsupported_items=0,
                 validation_errs=0):
        self._process_errs = process_errs
        self._conversion_errs = conversion_errs
        self._unsupported_items = unsupported_items
        self._validation_errs = validation_errs

    def add_process_error(self):
        """Increments the # of processing errors by 1"""
        if self._process_errs is None:
            self._process_errs = 1
        else:
            self._process_errs += 1

    def add_conversion_error(self):
        """Increments the # of conversion errors by 1"""
        if self._conversion_errs is None:
            self._conversion_errs = 1
        else:
            self._conversion_errs += 1

    def add_unsupported_item(self):
        """Increments the # of unsupported items by 1"""
        if self._unsupported_items is None:
            self._unsupported_items = 1
        else:
            self._unsupported_items += 1

    def add_validation_error(self):
        """Increments the # of validation errors by 1"""
        if self._validation_errs is None:
            self._validation_errs = 1
        else:
            self._validation_errs += 1

    @property
    def process_errors(self):
        """Returns the # of process errors"""
        return self._process_errs

    @property
    def conversion_errors(self):
        """Returns the # of conversion errors"""
        return self._conversion_errs

    @property
    def unsupported_items(self):
        """Returns the # of unsupported items"""
        return self._unsupported_items

    @property
    def validation_errors(self):
        """Returns the # of validation errors"""
        return self._validation_errs

    @process_errors.setter
    def process_errors(self, error_count):
        """Set the # of processing errors to error_count"""
        self._process_errs = error_count

    @conversion_errors.setter
    def conversion_errors(self, error_count):
        """Set the # of conversion errors to error_count"""
        self._conversion_errs = error_count

    @unsupported_items.setter
    def unsupported_items(self, unsupported):
        """Set the # of unsupported items to unsupported"""
        self._unsupported_items = unsupported

    @validation_errors.setter
    def validation_errors(self, error_count):
        """Set the # of validation_errs to error_count"""
        self._validation_errs = error_count

    def error_count(self):
        """Return the # of errors associate with this report"""
        errs = 0
        if self._process_errs is not None:
            errs = self._process_errs
        if self._conversion_errs is not None:
            errs += self._conversion_errs
        if self._unsupported_items is not None:
            errs += self._unsupported_items
        if self._validation_errs is not None:
            errs += self._validation_errs
        return errs

    def has_errors(self):
        """Returns boolean, True if there are any process errors, conversion
        errors, or unsupported items
        """
        if self._process_errs or self._conversion_errs \
            or self._unsupported_items or self._validation_errs:
            return True
        else:
            return False

    def __str__(self):
        return ("process errors: %(process)s, "
               "conversion errors: %(conversion)s, "
               "unsupported items: %(unsupported)s "
               "validation errors: %(validation)s " % \
                {"process": str(self.process_errors),
                 "conversion": str(self.conversion_errors),
                 "unsupported": str(self.unsupported_items),
                 "validation": str(self.validation_errors)})

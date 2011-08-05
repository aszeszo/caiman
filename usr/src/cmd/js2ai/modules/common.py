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
import shutil
import sys

from lxml import etree
from solaris_install.manifest import ManifestError
from solaris_install.manifest.parser import ManifestParser
from xml.dom import minidom
from StringIO import StringIO


ATTRIBUTE_ACTION = "action"
ATTRIBUTE_CREATE = "create"
ATTRIBUTE_ENABLED = "enabled"
ATTRIBUTE_FORCE = "force"
ATTRIBUTE_IN_VDEV = "in_vdev"
ATTRIBUTE_IN_ZPOOL = "in_zpool"
ATTRIBUTE_IS_ROOT = "is_root"
ATTRIBUTE_IS_SWAP = "is_swap"
ATTRIBUTE_KEY = "key"
ATTRIBUTE_NAME = "name"
ATTRIBUTE_NAME_TYPE = "name_type"
ATTRIBUTE_NOSWAP = "noswap"
ATTRIBUTE_NODUMP = "nodump"
ATTRIBUTE_PART_TYPE = "part_type"
ATTRIBUTE_REDUNDANCY = "redundancy"
ATTRIBUTE_SET = "set"
ATTRIBUTE_TYPE = "type"
ATTRIBUTE_USE = "use"
ATTRIBUTE_VAL = "val"
ATTRIBUTE_VALUE = "value"
ATTRIBUTE_VERSION = "version"
ATTRIBUTE_WHOLE_DISK = "whole_disk"

ELEMENT_AI_CRITERIA = "ai_criteria"
ELEMENT_AI_CRITERIA_MANIFEST = "ai_criteria_manifest"
ELEMENT_AI_DEVICE_PARTITIONING = "ai_device_partition"
ELEMENT_AI_INSTANCE = "ai_instance"
ELEMENT_AUTO_INSTALL = "auto_install"
ELEMENT_DESTINATION = "destination"
ELEMENT_DISK = "disk"
ELEMENT_DISK_KEYWORD = "disk_keyword"
ELEMENT_DISK_NAME = "disk_name"
ELEMENT_DUMP = "dump"
ELEMENT_FACET = "facet"
ELEMENT_HOST_LIST = "host_list"
ELEMENT_IMAGE = "image"
ELEMENT_INSTANCE = "instance"
ELEMENT_LOGICAL = "logical"
ELEMENT_NAME = "name"
ELEMENT_NET_ADDRESS_LIST = "net_address_list"
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
ELEMENT_SOURCE = "source"
ELEMENT_SWAP = "swap"
ELEMENT_TARGET = "target"
ELEMENT_VALUE = "value"
ELEMENT_VALUE_NODE = "value_node"
ELEMENT_VDEV = "vdev"
ELEMENT_ZPOOL = "zpool"
ELEMENT_ZVOL = "zvol"

ARCH_X86 = "x86"
ARCH_SPARC = "sparc"
ARCH_GENERIC = "generic"

# The ai manifest to merge our changes into
DEFAULT_AI_FILENAME = "/usr/share/auto_install/manifest/default.xml"
DEFAULT_AI_DTD_FILENAME = "/usr/share/install/ai.dtd"
DEFAULT_SC_PROFILE_DTD_FILENAME = "/usr/share/lib/xml/dtd/service_bundle.dtd.1"
RULES_FILENAME = "rules"
SYSIDCFG_FILENAME = "sysidcfg"
SC_PROFILE_FILENAME = "sc_profile.xml"

ERR_VAL_MODID = "js2ai-validation"

# LOGGER is for logging all processing, conversion, unknown items, warning,
# and validation errors so that the user can review the failures and take
# steps to fix them
LOGGER = logging.getLogger('js2ai')

# keys used in the formating string for log file output
LOG_KEY_FILE = "file"
LOG_KEY_LINE_NUM = "line_num"

LVL_PROCESS = logging.ERROR + 1
LVL_UNSUPPORTED = logging.ERROR + 2
LVL_CONVERSION = logging.ERROR + 3
LVL_VALIDATION = logging.ERROR + 4
LVL_WARNING = logging.WARNING

_ = gettext.translation("js2ai", "/usr/share/locale", fallback=True).gettext


def err(msg):
    """Output standard error message"""
    # Duplicate the syntax of the parser.error
    sys.stderr.write("%(prog)s: error: %(msg)s\n" %
                     {"prog": os.path.basename(sys.argv[0]), "msg": msg})


def generate_error(log_lvl, report, message, extra_log_params):
    """Generate log message at specified level.  Increment error count

       Arguments:
       log_lvl - the log level
       report - the conversion report to add the error to
       message - the message to log
       extra_log_params - a dictionary that contains the key LOG_KEY_FILE
                 and LOG_KEY_LINE_NUM
    """
    LOGGER.log(log_lvl, message, extra=extra_log_params)
    report.generate_error(log_lvl)


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
    # related to the embedded comments doc contained within the document
    # The resulting document will only be partically pretty printed and will
    # contain a large block of unseparated entries like:
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


def tree_copy(tree):
    """Return a copy of the passed in xml tree"""
    #
    # Ideally we'd use deepcopy() and make a copy of the tree.
    # deepcopy however, does not preserve the DOCTYPE entry
    copy = pretty_print(tree)
    return etree.parse(StringIO(copy))


def remove(path):
    """Remove specified file or directory.  If path specified is not a file or
       a directory an IOError is raised since files and directories are the
       only types of output files generated by js2ai

    """
    if os.path.exists(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
            else:
                raise IOError(_("not a file or directory"))
        except (IOError, OSError) as msg:
            # Regardless of what error we get here
            # just return an IOError.  The main() catches this and
            # treats is an a normal expected error
            raise IOError(_("Failed to delete %(path)s, %(msg)s\n") %
                          {"path": path, "msg": msg})


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


def validate(profile_name, manifest_path, manifest_filename, dtd_filename,
             conversion_report, verbose):
    """Validate the generated manifest/profile based on the specified dtd"""
    is_valid = True

    if verbose:
        print _("Validating %(manifest)s" % \
              {"manifest": manifest_filename})
    try:
        # set up then parse the manifest and the allow the manifest
        # parser to validate the generated manifest based on the default dtd.
        if os.access(manifest_path, os.F_OK):
            manifest = os.path.join(manifest_path, manifest_filename)
            mani_parser = ManifestParser("manifest-parser", manifest,
                                         validate_from_docinfo=False,
                                         dtd_file=dtd_filename)
            logging.raiseExceptions = False
            mani_parser.parse(doc=None)
            logging.raiseExceptions = True
        else:
            raise IOError(
                _("file does not exist: %s\n") % manifest_filename)

    except ManifestError, err_msg:
        is_valid = False
        log_name, ending = manifest_filename.rsplit(".", 1)
        log_name += "_validation" + ".log"
        log_file = os.path.join(manifest_path, log_name)
        err_lines = str(err_msg).split(" : ")
        try:
            if os.access(log_file, os.F_OK):
                os.remove(log_file)
            with open(log_file, "w+") as f_handle:
                f_handle.write(_("NOTE: The errors outputed in this file must "
                                 "be manually corrected before the resulting "
                                 "file can be used by the Solaris "
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
            err(_("failed to create log file: %(logfile)s" % \
                 {"logfile": log_file}))
            sys.stderr.write(_("Validation failed:\n"))
            for line in err_lines:
                sys.stderr.write(line)

        if not is_valid:
            # Store the error information in the error service
            error_info = errsvc.ErrorInfo(ERR_VAL_MODID, liberrsvc.ES_ERR)
            error_info.set_error_data(liberrsvc.ES_DATA_FAILED_AT,
                                      "ManifestParser")
            error_info.set_error_data(liberrsvc.ES_DATA_FAILED_STR,
                                     (_("%(profile)s: validation of "
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

       Process errors refers to errors that occur when the various entities are
       read in. Conversion errors refers to errors that occur when converting
       items from the Solaris 10 nomiclature to Solaris 11 unsupported items
       refers to items that can not be converted.

       NOTE: Conversion errors and unsupported items will have a value of
             None if there is a processing error that prevents the file from
             being read

    """

    def __init__(self, process_errs=0, conversion_errs=0, unsupported_items=0,
                 validation_errs=0):
        self._process_errs = process_errs
        self._conversion_errs = conversion_errs
        self._unsupported_items = unsupported_items
        self._validation_errs = validation_errs
        self._warnings = 0
        self._log_lvl_convert_to_method = {
            LVL_PROCESS: self.add_process_error,
            LVL_UNSUPPORTED: self.add_unsupported_item,
            LVL_CONVERSION: self.add_conversion_error,
            LVL_VALIDATION: self.add_validation_error,
            LVL_WARNING: self.add_warning
        }

    def generate_error(self, log_level):
        """Given a log level, add an error to the report associated with
           the specified log level

        """
        if log_level in self._log_lvl_convert_to_method:
            self._log_lvl_convert_to_method[log_level]()
        else:
            raise ValueError

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

    def add_warning(self):
        """Increments the # of warnings by 1"""
        if self._warnings is None:
            self._warnings = 1
        else:
            self._warnings += 1

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

    @property
    def warnings(self):
        """Returns the # of warnings"""
        return self._warnings

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

    @warnings.setter
    def warnings(self, warning_count):
        """Set the # of warnings to warning_count"""
        self._warnings = warning_count

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
        if self._warnings is not None:
            errs += self._warnings
        return errs

    def has_errors(self):
        """Returns boolean, True if there are any process errors, conversion
           errors, unsupported items, or warnings

        """
        if self.error_count():
            return True
        else:
            return False

    def __str__(self):
        return ("process errors: %(process)s, "
               "warnings: %(warnings)s, "
               "conversion errors: %(conversion)s, "
               "unsupported items: %(unsupported)s, "
               "validation errors: %(validation)s" %
                {"process": str(self.process_errors),
                 "warnings": str(self.warnings),
                 "conversion": str(self.conversion_errors),
                 "unsupported": str(self.unsupported_items),
                 "validation": str(self.validation_errors)})

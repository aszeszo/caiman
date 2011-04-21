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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
"""

A/I Verify Manifest

"""

# Eventually bring names into convention.
# pylint: disable-msg=C0103

import lxml.etree
import os.path

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.installadm_common as com

from solaris_install import _


def verifyDTDManifest(xml_dtd, data):
    """
    Use this for verifying a generic DTD based XML whose DOCTYPE points to its
    available DTD (absolute path needed). Will return the etree to walk the
    XML tree or the validation error
    """
    result = list()
    # Explanation of options: Here we don't want to load the DTD since it is
    # passed in; don't use the network in case someone passes in an HTTP
    # reference in the XML as that could be unexpected; we do DTD validation
    # separate from the XML file's validation; we want to leave comments
    # for now, since the embedded SC manifest can be stored as a comment
    # in some places
    parser = lxml.etree.XMLParser(load_dtd=False, no_network=True,
                                  dtd_validation=False, remove_comments=False)
    dtd = lxml.etree.DTD(os.path.abspath(xml_dtd))
    try:
        root = lxml.etree.parse(data, parser)
    except IOError:
        raise SystemExit(_("Error:\tCan not open: %s" % data))
    except lxml.etree.XMLSyntaxError, err:
        for error in err.error_log:
            result.append(error.message)
        return None, result
    if dtd.validate(root):
        return root, None
    else:
        # pylint: disable-msg=E1101
        for err in dtd.error_log.filter_from_errors():
            result.append(err.message)
        return None, result


def verifyRelaxNGManifest(schema_f, data):
    """
    Use this to verify a RelaxNG based document using the pointed to RelaxNG
    schema and receive the validation error or the etree to walk the XML tree
    """
    import logging
    logging.debug('schema')
    try:
        relaxng_schema_doc = lxml.etree.parse(schema_f)
    except IOError:
        raise SystemExit(_("Error:\tCan not open: %s" % schema_f))
    logging.debug('RelaxNG doc=%s' % relaxng_schema_doc)
    relaxng = lxml.etree.RelaxNG(relaxng_schema_doc)
    logging.debug('RelaxNG parse data=%s' % data)
    try:
        root = lxml.etree.parse(data)
    except IOError:
        raise SystemExit(_("Error:\tCan not open: %s" % data))
    except lxml.etree.XMLSyntaxError, err:
        return None, err.error_log.last_error
    logging.debug('validate')
    if relaxng.validate(root):
        return root, None
    # pylint: disable-msg=E1101
    logging.debug('error')
    return None, relaxng.error_log.last_error


# =============================================================================
# =============================================================================
# This section deals with checking of specific value types, and handling of
# single values which represent a range.  The single values are morphed to look
# like min/max pairs with the same number on both sides.

# =============================================================================
def checkIPv4(value):
# =============================================================================
    """
    Private function that checks an IPV4 string, that it has four values
    0 <= value <= 255, separated by dots.  Adds zero padding to three digits
    per value.

    Args:
      value: the string being checked and processed

    Returns:
      checked and massaged value.

    Raises:
      ValueError: Malformed IPV4 address in criteria
    """
# =============================================================================

    ipv4_err_msg = "Malformed IPV4 address in criteria"
    newval = ""

    values = value.split(".")
    if len(values) != 4:
        raise ValueError(ipv4_err_msg)
    for value in values:
        try:
            ivalue = int(value)
        except ValueError:
            raise ValueError(ipv4_err_msg)
        if ivalue < 0 or ivalue > 255:
            raise ValueError(ipv4_err_msg)
        newval += "%3.3d" % ivalue
    return newval


# =============================================================================
def checkMAC(value):
# =============================================================================
    """
    Private function that checks an MAC address string, that it has six hex
    values 0 <= value <= FF, separated by colons.  Adds zero padding to two
    digits per value.

    Args:
      value: the string being checked and processed

    Returns:
      checked and massaged value.

    Raises:
      ValueError: Malformed MAC address in criteria
    """
# =============================================================================

    mac_err_msg = "Malformed MAC address in criteria"
    try:
        macAddress = com.MACAddress(value)
    except com.MACAddress.MACAddressError:
        raise ValueError(mac_err_msg)
    return str(macAddress).lower()


# =============================================================================
def prepValuesAndRanges(criteriaRoot, database, table=AIdb.MANIFESTS_TABLE):
# =============================================================================
    """
    Processes criteria manifest data already read into memory but before
    it is stored in the AI database.

    Does the following:
    - When a criterion range of one is given by a single <value>, morph
            that value so it can be stored in the database as a <range>.
    - Pad the digit strings of MAC addresses so that the six values between
            the colons are two hex digits each.
    - Pad the digit strings of IP addresses so that the four values between
            the dots are three digits each and between 0 and 255.
    - Strip off colons from MAC addresses and dots from IPv4 addresses.

    Args:
      - criteriaRoot: Tree root for criteria manifest.  This is where
            data is checked / modified.
      - database: Used to find which criteria are range criteria.

    Returns: Nothing.  However, data may be checked and modified per above.

    Raises:
    - Exception: Exactly 1 value (no spaces) expected for cpu criteria tag
    - Exceptions raised by database calls, and calls to
            - checkIPv4()
            - checkMAC()
    """
# =============================================================================

    # Find from the database which criteria are range criteria.
    # Range criteria named xxx have names bounds values MINxxx and MAXxxx.
    # Assume that MINxxx is a good enough check.
    # All criteria names in database are stored as lower case, except
    # for their "MIN" and "MAX" prefixes.
    range_crit = []
    for crit_name in AIdb.getCriteria(database.getQueue(), table,
        onlyUsed=False, strip=False):
        if (crit_name.startswith("MIN")):
            range_crit.append(crit_name.replace("MIN", "", 1))

    # Loop through all criteria elements.
    for crit in criteriaRoot.findall('.//ai_criteria'):
        crit_name = crit.attrib['name'].lower()
        val_range = crit.getchildren()[0]

        # <range>'s here are a single element with a single
        # string containing two space-separated values for MIN and MAX
        # <value>'s here are a single element with a single
        # string containing one value.
        value_list = val_range.text.split()
        num_values = len(value_list)

        # Val_range.tag will be either value or range.
        # This is checked by the schema.
        if val_range.tag == "value":

            # Allow values with spaces (which here look like
            # multiple values), except for CPU items.  Non-CPU
            # items are "arch" and "platform".
            if num_values != 1 and crit_name == "cpu":
                raise StandardError("Exactly 1 value " +
                    "(no spaces) expected for cpu criteria tag")
        else:
            if range_crit.count(crit_name) == 0:
                raise StandardError("Range pair passed to " +
                    "non-range criterion \"" + crit_name + "\"")

        # For value criteria, there is no need to do anything to store
        # single value into val_range.text.  It is already there.
        #
        # For some types supported by range criteria, some additional
        # format checking is needed.  Also, single values passed as
        # range criteria need to be split into a range where min=max.

        # Current criterion is a range criterion.
        if range_crit.count(crit_name) > 0:

            # Each value will have already been checked against the
            # schema.  IPv4 values will be 4 numbers ranging from
            # 0-255, separated by dots.  MAC values will be 6 hex
            # numbers ranging from 0-FF, separated by colons.
            # There may be one or two values.

            new_values = ""
            for one_value in value_list:

                # Space between (range) values.
                if new_values != "":
                    new_values += " "

                # Handle "unbounded" keyword; and pass lowercase
                lowered_value = one_value.lower()
                if lowered_value == "unbounded":
                    new_values += lowered_value

                # Handle IPv4 addressses.
                elif crit_name == "ipv4" or crit_name == "network":
                    new_values += checkIPv4(one_value)

                # Handle MAC addresses.
                elif crit_name == "mac":
                    new_values += checkMAC(one_value)

                # Handle everything else by passing through.
                else:
                    new_values += one_value

                # Single values which come in under a "value"
                # tag but represent a range (e.g. a single ipv4
                # value) are "converted" into the form a range
                # value pair would take (a single string
                # consisting of two items) where
                # the min value = max value.
                if val_range.tag == "value":
                    # Change to a range.
                    # Set min = max = value.
                    val_range.tag = "range"
                    val_range.text = \
                        new_values + " " + new_values
                elif val_range.tag == "range":
                    # values will be a list of 2 already.
                    val_range.text = new_values

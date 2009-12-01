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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
"""

A/I List Manifests

"""

import sys

import gettext
from optparse import OptionParser
import os
import osol_install.auto_install.AI_database as AIdb

def parse_options():
    """
    Parse and validate options
    Return the options and service location (args[0])
    """

    usage = _("usage: %prog [options] A/I_data_directory")
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--criteria", dest="criteria", default=False,
                      action="store_true", help=_("provide manifest criteria"))
    (options, args) = parser.parse_args()

    # we need the A/I service directory to be passed in
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)

    return (options, args[0])

def print_headers(DB, options):
    """
    Prints out the headers for the rest of the command's output
    Returns a dictionary of maximum lengths computed (to be used spacing the output of later
    functions)
    """
    header_1 = ""
    header_2 = ""
    max_man_len = len(_("manifest"))
    max_ins_len = len(_("instance"))
    max_cri_len = dict()

    # calculate maximum instance name and maximum number of instances
    for name in AIdb.getManNames(DB.getQueue()):
        # calculate the maximum manifest name length
        max_man_len = max(max_man_len, len(name))
        # calculate the maximum length of instance numbers
        max_ins_len = max(max_ins_len,
                          len(str(AIdb.numInstances(name, DB.getQueue()))))

    # add the necessary spacing to the header for the manifest label and colon
    # (with a trailing space to separate from instances next)
    header_1 += _("manifest").ljust(max_man_len + 1) + " "

    # print a row of hyphens for manifest label
    # (with a trailing space to separate from instances next)
    header_2 += "-" * (max_man_len + 1) + " "

    # if we're printing out criteria, calculate lengths and print criteria names
    if options.criteria:

        # add the header for the instance label, space for excess instance
        # numbers (instances whose numbers are longer than len(_"instance")
        # and add a space before first criteria
        header_1 += _("instance").ljust(max_ins_len) + " "

        # repeat for hyphens to underline instances
        header_2 += "-" * max_ins_len + " "

        # first use un-stripped criteria to generate lengths of the criteria
        # values
        for cri in AIdb.getCriteria(DB.getQueue(),
                                    onlyUsed=False, strip=False):
            max_cri_len[cri] = 0
            # iterate through each value for this criteria getting the maximum
            # length
            for response in AIdb.getSpecificCriteria(DB.getQueue(), cri):
                max_cri_len[cri] = max(max_cri_len[cri],
                                       len(str(AIdb.formatValue(cri,
                                                                response[0]))))

            # add a space between criteria
            max_cri_len[cri] += 1

            # set MIN and MAX criteria to have equal lenghts since they share a
            # column (but have to run on MAXcri so MINcri has been set)
            if cri.startswith('MAX'):
                # first set MAXcri
                max_cri_len[cri] = max(max_cri_len[cri.replace('MIN', 'MAX')],
                                       max_cri_len[cri.replace('MAX', 'MIN')])

                # now set MINcri
                max_cri_len[cri.replace('MAX', 'MIN')] = max_cri_len[cri]

                # now set criteria
                max_cri_len[cri.replace('MAX', 'MIN').replace('MIN','')] = \
                    max_cri_len[cri]

        # now print stripped criteria for human consumption as the headers
        for cri in AIdb.getCriteria(DB.getQueue(), onlyUsed=True, strip=True):
            # lowercase each criteria for uniformity and print each to a field
            # length of max_cri_len for this criterion
            header_1 += cri.lower().ljust(max_cri_len[cri])
            header_2 += "-" * (max_cri_len[cri] - 1) + " "

    # print the final header
    print header_1
    print header_2

    # return dictionary of lengths computed during output
    return {"criteria": max_cri_len,
            "instance": max_ins_len + 1,
            "manifest": max_man_len + 1}

def print_manifests(DB, maxLengths=None):
    """
    Prints out a list of manifests registered in the SQL database
    (If printing criteria call for the criteria of each manifest)
    """
    for name in AIdb.getManNames(DB.getQueue()):
        # if we are handed maxLengths that means we need to print criteria too
        if maxLengths:
            print name + ":"
            printCriteria(DB, maxLengths, name)
        # we're simply printing manifest names
        else:
            print name

def printCriteria(DB, lengths, manifest):
    """
    Prints out a list of criteria for each manifest instance
    registered in the SQL database
    """
    # iterate over all instances of this manifest
    for instance in range(0, AIdb.numInstances(manifest, DB.getQueue())):

        # deal with manifest and instance columns
        # print MAX manifest name length + 1 spaces for padding
        # line one is used for single value and minimum values
        response_1 = " " * (lengths["manifest"] + 1)
        # line two is used for maximum values
        response_2 = " " * (lengths["manifest"] + 1)

        # add the instance number
        response_1 += str(instance).ljust(lengths["instance"])

        # space line two equally
        response_2 += " " * lengths["instance"]

        # now get the criteria to iterate over
        # need to iterate over all criteria not just used in case a MIN or MAX
        # is used but not its partner
        criteria = AIdb.getManifestCriteria(manifest, instance, DB.getQueue(),
                                            humanOutput=True, onlyUsed=False)
        # now iterate for each criteria in the database
        for cri in criteria.keys():

            # this criteria is unused in this instance
            if not criteria[cri]:
                # Ensure the criteria is used in the database - has a greater
                # than one length (due to space between criteria being added
                # above)
                if lengths["criteria"][cri] < 2:
                    continue

                # print a centered hyphen since this criteria is unset
                value = "-".center(lengths["criteria"][cri])
            # this criteria is used in this instance
            else:
                value = AIdb.formatValue(cri, criteria[cri])

            # now put the value out to the correct line
            # MIN and single values on line one MAX values on line two
            if cri.startswith('MAX'):
                response_2 += value.ljust(lengths["criteria"][cri])
            elif cri.startswith('MIN'):
                response_1 += value.ljust(lengths["criteria"][cri])
            # else a single value, so space out line two
            else:
                response_1 += value.ljust(lengths["criteria"][cri])
                response_2 += " " * lengths["criteria"][cri]

        print response_1
        print response_2


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    (options, DATA_LOC) = parse_options()
    if not os.path.exists(os.path.join(DATA_LOC, "AI.db")):
        raise SystemExit("Error:\tNeed a valid A/I service directory")
    AISQL = AIdb.DB(os.path.join(DATA_LOC, 'AI.db'))
    AISQL.verifyDBStructure()
    MAX_LENS = print_headers(AISQL, options)
    if options.criteria:
        print_manifests(AISQL, maxLengths=MAX_LENS)
    else:
        print_manifests(AISQL)

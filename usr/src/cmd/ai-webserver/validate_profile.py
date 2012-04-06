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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
"""
AI validate_profile
"""
import gettext
import os.path
import sys

import lxml.etree

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.data_files as df

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _, \
    validate_service_name
from osol_install.auto_install.service import AIService


def get_usage():
    ''' get usage for validate'''
    return _("validate\t-n|--service <svcname>\n"
             "\t\t-P|--profile-file <profile_path> ... |\n"
             "\t\t-p|--profile <profile_name> ...")


def parse_options(cmd_options=None):
    """ Parse and validate options
    Args: Optional cmd_options, used for unit testing. Otherwise, cmd line
          options handled by OptionParser
    Returns: parsed options and database file name
    Raises: many error conditions when caught raising SystemExit
    """
    parser = OptionParser(usage='\n' + get_usage())

    parser.add_option("-P", "--profile-file", dest="profile_path",
                      action="append", default=list(),
                      help=_("Path to profile file"))
    parser.add_option("-p", "--profile", dest="profile_name", action="append",
                      default=list(), help=_("Name of profile"))
    parser.add_option("-n", "--service", dest="service_name", default="",
                      help=_("Name of install service."))

    # Get the parsed options using parse_args().  We know we don't have
    # args, so check to make sure there are none.
    options, args = parser.parse_args(cmd_options)
    if not (options.profile_name or options.profile_path) or \
        (options.profile_name and options.profile_path):
        parser.error(_(
            "Specify either -p <profile name> or -P <profile path>"))
    if not options.service_name:
        parser.error(_("Service name is required (-n <service name>)."))
    if len(args) > 0:
        parser.error(_("Unexpected argument(s): %s" % args))

    if options.service_name:
        try:
            validate_service_name(options.service_name)
        except ValueError as err:
            parser.error(err)

    return options


def validate_internal(profile_list, database, table, image_dir):
    ''' given a list of profile files and the profile database and table,
        validate the list of profiles
    Args:
        profile_list - list of profile path names
        database - name of database
        table - name of database table
        image_dir - path of service image, used to locate service_bundle
    Returns True if all profiles are valid, return False if any are invalid
    '''
    # Open the database
    dbn = AIdb.DB(database, commit=True)
    dbn.verifyDBStructure()
    isvalid = True
    queue = dbn.getQueue()
    if not profile_list:
        profile_list = [None]
    for profile in profile_list:
        qstr = "SELECT name, file FROM %s WHERE name = %s" % \
                (table, AIdb.format_value('name', profile))
        query = AIdb.DBrequest(qstr, commit=True)
        queue.put(query)
        query.waitAns()
        # check response, if failure, getResponse prints error
        if query.getResponse() is None:  # database error
            return False  # give up
        if len(query.getResponse()) == 0:
            print >> sys.stderr, \
                    _('No profiles in database with basename ') + profile
            isvalid = False
            continue  # to the next profile
        for response in query.getResponse():
            if not df.validate_file(response[0], response[1], image_dir):
                isvalid = False
    return isvalid


def do_validate_profile(cmd_options=None):
    ''' external entry point for installadm
    Arg: cmd_options - command line options
    Effect: validate per command line
    '''
    options = parse_options(cmd_options)
    isvalid = True
    # get AI service directory, database name
    service = AIService(options.service_name)
    image_dir = service.image.path
    dbname = service.database_path

    if options.profile_name:
        isvalid = validate_internal(options.profile_name, dbname,
                                    AIdb.PROFILES_TABLE, image_dir)
    if options.profile_path:
        # iterate through profile files on command line
        for fname in options.profile_path:
            if not df.validate_file(os.path.basename(fname), fname, image_dir):
                isvalid = False
    # return failure status if any profiles failed validation
    if not isvalid:
        sys.exit(1)


if __name__ == '__main__':
    gettext.install("solaris_install_aiwebserver", "/usr/share/locale")
    do_validate_profile()

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
AI delete-profile
"""
import gettext
import logging
import os
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc

from errno import ENOENT
from optparse import OptionParser

from osol_install.auto_install.installadm_common import _, \
    validate_service_name
from osol_install.auto_install.service import AIService
from solaris_install import check_auth_and_euid, PROFILE_AUTH, \
    UnauthorizedUserError


def get_usage():
    ''' get usage for delete-profile'''
    return _("delete-profile\t-p|--profile <profile_name> ... "
             "-n|--service <svcname>")


def parse_options(cmd_options=None):
    ''' Parse and validate options
    Args: options handled by OptionParser
    Returns: options
    '''
    parser = OptionParser(usage='\n' + get_usage())

    parser.add_option("-p", "--profile", dest="profile_name", action="append",
                      default=list(), help=_("Name of profile"))
    parser.add_option("-n", "--service", dest="service_name", default='',
                      help=_("Name of install service."))
    # Get the parsed options using parse_args().  We know we don't have
    # args, so check to make sure there are none.
    options, args = parser.parse_args(cmd_options)

    if not options.profile_name or not options.service_name:
        parser.error(_("Both -p|--profile and -n|--service are required."))
    if len(args):
        parser.error(_("Unexpected argument(s): %s" % args))

    try:
        validate_service_name(options.service_name)
    except ValueError as err:
        parser.error(err)

    return options


def delete_profiles(profs, dbo, table):
    ''' deletes all database entries matching user's command line options
    Args:
        profs - list of profiles to delete by name
        dbo - database object
        table - database table name
    Returns: True if any errors encountered, False otherwise
    Exceptions: none
    '''
    # if any serious errors encountered, set exit status
    has_errors = False
    queue = dbo.getQueue()
    # Build a list of criteria for WHERE clause
    db_cols = [u'rowid'] + [u'file']
    # loop through all profiles from command line and delete them
    for profile_name in profs:
        query_str = "SELECT " + ", ".join(db_cols) + " FROM " + table + \
                " WHERE name=" + AIdb.format_value('name', profile_name)
        logging.debug("query=" + query_str)
        query = AIdb.DBrequest(query_str, commit=True)
        queue.put(query)
        query.waitAns()
        # check response, if failure, getResponse prints error
        rsp = query.getResponse()
        if rsp is None:
            has_errors = True
            continue
        if len(rsp) == 0:
            print >> sys.stderr, _("\tProfile %s not found.") % profile_name
            has_errors = True
            continue
        # delete database record and any accompanying internal profile file
        for response in rsp:
            deldict = dict()
            iresponse = iter(response)
            for crit in db_cols:
                deldict[crit] = next(iresponse)
            query_str = "DELETE FROM %s WHERE rowid=%d" % \
                    (table, deldict['rowid'])
            delquery = AIdb.DBrequest(query_str, commit=True)
            queue.put(delquery)
            delquery.waitAns()
            # check response, if failure, getResponse prints error
            if delquery.getResponse() is None:
                has_errors = True
                continue
            print >> sys.stderr, _("\tDeleted profile %s.") % profile_name
            # delete static (internal) files only
            if deldict['file'] is None or \
                not deldict['file'].startswith(sc.INTERNAL_PROFILE_DIRECTORY):
                continue
            try:
                os.unlink(deldict['file'])
            except OSError, (errno, errmsg):
                if errno != ENOENT:  # does not exist
                    print >> sys.stderr, _(
                            "Error (%(errno)s):  Problem deleting %(name)s "
                            "(%(file)s): %(msg)s") % {'errno': errno, \
                            'name': profile_name, 'file': deldict['file'], \
                            'msg': errmsg}
                has_errors = True
                continue
    return has_errors


def do_delete_profile(cmd_options=None):
    ''' external entry point for installadm
    Arg: cmd_options - command line options
    Effect: delete profiles per command line
    '''
    # check for authorization and euid
    try:
        check_auth_and_euid(PROFILE_AUTH)
    except UnauthorizedUserError as err:
        raise SystemExit(err)

    options = parse_options(cmd_options)

    # get AI service directory, database name
    service = AIService(options.service_name)
    dbname = service.database_path

    # Open the database
    aisql = AIdb.DB(dbname, commit=True)
    aisql.verifyDBStructure()

    # delete profiles per command line
    errs = delete_profiles(options.profile_name, aisql, AIdb.PROFILES_TABLE)
    if errs:
        sys.exit(1)


if __name__ == '__main__':
    gettext.install("solaris_install_aiwebserver", "/usr/share/locale")
    do_delete_profile()

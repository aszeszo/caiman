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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.

"""
AI export-profile
"""
# external modules
import gettext
from optparse import OptionParser
import sys

# Solaris modules
import osol_install.auto_install.AI_database as AIdb
from osol_install.auto_install.installadm_common import _, validate_service_name

def get_usage():
    ''' get usage for export'''
    return _("export\t-p|--profile <profile_name> ... -n|--service <svcname>")


def parse_options(cmd_options=None):
    """ Parse and validate options
    Args: Command line options handled by OptionParser
    Returns: OptionParser options
    """
    parser = OptionParser(usage='\n'+get_usage())

    parser.add_option("-p", "--profile", dest="profile_name", action="append",
                      default=[], help=_("Name of profile"))
    parser.add_option("-n", "--service", dest="service_name", default="",
                      help=_("Name of install service."))

    # Get the parsed options using parse_args().  We know we don't have
    # args, so check to make sure there are none.
    options, args = parser.parse_args(cmd_options)
    if not options.service_name or not options.profile_name:
        parser.error(_(
                    "Specify -p|--profile <profile> and -n|--service <service>."
                    ))
    if len(args) > 0:
        parser.error(_("Unexpected argument(s): %s" % args))

    try:
        validate_service_name(options.service_name)
    except ValueError as err:
        parser.error(err)

    return options


def export_profile(profile_name, dbn):
    """
    Export profiles to user
    Args:
        profile_name - list of profiles to export
        dbn - database object
    Effect: output requested profile(s) to stdout, errors and messages to stderr
    """
    queue = dbn.getQueue() 
    for name in profile_name:
        # sanitize and format for SELECT
        fmtname = AIdb.format_value('name', name)
        q_str = "SELECT file FROM  " + AIdb.PROFILES_TABLE + \
                " WHERE name=" + fmtname
        query = AIdb.DBrequest(q_str)
        queue.put(query)
        query.waitAns()
        # check response, if failure, getResponse prints error
        if query.getResponse() is None:
            continue
        if len(query.getResponse()) == 0:
            print >> sys.stderr, _("Profile %s not found.") % fmtname
            continue
        for row in query.getResponse():
            profpath = row['file']
            # read profile file
            try:
                with open(profpath) as fpp:
                    raw_profile = fpp.read()
            except IOError, (errno, strerror):
                print >> sys.stderr, \
                        _("Error:  Could not open %s: %s") % (fmtname, strerror)
                continue
            # just dump the content to stdout
            print raw_profile
            print >> sys.stderr, _("Exported profile %s.") % fmtname


def do_export_profile(cmd_options=None):
    ''' external entry point for installadm
    Arg: cmd_options - command line options
    Effect: export profiles per command line
    '''
    options = parse_options(cmd_options)

    # get AI service directory, database name
    service_dir, dbname, image_dir = AIdb.get_service_info(options.service_name)

    # Open the database
    aisql = AIdb.DB(dbname, commit=True)
    aisql.verifyDBStructure()

    # export profiles per command line
    export_profile(options.profile_name, aisql)

if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    do_export_profile()

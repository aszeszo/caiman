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
#
'''
export - write out a manifest or profile
'''
import errno
import gettext
import os
import shutil
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.service import AIService
from osol_install.auto_install.installadm_common import _, \
    validate_service_name


SCREEN = "/dev/stdout"
HEADER_WIDTH = 80


def get_usage():
    ''' get usage for export'''
    usage = _(
        'export\t-n|--service <svcname>\n'
        '\t\t-m|--manifest <manifest/script name> ...\n'
        '\t\t-p|--profile <profile name> ...\n'
        '\t\t[-o|--output <pathname>]')
    return(usage)


def parse_options(cmd_options=None):
    '''Parse commandline options for export command'''

    parser = OptionParser(usage=get_usage(), prog="export")
    parser.add_option('-p', '--profile', dest='pnames', action="append",
                      default=list(), help=_("Name of profile to export."))
    parser.add_option('-m', '--manifest', dest='mnames', action="append",
                      default=list(), help=_("Name of manifest to export."))
    parser.add_option('-n', '--service', dest='service_name',
                      default=None, help=_("Name of install service."))
    parser.add_option('-o', '--output', dest='output_name',
                      default=None, help=_("Name of output file."))

    (options, args) = parser.parse_args(cmd_options)

    if args:
        parser.error(_("Extra args given."))

    if not options.service_name:
        parser.error(_("Service name is required."))

    if not config.is_service(options.service_name):
        raise SystemExit(_("No such service: %s") % options.service_name)

    service = AIService(options.service_name)
    options.service = service

    if not len(options.mnames) and not len(options.pnames):
        parser.error(_("A manifest or profile name is required."))

    options.file_count = len(options.mnames) + len(options.pnames)

    if not options.output_name:
        options.output_name = SCREEN
        options.output_isdir = None

    else:
        # Non-stdout -o processing:
        # if output_name is an existing directory: write all files out to it.
        # if output_name is an existing file and output one file:
        #     overwrite the existing file.
        # if file exists with output_name and mult output files desired:
        #     error
        # if file or dir doesn't exist w/output name and mult files desired:
        #     create new directory with output name and write files there.
        # if file or dir doesn't exist with output name and one file desired:
        #     write the one file to that output name

        options.output_isdir = False
        if os.path.isdir(options.output_name):
            options.output_isdir = True
        elif os.path.exists(options.output_name):
            if (options.file_count > 1):
                parser.error(_("-o must specify a directory when multiple "
                               "files are requested."))
        else:
            if (options.file_count > 1):
                os.mkdir(options.output_name)
                options.output_isdir = True

    return options


def display_file_header(header):
    ''' Display file header / separator, as between two files (e.g. manifests)
    '''
    num_dashes = (HEADER_WIDTH - len(header) - 2) / 2
    print ("-" * num_dashes) + " " + header + " " + ("-" * num_dashes) + "\n"


def do_export(cmd_options=None):
    ''' Export a manifest or a profile.  Called from installadm.
    '''
    options = parse_options(cmd_options)

    merrno = perrno = 0
    if len(options.mnames):
        merrno = do_export_manifest(options)
    if len(options.pnames):
        perrno = do_export_profile(options)
    sys.exit(perrno if perrno != 0 else merrno)


def do_export_manifest(options):
    '''
    Export a manifest.
    '''
    save_errno = 0

    for mname in options.mnames:
        # Get the pathname of the manifest to export.
        input_mname = os.path.join(options.service.manifest_dir, mname)

        if options.output_isdir:
            output_name = "/".join([options.output_name, mname])
        else:
            output_name = options.output_name
        if output_name == SCREEN and options.file_count > 1:
            display_file_header(_("manifest: ") + mname)

        # Find the file in the directory and copy it to screen or file.
        try:
            shutil.copyfile(input_mname, output_name)
        except IOError as err:
            print >> sys.stderr, _("Error exporting manifest: "
                                   "%(error)s: %(file)s") % (
                                   {"error": err.strerror,
                                    "file": err.filename})
            save_errno = err.errno
        print
    return save_errno


def do_export_profile(options):
    '''
    Export a profile.
    '''
    save_errno = 0

    # Open the database
    aisql = AIdb.DB(options.service.database_path, commit=True)
    aisql.verifyDBStructure()

    queue = aisql.getQueue()
    for pname in options.pnames:
        # sanitize and format for SELECT
        fmtname = AIdb.format_value('name', pname)
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

            if options.output_isdir:
                output_name = "/".join([options.output_name, pname])
            else:
                output_name = options.output_name

            if output_name == SCREEN and options.file_count > 1:
                display_file_header(_("profile: ") + pname)

            try:
                shutil.copyfile(profpath, output_name)
            except IOError as err:
                print >> sys.stderr, _("Error exporting profile: "
                                       "%(error)s: %(file)s") % (
                                       {"error": err.strerror,
                                        "file": err.filename})
                save_errno = err.errno
            print
    return save_errno


if __name__ == '__main__':
    gettext.install("solaris_install_aiwebserver", "/usr/share/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_export()

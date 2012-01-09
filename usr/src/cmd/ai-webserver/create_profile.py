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
AI create-profile
"""
import gettext
import os.path
import sys
import tempfile
import shutil

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc
import osol_install.auto_install.data_files as df
import osol_install.auto_install.publish_manifest as pub_man
import osol_install.auto_install.service_config as config

from optparse import OptionParser
from stat import S_IRWXU

from osol_install.auto_install.installadm_common import _
from osol_install.auto_install.service import AIService

# Modes of operation.
DO_CREATE = True
DO_UPDATE = False


def get_create_usage():
    '''
    Return usage for create-profile.
    '''
    return _("create-profile -n|--service <svcname> "
             "-f|--file <profile_file>... \n"
             "\t\t[-p|--profile <profile_name>]\n"
             "\t\t[-c|--criteria <criteria=value|range> ...] | \n"
             "\t\t[-C|--criteria-file <criteria_file>]")


def get_update_usage():
    '''
    Return usage for update-profile.
    '''
    return _("update-profile -n|--service <svcname> "
             "-f|--file <profile_file> \n"
             "\t\t[-p|--profile <profile_name>]")


def parse_options(do_create, cmd_options=None):
    """ Parse and validate options
    Args:  - do_create (True) or do_update (False) 
           - cmd_options - command line handled by OptionParser

    Returns: options
    """

    if do_create:
        usage = '\n' + get_create_usage()
    else:
        usage = '\n' + get_update_usage()

    parser = OptionParser(usage=usage)

    if do_create:
        parser.add_option("-C", "--criteria-file", dest="criteria_file",
                          default='', help=_("Name of criteria XML file."))
        parser.add_option("-c", "--criteria", dest="criteria_c",
                          action="append", default=list(), metavar="CRITERIA",
                          help=_("Criteria: <-c criteria=value|range> ..."))

    parser.add_option("-f", "--file", dest="profile_file", action="append",
                      default=list(), help=_("Path to profile file"))
    parser.add_option("-p", "--profile", dest="profile_name",
                      default='', help=_("Name of profile"))
    parser.add_option("-n", "--service", dest="service_name", default="",
                      help=_("Name of install service."))

    options, args = parser.parse_args(cmd_options)

    if len(args):
        parser.error(_("Unexpected arguments: %s" % args))

    if not do_create:
        options.criteria_file = None
        options.criteria_c = None
        if len(options.profile_file) > 1:
            parser.error(_("Provide only one file name (-f)."))

    if not options.service_name:
        parser.error(_("Service name is required (-n <service name>)."))
    if not options.profile_file:
        parser.error(_("Profile file is required (-f <profile file>)."))
    if options.profile_name and len(options.profile_file) > 1:
        parser.error(_("If a profile name is specified (-p), only one file "
            "name may be specified (-f)."))

    if not config.is_service(options.service_name):
        raise SystemExit(_("No such service: %s") % options.service_name)

    return options


def add_profile(criteria, profile_name, profile_file, queue, table):
    """
    Set a profile record in the database with the criteria provided.
    Args:
        criteria - criteria object
        profile_name - name of profile to add
        profile_file - path of profile to add
        queue - database request queue
        table - profile table in database
    Returns: True if successful, false otherwise
    Effects:
        database record added
        stored resulting profile in internal profile directory
    """
    # get lists prepared for SQLite WHERE, INSERT VALUES from command line
    (wherel, insertl, valuesl) = \
        sc.sql_values_from_criteria(criteria, queue, table)

    # clear any profiles exactly matching the criteria
    wherel += ["name=" + AIdb.format_value('name', profile_name)]
    q_str = "DELETE FROM " + table + " WHERE " + " AND ".join(wherel)
    query = AIdb.DBrequest(q_str, commit=True)
    queue.put(query)
    query.waitAns()
    if query.getResponse() is None:
        return False

    # add profile to database
    insertl += ["name"]
    valuesl += [AIdb.format_value('name', profile_name)]
    insertl += ["file"]
    valuesl += [AIdb.format_value('name', profile_file)]
    q_str = "INSERT INTO " + table + "(" + ", ".join(insertl) + \
            ") VALUES (" + ", ".join(valuesl) + ")"
    query = AIdb.DBrequest(q_str, commit=True)
    queue.put(query)
    query.waitAns()
    if query.getResponse() is None:
        return False

    print >> sys.stderr, _('Profile %s added to database.') % profile_name
    return True


def copy_profile_internally(profile_string):
    '''given a profile string, write it to a file internal to the
    AI server profile storage and make database entry for it
    returns path to new internal profile file

    Arg: profile_string - the profile to write to an internal file
    Returns: filename if successful, False if OSError
    '''
    # use unique filename generator to create profile
    # file that will be internal to and managed by the AI server
    try:
        (tfp, full_profile_path) = tempfile.mkstemp(".xml",
            'sc_', sc.INTERNAL_PROFILE_DIRECTORY)
    except OSError:
        print >> sys.stderr, \
            _("Error creating temporary file for profile in directory %s.") % \
            sc.INTERNAL_PROFILE_DIRECTORY
        return False
    # output internal profile owned by webserver
    try:
        os.chmod(full_profile_path, S_IRWXU)  # not world-read
        os.fchown(tfp, sc.WEBSERVD_UID, sc.WEBSERVD_GID)
        os.write(tfp, profile_string)
        os.close(tfp)
    except OSError, err:
        print >> sys.stderr, _("Error writing profile %s: %s") % \
                (full_profile_path, err)
        return False
    return full_profile_path


def do_create_profile(cmd_options=None):
    ''' external entry point for installadm
    Arg: cmd_options - command line options
    Effect: add profiles to database per command line
    Raises SystemExit if condition cannot be handled
    '''
    options = parse_options(DO_CREATE, cmd_options)

    # get AI service image path and database name
    service = AIService(options.service_name)
    image_dir = service.image.path
    dbname = service.database_path
    
    # open database
    dbn = AIdb.DB(dbname, commit=True)
    dbn.verifyDBStructure()
    queue = dbn.getQueue()
    root = None
    criteria_dict = dict()

    # Handle old DB versions which did not store a profile.
    if not AIdb.tableExists(queue, AIdb.PROFILES_TABLE):
        raise SystemExit(_("Error:\tService %s does not support profiles") %
                           options.service_name)
    try:
        if options.criteria_file:  # extract criteria from file
            root = df.verifyCriteria(
                    df.DataFiles.criteriaSchema,
                    options.criteria_file, dbn, AIdb.PROFILES_TABLE)
        elif options.criteria_c:
            # if we have criteria from cmd line, convert into dictionary
            criteria_dict = pub_man.criteria_to_dict(options.criteria_c)
            root = df.verifyCriteriaDict(
                    df.DataFiles.criteriaSchema,
                    criteria_dict, dbn, AIdb.PROFILES_TABLE)
    except ValueError as err:
        raise SystemExit(_("Error:\tcriteria error: %s") % err)
    # Instantiate a Criteria object with the XML DOM of the criteria.
    criteria = df.Criteria(root)
    sc.validate_criteria_from_user(criteria, dbn, AIdb.PROFILES_TABLE)
    # track exit status for all profiles, assuming no errors
    has_errors = False

    # loop through each profile on command line
    for profile_file in options.profile_file:
        # take option name either from command line or from basename of profile
        if options.profile_name:
            profile_name = options.profile_name
        else:
            profile_name = os.path.basename(profile_file)
        # check for any scope violations
        if sc.is_name_in_table(profile_name, queue, AIdb.PROFILES_TABLE):
            print >> sys.stderr, \
                    _("Error:  A profile named %s is already in the database "
                      "for service %s.") % (profile_name, options.service_name)
            has_errors = True
            continue
        # open profile file specified by user on command line
        if not os.path.exists(profile_file):
            print >> sys.stderr, _("File %s does not exist") % profile_file
            has_errors = True
            continue

        # validates the profile and report errors if found
        raw_profile = df.validate_file(profile_name, profile_file, image_dir,
                                        verbose=False)
        if not raw_profile:
            has_errors = True
            continue

        # create file from profile string and report failures
        full_profile_path = copy_profile_internally(raw_profile)
        if not full_profile_path:
            has_errors = True
            continue

        # add new profile to database
        if not add_profile(criteria, profile_name, full_profile_path, queue,
                AIdb.PROFILES_TABLE):
            os.unlink(full_profile_path)  # failure, back out internal profile
            has_errors = True
    # exit with status if any errors in any profiles
    if has_errors:
        sys.exit(1)


def do_update_profile(cmd_options=None):
    ''' Updates exisiting profile
    Arg: cmd_options - command line options
    Effect: update existing profile 
    Raises SystemExit if condition cannot be handled
    '''

    options = parse_options(DO_UPDATE, cmd_options)

    # verify the file 
    profile_file = options.profile_file[0]
    if not os.path.exists(profile_file):
        raise SystemExit(_("Error:\tFile does not exist: %s\n") % profile_file)

    # get profile name
    if not options.profile_name:
        profile_name = os.path.basename(profile_file)
    else:
        profile_name = options.profile_name

    # get AI service image path and database name
    service = AIService(options.service_name)
    dbname = service.database_path
    image_dir = service.image.path

    # open database
    dbn = AIdb.DB(dbname, commit=True)
    dbn.verifyDBStructure()
    queue = dbn.getQueue()

    # Handle old DB versions which did not store a profile.
    if not AIdb.tableExists(queue, AIdb.PROFILES_TABLE):	
        raise SystemExit(_("Error:\tService %s does not support profiles") %
                         options.service_name)

    # check for the existence of profile
    missing_profile_error = _("Error:\tService {service} has no profile "
                              "named {profile}.")
    if not sc.is_name_in_table(profile_name, queue, AIdb.PROFILES_TABLE):
        raise SystemExit(missing_profile_error.format(
                         service=options.service_name, profile=profile_name))

    # validates the profile and report the errors if found 
    raw_profile = df.validate_file(profile_name, profile_file, image_dir,
                                    verbose=False)
    if not raw_profile:
        raise SystemExit(1)

    # create file from string and report failures
    tmp_profile_path = copy_profile_internally(raw_profile)
    if not tmp_profile_path:
        raise SystemExit(1) 

    # get the path of profile in db
    q_str = "SELECT file FROM " + AIdb.PROFILES_TABLE + " WHERE name=" \
                + AIdb.format_value('name', profile_name)
    query = AIdb.DBrequest(q_str)
    queue.put(query)
    query.waitAns()
    response = query.getResponse()
    # database error
    if response is None:
        raise SystemExit(missing_profile_error.format(
                         service=options.service_name, profile=profile_name))

    db_profile_path = response[0][0]

    # replace the file 
    try:
        shutil.copyfile(tmp_profile_path, db_profile_path)
    except IOError as err:
        raise SystemExit(_("Error:\t writing profile %s: %s") %
                         (profile_name, err))
    finally:
        os.unlink(tmp_profile_path)

    print >> sys.stderr, _("Profile updated successfully.")


if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    do_create_profile()

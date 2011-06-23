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
AI create-profile
"""
import gettext
import os.path
import sys
import tempfile

import lxml.etree

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc
import osol_install.auto_install.data_files as df
import osol_install.auto_install.publish_manifest as pub_man
import osol_install.auto_install.service_config as config

from optparse import OptionParser
from stat import S_IRWXU

from osol_install.auto_install.installadm_common import _, \
    validate_service_name
from osol_install.auto_install.service import AIService


def get_usage():
    '''
    Return usage for create-profile.
    '''
    return _("create-profile -n|--service <svcname> "
             "-f|--file <profile_file>... \n"
             "\t\t[-p|--profile <profile_name>]\n"
             "\t\t[-c|--criteria <criteria=value|range> ...] | \n"
             "\t\t[-C|--criteria-file <criteria_file>]")


def parse_options(cmd_options=None):
    """ Parse and validate options
    Args: cmd_options - command line handled by OptionParser
    Returns: options
    """
    parser = OptionParser(usage='\n' + get_usage())

    parser.add_option("-C", "--criteria-file", dest="criteria_file",
                      default='', help=_("Name of criteria XML file."))
    parser.add_option("-c", "--criteria", dest="criteria_c", action="append",
                      default=list(), metavar="CRITERIA",
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
    options = parse_options(cmd_options)

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
            continue
        # open profile file specified by user on command line
        if not os.path.exists(profile_file):
            print >> sys.stderr, _("File %s does not exist") % profile_file
        try:
            with open(profile_file, 'r') as pfp:
                raw_profile = pfp.read()
        except IOError as (errno, strerror):
            print >> sys.stderr, _("I/O error (%s) opening profile %s: %s") % \
                (errno, profile_file, strerror)
            continue

        # define all criteria in local environment for imminent validation
        for crit in AIdb.getCriteria(queue, table=AIdb.PROFILES_TABLE,
                onlyUsed=False, strip=True):
            if crit not in criteria_dict:
                continue
            val = criteria[crit]
            if not val:
                continue

            # Determine if this crit is a range criteria or not.
            is_range_crit = AIdb.isRangeCriteria(queue, crit,
                table=AIdb.PROFILES_TABLE)

            if is_range_crit:
                # Range criteria must be specified as a single value to be
                # supported for templating.
                if val[0] != val[1]:
                    continue

                # MAC specified in criteria - also set client-ID in environment
                if crit == 'mac':
                    val = val[0]
                    os.environ["AI_MAC"] = \
                        "%x:%x:%x:%x:%x:%x" % (
                                int(val[0:2], 16),
                                int(val[2:4], 16),
                                int(val[4:6], 16),
                                int(val[6:8], 16),
                                int(val[8:10], 16),
                                int(val[10:12], 16))
                    os.environ["AI_CID"] = "01" + str(val)
                # IP or NETWORK specified in criteria
                elif crit == 'network' or crit == 'ipv4':
                    val = val[0]
                    os.environ["AI_" + crit.upper()] = \
                        "%d.%d.%d.%d" % (
                                int(val[0:3]),
                                int(val[3:6]),
                                int(val[6:9]),
                                int(val[9:12]))
                else:
                    os.environ["AI_" + crit.upper()] = val[0]
            else:
                # Value criteria must be specified as a single value to be
                # supported for templating.
                if len(val) == 1:
                    os.environ["AI_" + crit.upper()] = val[0]

        tmpl_profile = raw_profile  # assume templating succeeded
        try:
            # resolve immediately (static)
            # substitute any criteria on command line
            tmpl_profile = sc.perform_templating(raw_profile, False)
            # validate profile according to any DTD
            profile_string = \
                    sc.validate_profile_string(tmpl_profile, image_dir,
                                               dtd_validation=True,
                                               warn_if_dtd_missing=True)
            if profile_string is None:
                continue
            full_profile_path = copy_profile_internally(tmpl_profile)
            if not full_profile_path:  # some failure handling file
                continue
        except KeyError:  # user specified bad template variable (not criteria)
            value = sys.exc_info()[1]  # take value from exception
            found = False
            # check if missing variable in error is supported
            for tmplvar in sc.TEMPLATE_VARIABLES:
                if "'" + tmplvar + "'" == str(value):  # values in sgl quotes
                    found = True  # valid template variable, but not in env
                    break
            if found:
                print >> sys.stderr, \
                    _("Error: template variable %s in profile %s was not "
                      "found among criteria or in the user's environment.") % \
                    (value, profile_name)
            else:
                print >> sys.stderr, \
                    _("Error: template variable %s in profile %s is not a "
                      "valid template variable.  Valid template variables: ") \
                    % (value, profile_name) + '\n\t' + \
                    ', '.join(sc.TEMPLATE_VARIABLES)
            continue
        # profile has XML/DTD syntax problem
        except lxml.etree.XMLSyntaxError, err:
            print tmpl_profile  # dump profile in error to stdout
            print >> sys.stderr, _('XML syntax error in profile %s:') % \
                    profile_name
            for eline in err:
                print >> sys.stderr, '\t' + eline
            continue

        # add new profile to database
        if not add_profile(criteria, profile_name, full_profile_path, queue,
                AIdb.PROFILES_TABLE):
            os.unlink(full_profile_path)  # failure, back out internal profile

if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    do_create_profile()

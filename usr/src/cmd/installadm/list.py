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
# Copyright (c) 2009, 2012, Oracle and/or its affiliates. All rights reserved.
#
"""
AI List Services
"""
import gettext
import os
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.service_config as config

from optparse import OptionParser

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from osol_install.auto_install.service import AIService, VersionError

# FDICT contains the width of each field that gets printed
FDICT = {
    'arch': 6,
    'cadd': 18,
    'status': 7,
}

STATUS_WORDS = [_('Status'), _('Default'), _('Inactive')]
DEFAULT = _("Default")
IGNORED = _("Ignored")
INACTIVE = _("Inactive")

_WARNED_ABOUT = set()

ARCH_UNKNOWN = _('* - Architecture unknown, service image does '
                 'not exist or is inaccessible.\n')


def warn_version(version_err):
    '''Prints a short warning about version incompatibility to stderr
    for a given service. For any one invocation of "installadm list"
    the warning will only be printed once.
    
    '''
    if version_err.service_name not in _WARNED_ABOUT:
        print >> sys.stderr, version_err.short_str()
        _WARNED_ABOUT.add(version_err.service_name)
        return True
    else:
        return False


def get_usage():
    ''' get usage for list'''
    return _("list\t[-n|--service <svcname>] [-c|--client] "
              "[-m|--manifest] [-p|--profile]")


def parse_options(cmd_options=None):
    """
    Parses and validate options

    Args
        None

    Returns
        a dictionary of the valid options

            { 'client':Bol, 'service':None/SName, 'manifest':Bol }

    Raises
        None

    """
    desc = _("Lists all enabled installation services on a system. "
             "Or, with -n option, lists a specific installation service. "
             "Or, with -c option, lists information about clients "
             "of installation services. "
             "Or, with -m option, lists the manifest information.")
    usage = '\n' + get_usage()
    parser = OptionParser(usage=usage, description=desc)

    parser.add_option("-n", "--service", dest="service", default=None,
                      type="string",
                      help=_("list information about named service"))
    parser.add_option("-c", "--client", dest="client", default=False,
                      action="store_true",
                      help=_("list client information"))
    parser.add_option("-m", "--manifest", dest="manifest", default=False,
                      action="store_true",
                      help=_("list manifest information"))
    parser.add_option("-p", "--profile", dest="profile", default=False,
                      action="store_true",
                      help=_("list profile information"))

    (loptions, args) = parser.parse_args(cmd_options)

    if args:
        parser.error(_('Unexpected argument(s): %s') % args)

    return loptions


def which_arch(service):
    """
    Looks to see if the platform of the service is i386 or sparc.
    If the service.image does not exist then we are unable to determine the
    architecture.

    Args
        service - service object to query

    Returns
        *       if service.arch is None
        otherwise return the value service.arch

    Raises
        None
    """
    if service.arch is None:
        return '*'

    return service.arch


def print_local_services(sdict, width, awidth):
    """
    Iterates over the local service dictionary and prints out
    service name, aliasof, status, architecture, and image path.
    All fields are left justified according to FDICT[field], width,
    awidth or simply printed in the case of path.

    The service dictionary looks like:

        {
            service1:
              [
                { 'status':on1, 'path':path1, 'arch':arch1 },
                ...
              ],
            ...
        }

    Args
        sdict = service dictionary
        width = length of longest service name
        awidth = length of longest aliasof service name

    Returns
        None

    Raises
        None
    """
    tkeys = sdict.keys()
    tkeys.sort()
    missing_image = False
    for aservice in tkeys:
        firstone = True
        for info in sdict[aservice]:
            if firstone == True:
                print aservice.ljust(width),
                firstone = False
            else:
                print ' ' * width
            print info['aliasof'].ljust(awidth),
            print info['status'].ljust(FDICT['status']),
            print info['arch'].ljust(FDICT['arch']),
            # If the architecture can't be identified, either the image is
            # missing or not accessible.
            if info['arch'] == "*":
                missing_image = True
            print info['path']

    if missing_image:
        print cw(ARCH_UNKNOWN)
    print


def find_clients(lservices, sname=None):
    """
    find_clients() returns a dictionary that contains a list of
    dictionaries.

    The service name is the key for the main dictionary and the
    client, image path, and arch are members of the subdictionary,
    as follows:

        {
          'service1': [
                { 'ipath':<path1>, 'client':<client1>, 'arch': <arch>},
                ....
                      ],
          ....
        }

    Args
        lservices = config.get_all_service_props()
        sname - service name, if only interesetd in clients of a
                specific service

    Returns
        dictionary of a list of dictionaries

    Raises
        None

    """
    sdict = dict()
    for servicename in lservices.keys():
        if sname and sname != servicename:
            continue
        try:
            service = AIService(servicename)
        except VersionError as version_err:
            warn_version(version_err)
            continue
        arch = which_arch(service)
        image_path = [service.image.path]
        client_info = config.get_clients(servicename)
        for clientkey in client_info:
            # strip off the leading '01' and reinsert ':'s
            client = AIdb.formatValue('mac', clientkey[2:])
            tdict = {'client': client, 'ipath': image_path, 'arch': arch}
            if servicename in sdict:  # existing service name
                slist = sdict[servicename]
                slist.extend([tdict])
                sdict[servicename] = slist
            else:  # new service name key
                sdict[servicename] = [tdict]
    return sdict


def do_header(lol):
    """
    Iterates over a list of list of the headers to print.
    The list of lists looks like:

        [
            [ 'field1', width1 ],
            ...
        ]
    Then it prints the resulting header and underlines based
    upon the widths.  The output looks like:

        Field1       Field2
        ------       ------

    The spacing between the fields is based upon the width.
    The underline is based upon the field name length.

    Args
        lol = list of lists

    Returns
        None

    Raises
        None
    """
    header = "\n"
    line = ""
    for part in lol:
        fname = part[0]
        header = header + fname[0:part[1]].ljust(part[1] + 1)
        line = line + "-" * len(fname[0:part[1]])
        line += ' ' * (part[1] - len(fname[0:part[1]]) + 1)
    print header
    print line


def get_local_services(services, sname=None):
    """
    Iterates over the local services on a host creating a dictionary
    with the service name as the key and status, path, architecture,
    and aliasof as the value.  If name is not None then it ensures
    that only the named service is retrieved.

    Args
        services = config.get_all_service_props()
        name = service name

    Returns
        a service dictionary made up of a list of dictionary of services.

        {
        service1:
          [
            {'status':on1, 'path':path1, 'arch':arch1, 'aliasof':aliasof1},
            ...
          ],
        ...
        }

        the width of the longest service name
        the width of the longest aliasof name

    Raises
        None
    """
    width = 0
    aliasofwidth = 1
    sdict = dict()
    for akey in services:
        serv = services[akey]
        servicename = akey
        # ensure that the current service has the keys we need.
        # if not, print error, but continue listing other services
        try:
            config.verify_key_properties(akey, serv)
        except config.ServiceCfgError as err:
            print >> sys.stderr, err
            continue
        try:
            service = AIService(servicename)
        except VersionError as err:
            warn_version(err)
            continue
        if config.PROP_ALIAS_OF in serv:
            image_path = service.image.path
            serv[config.PROP_IMAGE_PATH] = image_path
        
        info = dict()
        # if a service name is passed in then
        # ensure it matches the current name
        if not sname or sname == servicename:
            width = max(len(servicename), width)
            info['status'] = serv[config.PROP_STATUS]
            info['path'] = serv[config.PROP_IMAGE_PATH]
            info['arch'] = which_arch(service)
            if config.PROP_ALIAS_OF in serv:
                # have an alias
                aliasof = serv[config.PROP_ALIAS_OF]
            else:
                aliasof = '-'
            info['aliasof'] = aliasof
            aliasofwidth = max(len(aliasof), aliasofwidth)
            if servicename in sdict:
                slist = sdict[servicename]
                slist.extend([info])
                sdict[servicename] = slist
            else:
                sdict[servicename] = [info]
    
    return sdict, width, aliasofwidth


def list_local_services(services, name=None):
    """
    Lists the local services for a host.  If name is not
    None then it prints only the named service.

    Args
        services = config.get_all_service_props()
        name = service name

    Returns
        None

    Raises
        None
    
    """
    sdict, width, awidth = get_local_services(services, sname=name)
    
    width = max(width, len(_('Service Name')))
    awidth = max(awidth, len(_('Alias Of')))
    fields = [[_('Service Name'), width]]
    fields.extend([[_('Alias Of'), awidth]])
    fields.extend([[_('Status'), FDICT['status']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_local_services(sdict, width, awidth)


def list_local_clients(lservices, name=None):
    """
    Lists the local clients for a host or for a service
    if name is not None.

    Args
        lservices = config.get_all_service_props()
        service name

    Returns
        None

    Raises
        None
    """
    def get_clients(lservices, sname=None):
        """
        Gets the clients (x86 and Sparc) for the services of a local host.
        If a service name is passed in, then only get the clients for the
        named service on the local host.

        Args
            lservices = services on a host (config.get_all_service_props())
            sname = a named service

        Returns
            a service dictionary of both x86 and Sparc clients

                {
                    'service1': [
                                  {
                                    'ipath':[path1, path2],
                                    'client':client1,
                                    'arch':arch1
                                  },
                                ....
                                ],
                    ....
                }

        Raises
            None

        """

        allclients = find_clients(lservices, sname=sname)
        # get width of largest service name
        if allclients:
            width = max(map(len, allclients))
        else:
            width = 0

        return allclients, width

    def print_clients(width, sdict):
        """
        Iterates over a dictionary of service clients printing
        information about each one.

        Args
            width = widest service name
            sdict = service dictionary of clients
                    (same as in get_clients() description)

        Returns
            None

        Raises
            None
        """
        # sort the keys so that the service names are in alphabetic order.
        tkeys = sdict.keys()
        tkeys.sort()
        missing_image = False
        for aservice in tkeys:
            service_firstone = True
            for aclient in sdict[aservice]:
                if service_firstone == True:
                    print aservice.ljust(width),
                    service_firstone = False
                else:
                    print ' ' * width,
                print aclient['client'].ljust(FDICT['cadd']),
                print aclient['arch'].ljust(FDICT['arch']),
                # If the architecture can't be identified, either the image is
                # missing or not accessible.
                if aclient['arch'] == '*':
                    missing_image = True
                path_firstone = True
                cpaths = list()
                for cpath in aclient['ipath']:
                    if cpath not in cpaths:
                        if path_firstone == False:
                            spaces = width + FDICT['cadd'] + FDICT['arch'] + 2
                            print ' '.ljust(spaces),
                        else:
                            path_firstone = False
                        print cpath
                    cpaths.insert(0, cpath)
            if missing_image:
                print cw(ARCH_UNKNOWN)

    # start of list_local_clients
    sdict, width = get_clients(lservices, sname=name)
    if not sdict:
        if not name:
            print _('There are no clients configured for local services.\n')
        else:
            print _('There are no clients configured for local service, '
                    '"%s".\n') % name
        return

    width = max(width, len(_('Service Name')))
    fields = [[_('Service Name'), width]]
    fields.extend([[_('Client Address'), FDICT['cadd']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_clients(width, sdict)
    print


def get_manifest_or_profile_names(services, dbtable):
    """
    Iterate through the services retrieving
    all the stored manifest or profile names.

    Args
        services = dictionary of service properties
        dbtable = database table, distinguishing manifests from profiles

    Returns
        a dictionary of service manifests or profiles within a list:

            {
                servicename1:
                    [
                        [name, has_criteria (boolean), {crit:value, ... }],
                        ... 
                    ],
                ...
            }

        the width of the longest service name (swidth)

        the width of the longest manifest name (mwidth)

        the width of the longest criteria (cwidth)

    Raises
        None
    """
    swidth = 0
    mwidth = 0
    cwidth = 0
    sdict = dict()
    for sname in sorted(services.keys()):
        try:
            service = AIService(sname)
        except VersionError as err:
            warn_version(err)
            continue
        
        path = service.database_path
        
        if os.path.exists(path):
            try:
                maisql = AIdb.DB(path)
                maisql.verifyDBStructure()
                aiqueue = maisql.getQueue()
                swidth = max(len(sname), swidth)
                if not AIdb.tableExists(aiqueue, dbtable):
                    return sdict, swidth, mwidth
                for name in AIdb.getNames(aiqueue, dbtable):
                    mwidth = max(len(name), mwidth)
                    tdict = dict()
                    if dbtable == 'manifests':
                        instances = AIdb.numInstances(name, aiqueue)
                        for instance in range(0, instances):
                            criteria = AIdb.getTableCriteria(name,
                                            instance, aiqueue, dbtable,
                                            humanOutput=False,
                                            onlyUsed=True)
                            has_criteria = False
                            if criteria is not None:
                                for key in criteria.keys():
                                    if criteria[key] is not None:
                                        has_criteria = True
                                        break
                                if has_criteria:
                                    # We need criteria in human readable form
                                    hrcrit = AIdb.getTableCriteria(name,
                                                  instance, aiqueue, dbtable,
                                                  humanOutput=True,
                                                  onlyUsed=True)
                                    tdict, twidth = get_criteria_info(hrcrit)
                                    cwidth = max(twidth, cwidth)
                    else:
                        criteria = AIdb.getTableCriteria(name,
                                        None, aiqueue, dbtable,
                                        humanOutput=False,
                                        onlyUsed=True)
                        has_criteria = False
                        if criteria is not None:
                            for key in criteria.keys():
                                if criteria[key] is not None:
                                    has_criteria = True
                                    break
                    if sname in sdict:
                        slist = sdict[sname]
                        slist.append([name, has_criteria, tdict])
                        sdict[sname] = slist
                    else:
                        sdict[sname] = [[name, has_criteria, tdict]]
            except StandardError as err:
                sys.stderr.write(_('Error: AI database access error\n%s\n')
                                   % err)
                continue
        else:
            sys.stderr.write(_('Error: unable to locate AI database for "%s" '
                               'on server\n') % sname)
            continue

    return sdict, swidth, mwidth, cwidth


def get_criteria_info(crit_dict):
    """
    Iterates over the criteria which consists of a dictionary with
    possibly arch, min memory, max memory, min ipv4, max ipv4, min mac,
    max mac, cpu, platform, min network, max network and zonename converting
    it into a dictionary with arch, mem, ipv4, mac, cpu, platform, network
    and zonename.  Any min/max attributes are stored as a range within the
    new dictionary.

    Args
        crit_dict = dictionary of the criteria

    Returns
        dictionary of combined min/max and other criteria, formatted
           with possible endings such as MB
        maximum criteria width

    Raises
        None
    """

    if crit_dict is None:
        return dict(), 0

    # tdict values are formatted strings, with possible endings
    # such as MB.
    tdict = dict()

    crit_width = 0
    for key in crit_dict.keys():
        if key == 'service':
            continue
        is_range_crit = key.startswith('MIN') or key.startswith('MAX')
        # strip off the MAX or MIN for a new keyname
        if is_range_crit:
            keyname = key[3:]  # strip off the MAX or MIN for a new keyname
        else:
            keyname = key
        tdict.setdefault(keyname, '')
        db_value = crit_dict[key]
        if not db_value and not is_range_crit:
            # For non-range (value) criteria, None means it isn't set.
            # For range criteria, None means unbounded if the other
            # criteria in the MIN/MAX pair is set.
            continue    # value criteria not set
        crit_width = max(crit_width, len(keyname))
        fmt_value = AIdb.formatValue(key, db_value)
        if is_range_crit:
            if not db_value:
                fmt_value = "unbounded"
            if tdict[keyname] != '':
                if tdict[keyname] != fmt_value:  # dealing with range
                    if key.startswith('MAX'):
                        tdict[keyname] = tdict[keyname] + ' - ' + fmt_value
                    else:
                        tdict[keyname] = fmt_value + ' - ' + tdict[keyname]
                elif tdict[keyname] == "unbounded":
                    # MIN and MAX both unbounded, which means neither is
                    # set in db. Clear tdict value.
                    tdict[keyname] = ''   # no values for range, reset tdict
            else:  # first value, not range yet
                tdict[keyname] = fmt_value
                # if the partner MIN/MAX criterion is not set in the db,
                # handle now because otherwise it won't be processed.
                if key.startswith('MIN'):
                    if 'MAX' + keyname not in crit_dict.keys():
                        if fmt_value == "unbounded":
                            tdict[keyname] = ''
                        else:
                            tdict[keyname] = tdict[keyname] + ' - unbounded'
                else:
                    if 'MIN' + keyname not in crit_dict.keys():
                        if fmt_value == "unbounded":
                            tdict[keyname] = ''
                        else:
                            tdict[keyname] = 'unbounded - ' + tdict[keyname]
        else:
            tdict[keyname] = fmt_value

    return tdict, crit_width


def get_mfest_or_profile_criteria(sname, services, dbtable):
    """
    Iterate through all the manifests or profiles for the named service (sname)
    pointed to by the SCF service.

    Args
        sname = service name
        services = config.get_all_service_props()
        dbtable = database table, distinguishing manifests from profiles
            Assumed to be one of AIdb.MANIFESTS_TABLE or AIdb.PROFILES_TABLE

    Returns
        a dictionary of the criteria for the named service within a list:

            {
                servicename1:[
                             { 'arch':arch1, 'mem':memory1, 'ipv4':ipaddress1,
                               'mac':macaddr1, 'platform':platform1,
                               'network':network1, 'cpu':cpu1, 'zonename':z1 },
                             ...
                            ]
            }

        * Note1: platform, network and cpu are currently not-implemented
                 upstream.
        * Note2: could simply use a list of dictionaries but implemented as a
                 dictionary of a list of dictionary which will allow for
                 multiple services to be listed at the same time.

        width of longest manifest or profile name

        width of longest criteria

    Raises
        None
    """
    sdict = dict()
    width = 0
    cwidth = 0
    # ensure the named service is in our service dictionary.
    lservices = services.keys()
    if sname in lservices:
        try:
            path = AIService(sname).database_path
        except VersionError as version_err:
            warn_version(version_err)
            return sdict, width, cwidth

        if os.path.exists(path):
            try:
                maisql = AIdb.DB(path)
                maisql.verifyDBStructure()
                aiqueue = maisql.getQueue()
                if dbtable == AIdb.MANIFESTS_TABLE:
                    for name in AIdb.getNames(aiqueue, dbtable):
                        sdict[name] = list()
                        instances = AIdb.numInstances(name, aiqueue)
                        for instance in range(0, instances):
                            width = max(len(name), width)
                            criteria = AIdb.getManifestCriteria(name,
                                            instance, aiqueue,
                                            humanOutput=True,
                                            onlyUsed=True)
                            if criteria:
                                tdict, twidth = get_criteria_info(criteria)
                                cwidth = max(twidth, cwidth)
                                sdict[name].append(tdict)
                elif dbtable == AIdb.PROFILES_TABLE:
                    for name in AIdb.getNames(aiqueue, dbtable):
                        sdict[name] = list()
                        criteria = AIdb.getProfileCriteria(name,
                                        aiqueue,
                                        humanOutput=True,
                                        onlyUsed=True)
                        width = max(len(name), width)
                        tdict, twidth = get_criteria_info(criteria)
                        cwidth = max(twidth, cwidth)

                        sdict[name].append(tdict)
                else:
                    raise ValueError("Invalid value for dbtable: %s" % dbtable)

            except StandardError as err:
                sys.stderr.write(_('Error: AI database access error\n%s\n')
                                   % err)
                sys.exit(1)
        else:
            sys.stderr.write(_('Error: unable to locate AI database on server '
                               'for %s\n') % sname)
            sys.exit(1)

    return sdict, width, cwidth


def print_service_manifests(sdict, sname, width, swidth, cwidth):
    """
    Iterates over the criteria dictionary printing each non blank
    criteria.  The manifest dictionary is populated via
    get_mfest_or_profile_criteria().

    Args
        sdict = criteria dictionary
                (same as in get_mfest_or_profile_criteria() description)

        sname = name of service

        width = widest manifest name

        swidth = width of status column

        cwidth = widest criteria name (0 if no criteria)

    Returns
        None

    Raises
        None
    """
    default_mfest = None
    inactive_mfests = list()
    active_mfests = list()

    width += 1
    swidth += 1

    mnames = sdict.keys()
    if not mnames:
        return
    mnames.sort()

    try:
        default_mname = AIService(sname).get_default_manifest()
    except StandardError:
        default_mname = ""

    ordered_keys = ['arch', 'mac', 'ipv4']
    if cwidth > 0:
        # Criteria are present.
        keys = sdict[mnames[0]][0].keys()
        keys.sort()
        for akey in keys:
            if akey not in ordered_keys:
                ordered_keys.append(akey)

    for name in mnames:
        manifest_list = [name]
        if cwidth > 0:
            for ldict in sdict[name]:
                for akey in ordered_keys:
                    if akey in ldict and ldict[akey] != '':
                        manifest_list.append(akey.ljust(cwidth) + ' = ' +
                                             ldict[akey])
        if name == default_mname:
            default_mfest = manifest_list
        elif len(manifest_list) == 1:
            inactive_mfests.append(manifest_list)
        else:
            active_mfests.append(manifest_list)

    for mfest in active_mfests:
        # Active manifests have at least one criterion.
        print mfest[0].ljust(width) + ''.ljust(swidth) + mfest[1]
        for other_crit in range(2, len(mfest)):
            print ' '.ljust(width + swidth) + mfest[other_crit]
        print
    if default_mfest:
        # Since 'Default' is used in status column, it is in STATUS_WORDS
        # and so swidth accommodates it.
        first_line = default_mfest[0].ljust(width) + \
            DEFAULT.ljust(swidth)
        if len(default_mfest) > 1:
            first_line += "(" + IGNORED + ": " + default_mfest[1] + ")"
        else:
            first_line += "None"
        print first_line
        for other_crit in range(2, len(default_mfest)):
            print ''.ljust(width + swidth) + \
                "(" + IGNORED + ": " + default_mfest[other_crit] + ")"
        print
    for mfest in inactive_mfests:
        # Since 'Inactive' is used in status column, it is in STATUS_WORDS.
        # and so swidth accommodates it.
        print mfest[0].ljust(width) + INACTIVE.ljust(swidth) + \
            _("None")
        print


def print_service_profiles(sdict, width, cwidth):
    """
    Iterates over the criteria dictionary printing each non blank
    criteria.  The profile dictionary is populated via
    get_mfest_or_profile_criteria().

    Args
        sdict = criteria dictionary
                (same as in get_mfest_or_profile_criteria() description)

        width = widest profile name

        cwidth = widest criteria name (0 if no criteria)

    Returns
        None

    Raises
        None
    """
    pnames = sdict.keys()
    if not pnames:
        return
    pnames.sort()

    ordered_keys = ['arch', 'mac', 'ipv4']
    if cwidth > 0:
        # Criteria are present.
        keys = sdict[pnames[0]][0].keys()
        keys.sort()
        for akey in keys:
            if akey not in ordered_keys:
                ordered_keys.append(akey)

    for name in pnames:
        print name.ljust(width),
        first = True
        if cwidth > 0:
            for ldict in sdict[name]:
                for akey in ordered_keys:
                    if akey in ldict and ldict[akey] != '':
                        if not first:
                            print ''.ljust(width),
                        first = False
                        print akey.ljust(cwidth) + ' = ' + ldict[akey]
        # Flush line if no criteria displayed.
        if first:
            print "None"
        print


def print_local_manifests(sdict, smwidth, mfindent, stwidth, cwidth):
    """
    Iterates over the name dictionary printing each
    manifest or criteria within the dictionary.  The name dictionary
    is populated via get_manifest_or_profile_names().

    Args
        sdict = service manifest dictionary

            {
                'servicename1':
                    [
                        [ manifestfile1, has_criteria (boolean), {} ],
                        ...
                    ],
                ...
            }

        smwidth = the length of the widest service or manifest name

        mfindent = how many spaces will be manifest name indented

        stwidth = width of status column

        cwidth = the length of the widest criteria

    Returns
        None

    Raises
        None
    """

    tkeys = sdict.keys()
    tkeys.sort()
    smwidth += 1
    stwidth += 1
    for akey in tkeys:
        default_mfest = None
        inactive_mfests = list()
        active_mfests = list()
        try:
            default_mname = AIService(akey).get_default_manifest()
        except StandardError:
            default_mname = ""
        for manifest_item in sdict[akey]:
            # manifest_items are a list of
            # [ name, number of criteria, criteria_dictionary ]

            if manifest_item[0] == default_mname:
                default_mfest = manifest_item  # There could be max 1 default
            elif manifest_item[1]:  # has_criteria and not default
                active_mfests.append(manifest_item)
            else:
                inactive_mfests.append(manifest_item)

        print akey  # print service name on separate line

        line = ''.ljust(mfindent)  # Manifest is indented
        for manifest_i in active_mfests:
            line += manifest_i[0].ljust(smwidth - mfindent)  # Manifest
            line += ''.ljust(stwidth)  # Status is empty for active mfests
            ordered_keys = ['arch', 'mac', 'ipv4']
            keys = manifest_i[2].keys()
            keys.sort()
            for k in keys:
                if k not in ordered_keys:
                    ordered_keys.append(k)
            crit_printed = False
            for k in ordered_keys:
                if k in manifest_i[2] and manifest_i[2][k] != '':
                    line += k.ljust(cwidth) + ' = ' + manifest_i[2][k]
                    print line
                    crit_printed = True
                    line = ''.ljust(mfindent) + \
                        ''.ljust(smwidth - mfindent) + ''.ljust(stwidth)
            if not crit_printed:
                line += _("None")
                print line
            print  # Blank line after each manifest
            line = ''.ljust(mfindent)

        if default_mfest:
            line += default_mfest[0].ljust(smwidth - mfindent)  # Manifest name
            line += DEFAULT.ljust(stwidth)  # Status is Default
            # Default manifest can have ignored criteria
            ordered_keys = ['arch', 'mac', 'ipv4']
            keys = default_mfest[2].keys()
            keys.sort()
            for k in keys:
                if k not in ordered_keys:
                    ordered_keys.append(k)
            crit_printed = False
            for k in ordered_keys:
                if k in default_mfest[2] and default_mfest[2][k] != '':
                    line += '(' + IGNORED + ': ' + k.ljust(cwidth) + \
                        ' = ' + default_mfest[2][k] + ')'
                    print line
                    crit_printed = True
                    line = ''.ljust(mfindent) + \
                        ''.ljust(smwidth - mfindent) + ''.ljust(stwidth)
            if not crit_printed:
                line += _("None")
                print line
            line = ''.ljust(mfindent)
            print  # Blank line after each manifest
        for manifest_i in inactive_mfests:
            line += manifest_i[0].ljust(smwidth - mfindent)  # Manifest
            line += INACTIVE.ljust(stwidth)
            line += _("None")  # Inactive manifests have no criteria
            print line
            print  # Blank line after each manifest
            line = ''.ljust(mfindent)


def print_local_profiles(sdict, swidth):
    """
    Iterates over the name dictionary printing each
    profile or criteria within the dictionary.  The name dictionary
    is populated via get_manifest_or_profile_names().

    Args
        sdict = service profile dictionary

            {
                'servicename1':
                    [
                        [ profile1, has_criteria (boolean) ],
                        ...
                    ],
                ...
            }

        swidth = the length of the widest service name

    Returns
        None

    Raises
        None
    """
    tkeys = sdict.keys()
    tkeys.sort()
    swidth += 1
    for akey in tkeys:
        first_for_service = True
        # profile_items are a list of [ name, number of criteria ]
        for profile_item in sdict[akey]:
            if first_for_service:
                print akey.ljust(swidth) + profile_item[0]
                first_for_service = False
            else:
                print ''.ljust(swidth) + profile_item[0]
    print


def list_local_manifests(services, name=None):
    """
    list the local manifests.  If name is not passed in then
    print all the local manifests. List also the associated
    manifest criteria.

    Args
        services = config.get_all_service_props()
        name = service name

    Returns
        None

    Raises
        None
    """
    # list -m
    if not name:
        sdict, swidth, mwidth, cwidth = get_manifest_or_profile_names(services,
                                                     AIdb.MANIFESTS_TABLE)
        if not sdict:
            output = _('There are no manifests configured for local '
                       'services.\n')
            sys.stdout.write(output)
            return
        # manifest should be indented 3 spaces
        mfindent = 3
        smwidth = max(swidth, mwidth + mfindent,
            len(_('Service/Manifest Name'))) + 1
        fields = [[_('Service/Manifest Name'), smwidth]]
        stwidth = max([len(item) for item in STATUS_WORDS]) + 1
        fields.extend([[_('Status'), stwidth]])
        fields.extend([[_('Criteria'), len(_('Criteria'))]])

        do_header(fields)
        print_local_manifests(sdict, smwidth, mfindent, stwidth, cwidth)
    # list -m -n <service>
    else:
        sdict, mwidth, cwidth = \
            get_mfest_or_profile_criteria(name, services, AIdb.MANIFESTS_TABLE)
        if not sdict:
            output = _('There are no manifests configured for local service, '
                       '"%s".\n') % name
            sys.stdout.write(output)
            return

        mwidth = max(mwidth, len(_('Manifest'))) + 1
        fields = [[_('Manifest'), mwidth]]
        stwidth = max([len(item) for item in STATUS_WORDS]) + 1
        fields.extend([[_('Status'), stwidth]])
        fields.extend([[_('Criteria'), len(_('Criteria'))]])

        do_header(fields)
        print_service_manifests(sdict, name, mwidth, stwidth, cwidth)


def list_local_profiles(linst, name=None):
    """
    list the local profiles.  If name is not passed in then
    print all the local profiles.  Otherwise list the named
    service's profiles' criteria.

    Args
        inst = smf.AISCF()
        name = service name

    Returns
        None

    Raises
        None
    """
    # list -p
    if not name:
        sdict, swidth, mwidth, cwidth = \
                get_manifest_or_profile_names(linst, AIdb.PROFILES_TABLE)
        if not sdict:
            output = _('There are no profiles configured for local '
                       'services.\n')
            sys.stdout.write(output)
            return

        swidth = max(swidth, len(_('Service Name'))) + 1
        fields = [[_('Service Name'), swidth]]
        mwidth = max(mwidth, len(_('Profile')))
        fields.extend([[_('Profile'), mwidth]])

        do_header(fields)
        print_local_profiles(sdict, swidth)
    # list -p -n <service>
    else:
        sdict, mwidth, cwidth = \
            get_mfest_or_profile_criteria(name, linst, AIdb.PROFILES_TABLE)
        if not sdict:
            output = _('There are no profiles configured for local service, '
                       '"%s".\n') % name
            sys.stdout.write(output)
            return

        mwidth = max(mwidth, len(_('Profile'))) + 1
        fields = [[_('Profile'), mwidth]]
        fields.extend([[_('Criteria'), len(_('Criteria'))]])

        do_header(fields)
        print_service_profiles(sdict, mwidth, cwidth)


def do_list(cmd_options=None):
    '''
    List information about AI services, clients, and manifests.
        -n option, lists a specific install service.
        -c option, lists information about clients
            of install services.
        -m option, lists the manifest information.
        -p options, lists profiles

    '''
    options = parse_options(cmd_options)

    services = config.get_all_service_props()
    if not services:
        if options.service:
            raise SystemExit(_('Error: Service does not exist: "%s".\n') %
                               options.service)
        else:
            output = _('There are no services configured on this server.\n')
            sys.stdout.write(output)
            raise SystemExit(0)

    if options.service and options.service not in services:
        raise SystemExit(_('Error: Service does not exist: "%s".\n') %
                           options.service)

    # list
    if not options.client and not options.manifest and not options.profile:
        try:
            list_local_services(services, name=options.service)
        except (config.ServiceCfgError, ValueError) as err:
            raise SystemExit(err)
    else:
        # list -c
        if options.client:
            list_local_clients(services, name=options.service)
        # list -m
        if options.manifest:
            if options.client:
                print
            list_local_manifests(services, name=options.service)
        # list -p
        if options.profile:
            if options.client or options.manifest:
                print
            list_local_profiles(services, name=options.service)


if __name__ == '__main__':
    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_list()

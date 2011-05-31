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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#
"""

AI List Services

"""
import gettext
import os
import socket
import sys

from optparse import OptionParser

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.installadm_common as com
import osol_install.libaiscf as smf

from osol_install.auto_install.ai_smf_service import PROP_IMAGE_PATH, \
    PROP_SERVICE_NAME, PROP_STATUS, PROP_TXT_RECORD
from osol_install.auto_install.properties import get_service_info, get_default
from solaris_install import _

# FDICT contains the max width of each field that gets printed, plus one space.
# Note that "print item," adds another space, for a total of 2 between fields.
FDICT = {
    'arch': 6,
    'cadd': 18,
    'status': 7,
    'port': 6
}

STATUS_WORDS = [_('Status'), _('Default'), _('Inactive')]

DEFAULT = _("Default")
IGNORED = _("Ignored")
INACTIVE = _("Inactive")


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
    desc = _("Lists all enabled install services on a system. "
             "Or, with -n option, lists a specific install service. "
             "Or, with -c option, lists information about clients "
             "of install services. "
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


def which_arch(path):
    """
    Looks to see if the platform pointed to by path is x86 or Sparc.
    If the path does not exist then we are unable to determine the
    architecture.

    Args
        path = directory path to examine

    Returns
        x86     if <path>/platform/i86pc exists
        Sparc   if <path>/platform/sun4v exists
        -       if neither exists

    Raises
        None
    """
    lpath = os.path.join(path, 'platform/i86pc')
    if os.path.exists(lpath):
        arch = 'x86'
    else:
        lpath = os.path.join(path, 'platform/sun4v')
        if os.path.exists(lpath):
            arch = 'Sparc'
        else:
            arch = '-'

    return arch


def print_local_services(sdict, width):
    """
    Iterates over the local service dictionary and prints out the
    service name, status, architecture, port and image path.
    All fields are left justified according to FDICT[field] or
    width or simply printed in the case of path.

    The service dictionary looks like:

        {
            service1:
              [
                { 'status':on1, 'path':path1, 'arch':arch1, 'port':port1 },
                ...
              ],
            ...
        }

    Args
        sdict = service dictionary
        width = length of largest service name

    Returns
        None

    Raises
        None
    """
    tkeys = sdict.keys()
    tkeys.sort()
    for aservice in tkeys:
        firstone = True
        for info in sdict[aservice]:
            if firstone == True:
                print aservice.ljust(width + 1),
                firstone = False
            else:
                print ' '.ljust(width + 1),
            print info['status'].ljust(FDICT['status']),
            print info['arch'].ljust(FDICT['arch']),
            print info['port'].ljust(FDICT['port']),
            print info['path']
    print


def has_key(service, key):
    """
    has_key checks an AIservice for a specific key
    If the key exists within the SCF AIservice then
    return True otherwise return False.

    This function is necessary because SCF object does
    not have the get() and has_key() methods defined.
    Once these have been defined the has_key(serv, ...)
    code can be changed to serv.has_key(...).

    Args
        service = dictionary of services
        key = key within dictionary

    Returns
        True if key is in service
        False if not

    Raises
        None
    """
    return key in service.keys()


def find_sparc_clients(lservices, sname=None):
    """
    find_sparc_clients() searches /etc/netboot for all clients and
    returns a dictionary that contains a list of dictionaries.

    The service name is the key for the main dictionary and the
    client and image path are members of the subdictionary.  The
    dictionary will look something like:

        {
            'service1': [
                        { 'ipath':<path1>, 'client':<client1> },
                        ....
                        ],
            ....
        }

    The information is spread out across a couple of different
    files within the server.  The Client is embedded within a
    directory path (/etc/netboot/<IP Network>/01<client>).  The
    Image Path is in the wanboot.conf file pointed to by the
    Client path.  The Service Name is contained in the install.conf
    file pointed to by the Image Path.

    We first get the IP addresses for the host.  Then while only
    using IPv4 address we iterate over the client directories within
    /etc/netboot/<IP Network> to get the Image Path and Service Name.
    The client and image path are then added to the named service
    dictionary list.

    Args
        lservices =
        sname =

    Returns
        dictionary of a list of dictionaries

    Raises
        None
    """

    installconf = 'install.conf'
    wanbootconf = 'wanboot.conf'

    def get_image_path(lpath):
        """
        gets the Image Path for the client pointed to by lpath.
        The Image Path on Sparc is stored in the wanboot.conf file.

        Args
            lpath = path for directory which contains wanboot.conf file

        Returns
            image path for client

        Raises
            None
        """
        try:
            confpath = os.path.join(lpath, wanbootconf)
            sinfo = os.stat(confpath)
            with open(confpath) as fp:
                fstr = fp.read(sinfo.st_size)
        except (OSError, IOError):
            sys.stderr.write("Error: while accessing wanboot.conf file "
                             "(%s/wanboot.conf)\n" % lpath)
            return

        start = fstr.find('boot_file=') + len('boot_file=')
        end = fstr[start:].find('/platform')

        return fstr[start:start + end]

    def get_service_name(lpath):
        """
        gets the Service Name for the client from the lpath pointed
        to by the wanboot.conf file.  The Service Name is in the
        Image Path install.conf file.

        Args
            lpath = path to directory containing install.conf file

        Returns
            install service for client

        Raises
            None
        """
        try:
            confpath = os.path.join(lpath, installconf)
            sinfo = os.stat(confpath)
            with open(confpath) as fp:
                fstr = fp.read(sinfo.st_size)
        except (OSError, IOError):
            sys.stderr.write("Error: while accessing "
                             "install.conf file\n")
            return

        start = fstr.find('install_service=') + len('install_service=')
        end = fstr[start:].find('\n')

        return fstr[start:start + end]

    # start of find_sparc_clients
    if not os.path.exists(com.NETBOOT):
        return {}

    sdict = {}
    hostname = socket.getfqdn()
    ipaddr = socket.gethostbyname(hostname)
    # get the Network IP path for the host
    end = ipaddr.rfind('.')
    compatibility_path = os.path.join(com.NETBOOT, ipaddr[:end] + '.0')

    for path in [compatibility_path, com.NETBOOT]:
        if not os.path.exists(path) or not os.path.isdir(path):
            continue
        for clientdir in os.listdir(path):
            if not clientdir.startswith('01'):
                continue
            # strip off the 01 in the clientdir
            client = AIdb.formatValue('mac', clientdir[2:])

            # get the Image from the clientdir/wanboot.conf file
            ipath = get_image_path(os.path.join(path, clientdir))

            if not ipath or not os.path.exists(ipath):
                continue

            # get the service name from the ipath/install.conf file
            servicename = get_service_name(ipath)

            # Store the client and image path in the dictionary under the
            # service name.  First, check to see if the service name key
            # already exists.  If the service name key does not already exist
            # then add it to the dictionary.  If the service name key does
            # exist then extend the list and update the dictionary.
            if servicename in lservices and \
              (not sname or servicename == sname):
                tdict = {'client': client, 'ipath': [ipath], 'arch': 'Sparc'}
                if servicename in sdict:  # existing service name key
                    slist = sdict[servicename]
                    slist.extend([tdict])
                    sdict[servicename] = slist
                else:  # new service name key
                    sdict[servicename] = [tdict]

    return sdict


def find_x86_clients(lservices, sname=None):
    """
    find_x86_clients() searches TFTPDir for all clients and
    returns a dictionary that contains a list of dictionaries.

    The service name is the key for the main dictionary and the
    client and image path are members of the subdictionary.  The
    dictionary will look something like:

        {
            'service1': [
                        { 'ipath':<path1>, 'client':<client1> },
                        ....
                        ],
            ....
        }

    The information is contained within the menu.lst.01<client>
    file.  Though not the best approach architecturally it is
    the only method currently available.

    We first get the TFTProot directory.  Then iterate over the
    files within the TFTProot directory to get the client menu
    which contains the Image Path and Service Name.  The client
    and image path are then added to the named service dictionary
    list.
    """
    def get_menu_info(path):
        """
        Reads TFTPboot/menu.list file pointed to by 'path' via
        GrubMenu class in installadm_common.py.  Getting the
        install path from the install_media field, service name
        from install_service

        Args
            path = path for the menu.list.01<client> file.

        Returns
            a dictionary of services made up of a list of tuples of
            port, install path

        Raises
            None
        """
        iaddr = 'install_svc_address='
        iserv = 'install_service='
        imedia = 'install_media=http://'

        rdict = {}
        menu = com.GrubMenu(file_name=path)
        entries = menu.entries[0]
        if entries:
            if 'kernel$' in menu[entries]:
                mdict = menu[entries]['kernel$']
                start = mdict.find(iserv) + len(iserv)
                service = mdict[start:].split(',')[0]
                start = mdict.find(iaddr) + len(iaddr)
                port = mdict[start:].split(',')[0].split(':')[-1]
                start = mdict.find(imedia) + len(imedia)
                pstart = mdict[start:].split(',')[0].find('/')
                path = mdict[start:].split(',')[0][pstart:]
                if service in rdict:
                    tlist = rdict[service]
                    tlist.extend([(port, path)])
                    rdict[service] = tlist
                else:
                    rdict[service] = [(port, path)]

        return rdict

    # start of find_x86_clients
    sdict = {}
    tftp_dir = com.find_TFTP_root()
    if tftp_dir and os.path.exists(tftp_dir):
        for filenames in os.listdir(tftp_dir):
            if filenames.find("menu.lst.01") >= 0:
                path = os.path.join(tftp_dir, filenames)
                pservices = get_menu_info(path)
                tdict = {'client': '', 'ipath': '', 'arch': 'x86'}
                for servicename in pservices:
                    if servicename in lservices and \
                      (not sname or servicename == sname):
                        client = AIdb.formatValue('mac', filenames[11:])
                        tdict['client'] = client
                        # create a list of image_paths for the client
                        ipath = []
                        for tup in pservices[servicename]:
                            ipath.insert(0, tup[1])
                        tdict['ipath'] = ipath
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


def list_local_services(linst, name=None):
    """
    Lists the local services for a host.  If name is not
    None then it prints only the named service.

    Args
        linst = smf.AISCF()
        name = service name

    Returns
        None

    Raises
        None
    """

    def get_local_services(linst, sname=None):
        """
        Iterates over the local services on a host creating a dictionary
        with the service name as the key and status, path, architecture
        and port as the value.  If name is not None then it ensures that
        only the named services is retrieved.

        Args
            linst = smf.AISCF()
            name = service name

        Returns
            a service dictionary made up of a list of dictionary of services.

            {
                service1:
                  [
                    { 'status':on1, 'path':path1, 'arch':arch1, 'port':port1 },
                    ...
                  ],
                ...
            }

            the width of the widest service name

        Raises
            None
        """
        width = 0
        sdict = {}
        for akey in linst.services.keys():
            serv = smf.AIservice(linst, akey)
            # ensure that the current service has the keys we need.
            # if not then report the error and exit.
            if not (has_key(serv, PROP_SERVICE_NAME) and
                    has_key(serv, PROP_STATUS) and
                    has_key(serv, PROP_IMAGE_PATH) and
                    has_key(serv, PROP_TXT_RECORD)):
                sys.stderr.write(_('Error: SMF service key '
                                   'property does not exist\n'))
                sys.exit(1)

            servicename = serv[PROP_SERVICE_NAME]
            info = {'status': '', 'arch': '', 'port': '', 'path': ''}
            # if a service name is passed in then
            # ensure it matches the current name
            if not sname or sname == servicename:
                width = max(len(servicename), width)
                info['status'] = serv[PROP_STATUS]
                info['path'] = serv[PROP_IMAGE_PATH]
                info['port'] = serv[PROP_TXT_RECORD].split(':')[-1]
                info['arch'] = which_arch(info['path'])
                if servicename in sdict:
                    slist = sdict[servicename]
                    slist.extend([info])
                    sdict[servicename] = slist
                else:
                    sdict[servicename] = [info]

        return sdict, width

    # start of list_local_services
    sdict, width = get_local_services(linst, sname=name)
    if sdict == {}:
        if name != None:
            estr = _('Error: no service named "%s".\n') % name
        else:
            estr = _('Error: no local service\n')
        sys.stderr.write(estr)
        sys.exit(1)

    width = max(width, len(_('Service Name')))
    fields = [[_('Service Name'), width + 1]]
    fields.extend([[_('Status'), FDICT['status']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Port'), FDICT['port']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_local_services(sdict, width)


def list_local_clients(lservices, name=None):
    """
    Lists the local clients for a host or for a service
    if name is not None.

    Args
        inst = smf.AISCF()
        service name

    Returns
        None

    Raises
        None
    """
    def get_clients(lservices, sname=None):
        """
        Gets the clients (x86 and Sparc) for the services of a local host.
        If a service name is passed in the only get the clients for the
        named service on the local host.

        Args
            lservices = services on a host
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
        def merge_dictionaries(first, second):
            """
            Merges two similar dictionaries and returns the resulting
            dictionary.  The dictionaries are the same as in get_clients()
            description.
            """
            rdict = {}
            rdict.update(first)
            rdict.update(second)
            for key in set(first.keys()) & set(second.keys()):
                rdict[key] = first[key] + second[key]

            return rdict

        def calculate_service_name_widths(ldict):
            """
            Iterates over the client dictionary calculating the maximum
            service name length.

            Args
                ldict = dictionary of clients on a host with the
                        service name as the dictionary key
                        (same as in get_clients() description)
            Returns
                width of the largest key.

            Raises
                None
            """
            width = 0
            for akey in ldict:
                width = max(len(akey), width)

            return width

        sdict = find_sparc_clients(lservices, sname=sname)
        xdict = find_x86_clients(lservices, sname=sname)
        botharchs = {}
        if sdict != {} and xdict != {}:
            botharchs = merge_dictionaries(sdict, xdict)
        elif sdict != {}:
            botharchs = sdict
        elif xdict != {}:
            botharchs = xdict

        width = calculate_service_name_widths(botharchs)

        return botharchs, width

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
        for aservice in tkeys:
            service_firstone = True
            for aclient in sdict[aservice]:
                if service_firstone == True:
                    print aservice.ljust(width + 1),
                    service_firstone = False
                else:
                    print ' '.ljust(width + 1),
                print aclient['client'].ljust(FDICT['cadd']),
                print aclient['arch'].ljust(FDICT['arch']),
                path_firstone = True
                cpaths = []
                for cpath in aclient['ipath']:
                    if cpath not in cpaths:
                        if path_firstone == False:
                            spaces = width + FDICT['cadd'] + FDICT['arch'] + 2
                            print ' '.ljust(spaces),
                        else:
                            path_firstone = False
                        print cpath
                    cpaths.insert(0, cpath)

    # start of list_local_clients
    sdict, width = get_clients(lservices, sname=name)
    if sdict == {}:
        if not name:
            estr = _('Error: no clients for local service\n')
        else:
            estr = _('Error: no clients for local '
                     'service named "%s".\n') % name
        sys.stderr.write(estr)
        sys.exit(1)

    width = max(width, len(_('Service Name')))
    fields = [[_('Service Name'), width + 1]]
    fields.extend([[_('Client Address'), FDICT['cadd']]])
    fields.extend([[_('Arch'), FDICT['arch']]])
    fields.extend([[_('Image Path'), len(_('Image Path'))]])

    do_header(fields)
    print_clients(width, sdict)
    print


def get_manifest_or_profile_names(linst, dbtable):
    """
    Iterate through the services from smf.AISCF() retrieving
    all the stored manifest or profile names.

    Args
        inst = smf.AISCF()
        dbtable = database table, distinguishing manifests from profiles

    Returns
        a dictionary of service manifests or profiles within a list:

            {
                servicename1:[ file1, file2, ...],
                ...
            }

        the width of the longest service name (swidth)

        the width of the longest manifest name (mwidth)

    Raises
        None
    """
    swidth = 0
    mwidth = 0
    sdict = {}
    lservices = linst.services.keys()
    lservices.sort()
    for akey in lservices:
        serv = smf.AIservice(linst, akey)
        # ensure that the current service has the keys we need.
        # if not then continue with the next service.
        if not (has_key(serv, PROP_SERVICE_NAME) and
                has_key(serv, PROP_TXT_RECORD)):
            sys.stderr.write(_('Error: SMF service key '
                               'property does not exist\n'))
            sys.exit(1)

        sname = serv[PROP_SERVICE_NAME]
        dummy, path, dummy = get_service_info(sname)

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
                        slist.append([name, has_criteria])
                        sdict[sname] = slist
                    else:
                        sdict[sname] = [[name, has_criteria]]
            except StandardError, err:
                sys.stderr.write(_('Error: AI database '
                                   'access error\n%s\n') % err)
                sys.exit(1)
        else:
            sys.stderr.write(_('Error: unable to locate '
                               'AI database on server\n'))
            sys.exit(1)

    return sdict, swidth, mwidth


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
        return {}, 0
    # tdict values are formatted strings, with possible endings
    # such as MB.

    tdict = {}

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


def get_mfest_or_profile_criteria(sname, linst, dbtable):
    """
    Iterate through all the manifests or profiles for the named service (sname)
    pointed to by the SCF service.

    Args
        sname = service name
        inst = smf.AISCF()
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
    sdict = {}
    width = 0
    cwidth = 0
    # ensure the named service is in our service dictionary.
    lservices = linst.services.keys()
    if sname in lservices:
        serv = smf.AIservice(linst, sname)
        if not has_key(serv, PROP_TXT_RECORD):
            sys.stderr.write(_('Error: SMF service key '
                               'property does not exist\n'))
            sys.exit(1)

        dummy, path, dummy = get_service_info(sname)
        if os.path.exists(path):
            try:
                maisql = AIdb.DB(path)
                maisql.verifyDBStructure()
                aiqueue = maisql.getQueue()
                if dbtable == AIdb.MANIFESTS_TABLE:
                    for name in AIdb.getNames(aiqueue, dbtable):
                        sdict[name] = []
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
                                sdict[name].extend([tdict])
                elif dbtable == AIdb.PROFILES_TABLE:
                    for name in AIdb.getNames(aiqueue, dbtable):
                        sdict[name] = []
                        criteria = AIdb.getProfileCriteria(name,
                                        aiqueue,
                                        humanOutput=True,
                                        onlyUsed=True)
                        width = max(len(name), width)
                        tdict, twidth = get_criteria_info(criteria)
                        cwidth = max(twidth, cwidth)
                        sdict[name].extend([tdict])
                else:
                    sys.stderr.write(_('Error: Invalid dbtable: %s\n') %
                                       str(dbtable))
                    sys.exit(1)
            except StandardError, err:
                sys.stderr.write(_('Error: AI database access '
                                   'error\n%s\n') % err)
                sys.exit(1)
        else:
            sys.stderr.write(_('Error: unable to locate '
                               'AI database on server for %s\n') % sname)
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
    inactive_mfests = []
    active_mfests = []

    width += 1
    swidth += 1
    cwidth += 1

    mnames = sdict.keys()
    if mnames == []:
        return
    mnames.sort()

    try:
        default_mname = get_default(sname)
    except StandardError:
        default_mname = ""

    ordered_keys = ['arch', 'mac', 'ipv4']
    if cwidth > 1:
        # Criteria are present.
        keys = sdict[mnames[0]][0].keys()
        keys.sort()
        for akey in keys:
            if akey not in ordered_keys:
                ordered_keys.append(akey)

    for name in mnames:
        manifest_list = [name]
        if cwidth > 1:
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
    width += 1
    cwidth += 1

    pnames = sdict.keys()
    if pnames == []:
        return
    pnames.sort()

    ordered_keys = ['arch', 'mac', 'ipv4']
    if cwidth > 1:
        # Criteria are present.
        keys = sdict[pnames[0]][0].keys()
        keys.sort()
        for akey in keys:
            if akey not in ordered_keys:
                ordered_keys.append(akey)

    for name in pnames:
        print name.ljust(width),
        first = True
        if cwidth > 1:
            for ldict in sdict[name]:
                for akey in ordered_keys:
                    if akey in ldict and ldict[akey] != '':
                        if not first:
                            print ''.ljust(width),
                        first = False
                        print akey.ljust(cwidth) + ' = ' + ldict[akey]
        # Flush line if no criteria displayed.
        if first:
            print
        print


def print_local_manifests(sdict, swidth, mwidth):
    """
    Iterates over the name dictionary printing each
    manifest or criteria within the dictionary.  The name dictionary
    is populated via get_manifest_or_profile_names().

    Args
        sdict = service manifest dictionary

            {
                'servicename1':
                    [
                        [ manifestfile1, has_criteria (boolean) ],
                        ...
                    ],
                ...
            }

        swidth = the length of the widest service name

        mwidth = the length of the widest manifest name

    Returns
        None

    Raises
        None
    """

    tkeys = sdict.keys()
    tkeys.sort()
    swidth += 1
    mwidth += 1
    for akey in tkeys:
        default_mfest = ""
        active_mfests = []
        try:
            default_mname = get_default(akey)
        except StandardError:
            default_mname = ""
        for manifest_item in sdict[akey]:
            # manifest_items are a list of [ name, number of criteria ]

            # If the manifest is the default, note that in the status.
            # If the manifest has no criteria and is not the default,
            # do not print it.
            if manifest_item[0] == default_mname:
                default_mfest = manifest_item[0].ljust(mwidth) + DEFAULT
            elif manifest_item[1]:  # has_criteria
                active_mfests.append(manifest_item[0].ljust(mwidth))

        if len(active_mfests):
            print akey.ljust(swidth) + active_mfests[0]
            for idx in range(1, len(active_mfests)):
                print ''.ljust(swidth) + active_mfests[idx]
            print ''.ljust(swidth) + default_mfest
        else:
            print akey.ljust(swidth) + default_mfest
    print


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


def list_local_manifests(linst, name=None):
    """
    list the local manifests.  If name is not passed in then
    print all the local manifests.  Otherwise list the named
    service's manifest criteria.

    Args
        inst = smf.AISCF()
        name = service name

    Returns
        None

    Raises
        None
    """
    # list -m
    if not name:
        sdict, swidth, mwidth = get_manifest_or_profile_names(linst,
                                                     AIdb.MANIFESTS_TABLE)
        if sdict == {}:
            estr = _('Error: no manifests for local service(s)\n')
            sys.stderr.write(estr)
            sys.exit(1)

        # Pad swidth and mwidth with 1 extra space.  Status is at the end.
        swidth = max(swidth, len(_('Service Name'))) + 1
        fields = [[_('Service Name'), swidth]]
        mwidth = max(mwidth, len(_('Manifest'))) + 1
        fields.extend([[_('Manifest'), mwidth]])
        fields.extend([[_('Status'), len(_('Status'))]])

        do_header(fields)
        print_local_manifests(sdict, swidth, mwidth)
    # list -m -n <service>
    else:
        sdict, mwidth, cwidth = \
            get_mfest_or_profile_criteria(name, linst, AIdb.MANIFESTS_TABLE)
        if sdict == {}:
            estr = _('Error: no manifests for ' \
                     'local service named "%s".\n') % name
            sys.stderr.write(estr)
            sys.exit(1)

        # Pad swidth and stwidth with 1 extra space.  Criteria is at the end.
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
        sdict, swidth, mwidth = \
                get_manifest_or_profile_names(linst, AIdb.PROFILES_TABLE)
        if sdict == {}:
            estr = _('Error: no profiles for local service(s)\n')
            sys.stderr.write(estr)
            sys.exit(1)

        # Pad swidth and mwidth with 1 extra space.  Status is at the end.
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
        if sdict == {}:
            estr = _('No profiles for ' \
                     'local service named "%s".\n') % name
            sys.stderr.write(estr)
            sys.exit(1)

        # Pad swidth with 1 extra space.  Criteria is at the end.
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

    '''
    options = parse_options(cmd_options)

    try:
        inst = smf.AISCF(FMRI="system/install/server")
    except KeyError:
        raise SystemExit(_("Error: The system does not have the "
                           "system/install/server SMF service"))
    services = inst.services.keys()
    if not services:
        raise SystemExit(_('Error: no services on this server.\n'))

    if options.service and not options.service in services:
        raise SystemExit(_('Error: no local service named "%s".\n') % \
                           options.service)

    # list
    if not options.client and not options.manifest and not options.profile:
        list_local_services(inst, name=options.service)
    else:
        # list -c
        if options.client:
            list_local_clients(services, name=options.service)
        # list -m
        if options.manifest:
            if options.client:
                print
            list_local_manifests(inst, name=options.service)
        # list -p
        if options.profile:
            if options.client or options.manifest:
                print
            list_local_profiles(inst, name=options.service)


if __name__ == '__main__':

    # initialize gettext
    gettext.install("ai", "/usr/lib/locale")

    # If invoked from the shell directly, mostly for testing,
    # attempt to perform the action.
    do_list()

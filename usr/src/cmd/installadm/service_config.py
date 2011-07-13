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
#
'''
This file contains functions to manage the properties of installation
services.
'''
import ast
import ConfigParser
import errno
import logging
import os
import sys
import tempfile

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import CalledProcessError, Popen


# AI installation service property keys and values
PROP_BOOT_ARGS = 'boot_args'
PROP_BOOT_FILE = 'boot_file'
PROP_BOOT_MENU = 'boot_menu'
PROP_DEFAULT_MANIFEST = 'default-manifest'
PROP_GLOBAL_MENU = 'global_menu'
PROP_IMAGE_PATH = 'image_path'
PROP_ALIAS_OF = 'alias_of'
PROP_SERVICE_NAME = 'service_name'
PROP_STATUS = 'status'
PROP_VERSION = 'version'
PROP_TXT_RECORD = 'txt_record'
PROP_REVERIFY = 'reverify'
STATUS_OFF = 'off'
STATUS_ON = 'on'
CURRENT_VERSION = '2'

SERVICE = 'service'
CLIENTS = 'clients'
FILES = 'files'
BOOTARGS = 'bootargs'

AI_SERVICE_DIR_PATH = com.AI_SERVICE_DIR_PATH
CFGFILE = '.config'

AI_HTTPD_CONF = '/var/installadm/ai-webserver/ai-httpd.conf'
COMPATIBILITY_PORTS = ('/var/installadm/ai-webserver/'
                       'compatibility-configuration/ports.conf')
LISTEN_ADDRESSES = '/var/installadm/ai-webserver/listen-addresses.conf'
VOLATILE = '/system/volatile/'


class ServiceCfgError(Exception):
    '''
    Some sort of error occurred while interfacing with service
    configuration.
    '''
    pass


def is_service(service_name):
    '''Checks if a service has a config file

    Input:
        service_name - An service name
    Return:
        True  - if a config file exists under the subdir for
                the service_name
        False - otherwise

    '''
    logging.log(com.XDEBUG, '**** START service_config.is_service ****')
    cfgpath = _get_configfile_path(service_name)
    return os.path.exists(cfgpath)


def is_enabled(service_name):
    '''Checks if a service has status=on

    Input:
        service_name - An service name
    Return:
        True  - if status for the service is on
        False - otherwise

    '''
    logging.log(com.XDEBUG, '**** START service_config.is_enabled ****')
    enabled = False
    svc_dict = get_service_props(service_name)
    if PROP_STATUS not in svc_dict:
        enabled = False
    else:
        enabled = bool(svc_dict[PROP_STATUS] == STATUS_ON)
    logging.log(com.XDEBUG, '   enabled: %s', enabled)

    return enabled


def create_service_props(svcname, props):
    '''Create a property config file with the specified props.

    Input:
        svcname - service name
        props - A dictionary of properties to set when creating the
                installation service properties.

    '''
    logging.log(com.XDEBUG,
                "*** START service_config.create_service_props ***")
    logging.log(com.XDEBUG, "svcname=%s, props=%s", svcname, props)

    # verify that all required keys present
    verify_key_properties(svcname, props)

    _write_service_config(svcname, props)


def delete_service_props(service_name):
    '''Delete a service's property configuration file

    Input:
        service_name - service name whose props we wish to delete
    Raises:
        OSError if configuration file does not exist

    '''
    logging.log(com.XDEBUG,
                "*** START service_config.delete_service_props ***")

    logging.log(com.XDEBUG, "deleting props for service %s", service_name)
    cfgpath = _get_configfile_path(service_name)
    os.remove(cfgpath)


def get_service_props(service_name):
    ''' Get the properties for an installation service

    Generate a dictionary of the service properties as available for the
    specified service_name.

    Input:
        service_name - An AI service name or None if supplying configfile

    Return:
        A dictionary of relevant properties for the specified service_name.
        Returns None, if service config file does not exist

    '''
    logging.log(com.XDEBUG, '**** START service_config.get_service_props ****')
    
    cfgp = _read_config_file(service_name)
    if cfgp is None:
        return None
    
    props = dict()
    if cfgp.has_section(SERVICE):
        section_dict = dict(cfgp.items(SERVICE))
        props.update(section_dict)
    
    for prop in props:
        logging.log(com.XDEBUG, '   property: %s=%s', prop, props[prop])
    
    return props


def set_service_props(service_name, props):
    ''' Set the property values for a specified service name.

    Input:
        service_name - An AI service name
        props - A dictionary of properties to update for the specified
                   service_name.

    '''
    logging.log(com.XDEBUG, '**** START service_config.set_service_props '
                'service_name=%s ****', service_name)
    _write_service_config(service_name, props)


def get_all_service_names():
    '''
    Generate a list of service names

    Input:
        None
    Return:
        A list of service names or empty list if no services

    '''
    logging.log(com.XDEBUG,
                '**** START service_config.get_all_service_names ****')
    names = list()
    dirlist = os.listdir(AI_SERVICE_DIR_PATH)
    for subdir in dirlist:
        fullpath = os.path.join(AI_SERVICE_DIR_PATH, subdir)
        # if not a true directory, skip
        if not os.path.isdir(fullpath) or os.path.islink(fullpath):
            continue
        cfgfile = os.path.join(AI_SERVICE_DIR_PATH, subdir, CFGFILE)
        if os.path.isfile(cfgfile):
            names.append(subdir)
    logging.log(com.XDEBUG, 'services are: %s', names)
    return names


def get_all_service_props():
    '''
    Generate a dictionary of services where each service name entry
    in the dictionary contains a dictionary of properties.

    Input:
        None
    Return:
        A dictionary of service names each of which contains a
        dictionary of associated properties.

    '''
    logging.log(com.XDEBUG,
                '**** START service_config.get_all_service_props ****')

    all_properties = dict()
    all_svc_names = get_all_service_names()
    for service in all_svc_names:
        service_props = get_service_props(service)
        all_properties[service] = service_props

    logging.log(com.XDEBUG, 'all service properties are: %s', all_properties)
    return all_properties


def verify_key_properties(svcname, props):
    '''Verify key properties are present for a service

    Input:
        svcname - service name
        props - A dictionary of service properties to check
    Raises:
        ServiceCfgError if not all required service properties present

    '''
    logging.log(com.XDEBUG,
                "*** START service_config.verify_key_properties ***")
    logging.log(com.XDEBUG, "svcname %s, props=%s", svcname, props)

    # verify that all required keys present
    missing = set()
    if PROP_SERVICE_NAME not in props.keys():
        missing.add(PROP_SERVICE_NAME)
    else:
        prop_name = props[PROP_SERVICE_NAME]
        if prop_name != svcname:
            raise ServiceCfgError(cw(_("\nError: service name '%s' does not "
                                       "match %s property '%s'\n") % (svcname,
                                       PROP_SERVICE_NAME, prop_name)))

    if PROP_STATUS not in props.keys():
        missing.add(PROP_STATUS)
    if PROP_TXT_RECORD not in props.keys():
        missing.add(PROP_TXT_RECORD)
    else:
        port = props[PROP_TXT_RECORD].partition(':')[1]
        if not port:
            raise ServiceCfgError(cw(_("\nError: Unable to determine service "
                                       "directory for service %s\n") %
                                       svcname))
    if PROP_IMAGE_PATH not in props.keys():
        if PROP_ALIAS_OF not in props.keys():
            missing.add(PROP_IMAGE_PATH + _(' or ') + PROP_ALIAS_OF)
    if missing:
        raise ServiceCfgError(cw(_('\nError: installation service key '
                                   'properties missing for service %s: %s\n') %
                                   (svcname, ', '.join(missing))))


def get_aliased_services(service_name, recurse=False):
    '''
    Get list of services aliased to service_name
    Input: service name
           recurse - True if recursion desired, to get aliases of aliases...
                     False if only aliases of specified service name desired
    Returns: list of aliased service names or empty list
             if there are no aliases

    '''
    logging.log(com.XDEBUG, "get_aliased_services: %s, recurse %s",
                service_name, recurse)
    aliases = list()
    all_svc_data = get_all_service_props()
    for svc_data in all_svc_data.values():
        if (PROP_ALIAS_OF in svc_data and
            svc_data[PROP_ALIAS_OF] == service_name):
            aliases.append(svc_data[PROP_SERVICE_NAME])
    if recurse:
        taliases = list()
        for alias in aliases:
            taliases.extend(get_aliased_services(alias, recurse))
        aliases.extend(taliases)

    logging.log(com.XDEBUG, "aliases=%s" % aliases)
    return aliases


def add_client_info(service_name, clientid, clientdata):
    '''add client info to the service configuration file

    Input:
        service_name - service name
        clientid - clientid of client (01aabbccaabbcc)
        clientdata - dict of client data (see find_client)

    Raises:
        ServiceCfgError if service missing .config file

    '''
    logging.log(com.XDEBUG, '**** START service_config.add_client_info ****')
    logging.log(com.XDEBUG, '  service=%s, clientid=%s, clientdata=%s',
                service_name, clientid, clientdata)
    cfg = _read_config_file(service_name)
    if cfg is None:
        raise ServiceCfgError(_("\nMissing configuration file for service: "
                                "%s\n" % service_name))

    if CLIENTS not in cfg.sections():
        cfg.add_section(CLIENTS)

    # add the client
    cfg.set(CLIENTS, clientid, clientdata)

    _write_config_file(service_name, cfg)


def get_clients(service_name):
    '''
    Get info on all clients of a service
    Input: service name
    Returns: dictionary of clients, key is clientid (01aabbccaabbcc) and
             value is dict of client data (see find_client)
    Raises:
        ServiceCfgError if service missing .config file

    '''
    logging.log(com.XDEBUG, "**** START service_config.get_clients: %s ****",
                service_name)
    cfg = _read_config_file(service_name)
    if cfg is None:
        raise ServiceCfgError(_("\nMissing configuration file for service: "
                                "%s\n" % service_name))

    clients = dict()
    if CLIENTS not in cfg.sections():
        return clients
    rawclients = dict(cfg.items(CLIENTS))
    for client in rawclients:
        data = rawclients[client]
        value = ast.literal_eval(data)
        clients[client.upper()] = value
    logging.log(com.XDEBUG, 'clients are %s', clients)
    return clients


def find_client(client_id):
    '''
    Get info on a particular client
    Input: clientid ('01aabbccaabbcc')
    Returns: tuple consisting of service_name of client and
             dict of client data, both None if client does not exist.
             Client data can include:
                 FILES: [list of files to remove when deleting client]
                 BOOTARGS: comma separated string of client specific boot
                           args <property>=<value>,
    Raises:
        ServiceCfgError if service missing .config file

    '''
    logging.log(com.XDEBUG, "**** START service_config.find_client: %s ****",
                client_id)
    service = None
    files = None
    for svc in get_all_service_names():
        cfg = _read_config_file(svc)
        if cfg is None:
            raise ServiceCfgError(_("\nMissing configuration file for "
                                    "service: %s\n" % svc))
        if CLIENTS not in cfg.sections():
            continue
        clients = dict(cfg.items(CLIENTS))
        # cfgparser changes client_id to lower
        if client_id.lower() in clients:
            data = clients[client_id.lower()]
            files = ast.literal_eval(data)
            service = svc
            break
    logging.log(com.XDEBUG, 'service is %s, files are %s', service, files)
    return (service, files)


def is_client(client_id):
    '''
    Find out if client exists
    Input: clientid ('01aabbccaabbcc')
    Returns: True if client exists
             False otherwise
    Raises:
        ServiceCfgError if service missing .config file

    '''
    logging.log(com.XDEBUG, "**** START service_config.is_client: %s ****",
                client_id)
    exists = False
    all_svc_names = get_all_service_names()
    for svc in all_svc_names:
        cfg = _read_config_file(svc)
        if cfg is None:
            raise ServiceCfgError(_("\nMissing configuration file for "
                                    "service: %s\n" % svc))
        if CLIENTS not in cfg.sections():
            continue
        clients = dict(cfg.items(CLIENTS))
        # cfgparser changes client_id to lower
        if client_id.lower() in clients:
            exists = True
    logging.log(com.XDEBUG, 'client exists: %s', exists)
    return exists


def remove_client_from_config(service_name, client_id):
    '''
    Remove client entry from .config file
    Input: service name
          client_id of entry to remove
    Raises:
        ServiceCfgError if service missing .config file

    '''
    logging.log(com.XDEBUG,
                "**** START service_config.remove_client_from_config: %s "
                "%s ****", service_name, client_id)
    cfg = _read_config_file(service_name)
    if cfg is None:
        raise ServiceCfgError(_("\nMissing configuration file for "
                                "service: %s\n" % service_name))
    if CLIENTS not in cfg.sections():
        return
    clients = cfg.options(CLIENTS)
    if client_id.lower() in clients:
        cfg.remove_option(CLIENTS, client_id.lower())
    # if last client deleted, remove section
    if not cfg.options(CLIENTS):
        cfg.remove_section(CLIENTS)
    _write_config_file(service_name, cfg)


def get_service_port(svcname):
    ''' Get the port for a service (compatibility with old services)

    Input:
        svcname - Name of service
    Return:
        port number
    Raises:
        ServiceCfgError if service doesn't exist or if there is a
        problem with the txt_record.
    
    '''
    # get the port from the service's txt_record
    try:
        txt_rec = get_service_props(svcname)[PROP_TXT_RECORD]
    except KeyError as err:
        raise ServiceCfgError(err)
    
    # txt_record is of the form "aiwebserver=example:46503" so split
    # on ":" and take the trailing portion for the port number
    port = txt_rec.rsplit(':')[-1]
    
    return port


def enable_install_service(svcname):
    ''' Enable an install service

    Enable the specified install service and update the service's
    installation properties. This function requires the service properties
    to already exist.

    Input:
        svcname - Service name
    Return:
        none
    Raises:
        ServiceCfgError if service properties are missing or install
        service properties do not exist.

    '''
    logging.log(com.XDEBUG,
                '**** START service_config.enable_install_service ****')

    # Get the install properties for this service. The properties
    # should have already been created, even if the service is new.
    props = get_service_props(svcname)
    if not props:
        raise ServiceCfgError(_('\nError: installation service properties'
                                ' do not exist for %s.\n') % (svcname))

    # Confirm required keys are available and exit if not
    verify_key_properties(svcname, props)

    # Update status in service's properties
    props[PROP_STATUS] = STATUS_ON
    set_service_props(svcname, props)

    # ensure SMF install service is online
    aismf.service_enable_attempt()

    # Actually register service
    cmd = [com.SETUP_SERVICE_SCRIPT, com.SERVICE_REGISTER, svcname,
           props[PROP_TXT_RECORD]]
    try:
        logging.log(com.XDEBUG, "Executing: %s", cmd)
        Popen.check_call(cmd)
    except CalledProcessError:
        # Revert status in service's properties
        props = {PROP_STATUS: STATUS_OFF}
        set_service_props(svcname, props)
        raise ServiceCfgError()


def check_for_enabled_services():
    '''
    Check to see if any of the install services are enabled.
    If not, the installadm SMF service should be disabled and
    placed in maintenance.

    Inputs:
        none
    Returns:
        none

    '''
    logging.log(com.XDEBUG, '**** START '
                  'service_config.check_for_enabled_services ****')

    # Get all installation properties.
    all_svc_props = get_all_service_props()

    if not all_svc_props:
        # No install service properties were found. Move the SMF
        # service to maintenance if not already there.
        service_state = aismf.get_state()
        if service_state != aismf.SCF_STATE_STRING_MAINT:
            aismf.disable_instance()
            aismf.maintain_instance()
        return

    # If any install services are enabled (on), don't change the state
    # of the installadm SMF service.
    for service in all_svc_props:
        if all_svc_props[service][PROP_STATUS] == STATUS_ON:
            logging.log(com.XDEBUG, "At least one service currently "
                          "enabled, not going to maintenance.")
            return

    service_state = aismf.get_state()
    logging.log(com.XDEBUG, "Current state of smf service is %s",
                service_state)
    if service_state != aismf.SCF_STATE_STRING_MAINT:
        logging.log(com.XDEBUG, "Disabling installadm SMF service")
        aismf.disable_instance()
        logging.log(com.XDEBUG,
                    "Placing installadm SMF service in maintenance")
        aismf.maintain_instance()


def create_work_file():
    '''
    Create the work file that will be used to create the various Apache
    configuration files. The returned object is a tempfile.TemporaryFile.
    TemporaryFiles are automatically removed from the filesystem.

    Input:
        file_path - original file path
    Return: temporary file path

    '''
    intro = ('#\n'
             '# Do not edit by hand.\n'
             '# This file is created by the svc:/system/install/server '
             'method script\n'
             '# and is Included in the AI webserver configuration file.\n'
             '#\n')
    work_file = tempfile.TemporaryFile(dir=VOLATILE)
    work_file.write(intro)
    return work_file


def create_compatibility_file(smf_port):
    '''
    Create the compatibility file with the additional ports needed
    for older services to ensure that the apache webserver services
    old clients. The AI_HTTPD_CONF file contains a line that includes
    the COMPATIBILITY_PORTS file which this function creates.

    Input:
        smf_port - webserver port from smf
    Return: 
        0 - New COMPATIBILITY_PORTS file has been put into place.
        1 - Existing COMPATIBILITY_PORTS file was not touched.
    '''
    valid_networks = com.get_valid_networks()
    ports = set()
    for service in get_all_service_names():
        service_props = get_service_props(service)
        if service_props.get(PROP_STATUS) == STATUS_ON:
            port = get_service_port(service)
            ports.add(port)
    ports.discard(smf_port)
    work_file = create_work_file()
    try:
        # add Listen lines to file
        for port in ports:
            for ip in valid_networks:
                listen = 'Listen %s:%s\n' % (ip, port)
                work_file.write(listen)

        work_file.seek(0)
        work_data = work_file.read()
    finally:
        # Work file, as a tempfile.TemporaryFile object,
        # is automatically deleted upon close
        work_file.close()
    
    if os.path.exists(COMPATIBILITY_PORTS):
        with open(COMPATIBILITY_PORTS, 'r') as compat:
            compat_data = compat.read()
    else:
        compat_data = None

    if work_data == compat_data:
        # use existing configuration file
        return 1

    # Truncate when re-writing the data
    with open(COMPATIBILITY_PORTS, "w") as compat_file:
        compat_file.write(work_data)

    return 0


def create_main_ports_file(smf_port):
    '''
    Create the listen address:ports file for the apache webserver services
    so that other services do not step on the port being used.  The
    AI_HTTPD_CONF file contains a line that includes the LISTEN_ADDRESSES file
    which this function creates.

    Input:
        smf_port - webserver port from smf
    Return:
        0 - New LISTEN_ADDRESSES file has been put into place.
        1 - Existing LISTEN_ADDRESSES file was not touched.
    '''
    try:
        work_file = create_work_file()

        valid_networks = com.get_valid_networks()
        # add Listen lines to file
        for ip in valid_networks:
            listen = 'Listen %s:%s\n' % (ip, smf_port)
            work_file.write(listen)
        
        work_file.seek(0)
        work_data = work_file.read()
    finally:
        # Work file, as a tempfile.TemporaryFile object,
        # is automatically deleted upon close
        work_file.close()
    
    if os.path.exists(LISTEN_ADDRESSES):
        with open(LISTEN_ADDRESSES, 'r') as listen:
            listen_data = listen.read()
    else:
        listen_data = None

    if work_data == listen_data:
        # use existing configuration file
        return 1
    
    # Truncate existing file, write new data
    with open(LISTEN_ADDRESSES, "w") as listen_file:
        listen_file.write(work_data)

    return 0


def _get_configfile_path(service_name):
    '''get the path to a service's config file'''
    cfgpath = os.path.join(AI_SERVICE_DIR_PATH, service_name, CFGFILE)
    return cfgpath


def _read_config_file(service_name):
    ''' Get the current ConfigParser object for an installation service

    Input:
        service_name - An AI service name
    Return:
        A ConfigParser object with the current config

    '''
    logging.log(com.XDEBUG, '**** START service_config._read_config_file ****')

    cfg = ConfigParser.ConfigParser()
    cfgpath = _get_configfile_path(service_name)
    if not os.path.exists(cfgpath):
        return None
    cfg.readfp(open(cfgpath))
    return cfg


def _write_config_file(service_name, cfg):
    ''' Write out the passed in cfg for an installation service

    Input:
        service_name - An AI service name or None if supplying configfile
        cfg - A ConfigParser object with the current config
    Raises:
        OSError if problem creating service dir

    '''
    logging.log(com.XDEBUG,
                '**** START service_config._write_config_file ****')

    svcdir = os.path.join(AI_SERVICE_DIR_PATH, service_name)
    try:
        os.makedirs(svcdir)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise

    cfgpath = os.path.join(svcdir, CFGFILE)
    logging.log(com.XDEBUG, 'writing config file:  %s', cfgpath)
    with open(cfgpath, 'w') as cfgfile:
        cfg.write(cfgfile)


def _write_service_config(service_name, props):
    '''Writes out the service related info to the .config file
       for service_name, leaving other sections intact.

    Input:
        service_name - service name
        props - dictionary of props to write out to config file
    Raises: OSError if unable to create service directory

    '''
    logging.log(com.XDEBUG,
                '**** START service_config._write_service_config ****')
    newfile = False

    # read in existing config
    cfg = _read_config_file(service_name)
    if cfg is None:
        # No exisiting config file, start a new one
        newfile = True
        cfg = ConfigParser.ConfigParser()
    current_sections = cfg.sections()
    if SERVICE not in current_sections and props is not None:
        cfg.add_section(SERVICE)

    # update props in SERVICE section
    for prop in props:
        cfg.set(SERVICE, prop, str(props[prop]))

    # Add version if new file
    if newfile and cfg.has_section(SERVICE):
        cfg.set(SERVICE, PROP_VERSION, CURRENT_VERSION)
    
    if logging.root.isEnabledFor(com.XDEBUG):
        for section in cfg.sections():
            logging.log(com.XDEBUG, '%s %s items are: %s', service_name,
                        section, cfg.items(section))

    _write_config_file(service_name, cfg)


if __name__ == '__main__':
    if sys.argv[1] == "create-compatibility-file":
        sys.exit(create_compatibility_file(sys.argv[2]))
    elif sys.argv[1] == 'create-main-ports-file':
        sys.exit(create_main_ports_file(sys.argv[2]))
    elif sys.argv[1] == "listprop":
        print str(get_service_props(sys.argv[2])[sys.argv[3]])
    else:
        sys.exit("Invalid arguments")

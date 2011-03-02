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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
This file contains a thin wrapper around osol_install.libaiscf and
any supporting functions used to manage the Automated Installer SMF 
service. The use of osol_install.libaiscf is temporary as the
ISIM project will be modifying the functions in this file to interface 
with RAD instead. 

'''
import logging
import sys
import time

import osol_install.libaiscf as libaiscf
from osol_install.auto_install.installadm_common import _, \
    SERVICE_REGISTER, SETUP_SERVICE_SCRIPT 
from solaris_install import CalledProcessError, Popen

AI_SVC_FMRI = 'system/install/server'

MAX_WAIT_TIME = 45 # Max wait time in seconds for service to transition states

# AI service property group keys and values
PROP_BOOT_FILE = 'boot_file'
PROP_IMAGE_PATH = 'image_path'
PROP_SERVICE_NAME = 'service_name'
PROP_STATUS = 'status'
PROP_TXT_RECORD = 'txt_record'
STATUS_OFF = 'off'
STATUS_ON = 'on'

# From /usr/include/libscf.h
SCF_STATE_STRING_MAINT = 'maintenance'
SCF_STATE_STRING_OFFLINE = 'offline'
SCF_STATE_STRING_DISABLED = 'disabled'
SCF_STATE_STRING_ONLINE = 'online'


class InstalladmAISmfServicesError(Exception):
    '''
    Some sort of error occurred while interfacing with an SMF service.
    The exact cause of the error should have been logged. So, this
    just indicates that something is wrong.
    '''
    pass


def is_pg(pg_name):
    '''Checks if a property group is configured

    Input:
        pg_name - An AI service property group name
    Return:
        True  - if the specified pg_name exists
        False - otherwise

    '''
    logging.debug('**** START ai_smf_service.is_pg ****')

    if pg_name in libaiscf.AISCF(FMRI=AI_SVC_FMRI).services:
        return True
    else:
        return False


def get_pg_props(pg_name):
    ''' Get property group properties

    Generate a dictionary of the following properties as available for the
    specified pg_name:
        boot_file : astring
        image_path : astring
        service_name : astring
        status : astring
        txt_record : astring

    Input:
        pg_name - An AI service property group name
    Return:
        A dictionary of relevant properties for the specified pg_name.

    '''
    logging.debug('**** START ai_smf_service.get_pg_props ****')

    props = {}

    smf_inst = libaiscf.AISCF(FMRI=AI_SVC_FMRI)
    svc_obj = libaiscf.AIservice(smf_inst, pg_name)
    for prop in svc_obj.keys():
        logging.debug('   property: ' + prop + ' value: ' + svc_obj[prop])
        props[prop] = svc_obj[prop]

        if props[prop].upper() == 'FALSE':
            props[prop] = False
        elif props[prop].upper() == 'TRUE':
            props[prop] = True

    return props


def create_pg(pg_name, props=None):
    '''Create the property group, setting the properties, if provided.
       Note: libaiscf.new_service() prepends the "AI" to the pg name.

    Input:
        pg_name - An AI service name 
        props - (optional) A dictionary of properties to set when 
                creating the pg.

    '''
    logging.debug("*** START ai_smf_service.create_pg ***")
    inst = libaiscf.AISCF(FMRI=AI_SVC_FMRI)
    inst.new_service(pg_name)
    
    if props:
        set_pg_props(pg_name, props)


def set_pg_props(pg_name, props):
    '''
    Set the property values, as specified in dictionary, props, for a
    specified property group.

    Input:
        pg_name - An AI service property group name
        props - A dictionary of properties to set for the specified
                pg_name.

    '''
    logging.debug('**** START ai_smf_service.set_pg_props ****')

    for prop in props:
        logging.debug('\tsetting property: ' + prop + ' value: ' +
                      str(props[prop]))

        # Work around the fact that AIServices currently only supports
        # string objects.
        if props[prop] == False:
            libaiscf.AIservice(libaiscf.AISCF(FMRI=AI_SVC_FMRI),
                               pg_name)[prop] = 'FALSE'
        elif props[prop] == True:
            libaiscf.AIservice(libaiscf.AISCF(FMRI=AI_SVC_FMRI),
                               pg_name)[prop] = 'TRUE'
        else:
            libaiscf.AIservice(libaiscf.AISCF(FMRI=AI_SVC_FMRI),
                               pg_name)[prop] = props[prop]


def get_all_pg_props():
    '''
    Generate a dictionary of services where each service entry in the
    dictionary contains a dictionary of properties.

    Input:
        None
    Return:
        A dictionary of property groups each of which contains a
        dictionary of relevant properties.

    '''
    logging.debug('**** START ai_smf_service.get_all_pg_props ****')

    prop_groups = {}
    for prop_group in libaiscf.AISCF(FMRI=AI_SVC_FMRI).services:
        logging.debug('service: AI' + prop_group)
        prop_groups[prop_group] = get_pg_props(prop_group)

    return prop_groups


def get_state():
    ''' Return the state of the Automated Installer SMF service.

    This function is roughly analogous to smf_get_state(3SCF)

    Input:
        None
    Return:
        state - e.g. 'disabled', 'maintenance'... | None if not found
    Raises:
        Whatever exceptions AISCF encounters

    '''
    logging.debug('**** START ai_smf_service.get_state ****')

    try:
        return libaiscf.AISCF(FMRI=AI_SVC_FMRI).state
    except SystemError:
        return None


def maintain_instance():
    ''' Move the Automated Installer SMF service to the maintenance state.

    This function is roughly analogous to smf_maintain_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        InstalladmAISmfServicesError if service fails to transition to
        'MAINTENANCE' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.debug('**** START ai_smf_service.maintain_instance ****')

    libaiscf.AISCF(FMRI=AI_SVC_FMRI).state = 'MAINTENANCE'

    # Wait a reasonable amount of time to confirm state change.
    wait_cnt = 0
    while libaiscf.AISCF(FMRI=AI_SVC_FMRI).state.upper() != 'MAINTENANCE':
        if wait_cnt >= MAX_WAIT_TIME:
            logging.debug("Wait time exceeded on attempt to move "
                          "installadm SMF service to maintenance.")
            raise InstalladmAISmfServicesError(
                _('Error: Failed to place installadm SMF service '
                  'in maintenance.'))
        else:
            time.sleep(1)
            wait_cnt += 1

    logging.debug("Time to move installadm SMF service to maintenance is "
                  "%i seconds", wait_cnt)
    sys.stderr.write("The installadm SMF service is no longer online because "
                     "the last install service has been disabled or "
                     "deleted.\n")


def disable_instance():
    ''' Move the Automated Installer SMF service to the disabled state.

    This function is roughly analogous to smf_disable_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        InstalladmAISmfServicesError if service fails to transition to
        'DISABLED' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.debug('**** START ai_smf_service.disable_instance ****')
    sys.stderr.write("The installadm SMF service is being taken offline.\n")

    libaiscf.AISCF(FMRI=AI_SVC_FMRI).state = 'DISABLE'

    # Wait a reasonable amount of time to confirm state change.
    wait_cnt = 0
    while libaiscf.AISCF(FMRI=AI_SVC_FMRI).state.upper() != 'DISABLED':
        if wait_cnt >= MAX_WAIT_TIME:
            logging.debug("Wait time exceeded on attempt to move "
                          "installadm SMF service to disabled.")
            raise InstalladmAISmfServicesError(
                _('Error: Failed to disable installadm SMF service.'))
        else:
            time.sleep(1)
            wait_cnt += 1

    logging.debug("Time to move installadm SMF service to disabled is "
                  "%i seconds", wait_cnt)


def enable_instance():
    ''' Enable the Automated Installer SMF service.

    This function is roughly analogous to smf_enable_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        InstalladmAISmfServicesError if service fails to transition to
        'ONLINE' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.debug('**** START ai_smf_service.enable_instance ****')

    libaiscf.AISCF(FMRI=AI_SVC_FMRI).state = 'ENABLE'

    # Wait a reasonable amount of time to confirm state change.
    wait_cnt = 0
    while libaiscf.AISCF(FMRI=AI_SVC_FMRI).state.upper() != 'ONLINE':
        if wait_cnt >= MAX_WAIT_TIME:
            logging.debug("Wait time exceeded on attempt to enable "
                          "installadm SMF service.")
            raise InstalladmAISmfServicesError(
                _('Error: Failed to enable installadm SMF service.'))
        else:
            time.sleep(1)
            wait_cnt += 1

    logging.debug("Time to enable installadm SMF service is %i seconds", 
                  wait_cnt)


def restore_instance():
    ''' Restore the Automated Installer SMF service.

    This function is roughly analogous to smf_restore_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        InstalladmAISmfServicesError if service fails to transition to
        'DISABLED' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.debug('**** START ai_smf_service.restore_instance ****')

    libaiscf.AISCF(FMRI=AI_SVC_FMRI).state = 'RESTORE'

    # Wait a reasonable amount of time to confirm state change.
    wait_cnt = 0
    while libaiscf.AISCF(FMRI=AI_SVC_FMRI).state.upper() != 'DISABLED':
        if wait_cnt >= MAX_WAIT_TIME:
            logging.debug("Wait time exceeded on attempt to restore "
                          "installadm SMF service.")
            raise InstalladmAISmfServicesError(
                _('Error: Failed to restore installadm SMF service.'))
        else:
            time.sleep(1)
            wait_cnt += 1

    logging.debug("Time to restore installadm SMF service is %i seconds", 
                  wait_cnt)


def service_enable_attempt():
    ''' Attempt to enable the Automated Installer SMF service.

    Algorithm:
        If the service is online, everything is OK. return.
        If the service is offline, SMF is settling. Return
            or we get caught in recursion.
        If the service is disabled, try to enable it.
        If the service is in maintenance, try to clear it and
            then enable it.
    Input:
        None
    Return:
        None
    Raises:
        InstalladmAISmfServicesError if current state of service is
        unexpected.

    '''
    logging.debug('**** START ai_smf_service.service_enable_attempt ****')

    orig_state = get_state()
    if not orig_state:
        enable_instance()
    elif orig_state == SCF_STATE_STRING_ONLINE:
        # Instance is online and running - do nothing.
        logging.debug("Current smf service state already online")
        return
    elif orig_state == SCF_STATE_STRING_OFFLINE:
        logging.debug("Current smf service state offline")
        return
    elif orig_state == SCF_STATE_STRING_DISABLED:
        logging.debug("Current smf service state disabled, enabling "
                       "instance")
        enable_instance()
    elif orig_state == SCF_STATE_STRING_MAINT:
        logging.debug("Current smf service state is maintenance, "
                       "restoring instance")
        restore_instance()
 
        # Instance is now disabled - try to enable it.
        logging.debug("Current smf service state is disabled, "
                       "enabling instance")
        enable_instance()
    else:
        raise InstalladmAISmfServicesError(
            _('Error: unexpected state for install server: %s') % orig_state)


def enable_install_service(svcname):
    ''' Enable an install service

    Enable the specified install service and update the service's
    property group. This function requires the SMF service property
    to already exist.

    Input:
        svcname - Service name
    Return:
        none
    Raises:
        InstalladmAISmfServicesError if service properties are
        missing or property group does not exist.

    '''
    logging.debug('**** START ai_smf_service.enable_install_service ****')

    # This service should have already been set, even it is new.
    if not is_pg(svcname):
        raise InstalladmAISmfServicesError(
            _('Error: SMF service property group %s does not exist.\n') %
            (svcname))

    # Get the SMF property group data for this service
    pg_data = get_pg_props(svcname)

    # Confirm required keys are available and exit if not
    missing = []
    if not (PROP_TXT_RECORD in pg_data.keys()):
        missing.append(PROP_TXT_RECORD)
    if not (PROP_IMAGE_PATH in pg_data.keys()):
        missing.append(PROP_IMAGE_PATH)
    if not (PROP_STATUS in pg_data.keys()):
        missing.append(PROP_STATUS)
    if missing:
        raise InstalladmAISmfServicesError(
            _('Error: SMF service key properties missing: %s\n' % 
              ', '.join(missing)))

    # Update status in service's property group
    props = {PROP_STATUS: STATUS_ON}
    set_pg_props(svcname, props)

    # ensure SMF install service is online 
    service_enable_attempt()

    # Actually register service
    cmd = [SETUP_SERVICE_SCRIPT, SERVICE_REGISTER, svcname,
           pg_data[PROP_TXT_RECORD], pg_data[PROP_IMAGE_PATH]]
    logging.debug("enable_install_service: register command is %s", cmd)
    try:
        Popen.check_call(cmd)
    except CalledProcessError:
        # Revert status in service's property group
        props = {PROP_STATUS: STATUS_OFF}
        set_pg_props(svcname, props)
        raise InstalladmAISmfServicesError()


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
    logging.debug('**** START ' 
                  'ai_smf_service.check_for_enabled_services ****')

    # Get all propert groups.
    all_pg_props = get_all_pg_props()

    if not all_pg_props:
        # No property groups for install services were found. Move to
        # maintenance if not already there.
        service_state = get_state()
        if service_state != SCF_STATE_STRING_MAINT:
            disable_instance()
            maintain_instance()
        return

    # If any install services are enabled (on), don't change the state
    # of the installadm SMF service.
    for pg in all_pg_props:
        if all_pg_props[pg][PROP_STATUS] == STATUS_ON:
            logging.debug("At least one service currently "
                          "enabled, not going to maintenance.")
            return

    service_state = get_state()
    logging.debug("Current state of smf service is %s", service_state)
    if service_state != SCF_STATE_STRING_MAINT:
        logging.debug("Disabling installadm SMF service") 
        disable_instance()
        logging.debug("Placing installadm SMF service in maintenance") 
        maintain_instance()

    return


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
This file contains a thin wrapper around osol_install.libaiscf and
any supporting functions used to manage the Automated Installer SMF 
service. The use of osol_install.libaiscf is temporary as the
ISIM project will be modifying the functions in this file to interface 
with RAD instead. 
'''
import logging
import os
import sys
import time

import osol_install.auto_install.installadm_common as com
import osol_install.libaiscf as libaiscf

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen, CalledProcessError, SetUIDasEUID

_ = com._

MAX_WAIT_TIME = 45 # Max wait time in seconds for service to transition states

# libaiscf does not support the 'svc:/' prefix
AI_SVC_FMRI = 'system/install/server'
# From /usr/include/libscf.h
SCF_STATE_STRING_MAINT = 'maintenance'
SCF_STATE_STRING_OFFLINE = 'offline'
SCF_STATE_STRING_DISABLED = 'disabled'
SCF_STATE_STRING_ONLINE = 'online'

# For _start_tftpd
TFTP_FMRI = 'svc:/network/tftp/udp6'
INET_START = '"/usr/sbin/in.tftpd -s %s"'
INET_START_PROP = 'inetd_start/exec'
SVCCFG = '/usr/sbin/svccfg'
SVCPROP = '/usr/bin/svcprop'
SVCADM = '/usr/sbin/svcadm'


class ServicesError(Exception):
    '''
    Some sort of error occurred while interfacing with an SMF service.
    The exact cause of the error should have been logged. So, this
    just indicates that something is wrong.
    '''
    pass


def get_smf_instance():
    ''' Get the instance for the installadm SMF service
    Args: None
    Return: smf instance
    Raises:
        ServicesError if the installadm SMF service
        doesn't exist 

    '''
    logging.log(com.XDEBUG, '**** START ai_smf_service.get_smf_instance ****')
    try:
        smf_instance = libaiscf.AISCF(FMRI=AI_SVC_FMRI)
    except KeyError:
        raise ServicesError(_("The system does not have the "
                              "system/install/server SMF service.\n"))
    return smf_instance


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
    logging.log(com.XDEBUG, '**** START ai_smf_service.get_state ****')

    try:
        return libaiscf.AISCF(FMRI=AI_SVC_FMRI).state
    except SystemError:
        return None


def _set_instance(state, wait_for):
    '''Set the install/server service to a given
    state, and wait for it to finish transitioning.
    
    state - desired state, e.g. 'MAINTENANCE' or 'RESTORE'
    wait_for - Function will block until the SMF state of the install/server
        instance is one of the values passed in this list,
        e.g. ['DISABLED', 'OFFLINE']. List items should be upper case.
    
    Raises ServicesError
        if the transition doesn't complete before MAX_WAIT_TIME seconds pass.
    
    '''
    libaiscf.AISCF(FMRI=AI_SVC_FMRI).state = state.upper()

    # Wait a reasonable amount of time to confirm state change.
    wait_cnt = 0
    while libaiscf.AISCF(FMRI=AI_SVC_FMRI).state.upper() not in wait_for:
        if wait_cnt >= MAX_WAIT_TIME:
            logging.debug("Wait time exceeded on attempt to move "
                          "installadm SMF service to %s.", state.lower())

            raise ServicesError(cw(_("Error: Failed to place %(svc)s in "
                                     "%(state)s. See the output of 'svcs "
                                     "-xv %(svc)s' for more information.") %
                                    {'svc': AI_SVC_FMRI,
                                    'state': state.lower()}))
        else:
            time.sleep(1)
            wait_cnt += 1
    logging.log(com.XDEBUG, "Time to set installadm SMF service to '%s' is %i"
                " seconds", state, wait_cnt)


def maintain_instance():
    ''' Move the Automated Installer SMF service to the maintenance state.

    This function is roughly analogous to smf_maintain_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        ServicesError if service fails to transition to
        'MAINTENANCE' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.log(com.XDEBUG, '**** START ai_smf_service.maintain_instance ****')
    
    _set_instance('MAINTENANCE', ('MAINTENANCE',))
    
    sys.stderr.write(cw(_("The installadm SMF service is no longer online "
                          "because the last install service has been disabled "
                          "or deleted.\n")))


def disable_instance():
    ''' Move the Automated Installer SMF service to the disabled state.

    This function is roughly analogous to smf_disable_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        ServicesError if service fails to transition to
        'DISABLED' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.log(com.XDEBUG, '**** START ai_smf_service.disable_instance ****')
    sys.stderr.write("The installadm SMF service is being taken offline.\n")
    
    _set_instance('DISABLE', ('DISABLED',))


def _start_tftpd():
    '''Start the tftp/udp6 service, a dependency of installadm. If necessary,
    adjust the inetd_start/exec property to run tftp out of /etc/netboot.
    
    Raises ServicesError if tftp/udp6 is configured to use a different
        directory, and that directory exists and has files.
    
    '''
    getprop = [SVCPROP, '-p', INET_START_PROP, TFTP_FMRI]
    svcprop_popen = Popen.check_call(getprop, stdout=Popen.STORE,
                                     stderr=Popen.STORE)
    inet_start = svcprop_popen.stdout.strip().split()
    if inet_start[-1] != com.BOOT_DIR:
        if (os.path.exists(inet_start[-1]) and os.path.isdir(inet_start[-1])
            and os.listdir(inet_start[-1])):
            raise ServicesError(cw(_("The %(svc)s service has been configured "
                                     "to use the %(dir)s directory; "
                                     "installadm is incompatible with these "
                                     "settings. Please use svccfg to change "
                                     "the %(prop)s property of the %(svc)s "
                                     "service to migrate to the %(desired)s "
                                     "directory.")
                                      % {'svc': TFTP_FMRI,
                                         'dir': inet_start[-1],
                                         'desired': com.BOOT_DIR,
                                         'prop': INET_START_PROP}))

        setprop = [SVCCFG, '-s', TFTP_FMRI, 'setprop', 'inetd_start/exec', '=',
                   INET_START % com.BOOT_DIR]
        with SetUIDasEUID():
            Popen.check_call(setprop)
            Popen.check_call([SVCADM, 'refresh', TFTP_FMRI])

    with SetUIDasEUID(): 
        Popen.check_call([SVCADM, 'enable', TFTP_FMRI])


def enable_instance():
    ''' Enable the Automated Installer SMF service.

    This function is roughly analogous to smf_enable_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        ServicesError if service fails to transition to
        'ONLINE' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.log(com.XDEBUG, '**** START ai_smf_service.enable_instance ****')
    
    _start_tftpd()
    _set_instance('ENABLE', ('ONLINE',))


def restore_instance():
    ''' Restore the Automated Installer SMF service.

    This function is roughly analogous to smf_restore_instance(3SCF)

    Input:
        None
    Return:
        None
    Raises:
        ServicesError if service fails to transition to
        'DISABLED' within reasonable time.
        Whatever exceptions AISCF encounters

    '''
    logging.log(com.XDEBUG, '**** START ai_smf_service.restore_instance ****')
    _set_instance('RESTORE', ('DISABLED', 'OFFLINE', 'ONLINE'))


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
        ServicesError if current state of service is
        unexpected.

    '''
    logging.log(com.XDEBUG, "**** START ai_smf_service."
                "service_enable_attempt ****")

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
        raise ServicesError(
            _('Error: unexpected state for install server: %s') % orig_state)


def get_imagedir():
    ''' get value of default image basedir from AI SMF service '''

    getprop = [SVCPROP, '-p', com.BASEDIR_PROP, com.SRVINST]
    try:
        svcprop_popen = Popen.check_call(getprop, stdout=Popen.STORE,
                                         stderr=Popen.DEVNULL)
        imagedir = svcprop_popen.stdout.strip()
    except CalledProcessError:
        imagedir = com.IMAGE_DIR_PATH
    return imagedir

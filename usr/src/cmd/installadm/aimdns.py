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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
''' Auto Installer mDNS and DNS Service Discovery class and application.
'''
import atexit
import gettext
from optparse import OptionParser
import os
import pybonjour as pyb
import select
import signal
import subprocess
import sys
import osol_install.auto_install.installadm_common as common
import osol_install.libaimdns as libaimdns
import osol_install.libaiscf as smf
import osol_install.netif as netif

# location of the process ID file
PIDFILE = '/var/run/aimdns'
REMOVE_PID = False
MASK_TUPLE = (0, 128, 192, 224, 240, 248, 252, 254, 255)


def _convert_ipv4(ip):
    '''Converts an IPv4 address into an integer
       Args:
            ip - IPv4 address to convert

       Returns:
            an integer of the converted IPv4 address

       Raises:
            None
    '''
    seg = ip.split('.')
    return (int(seg[3]) << 24) + (int(seg[2]) << 16) + \
            (int(seg[1]) << 8) + int(seg[0])


def _convert_cidr_mask(cidr_mask):
    '''Converts a CIDR mask into an IPv4 mask
        Args:
            cidr_mask - CIDR mask number

        Returns:
            IPv4 mask address

        Raises:
            None
    '''
    # edge cases
    if cidr_mask > 32:
        return None
    if cidr_mask == 0:
        return '0.0.0.0'

    mask = ['255'] * (cidr_mask // 8)

    if len(mask) != 4:
        # figure out the partial octets
        index = cidr_mask % 8
        mask.append(str(MASK_TUPLE[index]))

    if len(mask) != 4:
        mask.extend(['0'] * (3 - (cidr_mask // 8)))

    # join the mask array together and return it
    return '.'.join(mask)


def compare_ipv4(ipv4_one, ipv4_two):
    '''Compares two IPv4 address
       Args:
           ipv4_one - IPv4 address, can contain CIDR mask
           ipv4_two - IPv4 address, can contain CIDR mask

       Returns:
           True if ipv4_one equals ipv4_two else
           False

       Raises:
           None
    '''
    # ensure there is no '/' (slash) in the first address,
    # effectively ignoring the CIDR mask.
    slash = ipv4_one.find('/')
    if '/' in ipv4_one:
        ipv4_one = ipv4_one[:slash]
    ipv4_one_num = _convert_ipv4(ipv4_one)

    # convert ipv4_two taking into account the possible CIDR mask
    if '/' not in ipv4_two:
        mask_two = _convert_cidr_mask(0)
        ipv4_two_num = _convert_ipv4(ipv4_two)
    else:
        mask_two = _convert_cidr_mask(int(ipv4_two.split('/')[-1]))
        if not mask_two:
            return False  # invalid mask
        ipv4_two_num = _convert_ipv4(ipv4_two.split('/')[0])
    mask_two_num = _convert_ipv4(mask_two)

    if '/' in ipv4_two and \
         mask_two_num & ipv4_two_num == mask_two_num & ipv4_one_num:
        return True
    elif ipv4_one_num == ipv4_two_num:
        return True

    return False


def in_networks(inter_ipv4, networks):
    '''Description:
        Checks to see if a single IPv4 address is in the list of
        networks

    Args:
        inter_ipv4 - an interface IPv4 address
        networks   - a list of networks from the SMF property networks

    Returns:
        True if the interface's IPv4 address is in the network -- OR --
        False if it is not

    Raises:
        None
    '''
    # iterate over the network list
    for network in networks:
        # check if the interface's IPv4 address is in the network
        if compare_ipv4(inter_ipv4, network):
            return True
    return False


class AIMDNSError(Exception):
    ''' Class for reporting AI mDNS issues
    '''
    pass


class AImDNS(object):
    ''' Class: AImDNS - base class for registering, browsing and looking up
                        AI and ad hoc mDNS records.
    '''
    # a _handle_event() loop control variable, used to restart the loop
    # after modification to the self.sdrefs variable, private
    _restart_loop = False

    # find/browse mode variables, private
    _do_lookup = False
    _found = False

    # mDNS record resolved variable, used as a stack to indicate that the
    # service has been found, private
    _resolved = []

    def __init__(self, servicename=None, domain='local', comment=None):
        '''Method: __init__, class private
           Parameters:
                        servicename - the AI servicename
                        domain      - the domain for the registered service
                        comment     - the text comment for the service
           Raises:
               AImDNSError - when unable to retrieve setup information from
                             the host about the available interfaces or the
                             AI SMF service.
        '''
        # find sdref handle
        self._find = None
        self._lookup = False
        self.services = {}
        self.servicename = servicename
        self.domain = domain
        self.txt = comment
        self.inter = None
        self.port = 0
        self.verbose = False
        self.timeout = 5
        self.done = False

        self.sdrefs = {}

        self.interfaces = libaimdns.getifaddrs()
        self.exclude = libaimdns.getboolean_property(common.SRVINST,
                                                     common.EXCLPROP)
        self.networks = libaimdns.getstrings_property(common.SRVINST,
                                                      common.NETSPROP)

        self.instance = None
        self.instance_services = None

    def __del__(self):
        '''Method: __del__
           Parameters:
                None

           Raises:
                None
        '''
        self.done = True
        self.clear_sdrefs()

    # pylint: disable-msg=W0613
    # disabled for sdref, flags
    def _resolve_callback(self, sdref, flags, interfaceindex, errorcode,
                          fullname, hosttarget, port, txtrecord):
        '''Method: _resolve_callback, class private
        Description:
            DNS Callback for the resolve process, stories the service
            information within the self.services variable.

        Args
            sdref          - service reference,
                             standard argument for callback, not used
            flags          - flag to determine what action is taking place
                             standard argument for callback, not used
            interfaceindex - the index for the interface that the service was
                             found on
            errorcode      - flag to determine if a registration error occurred
            fullname       - name of the service, should be
                             <service>._OSInstall._tcp.local.
            hosttarget     - name of the host, should be <nodename>.local.
            port           - the service port being used
            txtrecord      - the text record associated with the service,
                             standard argument for callback

        Returns
            None

        Raises
            None
        '''
        # handle errors from within the _browse_callback
        # after the select() call
        if errorcode == pyb.kDNSServiceErr_NoError:
            self._found = True
            # get the interface name for the index
            interface = netif.if_indextoname(interfaceindex)
            # interested in the service name and the domain only
            parts = fullname.split('.')
            service = {}
            service['flags'] = not (flags & pyb.kDNSServiceFlagsAdd)
            service['hosttarget'] = hosttarget
            service['servicename'] = parts[0]
            service['domain'] = parts[-2]
            service['port'] = port
            service['comments'] = str(pyb.TXTRecord.parse(txtrecord))[1:]
            self.services.setdefault(interface, []).append(service)

            # update the resolve stack flag
            self._resolved.append(True)
    # pylint: enable-msg=W0613

    # pylint: disable-msg=W0613
    # disabled for sdref, flags
    def _browse_callback(self, sdref, flags, interfaceindex, errorcode,
                         servicename, regtype, replydomain):
        '''Method: _browse_callback, class private
        Description:
            DNS Callback for the browse process

        Args
            sdref          - service reference,
                             standard argument for callback, not used
            flags          - flag to determine what action is taking place
                             standard argument for callback, not used
            interfaceindex - the index for the interface that the service was
                             found on
            errorcode      - flag to determine if a registration error occurred
            servicename    - name of the service
            hosttarget     - name of the host, should be <nodename>.local.
            regtype        - registration type, should be _OSInstall._tcp.
            replydomain    - DNS domain, either local or remote

        Returns
            None

        Raises
            None
        '''
        if errorcode != pyb.kDNSServiceErr_NoError:
            return  # error handled in the _handle_event() method

        if self._lookup and servicename != self.servicename:
            return

        resolve_sdref = pyb.DNSServiceResolve(0, interfaceindex,
                                              servicename, regtype,
                                              replydomain,
                                              self._resolve_callback)

        # wait for and process resolve the current request
        try:
            while not self._resolved:
                try:
                    ready = select.select([resolve_sdref], [], [],
                                           self.timeout)
                except select.error:
                    # purposely ignore errors.
                    continue

                if resolve_sdref not in ready[0]:
                    # not a catastrophic error for the class, therefore,
                    # simply warn that the mDNS service record needed
                    # additional time to process and do not issue an
                    # exception.
                    sys.stderr.write(_('warning:unable to resolve "%s", '
                                       'try using a longer timeout\n') %
                                       servicename)
                    break
                # process the service
                pyb.DNSServiceProcessResult(resolve_sdref)
            else:
                self._resolved.pop()
        # allow exceptions to fall through
        finally:
            # clean up when there is no exception
            resolve_sdref.close()
    # pylint: enable-msg=W0613

    def _handle_events(self):
        ''' Method: __handle_events, class private
            Description:
                Handle the event processing for the registered service
                requests.

            Args
                None

            Returns
                None

            Raises
                None
        '''
        self.done = False
        while not self.done:
            # The self.sdrefs is a dictionary of the form:
            #
            #   for the find mode:
            #       { 'find':[list of sdrefs] }
            #
            #   OR for the browse mode:
            #       { 'browse':[list of sdrefs] }
            #
            #   OR for the register mode:
            #       { <service-name>:[list of sdrefs] }
            #
            #   OR for the register all mode:
            #       { <service-name1>:[list of sdrefs],
            #         <service-name2>:[list of sdrefs],
            #         ... }
            #
            # This must be converted to a simple list of sdrefs for the
            # select() call.
            therefs = []
            # iterate through the dictionary
            for srv in self.sdrefs:
                for refs in self.sdrefs.get(srv, []):
                    if refs is not None:
                        therefs.append(refs)

            # loop until done or we need to redo the service reference
            # list mentioned above.  The service reference list will be
            # updated when the SMF service is refreshed which sends a
            # SIGHUP to the application in daemon mode.  This processing
            # of the SIGHUP is done in the signal_hup() method below.
            self._restart_loop = False
            count = 0
            while not self._restart_loop and not self.done:
                try:
                    # process the appropriate service reference
                    try:
                        ready = select.select(therefs, [], [], self.timeout)
                    except select.error:
                        continue
                    if self.done:
                        continue

                    for sdref in therefs:
                        if sdref in ready[0]:
                            pyb.DNSServiceProcessResult(sdref)

                    # if browse or find loop only 5 times, less then 5 times
                    # might cause registered mDNS records to not be retrieved.
                    if self._do_lookup is True:
                        count += 1
                        if count == 5:
                            self.done = True

                # <CTL>-C will exit the loop, application
                # needed for command line invocation
                except KeyboardInterrupt:
                    self.done = True

    # pylint: disable-msg=W0613
    # disabled for sdref, flags
    def _register_callback(self, sdref, flags, errorcode, name,
                           regtype, domain):
        '''Method: _register_callback, private to class
           Description:
                DNS Callback for the registration process

            Args
                sdref       - service reference
                              standard argument for callback, not used
                flags       - flag to determine what action is taking place
                              standard argument for callback, not used
                errorcode   - flag to determine if a registration error
                              occurred
                name        - name of the service
                regtype     - registration type, should be _OSInstall._tcp.
                domain      - DNS domain, either local or remote

            Returns
                None

            Raises
                None
        '''
        # note: DNSService Errors are ignored here and handled elsewhere.
        if errorcode == pyb.kDNSServiceErr_NoError and \
           self.verbose:
            print _('Registered service:')
            print _('\tname    = %s') % name
            print _('\tregtype = %s') % regtype
            print _('\tdomain  = %s') % domain
    # pylint: enable-msg=W0613

    def _register_a_service(self, name, interfaces=None, port=0,
                            comments=None):
        '''Method: _register_a_service, private to class

        Description:
            Register a single service on the interfaces

        Args
            interfaces - the interfaces to register the service on
            instance   - the SMF service instance handle
            name       - the service name to be registered
            port       - the port that the service is listening on, if
                         port is 0 then registering a service listed in
                         the AI SMF service instance.
            comments   - comments for the ad hoc registered service

        Returns
            list_sdrefs - list of service references

        Raises
            AImDNSError - if SMF status property does not exist, OR
                          if SMF txt_record property does not exist, OR
                          if SMF port property does not exist.
        '''
        smf_port = None
        # if port is 0 then processing an AI service
        if port is 0:
            try:
                serv = smf.AIservice(self.instance, name)
            except KeyError:
                raise AIMDNSError(_('error:aiMDNSError:no such install '
                                    'service "%s"') % name)

            # ensure the service is enabled
            if 'status' not in serv.keys():
                raise AIMDNSError(_('error:aiMDNSError:SMF service key '
                                    '"status" property does not exist'))

            if serv['status'] != 'on':
                print _('warning:Install service "%s" is not enabled') % name
                return None

            # get the port number for the service, will change with the
            # new AI Webserver design.
            if 'txt_record' not in serv.keys():
                raise AIMDNSError(_('error:aiMDNSError:SMF service key '
                                    '"txt_record" property does not exist'))

            # serv['txt_record'] = aiwebserver=<host>:<port>
            # for port split at ':'
            if serv['txt_record'].startswith('aiwebserver='):
                smf_port = serv['txt_record'].split(':')[-1]
            else:
                try:
                    smf_port = libaimdns.getinteger_property(common.SRVINST,
                                                             common.PORTPROP)
                    smf_port = str(smf_port)
                except libaimdns.aiMDNSError, err:
                    raise AIMDNSError(_('error:aiMDNSError:port property '
                                        'failure (%s)') % err)

        # iterate over the interfaces saving the service references
        list_sdrefs = []
        for inf in interfaces:
            # check the interface IP address against those listed in
            # the AI service SMF networks property.  Our logic for the
            # SMF exclude_networks and SMF networks list is:
            #
            #   IF ipv4 is in networks and
            #      SMF exclude_networks == false
            #   THEN include ipv4
            #   IF ipv4 is not in_networks and
            #      SMF exclude_network == true
            #   THEN include ipv4
            #   IF ipv4 is in_networks and
            #      SMF exclude_networks == true
            #   THEN exclude ipv4
            #   IF ipv4 is not in_networks and
            #      SMF exclude_network == false
            #   THEN exclude ipv4
            #
            # Assume that it is excluded and check the first 2 conditions only
            # as the last 2 conditions are covered by the assumption.
            in_net = in_networks(interfaces[inf], self.networks)
            include_it = False
            if (in_net and not self.exclude) or (not in_net and self.exclude):
                include_it = True

            if not include_it:
                continue

            if self.verbose:
                print _('Registering %s on %s (%s)') % \
                        (name, inf, interfaces[inf])

            if smf_port is not None:
                # comments are part of the service record
                commentkey = serv['txt_record'].split('=')[0]
                commenttxt = interfaces[inf].split('/')[0] + ':' + smf_port
                text = pyb.TXTRecord({commentkey: commenttxt})
                try:
                    port = int(smf_port)
                except ValueError:
                    # not a catastrophic error, just
                    # assume the default port of 5555.
                    port = common.DEFAULT_PORT
            # processing an ad hoc registration
            elif comments is None:
                adhoc_dict = {'service': 'ad hoc registration'}
                text = pyb.TXTRecord(adhoc_dict)
            else:
                text = pyb.TXTRecord({'service': comments})

            # register the service on the appropriate interface index
            try:
                interfaceindex = netif.if_nametoindex(inf)
            except netif.NetIFError, err:
                raise AIMDNSError(err)

            sdref = pyb.DNSServiceRegister(name=name,
                                           interfaceIndex=interfaceindex,
                                           regtype=common.REGTYPE,
                                           port=port,
                                           callBack=self._register_callback,
                                           txtRecord=text)

            # save the registered service reference
            list_sdrefs.append(sdref)

        return list_sdrefs

    def register(self, servicename=None, port=0, interfaces=None,
                 comments=None):
        '''Method: register
           Description:
                Registers an ad hoc service.  This method will loop until the
                the application is killed.

            Args
                servicename - the name of the ad hoc service
                port        - the port to use for the ad hoc service
                interfaces  - the interfaces to register the ad hoc service on
                comments    - the service comments for the ad hoc service

            Returns
                None

            Raises
                SystemError  - if the SMF service instance can not be loaded.
                AImDNSError  - if unable to register the service OR
                               if no servicename is present.
        '''
        self._do_lookup = False

        if servicename is not None:
            self.servicename = servicename

        if self.servicename is None:
            raise ValueError(_('must specify a service to register'))

        if self.verbose:
            print _('Registering "%s"...') % self.servicename

        # get the AI SMF service instance information
        try:
            self.instance = smf.AISCF(FMRI="system/install/server")
        except SystemError:
            raise SystemError(_("error:the system does not have the "
                                "system/install/server SMF service"))

        # use the interfaces within the class if none are passed in
        if interfaces is None:
            interfaces = self.interfaces

        sdrefs = self._register_a_service(name=self.servicename,
                                          interfaces=interfaces,
                                          port=port,
                                          comments=comments)

        if sdrefs is not None:
            self.sdrefs[servicename] = sdrefs
            self._handle_events()
        else:
            raise AIMDNSError(_('error:aiMDNSError:mDNS ad hoc registration '
                                'failed for "%s" service') % self.servicename)

    # pylint: disable-msg=W0613
    # disabled for signum, frame
    def _signal_hup(self, signum, frame):
        '''Method: _signal_hup, class private
        Description:
            Callback invoked when SIGHUP is received

        Args
            signum - standard argument for callback, not used
            frame  - standard argument for callback, not used

        Returns
            None

        Raises
            None
        '''
        # get the new service keys and iterate over them
        services = self.instance.services.keys()
        for srv in services:
            # is this service already registered
            if srv not in self.instance_services or srv not in self.sdrefs:
                # need to register the service
                if self.verbose:
                    print _('Registering %s') % srv

                sdrefs = self._register_a_service(interfaces=self.interfaces,
                                                  name=srv)

                # save the service reference list in self.sdrefs
                if sdrefs is not None:
                    # self.sdrefs update, force restart of event loop
                    self._restart_loop = True
                    if srv in self.sdrefs:
                        self.sdrefs[srv].extend(sdrefs)
                    else:
                        self.sdrefs[srv] = sdrefs

        # check the old service keys for removed or disabled services
        for srv in self.instance_services:
            # get the service (srv) from the instance
            try:
                serv = smf.AIservice(self.instance, srv)
            except KeyError:
                # not a catastrophic error for the class as additional
                # services can still be processed.  This error will be
                # caught in the service log file.
                sys.stderr.write(_('warning:No such Automated Install service '
                                   '%s\n') % srv)
                continue

            # was the service removed or disabled
            if (srv not in services) or \
               (srv in self.sdrefs and serv['status'] == 'off'):

                if self.verbose:
                    print _('Unregistering %s') % srv

                # remove the registered service
                if srv in self.sdrefs:
                    # self.sdrefs update, force restart of event loop
                    self._restart_loop = True
                    for sdref in self.sdrefs[srv]:
                        sdref.close()
                    del self.sdrefs[srv]

        # save the new services list
        self.instance_services = services
    # pylint: enable-msg=W0613

    def register_all(self, interfaces=None):
        '''Method: register_all
           Description:
                Registers all AI services.  This method will loop until the
                the application is killed.  It responds to SIGHUP signals,
                re-checking all registered services for additions and removals
                of a service from the AI SMF service.

            Args
                interfaces  - the interfaces to register the AI services on

            Returns
                None

            Raises
                SystemError  - if the SMF service instance can not be loaded.
                AIMDNSError  - if the Instance keys are not loaded.
        '''
        self._do_lookup = False

        if self.verbose:
            print _('Registering all Auto Install services...')

        # get the AI SMF service instance information
        try:
            self.instance = smf.AISCF(FMRI="system/install/server")
        except SystemError:
            raise SystemError(_("error:the system does not have the "
                                "system/install/server SMF service"))
        self.instance_services = self.instance.services.keys()
        if not self.instance_services:
            raise AIMDNSError(_('error:aiMDNSError:no services on this '
                                'server.'))

        # use interfaces within the class if none are passed
        if interfaces is None:
            interfaces = self.interfaces

        # iterate through each service and register it
        for servicename in self.instance_services:
            sdrefs = self._register_a_service(name=servicename,
                                              interfaces=interfaces)

            # save the service reference within the class
            if sdrefs:
                if servicename in self.sdrefs:
                    self.sdrefs[servicename].extend(sdrefs)
                else:
                    self.sdrefs[servicename] = sdrefs

        signal.signal(signal.SIGHUP, self._signal_hup)
        self._handle_events()

    def browse(self):
        '''Method: browse
        Description:
            browse all available _OSInstall._tcp services.

        Args
            None

        Returns
                True  -- if a service is found -- OR --
                False -- if a service is not found -- OR --
                sdref -- if actually in find mode

        Raises
            AImDNSError - if there are no service references available
        '''
        self.sdrefs = {}
        self._found = False
        self._resolved = []

        if self.verbose:
            print _('Browsing for services...')

        # pybonjour bug -- can not Browse on a specific interfaceIndex
        # thus only Browsing on all interfaces (0).  If and when this
        # bug gets fixed up stream then the iteration over the interfaces
        # would be appropriate.  The code should look like what is in
        # the find() method.
        # Resolve the DNS service
        sdref = pyb.DNSServiceBrowse(flags=0, regtype=common.REGTYPE,
                                     domain=common.DOMAIN,
                                     interfaceIndex=0,
                                     callBack=self._browse_callback)

        # save the service reference
        if sdref:
            self.sdrefs['browse'] = [sdref]
        else:
            raise AIMDNSError(_('error:aiMDNSError:mDNS browse failed'))

        # cause the event loop to loop only 5 times
        self._do_lookup = True
        self._handle_events()

        return self._found

    def find(self, servicename=None):
        ''' Method: find
            Description:
                finds the named Auto Install service

            Returns:
                True  -- if the service is found -- OR --
                False -- if the service is not found

            Raises:
                AImDNSError - if there are no service references available
        '''
        self.sdrefs = {}
        self._found = False
        self._lookup = True
        self.servicename = servicename if servicename else self.servicename

        if self.verbose:
            print _('Finding %s...') % self.servicename

        return self.browse()

    def print_services(self):
        '''Method: print_services
        Description:
            Prints the class services dictionary.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        # ensure service list is not blank
        if not self.services:
            if self.verbose:
                print _('"%s" service not found') % self.servicename
            else:
                print _('-:%s') % self.servicename
        else:
            # iterate through the interfaces
            for inter in self.services.keys():
                services = self.services[inter]
                # iterate through the services for the interface
                for service in services:
                    if self.verbose:
                        # save all labels
                        labels = [_('fullname'), _('hosttarget'),
                                  _('port'), _('interface')]
                        if service['comments'].startswith('aiwebserver='):
                            comlabel = service['comments'].split('=')[0]
                            comvalue = service['comments'].split('=')[1]
                        else:
                            comlabel = _('comment')
                            comvalue = service['comments']
                        labels.append(comlabel)
                        # figure out the maximum width of the labels
                        maxlen = max([len(l) for l in labels])
                        # output the label = value, labels are right justified
                        print _('Service:')
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('fullname'), \
                                 service['servicename'])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('hosttarget'), \
                                 service['hosttarget'])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('port'), \
                                 service['port'])
                        print '\t%-*.*s = %s (%s)' % \
                                (maxlen, maxlen, _('interface'), inter, \
                                 self.interfaces[inter])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, comlabel, comvalue)
                    else:
                        # output +:interface:IPv4:domain:servicename:port
                        flag = '+' if service['flags'] is True else '-'
                        print '%s:%s:%s:%s:%s:%d:%s' % \
                                (flag, inter, self.interfaces[inter], \
                                 service['domain'], service['servicename'], \
                                 service['port'], service['comments'])

    def reset(self):
        '''Method: reset
        Description:
            Resets all the class member variables to defaults.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        self._find = None
        self.services = {}
        self.servicename = None
        self.domain = 'local'
        self.txt = None
        self.inter = None
        self.port = 0
        self._found = False
        self._lookup = False
        self.clear_sdrefs()

    def clear_sdrefs(self):
        '''Method: clear_sdrefs
        Description:
            Clears the mDNS service description references.  The side effect
            is that the mDNS records are also de-registered.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        for srv in self.sdrefs.keys():
            for sdref in self.sdrefs[srv]:
                sdref.close()
        self.sdrefs = {}


def parse_options():
    '''Parses and validate options

    Args
        None

    Globals
        VERSION - version number of the program, used

    Returns
        a dictionary of the valid options

            {
                'verbose':Bool,
                'interface':interface_name (i.e., iwh0),
                'comment':string (comment for the server),
                'timeout':time (length of time to wait per request),
                'service':SName (service name to find),
                'browse':Bool (browse mode),
                'register':SName (service name to register),
                'port':port (port number for the service),
                'all':Bool (register all services)
            }

    Raises
        None
    '''
    desc = _("Multicast DNS (mDNS) & DNS Service Directory Automated "
                "Installations utility. "
                "Or with -f option, Find a service. "
                "Or with -b option, Browse the services. "
                "Or with -r option, Register a service. "
                "Or with -a option, Register All AI services. "
                "Or with -i option, Browse, Find, Register on a "
                "specific interface. "
                "Or with -c option, Comment for a mDNS record(s) being "
                "registered. "
                "Or with -t option, set the timeout for the operation. "
                "Or with -p option, set the port number for the registration. "
                "Or with -v option, Verbose output.")

    usage = _("usage: %prog [[-v][-i <interface>][-t <timeout>]]\n"
                "\t[-f <servicename>] |\n"
                "\t[-b] |\n"
                "\t[-r <servicename> -p <port>] [[-c comment]] |\n"
                "\t[-a]")

    parser = OptionParser(usage=usage, description=desc)

    parser.add_option('-v', '--verbose', dest='verbose', default=False,
                      action='store_true',
                      help=_('turn on verbose mode'))

    parser.add_option('-i', '--interface', dest='interface', default=None,
                      type='string',
                      help=_('interface to browse, find or register on'))

    parser.add_option('-c', '--comment', dest='comment', default=None,
                      type='string',
                      help=_('comment used in service registration'))

    parser.add_option('-t', '--timeout', dest='timeout', default=None,
                      type='int',
                      help=_('set the timeout for the operation'))

    parser.add_option('-p', '--port', dest='port', default=None,
                      type='int',
                      help=_('set the port for the ad hoc registration'))

    parser.add_option("-f", "--find", dest="service", default=None,
                      type="string",
                      help=_("find a named service"))

    parser.add_option("-b", "--browse", dest="browse", default=False,
                      action="store_true",
                      help=_("browse the services"))

    parser.add_option("-r", "--register", dest="register", default=None,
                      type="string",
                      help=_("register a service, root privileges required"))

    parser.add_option("-a", "--all", dest="all", default=False,
                      action="store_true",
                      help=_("register all the services, root "
                              "privileges required"))

    (loptions, args) = parser.parse_args()

    if args:
        parser.error(_('unknown argument(s): %s') % args)

    if loptions.all is True or loptions.register is not None:
        # check that we are root
        if os.geteuid() != 0:
            parser.error(_('root privileges required with the "%s" '
                          'operation.') % \
                          ('-a' if loptions.all else '-r'))

    if [bool(loptions.browse), bool(loptions.all), bool(loptions.register),
        bool(loptions.service)].count(True) > 1:
        parser.error(_('"-f", "-b", "-r" and "-a" operations are mutually '
                       'exclusive.'))

    if not loptions.browse and not loptions.all and \
       not loptions.register and not loptions.service:
        parser.error(_('must specify an operation of "-f", "-b", '
                       '"-r" or "-a".'))

    if loptions.register and not loptions.port:
        parser.error(_('must specify a "port" for the "-r" operation.'))

    if not loptions.register and loptions.port:
        parser.error(_('"-p" option only valid for the "-r" operation.'))

    if not loptions.register and loptions.comment:
        parser.error(_('"-c" option only valid for the "-r" operation.'))

    return loptions


def store_pid():
    '''Store the process ID for registering all services.

    Args
        None

    Globals
        PIDFILE    - location to store the register PID, the PID is used by
                     installadm delete-service/create-service, used
        REMOVE_PID - flag to indicate if the PID file should be removed,
                     modified

    Returns
        None

    Raises
        None
    '''
    # pylint: disable-msg=W0603
    # modifying the REMOVE_PID global
    global REMOVE_PID
    # pylint: enable-msg=W0603

    # ensure that the PIDFILE is removed
    REMOVE_PID = True

    if os.path.exists(PIDFILE):
        with open(PIDFILE, 'r') as pidfile:
            # get the pid from the file
            try:
                pid = int(pidfile.read().strip('\n'))
                # see if aimdns is still running via pgrep
                proc = subprocess.Popen(["/usr/bin/pgrep", "aimdns"],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                (stdout, stderr) = proc.communicate()

                if stderr:
                    print stderr
                else:
                    for pgrep_pid in str(stdout).split('\n')[:-1]:
                        runpid = int(pgrep_pid)
                        if runpid == pid:
                            sys.stderr.write(_('error:aimdns already running '
                                               '(pid %d)\n') % pid)
                            sys.exit(1)
            except ValueError:
                # var/run/aimdns file left over, truncate via open it.
                pass

    with open(PIDFILE, 'w+') as pidfile:
        mystr = str(os.getpid()) + '\n'
        pidfile.write(mystr)


def remove_pid():
    '''Removes the process ID file.

    Args
        None

    Globals
        PIDFILE    - location to store the register PID, the PID is used by
                     installadm delete-service/create-service, used
        REMOVE_PID - flag to indicate if the PID file should be removed, used

    Returns
        None

    Raises
        None
    '''
    if REMOVE_PID:
        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)


# pylint: disable-msg=W0613
# disabled for frame
def on_exit(signum=0, frame=None):
    '''Callback invoked when SIGTERM is received,
       or when the program is exiting

    Args
        signum - standard argument for callback
        frame  - standard argument for callback, not used

    Globals
        None

    Returns
        None

    Raises
        None
    '''
    remove_pid()
    AIMDNS.clear_sdrefs()
    if signum == signal.SIGTERM:
        sys.exit(0)
# pylint: enable-msg=W0613


def main(aimdns):
    '''main program.

    Args
        None

    Globals
        REMOVE_PID - sets to true for registering all services operation

    Returns
        None

    Raises
        None
    '''
    atexit.register(on_exit)
    try:
        gettext.install("ai", "/usr/lib/locale")
        options = parse_options()
        comments = options.comment
        aimdns.verbose = options.verbose

        if options.timeout:
            aimdns.timeout = options.timeout

        # setup SIGTERM handling to ensure cleanup of PID file
        signal.signal(signal.SIGTERM, on_exit)

        if options.register:
            # register single service
            aimdns.register(interfaces=options.interface, port=options.port,
                            servicename=options.register, comments=comments)
        elif options.all:
            # save the PID information so that SIGHUP can be used by other apps
            store_pid()
            # register all the services
            aimdns.register_all(interfaces=options.interface)
        elif options.browse:
            # browse services
            if aimdns.browse():
                aimdns.print_services()
            else:
                if options.verbose:
                    print _('No services found')
                else:
                    print _('-:None')
                    return 1
        elif options.service:
            # find a service
            if aimdns.find(servicename=options.service):
                aimdns.print_services()
            else:
                if options.verbose:
                    print _('Service "%s" not found') % options.service
                else:
                    print _("-:%s") % options.service
                    return 1
    except AIMDNSError, err:
        print err
        return 1

    return 0

if __name__ == '__main__':
    AIMDNS = AImDNS()
    sys.exit(main(AIMDNS))